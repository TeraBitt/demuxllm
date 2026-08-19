"""Train and analyse the router over the pool the product actually serves.

Every other experiment in this package runs on RouterBench's eleven 2023 models,
because that corpus carries release dates and the staleness study needs them. That
is the right pool for the research questions and the wrong pool for the product:
a customer's request is routed to one of the thirteen Chutes models, and none of
them are in RouterBench.

This module closes that gap. It builds a thirteen-column label matrix whose
behaviour comes from `catalog.CHUTES_PROXY` — real graded outcomes for a measured
stand-in per slot — and whose prices come from the Chutes list, then fits the same
§8 estimator over it and reports what the dashboard claims.

The split between the two halves is the load-bearing part:

    quality, tokens_out   MEASURED, per item, by LLMRouterBench's own graders
    price                 REAL, the published Chutes rate
    cost per cell         measured tokens x published price  (never the proxy's bill)
    the binding itself    AN ASSUMPTION — see catalog.CHUTES_PROXY

So `savings_pct` here is "what this traffic costs at Chutes prices if each Chutes
model behaves like its stand-in", which is a weaker claim than the RouterBench
numbers and is labelled as such in every artifact this module writes.

Training uses every item a model was graded on — 25,034 of them, unevenly covered,
because the small open models and the large ones were run on overlapping but
different task sets. Evaluation uses only the 3,932 items every one of the thirteen
answered. That asymmetry is deliberate: a Gram matrix should see all the evidence
there is, but a cost/quality frontier is only interpretable when every policy had
the same menu on every item.
"""

from __future__ import annotations

import numpy as np

from ..catalog import (
    CHUTES_CATALOG,
    CHUTES_PROXY,
    CLOSED_WEIGHT_PROXIES,
    OPEN_WEIGHT_PROXIES,
    Model,
    ProxyBinding,
    by_id,
    check_proxy_table,
    proxy_for,
    proxy_ids,
)
from ..data import llmrouterbench
from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    frontier_reference_column,
    per_cell_utility,
    savings_report,
)
from ..router import PoolState, RidgeLinUCBRouter, RouterConfig

TIER_ORDER = ("open", "mid", "frontier")


# ------------------------------------------------------------------- the pool --
def build_pool(cache=None, bindings=None) -> tuple[LabelMatrix, np.ndarray]:
    """The thirteen-column matrix, priced at Chutes rates.

    Returns the matrix (columns renamed to Chutes ids, in catalogue order) and the
    per-cell measured input-token counts, which pricing needs and `LabelMatrix` has
    no field for.

    `bindings` overrides `CHUTES_PROXY` — used by `open_weights_only` to rebuild the
    same pool from a different set of stand-ins and measure what changes.
    """
    bindings = bindings or CHUTES_PROXY
    if bindings is CHUTES_PROXY:
        check_proxy_table()
    ids = [b.proxy_id for b in bindings]
    kwargs = {"cache": cache} if cache is not None else {}
    lm = llmrouterbench.load(models=ids, **kwargs)
    tokens_in = llmrouterbench.tokens_in_for(models=ids,
                                             **({"cache": cache} if cache else {}))

    # Drop items no model in this pool answered; they carry no signal and would
    # distort every density figure.
    keep = np.flatnonzero(lm.observed.any(axis=1))
    lm = lm.subset_items(keep)
    tokens_in = tokens_in[keep]

    # A cell with no input tokens, no output tokens and a score of exactly zero is a
    # call that never completed — 470 of them, and their scores are 0.0 to the last
    # decimal while every other cell averages 0.60. Left in, they are poison twice
    # over: the quality lane learns a reliability failure as if it were an inability
    # to answer, and the cost lane learns that the model was free. The second is the
    # worse of the two, because c_ref appears in a denominator: on the two items
    # where the *reference* model failed, the cost ratio for every other model goes
    # to 1e9 and the mean utility with it.
    #
    # They are marked unobserved rather than deleted, which is the distinction the
    # mask exists for: "not run" and "run and scored badly" are different facts.
    # Cells that were billed for input and returned nothing (31 of them) are real
    # measurements of a real failure mode and stay.
    failed = lm.observed & (tokens_in <= 0) & (lm.tokens_out <= 0)
    lm.observed = lm.observed & ~failed

    # Re-price. The proxy's own bill is discarded: it was paid at a different
    # provider's rates for a different checkpoint, and the number the product needs
    # is what Chutes would charge for the same token counts.
    price_in = np.array([m.in_per_1m for m in CHUTES_CATALOG])
    price_out = np.array([m.out_per_1m for m in CHUTES_CATALOG])
    cost = (tokens_in / 1e6) * price_in[None, :] + (lm.tokens_out / 1e6) * price_out[None, :]
    lm.cost = np.where(lm.observed, cost, 0.0)

    lm.model_ids = [m.id for m in CHUTES_CATALOG]
    lm.source = "LLMRouterBench via CHUTES_PROXY (proxy-backed; see catalog.CHUTES_PROXY)"
    lm.notes = list(lm.notes) + [
        "PROXY-BACKED: quality and tokens are measured on a stand-in model per slot, "
        "not on the Chutes endpoint. See catalog.CHUTES_PROXY for each binding.",
        "cost = measured tokens x published Chutes price (the proxy's own bill is discarded)",
        f"{int(failed.sum())} zero-token, zero-score cells marked unobserved as failed calls",
    ]
    return lm, tokens_in


def split(lm: LabelMatrix, seed: int = 0, test_frac: float = 0.35,
          train_on: str = "dense") -> tuple[np.ndarray, np.ndarray]:
    """Split by item. Both halves come from the fully-observed core.

    `train_on="union"` instead trains on every graded item in the corpus — ten times
    the data — and is kept only because it is the ablation that justifies the
    default. It loses eleven points of quality retention. `coverage_ablation` runs
    both and explains why: the columns are graded on different task mixes, so their
    weights are fitted over different regions of feature space and are no longer
    comparable at the argmax. Model coverage has to be shared across columns, or
    more data makes the router worse.

    Held out by item, never by cell: the same prompt answered by thirteen models is
    one item, and letting it straddle the split leaks the answer.
    """
    dense_idx = np.flatnonzero(lm.observed.all(axis=1))
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(dense_idx)
    n_test = int(round(test_frac * len(shuffled)))
    test = np.sort(shuffled[:n_test])
    if train_on == "union":
        train = np.sort(np.setdiff1d(np.arange(lm.n_items), test))
    elif train_on == "dense":
        train = np.sort(shuffled[n_test:])
    else:
        raise ValueError(f"train_on must be 'dense' or 'union', got {train_on!r}")
    return train, test


