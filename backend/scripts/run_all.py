#!/usr/bin/env python
"""Run every experiment, write every number, draw every figure.

    python scripts/run_all.py                  # everything
    python scripts/run_all.py --quick          # smaller replays, for a smoke test
    python scripts/run_all.py --only frontier staleness

Results land in `artifacts/` as JSON and `artifacts/figures/` as PNG. The notebooks
read those files rather than recomputing, so the heavy work happens once here and the
analysis stays fast to open, re-read and re-render.

Every experiment is seeded and every input is a file on disk, so two runs of this
script on the same corpus produce the same numbers.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rollingbench.catalog import CHUTES_CATALOG, ROUTERBENCH_POOL  # noqa: E402
from rollingbench.data import routerbench, tie_rate  # noqa: E402
from rollingbench.data.cache import features_for  # noqa: E402
from rollingbench.experiments import (  # noqa: E402
    coldstart_sc,
    decomposition,
    frontier,
    gram,
    metric,
    scaling,
    staleness,
)

ARTIFACTS = ROOT / "artifacts"
FIGURES = ARTIFACTS / "figures"

ALL = ["overview", "scaling", "frontier", "staleness", "gram", "metric", "coldstart",
       "decomposition"]


def _jsonable(obj):
    """NumPy scalars and arrays are not JSON, and every result dict is full of them."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        f = float(obj)
        # JSON has no inf/nan; null round-trips into every consumer we have.
        return f if np.isfinite(f) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float):
        return obj if np.isfinite(obj) else None
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    return obj


