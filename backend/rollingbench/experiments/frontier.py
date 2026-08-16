"""The cost–quality frontier, and the per-model comparison behind it.

This is the experiment the product claims rest on. Everything else in this package
asks "does the router stay current"; this one asks the prior question — does routing
beat one good model at all, on real measured outcomes, and by how much.

λ_c is a dial, not a constant (it is the frontend's cost/quality control), so the
honest answer is a curve rather than a number. Sweeping it and reporting the whole
frontier is also the only way to state a savings figure without cherry-picking:
every point on the curve names the quality it gave up to get there.
"""

from __future__ import annotations

import numpy as np

from ..catalog import Model
from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    feasible_score_batch,
    frontier_reference_column,
    group_oracle_column,
    per_cell_utility,
    reference_column,
    score_batch,
)
from ..router import PoolState, RidgeLinUCBRouter, RouterConfig


def pool_state(pool: tuple[Model, ...]) -> PoolState:
    return PoolState(
        price_in=np.array([m.in_per_1m for m in pool]),
        price_out=np.array([m.out_per_1m for m in pool]),
    )


def model_table(lm: LabelMatrix, pool: tuple[Model, ...]) -> list[dict]:
    """Per-model summary: what each column of the label matrix actually is.

    The comparison a router is built on top of, and the first thing to check —
    a pool whose models all score the same leaves nothing to route between (§14.3).
    """
    q = lm.quality
    rows = []
    for j, mid in enumerate(lm.model_ids):
        m = next((x for x in pool if x.id == mid), None)
        obs = lm.observed[:, j]
        # Where this model is the only one in the pool to get an item right — its
        # unique contribution, and the reason it earns a slot.
        uniquely = (q[:, j] > 0.5) & ((q > 0.5).sum(axis=1) == 1)
        rows.append({
            "model_id": mid,
            "label": m.label if m else mid,
            "tier": m.tier if m else "?",
            "family": m.family if m else "?",
            "released": str(m.released) if m and m.released else "",
            "accuracy": float(q[obs, j].mean()),
            "cost_total_usd": float(lm.cost[obs, j].sum()),
            "cost_per_call_usd": float(lm.cost[obs, j].mean()),
            "price_in_per_1m": m.in_per_1m if m else float("nan"),
            "price_out_per_1m": m.out_per_1m if m else float("nan"),
            "blended_price": m.blended_price if m else float("nan"),
            "uniquely_correct": int(uniquely.sum()),
            "uniquely_correct_share": float(uniquely.mean()),
            "cells": int(obs.sum()),
        })
    return rows


def domain_table(lm: LabelMatrix) -> list[dict]:
    """Best model per domain, on quality and on quality-per-dollar.

    This is the evidence for §16.2's specialist argument: if one model won
    everywhere there would be no reason to keep a population of policies alive.
    """
    rows = []
    for d in sorted(set(lm.domain.tolist())):
        mask = lm.domain == d
        acc = lm.quality[mask].mean(axis=0)
        cost = lm.cost[mask].mean(axis=0)
        value = acc / np.maximum(cost, 1e-12)
        rows.append({
            "domain": d,
            "items": int(mask.sum()),
            "best_quality_model": lm.model_ids[int(acc.argmax())],
            "best_quality": float(acc.max()),
            "best_value_model": lm.model_ids[int(value.argmax())],
            "spread": float(acc.max() - acc.min()),
            "oracle_quality": float(lm.quality[mask].max(axis=1).mean()),
        })
    return rows


def sweep_lambda_cost(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    pool: tuple[Model, ...],
    lambdas: list[float] | None = None,
    alpha: float = 0.0,
    d: int | None = None,
) -> list[dict]:
    """Fit the router once per λ_c and report the whole frontier.

    α is 0 by default. Exploration earns its keep online, where trying an
    under-observed model buys information; in a static held-out evaluation it only
    adds variance to the measurement, so it is switched off here and studied
    separately where it matters (cold start).
    """
    if lambdas is None:
        lambdas = [0.0, 0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.4]
    d = d or X.shape[1]
    ps = pool_state(pool)
    groups = lm.task[test]

    # The savings counterfactual is fixed across the sweep — otherwise "savings"
    # would be measured against a different model at every point on the curve.
    frontier_col = frontier_reference_column(lm.quality[test])
    frontier_cost = float(lm.cost[test][:, frontier_col].sum())
    frontier_quality = float(lm.quality[test][:, frontier_col].mean())

    rows = []
    for lam_c in lambdas:
        ref_col = reference_column(lm.quality[train], lm.cost[train], lam_c)
        r = RidgeLinUCBRouter(d, lm.n_models,
                              RouterConfig(alpha=alpha, lam_cost=lam_c, ref_model=ref_col))
        r.fit(X[train], lm.quality[train], lm.observed[train], lm.tokens_out[train])
        dec = r.decide(X[test], ps)
        ch = dec.choice

        u = per_cell_utility(lm.quality[test], lm.cost[test], UtilityWeights(lam_cost=lam_c),
                             ref_col=ref_col)
        base_col = best_single_column(u)
        spec = score_batch(u, ch, base_col=base_col)
        feas = feasible_score_batch(u, ch, groups, base_col=base_col)

        routed_cost = float(lm.cost[test][np.arange(len(test)), ch].sum())
        routed_quality = float(lm.quality[test][np.arange(len(test)), ch].mean())
        rows.append({
            "lam_cost": lam_c,
            "quality": routed_quality,
            "cost_usd": routed_cost,
            "savings_vs_frontier": 1.0 - routed_cost / frontier_cost,
            "quality_vs_frontier": routed_quality / frontier_quality,
            "quality_delta": routed_quality - frontier_quality,
            "regret_spec": spec.regret,
            "score_spec": spec.score,
            "score_feasible": feas.score,
            "best_single_model": lm.model_ids[base_col],
            "ref_model": lm.model_ids[ref_col],
            "models_used": int(len(set(ch.tolist()))),
            "frontier_share": float((ch == frontier_col).mean()),
            "artifact_kb": r.artifact_bytes() / 1024,
        })
    return rows


