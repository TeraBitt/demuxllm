"""Cold start — RollingBench §8.6 baseline, and Contribution 2's derived prior (§5).

A brand-new model arrives with no observations. The baseline handles that with two
estimators — an IRT ability fit and a low-rank matrix completion — blended by "a
confidence factor" the source document never writes down. Contribution 2 replaces
the blend with one conjugate Bayesian step, which removes the free parameter and
turns "~250 items suffice" into a quantity that depends on how well the new model is
predicted by the pool's existing latent structure.

The bridge that makes it work is the linking assumption of §5.1: the low-rank item
factors are approximately linear in the same feature map, so there is a Φ with
U·v_k ≈ Φ·w_0. That is an assumption, not a theorem, so `fit_bridge` measures its
residual — experiment 7.4, the precondition for everything else in this file.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ----------------------------------------------------------------------- IRT --
@dataclass
class IRTModel:
    """2-parameter logistic IRT: P(correct | i, m) = sigmoid(a_i·(θ_m − b_i)).

    Item difficulties and discriminations are estimated once from the existing
    pool's history and then held fixed, which is what makes a new model's θ a
    one-dimensional fit over a few hundred observations rather than a joint
    estimation problem.
    """

    difficulty: np.ndarray        # b_i, (n_items,)
    discrimination: np.ndarray    # a_i, (n_items,)
    ability: np.ndarray           # θ_m, (n_models,)

    def prob(self, items: np.ndarray, ability: float) -> np.ndarray:
        z = self.discrimination[items] * (ability - self.difficulty[items])
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def fit_irt(
    quality: np.ndarray,
    observed: np.ndarray,
    n_iter: int = 30,
    tol: float = 1e-5,
) -> IRTModel:
    """Alternating MLE for (b, a, θ).

    Joint MLE by alternating one-dimensional Newton steps: closed-form per
    coordinate, no gradient descent over the whole parameter vector, consistent
    with §8.1's rule about exact solutions and incremental updates.
    """
    n_items, n_models = quality.shape
    y = np.clip(quality, 1e-6, 1 - 1e-6)

    # Initialise from marginals — item difficulty from its solve rate, model ability
    # from its accuracy. Both are already the right monotone transform, so the
    # iteration starts close.
    item_rate = np.array([
        y[i][observed[i]].mean() if observed[i].any() else 0.5
        for i in range(n_items)
    ])
    model_rate = np.array([
        y[observed[:, j], j].mean() if observed[:, j].any() else 0.5
        for j in range(n_models)
    ])
    logit = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
    b = -logit(item_rate)
    theta = logit(model_rate)
    a = np.ones(n_items)

    for _ in range(n_iter):
        theta_old = theta.copy()

        # θ_m | b, a — one Newton step per model.
        for j in range(n_models):
            mask = observed[:, j]
            if not mask.any():
                continue
            theta[j] = _newton_1d(
                theta[j], a[mask], b[mask], y[mask, j], wrt="ability"
            )

        # b_i | θ, a — one Newton step per item.
        for i in range(n_items):
            mask = observed[i]
            if not mask.any():
                continue
            b[i] = _newton_1d(b[i], a[i] * np.ones(mask.sum()), theta[mask], y[i, mask],
                              wrt="difficulty")

        # a_i: discrimination, clamped positive so an item cannot invert.
        for i in range(n_items):
            mask = observed[i]
            if mask.sum() < 3:
                continue
            z = theta[mask] - b[i]
            p = 1.0 / (1.0 + np.exp(-np.clip(a[i] * z, -30, 30)))
            g = np.sum((y[i, mask] - p) * z)
            h = -np.sum(p * (1 - p) * z * z) - 1e-3
            a[i] = float(np.clip(a[i] - g / h, 0.1, 4.0))

        if np.max(np.abs(theta - theta_old)) < tol:
            break

    return IRTModel(difficulty=b, discrimination=a, ability=theta)


def _newton_1d(x0: float, a: np.ndarray, other: np.ndarray, y: np.ndarray, wrt: str) -> float:
    """One damped Newton step on a single logistic coordinate.

    `wrt="ability"` solves for θ given item (a, b); `wrt="difficulty"` solves for b
    given (a, θ). The ridge term on the Hessian is what keeps a perfectly separated
    item (all-correct or all-wrong) from sending the parameter to infinity.
    """
    x = float(x0)
    for _ in range(8):
        z = a * (x - other) if wrt == "ability" else a * (other - x)
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        resid = y - p
        sign = 1.0 if wrt == "ability" else -1.0
        g = sign * np.sum(a * resid) - 0.05 * x          # weak prior toward 0
        h = -np.sum(a * a * p * (1 - p)) - 0.05
        step = g / h
        x -= float(np.clip(step, -1.0, 1.0))
    return float(np.clip(x, -6.0, 6.0))


def fit_ability(irt: IRTModel, items: np.ndarray, outcomes: np.ndarray) -> float:
    """θ for a new model from a handful of probed items — the 1-D Newton fit."""
    return _newton_1d(0.0, irt.discrimination[items], irt.difficulty[items], outcomes,
                      wrt="ability")


def select_probe_items(
    irt: IRTModel,
    candidate_items: np.ndarray,
    ability_estimate: float,
    n: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Adaptive probe selection (§8.6): items whose difficulty sits near the running
    ability estimate carry the most information per item.

    Fisher information for the 2PL is a²·p·(1−p), maximised at b ≈ θ. Sampling
    proportionally rather than taking the top-n keeps the probe from collapsing onto
    a handful of near-identical items.
    """
    b = irt.difficulty[candidate_items]
    a = irt.discrimination[candidate_items]
    p = 1.0 / (1.0 + np.exp(-np.clip(a * (ability_estimate - b), -30, 30)))
    info = a**2 * p * (1 - p) + 1e-9
    n = min(n, len(candidate_items))
    probs = info / info.sum()
    return rng.choice(candidate_items, size=n, replace=False, p=probs)