def coverage_ablation(lm: LabelMatrix, X: np.ndarray, tokens_in: np.ndarray,
                      seed: int = 0, lams: tuple[float, ...] = (1.0, 10.0, 100.0)) -> dict:
    """Does training on ten times the data help? Measured, because it does not.

    Same held-out items in every arm; only the training set differs.

    Three arms, not two. `dense` and `union` differ in *both* their coverage and their
    size, so a gap between them is equally consistent with "uneven coverage hurts" and
    with "more data hurts" — and those have opposite implications for what to do about
    it. `union_matched_n` trains on a random subset of the union items of exactly the
    dense arm's size, so the quantity is held fixed and only the coverage varies. It is
    the arm that says which of the two explanations is right, and on both pools where
    this has been run the answer is coverage: the gap is *larger* at equal n, because
    the union arm's extra volume was partly compensating for the damage. See
    `publish.coverage_bias_dose_response` for the full argument.
    """
    _, test = split(lm, seed=seed)
    ps = pool_state()
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    q = lm.quality[test]
    rows = np.arange(len(test))
    frontier_col = frontier_reference_column(lm.quality[_dense(lm, np.arange(lm.n_items))])
    base = float(q[:, frontier_col].mean())

    tr_dense, _ = split(lm, seed=seed, train_on="dense")
    tr_union, _ = split(lm, seed=seed, train_on="union")
    rng_sub = np.random.default_rng(seed + 977)
    tr_matched = (np.sort(rng_sub.choice(tr_union, size=len(tr_dense), replace=False))
                  if len(tr_union) > len(tr_dense) else tr_union)
    train_sets = {"dense": tr_dense, "union": tr_union, "union_matched_n": tr_matched}

    arms = []
    for mode, train in train_sets.items():
        for lam in lams:
            r, _ = train_router(lm, X, train, lam_cost=0.0, lam=lam)
            pred = r.quality.predict(X[test])
            choice = r.decide(X[test], ps, tokens_in=tin).choice
            arms.append({
                "train_on": mode,
                "ridge_lam": lam,
                "train_items": int(len(train)),
                "train_cells": int(lm.observed[train].sum()),
                "dense_share_of_train": float(lm.observed[train].all(axis=1).mean()),
                "val_brier": float(((pred - q) ** 2).mean()),
                "quality_at_lam_cost_0": float(q[rows, choice].mean()),
                "quality_vs_frontier": float(q[rows, choice].mean() / max(base, 1e-12)),
            })
    best = {m: max((a for a in arms if a["train_on"] == m),
                   key=lambda a: a["quality_vs_frontier"]) for m in train_sets}
    gap = (best["dense"]["quality_vs_frontier"]
           - best["union"]["quality_vs_frontier"])
    gap_n = (best["dense"]["quality_vs_frontier"]
             - best["union_matched_n"]["quality_vs_frontier"])
    return {
        "arms": arms,
        "frontier_model": lm.model_ids[frontier_col],
        "gap_points": gap,
        "gap_at_matched_n": gap_n,
        "cause": "coverage" if gap_n >= gap else "data volume",
        "reading": (
            f"dense-core training retains {best['dense']['quality_vs_frontier']:.1%} of "
            f"frontier quality on {best['dense']['train_items']:,} items; the union arm "
            f"has {best['union']['train_items'] / max(best['dense']['train_items'], 1):.0f}x "
            f"the items and retains {best['union']['quality_vs_frontier']:.1%}, a gap of "
            f"{gap:+.1%}. Held at the dense arm's own size, so that only the coverage "
            f"differs, it retains {best['union_matched_n']['quality_vs_frontier']:.1%} and "
            f"the gap is {gap_n:+.1%} — "
            + ("larger, so the extra data was partly compensating and the cause is the "
               "uneven coverage, not the volume."
               if gap_n >= gap else
               "smaller, so part of the effect really is about training on more items.")
        ),
    }


def _dense(lm: LabelMatrix, idx: np.ndarray) -> np.ndarray:
    """The rows of `idx` where every model in the pool was graded.

    Any statistic that compares one column against another has to be computed here
    and nowhere else. Coverage is uneven by construction — the small open models
    were run on 22 tasks and the large ones on 14 — so a column mean taken over the
    sparse matrix scores a model partly on how often it was *asked*, and picking the
    reference model that way hands the slot to whoever happened to be run most.
    """
    d = idx[lm.observed[idx].all(axis=1)]
    if len(d) == 0:
        raise ValueError("no fully-observed items in this split")
    return d


def pool_state(slots: list[str] | None = None) -> PoolState:
    """Live-lane prices for the pool being routed over.

    `slots` names a sub-pool in column order, for the case where only part of the
    catalogue is being evaluated — a graded run that could only reach four of the
    thirteen endpoints, say. Defaulting to the full catalogue keeps every existing
    caller unchanged; passing the wrong length here is a silent mis-pricing, so the
    ids are resolved through `by_id` rather than positionally.
    """
    pool = CHUTES_CATALOG if slots is None else tuple(by_id(CHUTES_CATALOG, s) for s in slots)
    return PoolState(
        price_in=np.array([m.in_per_1m for m in pool]),
        price_out=np.array([m.out_per_1m for m in pool]),
    )


# ---------------------------------------------------------------------- train --
def train_router(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    *,
    lam_cost: float = 0.05,
    alpha: float = 0.0,
    lam: float = 1.0,
) -> tuple[RidgeLinUCBRouter, dict]:
    """Fit the §8 estimator on the training items, and report what it learned."""
    ref = frontier_reference_column(lm.quality[_dense(lm, train)])
    cfg = RouterConfig(lam=lam, alpha=alpha, lam_cost=lam_cost, ref_model=int(ref))
    r = RidgeLinUCBRouter(X.shape[1], lm.n_models, cfg)
    r.fit(X[train], lm.quality[train], lm.observed[train], lm.tokens_out[train])

    q_pred = r.quality.predict(X[train])
    obs = lm.observed[train]
    resid = np.where(obs, q_pred - lm.quality[train], 0.0)
    brier = float((resid[obs] ** 2).mean())

    diagnostics = {
        "d": int(X.shape[1]),
        "n_train_items": int(len(train)),
        "n_train_cells": int(obs.sum()),
        "lam": lam,
        "lam_cost": lam_cost,
        "alpha": alpha,
        "ref_model": lm.model_ids[int(ref)],
        "artifact_bytes": int(r.artifact_bytes()),
        "train_brier": brier,
        "observations_per_model": {
            lm.model_ids[j]: int(obs[:, j].sum()) for j in range(lm.n_models)
        },
        "weight_norm_per_model": {
            lm.model_ids[j]: float(np.linalg.norm(r.quality.W[:, j]))
            for j in range(lm.n_models)
        },
    }
    return r, diagnostics


