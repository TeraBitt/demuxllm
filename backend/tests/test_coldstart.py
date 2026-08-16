"""Tests for IRT, low-rank completion, and the cold-start priors."""

from __future__ import annotations

import numpy as np

from rollingbench.coldstart import (
    fit_ability,
    fit_irt,
    fit_lowrank,
    fit_new_column,
    predicted_probe_count,
    select_probe_items,
)


def _irt_data(n_items=600, n_models=8, seed=0):
    """Outcomes generated from a known 2PL, so the fit has a truth to recover."""
    rng = np.random.default_rng(seed)
    difficulty = rng.normal(0, 1.2, n_items)
    ability = np.linspace(-2, 2, n_models)
    z = ability[None, :] - difficulty[:, None]
    p = 1 / (1 + np.exp(-z))
    return (rng.random((n_items, n_models)) < p).astype(float), difficulty, ability


def test_irt_recovers_ability_ordering():
    """Item difficulties are estimated once and held fixed, so ability must be recoverable."""
    y, difficulty, ability = _irt_data()
    obs = np.ones_like(y, dtype=bool)
    m = fit_irt(y, obs, n_iter=12)
    # Ordering matters more than the scale, which is only identified up to a shift.
    assert np.corrcoef(m.ability, ability)[0, 1] > 0.95
    assert np.corrcoef(m.difficulty, difficulty)[0, 1] > 0.7


def test_ability_from_a_few_hundred_items():
    """§8.6's claim that 200–300 items suffice for a usable ability estimate."""
    y, difficulty, ability = _irt_data(n_items=1200, n_models=9)
    obs = np.ones_like(y, dtype=bool)
    # Fit item parameters on everything except the model being onboarded.
    m = fit_irt(y[:, :-1], obs[:, :-1], n_iter=12)
    rng = np.random.default_rng(1)
    probe = rng.choice(1200, 250, replace=False)
    est = fit_ability(m, probe, y[probe, -1])
    full = fit_ability(m, np.arange(1200), y[:, -1])
    assert abs(est - full) < 0.6


def test_probe_selection_targets_informative_items():
    """Items whose difficulty sits near the ability estimate carry the most information."""
    y, difficulty, ability = _irt_data(n_items=900)
    m = fit_irt(y, np.ones_like(y, dtype=bool), n_iter=8)
    rng = np.random.default_rng(2)
    picked = select_probe_items(m, np.arange(900), ability_estimate=0.0, n=150, rng=rng)
    # Selected items should sit closer to θ = 0 than the corpus does on average.
    assert np.abs(m.difficulty[picked]).mean() < np.abs(m.difficulty).mean()
    assert len(set(picked.tolist())) == 150


def test_lowrank_completes_a_held_out_column():
    """§8.6's low-rank claim: a new model's column is predictable from ~250 cells."""
    rng = np.random.default_rng(3)
    n_items, r = 700, 4
    U = rng.standard_normal((n_items, r))
    V = rng.standard_normal((12, r))
    M = np.clip(0.5 + 0.15 * (U @ V.T), 0, 1)

    known, held = M[:, :11], M[:, 11]
    lr = fit_lowrank(known, np.ones_like(known, dtype=bool), rank=r, n_iter=30)
    probe = rng.choice(n_items, 250, replace=False)
    v = fit_new_column(lr, probe, held[probe])
    pred = lr.predict_column(v)
    # Predicting the unprobed items is the actual claim.
    rest = np.setdiff1d(np.arange(n_items), probe)
    assert np.corrcoef(pred[rest], held[rest])[0, 1] > 0.8


def test_probe_count_falls_as_the_prior_tightens():
    """§5.3's shape: a model the pool explains well needs fewer probe items."""
    tight = predicted_probe_count(tau2=0.01, sigma2=0.1, epsilon=0.01)
    loose = predicted_probe_count(tau2=10.0, sigma2=0.1, epsilon=0.01)
    assert tight < loose
    assert predicted_probe_count(tau2=1e-9, sigma2=0.1, epsilon=0.01) == 0.0
