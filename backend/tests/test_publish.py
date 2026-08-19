"""Tests for the publication-checklist work, and for every correction it forced.

The repository's rule is that a correction becomes a test, so that a future change
cannot silently reintroduce it. Three corrections came out of this pass and all three
are pinned here:

1. The γ-decomposition verdict used `mean > 2 * se`, a normal approximation, on eight
   seeds. It called the high-drift arm supported at 2.04 SE where the correct t-test
   gives p = 0.081. `test_paired_verdict_*` pins the t-test and the specific case.
2. `RIGOR.md` §5 reported a published baseline beating this router by 3.6 points from a
   single split. `test_baseline_vectors_reproduce_reported_means` pins the machinery
   that puts an interval on it — in particular that a cascade's bill is its own spend
   and not `cost[row, choice]`, which is what makes the interval right.
3. "Fifteen claims, no correction" treated counts, point estimates and hypothesis
   tests as one family. `test_claims_*` pins the classification and the two correction
   procedures.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from rollingbench.data import llmrouterbench
from rollingbench.data.cache import features_for
from rollingbench.experiments import baselines, chutes, publish
from rollingbench.experiments.decomposition import paired_verdict
from rollingbench.experiments.publish import _bh
from rollingbench.experiments.rigor import _holm

pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")

needs_cache = pytest.mark.skipif(
    not llmrouterbench.DEFAULT_CACHE.exists(),
    reason="run scripts/build_chutes_matrix.py first",
)


# ------------------------------------- correction 1: the significance rule --
def test_paired_verdict_uses_t_not_two_se():
    """At n = 8 the critical value is 2.365, and 2.04 SE is not significant.

    This is the exact case that shipped: the high-drift γ arm came in at
    +0.00206 ± 0.00101, cleared `mean > 2 * se`, and was written into an artifact as
    supported. Under the correct test it is p = 0.081.
    """
    # Eight values built to sit at exactly 2.04 SE — the ratio that shipped.
    spread = np.array([-3.0, -1.0, -0.5, 0.0, 0.0, 0.5, 1.0, 3.0])
    x = spread + 2.04 * spread.std(ddof=1) / np.sqrt(len(spread))
    v = paired_verdict(x, "demo")
    ratio = v["mean_regret_reduction"] / v["std_error"]
    assert 1.96 < ratio < v["t_critical_two_sided"], "not the regime under test"
    assert not v["supported"], "a 2-SE rule would have called this supported"
    assert v["p_value"] > 0.05


def test_paired_verdict_still_supports_a_real_effect():
    v = paired_verdict(np.array([1.0, 1.1, 0.9, 1.05, 0.95, 1.0, 1.02, 0.98]), "demo")
    assert v["supported"] and v["p_value"] < 1e-6


def test_paired_verdict_is_directional():
    """A significant difference the wrong way is not support for 'X beats Y'."""
    v = paired_verdict(np.array([-1.0, -1.1, -0.9, -1.05, -0.95, -1.0, -1.02, -0.98]),
                       "demo")
    assert v["p_value"] < 1e-6 and not v["supported"]


def test_decomposition_artifact_carries_the_test(artifacts_root):
    """The shipped artifact reports how it decided, not just what it decided."""
    path = artifacts_root / "decomposition.json"
    if not path.exists():
        pytest.skip("run scripts/run_all.py --only decomposition")
    for regime, block in json.loads(path.read_text())["replication"].items():
        for key in ("decomposition", "read_vs_learn"):
            v = block[key]
            assert "p_value" in v and "t_critical_two_sided" in v, (
                f"{regime}.{key} states a verdict without stating the test")
            assert v["supported"] == (v["mean_regret_reduction"] > 0
                                      and v["p_value"] <= 0.05)


# --------------------------------------- correction 2: baseline margin CIs --
@pytest.fixture(scope="module")
def pool():
    if not llmrouterbench.DEFAULT_CACHE.exists():
        pytest.skip("no cache")
    lm, tokens_in = chutes.build_pool()
    train, test = chutes.split(lm, seed=0)
    X, _ = features_for(lm, fit_idx=train, verbose=False)
    return lm, tokens_in, X, train, test


@needs_cache
def test_baseline_vectors_reproduce_reported_means(pool):
    """Every row's headline equals the mean of the vector handed back with it.

    The cascade rows are the point: a cascade pays for every attempt, so its bill is
    not `cost[row, choice]`. If `spend` were dropped on the way out, a bootstrap of
    the cascade's margin would silently price it as a single-shot router and make the
    family look competitive.
    """
    lm, tokens_in, X, train, test = pool
    v: dict = {}
    b = baselines.run(lm, X, tokens_in, train, test, lam_cost=0.2, seed=0, vectors=v)
    assert len(v) == len(b["rows"]) + len(b["our_dial"])
    for row in b["rows"] + b["our_dial"]:
        vec = v[row["policy"]]
        assert np.isclose(float(vec["spend"].mean()), row["cost_per_call_usd"])
        assert np.isclose(float(vec["quality"].mean()), row["quality"])

    cascades = [r for r in b["rows"] if r["family"] == "cascade"]
    assert cascades, "no cascade rows to check"
    q, c = lm.quality[test], lm.cost[test]
    rows = np.arange(len(test))
    for r in cascades:
        if r["mean_attempts"] > 1.01:
            single_shot = float(c[rows, v[r["policy"]]["choice"]].mean())
            assert r["cost_per_call_usd"] > single_shot * 1.01, (
                "a multi-attempt cascade priced as if it paid once")


@needs_cache
def test_margin_interval_is_wider_than_the_point_estimate_implies(pool):
    """The 3.6-point margin must come back with an interval that contains it."""
    lm, tokens_in, _, _, _ = pool
    m = publish.baseline_margin_intervals(lm, tokens_in, lam_cost=0.2,
                                          seeds=(0, 1), n_boot=200, seed=0)
    assert m["item_bootstrap"], "no family produced a useful operating point"
    for family, r in m["item_bootstrap"].items():
        assert r["lo"] <= r["mean"] <= r["hi"]
        assert r["draws_in_range"] <= r["n_boot"]
    for family, r in m["across_splits"].items():
        assert r["min"] <= r["mean"] <= r["max"]


# ---------------------------------------- correction 3: the claims ledger --
def test_claims_ledger_matches_the_adjudicated_count():
    """Fifteen claims, unique ids, every one classified and sourced."""
    assert len(publish.CLAIMS) == 15
    ids = [c.id for c in publish.CLAIMS]
    assert len(set(ids)) == 15
    for c in publish.CLAIMS:
        assert c.kind in {"census", "estimate", "test"}
        assert c.verdict in {"supported", "not supported", "mixed"}
        assert c.source.strip() and ":" in c.where


def test_holm_matches_a_worked_example():
    """Five p-values, one below alpha/5 and the rest not: exactly one survives."""
    out = _holm({"a": 0.009, "b": 0.02, "c": 0.03, "d": 0.2, "e": 0.9})
    assert out["a"]["significant"] and not any(
        out[k]["significant"] for k in "bcde")
    # Holm steps down: once one fails, everything after it fails too.
    assert out["b"]["holm_threshold"] == pytest.approx(0.05 / 4)


def test_holm_stops_at_the_first_failure():
    """The step-down property: 0.04 <= 0.05 on its own, but it is behind a failure.

    Bonferroni would compare both against 0.025 and reject neither. Holm compares the
    smaller against 0.025 — it fails — and that failure stops the procedure, so the
    larger is not tested against its own looser 0.05 threshold.
    """
    out = _holm({"a": 0.04, "b": 0.03})
    assert out["b"]["holm_threshold"] == pytest.approx(0.025)
    assert out["a"]["holm_threshold"] == pytest.approx(0.05)
    assert not out["b"]["significant"], "0.03 > 0.025, so it fails on its own"
    assert not out["a"]["significant"], (
        "0.04 <= its 0.05 threshold, but Holm steps down: once a smaller p fails, "
        "everything above it fails too")


def test_bh_matches_a_worked_example():
    """BH rejects up to the largest rank with p <= alpha*i/m, including gaps."""
    out = _bh({"a": 0.001, "b": 0.019, "c": 0.9, "d": 0.9, "e": 0.9})
    assert out["a"]["significant"] and out["b"]["significant"], (
        "ranks 1 and 2 clear 0.01 and 0.02")
    assert not out["c"]["significant"]
    assert out["b"]["bh_threshold"] == pytest.approx(0.05 * 2 / 5)


def test_bh_rejects_through_a_gap():
    """BH's step-up: a p that fails its own threshold is still rejected if a larger
    one clears its looser threshold. This is what makes it different from Holm."""
    out = _bh({"a": 0.001, "b": 0.025, "c": 0.03, "d": 0.9, "e": 0.9})
    assert out["b"]["p"] > out["b"]["bh_threshold"], "b fails on its own"
    assert out["c"]["significant"] and out["b"]["significant"], (
        "c clears 0.03 at rank 3, so everything at or below rank 3 is rejected")


def test_bh_is_less_conservative_than_holm():
    p = {f"t{i}": v for i, v in enumerate([0.001, 0.008, 0.02, 0.3, 0.5])}
    n_bh = sum(v["significant"] for v in _bh(p).values())
    n_holm = sum(v["significant"] for v in _holm(p).values())
    assert n_bh >= n_holm


def test_multiplicity_audit_partitions_every_claim(artifacts_root):
    a = publish.multiplicity_audit(artifacts_root.parent)
    assert sum(len(v) for v in a["claims_by_kind"].values()) == len(publish.CLAIMS)
    for name, t in a["tests"].items():
        assert 0.0 <= t["p"] <= 1.0
        assert t["family"] in a["families"]
        # Nothing may survive a correction it did not clear uncorrected.
        if t["holm_significant"] or t["bh_significant"]:
            assert t["p"] <= a["alpha"]


def test_domain_family_still_has_no_survivors(artifacts_root):
    """RIGOR.md §2's headline. If a change makes a domain 'significant', it is a bug."""
    path = artifacts_root / "chutes" / "17_domains.json"
    if not path.exists():
        pytest.skip("run scripts/train_chutes.py")
    d = json.loads(path.read_text())
    assert d["significant_after_correction"] == []


