"""Route over the real pool, and price it at Chutes rates.

`export_graded.py` answers "how wrong was the stand-in". This answers the other
question the graded run buys: what routing is worth on a pool where **no column is a
proxy**. Everything here — every score, every token count — was measured on the actual
checkpoint. It is the first number in this repository that carries no binding
assumption at all.

The pool is four models, not thirteen, because that is what the endpoint would serve
us (see `grade_fireworks.MAPPING`). A four-model pool understates what routing is worth
— less spread to exploit, and the two cheapest slots in the real catalogue are absent —
so treat the savings here as a floor for the thirteen-model product, not an estimate of
it. What it is *not* is proxy-backed, which is the whole point.

The same code path as the proxy pool: same feature map, same router, same metrics,
same split. Only the matrix underneath is different, which is what makes the two
comparable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rollingbench.catalog import CHUTES_CATALOG, by_id  # noqa: E402
from rollingbench.data.cache import features_for  # noqa: E402
from rollingbench.data.labelmatrix import LabelMatrix  # noqa: E402
from rollingbench.data.llmrouterbench import _DOMAIN_OF  # noqa: E402
from rollingbench.experiments import chutes  # noqa: E402
from rollingbench.metrics import best_single_column  # noqa: E402

GRD = ROOT / "artifacts" / "grading"


def build() -> tuple[LabelMatrix, np.ndarray]:
    z = np.load(GRD / "matrix.npz", allow_pickle=True)
    slots = [str(s) for s in z["model_ids"]]
    tin, tout, q = z["tokens_in"], z["tokens_out"], z["quality"]
    task = np.array([str(t) for t in z["task"]])

    # Price is read, never fitted: measured tokens x the Chutes list price. Identical
    # to build_pool's treatment, so the two pools are priced the same way.
    pin = np.array([by_id(CHUTES_CATALOG, s).in_per_1m for s in slots])
    pout = np.array([by_id(CHUTES_CATALOG, s).out_per_1m for s in slots])
    cost = tin / 1e6 * pin[None, :] + tout / 1e6 * pout[None, :]

    items = {i["key"]: i for i in json.loads((GRD / "items.json").read_text())["items"]}
    keys = [str(k) for k in z["item_keys"]]
    lm = LabelMatrix(
        item_ids=np.array(keys, dtype=object),
        model_ids=slots,
        quality=q.astype(np.float64),
        cost=cost,
        observed=np.ones_like(q, dtype=bool),
        tokens_out=tout.astype(np.float64),
        prompts=np.array([items[k]["prompt"] for k in keys], dtype=object),
        task=task,
        domain=np.array([_DOMAIN_OF.get(t, "other") for t in task]),
        source="Fireworks serverless — real checkpoints, no proxy",
        notes=["quality and tokens MEASURED on the real checkpoint",
               "cost = measured tokens x published Chutes price",
               "four of thirteen slots: the rest are not serverless on Fireworks"],
    )
    return lm, tin


def main() -> None:
    lm, tokens_in = build()
    print(f"real pool: {lm.n_items:,} items x {lm.n_models} models "
          f"({lm.n_items * lm.n_models:,} graded cells, all measured)\n")

    print(f"{'slot':40s} {'accuracy':>9s} {'$/call':>9s} {'tok_out':>8s}")
    for j, s in enumerate(lm.model_ids):
        print(f"{s[:40]:40s} {lm.quality[:, j].mean():9.4f} "
              f"{lm.cost[:, j].mean():9.5f} {lm.tokens_out[:, j].mean():8.0f}")

    util = lm.quality - 0.0 * lm.cost
    bs = best_single_column(lm.quality)
    print(f"\nbest single by quality alone : {lm.model_ids[bs]}")

    # The product's actual baseline: the model a buyer would pick once price counts.
    # Ranked by quality per dollar on the same items, which is the comparison
    # RESULTS.md §3.1 says is the honest one.
    ratio = [(lm.quality[:, j].mean(), lm.cost[:, j].mean(), j)
             for j in range(lm.n_models)]
    frontier = max(range(lm.n_models), key=lambda j: lm.quality[:, j].mean())
    print(f"frontier (highest quality)   : {lm.model_ids[frontier]}")

    train, test = chutes.split(lm, seed=0)
    X, _ = features_for(lm, fit_idx=train)
    print(f"\nsplit: {len(train):,} train / {len(test):,} test, features d={X.shape[1]}")

    out = {
        "proxy_backed": False,
        "n_items": int(lm.n_items),
        "models": list(lm.model_ids),
        "accuracy": {s: round(float(lm.quality[:, j].mean()), 4)
                     for j, s in enumerate(lm.model_ids)},
        "chutes_cost_per_call": {s: round(float(lm.cost[:, j].mean()), 6)
                                 for j, s in enumerate(lm.model_ids)},
        "mean_tokens_out": {s: round(float(lm.tokens_out[:, j].mean()), 1)
                            for j, s in enumerate(lm.model_ids)},
        "frontier_model": lm.model_ids[frontier],
        "n_train": len(train), "n_test": len(test),
        "lambda_sweep": [],
    }

    # Sweep the dial rather than quoting one operating point — RIGOR.md §5's lesson:
    # comparing single operating points mostly measures where a threshold happened
    # to land.
    keep = ("policy", "quality", "cost_per_call_usd", "savings_vs_frontier_pct",
            "quality_vs_frontier_pct", "savings_vs_best_single_pct",
            "quality_vs_best_single_pct")
    print(f"\n{'lam':>5s} {'router $/call':>13s} {'vs best single':>15s} "
          f"{'quality kept':>13s} {'traffic to cheapest':>19s}")
    for lam in (0.0, 0.05, 0.1, 0.2, 0.4, 0.8):
        try:
            ev = chutes.evaluate(lm, X, tokens_in, train, test, lam_cost=lam, seed=0)
        except Exception as e:                       # a 4-column pool is a thin case
            print(f"  lam={lam}: {type(e).__name__}: {e}")
            continue
        pols = [{k: (round(float(v), 6) if isinstance(v, (int, float)) else v)
                 for k, v in p.items() if k in keep} for p in ev["policies"]]
        r = next(p for p in ev["policies"] if p["policy"] == "router")
        out["lambda_sweep"].append({
            "lam_cost": lam,
            "best_single_model": ev["best_single_model"],
            "frontier_model": ev["frontier_model"],
            "dominated_models": ev.get("dominated_models", []),
            "policies": pols,
        })
        cheapest = min(lm.model_ids, key=lambda s: lm.cost[:, lm.model_ids.index(s)].mean())
        print(f"{lam:5.2f} {r['cost_per_call_usd']:13.6f} "
              f"{r['savings_vs_best_single_pct']:14.1f}% "
              f"{r['quality_vs_best_single_pct'] * 100:12.1f}% "
              f"{r['traffic_share'].get(cheapest, 0.0) * 100:18.0f}%")

    # The headline the pool can actually support, stated once and honestly.
    out["verdict"] = {
        "best_single_model": out["lambda_sweep"][0]["best_single_model"] if out["lambda_sweep"] else None,
        "dominated_models": out["lambda_sweep"][0]["dominated_models"] if out["lambda_sweep"] else [],
    }

    (GRD / "routing.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {(GRD / 'routing.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