def _tokens_in_per_item(tokens_in: np.ndarray, observed: np.ndarray) -> np.ndarray:
    """One input-token count per item: the median over the models that answered it.

    Tokenisers differ by a few percent between checkpoints, and the router prices an
    item before it has chosen a model, so it needs a single number per item.
    """
    out = np.zeros(observed.shape[0])
    for i in range(observed.shape[0]):
        obs = observed[i]
        out[i] = float(np.median(tokens_in[i, obs])) if obs.any() else 800.0
    return np.maximum(out, 1.0)


# ------------------------------------------------------------------- evaluate --
def evaluate(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    lam_cost: float = 0.05,
    seed: int = 0,
    ps: PoolState | None = None,
) -> dict:
    """Router against every baseline a reader would reasonably ask about.

    `ps` overrides the price lane, for pools that are a subset of the catalogue.
    """
    r, _ = train_router(lm, X, train, lam_cost=lam_cost)
    ps = ps if ps is not None else pool_state(list(lm.model_ids))
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]

    q, c = lm.quality[test], lm.cost[test]
    n = len(test)
    rows = np.arange(n)

    dec = r.decide(X[test], ps, tokens_in=tin)
    dtr = _dense(lm, train)
    frontier_col = frontier_reference_column(lm.quality[dtr])
    w = UtilityWeights(lam_cost=lam_cost)
    util = per_cell_utility(q, c, w, ref_col=frontier_col)
    best_single = best_single_column(per_cell_utility(
        lm.quality[dtr], lm.cost[dtr], w, ref_col=frontier_col))

    def report(name: str, choice: np.ndarray) -> dict:
        sav = savings_report(c, choice, frontier_col)
        # Reported against both baselines on purpose. The frontier model is the
        # counterfactual the product quotes ("what this would have cost on one strong
        # model"), but on this pool it is not the strongest policy available — one
        # model beats it on quality *and* price — so quoting only that comparison
        # would flatter the router. Best Single is the honest opponent.
        bs_sav = savings_report(c, choice, best_single)
        return {
            "policy": name,
            "quality": float(q[rows, choice].mean()),
            "cost_usd": float(c[rows, choice].sum()),
            "cost_per_call_usd": float(c[rows, choice].mean()),
            "utility": float(util[rows, choice].mean()),
            "savings_vs_frontier_pct": sav["savings_pct"],
            "quality_vs_frontier_pct": float(
                q[rows, choice].mean() / max(q[:, frontier_col].mean(), 1e-12)),
            "savings_vs_best_single_pct": bs_sav["savings_pct"],
            "quality_vs_best_single_pct": float(
                q[rows, choice].mean() / max(q[:, best_single].mean(), 1e-12)),
            "traffic_share": {
                lm.model_ids[j]: float((choice == j).mean()) for j in range(lm.n_models)
            },
        }

    rng = np.random.default_rng(seed)
    cheapest = int(np.argmin([m.blended_price for m in CHUTES_CATALOG]))
    policies = [
        report("router", dec.choice),
        report("best-single (utility)", np.full(n, best_single)),
        report(f"frontier model ({by_id(CHUTES_CATALOG, lm.model_ids[frontier_col]).label})",
               np.full(n, frontier_col)),
        report("cheapest model", np.full(n, cheapest)),
        report("random", rng.integers(0, lm.n_models, size=n)),
        report("oracle (per item, utility)", util.argmax(axis=1)),
        report("oracle (per item, quality)", q.argmax(axis=1)),
    ]

    # Is one model simply better than every other on both axes? If so, say so: it
    # bounds how much any router on this pool can be worth.
    mean_q, mean_c = q.mean(axis=0), c.mean(axis=0)
    dominated_by: dict[str, list[str]] = {}
    for j in range(lm.n_models):
        better = [lm.model_ids[i] for i in range(lm.n_models)
                  if i != j and mean_q[i] >= mean_q[j] and mean_c[i] <= mean_c[j]]
        if better:
            dominated_by[lm.model_ids[j]] = better
    # No model dominates a whole pool that has a real price ladder — the cheapest
    # column is never beaten on price. The question that actually matters is
    # narrower: is the counterfactual the product quotes ("what this would have cost
    # on one strong model") itself beaten outright by something cheaper? When it is,
    # savings quoted against it are inflated by the gap between two single models,
    # and the honest opponent is the one that dominates it.
    frontier_id = lm.model_ids[frontier_col]
    beats_frontier = dominated_by.get(frontier_id, [])

    return {
        "policies": policies,
        "frontier_model": frontier_id,
        "best_single_model": lm.model_ids[best_single],
        "n_test_items": int(n),
        "lam_cost": lam_cost,
        "dominated_models": dominated_by,
        "frontier_model_is_dominated": bool(beats_frontier),
        "models_beating_the_frontier_model": beats_frontier,
    }


def sweep_lambda(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    lambdas: list[float] | None = None,
) -> list[dict]:
    """The cost/quality dial, end to end — the curve behind the dashboard slider."""
    if lambdas is None:
        lambdas = [0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.35, 0.6, 1.0]
    ps = pool_state()
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    q, c = lm.quality[test], lm.cost[test]
    rows = np.arange(len(test))
    frontier_col = frontier_reference_column(lm.quality[_dense(lm, train)])

    out = []
    for lc in lambdas:
        r, _ = train_router(lm, X, train, lam_cost=lc)
        choice = r.decide(X[test], ps, tokens_in=tin).choice
        sav = savings_report(c, choice, frontier_col)
        tier_mix = _tier_mix(choice)
        out.append({
            "lam_cost": lc,
            "quality": float(q[rows, choice].mean()),
            "quality_vs_frontier": float(
                q[rows, choice].mean() / max(q[:, frontier_col].mean(), 1e-12)),
            "cost_usd": float(c[rows, choice].sum()),
            "savings_vs_frontier": sav["savings_pct"],
            "models_used": int(len(np.unique(choice))),
            "tier_mix": tier_mix,
        })
    return out


