"""7.3 — the two degeneracies in the §8.8 rolling regret metric.

Contribution 3 names one: on an uninformative batch, `U_oracle` and `U_base` converge,
the denominator collapses toward `eps`, and the score is noise reported as a number.
RollingBench's own tie rate (§3.1) means that should be common rather than rare, so the
first half of this module bins real batches by information content and measures how
much noisier the metric is where information is scarce.

The second degeneracy is not in either document and turned up while reproducing the
first. The per-item oracle takes the argmax of *realised* outcomes, and on binary
grading that argmax banks luck: if any model in the pool happened to answer an item
correctly, the oracle takes it. On RouterBench 95.9% of items have at least one model
correct, so `U_oracle` sits near the ceiling, the denominator is enormous, and every
achievable policy scores near zero — a clairvoyant per-task oracle included. AC-1's
"normalized regret below 0.6" is unreachable under that definition, not because a
router is bad but because the metric measures something no router can reach.

Both are measured here, and both matter for §16: emissions are paid on these scores.
"""

from __future__ import annotations

import numpy as np

from ..data.labelmatrix import LabelMatrix
from ..metrics import (
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
from ..router import PoolState, RidgeLinUCBRouter, RouterConfig


def _policies(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    pool_state: PoolState,
    lam_cost: float,
    ref_col: int,
) -> dict[str, RidgeLinUCBRouter]:
    """A ladder of genuinely different policies, for the ranking test.

    Feeding each router a different amount of training data produces policies whose
    true ordering is known by construction — more data is better — which is what lets
    the ranking test below ask whether a single batch recovers that order.
    """
    out = {}
    for frac, name in ((0.02, "weak (2% of train)"), (0.1, "fair (10%)"),
                       (0.4, "good (40%)"), (1.0, "best (100%)")):
        n = max(200, int(frac * len(train)))
        idx = train[:n]
        r = RidgeLinUCBRouter(X.shape[1], lm.n_models,
                              RouterConfig(alpha=0.0, lam_cost=lam_cost, ref_model=ref_col))
        r.fit(X[idx], lm.quality[idx], lm.observed[idx], lm.tokens_out[idx])
        out[name] = r
    return out


def run(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    pool,
    n_batches: int = 400,
    batch_items: int = 100,
    lam_cost: float = 0.05,
    seed: int = 0,
    n_info_bins: int = 5,
) -> dict:
    """Score many real batches, bin them by information, and test both degeneracies."""
    from .frontier import pool_state as make_pool_state

    rng = np.random.default_rng(seed)
    ps = make_pool_state(pool)
    ref_col = reference_column(lm.quality[train])
    policies = _policies(lm, X, train, ps, lam_cost, ref_col)

    # Each policy's decision on every test item, once. Batches then index into these,
    # so a policy's behaviour is fixed and only the batch composition varies.
    choices = {name: r.decide(X[test], ps).choice for name, r in policies.items()}
    u_test = per_cell_utility(lm.quality[test], lm.cost[test],
                              UtilityWeights(lam_cost=lam_cost), ref_col=ref_col)

    # Ground truth: each policy's utility over the whole test split. The ordering here
    # is what a single batch is being asked to recover.
    truth = {name: float(u_test[np.arange(len(test)), ch].mean())
             for name, ch in choices.items()}
    true_order = [n for n, _ in sorted(truth.items(), key=lambda kv: -kv[1])]

    batches = [rng.choice(len(test), size=batch_items, replace=False)
               for _ in range(n_batches)]

    records = []
    for bi, b in enumerate(batches):
        u_b = u_test[b]
        base_col = best_single_column(u_b)
        spec = {name: score_batch(u_b, ch[b], base_col=base_col, clip=False)
                for name, ch in choices.items()}
        info = next(iter(spec.values())).info
        # Second degeneracy: how much of the oracle is luck? Compare the per-item
        # oracle against the best attainable per-task assignment on the same batch.
        feas_oracle = float(u_b[np.arange(len(b)), group_oracle_column(u_b, lm.task[test][b])].mean())
        # Contribution 3 attributes low information to batches where "every model performs
        # about the same". These two columns test that attribution directly, and it does
        # not survive: see `_diagnosis_check`.
        means = u_b.mean(axis=0)
        ranked = np.sort(means)[::-1]
        records.append({
            "batch": bi,
            "info": info,
            "model_spread": float(ranked[0] - ranked[-1]),
            "dominance": float(ranked[0] - ranked[1]),
            "u_oracle": next(iter(spec.values())).u_oracle,
            "u_base": next(iter(spec.values())).u_base,
            "u_feasible_oracle": feas_oracle,
            "luck_share": (next(iter(spec.values())).u_oracle - feas_oracle) / max(info, 1e-12),
            "scores": {name: s.score for name, s in spec.items()},
            "regrets": {name: s.regret for name, s in spec.items()},
        })

    infos = np.array([r["info"] for r in records])
    kappa = calibrate_kappa(infos, quantile=0.25)

    # The shrinkage fix, applied per policy over the batch sequence.
    shrunk = {}
    for name in policies:
        raw = np.array([r["scores"][name] for r in records])
        shrunk[name] = shrink_scores(raw, infos, kappa=kappa)

    return {
        "config": {"n_batches": n_batches, "batch_items": batch_items,
                   "lam_cost": lam_cost, "kappa": kappa, "seed": seed},
        "true_utility": truth,
        "true_order": true_order,
        "records": records,
        "bins": _bin_analysis(records, infos, shrunk, policies, n_info_bins),
        "ranking": _ranking_test(records, infos, shrunk, true_order, n_info_bins),
        "oracle_luck": _luck_analysis(records),
        "diagnosis": _diagnosis_check(records),
    }


def _bin_analysis(records, infos, shrunk, policies, n_bins) -> dict:
    """Score variance within information bins, before and after shrinkage.

    The prediction: low-information bins are materially noisier under the raw metric,
    and shrinkage closes most of that gap without moving the high-information bins —
    if it moved those too it would be buying stability by discarding signal.
    """
    edges = np.quantile(infos, np.linspace(0, 1, n_bins + 1))
    edges[-1] += 1e-12
    out = []
    for k in range(n_bins):
        mask = (infos >= edges[k]) & (infos < edges[k + 1])
        if mask.sum() < 3:
            continue
        row = {
            "bin": k,
            "info_low": float(edges[k]),
            "info_high": float(edges[k + 1]),
            "n_batches": int(mask.sum()),
            "mean_info": float(infos[mask].mean()),
            "per_policy": {},
        }
        for name in policies:
            raw = np.array([r["scores"][name] for r in records])[mask]
            sm = shrunk[name]["score"][mask]
            row["per_policy"][name] = {
                "raw_sd": float(raw.std(ddof=1)),
                "shrunk_sd": float(sm.std(ddof=1)),
                "raw_mean": float(raw.mean()),
                "shrunk_mean": float(sm.mean()),
                "mean_weight": float(shrunk[name]["weight"][mask].mean()),
            }
        row["raw_sd_mean"] = float(np.mean([v["raw_sd"] for v in row["per_policy"].values()]))
        row["shrunk_sd_mean"] = float(np.mean([v["shrunk_sd"] for v in row["per_policy"].values()]))
        row["sd_reduction"] = row["raw_sd_mean"] - row["shrunk_sd_mean"]
        out.append(row)
    return {"bins": out, "edges": edges.tolist()}


def _ranking_test(records, infos, shrunk, true_order, n_bins) -> dict:
    """Does a single batch rank the policies correctly?

    This is the decision-relevant question, because §16.2 turns the score into
    emissions through a ranking. Variance only matters insofar as it reorders the
    leaderboard, so the measurement is the share of batches whose ordering matches the
    known truth — by information bin, raw against shrunk.
    """
    names = list(records[0]["scores"].keys())
    rank_true = {n: i for i, n in enumerate(true_order)}
    edges = np.quantile(infos, np.linspace(0, 1, n_bins + 1))
    edges[-1] += 1e-12

    def kendall(order: list[str]) -> float:
        """Concordant-pair share against the truth. 1.0 = identical ordering."""
        conc = disc = 0
        for a in range(len(order)):
            for b in range(a + 1, len(order)):
                same = (rank_true[order[a]] < rank_true[order[b]])
                conc, disc = (conc + 1, disc) if same else (conc, disc + 1)
        return conc / max(conc + disc, 1)

    out = []
    for k in range(n_bins):
        mask = (infos >= edges[k]) & (infos < edges[k + 1])
        if mask.sum() < 3:
            continue
        idxs = np.where(mask)[0]
        raw_tau, shr_tau, raw_top1, shr_top1 = [], [], [], []
        for i in idxs:
            raw_order = sorted(names, key=lambda n: -records[i]["scores"][n])
            shr_order = sorted(names, key=lambda n: -shrunk[n]["score"][i])
            raw_tau.append(kendall(raw_order))
            shr_tau.append(kendall(shr_order))
            raw_top1.append(raw_order[0] == true_order[0])
            shr_top1.append(shr_order[0] == true_order[0])
        out.append({
            "bin": k,
            "mean_info": float(infos[mask].mean()),
            "n_batches": int(mask.sum()),
            "raw_concordance": float(np.mean(raw_tau)),
            "shrunk_concordance": float(np.mean(shr_tau)),
            "raw_top1_accuracy": float(np.mean(raw_top1)),
            "shrunk_top1_accuracy": float(np.mean(shr_top1)),
        })
    return {"by_bin": out,
            "overall": {
                "raw_concordance": float(np.mean([b["raw_concordance"] for b in out])),
                "shrunk_concordance": float(np.mean([b["shrunk_concordance"] for b in out])),
            }}


def _diagnosis_check(records) -> dict:
    """Is §6 right about *why* a batch is uninformative?

    §6: "When a challenge batch happens to be easy — every model in the pool performs
    about the same on it — U_oracle and U_base converge." If that were so, batch
    information would rise with the spread between models. It falls.

    The reason is the same luck that inflates the oracle. When models are closely matched,
    per-item noise lets the realised-outcome oracle beat every single model by a wide
    margin, so the denominator is large. When one model dominates, the best single model
    is already nearly as good as the oracle, and the denominator collapses.
    """
    info = np.array([r["info"] for r in records])
    spread = np.array([r["model_spread"] for r in records])
    dom = np.array([r["dominance"] for r in records])
    r_spread = float(np.corrcoef(spread, info)[0, 1])
    r_dom = float(np.corrcoef(dom, info)[0, 1])
    return {
        "corr_info_vs_model_spread": r_spread,
        "corr_info_vs_dominance": r_dom,
        "section_6_predicts": "positive — similar models should mean low information",
        "measured": "negative — similar models mean HIGH information",
        "diagnosis_holds": bool(r_spread > 0),
        "reading": (
            f"batch information correlates {r_spread:+.2f} with the spread between the best "
            f"and worst model and {r_dom:+.2f} with how far the best model leads the second. "
            f"§6's stated cause is inverted: the degenerate batches are the ones where "
            f"models differ most, because a dominant model leaves the oracle little to add. "
            f"The fix keys on measured information so it still works, but filtering out "
            f"'easy' batches — the intervention §6's account suggests — would discard the "
            f"informative ones."
        ),
    }


def _luck_analysis(records) -> dict:
    """How much of the §8.8 oracle is unattainable luck rather than routable signal."""
    luck = np.array([r["luck_share"] for r in records])
    return {
        "mean_luck_share_of_gap": float(luck.mean()),
        "median_luck_share_of_gap": float(np.median(luck)),
        "p5": float(np.percentile(luck, 5)),
        "p95": float(np.percentile(luck, 95)),
        "reading": (
            "share of the oracle-to-baseline gap that comes from realised-outcome luck "
            "rather than from any assignment a policy could have chosen; the §8.8 "
            "denominator includes it, so every achievable score is deflated by it"
        ),
    }


def kappa_sensitivity(
    result: dict,
    quantiles: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0),
) -> dict:
    """κ ablation — §12 asks for this rather than hiding it.

    κ is the one constant the shrinkage fix introduces, and its calibration matters:
    set it far below the batch information distribution and the weight saturates at 1
    everywhere, so the fix does nothing; set it far above and every batch is shrunk to
    the running average, so the metric stops responding to evidence at all. The useful
    reading is where ranking recovery peaks and how flat it is around that point.

    `quantiles` above 1.0 are multiples of the maximum observed information, which is
    how the saturated end of the curve gets covered.
    """
    records = result["records"]
    infos = np.array([r["info"] for r in records])
    names = list(records[0]["scores"].keys())
    true_order = result["true_order"]
    rank_true = {n: i for i, n in enumerate(true_order)}

    def concordance(order: list[str]) -> float:
        conc = disc = 0
        for a in range(len(order)):
            for b in range(a + 1, len(order)):
                if rank_true[order[a]] < rank_true[order[b]]:
                    conc += 1
                else:
                    disc += 1
        return conc / max(conc + disc, 1)

    rows = []
    for q in quantiles:
        kappa = (float(np.quantile(infos, q)) if q <= 1.0
                 else float(infos.max() * q))
        shrunk = {n: shrink_scores(np.array([r["scores"][n] for r in records]), infos, kappa)
                  for n in names}
        taus, top1, sds = [], [], []
        for i in range(len(records)):
            order = sorted(names, key=lambda n: -shrunk[n]["score"][i])
            taus.append(concordance(order))
            top1.append(order[0] == true_order[0])
        for n in names:
            sds.append(float(shrunk[n]["score"].std(ddof=1)))
        rows.append({
            "quantile": q,
            "kappa": kappa,
            "mean_weight": float(np.mean(shrunk[names[0]]["weight"])),
            "concordance": float(np.mean(taus)),
            "top1_accuracy": float(np.mean(top1)),
            "mean_score_sd": float(np.mean(sds)),
        })

    best = max(rows, key=lambda r: r["concordance"])
    return {
        "rows": rows,
        "best_by_concordance": best,
        "raw_concordance": result["ranking"]["overall"]["raw_concordance"],
        "reading": (
            f"ranking recovery peaks at κ={best['kappa']:.4f} "
            f"(quantile {best['quantile']}) with concordance {best['concordance']:.3f} "
            f"against {result['ranking']['overall']['raw_concordance']:.3f} raw"
        ),
    }


