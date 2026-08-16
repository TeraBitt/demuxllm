"""Shared versus per-model Gram matrix — the §8.3 shortcut, measured.

Not one of the proposal's numbered contributions. It came out of trying to make the
staleness study's rolling arm work: with one shared A the arm could not exploit GPT-4
after it arrived, and the reason turned out to be structural rather than a bug.

§8.3 keeps a single Gram matrix for the whole pool on the grounds that "A depends only
on the queries, not on which model answered them", which makes the pool hot-swappable
— a thirteenth model is one more column of B. That is exact when every model has been
run on the same items. It is not exact when coverage is uneven, and the two cases the
system cares about most are both uneven: a model that arrived yesterday with 250 probe
cells, and the §18.2 sampling plan that deliberately runs reasoning models on a 25%
subset. In both, the shared A carries every item while the new column's b carries a
fraction, so w = A⁻¹b is shrunk toward zero and the under-observed model is
under-predicted rather than uncertain.

This module measures the size of that effect at a range of coverage ratios, which is
what turns "the shortcut is wrong" into "the shortcut costs this much, here".
"""

from __future__ import annotations

import numpy as np

from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    feasible_score_batch,
    per_cell_utility,
    reference_column,
)
from ..router import RidgeLinUCBRouter, RouterConfig


def run(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    pool,
    coverages: tuple[float, ...] = (1.0, 0.5, 0.25, 0.1, 0.05, 0.02, 0.01),
    lam_cost: float = 0.05,
    seed: int = 0,
) -> dict:
    """Thin one model's coverage and watch both estimators.

    The thinned model is the strongest one, because that is the case with something to
    lose: under-predicting a weak model costs nothing, since it would not have been
    selected anyway.
    """
    rng = np.random.default_rng(seed)
    d = X.shape[1]
    ref_col = reference_column(lm.quality[train])
    thin = int(np.argmax(lm.quality.mean(axis=0)))

    from .frontier import pool_state
    ps = pool_state(pool)

    u_test = per_cell_utility(lm.quality[test], lm.cost[test],
                              UtilityWeights(lam_cost=lam_cost), ref_col=ref_col)
    base_col = best_single_column(u_test)
    groups = lm.task[test]

    rows = []
    for cov in coverages:
        observed = lm.observed[train].copy()
        if cov < 1.0:
            keep = rng.random(len(train)) < cov
            observed[~keep, thin] = False

        for shared in (True, False):
            r = RidgeLinUCBRouter(
                d, lm.n_models,
                RouterConfig(alpha=0.0, lam_cost=lam_cost, ref_model=ref_col,
                             shared_gram=shared),
            )
            r.fit(X[train], lm.quality[train], observed, lm.tokens_out[train])
            ch = r.decide(X[test], ps).choice
            q_hat = r.quality.predict(X[test])

            feas = feasible_score_batch(u_test, ch, groups, base_col=base_col)
            rows.append({
                "coverage": cov,
                "gram": "shared (§8.3)" if shared else "per-model (§8.5)",
                "thinned_model": lm.model_ids[thin],
                "cells_for_thinned": int(observed[:, thin].sum()),
                # The diagnostic: what the router believes the thinned model can do,
                # against what it actually does. Shrinkage shows up here directly.
                "q_hat_thinned": float(q_hat[:, thin].mean()),
                "q_true_thinned": float(lm.quality[test][:, thin].mean()),
                "q_hat_others": float(np.delete(q_hat, thin, axis=1).mean()),
                "share_thinned": float((ch == thin).mean()),
                "utility": float(u_test[np.arange(len(test)), ch].mean()),
                "score_feasible": feas.score,
                "quality": float(lm.quality[test][np.arange(len(test)), ch].mean()),
                "cost_usd": float(lm.cost[test][np.arange(len(test)), ch].sum()),
                "artifact_kb": r.artifact_bytes() / 1024,
            })

    return {"rows": rows, "thinned_model": lm.model_ids[thin],
            "config": {"lam_cost": lam_cost, "seed": seed,
                       "coverages": list(coverages)},
            "summary": _summarise(rows)}


def _summarise(rows: list[dict]) -> dict:
    """Where the shortcut starts to cost something."""
    by = {}
    for r in rows:
        by.setdefault(r["coverage"], {})[r["gram"]] = r
    shared_k, per_k = "shared (§8.3)", "per-model (§8.5)"

    deltas = []
    for cov in sorted(by, reverse=True):
        if shared_k not in by[cov] or per_k not in by[cov]:
            continue
        s, p = by[cov][shared_k], by[cov][per_k]
        deltas.append({
            "coverage": cov,
            "utility_gap": p["utility"] - s["utility"],
            "share_gap": p["share_thinned"] - s["share_thinned"],
            # Under-prediction as a fraction of truth: 1.0 means the estimate has
            # collapsed to zero, 0.0 means it is unbiased.
            "shared_underprediction": 1.0 - s["q_hat_thinned"] / max(s["q_true_thinned"], 1e-9),
            "per_model_underprediction": 1.0 - p["q_hat_thinned"] / max(p["q_true_thinned"], 1e-9),
        })

    material = [d for d in deltas if d["utility_gap"] > 0.005]
    return {
        "by_coverage": deltas,
        "worst_utility_gap": max((d["utility_gap"] for d in deltas), default=0.0),
        "coverage_where_shortcut_costs": (
            max(d["coverage"] for d in material) if material else None
        ),
        "reading": (
            "at full coverage the two are equivalent, which is why §8.3's argument "
            "reads correctly; the gap opens as coverage thins, and the thinned regime "
            "is exactly cold start and the §18.2 sampling plan"
        ),
    }
