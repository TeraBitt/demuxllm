"""Tests for the Chutes pool — the thirteen models the product actually serves.

Each test pins something a stated result depends on. The cache is built from a
1.2 GB archive that is not in version control, so everything that needs real data
is skipped when the cache is absent rather than failing; the pure-logic tests
(the proxy table, the pricing arithmetic) always run.
"""

from __future__ import annotations

import numpy as np
import pytest

from rollingbench.catalog import (
    CHUTES_CATALOG,
    CHUTES_PROXY,
    check_proxy_table,
    proxy_for,
    proxy_ids,
)
from rollingbench.data import llmrouterbench
from rollingbench.data.cache import features_for
from rollingbench.experiments import chutes

pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")


def _have_cache() -> bool:
    return llmrouterbench.DEFAULT_CACHE.exists()


needs_cache = pytest.mark.skipif(
    not _have_cache(),
    reason="run scripts/build_chutes_matrix.py first (needs the LLMRouterBench tarball)",
)


# ------------------------------------------------------------- the bridge --
def test_proxy_table_covers_catalogue_exactly():
    """Every Chutes slot is bound, in catalogue order, and nothing extra."""
    check_proxy_table()
    assert [b.chutes_id for b in CHUTES_PROXY] == [m.id for m in CHUTES_CATALOG]


def test_proxy_bindings_are_distinct():
    """Two slots sharing a proxy would give the pool two identical columns.

    Every argmax downstream would then be deciding between duplicates, and the
    traffic split between them would be an artefact of float noise.
    """
    ids = proxy_ids()
    assert len(set(ids)) == len(ids) == 13


def test_every_binding_states_a_reason():
    for b in CHUTES_PROXY:
        assert b.why.strip(), f"{b.chutes_id} has no rationale"
        assert len(b.why) > 30, f"{b.chutes_id}'s rationale is too thin to audit"


def test_exact_binding_is_marked_and_is_the_same_checkpoint():
    b = proxy_for("Qwen/Qwen3-235B-A22B-Thinking-2507-TEE")
    assert b.exact and b.same_family
    # The catalogue id carries the Chutes org prefix and TEE suffix; strip both and
    # the two names have to be the same checkpoint.
    assert b.chutes_id.split("/")[-1].removesuffix("-TEE").lower() == b.proxy_id.lower()


def test_only_the_exact_binding_claims_to_be_exact():
    assert sum(b.exact for b in CHUTES_PROXY) == 1


# --------------------------------------------------------------- the pool --
@needs_cache
def test_pool_has_thirteen_columns_in_catalogue_order():
    lm, _ = chutes.build_pool()
    assert lm.model_ids == [m.id for m in CHUTES_CATALOG]
    assert lm.n_models == 13


@needs_cache
def test_cost_is_chutes_price_times_measured_tokens():
    """The proxy's own bill is discarded — it was paid at another provider's rates.

    This is the arithmetic the savings claim rests on, so it is checked cell by
    cell rather than in aggregate.
    """
    lm, tokens_in = chutes.build_pool()
    obs = lm.observed
    price_in = np.array([m.in_per_1m for m in CHUTES_CATALOG])
    price_out = np.array([m.out_per_1m for m in CHUTES_CATALOG])
    expect = (tokens_in / 1e6) * price_in[None, :] + (lm.tokens_out / 1e6) * price_out[None, :]
    assert np.allclose(lm.cost[obs], expect[obs], rtol=1e-9, atol=1e-12)
    # Unobserved cells must not carry a price.
    assert np.all(lm.cost[~obs] == 0.0)


@needs_cache
def test_pool_is_labelled_proxy_backed():
    """A number that cannot be traced back to its caveat will be quoted without it."""
    lm, _ = chutes.build_pool()
    assert "proxy" in lm.source.lower()
    assert any("PROXY-BACKED" in n for n in lm.notes)


@needs_cache
def test_price_ladder_spans_the_catalogue():
    """A pool whose models all cost the same leaves nothing to route between."""
    lm, _ = chutes.build_pool()
    dense = chutes._dense(lm, np.arange(lm.n_items))
    per_call = lm.cost[dense].mean(axis=0)
    assert per_call.max() / per_call.min() > 50


