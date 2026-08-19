"""Turn the graded ledger into a label matrix, and say how wrong the proxy was.

Two outputs, and the second is the one that was actually blocked on spending money:

`matrix.npz` — real per-item outcomes for the slots we could reach, in the same shape
the rest of the package consumes. Quality and token counts are measured; cost is left
to be recomputed at Chutes list price, which is what the architecture requires.

`measured.json` — the proxy audit. For every slot, the accuracy its stand-in predicted
on *these same items* beside the accuracy the real checkpoint scored. That difference
is the size of the assumption six headline numbers were resting on, and until now
nobody could put a number on it.

Only cells where the model produced a gradeable answer are counted. Truncations and
transport failures are reported separately and never scored — see `grade_fireworks.py`
for why turning either into a 0.0 is the specific mistake that cost this repository a
correction once already.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rollingbench.catalog import CHUTES_CATALOG, by_id, proxy_for  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from grade_fireworks import norm_math  # noqa: E402

GRD = ROOT / "artifacts" / "grading"
CACHE = ROOT / "data" / "cache" / "llmrouterbench.npz"


def regrade(task: str, ground_truth: str, pred: str | None) -> float | None:
    """Re-settle a cell from the answer the model gave, not the score written at the time.

    The extractor runs once, during the paid call, and its output (`pred`) is kept. The
    *comparison* is cheap and was tightened after the run began — against the corpus's
    own verdicts it went from 99.80% to 99.95% agreement. Re-deciding here means every
    cell is judged by the same, better rule, and no call has to be paid for twice.
    """
    if pred is None:
        return None
    if task in ("mmlupro", "gpqa"):
        return float(str(pred).strip().upper()[:1] == ground_truth.strip().upper()[:1])
    return float(norm_math(str(pred)) == norm_math(ground_truth))


def main() -> None:
    rows = [json.loads(l) for l in (GRD / "cells.jsonl").read_text().splitlines() if l.strip()]
    items = {i["key"]: i for i in json.loads((GRD / "items.json").read_text())["items"]}

    slots = sorted({r["slot"] for r in rows})
    # Dense set only: an item counts if every slot we ran returned a gradeable answer.
    # Anything else reintroduces the uneven-coverage bias RESULTS.md §4.2 measured.
    per_item: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for r in rows:
        per_item[r["item"]][r["slot"]] = r
    dense = [k for k, v in per_item.items()
             if len(v) == len(slots) and all(c.get("observed") for c in v.values())]
    dense.sort()

    attempted = len(per_item)
    n_trunc = sum(1 for r in rows if r.get("truncated"))
    n_ungrad = sum(1 for r in rows if r.get("ungradeable"))
    n_err = sum(1 for r in rows if r.get("error"))

    print(f"cells in ledger      : {len(rows):,}")
    print(f"items attempted      : {attempted:,}")
    print(f"items fully gradeable: {len(dense):,}  <- the dense set every number uses")
    print(f"  truncated cells    : {n_trunc:,}")
    print(f"  ungradeable cells  : {n_ungrad:,}")
    print(f"  transport failures : {n_err:,}\n")
    if not dense:
        raise SystemExit("no dense items yet")

    q = np.zeros((len(dense), len(slots)), dtype=np.float32)
    tin = np.zeros_like(q)
    tout = np.zeros_like(q)
    n_flipped = 0
    for i, k in enumerate(dense):
        for j, s in enumerate(slots):
            c = per_item[k][s]
            score = regrade(items[k]["task"], items[k]["ground_truth"], c.get("pred"))
            if score is None:
                score = c["score"]
            elif score != c["score"]:
                n_flipped += 1
            q[i, j], tin[i, j], tout[i, j] = score, c["tokens_in"], c["tokens_out"]
    if n_flipped:
        print(f"regrade: {n_flipped} cell(s) changed verdict under the tightened "
              f"comparison\n")

    task = np.array([items[k]["task"] for k in dense])

    # ---- the proxy audit: same items, stand-in's score vs the real thing ----
    z = np.load(CACHE, allow_pickle=True)
    cache_models = [str(m) for m in z["model_ids"]]
    cache_keys = {str(k): i for i, k in enumerate(z["item_keys"])}
    ridx = [cache_keys[k] for k in dense]

    audit = []
    for j, s in enumerate(slots):
        b = proxy_for(s)
        col = cache_models.index(b.proxy_id)
        pq = z["quality"][ridx, col]
        pobs = z["observed"][ridx, col]
        ptout = z["tokens_out"][ridx, col]
        real, proxy = float(q[:, j].mean()), float(pq[pobs].mean())

        # Paired bootstrap on the per-item difference. Paired because both columns
        # answered the *same* questions: resampling the difference cancels item
        # difficulty and gives a far tighter interval than two independent ones. With
        # n in the tens this interval is the result — the point estimate on its own
        # would imply a precision nothing here has earned.
        both = pobs
        diff = pq[both].astype(np.float64) - q[both, j].astype(np.float64)
        rng = np.random.default_rng(0)
        if len(diff):
            draws = rng.choice(diff, size=(2000, len(diff)), replace=True).mean(axis=1)
            lo, hi = np.percentile(draws, [2.5, 97.5])
        else:
            lo = hi = float("nan")
        audit.append({
            "slot": s,
            "proxy_id": b.proxy_id,
            "proxy_was_exact_checkpoint": bool(b.exact),
            "n_items": int(both.sum()),
            "real_accuracy": round(real, 4),
            "proxy_accuracy": round(proxy, 4),
            "abs_error": round(abs(real - proxy), 4),
            "signed_error_proxy_minus_real": round(proxy - real, 4),
            "error_ci95": [round(float(lo), 4), round(float(hi), 4)],
            "error_excludes_zero": bool(lo > 0 or hi < 0),
            "real_mean_tokens_out": round(float(tout[:, j].mean()), 1),
            "proxy_mean_tokens_out": round(float(np.nanmean(ptout[pobs])), 1),
        })

    print(f"{'slot':34s} {'stood in by':22s} {'real':>6s} {'proxy':>6s} "
          f"{'error':>7s} {'95% CI':>18s} {'sig':>4s}")
    for a in audit:
        lo, hi = a['error_ci95']
        print(f"{a['slot'][:34]:34s} {a['proxy_id'][:22]:22s} "
              f"{a['real_accuracy']:6.3f} {a['proxy_accuracy']:6.3f} "
              f"{a['signed_error_proxy_minus_real']:+7.3f} "
              f"{'[' + f'{lo:+.3f}, {hi:+.3f}' + ']':>18s} "
              f"{'yes' if a['error_excludes_zero'] else 'no':>4s}")
    errs = [a["abs_error"] for a in audit]
    print(f"\nmean |proxy error| = {np.mean(errs):.3f}   max = {max(errs):.3f}")

    # How much easier is the dense set than the items we attempted? Dropping a cell
    # because a model ran out of tokens is not random — it drops the items the
    # verbose models found hardest, so the survivors skew easy for *every* column.
    # The stand-ins answered all of these items, so the size of that skew can be read
    # off them directly, without paying for another call. Note this does not touch
    # the audit above: that is a paired comparison on identical items, so whatever
    # selection happened cancels between the two sides.
    all_rows = [cache_keys[k] for k in sorted(per_item)]
    bias = []
    for a in audit:
        col = cache_models.index(a["proxy_id"])
        dq, dobs = z["quality"][ridx, col], z["observed"][ridx, col]
        aq, aobs = z["quality"][all_rows, col], z["observed"][all_rows, col]
        on_dense, on_all = float(dq[dobs].mean()), float(aq[aobs].mean())
        bias.append({"slot": a["slot"], "proxy_on_dense_set": round(on_dense, 4),
                     "proxy_on_all_attempted": round(on_all, 4),
                     "selection_bias": round(on_dense - on_all, 4)})
    mb = float(np.mean([b["selection_bias"] for b in bias]))
    print(f"selection bias (dense set is easier by, per the stand-ins): {mb:+.3f}")

    by_task = {}
    for t in sorted(set(task.tolist())):
        m = task == t
        by_task[t] = {"n": int(m.sum()),
                      "accuracy_by_slot": {s: round(float(q[m, j].mean()), 4)
                                           for j, s in enumerate(slots)}}

    np.savez_compressed(
        GRD / "matrix.npz",
        item_keys=np.array(dense, dtype=object),
        model_ids=np.array(slots, dtype=object),
        quality=q, tokens_in=tin, tokens_out=tout,
        observed=np.ones_like(q, dtype=bool), task=task,
    )

    # Cost at Chutes list price — measured tokens, read price. Never fitted.
    cost_usd = {}
    for j, s in enumerate(slots):
        m = by_id(CHUTES_CATALOG, s)
        cost_usd[s] = round(float((tin[:, j] / 1e6 * m.in_per_1m
                                   + tout[:, j] / 1e6 * m.out_per_1m).mean()), 6)

    (GRD / "measured.json").write_text(json.dumps({
        "proxy_backed": False,
        "source": "Fireworks serverless, same open-weights checkpoints as the Chutes slots",
        "note": ("Quality and token counts are measured on the real checkpoint. The "
                 "remaining assumption is host, not model: the same weights served by "
                 "Fireworks rather than Chutes. Prices are the Chutes list."),
        "n_items": len(dense),
        "slots": slots,
        "tasks": {t: v["n"] for t, v in by_task.items()},
        "accuracy": {s: round(float(q[:, j].mean()), 4) for j, s in enumerate(slots)},
        "mean_tokens_out": {s: round(float(tout[:, j].mean()), 1) for j, s in enumerate(slots)},
        "chutes_cost_per_call_usd": cost_usd,
        "by_task": by_task,
        "proxy_audit": audit,
        "selection_bias": {"per_slot": bias, "mean": round(mb, 4),
                           "note": ("dense-set minus all-attempted, measured on the "
                                    "stand-ins which answered every item. The audit is "
                                    "paired on identical items so this does not bias it.")},
        "excluded": {"truncated": n_trunc, "ungradeable": n_ungrad, "errors": n_err},
    }, indent=1))
    print(f"\nwrote {(GRD / 'measured.json').relative_to(ROOT)} and matrix.npz")


if __name__ == "__main__":
    main()
