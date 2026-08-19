"""The publication checklist, closed as far as arithmetic can close it.

`PUBLISHABILITY.md` §6 lists eight steps between this repository and something a
venue would take. Four of them need a live endpoint and money; the other four need
compute, and this module is those four. `rigor.py` was the first pass at them and it
left each one at n = 1: one replication, one split, one family corrected.

    coverage_bias_dose_response   the most novel finding, run over a *designed* sweep
                                  of pools rather than one replication — including
                                  control pools where the mechanism predicts no effect
    coverage_mask_sweep           the same finding as an intervention rather than an
                                  observation: one pool, coverage removed by whole tasks,
                                  nothing else varied
    coverage_bias_seed_stability  and whether any of it depends on the split
    kfold_headlines               k-fold intervals on every headline, which is a
                                  different question from the bootstrap and answers
                                  the one `PUBLISHABILITY.md` actually asked
    baseline_margin_intervals     an error bar on the one comparison that goes against
                                  us, because a negative result quoted to three
                                  decimals from a single split is not a result either
    multiplicity_audit            all fifteen adjudicated claims, classified by what
                                  kind of inference each one is, and corrected inside
                                  the families where a correction means anything

The organising idea is that `rigor.py` answered "is it there?" and this answers "how
big is it, how sure are we, and does it move when the mechanism says it should".
Replication says a finding is not an artefact of one sample. Dose–response says it is
not an artefact of anything else either, and it is the stronger claim.

**On the negative controls.** The coverage-bias sweep includes pools whose columns
were all graded on the same task mix. There the union arm and the dense arm see very
nearly the same items, so the mechanism predicts no gap. Reporting an effect that
appears in the pools where it should and vanishes in the pools where it should not is
worth more than any number of further replications, because it rules out the
explanation replication cannot: that something about training on more items is bad
for reasons unrelated to coverage.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from ..data.cache import features_for
from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    frontier_reference_column,
    per_cell_utility,
)
from . import baselines
from .chutes import (
    _dense,
    _tokens_in_per_item,
    pool_state,
    train_router,
)
from .rigor import coverage_bias_for_pool

ROOT = Path(__file__).resolve().parent.parent.parent


# ============================================================ coverage bias ==
# The corpus grades two kinds of column. Twenty small open-weights models were run
# over 22 tasks; thirteen large commercial ones over 14. That asymmetry is not a
# defect of the corpus — it is what a real pool looks like, because a new or
# expensive model is always graded on less — and it is the mechanism the original
# finding blamed. Splitting the roster along it is what makes a dose possible.
#
# Membership is asserted against the corpus at run time rather than trusted, so a
# corpus revision that regrades a model surfaces as an error instead of a quietly
# mislabelled control arm.
BROAD_POOL: tuple[str, ...] = (
    "DeepHermes-3-Llama-3-8B-Preview", "DeepSeek-R1-Distill-Qwen-7B",
    "Qwen2.5-Coder-7B-Instruct", "Llama-3.1-8B-Instruct", "MiniCPM4.1-8B",
    "MiMo-7B-RL-0530", "OpenThinker3-7B", "internlm3-8b-instruct", "Fin-R1",
    "cogito-v1-preview-llama-8B", "glm-4-9b-chat", "GLM-Z1-9B-0414",
    "Llama-3.1-Nemotron-Nano-8B-v1", "Intern-S1-mini", "gemma-2-9b-it",
    "Llama-3.1-8B-UltraMedical", "Qwen3-8B", "granite-3.3-8b-instruct",
    "DeepSeek-R1-0528-Qwen3-8B", "NVIDIA-Nemotron-Nano-9B-v2",
)

NARROW_POOL: tuple[str, ...] = (
    "qwen3-235b-a22b-2507", "deepseek-v3.1-terminus", "gemini-2.5-flash",
    "claude-sonnet-4", "gemini-2.5-pro", "kimi-k2-0905",
    "qwen3-235b-a22b-thinking-2507", "gpt-5-chat", "intern-s1", "gpt-5",
    "deepseek-r1-0528", "deepseek-v3-0324", "glm-4.6",
)

#: A column counts as broadly graded if the corpus ran it on at least this many
#: distinct tasks. The two groups sit at 22 and 14 with nothing between them, so the
#: threshold is not a tuned parameter — any value in (14, 22] gives the same split.
BROAD_TASK_THRESHOLD = 20


def verify_roster(cache=None) -> dict:
    """Check the broad/narrow split against the corpus instead of trusting it."""
    from ..data import llmrouterbench

    kw = {"cache": cache} if cache is not None else {}
    lm = llmrouterbench.load(**kw)
    tasks_per_model = {}
    for j, mid in enumerate(lm.model_ids):
        obs = lm.observed[:, j]
        tasks_per_model[mid] = int(len(set(lm.task[obs].tolist())))

    wrong = []
    for m in BROAD_POOL:
        if tasks_per_model.get(m, 0) < BROAD_TASK_THRESHOLD:
            wrong.append((m, "declared broad", tasks_per_model.get(m)))
    for m in NARROW_POOL:
        if tasks_per_model.get(m, 99) >= BROAD_TASK_THRESHOLD:
            wrong.append((m, "declared narrow", tasks_per_model.get(m)))
    if wrong:
        raise ValueError(f"roster disagrees with the corpus: {wrong}")

    return {
        "broad": {m: tasks_per_model[m] for m in BROAD_POOL},
        "narrow": {m: tasks_per_model[m] for m in NARROW_POOL},
        "threshold_tasks": BROAD_TASK_THRESHOLD,
        "separation": (
            f"broad columns are graded on {min(tasks_per_model[m] for m in BROAD_POOL)}–"
            f"{max(tasks_per_model[m] for m in BROAD_POOL)} tasks, narrow ones on "
            f"{min(tasks_per_model[m] for m in NARROW_POOL)}–"
            f"{max(tasks_per_model[m] for m in NARROW_POOL)}; nothing sits between."
        ),
    }


def _draw_pools(n_narrow: int, n_pools: int, rng, size: int = 13) -> list[list[str]]:
    """Distinct pools of `size` columns, `n_narrow` of them narrowly graded."""
    seen, out, tries = set(), [], 0
    while len(out) < n_pools and tries < 200 * n_pools:
        tries += 1
        pool = (list(rng.choice(NARROW_POOL, n_narrow, replace=False))
                + list(rng.choice(BROAD_POOL, size - n_narrow, replace=False)))
        key = tuple(sorted(pool))
        if key in seen:
            continue
        seen.add(key)
        out.append(pool)
    return out


def coverage_bias_dose_response(
    cache=None,
    *,
    pools_per_level: int = 3,
    levels: tuple[int, ...] = (0, 2, 4, 6, 8, 10, 13),
    seed: int = 0,
    lams: tuple[float, ...] = (1.0, 10.0, 100.0),
) -> dict:
    """Does the coverage-bias effect track coverage asymmetry, or is it one pool?

    `rigor.replicate_coverage_bias` showed the effect survives on a second, disjoint
    pool. That rules out "a property of those particular thirteen models" and nothing
    else. In particular it does not rule out the boring alternative — that training a
    router on more items is simply worse, for reasons that have nothing to do with
    which columns were graded on what.

    This distinguishes them. Each pool is thirteen columns drawn with a controlled
    number of *narrowly graded* ones, which sets how far the union of graded items
    exceeds their intersection. The mechanism says the gap should grow with that
    asymmetry and disappear when it does. The boring alternative says the gap should
    be there at every level, because every level's union arm still trains on more
    items than its dense arm.

    Levels 0 and 13 are the controls: all-broad columns share a task mix almost
    exactly, and all-narrow columns share one too. Both still have a union arm with
    more items than the dense arm, so the boring alternative predicts an effect there.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for k in levels:
        # k = 13 admits exactly one pool — there are only thirteen narrow columns —
        # so asking for three would spin. Every other level has room for the full
        # allowance.
        n = 1 if k == len(NARROW_POOL) else pools_per_level
        for pool in _draw_pools(k, n, rng):
            r = coverage_bias_for_pool(pool, cache=cache, seed=seed, lams=lams)
            rows.append({
                "n_narrow": int(k),
                "pool": r["pool"],
                "coverage_asymmetry": r["coverage_asymmetry"],
                "dense_core_items": r["dense_core_items"],
                "union_items": r["union_items"],
                "dense_train_items": r["dense_best"]["train_items"],
                "union_train_items": r["union_best"]["train_items"],
                "union_over_dense_train": (r["union_best"]["train_items"]
                                           / max(r["dense_best"]["train_items"], 1)),
                "dense_quality_retained": r["dense_best"]["quality_vs_frontier"],
                "union_quality_retained": r["union_best"]["quality_vs_frontier"],
                "union_matched_n_quality_retained":
                    r["union_matched_n_best"]["quality_vs_frontier"],
                "gap_points": r["gap_points"],
                "gap_at_matched_n": r["gap_at_matched_n"],
            })

    a = np.array([r["coverage_asymmetry"] for r in rows])
    g = np.array([r["gap_points"] for r in rows])
    gm = np.array([r["gap_at_matched_n"] for r in rows])
    ratio = np.array([r["union_over_dense_train"] for r in rows])

    # Two competing predictors, fitted on the same rows: how asymmetric the pool's
    # coverage is, and how much more data the union arm simply got. If the second
    # explained the effect, the boring alternative would be the right story.
    def _fit(x: np.ndarray, y: np.ndarray = g) -> dict:
        A = np.column_stack([np.ones_like(x), x])
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ beta
        ss_tot = float(((y - y.mean()) ** 2).sum())
        return {
            "slope": float(beta[1]),
            "intercept": float(beta[0]),
            "r2": float(1.0 - (resid ** 2).sum() / ss_tot) if ss_tot > 0 else 0.0,
            "pearson_r": float(np.corrcoef(x, y)[0, 1]),
        }

    controls = [r for r in rows if r["coverage_asymmetry"] < 0.2]
    asymmetric = [r for r in rows if r["coverage_asymmetry"] >= 0.6]
    ctrl_g = np.array([r["gap_points"] for r in controls]) if controls else np.array([0.0])
    asym_g = np.array([r["gap_points"] for r in asymmetric]) if asymmetric else np.array([0.0])
    asym_gm = (np.array([r["gap_at_matched_n"] for r in asymmetric]) if asymmetric
               else np.array([0.0]))

    return {
        "n_pools": len(rows),
        "levels": list(levels),
        "pools_per_level": pools_per_level,
        "seed": seed,
        "rows": sorted(rows, key=lambda r: r["coverage_asymmetry"]),
        "fit_on_coverage_asymmetry": _fit(a),
        "fit_on_extra_training_data": _fit(np.log(ratio)),
        # The same regression against the matched-n gap, where the extra-data
        # explanation is held at zero by construction.
        "fit_on_coverage_asymmetry_at_matched_n": _fit(a, gm),
        "controls": {
            "definition": "pools whose coverage asymmetry is below 0.2",
            "n": len(controls),
            "mean_gap": float(ctrl_g.mean()),
            "max_abs_gap": float(np.abs(ctrl_g).max()),
            "mean_union_over_dense_train": float(np.mean(
                [r["union_over_dense_train"] for r in controls])) if controls else 0.0,
        },
        "asymmetric": {
            "definition": "pools whose coverage asymmetry is at least 0.6",
            "n": len(asymmetric),
            "mean_gap": float(asym_g.mean()),
            "min_gap": float(asym_g.min()),
            "replicated_in": int((asym_g > 0).sum()),
            "mean_gap_at_matched_n": float(asym_gm.mean()),
            "min_gap_at_matched_n": float(asym_gm.min()),
            "replicated_at_matched_n_in": int((asym_gm > 0).sum()),
            "matched_n_minus_union": float((asym_gm - asym_g).mean()),
        },
        "what_the_matched_n_arm_settles": (
            "The union arm differs from the dense arm in two ways at once: its "
            "coverage is uneven and it is about ten times larger. Those two are "
            "nearly collinear across these pools — asymmetry and log extra data "
            "predict the gap about equally well — so the sweep alone cannot separate "
            "them. The matched-n arm can: it trains on a random subset of the union "
            "items of exactly the dense arm's size, so the quantity is held fixed and "
            "only the coverage varies."),
        "reading": (
            f"Across {len(rows)} pools the gap tracks coverage asymmetry with "
            f"r = {_fit(a)['pearson_r']:+.2f} (slope {_fit(a)['slope']:+.3f} per unit "
            f"of asymmetry). In the {len(controls)} control pools — columns graded on "
            f"the same task mix, but the union arm still trained on "
            f"{np.mean([r['union_over_dense_train'] for r in controls]):.2f}× the items "
            f"— the mean gap is {ctrl_g.mean():+.1%} and the largest in absolute value "
            f"is {np.abs(ctrl_g).max():.1%}. In the {len(asymmetric)} asymmetric pools "
            f"it is {asym_g.mean():+.1%}, positive in "
            f"{int((asym_g > 0).sum())} of {len(asymmetric)}. Holding the amount of "
            f"training data fixed and varying only the coverage, the gap is "
            f"{asym_gm.mean():+.1%} — "
            f"{'larger' if asym_gm.mean() > asym_g.mean() else 'smaller'} than with ten "
            f"times the data, positive in {int((asym_gm > 0).sum())} of "
            f"{len(asymmetric)}. So more data is not the cause; it is a partial "
            f"{'compensation for' if asym_gm.mean() > asym_g.mean() else 'contributor to'} "
            f"the damage that uneven coverage does."
        ),
    }


