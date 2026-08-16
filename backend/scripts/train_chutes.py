#!/usr/bin/env python
"""Train the router over the thirteen Chutes models and write every number out.

    python scripts/build_chutes_matrix.py     # once — parses the corpus
    python scripts/train_chutes.py            # train, evaluate, plot
    python scripts/train_chutes.py --quick    # smaller sweeps

Each stage writes its own artifact rather than only the final one, so a reader can
see what the pipeline believed at every step instead of having to trust the last
number in the chain:

    artifacts/chutes/01_pool.json         the matrix, the proxy bindings, the corpus
    artifacts/chutes/02_training.json     fit diagnostics, per-model observations
    artifacts/chutes/03_ablation.json     dense vs union training
    artifacts/chutes/04_calibration.json  where the dial is set, and why
    artifacts/chutes/05_frontier.json     the λ_c sweep
    artifacts/chutes/06_policies.json     router against every baseline
    artifacts/chutes/07_analytics.json    per model, per domain, per task
    artifacts/chutes/09_scaling.json      loss vs data and capacity, and what each buys
    artifacts/chutes/10_prices.json       the live price list, and a price shock
    artifacts/chutes/11_crossval.json     headline figures over eight splits
    artifacts/chutes/router.npz           the trained policy itself
    artifacts/chutes/frontend.json        the numbers the product would quote
    artifacts/figures/chutes_*.png        the figures

The operating point is calibrated here rather than inherited. λ_c = 0.05 is right on
RouterBench and badly wrong on this pool — it spends 84% more than simply sending
everything to the best single model — because it weights a cost *ratio* and this
pool's ratios span three orders of magnitude where RouterBench's span one.

Everything here is proxy-backed. Read `catalog.CHUTES_PROXY` before quoting any of
it as a measurement of Chutes.
"""

from __future__ import annotations

import argparse
import json
import sys
import datetime as _dt
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rollingbench.catalog import CHUTES_CATALOG, CHUTES_PROXY, by_id  # noqa: E402
from rollingbench.data.cache import features_for  # noqa: E402
from rollingbench.catalog import chutes_dated  # noqa: E402
from rollingbench.experiments import (  # noqa: E402
    baselines, chutes, coldstart_sc, latency, prices, rigor, staleness,
)

OUT = ROOT / "artifacts" / "chutes"
FIGURES = ROOT / "artifacts" / "figures"


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        f = float(obj)
        return f if np.isfinite(f) else None
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, float):
        return obj if np.isfinite(obj) else None
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    return obj


