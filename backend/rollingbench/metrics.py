"""Scoring — RollingBench §8.8, plus the shrinkage fix from Contribution 3 (§6).

The whole point of normalised regret is that it stays comparable while the test
changes: oracle and baseline are recomputed on every batch, so a harder batch
lowers both and leaves the score alone.

The failure mode Contribution 3 names is visible directly in the formula: when `U_oracle`
and `U_base` converge, the denominator collapses toward `eps` and the score is noise
wearing a confident-looking number. `shrink_scores` is the empirical-Bayes weight that
pulls those batches toward a running estimate in proportion to how little they actually
discriminate.

Contribution 3's account of *when* that happens is backwards, though, and the correction
matters operationally. §6 reads: "When a challenge batch happens to be easy — every model
in the pool performs about the same on it — U_oracle and U_base converge." On binary-
graded data the opposite is true. If every model performs about the same, per-item luck
lets the realised-outcome oracle beat any single model by a wide margin, so the
denominator is *large*. It collapses when one model **dominates**, because then the best
single model is already nearly as good as the oracle. Measured on RouterBench, batch
information correlates −0.54 with the spread between the best and worst model in the
batch, and −0.49 with how far the best model leads the second.

The fix is unaffected — it keys on measured information, not on the reason — but an
operator who believed §6 might try to help by filtering easy items out of challenge
batches, which would remove the informative ones and keep the degenerate ones.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class UtilityWeights:
    """λ_c and λ_l from §8.7. Cost and latency enter unitless, normalised by the
    Best Single model's values, so the weights are comparable across pools."""

    # 0.05 is the calibrated operating point on RouterBench: 42.5% cost reduction at
    # 99.0% of the frontier model's quality on held-out items. λ_c reads as "quality
    # I will give up to save the cost of one frontier call", so it is the product's
    # cost/quality dial and the curve it traces is in experiments/frontier.py.
    lam_cost: float = 0.05
    lam_latency: float = 0.0


def per_cell_utility(
    quality: np.ndarray,
    cost: np.ndarray,
    weights: UtilityWeights = UtilityWeights(),
    latency: np.ndarray | None = None,
    cost_ref: np.ndarray | float | None = None,
    latency_ref: np.ndarray | float | None = None,
    ref_col: int | None = None,
) -> np.ndarray:
    """u(i, m) = qual − λ_c·cost/cost_ref − λ_l·lat/lat_ref.

    `ref_col` names the reference model, and §8.7 is specific that it should be the
    Best Single model: "c_ref and l_ref are the Best Single model's values, so both
    penalty terms are unitless."

    That choice is not cosmetic. Normalising by the *pool mean* instead — the obvious
    alternative — makes the router blind to a price change on a model that dominates
    the mean: cut the dearest model's price by 65% and the mean falls with it, so
    every ratio in the pool comes out roughly where it started and nothing re-routes.
    A fixed reference model has no such feedback, so a price cut moves the ratios it
    ought to move. Normalising per item, meanwhile, is what keeps a one-line prompt
    and a long one on the same scale.

    The pool mean is retained as the fallback for the case where no reference has
    been designated yet, which happens only on the very first batch.
    """
    if cost_ref is None:
        if ref_col is not None:
            cost_ref = np.maximum(cost[:, [ref_col]], 1e-12)
        else:
            cost_ref = np.maximum(cost.mean(axis=1, keepdims=True), 1e-12)
    u = quality - weights.lam_cost * (cost / cost_ref)
    if latency is not None and weights.lam_latency:
        if latency_ref is None:
            latency_ref = (
                np.maximum(latency[:, [ref_col]], 1e-12) if ref_col is not None
                else np.maximum(latency.mean(axis=1, keepdims=True), 1e-12)
            )
        u = u - weights.lam_latency * (latency / latency_ref)
    return u