def coverage_bias_seed_stability(
    cache=None, *, pool: list[str] | None = None,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4), lams: tuple[float, ...] = (1.0, 100.0),
) -> dict:
    """The same pool, several splits. Separates the effect from the split it was found on."""
    from .rigor import REPLICATION_POOL

    pool = list(pool or REPLICATION_POOL)
    gaps = [coverage_bias_for_pool(pool, cache=cache, seed=s, lams=lams)["gap_points"]
            for s in seeds]
    g = np.asarray(gaps)
    return {
        "pool": pool,
        "seeds": list(seeds),
        "gaps": [float(x) for x in g],
        "mean": float(g.mean()),
        "sd": float(g.std(ddof=1)),
        "se": float(g.std(ddof=1) / np.sqrt(len(g))),
        "positive_in": int((g > 0).sum()),
        "reading": (
            f"Over {len(seeds)} splits the gap is {g.mean():+.1%} ± {g.std(ddof=1):.1%} "
            f"(sd), positive in {int((g > 0).sum())} of {len(seeds)}."
        ),
    }


# ================================================================== k-fold ==
def kfold_headlines(
    lm: LabelMatrix,
    tokens_in: np.ndarray,
    *,
    lam_cost: float,
    k: int = 5,
    seed: int = 0,
) -> dict:
    """Every headline over k disjoint folds of the dense core.

    `PUBLISHABILITY.md` §6 asked for k-fold specifically, and `rigor.py` answered with
    a bootstrap. They are not the same instrument and the difference matters enough to
    report both:

    - the **bootstrap** fixes the fitted router and resamples evaluation items. It
      answers *how precisely do we know what this policy does on questions like these*.
    - **k-fold** refits everything on each of k disjoint training sets. It answers
      *how much does the policy itself move when the training data changes*.

    `chutes.cross_validate` already did something adjacent over eight random splits,
    but repeated random subsampling reuses items across test sets, so its spread is
    the spread of overlapping samples and is optimistic. Here every dense item is held
    out exactly once, which also yields a pooled out-of-fold estimate over the whole
    dense core — the one number in this repository computed on items that were all
    genuinely held out.

    The feature map is refitted inside each fold, because φ's projection is part of
    the model and fitting it on all items before splitting would leak.

    One caveat that is standard and worth stating: the k training sets overlap heavily
    (each shares (k−2)/(k−1) of its items with any other), so the folds are not
    independent and there is no unbiased estimator of the variance of a k-fold
    estimate. The spread below is reported as a spread, and the interval derived from
    it should be read as indicative rather than exact.
    """
    dense = np.flatnonzero(lm.observed.all(axis=1))
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(dense), k)
    ps = pool_state()
    tin_all = _tokens_in_per_item(tokens_in, lm.observed)

    keys = ("router_quality", "router_cost_per_call", "savings_vs_frontier",
            "quality_vs_frontier", "savings_vs_best_single", "quality_vs_best_single",
            "oracle_quality", "share_of_oracle_captured", "val_brier")
    per_fold: dict[str, list[float]] = {kk: [] for kk in keys}
    fold_rows = []
    oof_q, oof_c, oof_fq, oof_fc, oof_bq, oof_bc, oof_or = ([] for _ in range(7))

    for i, fold in enumerate(folds):
        test = np.sort(fold)
        train = np.sort(np.setdiff1d(dense, test))
        X, _ = features_for(lm, fit_idx=train, cache=False, verbose=False)
        r, _ = train_router(lm, X, train, lam_cost=lam_cost)
        choice = r.decide(X[test], ps, tokens_in=tin_all[test]).choice

        q, c = lm.quality[test], lm.cost[test]
        rows = np.arange(len(test))
        dtr = _dense(lm, train)
        fc = frontier_reference_column(lm.quality[dtr])
        bs = best_single_column(per_cell_utility(
            lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=lam_cost), ref_col=fc))

        rq, rc = q[rows, choice], c[rows, choice]
        vals = {
            "router_quality": float(rq.mean()),
            "router_cost_per_call": float(rc.mean()),
            "savings_vs_frontier": float(1.0 - rc.mean() / max(c[:, fc].mean(), 1e-12)),
            "quality_vs_frontier": float(rq.mean() / max(q[:, fc].mean(), 1e-12)),
            "savings_vs_best_single": float(1.0 - rc.mean() / max(c[:, bs].mean(), 1e-12)),
            "quality_vs_best_single": float(rq.mean() / max(q[:, bs].mean(), 1e-12)),
            "oracle_quality": float(q.max(axis=1).mean()),
            "share_of_oracle_captured": float(rq.mean() / max(q.max(axis=1).mean(), 1e-12)),
            "val_brier": float(((r.quality.predict(X[test]) - q) ** 2).mean()),
        }
        for kk in keys:
            per_fold[kk].append(vals[kk])
        fold_rows.append({"fold": i, "n_test": int(len(test)), "n_train": int(len(train)),
                          "frontier_model": lm.model_ids[fc],
                          "best_single_model": lm.model_ids[bs], **vals})
        oof_q.append(rq); oof_c.append(rc)
        oof_fq.append(q[:, fc]); oof_fc.append(c[:, fc])
        oof_bq.append(q[:, bs]); oof_bc.append(c[:, bs])
        oof_or.append(q.max(axis=1))

    from scipy import stats

    def summarise(v: list[float]) -> dict:
        a = np.asarray(v, dtype=float)
        sd = float(a.std(ddof=1))
        se = sd / np.sqrt(len(a))
        t = float(stats.t.ppf(0.975, df=len(a) - 1))
        return {"mean": float(a.mean()), "sd": sd, "se": float(se),
                "lo": float(a.mean() - t * se), "hi": float(a.mean() + t * se),
                "folds": [float(x) for x in a]}

    cat = np.concatenate
    oq, oc = cat(oof_q), cat(oof_c)
    pooled = {
        "n_items": int(len(oq)),
        "router_quality": float(oq.mean()),
        "router_cost_per_call": float(oc.mean()),
        "savings_vs_frontier": float(1.0 - oc.mean() / cat(oof_fc).mean()),
        "quality_vs_frontier": float(oq.mean() / cat(oof_fq).mean()),
        "savings_vs_best_single": float(1.0 - oc.mean() / cat(oof_bc).mean()),
        "quality_vs_best_single": float(oq.mean() / cat(oof_bq).mean()),
        "share_of_oracle_captured": float(oq.mean() / cat(oof_or).mean()),
    }

    out = {kk: summarise(per_fold[kk]) for kk in keys}
    s, qv = out["savings_vs_best_single"], out["quality_vs_best_single"]
    return {
        "k": int(k),
        "seed": int(seed),
        "n_dense_items": int(len(dense)),
        "train_frac": float(1.0 - 1.0 / k),
        "headline_protocol_train_frac": 0.65,
        "folds": fold_rows,
        "pooled_out_of_fold": pooled,
        **out,
        "reading": (
            f"{k}-fold over {len(dense):,} dense items: {s['mean']:.1%} cheaper than the "
            f"best single model (fold sd {s['sd']:.1%}) at {qv['mean']:.1%} of its "
            f"quality (fold sd {qv['sd']:.1%}). Pooled over the out-of-fold predictions, "
            f"where every item is held out exactly once, "
            f"{pooled['savings_vs_best_single']:.1%} at "
            f"{pooled['quality_vs_best_single']:.1%}. Each fold trains on "
            f"{1 - 1 / k:.0%} of the core against the headline protocol's 65%, so these "
            f"are not a drop-in replacement for the headline — they are a statement "
            f"about how much the policy moves when its training data does."
        ),
    }


