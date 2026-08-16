"""Latency — what the corpus can support, and what it cannot.

The short version: **per-request latency is not measurable from this data, and the
attempt to derive it is left in the file as a failed check rather than deleted.**
What *is* measured, per item, is the number of output tokens — and for a given
model that is what actually decides how long a request takes. So latency is routed
on in token units, and the conversion to seconds is left to whoever has a timed
endpoint.

### The attempt, and why it fails

The corpus publishes wall-clock per *run* — one `time_taken` for a whole (model,
task) file — never per record. The obvious move is to fit

    time_taken  ≈  counts · overhead  +  completion_tokens / throughput

per model across its task runs and read per-item latency off the measured token
count. `fit_throughput` does exactly that, and `throughput_is_credible` then checks
whether the result can be true. It cannot:

* 26 of 38 models come out above 500 tokens/second, and one at 10,810. Single-stream
  decoding for models this size is tens of tokens per second, not thousands.
* 22 of 38 fits have R² below 0.3; several are negative, meaning the fit is worse
  than predicting the mean.

Both point the same way: the runs were executed concurrently, so `time_taken`
measures the harness's aggregate throughput under whatever parallelism it chose, not
the latency of any request. Dividing it by `counts` produces a number with units of
seconds that is not a latency, and shipping that as p95 would be inventing data with
a plausible face on it.

### What is used instead

Output tokens, measured per item, as the latency signal. This is honest about what
it is — a **proxy, exactly measured**, rather than a latency, roughly invented — and
it is the right shape: within a model, time is very nearly linear in output tokens,
and the p50-to-p95 spread here is 3x to 25x depending on the model, which is where
tail latency actually comes from.

Seconds are reported too, but only under an explicitly named decoding rate
(`ASSUMED_TOK_S`), carried in the output so no reader can mistake it for measured.
One timed run against the real endpoint replaces all of this.
"""

from __future__ import annotations

import numpy as np

from ..catalog import CHUTES_CATALOG, CHUTES_PROXY, by_id
from ..data import llmrouterbench
from ..data.labelmatrix import LabelMatrix
from ..router import PoolState

#: Below this many runs a two-parameter fit is not worth attempting.
MIN_RUNS = 4

#: Single-stream decode rates above this are not physically plausible for models of
#: this size, so a fit that produces one is reporting batch throughput.
PLAUSIBLE_TOK_S = 500.0

#: Used only to put the token figures on a familiar axis. Not measured, not fitted,
#: and travels with every number derived from it.
ASSUMED_TOK_S = 60.0


def fit_throughput(cache=None) -> dict[str, dict]:
    """Per-model (overhead, throughput) by least squares over its runs.

    Kept because the *failure* of this fit is the finding. See the module docstring.
    """
    rows = llmrouterbench.timings(cache) if cache else llmrouterbench.timings()
    by_model: dict[str, list[dict]] = {}
    for r in rows:
        if r["counts"] > 0 and r["time_taken_s"] > 0:
            by_model.setdefault(r["model"], []).append(r)

    out: dict[str, dict] = {}
    for model, runs in by_model.items():
        if len(runs) < MIN_RUNS:
            continue
        n = np.array([r["counts"] for r in runs], dtype=float)
        tok = np.array([r["completion_tokens"] for r in runs], dtype=float)
        t = np.array([r["time_taken_s"] for r in runs], dtype=float)

        sol, *_ = np.linalg.lstsq(np.column_stack([n, tok]), t, rcond=None)
        overhead, inv_tp = float(sol[0]), float(sol[1])
        if overhead < 0 or inv_tp <= 0:
            inv_tp = float(tok @ t / max(tok @ tok, 1e-9))
            overhead = 0.0

        pred = n * overhead + tok * inv_tp
        ss_res = float(((t - pred) ** 2).sum())
        ss_tot = float(((t - t.mean()) ** 2).sum())
        out[model] = {
            "runs": len(runs),
            "overhead_s": overhead,
            "throughput_tok_s": 1.0 / max(inv_tp, 1e-12),
            "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
            "mean_wall_per_item_s": float((t / n).mean()),
        }
    return out