def reference_column(quality: np.ndarray, cost: np.ndarray | None = None,
                     lam_cost: float | None = None) -> int:
    """The model whose cost is c_ref: the strongest one by measured quality.

    §8.7 says c_ref should be "the Best Single model's values", and §8.8 defines Best
    Single as the highest-*utility* model — which is computed from c_ref. Taken
    literally the utility function is self-referential, and it is not a harmless
    circularity: because the fixed point jumps from one model to another as λ_c
    crosses a threshold, the units of the cost term change mid-curve. Sweeping λ_c
    under that definition produces a discontinuity — measured on RouterBench, savings
    jump from 19% to 93% between λ_c = 0.02 and 0.05 as the reference flips from
    GPT-4 to Yi-34B — which is an artefact of the normalisation, not a property of
    the router.

    Pinning c_ref to the highest-quality model removes the circularity and keeps λ_c
    interpretable as one number: how much quality is worth giving up to save the cost
    of one frontier call. It is also the counterfactual the product already quotes
    (FR-23, and `BASELINE_ID` in the frontend), so the metric and the invoice agree.

    `cost` and `lam_cost` are accepted and ignored so the call sites read the same
    either way; they are what the literal §8.7 definition would need.
    """
    return int(np.argmax(quality.mean(axis=0)))


def best_single_column(utility: np.ndarray) -> int:
    """The Best Single baseline: one model, everything sent to it.

    Chosen on the batch being scored, per §8.8 — re-selected each time, so the
    baseline never becomes a stale artefact of whichever model was best in month
    one.
    """
    return int(np.argmax(utility.mean(axis=0)))


@dataclass(frozen=True)
class BatchScore:
    """One batch, one policy. Everything needed to recompute the score by hand."""

    u_policy: float
    u_oracle: float
    u_base: float
    regret: float
    score: float
    info: float          # U_oracle − U_base: this batch's discriminating power
    n_items: int
    base_col: int

    def as_dict(self) -> dict:
        return {
            "u_policy": self.u_policy,
            "u_oracle": self.u_oracle,
            "u_base": self.u_base,
            "regret": self.regret,
            "score": self.score,
            "info": self.info,
            "n_items": self.n_items,
            "base_col": self.base_col,
        }


def score_batch(
    utility: np.ndarray,
    choices: np.ndarray,
    eps: float = 1e-6,
    base_col: int | None = None,
    clip: bool = True,
) -> BatchScore:
    """Normalised regret for one policy on one batch (§8.8).

    Parameters
    ----------
    utility : (n_items, n_models)
        Per-cell utility, from `per_cell_utility`.
    choices : (n_items,) int
        Which column the policy picked for each item.
    clip : bool
        §8.8 clips the score into [0, 1]. Set False to see how far below the
        baseline a policy actually falls — which is the interesting part of the
        staleness curve, and information the clipped form throws away.
    """
    n = utility.shape[0]
    u_policy = float(utility[np.arange(n), choices].mean())
    u_oracle = float(utility.max(axis=1).mean())
    if base_col is None:
        base_col = best_single_column(utility)
    u_base = float(utility[:, base_col].mean())

    info = u_oracle - u_base
    regret = (u_oracle - u_policy) / (info + eps)
    score = 1.0 - regret
    return BatchScore(
        u_policy=u_policy,
        u_oracle=u_oracle,
        u_base=u_base,
        regret=float(regret),
        score=float(np.clip(score, 0.0, 1.0) if clip else score),
        info=float(info),
        n_items=int(n),
        base_col=int(base_col),
    )