def write(name: str, payload) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / f"{name}.json"
    path.write_text(json.dumps(_jsonable(payload), indent=2))
    print(f"       → {path.relative_to(ROOT)}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="smaller replays and grids")
    ap.add_argument("--only", nargs="*", choices=ALL, default=ALL)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()
    quick = args.quick

    t_start = time.time()
    print("=" * 78)
    print("RollingBench — router engine experiments")
    print("=" * 78)

    lm = routerbench.load()
    print(f"corpus: {lm.source}")
    print(f"        {lm.n_items:,} items × {lm.n_models} models = "
          f"{int(lm.observed.sum()):,} graded cells, ${lm.cost.sum():,.2f} of measured inference")

    rng = np.random.default_rng(args.seed)
    order = rng.permutation(lm.n_items)
    n_train = int(0.685 * lm.n_items)          # ~25k train / ~11.5k test
    train, test = order[:n_train], order[n_train:]
    X, fm = features_for(lm, fit_idx=train)
    print(f"features: d={X.shape[1]} (frozen after fitting on the training split only)")
    print(f"split: {len(train):,} train / {len(test):,} test items, disjoint by item")

    figs = {}
    done = []

    # ---------------------------------------------------------------- overview --
    if "overview" in args.only:
        print("\n[1/7] overview: pool, ties, domains")
        t = time.time()
        models = frontier.model_table(lm, ROUTERBENCH_POOL)
        payload = {
            "corpus": lm.summary(),
            "ties": tie_rate(lm),
            "models": models,
            "domains": frontier.domain_table(lm),
            "solve_rate_percentiles": {
                str(p): float(np.percentile(lm.solve_rate(), p))
                for p in (0, 5, 25, 50, 75, 95, 100)
            },
            "chutes_pool": [
                {"id": m.id, "label": m.label, "tier": m.tier, "family": m.family,
                 "in_per_1m": m.in_per_1m, "out_per_1m": m.out_per_1m,
                 "blended_price": m.blended_price, "good_at": m.good_at}
                for m in CHUTES_CATALOG
            ],
        }
        write("overview", payload)
        if not args.no_figures:
            from rollingbench import plots
            figs["01_model_comparison"] = plots.model_comparison(models)
        print(f"       ties: {payload['ties']['pairwise_tie_rate']:.1%} of model pairs "
              f"score identically ({time.time() - t:.0f}s)")
        done.append("overview")

    # ----------------------------------------------------------------- scaling --
    if "scaling" in args.only:
        print("\n[2/8] scaling: loss against data, capacity, regularisation — and regret")
        t = time.time()
        res = scaling.run(lm, X, train, test, ROUTERBENCH_POOL, quick=quick, seed=args.seed)
        write("scaling", res)
        if not args.no_figures:
            from rollingbench import plots
            figs["10_loss_curves"] = plots.loss_curves(res)
            figs["11_loss_vs_routing"] = plots.loss_vs_routing(res)
            figs["12_per_model_loss"] = plots.per_model_loss(res)
        sm = res["summary"]
        print(f"       data: val Brier {sm['data']['val_brier_by_size'][0]:.4f} → "
              f"{sm['data']['val_brier_by_size'][-1]:.4f}; last doubling buys "
              f"{sm['data']['gain_from_last_doubling']:+.5f}")
        print(f"       capacity: best d={sm['capacity']['best_d']} "
              f"(Brier {sm['capacity']['best_val_brier']:.5f}), "
              f"saturates at d={sm['capacity']['saturates_at_d']}")
        print(f"       coupling: Brier↔regret r={res['coupling']['corr_val_brier_regret']:+.2f}, "
              f"ranking↔regret r={res['coupling']['corr_ranking_loss_regret']:+.2f} "
              f"({time.time() - t:.0f}s)")
        done.append("scaling")

    # ---------------------------------------------------------------- frontier --
    if "frontier" in args.only:
        print("\n[3/8] frontier: the cost/quality dial, and every policy compared")
        t = time.time()
        lambdas = ([0.0, 0.02, 0.05, 0.1, 0.2] if quick else
                   [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0])
        sweep = frontier.sweep_lambda_cost(lm, X, train, test, ROUTERBENCH_POOL, lambdas)
        policies = frontier.policy_comparison(lm, X, train, test, ROUTERBENCH_POOL,
                                              lam_cost=0.05, seed=args.seed)
        write("frontier", {"sweep": sweep, "policies": policies})
        if not args.no_figures:
            from rollingbench import plots
            figs["02_frontier"] = plots.frontier(sweep)
        at5 = next(r for r in sweep if abs(r["lam_cost"] - 0.05) < 1e-9)
        print(f"       λ_c=0.05: {at5['savings_vs_frontier']:.1%} cheaper at "
              f"{at5['quality_vs_frontier']:.1%} of frontier quality ({time.time() - t:.0f}s)")
        done.append("frontier")

    # --------------------------------------------------------------- staleness --
    if "staleness" in args.only:
        print("\n[4/8] staleness (§14.1): the experiment that could invalidate the premise")
        t = time.time()
        cfg = staleness.StalenessConfig(
            weeks=14 if quick else 26,
            batch_items=300 if quick else 400,
            seed=args.seed,
        )
        res = staleness.run(lm, X, ROUTERBENCH_POOL, cfg)
        summary = staleness.summarise(res)
        write("staleness", {"result": res.as_dict(), "summary": summary})
        if not args.no_figures:
            from rollingbench import plots
            figs["03_staleness"] = plots.staleness(res.as_dict())
            figs["04_staleness_quality"] = plots.staleness_quality(res.as_dict())
        print(f"       frozen {summary['frozen_start']:+.3f} → {summary['frozen_end']:+.3f}; "
              f"rolling {summary['rolling_start']:+.3f} → {summary['rolling_end']:+.3f}")
        print(f"       attribution: new models {summary['attribution_new_models']:+.3f}, "
              f"fresher data {summary['attribution_fresher_data']:+.3f}")
        print(f"       VERDICT: {summary['verdict']} ({time.time() - t:.0f}s)")
        done.append("staleness")

    # -------------------------------------------------------------------- gram --
    if "gram" in args.only:
        print("\n[5/8] gram: what §8.3's shared-matrix shortcut costs")
        t = time.time()
        cov = (1.0, 0.5, 0.1, 0.02) if quick else (1.0, 0.5, 0.25, 0.1, 0.05, 0.02, 0.01)
        res = gram.run(lm, X, train, test, ROUTERBENCH_POOL, coverages=cov, seed=args.seed)
        write("gram", res)
        if not args.no_figures:
            from rollingbench import plots
            figs["05_gram"] = plots.gram(res)
        print(f"       worst utility gap {res['summary']['worst_utility_gap']:+.4f}; "
              f"shortcut starts costing at coverage "
              f"{res['summary']['coverage_where_shortcut_costs']} ({time.time() - t:.0f}s)")
        done.append("gram")

    # ------------------------------------------------------------------ metric --
    if "metric" in args.only:
        print("\n[6/8] metric (7.3): both degeneracies in the §8.8 score")
        t = time.time()
        res = metric.run(lm, X, train, test, ROUTERBENCH_POOL,
                         n_batches=150 if quick else 400,
                         batch_items=100, seed=args.seed)
        sens = metric.kappa_sensitivity(res)
        trade = metric.kappa_tradeoff(res)
        write("metric", {"result": res, "kappa_sensitivity": sens, "kappa_tradeoff": trade})
        if not args.no_figures:
            from rollingbench import plots
            figs["06_metric"] = plots.metric_degeneracy(res)
            figs["07_kappa"] = plots.kappa_tradeoff(sens, trade)
        print(f"       oracle luck: {res['oracle_luck']['mean_luck_share_of_gap']:.1%} of the gap")
        print(f"       ranking: raw {res['ranking']['overall']['raw_concordance']:.3f} → "
              f"shrunk {res['ranking']['overall']['shrunk_concordance']:.3f} "
              f"({time.time() - t:.0f}s)")
        done.append("metric")

    # ---------------------------------------------------------------- coldstart --
    if "coldstart" in args.only:
        print("\n[7/8] coldstart (7.4 then 7.2): the bridge, then sample complexity")
        t = time.time()
        bridge = coldstart_sc.bridge_check(
            lm, X, train, n_lowrank_items=2000 if quick else 4000, seed=args.seed)
        print(f"       bridge R²={bridge['bridge_r2']:.3f} → {bridge['verdict']}")
        grid = (0, 25, 100, 500) if quick else coldstart_sc.PROBE_GRID
        lomo = coldstart_sc.leave_one_model_out(
            lm, X, train, test[:8000], ROUTERBENCH_POOL,
            probe_grid=grid, n_lowrank_items=2000, seed=args.seed)
        write("coldstart", {"bridge": bridge, "lomo": lomo})
        if not args.no_figures:
            from rollingbench import plots
            figs["08_coldstart"] = plots.coldstart(lomo)
        print(f"       probe items needed (models with a material gap): "
              f"{lomo['summary']['median_probe_items_material']} ({time.time() - t:.0f}s)")
        done.append("coldstart")

    # ----------------------------------------------------------- decomposition --
    if "decomposition" in args.only:
        print("\n[8/8] decomposition (7.1): component-wise γ, and read-vs-learn")
        t = time.time()
        cfg = decomposition.ShockConfig.default(lm)
        if quick:
            cfg.weeks, cfg.batch_items = 20, 300
        single = decomposition.run(lm, X, ROUTERBENCH_POOL, cfg,
                                   gamma_shared=1.0, gamma_quality=1.0, gamma_tokens=0.99)
        seeds = (0, 1, 2) if quick else (0, 1, 2, 3, 4, 5, 6, 7)
        reps = {
            regime: decomposition.replicate(lm, X, ROUTERBENCH_POOL, regime=regime,
                                            seeds=seeds)
            for regime in ("default", "high_drift")
        }
        tuning = None if quick else decomposition.tune_gammas(lm, X, ROUTERBENCH_POOL, cfg)
        write("decomposition", {"replay": single, "replication": reps, "gamma_tuning": tuning})
        if not args.no_figures:
            from rollingbench import plots
            figs["09_decomposition"] = plots.decomposition(single)
        for regime, r in reps.items():
            print(f"       {regime}: {r['decomposition']['reading']}")
        print(f"       ({time.time() - t:.0f}s)")
        done.append("decomposition")

    # ----------------------------------------------------------------- figures --
    if figs and not args.no_figures:
        from rollingbench import plots
        written = plots.save_all(figs, FIGURES)
        print(f"\nfigures: {len(written)} written to {FIGURES.relative_to(ROOT)}/")

    # Merge rather than overwrite, so `--only` does not erase the record of a full run.
    previous = {}
    mpath = ARTIFACTS / "manifest.json"
    if mpath.exists():
        try:
            previous = json.loads(mpath.read_text())
        except json.JSONDecodeError:
            previous = {}
    manifest = {
        **previous,
        "ran": sorted(set(previous.get("ran", [])) | set(done)),
        "ran_this_invocation": done,
        "quick": quick,
        "seed": args.seed,
        "corpus": lm.summary(),
        "feature_dim": int(X.shape[1]),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "elapsed_seconds": round(time.time() - t_start, 1),
    }
    write("manifest", manifest)
    print(f"\ndone in {manifest['elapsed_seconds']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