def calibrate_lam_cost(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    quality_floor: float = 0.99,
    lambdas: list[float] | None = None,
) -> dict:
    """Pick the dial setting, on this pool, against the strongest single model.

    λ_c = 0.05 is this package's calibrated operating point *on RouterBench*, and
    carrying it over unexamined is a mistake: it is a weight on a cost ratio, and
    the Chutes pool's cost ratios span three orders of magnitude against
    RouterBench's one. At 0.05 the router here spends 84% *more* than simply
    sending everything to the best single model, for slightly less quality — the
    dial is set so loose that the cost term barely enters the argmax.

    So it is calibrated rather than assumed: the largest λ_c that still holds
    `quality_floor` of the Best Single model's quality on held-out items. The
    floor is the constraint the product cares about; savings is what is maximised
    subject to it.
    """
    if lambdas is None:
        lambdas = [0.0, 0.01, 0.02, 0.05, 0.08, 0.12, 0.16, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7, 1.0]
    ps = pool_state()
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    q, c = lm.quality[test], lm.cost[test]
    rows = np.arange(len(test))
    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    bs = best_single_column(per_cell_utility(
        lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=0.05), ref_col=fc))
    bs_q, bs_c = float(q[:, bs].mean()), float(c[:, bs].mean())

    grid = []
    for lc in lambdas:
        r, _ = train_router(lm, X, train, lam_cost=lc)
        choice = r.decide(X[test], ps, tokens_in=tin).choice
        rq, rc = float(q[rows, choice].mean()), float(c[rows, choice].mean())
        grid.append({
            "lam_cost": lc,
            "quality": rq,
            "cost_per_call_usd": rc,
            "quality_vs_best_single": rq / max(bs_q, 1e-12),
            "cost_vs_best_single": rc / max(bs_c, 1e-12),
            "savings_vs_best_single": 1.0 - rc / max(bs_c, 1e-12),
        })

    feasible = [g for g in grid if g["quality_vs_best_single"] >= quality_floor]
    chosen = max(feasible, key=lambda g: g["savings_vs_best_single"]) if feasible else None
    return {
        "grid": grid,
        "quality_floor": quality_floor,
        "best_single_model": lm.model_ids[bs],
        "best_single_quality": bs_q,
        "best_single_cost_per_call": bs_c,
        "chosen_lam_cost": chosen["lam_cost"] if chosen else None,
        "chosen": chosen,
        "reading": (
            f"λ_c={chosen['lam_cost']:g} is the loosest setting that still holds "
            f"{quality_floor:.0%} of {lm.model_ids[bs]}'s quality: "
            f"{chosen['savings_vs_best_single']:.1%} cheaper at "
            f"{chosen['quality_vs_best_single']:.1%} of its quality."
            if chosen else
            f"No λ_c on the grid holds {quality_floor:.0%} of the best single model's "
            f"quality — on this pool the router cannot beat it at that floor."
        ),
    }


def _tier_mix(choice: np.ndarray) -> dict[str, float]:
    tiers = np.array([m.tier for m in CHUTES_CATALOG])
    picked = tiers[choice]
    return {t: float((picked == t).mean()) for t in TIER_ORDER}


# ------------------------------------------------------------------ analytics --
def model_table(lm: LabelMatrix, test: np.ndarray, choice: np.ndarray | None = None) -> list[dict]:
    """Per-model: what it scores, what it costs, and whether it earns its slot."""
    q = lm.quality[test]
    rows = []
    for j, mid in enumerate(lm.model_ids):
        m = by_id(CHUTES_CATALOG, mid)
        b = CHUTES_PROXY[j]
        uniquely = (q[:, j] > 0.5) & ((q > 0.5).sum(axis=1) == 1)
        rows.append({
            "model_id": mid,
            "label": m.label,
            "tier": m.tier,
            "family": m.family,
            "proxy_id": b.proxy_id,
            "proxy_exact": b.exact,
            "proxy_same_family": b.same_family,
            "accuracy": float(q[:, j].mean()),
            "cost_per_call_usd": float(lm.cost[test, j].mean()),
            "tokens_out_mean": float(lm.tokens_out[test, j].mean()),
            "in_per_1m": m.in_per_1m,
            "out_per_1m": m.out_per_1m,
            "blended_price": m.blended_price,
            "quality_per_dollar": float(
                q[:, j].mean() / max(lm.cost[test, j].mean(), 1e-12)),
            "uniquely_correct": int(uniquely.sum()),
            "uniquely_correct_share": float(uniquely.mean()),
            "traffic_share": float((choice == j).mean()) if choice is not None else None,
        })
    return rows


def domain_table(lm: LabelMatrix, test: np.ndarray, choice: np.ndarray | None = None) -> list[dict]:
    """Where each model wins. The evidence that a pool beats a single model."""
    q = lm.quality[test]
    dom = lm.domain[test]
    rows = []
    for d in sorted(set(dom.tolist())):
        mask = dom == d
        acc = q[mask].mean(axis=0)
        cost = lm.cost[test][mask].mean(axis=0)
        value = acc / np.maximum(cost, 1e-12)
        row = {
            "domain": d,
            "items": int(mask.sum()),
            "best_quality_model": lm.model_ids[int(acc.argmax())],
            "best_quality": float(acc.max()),
            "best_value_model": lm.model_ids[int(value.argmax())],
            "spread": float(acc.max() - acc.min()),
            "oracle_quality": float(q[mask].max(axis=1).mean()),
        }
        if choice is not None:
            picked = choice[mask]
            row["router_quality"] = float(q[mask][np.arange(mask.sum()), picked].mean())
            counts = np.bincount(picked, minlength=lm.n_models)
            row["router_top_model"] = lm.model_ids[int(counts.argmax())]
            row["router_models_used"] = int((counts > 0).sum())
        rows.append(row)
    return rows


def task_table(lm: LabelMatrix, test: np.ndarray, choice: np.ndarray) -> list[dict]:
    """Same, at the corpus's own task granularity."""
    tasks = lm.task[test]
    q = lm.quality[test]
    rows = []
    for t in sorted(set(tasks.tolist())):
        mask = tasks == t
        acc = q[mask].mean(axis=0)
        picked = choice[mask]
        counts = np.bincount(picked, minlength=lm.n_models)
        rows.append({
            "task": t,
            "items": int(mask.sum()),
            "best_model": lm.model_ids[int(acc.argmax())],
            "best_quality": float(acc.max()),
            "router_quality": float(q[mask][np.arange(mask.sum()), picked].mean()),
            "oracle_quality": float(q[mask].max(axis=1).mean()),
            "router_top_model": lm.model_ids[int(counts.argmax())],
            "tier_mix": _tier_mix(picked),
        })
    return rows