# -------------------------------------------------------------- the split --
@needs_cache
def test_split_is_disjoint_by_item_and_test_is_dense():
    lm, _ = chutes.build_pool()
    train, test = chutes.split(lm)
    assert not set(train.tolist()) & set(test.tolist())
    # Every policy must have had the same menu on every scored item.
    assert lm.observed[test].all()


@needs_cache
def test_union_split_holds_out_the_same_items():
    """The ablation is only a fair comparison if both arms are scored identically."""
    lm, _ = chutes.build_pool()
    _, test_dense = chutes.split(lm, train_on="dense")
    train_union, test_union = chutes.split(lm, train_on="union")
    assert np.array_equal(test_dense, test_union)
    assert not set(train_union.tolist()) & set(test_union.tolist())


@needs_cache
def test_dense_helper_returns_only_fully_observed_rows():
    lm, _ = chutes.build_pool()
    d = chutes._dense(lm, np.arange(lm.n_items))
    assert lm.observed[d].all()
    assert len(d) == int(lm.observed.all(axis=1).sum())


# ------------------------------------------------------------- the router --
@pytest.fixture(scope="module")
def trained():
    if not _have_cache():
        pytest.skip("no cache")
    lm, tokens_in = chutes.build_pool()
    train, test = chutes.split(lm)
    X, _ = features_for(lm, fit_idx=train, verbose=False)
    return lm, tokens_in, X, train, test


@needs_cache
def test_router_beats_the_best_single_model_on_cost_at_the_calibrated_dial(trained):
    """The claim the product rests on, against the opponent that can actually win.

    Not stated as "the router beats Best Single on utility". At a low λ_c the cost
    term is bounded by λ_c itself, so utility is very nearly quality alone and Best
    Single — chosen with hindsight over the training split — is close to unbeatable
    by a router with imperfect per-item predictions. The product's claim is the
    cost axis: same quality, materially less money. That is what is asserted.
    """
    lm, tokens_in, X, train, test = trained
    cal = chutes.calibrate_lam_cost(lm, X, tokens_in, train, test, quality_floor=0.99)
    assert cal["chosen_lam_cost"] is not None, "no dial setting holds the quality floor"
    ev = chutes.evaluate(lm, X, tokens_in, train, test, lam_cost=cal["chosen_lam_cost"])
    router = next(p for p in ev["policies"] if p["policy"] == "router")
    assert router["savings_vs_best_single_pct"] > 0.10
    assert router["quality_vs_best_single_pct"] > 0.98


@needs_cache
def test_inherited_operating_point_is_wrong_on_this_pool(trained):
    """Why calibration is a stage and not a constant.

    RouterBench's λ_c = 0.05 does not merely underperform here — it spends more
    than the do-nothing policy. If this ever stops being true the calibration
    stage can be simplified, so it is pinned.
    """
    lm, tokens_in, X, train, test = trained
    ev = chutes.evaluate(lm, X, tokens_in, train, test, lam_cost=0.05)
    router = next(p for p in ev["policies"] if p["policy"] == "router")
    assert router["savings_vs_best_single_pct"] < 0


@needs_cache
def test_dominance_is_detected_and_reported(trained):
    """A pool with a dominant model bounds what any router can be worth.

    Silently reporting savings against the frontier model while one cheaper model
    beats it outright would be the single most misleading number this file could
    produce, so the dominance check is pinned rather than left to a reader.
    """
    lm, tokens_in, X, train, test = trained
    ev = chutes.evaluate(lm, X, tokens_in, train, test, lam_cost=0.2)
    assert ev["best_single_model"] != ev["frontier_model"]
    assert ev["frontier_model"] in ev["dominated_models"]
    assert ev["best_single_model"] in ev["dominated_models"][ev["frontier_model"]]