def throughput_is_credible(fits: dict[str, dict]) -> dict:
    """Can the fitted throughputs be per-request rates? Decided, not assumed."""
    tp = np.array([f["throughput_tok_s"] for f in fits.values()])
    r2 = np.array([f["r2"] for f in fits.values()])
    n_impl = int((tp > PLAUSIBLE_TOK_S).sum())
    n_badfit = int((r2 < 0.3).sum())
    credible = n_impl == 0 and n_badfit <= len(r2) // 4
    return {
        "credible": credible,
        "models_fitted": len(tp),
        "median_tok_s": float(np.median(tp)),
        "max_tok_s": float(tp.max()),
        "implausible_rate_count": n_impl,
        "poor_fit_count": n_badfit,
        "verdict": (
            f"NOT USABLE as per-request latency: {n_impl} of {len(tp)} models fit above "
            f"{PLAUSIBLE_TOK_S:g} tok/s (max {tp.max():.0f}) and {n_badfit} of {len(r2)} "
            f"fits have R² < 0.3. The runs were concurrent, so wall-clock measures "
            f"harness throughput, not request latency. Routing uses measured output "
            f"tokens instead."
            if not credible else
            "Fits are plausible; per-request seconds can be derived."
        ),
    }


def token_percentiles(lm: LabelMatrix, idx: np.ndarray) -> list[dict]:
    """The measured latency signal: output tokens per item, per model.

    Seconds are shown alongside at `ASSUMED_TOK_S` purely to put the spread on a
    familiar axis; the token columns are the measurement.
    """
    rows = []
    for j, mid in enumerate(lm.model_ids):
        m = by_id(CHUTES_CATALOG, mid)
        obs = lm.observed[idx, j]
        if not obs.any():
            continue
        v = lm.tokens_out[idx, j][obs]
        p50, p95, p99 = (float(np.percentile(v, p)) for p in (50, 95, 99))
        rows.append({
            "model_id": mid, "label": m.label, "tier": m.tier,
            "measured": "output tokens", "seconds_assume_tok_s": ASSUMED_TOK_S,
            "p50_tokens": p50, "p95_tokens": p95, "p99_tokens": p99,
            "p50_s": p50 / ASSUMED_TOK_S,
            "p95_s": p95 / ASSUMED_TOK_S,
            "p99_s": p99 / ASSUMED_TOK_S,
            "tail_ratio_p95_p50": p95 / max(p50, 1.0),
        })
    return rows


def routed_tokens(lm: LabelMatrix, idx: np.ndarray, choice: np.ndarray) -> dict:
    """What the router's own answers cost in output tokens — the number a user feels.

    A per-model table says how slow each model is; it does not say how slow the
    product is, because traffic is not split evenly.
    """
    v = lm.tokens_out[idx][np.arange(len(idx)), choice]
    p50, p95, p99 = (float(np.percentile(v, p)) for p in (50, 95, 99))
    return {
        "p50_tokens": p50, "p95_tokens": p95, "p99_tokens": p99,
        "mean_tokens": float(v.mean()),
        "p50_s": p50 / ASSUMED_TOK_S, "p95_s": p95 / ASSUMED_TOK_S,
        "p99_s": p99 / ASSUMED_TOK_S,
        "seconds_assume_tok_s": ASSUMED_TOK_S,
    }


