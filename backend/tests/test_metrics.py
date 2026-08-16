"""Tests for the scoring rule. These encode the two degeneracies notebook 05 reports."""

from __future__ import annotations

import numpy as np

from rollingbench.metrics import (
    UtilityWeights,
    best_single_column,
    calibrate_kappa,
    feasible_score_batch,
    group_oracle_column,
    per_cell_utility,
    reference_column,
    score_batch,
    shrink_scores,
)


def test_score_endpoints():
    """§8.8's scale: 1.0 is oracle-equivalent, 0.0 is no better than one good model."""
    rng = np.random.default_rng(0)
    u = rng.random((300, 4))
    base = best_single_column(u)

    oracle = score_batch(u, u.argmax(axis=1), base_col=base)
    assert abs(oracle.score - 1.0) < 1e-6
    assert abs(oracle.regret) < 1e-6

    baseline = score_batch(u, np.full(300, base), base_col=base)
    # Not exactly zero: §8.8 adds eps to the denominator to keep it finite, so the
    # endpoint is approached rather than reached.
    assert abs(baseline.score) < 1e-4
    assert abs(baseline.regret - 1.0) < 1e-4


def test_harder_batch_leaves_score_unchanged():
    """Architectural Rule 3: a harder batch lowers oracle and baseline together.

    This is the property a rolling benchmark needs. Shifting every cell down by a
    constant makes the batch uniformly harder without changing which model is best
    anywhere, so a policy's score must not move.
    """
    rng = np.random.default_rng(1)
    u = rng.random((400, 5))
    choices = rng.integers(0, 5, 400)
    easy = score_batch(u, choices, base_col=best_single_column(u))
    hard = score_batch(u - 0.3, choices, base_col=best_single_column(u - 0.3))
    assert abs(easy.score - hard.score) < 1e-9


def test_score_degenerates_when_one_model_dominates():
    """Contribution 3's premise — with its diagnosis corrected.

    §6 says the denominator collapses "when a challenge batch happens to be easy — every
    model in the pool performs about the same on it". On binary-graded data the opposite
    holds, and it is measurable: when models perform about the same, per-item luck lets
    the oracle beat any single model by a wide margin, so U_oracle − U_base is *large*.
    The denominator collapses when one model **dominates**, because then the best single
    model is already almost as good as the per-item oracle.

    On RouterBench, batch information correlates −0.54 with the spread between the best
    and worst model. The fix still works — it keys on measured information, not on the
    reason — but the diagnosis matters: an operator who believed §6 might try to help by
    filtering out easy items, which would make it worse.
    """
    rng = np.random.default_rng(2)
    # One model pulls further ahead of the rest as `spread` grows, while the per-item
    # noise stays fixed. Scaling signal and noise together would prove nothing — the score
    # is a ratio, so a uniform rescaling cancels.
    offsets = np.array([0.0, 1.0, 2.0, 3.0])
    sds, infos = [], []
    for spread in (0.005, 0.02, 0.1, 1.0):
        scores, batch_infos = [], []
        for _ in range(300):
            u = spread * offsets[None, :] + 0.05 * rng.random((50, 4))
            base = best_single_column(u)
            s = score_batch(u, rng.integers(0, 4, 50), base_col=base, clip=False)
            scores.append(s.score)
            batch_infos.append(s.info)
        sds.append(float(np.std(scores)))
        infos.append(float(np.mean(batch_infos)))

    # More dominance → less information → a score dominated by noise.
    assert infos[-1] < infos[0]
    assert sds[-1] > 100 * sds[0]


def test_shrinkage_is_causal():
    """The running average must be built from earlier batches only.

    If it peeked at the batch it is correcting, the fix would look better than it is —
    and the improvement reported in notebook 05 would be an artefact.
    """
    raw = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
    infos = np.full(5, 0.001)                  # weight ≈ 0: shrink almost entirely
    out = shrink_scores(raw, infos, kappa=1.0)
    # The first batch has no history, so it can only shrink toward itself.
    assert abs(out["score"][0] - raw[0]) < 1e-9
    # Later batches are pulled toward the earlier level, not toward their own value.
    assert out["score"][1] > 0.5


def test_shrinkage_leaves_informative_batches_alone():
    """weight → 1 when a batch is informative relative to κ."""
    raw = np.array([0.2, 0.9, 0.4, 0.8])
    out = shrink_scores(raw, infos=np.full(4, 100.0), kappa=0.01)
    np.testing.assert_allclose(out["score"], raw, atol=1e-3)
    assert out["weight"].min() > 0.999


def test_group_oracle_is_attainable_and_below_item_oracle():
    """The second degeneracy: the per-item oracle exceeds anything a policy can reach."""
    rng = np.random.default_rng(3)
    # Two groups, and within a group the best model is fixed — so a per-group assignment
    # is attainable, while per-item argmax also banks the noise.
    # The group-level advantage has to be smaller than the per-item noise, or the
    # per-item argmax always lands on the group's best model and the two oracles
    # coincide. Real grading is exactly this regime: a reliable average difference
    # between models, swamped item by item.
    u = np.zeros((400, 3))
    groups = np.array(["a"] * 200 + ["b"] * 200)
    u[:200, 0] = 0.12
    u[200:, 1] = 0.12
    u += 0.5 * rng.random((400, 3))

    item_oracle = u.max(axis=1).mean()
    group_choices = group_oracle_column(u, groups)
    group_oracle = u[np.arange(400), group_choices].mean()
    assert group_oracle < item_oracle
    # And the group oracle must pick the right model in each group.
    assert group_choices[0] == 0 and group_choices[-1] == 1


def test_feasible_score_can_exceed_one():
    """A per-item policy may beat the best per-group assignment; that is information."""
    rng = np.random.default_rng(4)
    u = rng.random((300, 3))
    groups = np.array(["g"] * 300)
    s = feasible_score_batch(u, u.argmax(axis=1), groups)
    assert s.score > 1.0


def test_pool_mean_normalisation_hides_a_dominant_model_price_cut():
    """Why c_ref is a fixed model rather than the pool mean.

    A model that dominates the pool's mean cost has a nearly price-invariant cost ratio
    under mean normalisation: cut its price and the mean falls with it, so cost_m / mean
    barely moves. Against a fixed reference the same cut shows up in full. This is the
    mechanism behind the null price-shock result that came out of the first run of §7.1,
    before the normalisation was corrected.
    """
    # Model 0 dominates the pool's cost; the reference is one of the cheap models.
    cost = np.tile(np.array([1.0, 0.01, 0.01, 0.01, 0.01]), (100, 1))
    cut = cost.copy()
    cut[:, 0] *= 0.2                                  # an 80% price cut
    ref = 1

    def ratio(c, **kw):
        # The cost term for model 0, normalised two different ways.
        return (per_cell_utility(np.zeros_like(c), c, UtilityWeights(lam_cost=1.0), **kw)
                * -1)[:, 0].mean()

    fixed_change = 1 - ratio(cut, ref_col=ref) / ratio(cost, ref_col=ref)
    mean_change = 1 - ratio(cut) / ratio(cost)

    # Against a fixed reference the ratio falls by the full 80%; against the pool mean
    # it barely registers.
    assert fixed_change > 0.75
    assert mean_change < 0.2


def test_calibrate_kappa_tracks_the_information_distribution():
    infos = np.concatenate([np.full(50, 0.01), np.full(50, 1.0)])
    assert 0.005 < calibrate_kappa(infos, quantile=0.25) < 0.05
    assert calibrate_kappa(np.zeros(10)) > 0