def write(name: str, payload) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(_jsonable(payload), indent=2))
    print(f"       → {path.relative_to(ROOT)}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--lam-cost", type=float, default=0.05,
                    help="fallback operating point if calibration finds none")
    ap.add_argument("--quality-floor", type=float, default=0.99,
                    help="share of the best single model's quality the dial must hold")
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 78)
    print("RollingBench — the Chutes pool (proxy-backed)")
    print("=" * 78)

    # -------------------------------------------------------------- [1] pool --
    print("\n[1/18] pool: thirteen Chutes slots, priced at Chutes rates")
    t = time.time()
    lm, tokens_in = chutes.build_pool()
    train, test = chutes.split(lm, seed=args.seed)
    dense_all = int(lm.observed.all(axis=1).sum())
    print(f"       {lm.n_items:,} items x {lm.n_models} models, "
          f"{int(lm.observed.sum()):,} graded cells (density {lm.observed.mean():.3f})")
    print(f"       dense core {dense_all:,} items → {len(train):,} train / {len(test):,} test")

    X, fm = features_for(lm, fit_idx=train)
    print(f"       features d={X.shape[1]}, frozen after fitting on the training split")

    write("01_pool", {
        "proxy_backed": True,
        "corpus": lm.summary(),
        "dense_core_items": dense_all,
        "n_train_items": len(train),
        "n_test_items": len(test),
        "feature_dim": int(X.shape[1]),
        "bindings": [
            {"chutes_id": b.chutes_id,
             "label": by_id(CHUTES_CATALOG, b.chutes_id).label,
             "tier": by_id(CHUTES_CATALOG, b.chutes_id).tier,
             "proxy_id": b.proxy_id, "exact": b.exact,
             "same_family": b.same_family, "why": b.why}
            for b in CHUTES_PROXY
        ],
        "tasks": sorted(set(lm.task.tolist())),
        "domains": sorted(set(lm.domain.tolist())),
    })
    print(f"       ({time.time() - t:.0f}s)")

    # ------------------------------------------------- [1b] binding audit --
    ow = chutes.open_weights_only()
    write("01b_bindings", ow)
    print(f"       bindings: {round(ow['open_binding_share'] * 13)} of 13 stand in with "
          f"open-weights models, like the pool itself")
    if ow["closed_bindings_in_use"]:
        print("       " + "; ".join(
            f"{c['label']} leans on {c['proxy_id']} (closed weights)"
            for c in ow["closed_bindings_in_use"]))
        print(f"       {ow['reading']}")

    # ---------------------------------------------------------- [2] training --
    print("\n[2/18] training: the §8 estimator over the pool")
    t = time.time()
    router, diagnostics = chutes.train_router(lm, X, train, lam_cost=args.lam_cost)
    saved = chutes.save_artifact(router, lm, OUT / "router.npz")
    diagnostics["artifact"] = saved
    write("02_training", diagnostics)
    print(f"       {diagnostics['n_train_cells']:,} cells absorbed, "
          f"train Brier {diagnostics['train_brier']:.4f}")
    print(f"       policy artifact {saved['bytes'] / 1024:.0f} KB on disk "
          f"({saved['in_memory_bytes'] / 1024:.0f} KB in memory)")
    print(f"       ({time.time() - t:.0f}s)")

    # --------------------------------------------------------- [3] ablation --
    print("\n[3/18] ablation: does training on ten times the data help?")
    t = time.time()
    lams = (1.0, 100.0) if args.quick else (1.0, 10.0, 100.0, 1000.0)
    ablation = chutes.coverage_ablation(lm, X, tokens_in, seed=args.seed, lams=lams)
    write("03_ablation", ablation)
    print(f"       {ablation['reading']}")
    print(f"       ({time.time() - t:.0f}s)")

    # ------------------------------------------------------ [4] calibration --
    print("\n[4/18] calibration: the dial setting, on this pool")
    t = time.time()
    grid = ([0.0, 0.05, 0.12, 0.2, 0.35] if args.quick else None)
    calibration = chutes.calibrate_lam_cost(lm, X, tokens_in, train, test,
                                            quality_floor=args.quality_floor,
                                            lambdas=grid)
    write("04_calibration", calibration)
    print(f"       {calibration['reading']}")
    lam_cost = calibration["chosen_lam_cost"]
    if lam_cost is None:
        lam_cost = args.lam_cost
        print(f"       falling back to λ_c={lam_cost:g}")
    elif abs(lam_cost - args.lam_cost) > 1e-12:
        print(f"       (RouterBench's λ_c={args.lam_cost:g} would spend "
              f"{-100 * next(g['savings_vs_best_single'] for g in calibration['grid'] if abs(g['lam_cost'] - args.lam_cost) < 1e-12):.0f}% "
              f"more than the best single model — recalibrated)")
    print(f"       ({time.time() - t:.0f}s)")

    # --------------------------------------------------------- [5] frontier --
    print("\n[5/18] frontier: the cost/quality dial")
    t = time.time()
    lambdas = ([0.0, 0.02, 0.05, 0.12, 0.35] if args.quick else
               [0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.35, 0.6, 1.0])
    sweep = chutes.sweep_lambda(lm, X, tokens_in, train, test, lambdas)
    write("05_frontier", sweep)
    at = min(sweep, key=lambda s: abs(s["lam_cost"] - lam_cost))
    print(f"       λ_c={at['lam_cost']:g}: {at['savings_vs_frontier']:.1%} cheaper at "
          f"{at['quality_vs_frontier']:.1%} of frontier quality, "
          f"{at['models_used']} of {lm.n_models} models used")
    print(f"       ({time.time() - t:.0f}s)")

    # --------------------------------------------------------- [6] policies --
    print("\n[6/18] policies: the router against every baseline")
    t = time.time()
    evaluation = chutes.evaluate(lm, X, tokens_in, train, test,
                                 lam_cost=lam_cost, seed=args.seed)
    write("06_policies", evaluation)
    print(f"       {'policy':<42s} {'quality':>8s} {'$ total':>9s} {'vs frontier':>12s} "
          f"{'vs best-single':>15s}")
    for p in evaluation["policies"]:
        print(f"       {p['policy']:<42s} {p['quality']:8.4f} {p['cost_usd']:9.2f} "
              f"{p['savings_vs_frontier_pct']:11.1%} {p['savings_vs_best_single_pct']:14.1%}")
    if evaluation["frontier_model_is_dominated"]:
        print(f"       NOTE: {evaluation['frontier_model']} is the highest-quality model "
              f"but is beaten outright on both axes by "
              f"{', '.join(evaluation['models_beating_the_frontier_model'])}.")
        print("       Savings quoted against it are therefore inflated; "
              "'vs best-single' is the honest column.")
    print(f"       ({time.time() - t:.0f}s)")

    # -------------------------------------------------------- [7] analytics --
    print("\n[7/18] analytics: per model, per domain, per task")
    t = time.time()
    # Re-fit at the calibrated dial so the analytics describe the shipped policy,
    # not the one trained at the inherited default.
    router, diagnostics = chutes.train_router(lm, X, train, lam_cost=lam_cost)
    diagnostics["artifact"] = chutes.save_artifact(router, lm, OUT / "router.npz")
    ps = chutes.pool_state()
    tin_item = chutes._tokens_in_per_item(tokens_in, lm.observed)[test]
    choice = router.decide(X[test], ps, tokens_in=tin_item).choice

    models = chutes.model_table(lm, test, choice)
    domains = chutes.domain_table(lm, test, choice)
    tasks = chutes.task_table(lm, test, choice)
    prediction = chutes.prediction_quality(lm, X, train, test)
    analytics = {
        "operating_point": lam_cost,
        "models": models,
        "domains": domains,
        "tasks": tasks,
        "prediction_quality": prediction,
        "tier_mix": chutes._tier_mix(choice),
        "unused_models": [m["label"] for m in models if (m["traffic_share"] or 0) == 0.0],
    }
    write("07_analytics", analytics)
    print(f"       Brier {prediction['val_brier']:.4f} "
          f"(skill {prediction['brier_skill_score']:+.3f}), "
          f"pairwise ranking concordance {prediction['pairwise_ranking_concordance']:.3f}")
    print(f"       tier mix: " + ", ".join(
        f"{k} {v:.0%}" for k, v in analytics["tier_mix"].items()))
    if analytics["unused_models"]:
        print(f"       never selected: {', '.join(analytics['unused_models'])}")
    print(f"       ({time.time() - t:.0f}s)")

    # ---------------------------------------------------------- [8] scaling --
    print("\n[8/18] scaling: loss against data and capacity, beside what each buys")
    t = time.time()
    sizes = (100, 500, 1500, len(train)) if args.quick else None
    dims = (8, 16, 32, 52) if args.quick else (4, 8, 16, 24, 32, 40, 52)
    scaling = chutes.scaling_curves(lm, X, tokens_in, train, test, lam_cost=lam_cost,
                                    sizes=sizes, dims=dims,
                                    repeats=2 if args.quick else 3, seed=args.seed)
    write("09_scaling", scaling)
    cp = scaling["coupling"]
    conv = scaling["converged"]
    print(f"       converged: Brier {conv['val_brier']:.4f}, "
          f"{conv['savings_vs_best_single']:.1%} cheaper at "
          f"{conv['quality_vs_best_single']:.1%} of best-single quality")
    print(f"       best d by loss = {cp['best_d_by_loss']}, "
          f"best d by savings = {cp['best_d_by_savings']} "
          f"(corr {cp['corr_brier_savings_over_capacity']:+.2f}) — "
          f"loss alone would size the model wrong")
    print(f"       ({time.time() - t:.0f}s)")

    # ----------------------------------------------------------- [9] prices --
    print("\n[9/18] prices: read live, and what a price change does to routing")
    t = time.time()
    price_report = {"live_fetch_ok": False}
    try:
        live = prices.fetch_live()
        price_report["live"] = live
        price_report["diff"] = prices.diff_against_catalogue(live)
        price_report["live_fetch_ok"] = True
        d = price_report["diff"]
        print(f"       llm.chutes.ai/v1/models: {d['live_model_count']} chat models, "
              f"catalogue {'in sync' if d['in_sync'] else 'DRIFTED'}")
        for row in d["drift"]:
            print(f"         {row['label']}: {row['catalogue_in']}/{row['catalogue_out']} "
                  f"→ {row['live_in']}/{row['live_out']} "
                  f"({row['blended_change_pct']:+.1%} blended)")
    except (OSError, RuntimeError, ValueError) as e:
        # Offline is a normal way to run this; it must not take the pipeline down.
        price_report["error"] = str(e)
        print(f"       live price read failed ({e}) — shock still runs on the catalogue")

    shock = prices.price_shock(router, lm, X, test, tin_item,
                               target_id=evaluation["best_single_model"])
    price_report["shock"] = shock
    write("10_prices", price_report)
    print(f"       {shock['reading']}")
    worst = max(shock["points"], key=lambda p: p["saved_by_reacting_usd"])
    print(f"       at {worst['factor']:g}x, reacting saves "
          f"${worst['saved_by_reacting_usd']:.2f} of ${worst['spend_if_frozen_usd']:.2f} "
          f"({worst['saved_by_reacting_usd'] / max(worst['spend_if_frozen_usd'], 1e-9):.0%})")
    print(f"       ({time.time() - t:.0f}s)")

    # --------------------------------------------------------- [10] crossval --
    print("\n[10/18] cross-validation: the headline figures over eight splits")
    t = time.time()
    seeds = (0, 1, 2) if args.quick else (0, 1, 2, 3, 4, 5, 6, 7)
    cv = chutes.cross_validate(lm, X, tokens_in, lam_cost=lam_cost, seeds=seeds)
    write("11_crossval", cv)
    s, q = cv["savings_vs_frontier"], cv["quality_vs_frontier"]
    sb, qb = cv["savings_vs_best_single"], cv["quality_vs_best_single"]
    print(f"       vs frontier model:  {s['mean']:.1%} ± {s['se']:.1%} cheaper at "
          f"{q['mean']:.1%} ± {q['se']:.1%} of its quality")
    print(f"       vs best single:     {sb['mean']:.1%} ± {sb['se']:.1%} cheaper at "
          f"{qb['mean']:.1%} ± {qb['se']:.1%} of its quality")
    print(f"       ({time.time() - t:.0f}s)")


    # ------------------------------------------------- [11] the dead slots --
    print("\n[11/18] slots: are the never-selected models actually dominated?")
    t = time.time()
    tau = chutes.sweep_tau(lm, X, tokens_in, train, test, lam_cost=lam_cost)
    from rollingbench.metrics import UtilityWeights, per_cell_utility
    dall = chutes._dense(lm, np.arange(lm.n_items))
    fcol = int(np.argmax(lm.quality[dall].mean(axis=0)))
    oracle_choice = per_cell_utility(lm.quality[dall], lm.cost[dall],
                                     UtilityWeights(lam_cost=lam_cost),
                                     ref_col=fcol).argmax(axis=1)
    oracle_share = {lm.model_ids[j]: float((oracle_choice == j).mean())
                    for j in range(lm.n_models)}
    router_share = tau["argmax"]["traffic_share"]
    unused = [m for m in lm.model_ids if router_share.get(m, 0.0) == 0.0]
    slots = {
        "oracle_share": oracle_share,
        "router_share": router_share,
        "never_selected": unused,
        "oracle_wants_on_never_selected": float(sum(oracle_share[m] for m in unused)),
        "threshold_rule": tau,
        "reading": (
            f"The router sends {', '.join(unused)} no traffic at all, but a per-item "
            f"oracle sends them {sum(oracle_share[m] for m in unused):.1%}. They are not "
            f"dominated — they are unreachable. {tau['reading']}"
        ),
    }
    write("12_slots", slots)
    print(f"       never selected by the router: {len(unused)} slots")
    print(f"       a per-item oracle would send them "
          f"{slots['oracle_wants_on_never_selected']:.1%} of traffic — not dominated, unreachable")
    print(f"       {tau['reading']}")
    print(f"       ({time.time() - t:.0f}s)")

    # ------------------------------------------------------- [12] staleness --
    print("\n[12/18] staleness: does the current pool decay too?")
    t = time.time()
    lm_dense = lm.subset_items(dall)
    X_dense = X[dall]
    cfg = staleness.StalenessConfig(
        cutoff=_dt.date(2025, 5, 1), start=_dt.date(2025, 5, 1),
        weeks=14 if args.quick else 26, batch_items=90,
        warmup_items=1200, lam_cost=lam_cost, alpha=0.1, seed=args.seed)
    st = staleness.run(lm_dense, X_dense, chutes_dated(), cfg)
    st_sum = staleness.summarise(st)
    write("13_staleness", {"result": st.as_dict(), "summary": st_sum})
    print(f"       pool grows {st.pool_size[0]} → {st.pool_size[-1]} models over "
          f"{cfg.weeks} weeks")
    print(f"       frozen {st_sum['frozen_start']:+.3f} → {st_sum['frozen_end']:+.3f}; "
          f"rolling {st_sum['rolling_start']:+.3f} → {st_sum['rolling_end']:+.3f}")
    print(f"       crosses below best-single at week "
          f"{st_sum['week_crossed_below_best_single']}")
    print(f"       attribution: new models {st_sum['attribution_new_models']:+.3f}, "
          f"fresher data {st_sum['attribution_fresher_data']:+.3f}")
    print(f"       ({time.time() - t:.0f}s)")

    # ------------------------------------------------------- [13] coldstart --
    print("\n[13/18] cold start: how many probes before a new model is usable?")
    t = time.time()
    grid = (0, 100, 500) if args.quick else (0, 25, 100, 250, 500, 1000)
    cs = coldstart_sc.leave_one_model_out(
        lm, X, train, test, chutes_dated(), probe_grid=grid, lam_cost=lam_cost,
        n_lowrank_items=2000, seed=args.seed)
    write("14_coldstart", cs)
    cs_sum = cs["summary"]
    print(f"       models with a material onboarding gap: "
          f"{len(cs_sum['material_models'])} of {lm.n_models}")
    print(f"       probe items needed (material models): "
          f"{cs_sum['median_probe_items_material']}")
    print(f"       ({time.time() - t:.0f}s)")

    # --------------------------------------------------------- [14] latency --
    print("\n[14/18] latency: what the corpus can and cannot support")
    t = time.time()
    lat = latency.run(lm, X, tokens_in, train, test, lam_cost=lam_cost)
    write("15_latency", lat)
    print(f"       {lat['throughput_fit']['verdict']}")
    r0 = lat["lam_latency_sweep"][0]
    rb = min(lat["lam_latency_sweep"], key=lambda s_: s_["p95_tokens"])
    print(f"       routed p95 {lat['routed']['p95_tokens']:,.0f} output tokens, "
          f"p99 {lat['routed']['p99_tokens']:,.0f}")
    print(f"       latency term on: p95 {r0['p95_tokens']:,.0f} → {rb['p95_tokens']:,.0f} "
          f"tokens for {rb['quality'] - r0['quality']:+.4f} quality")
    print(f"       ({time.time() - t:.0f}s)")


    # ----------------------------------------------------------- [15] rigor --
    print("\n[15/18] rigor: confidence intervals on every headline")
    t = time.time()
    boot = rigor.bootstrap_headlines(lm, X, tokens_in, train, test, lam_cost=lam_cost)
    write("16_bootstrap", boot)
    print(f"       {boot['reading']}")
    qb = boot["quality_vs_best_single"]
    if qb["lo"] <= 1.0 <= qb["hi"]:
        print("       the quality interval includes 100% — matching the best single "
              "model is supported; losing to it is not")
    print(f"       ({time.time() - t:.0f}s)")

    # ------------------------------------------------- [16] domain stats --
    print("\n[16/18] domains: paired SEs with a family-wise correction")
    t = time.time()
    dom = rigor.domain_significance(lm, X, tokens_in, train, test, lam_cost=lam_cost)
    write("17_domains", dom)
    print(f"       {dom['reading']}")
    print(f"       ({time.time() - t:.0f}s)")

    # --------------------------------------------- [17] replication --
    print("\n[17/18] replication: the coverage finding on a disjoint pool")
    t = time.time()
    rep = rigor.replicate_coverage_bias(seed=args.seed)
    mix = rigor.workload_mix(lm, X, tokens_in, train, test, lam_cost=lam_cost)
    write("18_replication", {"coverage_bias": rep, "workload_mix": mix})
    print(f"       {rep['reading']}")
    print(f"       {mix['reading']}")
    print(f"       ({time.time() - t:.0f}s)")

    # ------------------------------------------------------ [18] baselines --
    print("\n[18/18] baselines: published routing strategies on the same items")
    t = time.time()
    base = baselines.run(lm, X, tokens_in, train, test, lam_cost=lam_cost, seed=args.seed)
    write("19_baselines", base)
    print(f"       {base['reading']}")
    print(f"       ({time.time() - t:.0f}s)")

    # -------------------------------------------------------------- exports --
    payload = chutes.frontend_payload(lm, evaluation, sweep, models, diagnostics)
    payload["crossval"] = {
        "savings_pct_mean": s["mean"], "savings_pct_se": s["se"],
        "quality_retained_mean": q["mean"], "quality_retained_se": q["se"],
        "savings_vs_best_single_mean": sb["mean"], "savings_vs_best_single_se": sb["se"],
        "quality_vs_best_single_mean": qb["mean"], "quality_vs_best_single_se": qb["se"],
        "splits": len(seeds),
    }
    payload["best_single_model"] = evaluation["best_single_model"]
    payload["frontier_model_is_dominated"] = evaluation["frontier_model_is_dominated"]
    payload["models_beating_the_frontier_model"] = evaluation["models_beating_the_frontier_model"]
    write("frontend", payload)

    if not args.no_figures:
        from rollingbench import plots
        figs = {
            "chutes_01_pool": plots.chutes_pool(models),
            "chutes_02_frontier": plots.chutes_frontier(sweep, highlight=lam_cost),
            "chutes_03_traffic": plots.chutes_traffic(models),
            "chutes_04_domains": plots.chutes_domains(domains),
            "chutes_05_coverage": plots.chutes_coverage(ablation),
            "chutes_06_loss": plots.chutes_loss(scaling),
            "chutes_07_prices": plots.chutes_prices(shock),
            "chutes_08_staleness": plots.staleness(st.as_dict()),
            "chutes_09_slots": plots.chutes_slots(slots),
            "chutes_10_latency": plots.chutes_latency(lat),
            "chutes_11_baselines": plots.chutes_baselines(base),
        }
        written = plots.save_all(figs, FIGURES)
        print(f"\nfigures: {len(written)} written to {FIGURES.relative_to(ROOT)}/")

    manifest = {
        "proxy_backed": True,
        "disclaimer": payload["disclaimer"],
        "lam_cost": lam_cost,
        "lam_cost_inherited_default": args.lam_cost,
        "seed": args.seed,
        "quick": args.quick,
        "corpus": lm.summary(),
        "dense_core_items": dense_all,
        "feature_dim": int(X.shape[1]),
        "headline": {
            "vs_frontier_model": {
                "model": evaluation["frontier_model"],
                "savings_pct": s["mean"], "savings_pct_se": s["se"],
                "quality_retained": q["mean"], "quality_retained_se": q["se"],
            },
            "vs_best_single": {
                "model": evaluation["best_single_model"],
                "savings_pct": sb["mean"], "savings_pct_se": sb["se"],
                "quality_retained": qb["mean"], "quality_retained_se": qb["se"],
            },
            "frontier_model_is_dominated": evaluation["frontier_model_is_dominated"],
        },
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    write("manifest", manifest)
    print(f"\ndone in {manifest['elapsed_seconds']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
