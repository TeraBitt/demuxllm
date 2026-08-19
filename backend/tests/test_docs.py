"""The numbers the documents lead with, pinned to the artifacts they came from.

`RESULTS.md`, `RIGOR.md` and `PUBLISHING.md` each quote figures to one or three
decimals. Nothing stops a re-run from moving one and leaving the prose behind — which
is the same failure mode the Makefile guards for `src/lib/measured.ts`, and a stale
number in a document that argues about rigour is worse than a stale number on a page.

So the headline of each section is pinned here. A change that moves one of these fails
the suite, and the fix is to update the document rather than the test. Tolerances are
one unit in the last place the document quotes.

Only headlines. Pinning every number would make the suite a copy of the artifacts and
would fail for changes nobody needs to be told about.
"""

from __future__ import annotations

import json

import pytest

ART = None


@pytest.fixture(scope="module")
def art(artifacts_root):
    def load(name):
        p = artifacts_root / name
        if not p.exists():
            pytest.skip(f"{name} not written — run `make publish`")
        return json.loads(p.read_text())
    return load


# ------------------------------------------------ PUBLISHING.md §1 --
def test_coverage_bias_is_present_where_uneven_and_absent_where_not(art):
    d = art("chutes/20_dose_response.json")["dose_response"]
    assert d["n_pools"] == 19
    assert d["controls"]["n"] == 4 and d["asymmetric"]["n"] == 15
    assert d["asymmetric"]["replicated_in"] == 15, "§1a claims 15 of 15"
    assert d["asymmetric"]["replicated_at_matched_n_in"] == 15
    assert abs(d["asymmetric"]["mean_gap"] - 0.136) < 0.001
    assert abs(d["asymmetric"]["mean_gap_at_matched_n"] - 0.165) < 0.001
    assert abs(d["controls"]["max_abs_gap"] - 0.003) < 0.001, "§1a claims 0.3%"
    # The control pools must actually carry the confound they are controlling for:
    # more training data. Otherwise they rule nothing out.
    assert d["controls"]["mean_union_over_dense_train"] > 1.0


def test_the_effect_survives_holding_the_item_count_fixed(art):
    r = art("chutes/20_dose_response.json")["first_replication"]
    assert r["dense_best"]["train_items"] == r["union_matched_n_best"]["train_items"], (
        "the size-matched arm is only a control if the sizes match")
    assert abs(r["gap_at_matched_n"] - 0.237) < 0.001, "§1b claims +23.7 points"
    assert r["gap_at_matched_n"] > r["gap_points"], (
        "§1b claims extra data compensates rather than causes; if this flips, the "
        "whole framing in PUBLISHING.md §1 is wrong")


def test_the_mask_sweep_starts_at_zero_and_is_monotone(art):
    m = art("chutes/20_dose_response.json")["mask_sweep"]
    rows = m["rows"]
    assert rows[0]["target_fraction_removed"] == 0.0
    assert abs(rows[0]["gap_at_matched_n"]) < 0.005, (
        "the zero-removal control must show no effect, or the sweep proves nothing")
    gaps = [r["gap_at_matched_n"] for r in rows]
    assert gaps == sorted(gaps), "§1c calls the size-matched column monotone"


# ------------------------------------------------ PUBLISHING.md §2 --
def test_kfold_agrees_with_the_bootstrap_on_the_level(art):
    kf, boot = art("chutes/21_kfold.json"), art("chutes/16_bootstrap.json")
    b = boot["savings_vs_best_single"]["mean"]
    for k in kf["ks"]:
        v = kf["by_k"][str(k)]["savings_vs_best_single"]["mean"]
        assert 0.21 < v < 0.24, f"§2 quotes 21.4–23.0%; k={k} gives {v:.3f}"
        assert abs(v - b) < 0.05, "the two instruments must agree on the level"
        pooled = kf["by_k"][str(k)]["pooled_out_of_fold"]["savings_vs_best_single"]
        assert abs(pooled - v) < 0.002, "pooled out-of-fold should track the fold mean"


def test_the_parity_verdict_is_instrument_dependent(art):
    """§2's whole point: the k-fold interval answers this differently at different k."""
    p = art("chutes/21_kfold.json")["does_the_quality_interval_contain_parity"]
    assert p["bootstrap"] is True, "RIGOR.md §1 rests on this"
    assert not p["stable_across_k"], (
        "§2 argues a CV spread is not a confidence interval *because* its parity "
        "verdict moves with k. If it stops moving, that argument needs rewriting")


# ------------------------------------------------ PUBLISHING.md §3 --
def test_the_matrix_factorisation_result_does_not_survive_eight_splits(art):
    m = art("chutes/22_baseline_margins.json")
    s = m["across_splits"]["matrix"]
    assert s["mean"] < 0, "§3 retracts 'beats us' on the strength of a negative mean"
    assert abs(s["mean"] - -0.066) < 0.001
    assert s["beats_us_in"] == 2
    b = m["item_bootstrap"]["matrix"]
    assert b["lo"] < 0 < b["hi"], "§3 says the bootstrap interval contains zero"


def test_cascades_and_hybrid_lose_on_every_split(art):
    """The part of RIGOR.md §5 that survives, and the reason is structural."""
    per_seed = art("chutes/22_baseline_margins.json")["per_seed"]
    assert len(per_seed) == 8
    for family in ("cascade", "hybrid"):
        n = sum(1 for r in per_seed if family in r["no_useful_point"])
        assert n == 8, f"§3 claims {family} has no useful point in 8 of 8, got {n}"


# ------------------------------------------------ PUBLISHING.md §4 --
def test_the_claims_split_four_nine_two(art):
    a = art("chutes/23_multiplicity.json")
    assert {k: len(v) for k, v in a["claims_by_kind"].items()} == {
        "census": 4, "estimate": 9, "test": 2}, "§4's table"
    assert a["n_tests"] == 15
    assert a["significant_uncorrected"] == 5
    assert len(a["significant_after_holm_within_family"]) == 1, "§4 claims one survivor"
    assert a["significant_after_bh_across_all"] == [], "§4 claims none survive BH"


# ------------------------------------------------ PUBLISHING.md §5 --
def test_neither_gamma_regime_is_significant(art):
    """The correction. Both arms null; §5 and PUBLISHABILITY.md §2 both say so."""
    rep = art("decomposition.json")["replication"]
    for regime in ("default", "high_drift"):
        d = rep[regime]["decomposition"]
        assert not d["supported"], f"{regime} is significant again — §5 says it is not"
        assert d["p_value"] > 0.05
    hd = rep["high_drift"]["decomposition"]
    ratio = hd["mean_regret_reduction"] / hd["std_error"]
    assert 1.96 < ratio < hd["t_critical_two_sided"], (
        "§5's whole argument is that this arm sits between the normal and the t "
        "critical value. If it moves outside that band the example needs replacing")