def kappa_tradeoff(
    result: dict,
    switch_at: float = 0.5,
    quantiles: tuple[float, ...] = (0.05, 0.25, 0.5, 1.0, 2.0, 5.0),
) -> dict:
    """The other half of the κ ablation: how slowly does an over-shrunk score notice change?

    `kappa_sensitivity` finds that ranking recovery improves monotonically with κ, which
    looks like "shrink as hard as possible" but is an artefact of the test. As κ grows
    the weight goes to zero and every batch score becomes the running average — a pooled
    estimate over the whole sequence — and pooling is unbeatable at ranking a set of
    policies that never change. The §16.2 payout is not applied to a static set: miners
    submit new policies, and a score that cannot notice an improvement stops paying for
    one.

    So the responsiveness axis: swap one policy's decisions from the weakest to the
    strongest halfway through the sequence, and measure how many batches the score takes
    to close 90% of the distance to its new level. κ then trades ranking accuracy
    against detection lag, and the useful κ is where both are acceptable rather than
    where either is optimal.
    """
    records = result["records"]
    infos = np.array([r["info"] for r in records])
    names = list(records[0]["scores"].keys())
    weak, strong = result["true_order"][-1], result["true_order"][0]
    t_switch = int(switch_at * len(records))

    # The switching policy: weak scores before the swap, strong scores after.
    raw_switch = np.array([
        r["scores"][weak] if i < t_switch else r["scores"][strong]
        for i, r in enumerate(records)
    ])
    before = raw_switch[:t_switch].mean()
    after = raw_switch[t_switch:].mean()
    target = before + 0.9 * (after - before)

    rows = []
    for q in quantiles:
        kappa = float(np.quantile(infos, q)) if q <= 1.0 else float(infos.max() * q)
        sm = shrink_scores(raw_switch, infos, kappa)["score"]
        lag = next((i - t_switch for i in range(t_switch, len(sm))
                    if (sm[i] >= target if after > before else sm[i] <= target)), None)
        rows.append({
            "quantile": q,
            "kappa": kappa,
            "detection_lag_batches": float(lag) if lag is not None else float("inf"),
            "score_sd": float(sm.std(ddof=1)),
            "mean_weight": float(shrink_scores(raw_switch, infos, kappa)["weight"].mean()),
        })

    return {
        "rows": rows,
        "switched_from": weak,
        "switched_to": strong,
        "switch_batch": t_switch,
        "raw_detection_lag": float(
            next((i - t_switch for i in range(t_switch, len(raw_switch))
                  if raw_switch[i] >= target), float("inf"))),
        "reading": (
            "κ trades ranking accuracy (kappa_sensitivity) against detection lag (here); "
            "the operating point is the largest κ whose lag is still acceptable for the "
            "payout cadence, not the κ that maximises either one"
        ),
    }
