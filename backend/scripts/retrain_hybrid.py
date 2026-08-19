"""Retrain the thirteen-slot router with the measured columns swapped in.

`analyze_graded.py` routes over the four real columns alone. This does the thing the
product actually needs: rebuild the **thirteen-slot** pool, replace the four slots we
measured with their real outcomes, leave the other nine on their stand-ins, and refit.

The comparison is run as an A/B on one item set, which is the only way the difference
means anything:

    arm A  all thirteen columns proxy-backed   (what shipped)
    arm B  four columns real, nine proxy       (what we now know)

Same items, same split, same feature map, same estimator, same prices. The only thing
that differs is the contents of four columns, so every difference in the output is
attributable to the proxy assumption and nothing else.

**Why the overlap items and not the whole dense core.** A column has to mean one thing.
If a slot carried real outcomes on the 200-odd items we graded and stand-in outcomes on
the other 3,700, that column would be a mixture of two different models and every
argmax over it would be comparing a real model against a hypothetical one, item by item.
So arm B is restricted to items where *all four* measured slots have real data, and arm
A is restricted to exactly the same items. That makes the pool small and the comparison
sound; the alternative is large and meaningless.

What this cannot do is re-measure the other nine slots. Six of them are the cheap end of
the catalogue, and `RESULTS.md` §8 already showed the cheap slots are where the
unclaimed value is — so read arm B as "the frontier of the pool is now measured", not
as a de-proxied product.
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
from rollingbench.experiments import chutes  # noqa: E402

GRD = ROOT / "artifacts" / "grading"
LAMBDAS = (0.0, 0.05, 0.1, 0.2, 0.4)


def load_arms():
    """Arm A (all proxy) and arm B (four columns real), on identical items."""
    lm, tokens_in = chutes.build_pool()
    real = np.load(GRD / "matrix.npz", allow_pickle=True)
    real_slots = [str(s) for s in real["model_ids"]]
    real_keys = [str(k) for k in real["item_keys"]]

    pos = {str(k): i for i, k in enumerate(lm.item_ids)}
    keep_keys = [k for k in real_keys if k in pos]
    rows = np.array([pos[k] for k in keep_keys])
    rrow = np.array([real_keys.index(k) for k in keep_keys])

    lm_a = lm.subset_items(rows)
    tin_a = tokens_in[rows]

    # Arm B: same object, four columns overwritten.
    import copy
    lm_b = copy.deepcopy(lm_a)
    tin_b = tin_a.copy()
    cols = [lm.model_ids.index(s) for s in real_slots]
    for j, c in enumerate(cols):
        lm_b.quality[:, c] = real["quality"][rrow, j]
        lm_b.tokens_out[:, c] = real["tokens_out"][rrow, j]
        tin_b[:, c] = real["tokens_in"][rrow, j]
        lm_b.observed[:, c] = True

    # Re-price both from their own token counts at the same Chutes list prices.
    pin = np.array([m.in_per_1m for m in CHUTES_CATALOG])
    pout = np.array([m.out_per_1m for m in CHUTES_CATALOG])
    for lmx, tinx in ((lm_a, tin_a), (lm_b, tin_b)):
        cost = tinx / 1e6 * pin[None, :] + lmx.tokens_out / 1e6 * pout[None, :]
        lmx.cost = np.where(lmx.observed, cost, 0.0)

    lm_b.source = "hybrid: 4 slots measured on the real checkpoint, 9 proxy-backed"
    return (lm_a, tin_a), (lm_b, tin_b), real_slots, keep_keys


def shipped_router_meets_reality(lam_cost: float = 0.2) -> dict:
    """Arm C — fit on the stand-ins, then score the decisions against what really happened.

    Arms A and B both retrain. This one does not: it is the router as *shipped*, fitted
    on proxy outcomes over the full dense core, and then asked to route items whose true
    outcomes we now know. It answers the question a customer would actually ask — not
    "what would you have learned from better data" but "were the decisions you already
    made the right ones".

    Training excludes every graded item, so there is no leakage and no mixed column: the
    fit sees only proxy data, the scoring sees only real data, and the two never touch
    the same cell.
    """
    lm, tokens_in = chutes.build_pool()
    real = np.load(GRD / "matrix.npz", allow_pickle=True)
    real_slots = [str(s) for s in real["model_ids"]]
    real_keys = [str(k) for k in real["item_keys"]]
    pos = {str(k): i for i, k in enumerate(lm.item_ids)}
    keep = [k for k in real_keys if k in pos]
    test_rows = np.array([pos[k] for k in keep])
    rrow = np.array([real_keys.index(k) for k in keep])

    dense = np.flatnonzero(lm.observed.all(axis=1))
    train_rows = np.setdiff1d(dense, test_rows)      # no leakage

    X, _ = features_for(lm, fit_idx=train_rows)
    r, _ = chutes.train_router(lm, X, train_rows, lam_cost=lam_cost)

    cols = [lm.model_ids.index(s) for s in real_slots]
    q_real = lm.quality[test_rows].copy()
    tout_real = lm.tokens_out[test_rows].copy()
    tin_real = tokens_in[test_rows].copy()
    for j, c in enumerate(cols):
        q_real[:, j * 0 + c] = real["quality"][rrow, j]
        tout_real[:, c] = real["tokens_out"][rrow, j]
        tin_real[:, c] = real["tokens_in"][rrow, j]

    pin = np.array([m.in_per_1m for m in CHUTES_CATALOG])
    pout = np.array([m.out_per_1m for m in CHUTES_CATALOG])
    c_real = tin_real / 1e6 * pin[None, :] + tout_real / 1e6 * pout[None, :]
    c_proxy = (tokens_in[test_rows] / 1e6 * pin[None, :]
               + lm.tokens_out[test_rows] / 1e6 * pout[None, :])

    ps = chutes.pool_state()
    tin_item = chutes._tokens_in_per_item(tokens_in, lm.observed)[test_rows]
    choice = r.decide(X[test_rows], ps, tokens_in=tin_item)
    if not isinstance(choice, np.ndarray):
        choice = np.asarray(getattr(choice, "choice", choice))
    choice = np.asarray(choice).astype(int).ravel()

    rows = np.arange(len(test_rows))
    out = {"lam_cost": lam_cost, "n_test": int(len(test_rows))}
    for name, q, c in (("as the proxy predicted", lm.quality[test_rows], c_proxy),
                       ("as it really is", q_real, c_real)):
        out[name] = {
            "router_quality": round(float(q[rows, choice].mean()), 4),
            "router_cost_per_call": round(float(c[rows, choice].mean()), 6),
            "best_single_quality": round(float(q.mean(axis=0).max()), 4),
            "best_single_model": lm.model_ids[int(q.mean(axis=0).argmax())],
        }
    # Did the router pick a slot we can actually vouch for?
    out["traffic_to_measured_slots"] = round(
        float(np.isin(choice, cols).mean()), 4)
    return out


def run_arm(lm, tokens_in, X, train, test, label: str) -> dict:
    out = {"arm": label, "sweep": []}
    for lam in LAMBDAS:
        ev = chutes.evaluate(lm, X, tokens_in, train, test, lam_cost=lam, seed=0)
        r = next(p for p in ev["policies"] if p["policy"] == "router")
        out["sweep"].append({
            "lam_cost": lam,
            "best_single_model": ev["best_single_model"],
            "frontier_model": ev["frontier_model"],
            "router_cost_per_call": round(float(r["cost_per_call_usd"]), 6),
            "savings_vs_best_single_pct": round(float(r["savings_vs_best_single_pct"]), 2),
            "quality_vs_best_single_pct": round(float(r["quality_vs_best_single_pct"]), 4),
            "savings_vs_frontier_pct": round(float(r["savings_vs_frontier_pct"]), 2),
            "quality_vs_frontier_pct": round(float(r["quality_vs_frontier_pct"]), 4),
            "traffic_share": {k: round(float(v), 4)
                              for k, v in r["traffic_share"].items() if v > 0},
            "dominated_models": ev.get("dominated_models", []),
        })
    return out


def main() -> None:
    (lm_a, tin_a), (lm_b, tin_b), real_slots, keys = load_arms()
    print(f"overlap items: {lm_a.n_items:,}  (13 slots; {len(real_slots)} of them measured)\n")

    train, test = chutes.split(lm_a, seed=0)
    X, _ = features_for(lm_a, fit_idx=train)          # prompts identical across arms
    print(f"split {len(train):,} train / {len(test):,} test, d={X.shape[1]}\n")

    print(f"{'slot':40s} {'proxy acc':>10s} {'real acc':>9s} {'delta':>7s}")
    per_model = []
    for s in real_slots:
        c = lm_a.model_ids.index(s)
        pa, ra = float(lm_a.quality[:, c].mean()), float(lm_b.quality[:, c].mean())
        per_model.append({"slot": s, "proxy_accuracy": round(pa, 4),
                          "real_accuracy": round(ra, 4), "delta": round(ra - pa, 4)})
        print(f"{s[:40]:40s} {pa:10.4f} {ra:9.4f} {ra - pa:+7.4f}")

    a = run_arm(lm_a, tin_a, X, train, test, "A: all thirteen proxy-backed")
    b = run_arm(lm_b, tin_b, X, train, test, "B: four slots measured")

    print(f"\n{'lam':>5s} | {'A best single':>28s} {'A sav%':>7s} | "
          f"{'B best single':>28s} {'B sav%':>7s}")
    for ra, rb in zip(a["sweep"], b["sweep"]):
        print(f"{ra['lam_cost']:5.2f} | {ra['best_single_model'][:28]:>28s} "
              f"{ra['savings_vs_best_single_pct']:7.2f} | "
              f"{rb['best_single_model'][:28]:>28s} "
              f"{rb['savings_vs_best_single_pct']:7.2f}")

    print("\narm C — the shipped router, scored against what really happened:")
    c = shipped_router_meets_reality()
    print(f"  trained on {'proxy':>5s} outcomes, tested on {c['n_test']} graded items")
    for k in ("as the proxy predicted", "as it really is"):
        v = c[k]
        print(f"  {k:24s}: router quality {v['router_quality']:.4f}  "
              f"${v['router_cost_per_call']:.6f}/call  "
              f"best single = {v['best_single_model'][:34]}")
    print(f"  traffic sent to slots we measured: {c['traffic_to_measured_slots'] * 100:.0f}%")

    payload = {
        "n_items": int(lm_a.n_items),
        "measured_slots": real_slots,
        "n_train": len(train), "n_test": len(test),
        "per_model_accuracy": per_model,
        "arm_a_all_proxy": a,
        "arm_b_hybrid": b,
        "arm_c_shipped_router_vs_reality": c,
        "caveat": ("Nine of thirteen slots remain proxy-backed, and the item set is the "
                   "subset gradeable without a judge. Read arm B as 'the frontier of the "
                   "pool is measured', not as a de-proxied product."),
    }
    (GRD / "retrain.json").write_text(json.dumps(payload, indent=1))
    print(f"\nwrote {(GRD / 'retrain.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