# ------------------------------------------------------------ low-rank (§8.6) --
@dataclass
class LowRankModel:
    """M ≈ U·Vᵀ. Item factors U are fixed; a new model is one ridge solve for v_k."""

    U: np.ndarray            # (n_items, r)
    V: np.ndarray            # (n_models, r)
    mean: float
    rank: int

    def predict_column(self, v: np.ndarray) -> np.ndarray:
        return self.mean + self.U @ v


def fit_lowrank(
    quality: np.ndarray,
    observed: np.ndarray,
    rank: int = 8,
    n_iter: int = 25,
    lam: float = 1.0,
) -> LowRankModel:
    """Alternating-least-squares matrix completion over observed cells only.

    Each half-step is a ridge solve, so this is closed-form per block — the same
    discipline as the rest of the estimator.
    """
    n_items, n_models = quality.shape
    mean = float(quality[observed].mean()) if observed.any() else 0.0
    R = np.where(observed, quality - mean, 0.0)

    rng = np.random.default_rng(0)
    U = 0.1 * rng.standard_normal((n_items, rank))
    V = 0.1 * rng.standard_normal((n_models, rank))

    for _ in range(n_iter):
        for j in range(n_models):
            mask = observed[:, j]
            if mask.sum() < rank:
                continue
            Uj = U[mask]
            V[j] = np.linalg.solve(Uj.T @ Uj + lam * np.eye(rank), Uj.T @ R[mask, j])
        for i in range(n_items):
            mask = observed[i]
            if mask.sum() < 1:
                continue
            Vi = V[mask]
            U[i] = np.linalg.solve(Vi.T @ Vi + lam * np.eye(rank), Vi.T @ R[i, mask])

    return LowRankModel(U=U, V=V, mean=mean, rank=rank)


def fit_new_column(lr: LowRankModel, items: np.ndarray, outcomes: np.ndarray,
                   lam: float = 1.0) -> np.ndarray:
    """v_k for a new model with U held fixed — one ridge solve over ~250 cells."""
    Ui = lr.U[items]
    r = lr.rank
    return np.linalg.solve(Ui.T @ Ui + lam * np.eye(r), Ui.T @ (outcomes - lr.mean))


# ---------------------------------------------- Contribution 2: derived prior --
@dataclass
class Bridge:
    """Φ, the linking map of §5.1, plus the residual that says whether to trust it.

    `tau2` is the fitted residual variance of the linking assumption. It is not a
    confidence knob: it is measured once from the existing pool, and it is what
    makes the sample-complexity claim in §5.3 a prediction rather than a constant.
    """

    Phi: np.ndarray           # (n_items_sample, d) — item-space ← feature-space
    Phi_pinv: np.ndarray      # (d, n_items_sample)
    tau2: float
    residual_ratio: float     # unexplained share of variance; 7.4's headline number
    r2: float

    @property
    def holds(self) -> bool:
        """A usable bridge explains most of the variance it is asked to carry.

        The 0.5 line is a reporting convention, not a result — the number that
        matters is `r2`, and it is published either way.
        """
        return self.r2 >= 0.5


