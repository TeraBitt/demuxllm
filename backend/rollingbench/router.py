"""The router engine — RollingBench §8.3–§8.7, and the §4 decomposition.

Everything here is closed-form. One d×d Gram matrix is shared across every model
in the pool (§8.3), so adding a model appends a column to B and costs one
matrix-vector product rather than a retrain. New observations arrive as rank-one
updates (§8.4). Uncertainty falls out of the same matrix that produced the
estimate, which is why cold start, drift absorption and exploration are one
mechanism and not three (§8.5).

Two estimators live in this file and the difference between them is the research
claim:

`RidgeLinUCBRouter` is the baseline. One shared forgetting factor γ decays the
whole state — quality and token-count targets alike.

`DecomposedRouter` is Contribution 1. Quality and token count get their own Gram
matrix and their own decay rate; anything observable at decision time (price,
latency, availability) is read from a live table and never enters the fit at all.
Same interface, same artifact shape, same flop count per update.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# --------------------------------------------------------------------- state --
class _RidgeLane:
    """One discounted-RLS lane: Gram matrices and one target column per model.

    Holds A and B rather than the solved weights because A is what the uncertainty
    term needs, and refactorising on demand is cheaper than keeping an inverse in
    step with a stream of rank-one updates.

    Shared versus per-model Gram
    ----------------------------
    The source document is inconsistent on this and the difference decides whether
    cold start works, so it is a switch rather than a silent choice.

    §8.3 keeps one A for the whole pool: "A depends only on the queries, not on
    which model answered them. So one 64×64 inverse serves every model." That is
    exact only when every model was run on the same items. When coverage is uneven
    — a model that just arrived and has 250 probe cells against a pool with 8,000
    items of history, or the §18.2 sampling plan that runs reasoning models on a 25%
    subset — the shared A carries every item while the new column's b carries a
    fraction of them, so w = A⁻¹b is shrunk toward zero by roughly the coverage
    ratio. The under-observed model is then systematically *under*-predicted, which
    is precisely backwards for exploration: the model we know least about looks
    worst rather than most uncertain.

    §8.5 writes the opposite, and gets the behaviour right: σ_m(x) = sqrt(xᵀA_m⁻¹x),
    "a newly added model has a nearly uninformative A, so its σ is large, so it gets
    tried". §8.9's own budget agrees — "state per model: A 64×64, plus 3 target
    vectors, ~17 KB", times twelve models, is where the ~210 KB artifact comes from.

    Per-model is therefore the default. K solves of a 64×64 system is microseconds,
    so the shared-A shortcut buys nothing measurable and costs correctness exactly
    where the system needs it most. `shared_gram=True` reproduces §8.3 as written so
    the cost of the shortcut can be measured rather than asserted.
    """

    def __init__(
        self,
        d: int,
        n_models: int,
        lam: float = 1.0,
        gamma: float = 1.0,
        shared_gram: bool = False,
    ):
        self.d = d
        self.lam = lam
        self.gamma = gamma
        self.shared_gram = shared_gram
        self.A = lam * np.eye(d)                                    # shared / pooled
        self.A_m = np.stack([lam * np.eye(d) for _ in range(n_models)])
        self.B = np.zeros((d, n_models))
        self._W: np.ndarray | None = None
        self._Ainv: np.ndarray | None = None
        self._Ainv_m: np.ndarray | None = None

    def _gram(self, model: int) -> np.ndarray:
        return self.A if self.shared_gram else self.A_m[model]

    def add_model(self) -> None:
        """A new model is one more column of B and one more Gram matrix.

        Under §8.3 that is one column and nothing else, which is the hot-swappable
        pool the document advertises. Per-model costs a 64×64 matrix — 32 KB — and
        is what makes the new column's uncertainty honest.
        """
        self.B = np.hstack([self.B, np.zeros((self.d, 1))])
        self.A_m = np.concatenate([self.A_m, (self.lam * np.eye(self.d))[None]], axis=0)
        self._W = None
        self._Ainv_m = None

    def _decay(self, factor: float, models: list[int]) -> None:
        """Age the state, keeping the ridge floor intact.

        Naively scaling A by γ decays the λI term too, and over a long replay that is
        fatal: γ=0.9 across a 400-item block is 0.9⁴⁰⁰ ≈ 1e-18, so A collapses to the
        zero matrix and the solve raises `Singular matrix`. Discounted RLS is defined
        with the regulariser held out of the discount —

            A ← γ(A − λI) + λI + xxᵀ

        — so the evidence ages while the floor stays put and the system stays
        invertible no matter how aggressive γ is. Only the evidence should ever be
        forgotten; the prior is not an observation.
        """
        floor = self.lam * np.eye(self.d)
        self.A = (self.A - floor) * factor + floor
        self.B *= factor
        for j in models:
            self.A_m[j] = (self.A_m[j] - floor) * factor + floor

    def _decay_block(self, n_block: int, per_model_counts: dict[int, int]) -> None:
        floor = self.lam * np.eye(self.d)
        self.A = (self.A - floor) * (self.gamma ** n_block) + floor
        self.B *= self.gamma ** n_block
        for j, n in per_model_counts.items():
            self.A_m[j] = (self.A_m[j] - floor) * (self.gamma ** n) + floor

    def update(self, x: np.ndarray, model: int, y: float, gram: bool = True) -> None:
        """Rank-one update, O(d²) ≈ 4,000 flops at d = 64 — §8.4.

        `gram=False` credits the target column without touching A. That switch
        exists because §8.3 and §8.4 use different conventions and the difference
        is a factor of K: §8.3 builds A from one row per *query* ("A depends only on
        the queries, not on which model answered them"), while §8.4's streaming form
        adds x·xᵀ per *cell*. Stream K cells for the same query under §8.4 and A
        carries that query K times while each b_m carries it once, which shrinks
        every w_m by roughly K and silently re-weights the cost term against
        quality. The §8.3 convention is the one where a single inverse serves every
        model exactly, so it is the convention used throughout: A sees each query
        once, whoever answered it.
        """
        if self.gamma < 1.0:
            self._decay(self.gamma, [model])
        if gram:
            outer = np.outer(x, x)
            self.A += outer
            self.A_m[model] += outer
        self.B[:, model] += y * x
        self._W = None
        self._Ainv = None
        self._Ainv_m = None

    def absorb(
        self,
        X: np.ndarray,
        Y: np.ndarray,
        observed: np.ndarray,
        models: list[int] | None = None,
    ) -> None:
        """Absorb a block of items with every cell that was graded for them.

        This is how a rolling label matrix actually arrives — a day's items, each
        with the outcomes of whichever models were run on it — and it is the update
        that keeps A on the §8.3 convention: one x·xᵀ per item, one y·x per observed
        cell.

        Within a block the rows are treated as simultaneous — they arrived together,
        so none is older than another — but the block as a whole ages by γⁿ, which
        keeps γ's effective window measured in observations as §8.4 defines it.
        """
        if len(X) == 0:
            return
        cols = list(models) if models is not None else list(range(Y.shape[1]))

        if self.gamma < 1.0:
            # γ's window is defined in observations, not in blocks: §8.4 reads
            # "γ ~ 0.999 gives an effective window of about 1/(1-γ) recent
            # observations". A block of n items must therefore age by γⁿ, otherwise γ
            # silently means "per evaluation round" and its effective window depends
            # on how the stream happens to be batched — 0.999 per week over a
            # six-month replay would forget almost nothing at all.
            #
            # Only the columns this block touches age. A model that was not run this
            # round has not gone stale by sitting still — its evidence is as old as it
            # was, and decaying it anyway would punish the pool for the sampling plan
            # rather than for drift.
            counts = {j: int(observed[:, i].sum()) for i, j in enumerate(cols)}
            n_block = int(observed.any(axis=1).sum())
            self._decay_block(n_block, counts)

        any_obs = observed.any(axis=1)
        if any_obs.any():
            Xg = X[any_obs]
            self.A += Xg.T @ Xg

        for local_j, j in enumerate(cols):
            mask = observed[:, local_j]
            if mask.any():
                Xj = X[mask]
                self.B[:, j] += Xj.T @ Y[mask, local_j]
                self.A_m[j] += Xj.T @ Xj

        self._W = None
        self._Ainv = None
        self._Ainv_m = None

    @property
    def W(self) -> np.ndarray:
        """(d, n_models) fitted weights.

        Under §8.3 this is one factorisation for the whole pool. Per-model it is K
        solves of a 64×64 system, which numpy batches into a single call.
        """
        if self._W is None:
            if self.shared_gram:
                self._W = np.linalg.solve(self.A, self.B)
            else:
                # solve(A_m, b_m) for every m at once: (K,d,d) against (K,d,1).
                self._W = np.linalg.solve(self.A_m, self.B.T[:, :, None])[:, :, 0].T
        return self._W

    @property
    def Ainv(self) -> np.ndarray:
        if self._Ainv is None:
            self._Ainv = np.linalg.inv(self.A)
        return self._Ainv

    @property
    def Ainv_m(self) -> np.ndarray:
        if self._Ainv_m is None:
            self._Ainv_m = np.linalg.inv(self.A_m)
        return self._Ainv_m

    def predict(self, X: np.ndarray) -> np.ndarray:
        """(n, n_models) predictions — one matmul."""
        return X @ self.W

    def sigma(self, X: np.ndarray) -> np.ndarray:
        """Predictive standard deviation — §8.5.

        Per-model: σ_m(x) = sqrt(xᵀA_m⁻¹x), exactly as §8.5 writes it, which is what
        makes cold start, drift detection and exploration one mechanism instead of
        three. A model with little history has a nearly uninformative A_m, so its σ
        is large, so it gets tried on queries where it might win — and σ shrinks on
        its own as evidence arrives, with nothing to schedule.

        Shared: one σ for every model, so exploration cannot distinguish between
        them. `count_bonus` in `RouterConfig` is the crutch that gets bolted on when
        the shortcut is taken, and comparing the two is the point of the switch.
        """
        if self.shared_gram:
            s = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", X, self.Ainv, X), 0.0))
            return np.repeat(s[:, None], self.B.shape[1], axis=1)
        # (n, K): quadratic form against each model's own inverse.
        quad = np.einsum("nd,kde,ne->nk", X, self.Ainv_m, X)
        return np.sqrt(np.maximum(quad, 0.0))

    def seed_prior(self, model: int, A_prior: np.ndarray, b_prior: np.ndarray) -> None:
        """Install a cold-start prior on one column without disturbing the others.

        The prior lands on that model's own Gram matrix and target column and
        nowhere else — a new model's prior should inform its own estimate, not
        re-weight what the pool already knows. Under `shared_gram` there is no such
        separation available, which is another way of saying the same thing.
        """
        self.B[:, model] += b_prior
        self.A_m[model] += A_prior
        if self.shared_gram:
            self.A += A_prior
        self._W = None
        self._Ainv = None
        self._Ainv_m = None


# ------------------------------------------------------------------- routers --
@dataclass
class PoolState:
    """The live-read lane (§4.1): what is true at decision time, never fitted.

    Read fresh from a table on every decision, which is what makes FR-16 (a price
    change reaching decisions in minutes) a property of the architecture rather
    than of a retraining schedule.
    """

    price_in: np.ndarray                   # (n_models,) USD per 1M
    price_out: np.ndarray                  # (n_models,) USD per 1M
    available: np.ndarray | None = None    # (n_models,) bool
    p95_ms: np.ndarray | None = None       # (n_models,) float
    context_limit: np.ndarray | None = None

    def n_models(self) -> int:
        return len(self.price_in)


@dataclass
class RouterConfig:
    lam: float = 1.0
    alpha: float = 0.35                # exploration weight on σ
    lam_cost: float = 0.05             # λ_c in §8.7; calibrated, see metrics.UtilityWeights
    lam_latency: float = 0.0           # λ_l
    gamma: float = 1.0                 # shared decay (baseline)
    gamma_quality: float = 1.0         # γ_q (decomposed)
    gamma_tokens: float = 1.0          # γ_t (decomposed)
    count_bonus: float = 0.0           # crutch for shared_gram; see _RidgeLane.sigma
    tokens_in_default: float = 800.0
    shared_gram: bool = False          # True reproduces §8.3 as written
    # The Best Single model, whose predicted cost is c_ref (§8.7). Set on the control
    # plane's clock, not per request — it is a normalisation constant, not a decision.
    ref_model: int | None = None


@dataclass
class Decision:
    """One routing decision, fully explainable after the fact (NFR-12)."""

    choice: np.ndarray                 # (n,) chosen column per item
    utility: np.ndarray                # (n, n_models)
    q_hat: np.ndarray
    sigma: np.ndarray
    cost_hat: np.ndarray
    tokens_hat: np.ndarray


class RidgeLinUCBRouter:
    """RollingBench §8 as written: one shared γ over the whole state.

    Parameters
    ----------
    d : int
        Feature dimension from `FeatureMap.dim`.
    n_models : int
        Pool size. Grows via `add_model`.
    """

    name = "shared-gamma (RollingBench §8)"

    def __init__(self, d: int, n_models: int, config: RouterConfig | None = None):
        self.cfg = config or RouterConfig()
        self.d = d
        self.n_models = n_models
        # Baseline: one γ, both targets riding it.
        self.quality = _RidgeLane(d, n_models, self.cfg.lam, self.cfg.gamma,
                                  shared_gram=self.cfg.shared_gram)
        self.tokens = _RidgeLane(d, n_models, self.cfg.lam, self.cfg.gamma,
                                 shared_gram=self.cfg.shared_gram)
        self.counts = np.zeros(n_models)

    # ---------------------------------------------------------------- growth --
    def add_model(self) -> int:
        self.quality.add_model()
        self.tokens.add_model()
        self.counts = np.append(self.counts, 0.0)
        self.n_models += 1
        return self.n_models - 1

    # ----------------------------------------------------------------- fitting --
    def fit(
        self,
        X: np.ndarray,
        quality: np.ndarray,
        observed: np.ndarray,
        tokens_out: np.ndarray | None = None,
        models: list[int] | None = None,
    ) -> "RidgeLinUCBRouter":
        """One pass over a label matrix — the reference `fit` from §15.1.

        Identical arithmetic to streaming the same observations through `absorb`,
        which is the property that makes "there is no retraining job, only a stream
        of rank-one updates" true rather than aspirational. `tests/test_router.py`
        asserts the two agree.
        """
        self.absorb(X, quality, observed, tokens_out, models=models)
        return self

    def absorb(
        self,
        X: np.ndarray,
        quality: np.ndarray,
        observed: np.ndarray,
        tokens_out: np.ndarray | None = None,
        models: list[int] | None = None,
    ) -> None:
        """Absorb a block of graded items into both lanes (§8.4)."""
        self.quality.absorb(X, quality, observed, models=models)
        if tokens_out is not None:
            self.tokens.absorb(X, tokens_out, observed, models=models)
        cols = models if models is not None else range(quality.shape[1])
        for local_j, j in enumerate(cols):
            self.counts[j] += int(observed[:, local_j].sum())

    def observe(
        self,
        x: np.ndarray,
        model: int,
        quality: float,
        tokens_out: float | None = None,
        gram: bool = True,
    ) -> None:
        """Absorb one graded outcome. No retraining job (FR-14).

        `gram=False` when several models' outcomes for the *same* query are streamed
        in sequence and A has already seen that query — see `_RidgeLane.update`.
        """
        self.quality.update(x, model, quality, gram=gram)
        if tokens_out is not None:
            self.tokens.update(x, model, tokens_out, gram=gram)
        self.counts[model] += 1

    # ---------------------------------------------------------------- serving --
    def _sigma(self, X: np.ndarray) -> np.ndarray:
        """(n, n_models) predictive standard deviation.

        Per-model this is σ from §8.5 and needs nothing added. Under `shared_gram`
        every model gets the same σ, so `count_bonus / sqrt(1 + n_m)` restores the
        one thing the shortcut throws away — that an under-observed model should look
        uncertain rather than bad.
        """
        s = self.quality.sigma(X)
        if self.cfg.count_bonus:
            s = s + self.cfg.count_bonus / np.sqrt(1.0 + self.counts)[None, :]
        return s

    def decide(
        self,
        X: np.ndarray,
        pool: PoolState,
        tokens_in: np.ndarray | float | None = None,
        allowed: np.ndarray | None = None,
    ) -> Decision:
        """The decision rule of §8.7.

            U_m = q̂_m(x) + α·σ_m(x) − λ_c·ĉ_m/c_ref − λ_l·l̂_m/l_ref

        Price is read from `pool`, never learned. Quality and expected output
        tokens are the only fitted quantities.
        """
        n = X.shape[0]
        q_hat = self.quality.predict(X)
        sigma = self._sigma(X)
        tokens_hat = np.maximum(self.tokens.predict(X), 1.0)

        if tokens_in is None:
            tokens_in = self.cfg.tokens_in_default
        tokens_in_arr = np.full(n, tokens_in) if np.isscalar(tokens_in) else np.asarray(tokens_in)

        cost_hat = (
            tokens_hat * pool.price_out[None, :] / 1e6
            + tokens_in_arr[:, None] * pool.price_in[None, :] / 1e6
        )
        # c_ref is the Best Single model's predicted cost for this item (§8.7), per
        # item so λ_c means the same thing for a one-line prompt and a long one. Note
        # that c_ref is computed from the *live* price too, which is what makes a
        # price cut on the reference model re-rank the whole pool immediately.
        if self.cfg.ref_model is not None and self.cfg.ref_model < cost_hat.shape[1]:
            cost_ref = np.maximum(cost_hat[:, [self.cfg.ref_model]], 1e-12)
        else:
            cost_ref = np.maximum(cost_hat.mean(axis=1, keepdims=True), 1e-12)

        utility = q_hat + self.cfg.alpha * sigma - self.cfg.lam_cost * (cost_hat / cost_ref)

        if pool.p95_ms is not None and self.cfg.lam_latency:
            lat = np.repeat(pool.p95_ms[None, :], n, axis=0)
            utility = utility - self.cfg.lam_latency * (lat / max(pool.p95_ms.mean(), 1e-9))

        # Hard filters run before the argmax (FR-21), so a filtered model can never
        # win on utility.
        mask = np.ones((n, self.n_models), dtype=bool)
        if pool.available is not None:
            mask &= pool.available[None, :]
        if allowed is not None:
            mask &= allowed if allowed.ndim == 2 else allowed[None, :]
        utility = np.where(mask, utility, -np.inf)

        choice = np.argmax(utility, axis=1)
        return Decision(choice, utility, q_hat, sigma, cost_hat, tokens_hat)

    # --------------------------------------------------------------- artifact --
    def artifact_bytes(self, dtype_bytes: int = 4) -> int:
        """Size of the published policy — §8.9 claims ~210 KB at d=64, K=12.

        Counted at float32, which is what §8.9's "~17 KB per model" implies (a 64×64
        float64 matrix is 32 KB on its own) and is ample for weights whose inputs are
        unit-variance features. Only what a gateway needs to run the policy is
        counted: Gram matrices, target columns, and the observation counts.

        A note on §8.9's budget, because it interacts with Contribution 1. "State per
        model: A 64×64, plus 3 target vectors, ~17 KB" describes *one* Gram matrix per
        model serving three targets — quality, tokens, latency — which is sound, since
        A depends only on x and not on which target is being predicted. Twelve of those
        is the ~210 KB figure. But per-component decay means the quality and token
        lanes age at different rates, and two differently-decayed Gram matrices are not
        the same matrix, so they cannot be shared. Giving each target its own γ
        therefore doubles the Gram state: 358 KB here at d=64, K=11, against 180 KB if
        the lanes shared one. Still far inside NFR-4's 5 MB, but it is a real cost of
        the decomposition and §8.9's budget quietly assumes it is not paid.
        """
        if self.cfg.shared_gram:
            gram_elems = 2 * self.d * self.d
        else:
            gram_elems = 2 * self.n_models * self.d * self.d
        target_elems = 2 * self.d * self.n_models + self.n_models
        return int((gram_elems + target_elems) * dtype_bytes)

    def state(self) -> dict:
        return {
            "kind": type(self).__name__,
            "quality_A": self.quality.A,
            "quality_B": self.quality.B,
            "tokens_A": self.tokens.A,
            "tokens_B": self.tokens.B,
            "counts": self.counts,
            "config": vars(self.cfg),
        }


class DecomposedRouter(RidgeLinUCBRouter):
    """Contribution 1 (§4): per-target decay, and a live-read lane that is never fitted.

    The only structural difference from the baseline is that the two lanes carry
    their own γ. That is enough to break the trade-off §4.4 describes — a decay
    fast enough to unlearn stale token behaviour no longer forces the quality
    estimate to be noisy, because they are no longer the same number.

    Cost and latency were already read live in RollingBench §8.7 for price
    specifically; here that is the stated rule for every component that qualifies
    (§4.2), so nothing observable at decision time enters A or B.
    """

    name = "decomposed (γ_q, γ_t + live-read)"

    def __init__(self, d: int, n_models: int, config: RouterConfig | None = None):
        super().__init__(d, n_models, config)
        self.quality = _RidgeLane(d, n_models, self.cfg.lam, self.cfg.gamma_quality,
                                  shared_gram=self.cfg.shared_gram)
        self.tokens = _RidgeLane(d, n_models, self.cfg.lam, self.cfg.gamma_tokens,
                                 shared_gram=self.cfg.shared_gram)


class OracleRouter:
    """The ceiling: always picks the best available cell. Not achievable live."""

    name = "oracle"

    def decide_from_utility(self, utility: np.ndarray) -> np.ndarray:
        return np.argmax(utility, axis=1)


class BestSingleRouter:
    """The baseline any router must beat: one model, everything to it."""

    name = "best-single"

    def __init__(self, column: int):
        self.column = column

    def decide(self, n: int) -> np.ndarray:
        return np.full(n, self.column)


class RandomRouter:
    """A control. Included because "beats random" is a weaker claim than it sounds
    and reporting it makes the gap to Best Single legible."""

    name = "random"

    def __init__(self, n_models: int, seed: int = 0):
        self.n_models = n_models
        self.rng = np.random.default_rng(seed)

    def decide(self, n: int) -> np.ndarray:
        return self.rng.integers(0, self.n_models, size=n)