@needs_cache
def test_router_matches_frontier_quality_far_cheaper(trained):
    """The headline. Held loosely — it is a measured quantity, not a constant."""
    lm, tokens_in, X, train, test = trained
    cv = chutes.cross_validate(lm, X, tokens_in, lam_cost=0.05, seeds=(0, 1, 2, 3))
    assert cv["quality_vs_frontier"]["mean"] > 0.97
    assert cv["savings_vs_frontier"]["mean"] > 0.30


@needs_cache
def test_turning_the_dial_trades_quality_for_cost_monotonically(trained):
    """λ_c is the product's slider; it has to mean one thing along its whole range."""
    lm, tokens_in, X, train, test = trained
    sweep = chutes.sweep_lambda(lm, X, tokens_in, train, test,
                                lambdas=[0.0, 0.05, 0.2, 1.0])
    savings = [s["savings_vs_frontier"] for s in sweep]
    assert savings == sorted(savings), "raising λ_c must not cost more"
    assert sweep[-1]["quality_vs_frontier"] < sweep[0]["quality_vs_frontier"]


@needs_cache
def test_router_uses_more_than_one_model(trained):
    """A 'router' that always picks the same column is a redirect."""
    lm, tokens_in, X, train, test = trained
    sweep = chutes.sweep_lambda(lm, X, tokens_in, train, test, lambdas=[0.05])
    assert sweep[0]["models_used"] >= 5


@needs_cache
def test_uneven_coverage_costs_more_than_extra_data_buys(trained):
    """The finding that sets the default training set — see chutes.split."""
    lm, tokens_in, X, train, test = trained
    ab = chutes.coverage_ablation(lm, X, tokens_in, lams=(1.0, 100.0))
    best = {m: max((a for a in ab["arms"] if a["train_on"] == m),
                   key=lambda a: a["quality_vs_frontier"]) for m in ("dense", "union")}
    assert best["union"]["train_items"] > 5 * best["dense"]["train_items"]
    assert best["dense"]["quality_vs_frontier"] > best["union"]["quality_vs_frontier"]


@needs_cache
def test_prediction_has_skill_over_the_pool_mean(trained):
    """Brier alone does not prove routing works, but no skill would disprove it."""
    lm, tokens_in, X, train, test = trained
    pq = chutes.prediction_quality(lm, X, train, test)
    assert pq["brier_skill_score"] > 0.05
    assert pq["pairwise_ranking_concordance"] > 0.6


@needs_cache
def test_saved_artifact_round_trips_and_fits_the_budget(tmp_path, trained):
    """NFR-4 caps the published policy at 5 MB."""
    lm, tokens_in, X, train, test = trained
    router, _ = chutes.train_router(lm, X, train)
    info = chutes.save_artifact(router, lm, tmp_path / "router.npz")
    assert info["in_memory_bytes"] < 5 * 1024 * 1024
    z = np.load(tmp_path / "router.npz", allow_pickle=True)
    assert [str(m) for m in z["model_ids"]] == [m.id for m in CHUTES_CATALOG]
    assert z["quality_W"].shape == (X.shape[1], 13)


# --------------------------------------------------------------- the cache --
@needs_cache
def test_items_are_content_addressed_not_index_addressed():
    """Indices restart per split; two splits of one task would otherwise collide."""
    a = llmrouterbench._item_key("mmlupro", "What is 2 + 2?")
    b = llmrouterbench._item_key("mmlupro", "What is  2 + 2?\n")
    c = llmrouterbench._item_key("gpqa", "What is 2 + 2?")
    assert a == b, "whitespace must not change an item's identity"
    assert a != c, "the same question in two tasks is two items"


# -------------------------------------------------------------- scaling --
@needs_cache
def test_more_data_helps_until_it_converges(trained):
    """The learning curve has to be monotone-ish, or the fit is unstable."""
    lm, tokens_in, X, train, test = trained
    sc = chutes.scaling_curves(lm, X, tokens_in, train, test, lam_cost=0.2,
                               sizes=(100, 500, len(train)), dims=(16, 52), repeats=1)
    import collections
    by = collections.defaultdict(list)
    for r in sc["learning_curve"]:
        by[r["n_train"]].append(r["val_brier"])
    ns = sorted(by)
    first = float(np.mean(by[ns[0]]))
    last = float(np.mean(by[ns[-1]]))
    assert last < first, "more data must not increase validation loss"