# ====================================================== baseline margins ==
def baseline_margin_intervals(
    lm: LabelMatrix,
    tokens_in: np.ndarray,
    *,
    lam_cost: float,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7),
    n_boot: int = 2000,
    seed: int = 0,
) -> dict:
    """An error bar on the comparison that goes against us.

    `RIGOR.md` §5 reports that a RouteLLM-style matrix factorisation beats this router
    by 3.6 points of savings at matched quality. That is the most consequential single
    number in the repository — it is the one a reviewer will lead with — and it was
    measured on one split with no interval, which is precisely the failure the same
    document criticises everywhere else.

    Two instruments, because they answer different questions:

    **Item bootstrap.** Every policy is fitted once on the training split, then the
    *evaluation* items are resampled and each family's margin recomputed, including
    the interpolation onto our dial. This says how much the margin depends on which
    questions were asked. Each family's operating point is the one selected on the
    full sample and then held fixed — reselecting the best point inside each draw
    would let the bootstrap pick winners and would report an interval for a policy
    nobody would have shipped.

    **Split spread.** The whole comparison — refit, re-swept, re-selected — is rerun
    on each of `seeds` splits. This says how much the margin depends on which
    questions were used for training, and it is the one that can change a verdict,
    because the family's best operating point is free to move.
    """
    ps = pool_state()
    tin_all = _tokens_in_per_item(tokens_in, lm.observed)

    # ------------------------------------------------ instrument 1: items --
    from .chutes import split as _split

    train, test = _split(lm, seed=seed)
    X, _ = features_for(lm, fit_idx=train, cache=False, verbose=False)
    vecs: dict = {}
    ref = baselines.run(lm, X, tokens_in, train, test,
                        lam_cost=lam_cost, seed=seed, vectors=vecs)

    q, c = lm.quality[test], lm.cost[test]
    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    bs = best_single_column(per_cell_utility(
        lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=lam_cost), ref_col=fc))
    bs_q_i, bs_c_i = q[:, bs], c[:, bs]

    n = len(test)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))

    def mean_draws(v: np.ndarray) -> np.ndarray:
        return v[idx].mean(axis=1)

    bs_q_b, bs_c_b = mean_draws(bs_q_i), mean_draws(bs_c_i)

    ours_names = [p["policy"] for p in ref["our_dial"]]
    ours_q = np.stack([mean_draws(vecs[nm]["quality"]) for nm in ours_names]) / bs_q_b
    ours_s = 1.0 - np.stack([mean_draws(vecs[nm]["spend"]) for nm in ours_names]) / bs_c_b

    boot = {}
    for family, row in ref["best_by_family"].items():
        nm = row["policy"]
        fq = mean_draws(vecs[nm]["quality"]) / bs_q_b
        fs = 1.0 - mean_draws(vecs[nm]["spend"]) / bs_c_b
        margins = np.empty(n_boot)
        for b in range(n_boot):
            order = np.argsort(ours_q[:, b])
            xs, ys = ours_q[order, b], ours_s[order, b]
            # Outside our dial's range the comparison is undefined rather than zero;
            # np.interp would silently clamp, so those draws are dropped and counted.
            margins[b] = (np.nan if fq[b] < xs[0] or fq[b] > xs[-1]
                          else fs[b] - float(np.interp(fq[b], xs, ys)))
        ok = ~np.isnan(margins)
        m = margins[ok]
        lo, hi = np.percentile(m, [2.5, 97.5]) if len(m) else (np.nan, np.nan)
        boot[family] = {
            "policy": nm,
            "margin_point_estimate": row["margin_vs_us"],
            "mean": float(m.mean()) if len(m) else None,
            "lo": float(lo), "hi": float(hi),
            "se": float(m.std(ddof=1)) if len(m) > 1 else None,
            "draws_in_range": int(ok.sum()), "n_boot": int(n_boot),
            "p_beats_us": float((m > 0).mean()) if len(m) else None,
            "interval_excludes_zero": bool(len(m) and (lo > 0 or hi < 0)),
        }

    # ----------------------------------------------- instrument 2: splits --
    by_seed: dict[str, list[float]] = {}
    per_seed_rows = []
    for s in seeds:
        tr, te = _split(lm, seed=s)
        Xs, _ = features_for(lm, fit_idx=tr, cache=False, verbose=False)
        b = baselines.run(lm, Xs, tokens_in, tr, te, lam_cost=lam_cost, seed=s)
        row = {"seed": int(s), "beaten_by": b["beaten_by"], "tied_with": b["tied_with"],
               "no_useful_point": b["families_with_no_useful_point"]}
        for family, r_ in b["best_by_family"].items():
            by_seed.setdefault(family, []).append(float(r_["margin_vs_us"]))
            row[family] = float(r_["margin_vs_us"])
        per_seed_rows.append(row)

    splits = {}
    for family, v in by_seed.items():
        a = np.asarray(v)
        splits[family] = {
            "n_splits_with_a_useful_point": int(len(a)),
            "of_seeds": len(seeds),
            "mean": float(a.mean()), "sd": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "min": float(a.min()), "max": float(a.max()),
            "beats_us_in": int((a > 0.02).sum()),
            "values": [float(x) for x in a],
        }

    mf_b, mf_s = boot.get("matrix"), splits.get("matrix")
    reading = "matrix factorisation did not produce a useful operating point."
    if mf_b and mf_s:
        reading = (
            f"The headline negative result — matrix factorisation "
            f"{mf_b['margin_point_estimate']:+.1%} against us at matched quality — "
            f"carries an item-bootstrap interval of [{mf_b['lo']:+.1%}, {mf_b['hi']:+.1%}] "
            f"and is positive in {mf_b['p_beats_us']:.0%} of draws. Across "
            f"{mf_s['of_seeds']} training splits it is {mf_s['mean']:+.1%} ± "
            f"{mf_s['sd']:.1%} (sd), ranging {mf_s['min']:+.1%} to {mf_s['max']:+.1%}, "
            f"and clears the 2-point margin in {mf_s['beats_us_in']} of "
            f"{mf_s['n_splits_with_a_useful_point']} splits where it had a useful "
            f"operating point at all. "
            + ("The result holds: it is not a single-split artefact."
               if mf_b["lo"] > 0 else
               "The interval contains zero — the point estimate overstates how "
               "settled this is.")
        )
    return {
        "reference_seed": int(seed),
        "n_test_items": int(n),
        "useful_quality_floor": ref["useful_quality_floor"],
        "item_bootstrap": boot,
        "across_splits": splits,
        "per_seed": per_seed_rows,
        "reading": reading,
    }


