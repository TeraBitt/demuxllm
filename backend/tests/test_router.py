"""Tests for the estimator. These are the properties the claims depend on.

Not coverage for its own sake: each test here corresponds to something a notebook
asserts about the router, so if one breaks a stated result is wrong.
"""

from __future__ import annotations

import numpy as np
import pytest

from rollingbench.metrics import (
    UtilityWeights,
    best_single_column,
    calibrate_kappa,
    feasible_score_batch,
    per_cell_utility,
    reference_column,
    score_batch,
    shrink_scores,
)
from rollingbench.router import (
    DecomposedRouter,
    PoolState,
    RidgeLinUCBRouter,
    RouterConfig,
)


@pytest.fixture
def synthetic():
    """A small pool where the right answer is known by construction.

    Three models: one strong-and-dear, one weak-and-cheap, one that is good only on
    items whose first feature is positive. A router that cannot find that third model's
    speciality is not routing.
    """
    rng = np.random.default_rng(0)
    n, d, K = 1200, 8, 3
    X = rng.standard_normal((n, d))
    X[:, -1] = 1.0                                    # bias column
    specialist = (X[:, 0] > 0).astype(float)
    quality = np.column_stack([
        0.8 + 0.05 * rng.standard_normal(n),          # strong, flat
        0.4 + 0.05 * rng.standard_normal(n),          # weak, flat
        0.3 + 0.6 * specialist + 0.05 * rng.standard_normal(n),
    ]).clip(0, 1)
    cost = np.column_stack([
        np.full(n, 0.01), np.full(n, 0.0005), np.full(n, 0.001),
    ])
    observed = np.ones((n, K), dtype=bool)
    tokens = np.full((n, K), 500.0)
    pool = PoolState(price_in=np.array([10.0, 0.2, 0.5]),
                     price_out=np.array([30.0, 0.2, 1.0]))
    return X, quality, cost, observed, tokens, pool, specialist


def test_fit_equals_streamed_updates(synthetic):
    """§8.4's claim that there is no retraining job, only rank-one updates.

    Fitting in one pass and absorbing the same rows in blocks must land on the same
    state, or "the router absorbs a new observation in microseconds rather than waiting
    for a nightly retrain" is not true of this implementation.
    """
    X, q, c, obs, tok, pool, _ = synthetic
    batch = RidgeLinUCBRouter(X.shape[1], 3).fit(X, q, obs, tok)

    streamed = RidgeLinUCBRouter(X.shape[1], 3)
    for lo in range(0, len(X), 100):
        hi = lo + 100
        streamed.absorb(X[lo:hi], q[lo:hi], obs[lo:hi], tok[lo:hi])

    np.testing.assert_allclose(batch.quality.A_m, streamed.quality.A_m, rtol=1e-10)
    np.testing.assert_allclose(batch.quality.B, streamed.quality.B, rtol=1e-10)
    np.testing.assert_allclose(batch.quality.W, streamed.quality.W, rtol=1e-9)


def test_finds_the_specialist(synthetic):
    """The router must route the specialist's items to the specialist."""
    X, q, c, obs, tok, pool, specialist = synthetic
    r = RidgeLinUCBRouter(X.shape[1], 3, RouterConfig(alpha=0.0, lam_cost=0.05, ref_model=0))
    r.fit(X, q, obs, tok)
    q_hat = r.quality.predict(X)
    # On its own items the specialist should be predicted best of the two cheap models.
    on = specialist > 0.5
    assert (q_hat[on, 2] > q_hat[on, 1]).mean() > 0.9
    assert (q_hat[~on, 2] < q_hat[~on, 0]).mean() > 0.9


def test_adding_a_model_preserves_existing_columns(synthetic):
    """§8.3's hot-swappable pool: a new model must not disturb what is already known."""
    X, q, c, obs, tok, pool, _ = synthetic
    r = RidgeLinUCBRouter(X.shape[1], 3).fit(X, q, obs, tok)
    before = r.quality.W.copy()
    j = r.add_model()
    assert j == 3
    np.testing.assert_allclose(r.quality.W[:, :3], before, rtol=1e-12)


def test_new_model_has_high_sigma(synthetic):
    """§8.5: a newly added model has a nearly uninformative A, so its σ is large.

    This is the property that makes cold start, drift and exploration one mechanism, and
    it is exactly what the shared-Gram shortcut destroys.
    """
    X, q, c, obs, tok, pool, _ = synthetic
    r = RidgeLinUCBRouter(X.shape[1], 3).fit(X, q, obs, tok)
    r.add_model()
    sigma = r.quality.sigma(X[:50])
    assert sigma[:, 3].mean() > 20 * sigma[:, 0].mean()