@needs_cache
def test_loss_and_money_do_not_peak_at_the_same_capacity(trained):
    """Why the capacity sweep reports both curves.

    Sizing the model on validation loss alone picks a different d than sizing it on
    savings. If that ever stops being true the second curve can be dropped, so the
    divergence is pinned rather than assumed.
    """
    lm, tokens_in, X, train, test = trained
    sc = chutes.scaling_curves(lm, X, tokens_in, train, test, lam_cost=0.2,
                               sizes=(len(train),), dims=(8, 16, 24, 32, 40, 52),
                               repeats=1)
    cp = sc["coupling"]
    assert cp["best_d_by_loss"] != cp["best_d_by_savings"]


@needs_cache
def test_capacity_sweep_reports_each_dimension_once(trained):
    """A request for more components than φ has must clamp, not silently repeat."""
    lm, tokens_in, X, train, test = trained
    sc = chutes.scaling_curves(lm, X, tokens_in, train, test, lam_cost=0.2,
                               sizes=(len(train),), dims=(8, 52, 96, 4096), repeats=1)
    ds = [r["d"] for r in sc["capacity_curve"]]
    assert len(ds) == len(set(ds))


# --------------------------------------------------------------- prices --
def test_price_table_shape_is_parsed_not_assumed():
    """The adapter reads Chutes' `pricing` block; a shape change must not pass."""
    from rollingbench.experiments import prices

    assert prices.ENDPOINT.startswith("https://")
    cat = prices.catalogue_prices()
    assert len(cat) == 13
    assert all({"in_per_1m", "out_per_1m"} <= set(v) for v in cat.values())


@needs_cache
def test_a_price_change_reaches_routing_without_touching_the_estimator(trained):
    """FR-16, as a test rather than a claim.

    Price is a live-read lane, so changing it must re-route traffic while leaving
    the fitted weights byte-identical. If a future refactor ever folded price into
    the fit, this is what would catch it.
    """
    from rollingbench.experiments import prices

    lm, tokens_in, X, train, test = trained
    router, _ = chutes.train_router(lm, X, train, lam_cost=0.2)
    tin = chutes._tokens_in_per_item(tokens_in, lm.observed)[test]

    dearer = {k: dict(v) for k, v in prices.catalogue_prices().items()}
    target = "Qwen/Qwen3-235B-A22B-Thinking-2507-TEE"
    dearer[target]["in_per_1m"] *= 8
    dearer[target]["out_per_1m"] *= 8

    res = prices.reprice(router, lm, X, test, tin, dearer)
    assert res["estimator_unchanged"], "price must never enter the fitted state"
    assert res["requests_rerouted"] > 0, "an 8x price rise must move traffic"
    assert res["traffic_after"][target] < res["traffic_before"][target]
    # Reacting must beat standing still once the price has moved.
    assert res["spend_after_usd"] < res["spend_if_frozen_usd"]


@needs_cache
def test_price_shock_curve_is_monotone_in_price(trained):
    """Dearer must never mean more traffic. A non-monotone curve is a bug."""
    from rollingbench.experiments import prices

    lm, tokens_in, X, train, test = trained
    router, _ = chutes.train_router(lm, X, train, lam_cost=0.2)
    tin = chutes._tokens_in_per_item(tokens_in, lm.observed)[test]
    sh = prices.price_shock(router, lm, X, test, tin,
                            target_id="Qwen/Qwen3-235B-A22B-Thinking-2507-TEE",
                            factors=(0.5, 1.0, 2.0, 4.0))
    shares = [p["target_share_after"] for p in sh["points"]]
    assert shares == sorted(shares, reverse=True)


# ------------------------------------------------------- the binding audit --
@needs_cache
def test_most_bindings_are_open_weights_like_the_pool_itself():
    """Chutes serves open weights only, so a closed stand-in is a weaker analogue."""
    from rollingbench.catalog import OPEN_WEIGHT_PROXIES

    open_bound = sum(b.proxy_id in OPEN_WEIGHT_PROXIES for b in CHUTES_PROXY)
    assert open_bound >= 11, f"only {open_bound}/13 bindings are open-weights"