def group_oracle_column(utility: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Best model per group — an *attainable* ceiling, unlike the per-item oracle.

    The per-item oracle of §8.8 takes the argmax of realised outcomes. On binary
    grading that argmax is partly luck: if a weak model happened to guess a
    multiple-choice item correctly, the oracle banks it, and no policy could have
    predicted it. Grouping first (by task, domain, or cluster) averages the luck out
    and leaves the part of the gap a policy could actually capture.
    """
    choices = np.empty(utility.shape[0], dtype=int)
    for g in np.unique(groups):
        mask = groups == g
        choices[mask] = int(utility[mask].mean(axis=0).argmax())
    return choices


@dataclass(frozen=True)
class FeasibleScore:
    """Regret against an attainable ceiling rather than a lucky one.

    `score` can exceed 1: a policy routing per item may beat the best per-group
    assignment. That is information, not an error, so it is not clipped.
    """

    u_policy: float
    u_feasible: float
    u_base: float
    score: float
    info: float
    n_groups: int

    def as_dict(self) -> dict:
        return {
            "u_policy": self.u_policy,
            "u_feasible": self.u_feasible,
            "u_base": self.u_base,
            "score": self.score,
            "info": self.info,
            "n_groups": self.n_groups,
        }


def feasible_score_batch(
    utility: np.ndarray,
    choices: np.ndarray,
    groups: np.ndarray,
    base_col: int | None = None,
    eps: float = 1e-9,
) -> FeasibleScore:
    """Share of the *achievable* oracle-to-baseline gap a policy captured.

    Same shape as §8.8 — recomputed per batch, so it stays comparable while the
    test changes — with the oracle replaced by the best per-group assignment on this
    batch. Reported alongside the literal §8.8 score, never instead of it.
    """
    n = utility.shape[0]
    if base_col is None:
        base_col = best_single_column(utility)
    u_policy = float(utility[np.arange(n), choices].mean())
    feasible_choices = group_oracle_column(utility, groups)
    u_feasible = float(utility[np.arange(n), feasible_choices].mean())
    u_base = float(utility[:, base_col].mean())
    info = u_feasible - u_base
    return FeasibleScore(
        u_policy=u_policy,
        u_feasible=u_feasible,
        u_base=u_base,
        score=float((u_policy - u_base) / (info + eps)),
        info=float(info),
        n_groups=int(len(np.unique(groups))),
    )


def frontier_reference_column(quality: np.ndarray) -> int:
    """The strongest model by measured quality — the savings counterfactual (FR-23).

    Deliberately not the same as `best_single_column`. §8.8's Best Single is the
    best *utility* model, which under a heavy cost weight is a cheap one; quoting
    savings against that would flatter or penalise the router depending on where the
    dial sits. The customer-facing claim is "what this traffic would have cost on
    one strong model", which is the highest-quality column, matching `BASELINE_ID`
    in the frontend.
    """
    return int(np.argmax(quality.mean(axis=0)))


def shrink_scores(
    raw_scores: np.ndarray,
    infos: np.ndarray,
    kappa: float,
    beta: float = 0.8,
) -> dict[str, np.ndarray]:
    """Information-aware shrinkage — Contribution 3, §6.1.

        info_t   = U_oracle_t − U_base_t
        weight_t = info_t / (info_t + kappa)
        score'_t = weight_t · score_t + (1 − weight_t) · running_avg

    The running average is the §16.2 exponential smoother, so this composes with
    the payout mechanism rather than replacing it. Causality matters here: the
    running average must be built from batches *before* t, otherwise the fix looks
    better than it is by peeking at the score it is correcting.
    """
    raw_scores = np.asarray(raw_scores, dtype=float)
    infos = np.maximum(np.asarray(infos, dtype=float), 0.0)
    weights = infos / (infos + kappa)

    smoothed = np.empty_like(raw_scores)
    running = np.empty_like(raw_scores)
    prior = float(raw_scores[0])
    for t, raw in enumerate(raw_scores):
        running[t] = prior
        smoothed[t] = weights[t] * raw + (1.0 - weights[t]) * prior
        # §16.2's β-smoother, fed the shrunk score so one easy batch cannot move
        # the prior much either.
        prior = beta * prior + (1.0 - beta) * smoothed[t]
    return {"score": smoothed, "weight": weights, "running": running}


def calibrate_kappa(infos: np.ndarray, quantile: float = 0.25) -> float:
    """κ from data, not by hand.

    Setting κ to a low quantile of the observed information distribution means
    `weight ≈ 0.5` exactly where batches start being uninformative for this pool,
    and `weight → 1` on the batches that discriminate. Calibrated once, offline,
    which is the only kind of tuning this system has.
    """
    infos = np.asarray(infos, dtype=float)
    infos = infos[np.isfinite(infos) & (infos > 0)]
    if infos.size == 0:
        return 1e-3
    return float(np.quantile(infos, quantile))


def savings_report(
    utility_cost: np.ndarray,
    choices: np.ndarray,
    base_col: int,
) -> dict[str, float]:
    """Realised spend against the Best Single counterfactual (FR-23).

    This is the arithmetic claim the product makes on its dashboard: same requests,
    what they cost routed versus what they would have cost on one strong model.
    """
    n = utility_cost.shape[0]
    routed = float(utility_cost[np.arange(n), choices].sum())
    baseline = float(utility_cost[:, base_col].sum())
    frontier = float(utility_cost.max(axis=1).sum())  # dearest-per-item upper bound
    return {
        "routed_cost": routed,
        "best_single_cost": baseline,
        "savings_usd": baseline - routed,
        "savings_pct": (baseline - routed) / baseline if baseline > 0 else 0.0,
        "vs_dearest_pct": (frontier - routed) / frontier if frontier > 0 else 0.0,
    }
