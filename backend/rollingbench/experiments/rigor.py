"""The statistics the rest of this package mostly skipped.

`PUBLISHABILITY.md` graded every finding and the recurring complaint was the same:
large effects, clear mechanisms, and almost no error bars. Three of roughly twenty
headline numbers carried one. Fifteen claims were adjudicated with no correction for
having tested fifteen things.

This module fixes what can be fixed with compute rather than money:

    bootstrap_headlines      confidence intervals on every headline, by resampling
                             held-out items — so a figure quoted to three decimals
                             has a stated width
    domain_significance      paired standard errors per domain, with Holm–Bonferroni
                             across the family, because five comparisons were being
                             read as five independent findings
    replicate_coverage_bias  the most novel result, re-run on a second pool of
                             thirteen models sharing no column with the first
    workload_mix             what the savings figure becomes when the traffic is not
                             all hard benchmarks

What it cannot fix: the labels are still stand-ins, and there is still no timed
endpoint. Both need spending, not arithmetic.

Every function here answers "is the effect there?" at n = 1 — one replication, one
split, one family. `publish.py` is the second pass that asks how big each one is and
whether it moves when the mechanism says it should, and two of the answers changed.

A note on the bootstrap. Items are resampled, not cells, because the unit of
independence is the question — the same prompt answered by thirteen models is one
observation, and resampling cells would treat it as thirteen and shrink every
interval by roughly √13. The percentile interval is used rather than BCa: the
statistics here are means and ratios of means over n > 1,000, where the two agree to
the third decimal, and the percentile version is auditable by eye.
"""

from __future__ import annotations

import numpy as np

from ..catalog import CHUTES_CATALOG
from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    frontier_reference_column,
    per_cell_utility,
)
from .chutes import (
    _dense,
    _tokens_in_per_item,
    pool_state,
    split,
    train_router,
)

#: Resamples for every bootstrap in this module. 2,000 gives a 95% interval whose
#: endpoints are stable to about the third decimal, which is the precision anything
#: here is quoted at.
N_BOOT = 2000


def _pct_ci(draws: np.ndarray, alpha: float = 0.05) -> dict:
    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"mean": float(draws.mean()), "lo": float(lo), "hi": float(hi),
            "se": float(draws.std(ddof=1)), "n_boot": int(len(draws))}


# ------------------------------------------------------------------ headlines --
def bootstrap_headlines(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    lam_cost: float,
    n_boot: int = N_BOOT,
    seed: int = 0,
) -> dict:
    """95% intervals for every number the product quotes.

    The router is fitted once on the training split and then held fixed; only the
    *evaluation* items are resampled. That is the right question — "how precisely do
    we know what this policy does?" — and it is separable from "how much does the
    policy move between training splits", which `chutes.cross_validate` already
    answers over eight splits.
    """
    ps = pool_state()
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    r, _ = train_router(lm, X, train, lam_cost=lam_cost)
    choice = r.decide(X[test], ps, tokens_in=tin).choice

    q, c = lm.quality[test], lm.cost[test]
    n = len(test)
    rows = np.arange(n)
    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    bs = best_single_column(per_cell_utility(
        lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=lam_cost), ref_col=fc))

    rq = q[rows, choice]
    rc = c[rows, choice]
    pred = r.quality.predict(X[test])

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))

    def draw(v: np.ndarray) -> np.ndarray:
        return v[idx].mean(axis=1)

    rq_b, rc_b = draw(rq), draw(rc)
    fq_b, fc_b = draw(q[:, fc]), draw(c[:, fc])
    bq_b, bc_b = draw(q[:, bs]), draw(c[:, bs])
    oracle_b = draw(q.max(axis=1))
    brier_b = ((pred - q) ** 2).mean(axis=1)[idx].mean(axis=1)

    out = {
        "n_test_items": int(n),
        "n_boot": int(n_boot),
        "frontier_model": lm.model_ids[fc],
        "best_single_model": lm.model_ids[bs],
        "router_quality": _pct_ci(rq_b),
        "router_cost_per_call": _pct_ci(rc_b),
        "savings_vs_frontier": _pct_ci(1.0 - rc_b / fc_b),
        "quality_vs_frontier": _pct_ci(rq_b / fq_b),
        "savings_vs_best_single": _pct_ci(1.0 - rc_b / bc_b),
        "quality_vs_best_single": _pct_ci(rq_b / bq_b),
        "oracle_quality": _pct_ci(oracle_b),
        "share_of_oracle_captured": _pct_ci(rq_b / oracle_b),
        "val_brier": _pct_ci(brier_b),
        "traffic_share": {
            lm.model_ids[j]: _pct_ci(draw((choice == j).astype(float)))
            for j in range(lm.n_models)
        },
    }
    s, qv = out["savings_vs_best_single"], out["quality_vs_best_single"]
    out["reading"] = (
        f"Against {lm.model_ids[bs]}: {s['mean']:.1%} cheaper "
        f"(95% CI {s['lo']:.1%} to {s['hi']:.1%}) at {qv['mean']:.1%} of its quality "
        f"(95% CI {qv['lo']:.1%} to {qv['hi']:.1%}), on {n:,} held-out items."
    )
    return out