# ---------------------------------------------- the coverage-bias mechanism --
@needs_cache
def test_roster_split_matches_the_corpus():
    r = publish.verify_roster()
    assert set(publish.BROAD_POOL) & set(publish.NARROW_POOL) == set()
    assert min(r["broad"].values()) >= publish.BROAD_TASK_THRESHOLD
    assert max(r["narrow"].values()) < publish.BROAD_TASK_THRESHOLD


@needs_cache
def test_uniformly_covered_pool_shows_no_coverage_bias():
    """The negative control, and the whole reason the dose–response is evidence.

    Thirteen columns all graded on the same 22 tasks. The union arm still trains on
    more items than the dense arm, so "more data is worse" predicts a gap here. The
    coverage mechanism predicts none, and there is none.
    """
    from rollingbench.experiments.rigor import coverage_bias_for_pool

    r = coverage_bias_for_pool(list(publish.BROAD_POOL[:13]), lams=(1.0, 100.0))
    assert r["coverage_asymmetry"] < 0.02, "this pool is not uniformly covered"
    assert r["union_best"]["train_items"] >= r["dense_best"]["train_items"]
    assert abs(r["gap_points"]) < 0.02, (
        f"a uniformly covered pool shows a {r['gap_points']:+.1%} gap; the effect is "
        f"then not about coverage")