@needs_cache
def test_closed_anchors_are_justified_by_measurement_not_preference():
    """The frontier slots keep closed anchors only because open ones break the tier.

    If the corpus ever grades an open model strong enough, this test fails and the
    anchors should be replaced — which is the point of asserting it.
    """
    r = chutes.open_weights_only()
    assert r["closed_bindings_in_use"], "no closed anchors left; simplify the audit"
    assert not r["frontier_tier_still_above_mid"], (
        "an open-weights binding now holds the tier ordering — replace the anchors")


@needs_cache
def test_candidate_models_are_ranked_on_a_shared_task_set():
    """Ranking on own-coverage flatters the small models; that trap is fixed.

    The best open substitute for a frontier slot must not out-score the closed
    anchor it replaces — if it does, the ranking is reading the question mix rather
    than the models.
    """
    r = chutes.open_weights_only()
    for s in r["swaps"]:
        assert s["now_accuracy"] <= s["was_accuracy"], (
            f"{s['now']} scoring above {s['was']} means coverage bias has returned")


# ------------------------------------------------------- the unreachable slots --
@needs_cache
def test_never_selected_slots_are_not_dominated(trained):
    """They take 0% of traffic, and a per-item oracle still wants them badly.

    This is the difference between "retire the slot" and "fix the estimator", so it
    is asserted rather than left to a reader's judgement.
    """
    import numpy as _np

    from rollingbench.metrics import UtilityWeights, per_cell_utility

    lm, tokens_in, X, train, test = trained
    tau = chutes.sweep_tau(lm, X, tokens_in, train, test, lam_cost=0.2, taus=(0.7,))
    router_share = tau["argmax"]["traffic_share"]
    unused = [m for m in lm.model_ids if router_share[m] == 0.0]
    assert unused, "expected at least one never-selected slot"

    d = chutes._dense(lm, _np.arange(lm.n_items))
    fc = int(_np.argmax(lm.quality[d].mean(axis=0)))
    oracle = per_cell_utility(lm.quality[d], lm.cost[d],
                              UtilityWeights(lam_cost=0.2), ref_col=fc).argmax(axis=1)
    owed = sum(float((oracle == lm.model_ids.index(m)).mean()) for m in unused)
    assert owed > 0.10, (
        f"a per-item oracle sends the never-selected slots only {owed:.1%}; "
        "if this ever falls to ~0 they really are dominated and can be retired")


@needs_cache
def test_threshold_rule_loses_to_the_argmax_at_matched_quality(trained):
    """The rule the product advertises is worse here, and that is a finding.

    A threshold needs the predicted *level* to be right; an argmax needs only the
    ordering. The level is the badly-estimated half, so the simpler rule wins. If a
    better encoder ever flips this, the product copy should change with it.
    """
    lm, tokens_in, X, train, test = trained
    r = chutes.sweep_tau(lm, X, tokens_in, train, test, lam_cost=0.2)
    argmax = r["argmax"]
    matched = [g for g in r["grid"]
               if g["quality_vs_best_single"] >= argmax["quality_vs_best_single"] - 0.01]
    assert matched, "no threshold setting reaches the argmax's quality"
    best = max(matched, key=lambda g: g["savings_vs_best_single"])
    assert best["savings_vs_best_single"] < argmax["savings_vs_best_single"]


@needs_cache
def test_sufficiency_never_refuses_a_request(trained):
    """Where no model clears the bar the rule must still answer, not return nothing."""
    import numpy as _np

    q_hat = _np.full((50, 13), 0.1)
    cost_hat = _np.tile(_np.arange(1, 14, dtype=float), (50, 1))
    choice = chutes.sufficiency_policy(q_hat, cost_hat, tau=0.99)
    assert choice.shape == (50,)
    assert ((choice >= 0) & (choice < 13)).all()


# ------------------------------------------------------------- dated pool --
def test_every_slot_has_a_release_date():
    """The growing-pool replay cannot run on a slot with no date."""
    from rollingbench.catalog import chutes_dated

    dated = chutes_dated()
    assert len(dated) == 13
    assert all(m.released is not None for m in dated), (
        [m.id for m in dated if m.released is None])


