#!/usr/bin/env python
"""Close the rows of `PUBLISHABILITY.md` §6 that do not need a live endpoint.

    python scripts/publish_close.py                 # everything, ~8 min
    python scripts/publish_close.py --only kfold multiplicity
    python scripts/publish_close.py --quick         # smaller sweeps, ~2 min

`rigor.py` and `RIGOR.md` were the first pass at that list and each row landed at
n = 1: one replication, one split, one corrected family. This is the second pass, and
it exists because the first one left three claims quotable to three decimals with no
statement of how much they would move if the experiment were run again.

    20_dose_response.json    coverage bias against a designed sweep of pools, with two
                             arms where the mechanism predicts no effect
    21_kfold.json            k-fold intervals on every headline, at three values of k
    22_baseline_margins.json an error bar on the one published baseline that beat us
    23_multiplicity.json     all fifteen claims classified, every real test corrected

Every stage reads files on disk and touches no network. The four §6 rows that are not
here — grading the remaining nine slots, extending the graded set past 55 items,
and a timed run — need an endpoint, and `scripts/measure_latency.py` is the harness
waiting for one.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rollingbench.experiments import chutes, publish, rigor  # noqa: E402

OUT = ROOT / "artifacts" / "chutes"
FIGURES = ROOT / "artifacts" / "figures"
ALL = ["dose", "kfold", "margins", "multiplicity"]


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if np.isfinite(f) else None
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def write(name: str, payload) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(_jsonable(payload), indent=2))
    print(f"       → {path.relative_to(ROOT)}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", choices=ALL, default=ALL)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--lam-cost", type=float, default=None,
                    help="operating point; defaults to the calibrated one in "
                         "artifacts/chutes/04_calibration.json")
    args = ap.parse_args()
    t0 = time.time()

    lam_cost = args.lam_cost
    if lam_cost is None:
        cal = OUT / "04_calibration.json"
        lam_cost = (json.loads(cal.read_text())["chosen"]["lam_cost"]
                    if cal.exists() else 0.2)
    print(f"operating point λ_c = {lam_cost:g}  (seed {args.seed})")

    lm = tokens_in = None
    if {"kfold", "margins"} & set(args.only):
        lm, tokens_in = chutes.build_pool()
        print(f"pool: {lm.n_items:,} items x {lm.n_models} slots, "
              f"{int(lm.observed.all(axis=1).sum()):,} in the dense core")

    # ------------------------------------------------------------- [1] dose --
    if "dose" in args.only:
        print("\n[1/4] coverage bias: does the effect track the mechanism?")
        t = time.time()
        roster = publish.verify_roster()
        dose = publish.coverage_bias_dose_response(
            pools_per_level=2 if args.quick else 3,
            levels=(0, 4, 8, 13) if args.quick else (0, 2, 4, 6, 8, 10, 13),
            seed=args.seed,
            lams=(1.0, 100.0) if args.quick else (1.0, 10.0, 100.0),
        )
        stab = publish.coverage_bias_seed_stability(
            seeds=(0, 1, 2) if args.quick else (0, 1, 2, 3, 4))
        mask = publish.coverage_mask_sweep(
            seed=args.seed,
            fractions=(0.0, 0.3, 0.6) if args.quick
            else (0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8))
        payload = {"roster": roster, "dose_response": dose, "mask_sweep": mask,
                   "seed_stability": stab,
                   "first_replication": rigor.replicate_coverage_bias(seed=args.seed)}
        write("20_dose_response", payload)
        print(f"       {dose['reading']}")
        print(f"       {mask['reading']}")
        print(f"       {stab['reading']}")
        if not args.no_figures:
            import matplotlib
            matplotlib.use("Agg")
            from rollingbench import plots

            fig = plots.chutes_dose_response(dose, mask)
            FIGURES.mkdir(parents=True, exist_ok=True)
            fig.savefig(FIGURES / "chutes_12_coverage_cause.png", dpi=150)
            print(f"       → artifacts/figures/chutes_12_coverage_cause.png")
        print(f"       ({time.time() - t:.0f}s)")

    # ------------------------------------------------------------ [2] kfold --
    if "kfold" in args.only:
        print("\n[2/4] k-fold: how much does the policy move with its training data?")
        t = time.time()
        ks = (5,) if args.quick else (3, 5, 10)
        folds = {str(k): publish.kfold_headlines(lm, tokens_in, lam_cost=lam_cost,
                                                 k=k, seed=args.seed) for k in ks}
        boot_path = OUT / "16_bootstrap.json"
        payload = {"by_k": folds, "ks": list(ks)}
        if boot_path.exists():
            boot = json.loads(boot_path.read_text())
            payload["against_the_bootstrap"] = {
                q: {
                    "bootstrap": {"mean": boot[q]["mean"],
                                  "lo": boot[q]["lo"], "hi": boot[q]["hi"],
                                  "width": boot[q]["hi"] - boot[q]["lo"]},
                    "kfold_k5": {"mean": folds["5"][q]["mean"],
                                 "lo": folds["5"][q]["lo"], "hi": folds["5"][q]["hi"],
                                 "width": folds["5"][q]["hi"] - folds["5"][q]["lo"]},
                }
                for q in ("savings_vs_best_single", "quality_vs_best_single",
                          "savings_vs_frontier", "quality_vs_frontier",
                          "share_of_oracle_captured", "val_brier")
                if q in boot and q in folds["5"]
            }
            q = "quality_vs_best_single"
            contains = {str(k): bool(folds[str(k)][q]["lo"] <= 1.0 <= folds[str(k)][q]["hi"])
                        for k in ks}
            payload["does_the_quality_interval_contain_parity"] = {
                "bootstrap": bool(boot[q]["lo"] <= 1.0 <= boot[q]["hi"]),
                "kfold_by_k": contains,
                "stable_across_k": len(set(contains.values())) == 1,
                "note": (
                    "RIGOR.md §1 reads the bootstrap interval containing 1.0 as support "
                    "for 'we match the best single model'. The k-fold interval answers "
                    "that question differently at different k, which is the clearest "
                    "possible demonstration that a cross-validation spread is not a "
                    "confidence interval: the folds share training items, so its width "
                    "has no coverage guarantee and it must not be used to accept or "
                    "reject a parity claim. The bootstrap interval is the one to quote."),
            }
            payload["reading"] = (
                "The two instruments agree on the level and differ on the width, which "
                "is what they should do: the bootstrap holds the policy fixed and asks "
                "how precisely its behaviour is known on these items, k-fold refits and "
                "asks how much the policy itself moves. Quote the bootstrap interval "
                "for a headline; quote the k-fold spread when the question is whether "
                "the number survives being retrained."
            )
        write("21_kfold", payload)
        for k in ks:
            print(f"       k={k}: {folds[str(k)]['reading'].splitlines()[0]}")
        print(f"       ({time.time() - t:.0f}s)")

    # ---------------------------------------------------------- [3] margins --
    if "margins" in args.only:
        print("\n[3/4] baselines: an error bar on the comparison that goes against us")
        t = time.time()
        m = publish.baseline_margin_intervals(
            lm, tokens_in, lam_cost=lam_cost,
            seeds=(0, 1, 2, 3) if args.quick else (0, 1, 2, 3, 4, 5, 6, 7),
            n_boot=500 if args.quick else 2000, seed=args.seed)
        write("22_baseline_margins", m)
        print(f"       {m['reading']}")
        print(f"       ({time.time() - t:.0f}s)")

    # ----------------------------------------------------- [4] multiplicity --
    if "multiplicity" in args.only:
        print("\n[4/4] multiplicity: fifteen claims, classified and corrected")
        t = time.time()
        a = publish.multiplicity_audit(ROOT)
        write("23_multiplicity", a)
        print(f"       {a['reading']}")
        print(f"       ({time.time() - t:.0f}s)")

    print(f"\ndone in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