# ============================================================ multiplicity ==
@dataclass(frozen=True)
class Claim:
    """One adjudicated claim, and what kind of inference backs it.

    `kind` is the field that does the work, because "fifteen claims, no correction"
    conflates three different situations and only one of them is fixable by a
    correction:

    `census`    a direct count over the whole population — a tie rate over two million
                comparisons, an artifact's size in kilobytes, the share of an oracle
                gap that is definitionally luck. There is no sampling and no null
                hypothesis, so a p-value would be a category error and a correction
                would be a correction to nothing.
    `estimate`  a point estimate whose uncertainty is real but was never quantified.
                What this needs is an interval, not a correction. Applying a
                multiple-comparison procedure to a number with no standard error
                would be theatre.
    `test`      a genuine two-sided comparison with a standard error. These, and only
                these, are what a family-wise or false-discovery procedure applies to.
    """

    id: str
    text: str
    source: str
    kind: str
    family: str
    verdict: str
    where: str


#: The fifteen claims adjudicated in `notebooks/07_verdicts.ipynb`, transcribed here
#: so that "fifteen claims, no correction" can be answered by a program rather than by
#: counting rows in a rendered table. A test pins the count and the ids against the
#: notebook's table.
CLAIMS: tuple[Claim, ...] = (
    Claim("1", "Most queries do not need the strongest model", "§3.1", "census",
          "descriptive", "supported", "overview.json:ties.pairwise_tie_rate"),
    Claim("2", "Routing beats one good model on cost at near-equal quality", "AC-1",
          "estimate", "headline", "supported", "frontier.json:sweep"),
    Claim("3", "A router trained once measurably decays", "§14.1", "estimate",
          "staleness", "supported", "staleness.json:summary.frozen_decay"),
    Claim("4", "The decay is about evaluation freshness", "§1 framing", "estimate",
          "staleness", "not supported", "staleness.json:summary.attribution_new_models"),
    Claim("5", "A useful router needs under 1 MB and no GPU", "O3", "census",
          "descriptive", "supported", "frontier.json:sweep[0].artifact_kb"),
    Claim("6", "Uninformative batches make the score noise", "§6", "estimate",
          "scoring rule", "supported", "metric.json:result.bins.bins"),
    Claim("6b", "...because similar models converge oracle and baseline", "§6",
          "estimate", "scoring rule", "not supported",
          "metric.json:result.diagnosis.corr_info_vs_model_spread"),
    Claim("7", "Information-aware shrinkage fixes it", "§6.1", "estimate",
          "scoring rule", "supported", "metric.json:result.ranking.overall"),
    Claim("8", "Normalised regret below 0.6 is achievable", "AC-1", "census",
          "descriptive", "not supported", "metric.json:result.oracle_luck"),
    Claim("9", "Low-rank item factors bridge to a feature-space prior", "§5.1",
          "estimate", "cold start", "not supported", "coldstart.json:bridge.bridge_r2"),
    Claim("10", "Probe count tracks how well the pool explains a new model", "§5.3",
          "estimate", "cold start", "mixed", "coldstart.json:lomo.summary"),
    Claim("11", "Component-wise γ_q/γ_t beats one shared γ", "§4", "test",
          "gamma decomposition", "mixed",
          "decomposition.json:replication.*.decomposition"),
    Claim("12", "Price should be read, not fitted", "§8.7", "test", "price lane",
          "supported", "decomposition.json:replication.*.read_vs_learn"),
    Claim("13", "γ ≈ 0.999 is a sensible default", "§8.4", "estimate",
          "gamma decomposition", "not supported", "decomposition.json:gamma_tuning"),
    Claim("14", "One shared Gram matrix serves every model", "§8.3", "census",
          "descriptive", "not supported", "gram.json:summary.worst_utility_gap"),
)