def fit_bridge(
    X: np.ndarray,
    lowrank: LowRankModel,
    W_quality: np.ndarray,
    lam: float = 1.0,
) -> Bridge:
    """Experiment 7.4: does the item-space low-rank prediction transfer to feature space?

    The check is direct. For every model already in the pool we know both its
    low-rank column prediction `U·v_m` and its fitted feature-space weights `w_m`.
    If the linking assumption holds there is a single Φ with `U·v_m ≈ Φ·w_m` for all
    m simultaneously. Fitting that Φ by ridge and reporting its R² is the test —
    and if it fails, Contribution 2 has no bridge and must be reworked or dropped.

    Parameters
    ----------
    X : (n_items, d)
        Features for the items the low-rank model was fitted on.
    W_quality : (d, n_models)
        Fitted quality weights per existing model, from a `_RidgeLane`.
    """
    n_items, d = X.shape
    n_models = W_quality.shape[1]

    # Targets: each existing model's predicted column in item space.
    targets = np.column_stack([
        lowrank.predict_column(lowrank.V[j]) for j in range(n_models)
    ])                                                # (n_items, n_models)
    # Predictors: each model's feature-space linear prediction of the same column.
    preds = X @ W_quality                             # (n_items, n_models)

    # Φ is the map that best sends the feature-space predictions onto the item-space
    # ones, shared across models. Solved column-space-wise: one ridge per item row
    # would overfit, so fit a single scalar-plus-affine map in the pooled space.
    P = preds.reshape(-1, 1)
    T = targets.reshape(-1, 1)
    design = np.hstack([P, np.ones_like(P)])
    coef = np.linalg.solve(design.T @ design + lam * np.eye(2), design.T @ T)
    fitted = design @ coef

    resid = T - fitted
    ss_res = float((resid**2).sum())
    ss_tot = float(((T - T.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
    tau2 = float(resid.var())

    # Φ as an operator: item-space column ← feature-space weights, i.e. scale X by
    # the fitted slope and carry the intercept.
    Phi = float(coef[0, 0]) * X
    Phi_pinv = np.linalg.pinv(Phi) if np.isfinite(Phi).all() else np.zeros((d, n_items))

    return Bridge(
        Phi=Phi,
        Phi_pinv=Phi_pinv,
        tau2=max(tau2, 1e-8),
        residual_ratio=ss_res / max(ss_tot, 1e-12),
        r2=r2,
    )


@dataclass
class ColdStartPrior:
    """A prior on (A_k, b_k) for a model with no history."""

    A_prior: np.ndarray
    b_prior: np.ndarray
    w0: np.ndarray
    tau2: float
    method: str


def derived_prior(
    bridge: Bridge,
    lowrank: LowRankModel,
    v_k: np.ndarray,
    A_pool: np.ndarray,
    strength: float = 1.0,
) -> ColdStartPrior:
    """Contribution 2, §5.2 — the conjugate prior, with no free confidence knob.

        w_0     = Φ⁺ (U v_k)
        A_prior = A_0 / τ²  · strength
        b_prior = A_prior w_0

    τ² comes from the bridge fit, so a bridge that transfers badly produces a loose
    prior automatically and real observations dominate it sooner. That self-limiting
    behaviour is the reason this is preferable to a hand-set weight even when the
    two happen to agree numerically.
    """
    column = lowrank.predict_column(v_k)                    # (n_items,)
    w0 = bridge.Phi_pinv @ column                           # (d,)

    # A_0 normalised to unit scale so `strength` is interpretable as "worth this
    # many effective observations" rather than inheriting the pool's sample size.
    A0 = A_pool / max(np.trace(A_pool) / A_pool.shape[0], 1e-12)
    A_prior = A0 * (strength / bridge.tau2)
    b_prior = A_prior @ w0
    return ColdStartPrior(A_prior, b_prior, w0, bridge.tau2, method="derived (§5.2)")


def blended_prior(
    irt: IRTModel,
    lowrank: LowRankModel,
    X: np.ndarray,
    v_k: np.ndarray,
    ability: float,
    A_pool: np.ndarray,
    confidence: float = 0.5,
    lam: float = 1.0,
) -> ColdStartPrior:
    """RollingBench §8.6 as written — best-effort reproduction of the informal blend.

    The two estimators are averaged into a synthetic target column, regressed onto
    the feature space, and down-weighted by `confidence`. `confidence` is exactly
    the parameter the source document leaves unspecified; it is a keyword argument
    here so the comparison in experiment 7.2 can sweep it rather than pretend a
    particular value was intended.
    """
    lowrank_col = lowrank.predict_column(v_k)
    irt_col = irt.prob(np.arange(len(irt.difficulty)), ability)
    synthetic = 0.5 * lowrank_col + 0.5 * irt_col

    d = X.shape[1]
    w0 = np.linalg.solve(X.T @ X + lam * np.eye(d), X.T @ synthetic)

    A0 = A_pool / max(np.trace(A_pool) / A_pool.shape[0], 1e-12)
    A_prior = A0 * confidence
    return ColdStartPrior(A_prior, A_prior @ w0, w0, float("nan"),
                          method=f"blend (§8.6, confidence={confidence})")


def predicted_probe_count(
    tau2: float,
    sigma2: float,
    epsilon: float,
) -> float:
    """§5.3's sample-complexity expression.

        posterior variance ≈ σ² / (n_k + σ²/τ²)   ⇒   n_k ≈ σ²/ε − σ²/τ²

    A model that loads cleanly onto the pool's existing factors has small τ² and so
    needs fewer probe items; one with no close analogue needs more. A flat ~250
    cannot express that difference, which is the whole claim.
    """
    return max(0.0, sigma2 / max(epsilon, 1e-12) - sigma2 / max(tau2, 1e-12))