def test_shared_gram_underpredicts_thin_coverage(synthetic):
    """The finding in notebooks 03 and 06, as a regression test.

    With a shared Gram matrix, a model observed on a fraction of items is under-predicted
    by roughly (1 − coverage). With per-model matrices it is not.
    """
    X, q, c, obs, tok, pool, _ = synthetic
    thin = obs.copy()
    thin[200:, 0] = False                             # model 0 covered on 1/6 of items

    shared = RidgeLinUCBRouter(X.shape[1], 3, RouterConfig(shared_gram=True))
    shared.fit(X, q, thin, tok)
    per_model = RidgeLinUCBRouter(X.shape[1], 3, RouterConfig(shared_gram=False))
    per_model.fit(X, q, thin, tok)

    truth = q[:, 0].mean()
    assert shared.quality.predict(X)[:, 0].mean() < 0.5 * truth
    assert abs(per_model.quality.predict(X)[:, 0].mean() - truth) < 0.1 * truth


def test_gram_stays_invertible_under_aggressive_decay(synthetic):
    """γ must never decay the ridge floor, or a long replay ends in a singular solve."""
    X, q, c, obs, tok, pool, _ = synthetic
    r = RidgeLinUCBRouter(X.shape[1], 3, RouterConfig(gamma=0.5))
    for lo in range(0, len(X), 100):
        r.absorb(X[lo:lo + 100], q[lo:lo + 100], obs[lo:lo + 100], tok[lo:lo + 100])
    assert np.all(np.linalg.eigvalsh(r.quality.A_m[0]) > 0)
    assert np.isfinite(r.quality.W).all()


def test_price_read_live_changes_decisions_without_refitting(synthetic):
    """FR-16: a price change reaches decisions with no retraining and no redeploy.

    The shocked models are deliberately not the reference model whose cost is c_ref.
    Shocking the numeraire moves every ratio in the pool together and the effect largely
    cancels — the same trap the §7.1 shock schedule avoids, and worth encoding here so a
    future change to the normalisation cannot quietly pass this test by breaking it.
    """
    X, q, c, obs, tok, pool, _ = synthetic
    r = RidgeLinUCBRouter(X.shape[1], 3, RouterConfig(alpha=0.0, lam_cost=0.3, ref_model=0))
    r.fit(X, q, obs, tok)
    before = r.decide(X, pool).choice

    dearer = PoolState(price_in=pool.price_in.copy(), price_out=pool.price_out.copy())
    dearer.price_out[1:] *= 60.0                      # the cheap models stop being cheap
    dearer.price_in[1:] *= 60.0
    after = r.decide(X, dearer).choice

    # No refit happened between the two calls: the weights are byte-identical and only
    # the price table changed.
    assert (before != after).mean() > 0.2
    assert (after == 0).mean() > (before == 0).mean() + 0.2


def test_hard_filters_beat_utility(synthetic):
    """FR-21: filters run before the argmax, so a filtered model can never win."""
    X, q, c, obs, tok, pool, _ = synthetic
    r = RidgeLinUCBRouter(X.shape[1], 3, RouterConfig(alpha=0.0, lam_cost=0.0))
    r.fit(X, q, obs, tok)
    blocked = PoolState(price_in=pool.price_in, price_out=pool.price_out,
                        available=np.array([False, True, True]))
    assert not (r.decide(X, blocked).choice == 0).any()


def test_decomposed_matches_baseline_when_gammas_equal(synthetic):
    """The decomposition must be a strict generalisation, not a different estimator.

    With γ_q = γ_t = γ the two must agree exactly; otherwise a difference measured in
    notebook 06 could be an implementation artefact rather than the decomposition.
    """
    X, q, c, obs, tok, pool, _ = synthetic
    base = RidgeLinUCBRouter(X.shape[1], 3, RouterConfig(gamma=0.99))
    dec = DecomposedRouter(X.shape[1], 3,
                           RouterConfig(gamma_quality=0.99, gamma_tokens=0.99))
    for lo in range(0, len(X), 150):
        sl = slice(lo, lo + 150)
        base.absorb(X[sl], q[sl], obs[sl], tok[sl])
        dec.absorb(X[sl], q[sl], obs[sl], tok[sl])
    np.testing.assert_allclose(base.quality.W, dec.quality.W, rtol=1e-12)
    np.testing.assert_allclose(base.tokens.W, dec.tokens.W, rtol=1e-12)


def test_artifact_within_nfr4(synthetic):
    """NFR-4: a policy artifact must not exceed 5 MB."""
    r = RidgeLinUCBRouter(64, 12)
    assert r.artifact_bytes() < 5 * 1024 * 1024
    shared = RidgeLinUCBRouter(64, 12, RouterConfig(shared_gram=True))
    assert shared.artifact_bytes() < r.artifact_bytes()


def test_serving_latency_budget(synthetic):
    """NFR-1: routing overhead under 50 ms p95, excluding provider time.

    The embedding call dominates in production (§8.9 puts it at ~6 ms); what is measured
    here is the part this code is responsible for.
    """
    import time

    X, q, c, obs, tok, pool, _ = synthetic
    r = RidgeLinUCBRouter(X.shape[1], 3).fit(X, q, obs, tok)
    r.decide(X[:1], pool)                             # warm the lazy solve
    times = []
    for i in range(200):
        t0 = time.perf_counter()
        r.decide(X[i:i + 1], pool)
        times.append((time.perf_counter() - t0) * 1000)
    assert float(np.percentile(times, 95)) < 50.0