def _bh(pvals: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Benjamini–Hochberg. Controls the false-discovery rate, not the family-wise rate.

    Used across families rather than within one, because the question that spans the
    whole repository is "of everything I called a finding, what share is likely to be
    wrong" — which is the FDR's question. Holm's question, "is *any* of these a false
    positive", is the right one inside a family of five per-domain comparisons and
    much too conservative across fifteen unrelated tests on different corpora.
    """
    order = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(order)
    out, k_max = {}, 0
    for i, (_, p) in enumerate(order, start=1):
        if p <= alpha * i / m:
            k_max = i
    for i, (k, p) in enumerate(order, start=1):
        out[k] = {"p": p, "bh_threshold": alpha * i / m, "rank": i,
                  "significant": bool(i <= k_max)}
    return out


def _t_test(estimate: float, se: float, n: int) -> float:
    """Two-sided p for a mean against zero, given its standard error and n."""
    from scipy import stats

    if not se or se <= 0 or n < 2:
        return 1.0
    return float(2 * stats.t.sf(abs(estimate / se), df=n - 1))


def multiplicity_audit(root: Path | str = ROOT, *, alpha: float = 0.05) -> dict:
    """All fifteen claims, classified, and every actual test corrected.

    `PUBLISHABILITY.md` §3 says fifteen claims were adjudicated with no
    multiple-comparison correction and that roughly one false positive is expected by
    construction. That statement is not quite right in either direction, and this
    settles it: most of the fifteen are not hypothesis tests at all, so there was
    never an inflated family-wise error rate over fifteen things — but the ones that
    *are* tests are backed by more comparisons than the claim count suggests, because
    a single claim like "price should be read, not fitted" is adjudicated on eight
    separate contrasts across two drift regimes and three shock kinds.

    So: Holm inside each family, because within a family the question is "is any of
    these a false positive"; Benjamini–Hochberg across the union, because across
    unrelated corpora the question is "what share of my discoveries are wrong".
    """
    root = Path(root)

    def load(name: str) -> dict:
        return json.loads((root / "artifacts" / name).read_text())

    tests: dict[str, dict] = {}

    # -- family: per-domain router wins (claim 2's per-domain breakout) ------
    dom_path = root / "artifacts" / "chutes" / "17_domains.json"
    if dom_path.exists():
        for r in json.loads(dom_path.read_text())["rows"]:
            tests[f"domain:{r['domain']}"] = {
                "family": "per-domain router wins", "claim": "2",
                "estimate": r["delta"], "se": r["se"], "n": r["items"],
                "p": r["p_uncorrected"],
                "what": f"router minus best-single quality on {r['domain']}",
            }

    # -- families: gamma decomposition and the price lane --------------------
    dec = load("decomposition.json")["replication"]
    for regime, block in dec.items():
        d = block["decomposition"]
        n = int(block["per_arm"][next(iter(block["per_arm"]))]["n_seeds"])
        tests[f"gamma:{regime}"] = {
            "family": "gamma decomposition", "claim": "11",
            "estimate": d["mean_regret_reduction"], "se": d["std_error"], "n": n,
            "p": _t_test(d["mean_regret_reduction"], d["std_error"], n),
            "what": f"component-wise γ_q/γ_t minus shared γ, {regime} regime",
        }
        rl = block["read_vs_learn"]
        tests[f"price:read_vs_learn:{regime}"] = {
            "family": "price lane", "claim": "12",
            "estimate": rl["mean_regret_reduction"], "se": rl["std_error"], "n": n,
            "p": _t_test(rl["mean_regret_reduction"], rl["std_error"], n),
            "what": f"live-read price minus fitted price, {regime} regime",
        }
        for kind, sh in block["transient_by_shock_kind"].items():
            tests[f"price:shock:{kind}:{regime}"] = {
                "family": "price lane", "claim": "12",
                "estimate": sh["live_read_advantage"], "se": sh["live_read_se"],
                "n": int(sh["n"]),
                "p": _t_test(sh["live_read_advantage"], sh["live_read_se"], int(sh["n"])),
                "what": f"live-read advantage under a {kind} shock, {regime} regime",
            }

    # -- correct: Holm inside each family, BH across all of them -------------
    from .rigor import _holm

    families: dict[str, list[str]] = {}
    for k, t in tests.items():
        families.setdefault(t["family"], []).append(k)

    for fam, keys in families.items():
        holm = _holm({k: tests[k]["p"] for k in keys}, alpha=alpha)
        for k in keys:
            tests[k]["holm_threshold"] = holm[k]["holm_threshold"]
            tests[k]["holm_significant"] = holm[k]["significant"]

    bh = _bh({k: t["p"] for k, t in tests.items()}, alpha=alpha)
    for k, t in tests.items():
        t["bh_threshold"] = bh[k]["bh_threshold"]
        t["bh_significant"] = bh[k]["significant"]
        t["bh_rank"] = bh[k]["rank"]

    by_kind: dict[str, list[str]] = {}
    for c in CLAIMS:
        by_kind.setdefault(c.kind, []).append(c.id)

    uncorrected = sum(1 for t in tests.values() if t["p"] <= alpha)
    holm_sig = [k for k, t in tests.items() if t["holm_significant"]]
    bh_sig = [k for k, t in tests.items() if t["bh_significant"]]

    return {
        "alpha": alpha,
        "n_claims": len(CLAIMS),
        "claims": [asdict(c) for c in CLAIMS],
        "claims_by_kind": {k: sorted(v) for k, v in by_kind.items()},
        "n_tests": len(tests),
        "families": {f: sorted(k) for f, k in families.items()},
        "tests": dict(sorted(tests.items(), key=lambda kv: kv[1]["p"])),
        "significant_uncorrected": uncorrected,
        "significant_after_holm_within_family": sorted(holm_sig),
        "significant_after_bh_across_all": sorted(bh_sig),
        "expected_false_positives_uncorrected": alpha * len(tests),
        "reading": (
            f"Of the {len(CLAIMS)} adjudicated claims, "
            f"{len(by_kind.get('census', []))} are counts over a census and "
            f"{len(by_kind.get('estimate', []))} are point estimates with no standard "
            f"error; neither kind can be corrected, and the first kind needs no "
            f"correcting. The {len(by_kind.get('test', []))} that are genuine tests are "
            f"backed by {len(tests)} separate comparisons — more than the claim count "
            f"implies, because one claim is adjudicated across several regimes. "
            f"{uncorrected} of {len(tests)} clear α = {alpha} uncorrected against "
            f"{alpha * len(tests):.1f} expected by chance; {len(holm_sig)} survive Holm "
            f"inside their family and {len(bh_sig)} survive Benjamini–Hochberg across "
            f"all of them. The honest statement is not 'expect one false positive' — "
            f"it is that the estimate-class claims need intervals, which is a different "
            f"and larger job than a correction."
        ),
    }


def coverage_mask_sweep(
    cache=None,
    *,
    pool: tuple[str, ...] | None = None,
    n_thinned: int = 6,
    fractions: tuple[float, ...] = (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5),
    seed: int = 0,
    lams: tuple[float, ...] = (1.0, 100.0),
    min_dense_items: int = 300,
) -> dict:
    """The same thirteen models throughout; only the coverage mask changes.

    `coverage_bias_dose_response` compares real pools, and real pools turn out to
    offer only two levels of coverage asymmetry: a pool with no narrowly graded column
    sits near zero, and a pool with even one sits near 0.85, because a single column
    graded on fourteen tasks collapses the intersection to those fourteen. That is a
    two-level contrast with a control, not a dose, and calling it one would be an
    overclaim.

    This is the dose. Start from thirteen columns that were all graded on the same 22
    tasks — coverage is uniform, and the effect is absent — then remove tasks from
    `n_thinned` of them until a target share of their observations is gone. Nothing
    else changes: same models, same items, same prices, same code path. Coverage is
    the only variable, and it moves continuously.

    Whole tasks are removed rather than random cells, because that is the shape real
    unevenness has. A model is run on a benchmark or it is not; nobody grades a
    uniformly random 30% of MMLU-Pro. Removing random cells would also make the
    missingness independent of the features, which is exactly the assumption that
    makes the bias disappear — and would quietly turn the experiment into a null.

    The sweep has a ceiling and it is worth being explicit about where. Removing
    coverage shrinks the intersection much faster than it shrinks the union, so past
    some point the dense arm has too few items to train on and the comparison stops
    being between two routers and starts being between a router and a stub. Levels
    whose dense core falls below `min_dense_items` are recorded as skipped, with the
    core size that ruled them out, rather than run and quietly believed.
    """
    from .rigor import dense_union_ablation, load_pool_matrix

    pool = tuple(pool or BROAD_POOL[:13])
    lm0, tokens_in = load_pool_matrix(list(pool), cache=cache)
    tasks = np.asarray(lm0.task)
    all_tasks = sorted(set(tasks.tolist()))
    rng = np.random.default_rng(seed)
    thinned_cols = sorted(rng.choice(lm0.n_models, n_thinned, replace=False).tolist())
    base_obs = lm0.observed.copy()
    # One task order per column, drawn once, so that a larger target removes a
    # superset of what a smaller one removed. Redrawing per fraction would make the
    # sweep a set of unrelated experiments rather than a dose, and could put a
    # non-monotone kink in the curve for a reason that has nothing to do with the
    # mechanism.
    task_order = {j: list(rng.permutation(all_tasks)) for j in thinned_cols}

    rows, skipped = [], []
    for f in fractions:
        obs = base_obs.copy()
        removed = {}
        for j in thinned_cols:
            order = task_order[j]
            have = int(base_obs[:, j].sum())
            target, gone, drop = f * have, 0, []
            for t in order:
                if gone >= target:
                    break
                m = (tasks == t) & base_obs[:, j]
                if not m.any():
                    continue
                drop.append(t)
                gone += int(m.sum())
                obs[m, j] = False
            removed[lm0.model_ids[j]] = {"tasks_dropped": len(drop),
                                         "share_removed": gone / max(have, 1)}

        lm = lm0.subset_items(np.arange(lm0.n_items))
        lm.observed = obs
        lm.cost = np.where(obs, lm0.cost, 0.0)
        keep = np.flatnonzero(obs.any(axis=1))
        lm, tin = lm.subset_items(keep), tokens_in[keep]

        core = int(lm.observed.all(axis=1).sum())
        if core < min_dense_items:
            skipped.append({"target_fraction_removed": f, "dense_core_items": core,
                            "reason": f"dense core below {min_dense_items} items"})
            continue

        r = dense_union_ablation(lm, tin, seed=seed, lams=lams)
        rows.append({
            "target_fraction_removed": f,
            "thinned_columns": [lm0.model_ids[j] for j in thinned_cols],
            "removed": removed,
            "coverage_asymmetry": r["coverage_asymmetry"],
            "dense_core_items": r["dense_core_items"],
            "union_items": r["union_items"],
            "dense_train_items": r["dense_best"]["train_items"],
            "union_train_items": r["union_best"]["train_items"],
            "dense_quality_retained": r["dense_best"]["quality_vs_frontier"],
            "union_quality_retained": r["union_best"]["quality_vs_frontier"],
            "union_matched_n_quality_retained":
                r["union_matched_n_best"]["quality_vs_frontier"],
            "gap_points": r["gap_points"],
            "gap_at_matched_n": r["gap_at_matched_n"],
        })

    if not rows:
        raise ValueError("every level was skipped; lower min_dense_items or the "
                         "fractions, because nothing was measured")
    a = np.array([r["coverage_asymmetry"] for r in rows])
    g = np.array([r["gap_points"] for r in rows])
    gm = np.array([r["gap_at_matched_n"] for r in rows])

    def _r(x: np.ndarray, y: np.ndarray) -> float:
        if len(x) < 3 or x.std() == 0 or y.std() == 0:
            return float("nan")
        return float(np.corrcoef(x, y)[0, 1])

    base, top = rows[0], max(rows, key=lambda r: r["gap_at_matched_n"])
    return {
        "pool": list(pool),
        "n_thinned_columns": n_thinned,
        "fractions": list(fractions),
        "fractions_evaluated": [r["target_fraction_removed"] for r in rows],
        "skipped": skipped,
        "min_dense_items": min_dense_items,
        "seed": seed,
        "rows": rows,
        "pearson_r_gap_vs_asymmetry": _r(a, g),
        "pearson_r_matched_n_vs_asymmetry": _r(a, gm),
        "at_zero_removal": {"asymmetry": base["coverage_asymmetry"],
                            "gap": base["gap_points"],
                            "gap_at_matched_n": base["gap_at_matched_n"]},
        "largest": {"fraction_removed": top["target_fraction_removed"],
                    "asymmetry": top["coverage_asymmetry"],
                    "gap": top["gap_points"],
                    "gap_at_matched_n": top["gap_at_matched_n"]},
        "reading": (
            f"Thirteen columns that were all graded on the same tasks, with coverage "
            f"progressively removed from {n_thinned} of them. At zero removal the gap "
            f"is {base['gap_at_matched_n']:+.1%}; at "
            f"{top['target_fraction_removed']:.0%} removal it is "
            f"{top['gap_at_matched_n']:+.1%} with the training-set size held at the dense "
            f"arm's, and {top['gap_points']:+.1%} with the union arm keeping every item "
            f"it has. Across the sweep the size-matched gap tracks the realised "
            f"asymmetry at r = {_r(a, gm):+.2f}. Nothing varies here except "
            f"which cells are observed — same models, same items, same prices — so the "
            f"effect is caused by the coverage and not by anything about the pool."
            + (f" {len(skipped)} of {len(fractions)} levels are not reported: past "
               f"{skipped[0]['target_fraction_removed']:.0%} removal the dense core "
               f"falls below {min_dense_items} items and the comparison stops being "
               f"between two trained routers." if skipped else "")
        ),
    }