def sweep_lam_latency(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    tokens_in: np.ndarray,
    *,
    lam_cost: float,
    lam_latencies: tuple[float, ...] = (0.0, 0.02, 0.05, 0.1, 0.2, 0.4, 0.8),
) -> list[dict]:
    """Switch §8.7's latency term on for the first time and price what it buys.

    `lam_latency` has been zero throughout this package because nothing had ever
    populated a latency table. The live table here carries each model's **measured
    p95 output tokens**, which is the quantity a latency-aware gateway would publish
    and the one that drives the tail being routed around.
    """
    from ..metrics import frontier_reference_column
    from .chutes import _dense, _tokens_in_per_item, pool_state, train_router

    ps = pool_state()
    dtr = _dense(lm, train)
    p95_tokens = np.array([
        np.percentile(lm.tokens_out[dtr, j][lm.observed[dtr, j]], 95)
        if lm.observed[dtr, j].any() else np.nan
        for j in range(lm.n_models)
    ])
    ps_lat = PoolState(price_in=ps.price_in, price_out=ps.price_out,
                       p95_ms=p95_tokens / ASSUMED_TOK_S * 1000.0)

    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    q, c = lm.quality[test], lm.cost[test]
    rows = np.arange(len(test))
    fc = frontier_reference_column(lm.quality[dtr])

    out = []
    for ll in lam_latencies:
        r, _ = train_router(lm, X, train, lam_cost=lam_cost)
        r.cfg.lam_latency = ll
        choice = r.decide(X[test], ps_lat, tokens_in=tin).choice
        rt = routed_tokens(lm, test, choice)
        out.append({
            "lam_latency": ll,
            "quality": float(q[rows, choice].mean()),
            "cost_per_call_usd": float(c[rows, choice].mean()),
            "savings_vs_frontier": 1.0 - float(c[rows, choice].mean()) / max(
                float(c[:, fc].mean()), 1e-12),
            "p50_tokens": rt["p50_tokens"], "p95_tokens": rt["p95_tokens"],
            "p99_tokens": rt["p99_tokens"],
            "models_used": int(len(np.unique(choice))),
        })
    return out


def run(lm: LabelMatrix, X: np.ndarray, tokens_in: np.ndarray,
        train: np.ndarray, test: np.ndarray, *, lam_cost: float,
        cache=None) -> dict:
    from .chutes import _tokens_in_per_item, pool_state, train_router

    fits = fit_throughput(cache)
    credibility = throughput_is_credible(fits)

    r, _ = train_router(lm, X, train, lam_cost=lam_cost)
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    choice = r.decide(X[test], pool_state(), tokens_in=tin).choice

    per_model = token_percentiles(lm, test)
    routed = routed_tokens(lm, test, choice)
    sweep = sweep_lam_latency(lm, X, train, test, tokens_in, lam_cost=lam_cost)

    slowest = max(per_model, key=lambda x: x["p95_tokens"])
    fastest = min(per_model, key=lambda x: x["p95_tokens"])
    off, on = sweep[0], min(sweep, key=lambda s: s["p95_tokens"])
    return {
        "latency_is_measured": False,
        "signal": "output tokens per item (measured); seconds shown at an assumed decode rate",
        "assumed_tok_s": ASSUMED_TOK_S,
        "throughput_fit": {"fits": dict(sorted(fits.items())), **credibility},
        "per_model": per_model,
        "routed": routed,
        "lam_latency_sweep": sweep,
        "reading": (
            f"Per-request latency is not in this corpus — {credibility['verdict']} "
            f"On the measured signal, routed p95 is {routed['p95_tokens']:,.0f} output "
            f"tokens and p99 {routed['p99_tokens']:,.0f}, against a pool spanning "
            f"{fastest['p95_tokens']:,.0f} ({fastest['label']}) to "
            f"{slowest['p95_tokens']:,.0f} ({slowest['label']}) at p95. Turning the "
            f"latency term on moves routed p95 from {off['p95_tokens']:,.0f} to "
            f"{on['p95_tokens']:,.0f} tokens "
            f"({1 - on['p95_tokens'] / max(off['p95_tokens'], 1):.0%} shorter) for "
            f"{off['quality'] - on['quality']:+.4f} of quality."
        ),
    }
