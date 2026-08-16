"""7.4 then 7.2 — the bridge check, then cold-start sample complexity.

Order matters and the proposal is explicit about it: 7.4 is a precondition. If the
low-rank item-space prediction does not transfer into a feature-space prior, then
Contribution 2 has no bridge and the sample-complexity claim rests on nothing. It
takes an afternoon, so it runs first and its result is reported either way.

7.2 is leave-one-model-out. For each of the eleven models in turn: hide it, fit
everything on the other ten, then onboard it with n probe items and measure how well
the router routes. Three priors compete — none, RollingBench's informal blend (§8.6),
and the derived conjugate prior (§5.2) — and the question is how many probe items
each needs to reach a fixed quality of routing.

The claim being tested is sharper than "the prior helps". §5.3 predicts the probe
count should depend on how well the new model loads onto the pool's existing latent
factors, rather than being the flat ~250 the source document asserts. So the loading
is measured per model and correlated against the probe count each model actually
needed. A flat constant cannot track that variation; a derived prior should.
"""

from __future__ import annotations

import numpy as np

from ..catalog import Model
from ..coldstart import (
    Bridge,
    blended_prior,
    derived_prior,
    fit_ability,
    fit_bridge,
    fit_irt,
    fit_lowrank,
    fit_new_column,
    select_probe_items,
)
from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    feasible_score_batch,
    per_cell_utility,
    reference_column,
)
from ..router import PoolState, RidgeLinUCBRouter, RouterConfig

PROBE_GRID = (0, 10, 25, 50, 100, 250, 500, 1000)


def _pool_state(pool: tuple[Model, ...], ids: list[str]) -> PoolState:
    lookup = {m.id: m for m in pool}
    return PoolState(
        price_in=np.array([lookup[i].in_per_1m for i in ids]),
        price_out=np.array([lookup[i].out_per_1m for i in ids]),
    )


def bridge_check(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    rank: int = 8,
    n_lowrank_items: int = 4000,
    seed: int = 0,
) -> dict:
    """7.4 — fit Φ once and report its residual.

    The low-rank fit is on a subsample: ALS over 36k × 11 converges to the same
    factors as over 4k × 11 and takes a fraction of the time, and the quantity being
    measured is how well the two spaces align, not the factors themselves.
    """
    rng = np.random.default_rng(seed)
    sub = rng.choice(train, size=min(n_lowrank_items, len(train)), replace=False)

    lr = fit_lowrank(lm.quality[sub], lm.observed[sub], rank=rank, n_iter=25)
    router = RidgeLinUCBRouter(X.shape[1], lm.n_models, RouterConfig(alpha=0.0))
    router.fit(X[sub], lm.quality[sub], lm.observed[sub], lm.tokens_out[sub])

    bridge = fit_bridge(X[sub], lr, router.quality.W)

    # How well each model's true column is explained by the *other* models' latent
    # factors — the "loading" §5.3 says probe count should depend on. Measured by
    # holding a model out of the factorisation and predicting its column from the
    # factors the rest produced.
    loadings = {}
    for j, mid in enumerate(lm.model_ids):
        others = [k for k in range(lm.n_models) if k != j]
        lr_wo = fit_lowrank(lm.quality[sub][:, others], lm.observed[sub][:, others],
                            rank=rank, n_iter=15)
        v = fit_new_column(lr_wo, np.arange(len(sub)), lm.quality[sub][:, j])
        pred = lr_wo.predict_column(v)
        truth = lm.quality[sub][:, j]
        ss_res = float(((truth - pred) ** 2).sum())
        ss_tot = float(((truth - truth.mean()) ** 2).sum())
        loadings[mid] = {
            "r2": 1.0 - ss_res / max(ss_tot, 1e-12),
            "residual_var": float((truth - pred).var()),
        }

    return {
        "rank": rank,
        "n_items_fitted": int(len(sub)),
        "bridge_r2": bridge.r2,
        "bridge_residual_ratio": bridge.residual_ratio,
        "tau2": bridge.tau2,
        "holds": bridge.holds,
        "per_model_loading": loadings,
        "verdict": (
            "bridge usable — Contribution 2 can proceed" if bridge.holds
            else "bridge does NOT hold; §5.1's linking assumption needs revision or "
                 "Contribution 2 must be dropped (the proposal's own gate)"
        ),
    }