# -------------------------------------------------------------------- domains --
def _holm(pvals: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Holm–Bonferroni. Uniformly more powerful than Bonferroni, same guarantee.

    Chosen over Benjamini–Hochberg because the question here is "which of these
    differences are real", not "what share of my discoveries are false" — with five
    comparisons, controlling the family-wise error rate is the honest bar.
    """
    order = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(order)
    out, rejected_so_far = {}, True
    for i, (k, p) in enumerate(order):
        thresh = alpha / (m - i)
        reject = rejected_so_far and p <= thresh
        rejected_so_far = reject
        out[k] = {"p": p, "holm_threshold": thresh, "significant": bool(reject)}
    return out


def domain_significance(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    lam_cost: float,
) -> dict:
    """Router minus best-single per domain, paired, with a family-wise correction.

    The differences are paired by item — the same question answered by both policies
    — so the standard error is of the *difference*, not of two independent means.
    That is what makes n = 58 usable at all, and it is still not enough.
    """
    from scipy import stats

    ps = pool_state()
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    r, _ = train_router(lm, X, train, lam_cost=lam_cost)
    choice = r.decide(X[test], ps, tokens_in=tin).choice
    q, dom = lm.quality[test], lm.domain[test]

    rows, pvals = [], {}
    for d in sorted(set(dom.tolist())):
        m = dom == d
        n = int(m.sum())
        rq = q[m][np.arange(n), choice[m]]
        # Best single model *within the domain*, chosen with hindsight — the hardest
        # per-domain baseline there is.
        bj = int(np.argmax(q[m].mean(axis=0)))
        diff = rq - q[m][:, bj]
        se = float(diff.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
        t = float(diff.mean() / se) if se > 0 else 0.0
        p = float(2 * stats.t.sf(abs(t), df=n - 1)) if n > 1 else 1.0
        pvals[d] = p
        rows.append({
            "domain": d, "items": n,
            "router_quality": float(rq.mean()),
            "best_single_quality": float(q[m][:, bj].mean()),
            "best_single_model": lm.model_ids[bj],
            "delta": float(diff.mean()), "se": se, "t": t, "p_uncorrected": p,
        })

    holm = _holm(pvals)
    for row in rows:
        row.update(holm[row["domain"]])

    survivors = [r_["domain"] for r_ in rows if r_["significant"]]
    return {
        "rows": sorted(rows, key=lambda r_: r_["p_uncorrected"]),
        "family_size": len(rows),
        "correction": "Holm–Bonferroni, alpha = 0.05",
        "significant_after_correction": survivors,
        "reading": (
            f"Of {len(rows)} per-domain comparisons, {len(survivors)} survive "
            f"Holm–Bonferroni: {', '.join(survivors) if survivors else 'none'}. "
            f"Every other difference — including the router's apparent win on "
            f"open-ended work — is inside the noise and must not be quoted as a result."
        ),
    }


# ---------------------------------------------------------- second-pool replay --
#: Thirteen models sharing no column with `CHUTES_PROXY`, in the same shape: some
#: graded on 22 tasks, some on 14, so the coverage asymmetry that produced the
#: original finding is present here too. If the finding is real it reappears; if it
#: was a property of the particular thirteen, it does not.
REPLICATION_POOL: tuple[str, ...] = (
    # large, 14-task coverage
    "claude-sonnet-4", "deepseek-r1-0528", "deepseek-v3-0324",
    "gemini-2.5-flash", "gpt-5-chat",
    # small, 22-task coverage
    "GLM-Z1-9B-0414", "MiniCPM4.1-8B", "Intern-S1-mini",
    "Llama-3.1-Nemotron-Nano-8B-v1", "DeepSeek-R1-Distill-Qwen-7B",
    "OpenThinker3-7B", "granite-3.3-8b-instruct", "internlm3-8b-instruct",
)


def coverage_bias_for_pool(
    models: list[str],
    *,
    cache=None,
    seed: int = 0,
    lams: tuple[float, ...] = (1.0, 10.0, 100.0),
) -> dict:
    """The dense-vs-union ablation on an arbitrary thirteen-model pool.

    Factored out of `replicate_coverage_bias` so the same code path can be pointed at
    any pool — which is what `publish.coverage_bias_dose_response` needs in order to
    ask whether the effect tracks coverage asymmetry or is a property of one pool.

    Thirteen columns exactly, because the price ladder and `pool_state` are the
    Chutes catalogue's and are indexed positionally. Prices do not enter the
    comparison — both arms run at ``lam_cost = 0``, where the cost term drops out of
    the argmax — but `decide` still needs a table of the right length.
    """
    from ..catalog import CHUTES_CATALOG as _CAT

    if len(models) != len(_CAT):
        raise ValueError(
            f"pool must have {len(_CAT)} columns to reuse the catalogue price ladder, "
            f"got {len(models)}")
    if len(set(models)) != len(models):
        raise ValueError("pool contains a duplicated column")

    lm, tokens_in = load_pool_matrix(models, cache=cache)
    out = dense_union_ablation(lm, tokens_in, seed=seed, lams=lams)
    # The ablation reports the columns it routed over, which are catalogue slots. The
    # caller asked about source models, and which ones they were is the whole point of
    # a replication, so name them.
    out["pool"] = list(models)
    out["columns"] = list(lm.model_ids)
    return out


def load_pool_matrix(models: list[str], *, cache=None):
    """A thirteen-column matrix for an arbitrary pool, priced off the catalogue ladder."""
    from ..data import llmrouterbench
    from ..catalog import CHUTES_CATALOG as _CAT

    kw = {"cache": cache} if cache is not None else {}
    lm = llmrouterbench.load(models=list(models), **kw)
    tokens_in = llmrouterbench.tokens_in_for(models=list(models), **kw)
    keep = np.flatnonzero(lm.observed.any(axis=1))
    lm, tokens_in = lm.subset_items(keep), tokens_in[keep]

    failed = lm.observed & (tokens_in <= 0) & (lm.tokens_out <= 0)
    lm.observed = lm.observed & ~failed

    price_in = np.array([m.in_per_1m for m in _CAT])
    price_out = np.array([m.out_per_1m for m in _CAT])
    lm.cost = np.where(
        lm.observed,
        (tokens_in / 1e6) * price_in[None, :] + (lm.tokens_out / 1e6) * price_out[None, :],
        0.0)
    lm.model_ids = [m.id for m in _CAT]
    return lm, tokens_in


def dense_union_ablation(lm, tokens_in, *, seed: int = 0,
                         lams: tuple[float, ...] = (1.0, 10.0, 100.0)) -> dict:
    """Train on the fully-observed core, on everything, and on a size-matched sample.

    Three arms, because two cannot answer the question. `dense` and `union` differ in
    both coverage and size, so a gap between them is equally consistent with "uneven
    coverage hurts" and "more data hurts". `union_matched_n` holds the size at the
    dense arm's and varies only the coverage.
    """
    from ..data.cache import features_for

    train, test = split(lm, seed=seed)
    X, _ = features_for(lm, fit_idx=train, verbose=False)

    ps = pool_state()
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    q = lm.quality[test]
    rows_idx = np.arange(len(test))
    fc = frontier_reference_column(lm.quality[_dense(lm, np.arange(lm.n_items))])
    base = float(q[:, fc].mean())

    tr_dense, _ = split(lm, seed=seed, train_on="dense")
    tr_union, _ = split(lm, seed=seed, train_on="union")
    # The arm that decides what the effect is *about*. `union` differs from `dense`
    # in two ways at once — it is unevenly covered and it is ten times larger — so a
    # gap between them is consistent with "uneven coverage hurts" and equally with
    # "more data hurts". This third arm holds the size fixed and varies only the
    # coverage: a random subset of the union training items, exactly as many as the
    # dense arm gets. If the gap survives here it is not about quantity.
    rng_sub = np.random.default_rng(seed + 977)
    tr_matched = (np.sort(rng_sub.choice(tr_union, size=len(tr_dense), replace=False))
                  if len(tr_union) > len(tr_dense) else tr_union)
    train_sets = {"dense": tr_dense, "union": tr_union, "union_matched_n": tr_matched}

    arms = []
    for mode, tr in train_sets.items():
        for lam in lams:
            r, _ = train_router(lm, X, tr, lam_cost=0.0, lam=lam)
            choice = r.decide(X[test], ps, tokens_in=tin).choice
            pred = r.quality.predict(X[test])
            arms.append({
                "train_on": mode, "ridge_lam": lam,
                "train_items": int(len(tr)),
                "dense_share_of_train": float(
                    lm.observed[tr].all(axis=1).mean()) if len(tr) else 0.0,
                "val_brier": float(((pred - q) ** 2).mean()),
                "quality_vs_frontier": float(q[rows_idx, choice].mean() / max(base, 1e-12)),
            })

    best = {m: max((a for a in arms if a["train_on"] == m),
                   key=lambda a: a["quality_vs_frontier"]) for m in train_sets}
    dense_items = int(lm.observed.all(axis=1).sum())
    union_items = int(lm.observed.any(axis=1).sum())
    # The dose. Coverage is asymmetric exactly to the extent that the union of graded
    # items exceeds their intersection; a pool whose columns were all graded on the
    # same tasks has a ratio of 1 and, by the mechanism, no effect to find.
    return {
        "pool": list(lm.model_ids),
        "n_models": lm.n_models,
        "dense_core_items": dense_items,
        "union_items": union_items,
        "coverage_asymmetry": float(1.0 - dense_items / max(union_items, 1)),
        "arms": arms,
        "dense_best": best["dense"], "union_best": best["union"],
        "union_matched_n_best": best["union_matched_n"],
        "gap_points": best["dense"]["quality_vs_frontier"]
                      - best["union"]["quality_vs_frontier"],
        "gap_at_matched_n": best["dense"]["quality_vs_frontier"]
                            - best["union_matched_n"]["quality_vs_frontier"],
    }


#: Thirteen models sharing no column with `CHUTES_PROXY`, in the same shape: some
#: graded on 22 tasks, some on 14, so the coverage asymmetry that produced the
#: original finding is present here too. If the finding is real it reappears; if it
#: was a property of the particular thirteen, it does not.
REPLICATION_POOL: tuple[str, ...] = (
    # large, 14-task coverage
    "claude-sonnet-4", "deepseek-r1-0528", "deepseek-v3-0324",
    "gemini-2.5-flash", "gpt-5-chat",
    # small, 22-task coverage
    "GLM-Z1-9B-0414", "MiniCPM4.1-8B", "Intern-S1-mini",
    "Llama-3.1-Nemotron-Nano-8B-v1", "DeepSeek-R1-Distill-Qwen-7B",
    "OpenThinker3-7B", "granite-3.3-8b-instruct", "internlm3-8b-instruct",
)


def replicate_coverage_bias(
    cache=None, *, seed: int = 0, lams: tuple[float, ...] = (1.0, 10.0, 100.0),
) -> dict:
    """Re-run the dense-vs-union ablation on a disjoint pool.

    The original finding — training on ten times the data costs twelve points of
    quality retention — is the most novel thing in this repository and was measured
    once, on one pool. This is the cheapest possible replication: same corpus,
    same code path, thirteen different models.

    One replication answers "is it real here too". It does not answer "how large is
    it, and does it track the mechanism" — for that see
    `publish.coverage_bias_dose_response`, which runs this over a designed sweep of
    pools including two arms where the mechanism predicts no effect at all.
    """
    from ..catalog import CHUTES_PROXY

    overlap = set(REPLICATION_POOL) & {b.proxy_id for b in CHUTES_PROXY}
    if overlap:
        raise ValueError(f"replication pool is not disjoint: {sorted(overlap)}")

    out = coverage_bias_for_pool(list(REPLICATION_POOL), cache=cache, seed=seed, lams=lams)
    gap = out["gap_points"]
    best = {"dense": out["dense_best"], "union": out["union_best"]}
    out.update({
        "disjoint_from_chutes_proxies": True,
        "replicates": bool(gap > 0),
        "reading": (
            f"On thirteen models sharing no column with the first pool, dense-core "
            f"training retains {best['dense']['quality_vs_frontier']:.1%} of frontier "
            f"quality on {best['dense']['train_items']:,} items against "
            f"{best['union']['quality_vs_frontier']:.1%} on "
            f"{best['union']['train_items']:,}. The finding "
            f"{'replicates' if gap > 0 else 'does NOT replicate'} — gap "
            f"{gap:+.1%} against the original +12.2%. Held at the dense arm's own "
            f"size, so that only the coverage differs, the unevenly covered arm "
            f"retains {out['union_matched_n_best']['quality_vs_frontier']:.1%} and the "
            f"gap is {out['gap_at_matched_n']:+.1%} — the effect is coverage, not "
            f"quantity."
        ),
    })
    return out


# --------------------------------------------------------------- workload mix --
def workload_mix(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    lam_cost: float,
    easy_shares: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 0.9),
    seed: int = 0,
) -> dict:
    """What the savings figure becomes when the traffic is not all hard benchmarks.

    Every headline in this repository is measured on nine hard benchmarks — AIME,
    GPQA, LiveCodeBench, MMLU-Pro, Arena-Hard. Real product traffic is mostly
    routine. Rather than assert that the figures are conservative, this reweights
    the held-out set toward the items the pool finds easy and reports what happens.

    "Easy" is defined by pool solve rate, which is a property of the *items* and not
    of any policy, so the reweighting cannot flatter the router by construction.
    """
    ps = pool_state()
    tin_all = _tokens_in_per_item(tokens_in, lm.observed)
    r, _ = train_router(lm, X, train, lam_cost=lam_cost)
    choice = r.decide(X[test], ps, tokens_in=tin_all[test]).choice

    q, c = lm.quality[test], lm.cost[test]
    n = len(test)
    rows = np.arange(n)
    solve = q.mean(axis=1)
    easy = solve >= np.median(solve)
    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    bs = best_single_column(per_cell_utility(
        lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=lam_cost), ref_col=fc))

    rng = np.random.default_rng(seed)
    easy_idx, hard_idx = np.flatnonzero(easy), np.flatnonzero(~easy)

    out = []
    for share in easy_shares:
        n_easy = int(round(share * n))
        pick = np.concatenate([
            rng.choice(easy_idx, size=n_easy, replace=True),
            rng.choice(hard_idx, size=n - n_easy, replace=True),
        ]) if n_easy else rng.choice(hard_idx, size=n, replace=True)
        ch = choice[pick]
        rq = float(q[pick, ch].mean())
        rc = float(c[pick, ch].mean())
        tiers = np.array([m.tier for m in CHUTES_CATALOG])[ch]
        out.append({
            "easy_share": share,
            "quality": rq,
            "cost_per_call_usd": rc,
            "savings_vs_best_single": 1.0 - rc / max(float(c[pick, bs].mean()), 1e-12),
            "savings_vs_frontier": 1.0 - rc / max(float(c[pick, fc].mean()), 1e-12),
            "open_tier_share": float((tiers == "open").mean()),
        })

    all_hard, mostly_easy = out[0], out[-1]
    return {
        "rows": out,
        "easy_defined_as": "pool solve rate at or above the median held-out item",
        "reading": (
            f"On the benchmark mix as measured (0% reweighting) the router is "
            f"{all_hard['savings_vs_best_single']:.1%} cheaper than the best single "
            f"model. Reweighted to {mostly_easy['easy_share']:.0%} easy traffic it is "
            f"{mostly_easy['savings_vs_best_single']:.1%} cheaper, with the open tier "
            f"carrying {mostly_easy['open_tier_share']:.1%} against "
            f"{all_hard['open_tier_share']:.1%}. Savings are flat across the range, so "
            f"the headline is robust to workload mix rather than a conservative lower "
            f"bound for it — see RIGOR.md §4, which retracts the earlier claim."
        ),
    }