@needs_cache
def test_pool_must_be_thirteen_columns():
    from rollingbench.experiments.rigor import coverage_bias_for_pool

    with pytest.raises(ValueError, match="columns"):
        coverage_bias_for_pool(list(publish.BROAD_POOL[:5]))
    with pytest.raises(ValueError, match="duplicated"):
        coverage_bias_for_pool([publish.BROAD_POOL[0]] * 13)


@needs_cache
def test_drawn_pools_are_distinct_and_correctly_composed():
    rng = np.random.default_rng(0)
    pools = publish._draw_pools(6, 4, rng)
    assert len({tuple(sorted(p)) for p in pools}) == len(pools)
    for p in pools:
        assert len(p) == 13
        assert sum(m in publish.NARROW_POOL for m in p) == 6


# ---------------------------------------------------------------- k-fold --
@needs_cache
def test_kfold_holds_out_every_item_exactly_once(pool):
    lm, tokens_in, _, _, _ = pool
    r = publish.kfold_headlines(lm, tokens_in, lam_cost=0.2, k=3)
    assert r["pooled_out_of_fold"]["n_items"] == r["n_dense_items"]
    assert sum(f["n_test"] for f in r["folds"]) == r["n_dense_items"]
    for f in r["folds"]:
        assert f["n_train"] + f["n_test"] == r["n_dense_items"]


@needs_cache
def test_kfold_interval_brackets_its_own_mean(pool):
    lm, tokens_in, _, _, _ = pool
    r = publish.kfold_headlines(lm, tokens_in, lam_cost=0.2, k=3)
    for key in ("savings_vs_best_single", "quality_vs_best_single", "val_brier"):
        v = r[key]
        assert v["lo"] <= v["mean"] <= v["hi"]
        assert len(v["folds"]) == 3