def policy_comparison(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    pool: tuple[Model, ...],
    lam_cost: float = 0.02,
    seed: int = 0,
) -> list[dict]:
    """Every policy on one batch, scored identically.

    Includes the controls that make the router's number legible: random (how much of
    the gap is just "not always picking the dearest"), each single model on its own,
    the per-task oracle (the attainable ceiling), and the per-item oracle (the lucky
    one).
    """
    ps = pool_state(pool)
    n = len(test)
    ref_col = reference_column(lm.quality[train], lm.cost[train], lam_cost)
    u = per_cell_utility(lm.quality[test], lm.cost[test], UtilityWeights(lam_cost=lam_cost),
                         ref_col=ref_col)
    base_col = best_single_column(u)
    groups = lm.task[test]
    frontier_col = frontier_reference_column(lm.quality[test])
    frontier_cost = float(lm.cost[test][:, frontier_col].sum())

    router = RidgeLinUCBRouter(X.shape[1], lm.n_models,
                               RouterConfig(alpha=0.0, lam_cost=lam_cost, ref_model=ref_col))
    router.fit(X[train], lm.quality[train], lm.observed[train], lm.tokens_out[train])

    # A quality-only router: no cost term at all. Isolates how much of the saving
    # comes from picking well versus from the cost penalty steering cheap.
    quality_only = RidgeLinUCBRouter(X.shape[1], lm.n_models,
                                     RouterConfig(alpha=0.0, lam_cost=0.0, ref_model=ref_col))
    quality_only.fit(X[train], lm.quality[train], lm.observed[train], lm.tokens_out[train])

    # Per-task assignment learned on train only — a strong, cheap, non-ML baseline
    # that a router has to beat to justify itself.
    task_best = {}
    u_tr = per_cell_utility(lm.quality[train], lm.cost[train], UtilityWeights(lam_cost=lam_cost),
                            ref_col=ref_col)
    for t in set(lm.task[train].tolist()):
        m = lm.task[train] == t
        task_best[t] = int(u_tr[m].mean(axis=0).argmax())
    task_choices = np.array([task_best.get(t, base_col) for t in lm.task[test]])

    rng = np.random.default_rng(seed)
    policies: list[tuple[str, str, np.ndarray]] = [
        ("random", "control", rng.integers(0, lm.n_models, size=n)),
        ("best single (utility)", "baseline", np.full(n, base_col)),
        ("frontier only", "baseline", np.full(n, frontier_col)),
        ("per-task table (train)", "baseline", task_choices),
        ("router: quality only", "router", quality_only.decide(X[test], ps).choice),
        ("router: §8 ridge+LinUCB", "router", router.decide(X[test], ps).choice),
        ("oracle: per-task (feasible)", "ceiling", group_oracle_column(u, groups)),
        ("oracle: per-item (§8.8)", "ceiling", u.argmax(axis=1)),
    ]

    rows = []
    for name, kind, ch in policies:
        spec = score_batch(u, ch, base_col=base_col, clip=False)
        feas = feasible_score_batch(u, ch, groups, base_col=base_col)
        cost = float(lm.cost[test][np.arange(n), ch].sum())
        rows.append({
            "policy": name,
            "kind": kind,
            "quality": float(lm.quality[test][np.arange(n), ch].mean()),
            "cost_usd": cost,
            "savings_vs_frontier": 1.0 - cost / frontier_cost,
            "utility": spec.u_policy,
            "regret_spec": spec.regret,
            "score_spec": float(np.clip(spec.score, 0, 1)),
            "score_feasible": feas.score,
            "models_used": int(len(set(ch.tolist()))),
        })
    return rows