def prediction_quality(lm: LabelMatrix, X: np.ndarray, train: np.ndarray,
                       test: np.ndarray) -> dict:
    """Does the estimator predict, and does predicting help it rank?

    Both are reported because this package's own scaling study found they come
    apart: the argmax reads the order between models and throws the level away.
    """
    r, _ = train_router(lm, X, train)
    pred = r.quality.predict(X[test])
    truth = lm.quality[test]

    brier = float(((pred - truth) ** 2).mean())
    base = float(((truth.mean() - truth) ** 2).mean())

    # Ranking concordance: over random model pairs on the same item, how often does
    # the predicted order match the measured one? Ties in truth are skipped.
    rng = np.random.default_rng(0)
    n, k = truth.shape
    a = rng.integers(0, k, size=20000)
    b = rng.integers(0, k, size=20000)
    i = rng.integers(0, n, size=20000)
    keep = a != b
    a, b, i = a[keep], b[keep], i[keep]
    dt = truth[i, a] - truth[i, b]
    dp = pred[i, a] - pred[i, b]
    nz = np.abs(dt) > 1e-9
    concordance = float((np.sign(dt[nz]) == np.sign(dp[nz])).mean())

    return {
        "val_brier": brier,
        "baseline_brier": base,
        "brier_skill_score": float(1.0 - brier / max(base, 1e-12)),
        "pairwise_ranking_concordance": concordance,
        "pairs_compared": int(nz.sum()),
        "per_model_brier": {
            lm.model_ids[j]: float(((pred[:, j] - truth[:, j]) ** 2).mean())
            for j in range(lm.n_models)
        },
    }


def sufficiency_policy(
    q_hat: np.ndarray,
    cost_hat: np.ndarray,
    tau: float,
    *,
    allowed: np.ndarray | None = None,
) -> np.ndarray:
    """Cheapest model whose predicted quality clears τ; else the best available.

    This is the decision rule the product actually advertises — "the cheapest model
    in the pool that we expect to get this particular question right" — and it is
    *not* the same rule as the §8.7 argmax of q̂ − λ_c·ĉ.

    The difference matters, and it is why two slots looked dead. Under the argmax a
    model can only win by having the highest score, so a column whose mean sits 0.62
    below the leader needs a six-sigma per-item excursion to be picked; the measured
    per-item spread is 0.16, so it is never picked at any λ_c that keeps quality.
    Under a threshold rule a cheap model wins whenever it is *good enough*, which is
    a bar it clears on easy items regardless of what the strongest model would score.
    That is the same reason a per-item oracle sends these columns 31% of traffic
    while the argmax router sends them none.

    τ is a probability of being right, so it reads directly as a service level: at
    τ = 0.5 the router accepts any model it believes more likely than not to answer
    correctly; at τ = 0.9 it accepts almost nothing but the strongest.
    """
    n, k = q_hat.shape
    ok = q_hat >= tau
    if allowed is not None:
        mask = allowed if allowed.ndim == 2 else np.repeat(allowed[None, :], n, axis=0)
        ok = ok & mask
        q_eff = np.where(mask, q_hat, -np.inf)
    else:
        q_eff = q_hat
    # Among the models that clear the bar, take the cheapest; where none clears it,
    # fall back to the best predicted quality — a request is never refused.
    cost_masked = np.where(ok, cost_hat, np.inf)
    choice = cost_masked.argmin(axis=1)
    none_ok = ~ok.any(axis=1)
    if none_ok.any():
        choice[none_ok] = q_eff[none_ok].argmax(axis=1)
    return choice


def sweep_tau(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    taus: tuple[float, ...] = (0.3, 0.4, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9),
    lam_cost: float = 0.2,
) -> dict:
    """The threshold rule across its whole range, against the argmax at its best.

    Reported together because the two rules are not variants of each other — they
    answer different questions, and which one is better depends on whether the pool
    contains models that are cheap and *sometimes* sufficient.
    """
    ps = pool_state()
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    q, c = lm.quality[test], lm.cost[test]
    rows = np.arange(len(test))
    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    bs = best_single_column(per_cell_utility(
        lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=lam_cost), ref_col=fc))
    bs_q, bs_c = float(q[:, bs].mean()), float(c[:, bs].mean())

    r, _ = train_router(lm, X, train, lam_cost=lam_cost)
    dec = r.decide(X[test], ps, tokens_in=tin)
    q_hat, cost_hat = dec.q_hat, dec.cost_hat

    def report(name: str, choice: np.ndarray, extra: dict) -> dict:
        rq, rc = float(q[rows, choice].mean()), float(c[rows, choice].mean())
        shares = {lm.model_ids[j]: float((choice == j).mean()) for j in range(lm.n_models)}
        return {
            "policy": name, **extra,
            "quality": rq, "cost_per_call_usd": rc,
            "quality_vs_best_single": rq / max(bs_q, 1e-12),
            "savings_vs_best_single": 1.0 - rc / max(bs_c, 1e-12),
            "savings_vs_frontier": 1.0 - rc / max(float(c[:, fc].mean()), 1e-12),
            "models_used": int(len(np.unique(choice))),
            "open_tier_share": float(sum(
                v for k, v in shares.items()
                if by_id(CHUTES_CATALOG, k).tier == "open")),
            "traffic_share": shares,
        }

    grid = [report(f"sufficiency τ={t:g}",
                   sufficiency_policy(q_hat, cost_hat, t), {"tau": t})
            for t in taus]
    argmax = report("argmax (§8.7)", dec.choice, {"tau": None})

    # The comparison that decides it: at matched quality, which rule is cheaper?
    feasible = [g for g in grid if g["quality_vs_best_single"] >= 0.98]
    best_suff = max(feasible, key=lambda g: g["savings_vs_best_single"]) if feasible else None

    return {
        "argmax": argmax,
        "grid": grid,
        "best_sufficiency_at_98pct_quality": best_suff,
        "best_single_model": lm.model_ids[bs],
        "reading": (
            f"At ≥98% of {lm.model_ids[bs]}'s quality the threshold rule (τ="
            f"{best_suff['tau']:g}) is {best_suff['savings_vs_best_single']:.1%} cheaper "
            f"against the argmax's {argmax['savings_vs_best_single']:.1%}, and it puts "
            f"{best_suff['open_tier_share']:.0%} of traffic on the open tier against "
            f"{argmax['open_tier_share']:.0%}."
            if best_suff else
            "No threshold on the grid holds 98% of the best single model's quality."
        ),
    }