def test_pool_actually_grows_over_the_replay_window():
    """A pool that was complete on day one would make the staleness arm vacuous."""
    import datetime as _dt

    from rollingbench.catalog import chutes_dated, released_by

    dated = chutes_dated()
    at_start = len(released_by(dated, _dt.date(2025, 5, 1)))
    at_end = len(released_by(dated, _dt.date(2025, 11, 1)))
    assert at_start < at_end == 13, f"{at_start} → {at_end}"


# ----------------------------------------------------------------- latency --
@needs_cache
def test_wall_clock_is_rejected_as_a_latency_source():
    """The corpus's timings are concurrent, and the code must say so rather than divide.

    If a future corpus ships credible per-request timings this test fails, which is
    the signal to switch from the token proxy to real seconds.
    """
    from rollingbench.experiments import latency

    fits = latency.fit_throughput()
    verdict = latency.throughput_is_credible(fits)
    assert not verdict["credible"]
    assert verdict["implausible_rate_count"] > 0


@needs_cache
def test_latency_term_shortens_the_tail(trained):
    """§8.7's λ_l has never been switched on before; it has to actually do something."""
    from rollingbench.experiments import latency

    lm, tokens_in, X, train, test = trained
    sweep = latency.sweep_lam_latency(lm, X, train, test, tokens_in,
                                      lam_cost=0.2, lam_latencies=(0.0, 0.2))
    off, on = sweep[0], sweep[1]
    assert on["p95_tokens"] < off["p95_tokens"] * 0.75
    # Shorter answers are also cheaper, so this knob must not cost money.
    assert on["savings_vs_frontier"] >= off["savings_vs_frontier"]


# ------------------------------------------------------------------- rigor --
@needs_cache
def test_bootstrap_intervals_bracket_the_point_estimate(trained):
    """A CI that excludes its own point estimate means the resampling is wrong."""
    from rollingbench.experiments import rigor

    lm, tokens_in, X, train, test = trained
    b = rigor.bootstrap_headlines(lm, X, tokens_in, train, test,
                                  lam_cost=0.2, n_boot=400)
    for key in ("savings_vs_best_single", "quality_vs_best_single", "val_brier"):
        ci = b[key]
        assert ci["lo"] <= ci["mean"] <= ci["hi"], key
        assert ci["hi"] > ci["lo"], f"{key} has a degenerate interval"


@needs_cache
def test_bootstrap_resamples_items_not_cells(trained):
    """Resampling cells would treat one prompt as thirteen observations.

    The tell is interval width: cell-resampling would shrink it by roughly sqrt(13).
    A floor on the width catches that regression.
    """
    from rollingbench.experiments import rigor

    lm, tokens_in, X, train, test = trained
    b = rigor.bootstrap_headlines(lm, X, tokens_in, train, test,
                                  lam_cost=0.2, n_boot=400)
    ci = b["savings_vs_best_single"]
    assert ci["hi"] - ci["lo"] > 0.02, "interval implausibly tight for n≈1,200 items"


@needs_cache
def test_no_per_domain_difference_survives_correction(trained):
    """Pinned because the uncorrected table was quoted as five findings.

    If a future encoder makes one real, this fails and the claim can be made — with
    the correction still applied.
    """
    from rollingbench.experiments import rigor

    lm, tokens_in, X, train, test = trained
    d = rigor.domain_significance(lm, X, tokens_in, train, test, lam_cost=0.2)
    assert d["family_size"] == 5
    assert d["significant_after_correction"] == []