def leave_one_model_out(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    pool: tuple[Model, ...],
    probe_grid: tuple[int, ...] = PROBE_GRID,
    lam_cost: float = 0.05,
    rank: int = 8,
    n_lowrank_items: int = 4000,
    seed: int = 0,
    confidence: float = 0.5,
) -> dict:
    """7.2 — onboard each model from scratch under three priors.

    The router is fitted on the other ten models over the training split, then the
    held-out model is introduced with `n` probe items. Routing is scored on the test
    split over the *full* pool, so the held-out model is available to the oracle
    whether or not the router has learned to use it — which is the whole point: a
    prior earns its keep by making the new column selectable sooner.
    """
    rng = np.random.default_rng(seed)
    sub = rng.choice(train, size=min(n_lowrank_items, len(train)), replace=False)
    d = X.shape[1]
    ref_col = reference_column(lm.quality[train])
    ps_full = _pool_state(pool, lm.model_ids)

    u_test = per_cell_utility(lm.quality[test], lm.cost[test],
                              UtilityWeights(lam_cost=lam_cost), ref_col=ref_col)
    base_col = best_single_column(u_test)
    groups = lm.task[test]

    # The target to catch up to: a router that had the new model all along. Measuring
    # the deficit against this rather than against an absolute score is what makes the
    # answer a sample complexity — "how many probe items until onboarding has paid for
    # itself" — instead of a statement about how much that particular model was worth.
    full_router = RidgeLinUCBRouter(d, lm.n_models,
                                    RouterConfig(alpha=0.0, lam_cost=lam_cost,
                                                 ref_model=ref_col))
    full_router.fit(X[train], lm.quality[train], lm.observed[train], lm.tokens_out[train])
    u_full_router = float(u_test[np.arange(len(test)),
                                 full_router.decide(X[test], ps_full).choice].mean())

    rows: list[dict] = []
    for j, held in enumerate(lm.model_ids):
        others = [k for k in range(lm.n_models) if k != j]

        # Everything the pool knew before the new model arrived.
        # α = 0 throughout this experiment. On a frozen evaluation batch the
        # exploration bonus cannot pay for itself — there is no later request to spend
        # the information on — and an unobserved column has σ = ‖x‖/√λ, which is large
        # enough to capture all the traffic and drown out the thing being measured.
        # Exploration is studied where it belongs, in the rolling replay.
        base_router = RidgeLinUCBRouter(d, lm.n_models,
                                        RouterConfig(alpha=0.0, lam_cost=lam_cost,
                                                     ref_model=ref_col))
        base_router.fit(X[train], lm.quality[train][:, others], lm.observed[train][:, others],
                        lm.tokens_out[train][:, others], models=others)

        lr = fit_lowrank(lm.quality[sub][:, others], lm.observed[sub][:, others],
                         rank=rank, n_iter=20)
        irt = fit_irt(lm.quality[sub][:, others], lm.observed[sub][:, others], n_iter=12)
        bridge = fit_bridge(X[sub], lr, base_router.quality.W[:, others])

        for n_probe in probe_grid:
            r = _clone_with_probe(
                base_router, d, lm, X, sub, others, j, n_probe, irt, lr, bridge,
                prior="none", rng=rng, lam_cost=lam_cost, ref_col=ref_col,
                confidence=confidence,
            )
            variants = {"no prior": r}
            variants["blend (§8.6)"] = _clone_with_probe(
                base_router, d, lm, X, sub, others, j, n_probe, irt, lr, bridge,
                prior="blend", rng=rng, lam_cost=lam_cost, ref_col=ref_col,
                confidence=confidence)
            variants["derived (§5.2)"] = _clone_with_probe(
                base_router, d, lm, X, sub, others, j, n_probe, irt, lr, bridge,
                prior="derived", rng=rng, lam_cost=lam_cost, ref_col=ref_col,
                confidence=confidence)

            for prior_name, router in variants.items():
                ch = router.decide(X[test], ps_full).choice
                feas = feasible_score_batch(u_test, ch, groups, base_col=base_col)
                rows.append({
                    "held_out": held,
                    "prior": prior_name,
                    "n_probe": n_probe,
                    "utility": float(u_test[np.arange(len(test)), ch].mean()),
                    "utility_full_router": u_full_router,
                    "score_feasible": feas.score,
                    "quality": float(lm.quality[test][np.arange(len(test)), ch].mean()),
                    "cost_usd": float(lm.cost[test][np.arange(len(test)), ch].sum()),
                    "share_new_model": float((ch == j).mean()),
                    "tau2": bridge.tau2,
                    "bridge_r2": bridge.r2,
                })

    return {
        "rows": rows,
        "probe_grid": list(probe_grid),
        "config": {"rank": rank, "lam_cost": lam_cost, "confidence": confidence,
                   "n_lowrank_items": int(len(sub)), "seed": seed},
        "summary": _summarise_lomo(rows, probe_grid),
    }