def open_weights_only(cache=None) -> dict:
    """What it would cost to bind every slot to an open-weights stand-in.

    A fair question, because every model Chutes serves is open-weights and two of
    the thirteen bindings are not: the frontier slots lean on gpt-5 and
    gemini-2.5-pro as capability anchors. If open stand-ins would do, they should be
    used.

    This checks rather than argues. It rebinds the closed slots to the strongest
    unused open model in the corpus and reports the resulting pool, so the answer is
    a table instead of a preference.
    """
    from ..data import llmrouterbench as _lrb

    # Candidates have to be ranked on a *common* task set. Scoring each on its own
    # coverage is the same trap that made union-training lose twelve points: the
    # small open models were run on 22 tasks including easy ones the large models
    # never saw, so their raw means come out flattering. Ranked that way,
    # GLM-Z1-9B-0414 "beats" gemini-2.5-pro — which is an artefact of the question
    # mix, not a fact about the models.
    lm_ref, _ = build_pool(cache=cache)
    shared_tasks = sorted(set(lm_ref.task[_dense(lm_ref, np.arange(lm_ref.n_items))]))

    lm_all = _lrb.load(cache, tasks=shared_tasks) if cache else _lrb.load(tasks=shared_tasks)
    acc: dict[str, float] = {}
    for j, mid in enumerate(lm_all.model_ids):
        obs = lm_all.observed[:, j]
        if obs.sum() > 500:
            acc[mid] = float(lm_all.quality[obs, j].mean())

    used = {b.proxy_id for b in CHUTES_PROXY}
    spare_open = sorted(
        (m for m in acc if m in OPEN_WEIGHT_PROXIES and m not in used),
        key=lambda m: -acc[m])

    swaps, new_bindings = [], []
    spare = list(spare_open)
    for b in CHUTES_PROXY:
        if b.proxy_id in CLOSED_WEIGHT_PROXIES and spare:
            replacement = spare.pop(0)
            swaps.append({
                "chutes_id": b.chutes_id,
                "label": by_id(CHUTES_CATALOG, b.chutes_id).label,
                "tier": by_id(CHUTES_CATALOG, b.chutes_id).tier,
                "was": b.proxy_id, "was_accuracy": acc.get(b.proxy_id),
                "now": replacement, "now_accuracy": acc.get(replacement),
            })
            new_bindings.append(ProxyBinding(b.chutes_id, replacement,
                                             "open-weights substitute", False, False))
        else:
            new_bindings.append(b)

    lm_open, _ = build_pool(cache=cache, bindings=tuple(new_bindings))
    dense = _dense(lm_open, np.arange(lm_open.n_items))
    open_acc = lm_open.quality[dense].mean(axis=0)
    tiers = [m.tier for m in CHUTES_CATALOG]

    # The question that decides it: does the frontier tier still sit above the mid
    # tier? A frontier slot that scores below the models it is meant to back up is
    # not a frontier slot, it is a dominated column nobody will ever be routed to.
    mid_max = max((float(open_acc[i]) for i, t in enumerate(tiers) if t == "mid"),
                  default=0.0)
    frontier_scores = {CHUTES_CATALOG[i].label: float(open_acc[i])
                       for i, t in enumerate(tiers) if t == "frontier"}
    frontier_holds = all(v >= mid_max for v in frontier_scores.values())

    return {
        "swaps": swaps,
        "spare_open_models_available": len(spare_open),
        "best_mid_tier_accuracy": mid_max,
        "frontier_tier_accuracy": frontier_scores,
        "frontier_tier_still_above_mid": frontier_holds,
        "closed_bindings_in_use": [
            {"chutes_id": b.chutes_id,
             "label": by_id(CHUTES_CATALOG, b.chutes_id).label,
             "proxy_id": b.proxy_id}
            for b in CHUTES_PROXY if b.proxy_id in CLOSED_WEIGHT_PROXIES
        ],
        "open_binding_share": sum(
            b.proxy_id in OPEN_WEIGHT_PROXIES for b in CHUTES_PROXY) / len(CHUTES_PROXY),
        "reading": (
            "Every slot can be bound to an open-weights model, but the frontier tier "
            "stops being a frontier tier: "
            + "; ".join(f"{k} falls to {v:.3f}" for k, v in frontier_scores.items())
            + f" against a best mid-tier model at {mid_max:.3f}. The corpus grades no "
            "open model strong enough to sit above the mid tier, so the two frontier "
            "slots keep closed-weight capability anchors and are labelled as such."
            if not frontier_holds else
            "Open-weights stand-ins hold the tier ordering; the closed anchors are "
            "not needed and should be replaced."
        ),
    }