def test_holm_is_monotone_and_no_looser_than_bonferroni():
    """A correction that is wrong in the permissive direction is worse than none."""
    from rollingbench.experiments.rigor import _holm

    p = {"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5}
    out = _holm(p, alpha=0.05)
    assert out["a"]["significant"]
    # Holm's first threshold equals Bonferroni's, so it is never more permissive there.
    assert out["a"]["holm_threshold"] == 0.05 / 4
    # Once a hypothesis fails, every later one fails too.
    flags = [out[k]["significant"] for k in ("a", "b", "c", "d")]
    assert flags == sorted(flags, reverse=True)


@needs_cache
def test_coverage_bias_replicates_on_a_disjoint_pool():
    """The most novel finding, on thirteen models sharing no column with the first."""
    from rollingbench.catalog import CHUTES_PROXY
    from rollingbench.experiments import rigor

    assert not set(rigor.REPLICATION_POOL) & {b.proxy_id for b in CHUTES_PROXY}
    r = rigor.replicate_coverage_bias(lams=(1.0, 100.0))
    assert r["replicates"], r["reading"]
    assert r["gap_points"] > 0.05


@needs_cache
def test_savings_are_robust_to_workload_mix(trained):
    """Measured after the 'conservative lower bound' claim turned out to be false."""
    from rollingbench.experiments import rigor

    lm, tokens_in, X, train, test = trained
    w = rigor.workload_mix(lm, X, tokens_in, train, test, lam_cost=0.2)
    sav = [r["savings_vs_best_single"] for r in w["rows"]]
    assert max(sav) - min(sav) < 0.10, "savings should be flat across the mix"
    # Easier traffic must at least route to cheaper models, even if savings are flat.
    assert w["rows"][-1]["open_tier_share"] > w["rows"][0]["open_tier_share"]


# --------------------------------------------------------------- baselines --
@needs_cache
def test_cascade_pays_for_every_attempt(trained):
    """The structural reason cascades lose here; if it stops being true, so does §5."""
    from rollingbench.experiments import baselines

    lm, tokens_in, X, train, test = trained
    r = baselines.run(lm, X, tokens_in, train, test, lam_cost=0.2)
    cascades = [x for x in r["rows"] if x["policy"].startswith("cascade")]
    assert cascades
    dear = max(cascades, key=lambda x: x["quality_vs_best_single"])
    assert dear["mean_attempts"] > 1.0
    assert dear["savings_vs_best_single"] < 0, "a paying cascade must cost more"


@needs_cache
def test_matrix_factorisation_beats_us_in_the_aggressive_region(trained):
    """Pinned because it is a real negative and must not quietly disappear.

    Swept across its own dial and compared at matched quality, a RouteLLM-style
    low-rank router is *better* than ours where savings are aggressive — 59.4%
    against 55.8% at 95.5% of the best single model's quality. That is the honest
    state of the comparison and the strongest argument that our estimator is not
    where the advantage lives.

    The assertion is bounded on both sides: if the margin grows past ten points we
    should adopt their rule, and if it inverts the claim in the docs is stale.
    """
    from rollingbench.experiments import baselines

    lm, tokens_in, X, train, test = trained
    r = baselines.run(lm, X, tokens_in, train, test, lam_cost=0.2)
    assert "matrix" in r["beaten_by"], r["reading"]
    margin = r["best_by_family"]["matrix"]["margin_vs_us"]
    assert 0.02 < margin < 0.10, f"margin moved to {margin:+.3f} — revisit the docs"


@needs_cache
def test_cascade_and_hybrid_have_no_useful_operating_point(trained):
    """Neither ever both saves money and holds 95% quality on this pool.

    A comparison is only meaningful where a strategy beats doing nothing; these two
    never do, which is a stronger statement than losing on margin.
    """
    from rollingbench.experiments import baselines

    lm, tokens_in, X, train, test = trained
    r = baselines.run(lm, X, tokens_in, train, test, lam_cost=0.2)
    assert set(r["families_with_no_useful_point"]) >= {"cascade", "hybrid"}, r["reading"]


@needs_cache
def test_all_six_published_families_are_compared(trained):
    """The gap PUBLISHABILITY.md named was 'zero published baselines'."""
    from rollingbench.experiments import baselines

    lm, tokens_in, X, train, test = trained
    r = baselines.run(lm, X, tokens_in, train, test, lam_cost=0.2)
    for fam in ("cascade", "matrix", "hybrid", "classifier", "knn", "no-routing"):
        assert fam in r["families_compared"], fam