def _clone_with_probe(
    base: RidgeLinUCBRouter,
    d: int,
    lm: LabelMatrix,
    X: np.ndarray,
    sub: np.ndarray,
    others: list[int],
    j_new: int,
    n_probe: int,
    irt,
    lr,
    bridge: Bridge,
    prior: str,
    rng: np.random.Generator,
    lam_cost: float,
    ref_col: int,
    confidence: float,
) -> RidgeLinUCBRouter:
    """A copy of the pool's router with one model onboarded.

    Copying rather than refitting keeps the ten known columns byte-identical across
    the three prior variants, so any difference in routing is attributable to the
    prior on the eleventh and to nothing else.
    """
    r = RidgeLinUCBRouter(d, lm.n_models,
                          RouterConfig(alpha=0.0, lam_cost=lam_cost, ref_model=ref_col))
    r.quality.A = base.quality.A.copy()
    r.quality.A_m = base.quality.A_m.copy()
    r.quality.B = base.quality.B.copy()
    r.tokens.A = base.tokens.A.copy()
    r.tokens.A_m = base.tokens.A_m.copy()
    r.tokens.B = base.tokens.B.copy()
    r.counts = base.counts.copy()

    # Adaptive probe (§8.6): pick items whose difficulty sits near the running ability
    # estimate, because those carry the most information per item.
    if n_probe > 0:
        probe_local = select_probe_items(irt, np.arange(len(sub)), 0.0, n_probe, rng)
        probe_items = sub[probe_local]
        outcomes = lm.quality[probe_items][:, j_new]
    else:
        probe_local = np.array([], dtype=int)
        probe_items = np.array([], dtype=int)
        outcomes = np.array([])

    if prior != "none" and n_probe > 0:
        v_k = fit_new_column(lr, probe_local, outcomes)
        if prior == "derived":
            p = derived_prior(bridge, lr, v_k, base.quality.A_m[others[0]], strength=1.0)
        else:
            ability = fit_ability(irt, probe_local, outcomes)
            p = blended_prior(irt, lr, X[sub], v_k, ability,
                              base.quality.A_m[others[0]], confidence=confidence)
        r.quality.seed_prior(j_new, p.A_prior, p.b_prior)

    if n_probe > 0:
        r.absorb(X[probe_items], lm.quality[probe_items][:, [j_new]],
                 np.ones((len(probe_items), 1), dtype=bool),
                 lm.tokens_out[probe_items][:, [j_new]], models=[j_new])
    return r


def _summarise_lomo(rows: list[dict], probe_grid: tuple[int, ...]) -> dict:
    """Probe items needed to close the onboarding gap, per model and per prior.

    The gap is measured against a router that always had the model (`utility_full_
    router`), and the target is closing 90% of the gap that existed at zero probe
    items. Anchoring it this way makes the answer a sample complexity rather than a
    statement about how valuable that particular model happened to be: a model worth
    little to the pool has a small gap and closes it immediately, which is the correct
    reading rather than a flattering one.
    """
    priors = sorted({r["prior"] for r in rows})
    models = sorted({r["held_out"] for r in rows})
    needed: dict[str, dict[str, float]] = {p: {} for p in priors}
    gap0: dict[str, float] = {}

    for mid in models:
        target_u = next(r["utility_full_router"] for r in rows if r["held_out"] == mid)
        at_zero = np.mean([r["utility"] for r in rows
                           if r["held_out"] == mid and r["n_probe"] == 0])
        gap0[mid] = float(target_u - at_zero)
        # A model the pool did not need: no gap to close, so onboarding is free.
        threshold = target_u - 0.1 * max(gap0[mid], 0.0)
        for p in priors:
            series = sorted(
                [r for r in rows if r["held_out"] == mid and r["prior"] == p],
                key=lambda r: r["n_probe"],
            )
            hit = next((r["n_probe"] for r in series if r["utility"] >= threshold), None)
            needed[p][mid] = float(hit) if hit is not None else float("inf")

    finite = lambda p: [v for v in needed[p].values() if np.isfinite(v)]
    # Most held-out models turn out to add nothing to the pool, so their gap is ~0 and
    # they are "onboarded" at zero probe items by definition. Averaging those in would
    # report a probe count of zero and say nothing. The figure that matters is over the
    # models whose arrival actually changed what the pool could do.
    material = [m for m in models if gap0[m] > 0.005]
    mat_finite = lambda p: [needed[p][m] for m in material if np.isfinite(needed[p][m])]
    out = {
        "probe_items_needed": needed,
        "onboarding_gap_at_zero_probe": gap0,
        "material_models": material,
        "median_probe_items": {p: float(np.median(finite(p))) if finite(p) else float("inf")
                               for p in priors},
        "median_probe_items_material": {
            p: float(np.median(mat_finite(p))) if mat_finite(p) else float("inf")
            for p in priors
        },
        "mean_utility_by_prior_and_probe": {
            p: {
                str(n): float(np.mean([r["utility"] for r in rows
                                       if r["prior"] == p and r["n_probe"] == n]))
                for n in probe_grid
            }
            for p in priors
        },
        "mean_score_by_prior_and_probe": {
            p: {
                str(n): float(np.mean([r["score_feasible"] for r in rows
                                       if r["prior"] == p and r["n_probe"] == n]))
                for n in probe_grid
            }
            for p in priors
        },
    }

    # §5.3's actual prediction: probe count should track τ² — how poorly the new model
    # is explained by the pool's latent structure — rather than being a constant.
    tau2_by_model = {mid: next(r["tau2"] for r in rows if r["held_out"] == mid)
                     for mid in models}
    for p in priors:
        xs = [tau2_by_model[m] for m in models if np.isfinite(needed[p][m])]
        ys = [needed[p][m] for m in models if np.isfinite(needed[p][m])]
        out.setdefault("tau2_vs_probe_correlation", {})[p] = (
            float(np.corrcoef(xs, ys)[0, 1]) if len(xs) > 2 and np.std(xs) > 0 else float("nan")
        )
    out["tau2_by_model"] = tau2_by_model
    return out