def scaling_curves(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    lam_cost: float = 0.2,
    sizes: tuple[int, ...] | None = None,
    dims: tuple[int, ...] = (4, 8, 16, 32, 52, 64, 96, 128),
    repeats: int = 3,
    seed: int = 0,
) -> dict:
    """Loss against data and against capacity — and what each buys the product.

    Every row carries the prediction loss *and* the routing outcome from the same
    fit, because on this codebase's own evidence the two come apart: the argmax
    reads the order between models and throws the level away, so a model can
    improve its Brier score while routing worse. A loss curve on its own would
    therefore be the wrong thing to size the model by, and a curve that only showed
    savings would hide whether the estimator had converged.

    The product reading is the third series: `savings_vs_best_single`. That is the
    money, and it is what the capacity sweep should be read against.
    """
    if sizes is None:
        sizes = (100, 250, 500, 1000, 1500, 2000, len(train))
    ps = pool_state()
    tin_item = _tokens_in_per_item(tokens_in, lm.observed)
    tin_test = tin_item[test]
    q, c = lm.quality[test], lm.cost[test]
    rows_idx = np.arange(len(test))
    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    bs = best_single_column(per_cell_utility(
        lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=lam_cost), ref_col=fc))
    bs_q, bs_c = float(q[:, bs].mean()), float(c[:, bs].mean())

    def score(r, Xt: np.ndarray, Xv: np.ndarray) -> dict:
        pred = r.quality.predict(Xv)
        choice = r.decide(Xv, ps, tokens_in=tin_test).choice
        rq = float(q[rows_idx, choice].mean())
        rc = float(c[rows_idx, choice].mean())
        return {
            "val_brier": float(((pred - q) ** 2).mean()),
            "quality": rq,
            "cost_per_call_usd": rc,
            "quality_vs_best_single": rq / max(bs_q, 1e-12),
            "savings_vs_best_single": 1.0 - rc / max(bs_c, 1e-12),
            "savings_vs_frontier": 1.0 - rc / max(float(c[:, fc].mean()), 1e-12),
            "models_used": int(len(np.unique(choice))),
        }

    # ------------------------------------------------------------ learning --
    rng = np.random.default_rng(seed)
    learning = []
    for n in sizes:
        n = int(min(n, len(train)))
        for rep in range(repeats if n < len(train) else 1):
            sub = rng.choice(train, size=n, replace=False)
            r, _ = train_router(lm, X, sub, lam_cost=lam_cost)
            learning.append({"n_train": n, "repeat": rep,
                             **score(r, X[sub], X[test])})

    # ------------------------------------------------------------ capacity --
    # Re-fitting φ per d would confound encoder and dimension, so the frozen
    # projection is simply truncated: the leading k components plus the surface
    # block and the bias, which is what a smaller d would have selected anyway.
    from ..features import N_SURFACE

    n_sem = X.shape[1] - N_SURFACE - 1
    capacity = []
    # Clamped and de-duplicated: a request for more components than φ was fitted
    # with would otherwise silently repeat the widest fit several times and read as
    # a plateau that was never measured.
    for k in sorted({int(min(k, n_sem)) for k in dims}):
        cols = list(range(k)) + list(range(n_sem, X.shape[1]))
        Xk = X[:, cols]
        r, _ = train_router(lm, Xk, train, lam_cost=lam_cost)
        capacity.append({"d": len(cols), "semantic_components": k,
                         "artifact_kb": r.artifact_bytes() / 1024,
                         **score(r, Xk[train], Xk[test])})

    def _corr(rows: list[dict], a: str, b: str) -> float:
        u = np.array([r[a] for r in rows], dtype=float)
        v = np.array([r[b] for r in rows], dtype=float)
        if len(u) < 3 or u.std() == 0 or v.std() == 0:
            return float("nan")
        return float(np.corrcoef(u, v)[0, 1])

    full = [r for r in learning if r["n_train"] == max(r2["n_train"] for r2 in learning)]
    best_d = min(capacity, key=lambda r: r["val_brier"])
    best_d_routing = max(capacity, key=lambda r: r["savings_vs_best_single"])
    return {
        "lam_cost": lam_cost,
        "best_single_model": lm.model_ids[bs],
        "best_single_quality": bs_q,
        "best_single_cost_per_call": bs_c,
        "learning_curve": learning,
        "capacity_curve": capacity,
        "coupling": {
            "corr_brier_savings_over_capacity": _corr(capacity, "val_brier",
                                                      "savings_vs_best_single"),
            "corr_brier_quality_over_capacity": _corr(capacity, "val_brier",
                                                      "quality_vs_best_single"),
            "best_d_by_loss": best_d["d"],
            "best_d_by_savings": best_d_routing["d"],
        },
        "converged": {
            "val_brier": float(np.mean([r["val_brier"] for r in full])),
            "savings_vs_best_single": float(
                np.mean([r["savings_vs_best_single"] for r in full])),
            "quality_vs_best_single": float(
                np.mean([r["quality_vs_best_single"] for r in full])),
        },
    }


def cross_validate(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    *,
    lam_cost: float = 0.05,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7),
) -> dict:
    """The headline numbers over several splits, with a standard error.

    The dense core is 3,932 items and the test half of one split is ~1,376, which is
    small enough that a single split's savings figure moves by a point or two on the
    seed alone. Quoting one split would be quoting noise.
    """
    ps = pool_state()
    tin_item = _tokens_in_per_item(tokens_in, lm.observed)
    sav, qual, qvf, used, sav_bs, q_bs = [], [], [], [], [], []
    for s in seeds:
        train, test = split(lm, seed=s)
        r, _ = train_router(lm, X, train, lam_cost=lam_cost)
        choice = r.decide(X[test], ps, tokens_in=tin_item[test]).choice
        q, c = lm.quality[test], lm.cost[test]
        rows = np.arange(len(test))
        dtr = _dense(lm, train)
        fc = frontier_reference_column(lm.quality[dtr])
        bs = best_single_column(per_cell_utility(
            lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=lam_cost), ref_col=fc))
        rep = savings_report(c, choice, fc)
        sav.append(rep["savings_pct"])
        qual.append(float(q[rows, choice].mean()))
        qvf.append(float(q[rows, choice].mean() / max(q[:, fc].mean(), 1e-12)))
        sav_bs.append(savings_report(c, choice, bs)["savings_pct"])
        q_bs.append(float(q[rows, choice].mean() / max(q[:, bs].mean(), 1e-12)))
        used.append(int(len(np.unique(choice))))

    def ms(v: list[float]) -> dict:
        a = np.asarray(v, dtype=float)
        return {"mean": float(a.mean()),
                "se": float(a.std(ddof=1) / np.sqrt(len(a))) if len(a) > 1 else 0.0,
                "values": [float(x) for x in a]}

    return {
        "seeds": list(seeds),
        "lam_cost": lam_cost,
        "savings_vs_frontier": ms(sav),
        "quality": ms(qual),
        "quality_vs_frontier": ms(qvf),
        "savings_vs_best_single": ms(sav_bs),
        "quality_vs_best_single": ms(q_bs),
        "models_used": ms([float(u) for u in used]),
    }


def load_artifact(path):
    """Reconstruct a routable engine from disk. No corpus, no refit.

    Returns `(router, feature_map, pool, model_ids)` — everything a gateway needs to
    turn a prompt into a model choice:

        router, fm, pool, ids = load_artifact("router_real.npz")
        x = fm.transform([prompt])
        choice = router.decide(x, pool).choice

    The lanes store A and B, not the solved weights, because σ needs A. Only W and A
    are written, so B is recovered as `A @ W` — exact up to the solve, and asserted
    against the saved W on load rather than trusted.

    Raises if the artifact predates `feature_map=` and therefore cannot transform a
    prompt. That is deliberate: an engine that silently cannot compute its own inputs
    is worse than one that refuses to load, because the failure surfaces as a
    dimension error somewhere in a request path instead of here.
    """
    from pathlib import Path

    from ..features import FeatureMap

    z = np.load(Path(path), allow_pickle=True)
    ids = [str(m) for m in z["model_ids"]]
    k, d = len(ids), int(z["quality_W"].shape[0])

    if "fm_basis" not in z:
        raise ValueError(
            f"{path} carries no feature map, so it cannot transform a prompt. "
            "Re-save with save_artifact(..., feature_map=fm).")
    fm = FeatureMap(n_components=int(z["fm_n_components"]),
                    n_buckets=int(z["fm_n_buckets"]))
    fm._mean, fm._basis, fm._scale = z["fm_mean"], z["fm_basis"], z["fm_scale"]

    cfg = RouterConfig(lam=float(z["cfg_lam"]), alpha=float(z["cfg_alpha"]),
                       lam_cost=float(z["cfg_lam_cost"]),
                       ref_model=(None if int(z["cfg_ref_model"]) < 0
                                  else int(z["cfg_ref_model"])))
    r = RidgeLinUCBRouter(d, k, cfg)
    for lane, wk, ak in ((r.quality, "quality_W", "quality_A"),
                         (r.tokens, "tokens_W", "tokens_A")):
        W = z[wk].astype(np.float64)
        lane.A_m = z[ak].astype(np.float64)
        lane.B = np.stack([lane.A_m[m] @ W[:, m] for m in range(k)], axis=1)
        lane._W = None
        assert np.allclose(lane.W, W, atol=1e-3), "weights did not survive the round trip"
    r.counts = z["counts"]

    pool = PoolState(price_in=z["price_in"], price_out=z["price_out"])
    return r, fm, pool, ids


def save_artifact(router: RidgeLinUCBRouter, lm: LabelMatrix, path,
                  feature_map=None) -> dict:
    """Write the trained policy — the thing a gateway would actually load.

    Stored as the solved weights plus the Gram matrices, because σ needs A and a
    gateway that cannot compute σ cannot explore.

    Every array is indexed by **this matrix's** columns, not by the catalogue. That
    distinction only shows up when the pool is a subset — a graded run that reached
    four of the thirteen slots writes four weight columns, and a price vector of
    thirteen taken from the catalogue would silently pair column 1 with slot 1's
    price. Prices and the proxy list are resolved through `lm.model_ids` for that
    reason, and the lengths are asserted before anything is written: a gateway that
    loads a mismatched artifact does not crash, it just bills the wrong model.
    """
    from pathlib import Path

    pool = [by_id(CHUTES_CATALOG, m) for m in lm.model_ids]
    k = len(lm.model_ids)
    assert router.quality.W.shape[1] == k, (
        f"weights have {router.quality.W.shape[1]} columns, pool has {k}")

    proxies = []
    for m in lm.model_ids:
        try:
            proxies.append(proxy_for(m).proxy_id)
        except KeyError:                      # measured directly; nothing stood in
            proxies.append("")

    # φ is part of the engine, not a detail of how it was trained: weights are
    # meaningless against features computed by a different projection, and the
    # projection's rank depends on how many items it was fitted on. Shipping them
    # apart is how you get a dimension error in a request path.
    fm_arrays = {}
    if feature_map is not None:
        fm_arrays = {
            "fm_mean": feature_map._mean, "fm_basis": feature_map._basis,
            "fm_scale": feature_map._scale,
            "fm_n_components": int(feature_map.n_components),
            "fm_n_buckets": int(feature_map.n_buckets),
        }

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        model_ids=np.array(lm.model_ids, dtype=object),
        proxy_ids=np.array(proxies, dtype=object),
        quality_W=router.quality.W.astype(np.float32),
        tokens_W=router.tokens.W.astype(np.float32),
        quality_A=router.quality.A_m.astype(np.float32),
        tokens_A=router.tokens.A_m.astype(np.float32),
        counts=router.counts,
        price_in=np.array([m.in_per_1m for m in pool]),
        price_out=np.array([m.out_per_1m for m in pool]),
        # The config the weights were fitted under. Without it a reload has to guess
        # lam_cost, and lam_cost is the dial that decides every routing choice.
        cfg_lam=float(router.cfg.lam),
        cfg_alpha=float(router.cfg.alpha),
        cfg_lam_cost=float(router.cfg.lam_cost),
        cfg_ref_model=int(-1 if router.cfg.ref_model is None else router.cfg.ref_model),
        allow_pickle=True,
        **fm_arrays,
    )
    return {"path": str(path), "bytes": int(path.stat().st_size),
            "in_memory_bytes": int(router.artifact_bytes())}


def frontend_payload(lm: LabelMatrix, evaluation: dict, sweep: list[dict],
                     models: list[dict], diagnostics: dict) -> dict:
    """The numbers `src/lib/data.ts` would quote, in one place.

    Kept explicit rather than letting the frontend read the raw artifact, so that
    the proxy caveat travels with the numbers.
    """
    router = next(p for p in evaluation["policies"] if p["policy"] == "router")
    return {
        "proxy_backed": True,
        "disclaimer": (
            "Quality and token behaviour are measured on a stand-in model per Chutes "
            "slot (see catalog.CHUTES_PROXY), not on the Chutes endpoint. Prices are "
            "the published Chutes rates."
        ),
        "pool_size": lm.n_models,
        "test_items": evaluation["n_test_items"],
        "lam_cost": evaluation["lam_cost"],
        "savings_pct": router["savings_vs_frontier_pct"],
        "quality_retained_pct": router["quality_vs_frontier_pct"],
        "baseline_model": evaluation["frontier_model"],
        "artifact_bytes": diagnostics["artifact_bytes"],
        "tier_mix": {
            t: float(sum(v for k, v in router["traffic_share"].items()
                         if by_id(CHUTES_CATALOG, k).tier == t))
            for t in TIER_ORDER
        },
        "models": [
            {"id": m["model_id"], "label": m["label"], "tier": m["tier"],
             "accuracy": m["accuracy"], "traffic_share": m["traffic_share"],
             "blended_price": m["blended_price"], "proxy_id": m["proxy_id"]}
            for m in models
        ],
        "frontier_curve": [
            {"lam_cost": s["lam_cost"], "savings": s["savings_vs_frontier"],
             "quality_retained": s["quality_vs_frontier"]}
            for s in sweep
        ],
    }
