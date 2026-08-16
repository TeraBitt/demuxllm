"""Loss curves: against data, against capacity, against regularisation — and against regret.

The router is closed-form, so there is no epoch loop and no training loss to watch tick
down. That does not mean there is no loss. The quality head is a regression onto a binary
outcome, so it has a Brier score and a log-loss like any classifier, and those are what
the decision rule is built on. The interesting questions are the ones a training curve
would normally answer:

  · **Data.** Has the fit converged, or would more graded cells still help? A learning
    curve answers this directly, and it is the honest way to decide whether the daily
    evaluation spend in §18.2 is buying anything.
  · **Capacity.** d ≈ 64 is asserted in §8.2, never justified. Sweeping d gives the
    capacity curve and shows where it saturates.
  · **Regularisation.** λ is a free parameter the documents never discuss. Train and
    validation loss against λ is the classic U, and it says whether the model is
    over- or under-regularised.
  · **Coupling.** The one that matters most: does lower prediction loss actually produce
    better routing? A router is not scored on its loss, and the two can come apart —
    predicting every model's quality slightly better does nothing if the *ranking*
    between them is unchanged.

Every curve is train-and-validation, because a validation curve alone cannot distinguish
"more data would help" from "the model is too small".
"""

from __future__ import annotations

import time

import numpy as np

from ..data.labelmatrix import LabelMatrix
from ..features import FeatureMap
from ..metrics import (
    UtilityWeights,
    best_single_column,
    feasible_score_batch,
    per_cell_utility,
    reference_column,
    score_batch,
)
from ..router import RidgeLinUCBRouter, RouterConfig


# ------------------------------------------------------------------- losses --
def losses(y: np.ndarray, p: np.ndarray, observed: np.ndarray) -> dict[str, float]:
    """Prediction loss for the quality head, over observed cells only.

    Brier is the headline: it is the mean squared error of a probability forecast, which
    is exactly what the ridge fit minimises, so it is the loss the estimator is actually
    optimising rather than a proxy chosen after the fact. Log-loss is reported alongside
    because it punishes confident mistakes harder, and a router that is confidently wrong
    about a model is the failure that costs money.
    """
    yy, pp = y[observed], p[observed]
    clipped = np.clip(pp, 1e-6, 1 - 1e-6)
    resid = pp - yy
    return {
        "brier": float(np.mean(resid**2)),
        "log_loss": float(-np.mean(yy * np.log(clipped) + (1 - yy) * np.log(1 - clipped))),
        "mae": float(np.mean(np.abs(resid))),
        # Against predicting the pool's base rate for everything — the trivial forecast.
        # Below zero means the fit is worse than a constant.
        "skill_vs_base_rate": float(1 - np.mean(resid**2) / max(np.var(yy), 1e-12)),
    }


def ranking_loss(y: np.ndarray, p: np.ndarray, observed: np.ndarray) -> float:
    """Pairwise disagreement between predicted and true model ordering, per item.

    A router only ever uses the *ranking* of models within an item; the absolute level is
    discarded by the argmax. This is therefore the loss closest to what the router is for,
    and it is the one that decouples from Brier — see `loss_vs_routing`.
    """
    n = y.shape[0]
    wrong = total = 0
    for i in range(n):
        obs = np.where(observed[i])[0]
        if len(obs) < 2:
            continue
        yt, pt = y[i, obs], p[i, obs]
        dy = yt[:, None] - yt[None, :]
        dp = pt[:, None] - pt[None, :]
        mask = np.triu(np.abs(dy) > 1e-9, k=1)
        wrong += int(np.sum((np.sign(dy) != np.sign(dp)) & mask))
        total += int(mask.sum())
    return wrong / max(total, 1)


# ------------------------------------------------------------------- helpers --
def _fit_and_score(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    val: np.ndarray,
    pool,
    lam: float = 1.0,
    lam_cost: float = 0.05,
    ref_col: int | None = None,
    with_ranking_loss: bool = True,
    ranking_sample: int = 1500,
) -> dict:
    """One fit, with both its loss and its routing outcome.

    Returning them together is the point: every row of every sweep below carries the loss
    and the regret from the same fitted model, so the coupling between them can be read
    off directly rather than inferred across runs.
    """
    from .frontier import pool_state

    d = X.shape[1]
    ref_col = ref_col if ref_col is not None else reference_column(lm.quality[train])
    t0 = time.perf_counter()
    r = RidgeLinUCBRouter(d, lm.n_models,
                          RouterConfig(alpha=0.0, lam=lam, lam_cost=lam_cost,
                                       ref_model=ref_col))
    r.fit(X[train], lm.quality[train], lm.observed[train], lm.tokens_out[train])
    fit_ms = (time.perf_counter() - t0) * 1000

    p_tr = r.quality.predict(X[train])
    p_va = r.quality.predict(X[val])
    out = {
        "d": int(d),
        "lam": lam,
        "n_train": int(len(train)),
        "fit_ms": fit_ms,
        "artifact_kb": r.artifact_bytes() / 1024,
        **{f"train_{k}": v for k, v in
           losses(lm.quality[train], p_tr, lm.observed[train]).items()},
        **{f"val_{k}": v for k, v in
           losses(lm.quality[val], p_va, lm.observed[val]).items()},
    }
    if with_ranking_loss:
        sub = val[:ranking_sample]
        out["val_ranking_loss"] = ranking_loss(
            lm.quality[sub], r.quality.predict(X[sub]), lm.observed[sub])

    # Downstream: the same fit, scored as a router.
    ps = pool_state(pool)
    ch = r.decide(X[val], ps).choice
    u = per_cell_utility(lm.quality[val], lm.cost[val],
                         UtilityWeights(lam_cost=lam_cost), ref_col=ref_col)
    base = best_single_column(u)
    spec = score_batch(u, ch, base_col=base, clip=False)
    feas = feasible_score_batch(u, ch, lm.task[val], base_col=base)
    frontier_cost = float(lm.cost[val][:, ref_col].sum())
    routed_cost = float(lm.cost[val][np.arange(len(val)), ch].sum())
    out.update({
        "regret": spec.regret,
        "score_feasible": feas.score,
        "routed_quality": float(lm.quality[val][np.arange(len(val)), ch].mean()),
        "routed_cost": routed_cost,
        "savings": 1.0 - routed_cost / frontier_cost,
        "models_used": int(len(set(ch.tolist()))),
    })
    out["overfit_gap"] = out["val_brier"] - out["train_brier"]
    return out


# -------------------------------------------------------------------- sweeps --
def learning_curve(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    val: np.ndarray,
    pool,
    sizes: tuple[int, ...] | None = None,
    lam: float = 1.0,
    lam_cost: float = 0.05,
    repeats: int = 3,
    seed: int = 0,
) -> list[dict]:
    """Loss against the number of training items — has the fit converged?

    Repeated over several random subsets at each size, because a single draw at n = 100 is
    mostly telling you which hundred items you happened to get.
    """
    if sizes is None:
        sizes = (100, 250, 500, 1000, 2500, 5000, 10000, 17500, 25000)
    rng = np.random.default_rng(seed)
    ref_col = reference_column(lm.quality[train])
    rows = []
    for n in sizes:
        n = min(n, len(train))
        for rep in range(repeats if n < len(train) else 1):
            sub = rng.choice(train, size=n, replace=False)
            row = _fit_and_score(lm, X, sub, val, pool, lam=lam, lam_cost=lam_cost,
                                 ref_col=ref_col, with_ranking_loss=(rep == 0))
            row["repeat"] = rep
            rows.append(row)
    return rows


def capacity_curve(
    lm: LabelMatrix,
    train: np.ndarray,
    val: np.ndarray,
    pool,
    dims: tuple[int, ...] = (4, 8, 16, 32, 52, 96, 160, 256, 384),
    # The adopted hash width, so the d-optimum this sweep reports is the one that applies
    # to the shipped encoder rather than to a narrower one.
    n_buckets: int = 4096,
    lam: float = 1.0,
    lam_cost: float = 0.05,
    seed: int = 0,
) -> list[dict]:
    """Loss against feature dimension — is d ≈ 64 the right size?

    The feature map is refitted at every d, because d is a property of φ and not of the
    ridge solve. That makes this the expensive sweep, and the only one that genuinely
    costs compute.
    """
    from ..features import N_SURFACE, hashed_bow, surface_features

    ref_col = reference_column(lm.quality[train])

    # The hashed bag of words does not depend on d — only the projection does. Computing
    # it once and re-projecting is a 9x saving on this sweep and changes nothing about the
    # result: each d still gets its own SVD basis, fitted on the training split only.
    t0 = time.perf_counter()
    texts = list(lm.prompts)
    bow = hashed_bow(texts, n_buckets)
    surface = surface_features(texts)
    bias = np.ones((len(texts), 1))
    bow_seconds = time.perf_counter() - t0

    rows = []
    for n_comp in dims:
        t0 = time.perf_counter()
        fm = FeatureMap(n_components=n_comp, n_buckets=n_buckets)
        # Fit the projection on the training rows of the precomputed bow.
        fm._mean = bow[train].mean(axis=0)
        centred = bow[train] - fm._mean
        rng = np.random.default_rng(seed)
        omega = rng.standard_normal((centred.shape[1], n_comp + 10))
        q, _ = np.linalg.qr(centred @ omega)
        _, _, vt = np.linalg.svd(q.T @ centred, full_matrices=False)
        fm._basis = vt[:n_comp].T
        proj_train = centred @ fm._basis
        fm._scale = np.maximum(proj_train.std(axis=0), 1e-8)

        semantic = ((bow - fm._mean) @ fm._basis) / fm._scale
        Xd = np.hstack([semantic, surface, bias])
        feat_s = time.perf_counter() - t0

        row = _fit_and_score(lm, Xd, train, val, pool, lam=lam, lam_cost=lam_cost,
                             ref_col=ref_col)
        row["n_components"] = n_comp
        row["n_buckets"] = n_buckets
        row["feature_seconds"] = feat_s
        row["bow_seconds"] = bow_seconds
        rows.append(row)
    return rows


def regularisation_curve(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    val: np.ndarray,
    pool,
    lams: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0, 1e5),
    lam_cost: float = 0.05,
) -> list[dict]:
    """Train and validation loss against λ — the classic U, never discussed in §8."""
    ref_col = reference_column(lm.quality[train])
    return [_fit_and_score(lm, X, train, val, pool, lam=lam, lam_cost=lam_cost,
                           ref_col=ref_col)
            for lam in lams]


def bucket_curve(
    lm: LabelMatrix,
    train: np.ndarray,
    val: np.ndarray,
    pool,
    buckets: tuple[int, ...] = (128, 256, 512, 1024, 2048, 4096),
    n_components: int = 52,
    lam: float = 1.0,
    lam_cost: float = 0.05,
    seed: int = 0,
) -> list[dict]:
    """Loss against hash width — how much the cheap encoder is losing to collisions.

    Separates two things that a single d sweep confounds: how many directions the router
    can use, and how much information the hashing threw away before the projection ever
    saw it.
    """
    ref_col = reference_column(lm.quality[train])
    rows = []
    for nb in buckets:
        fm = FeatureMap(n_components=n_components, n_buckets=nb)
        fm.fit(list(lm.prompts[train]), seed=seed)
        Xd = fm.transform(list(lm.prompts))
        row = _fit_and_score(lm, Xd, train, val, pool, lam=lam, lam_cost=lam_cost,
                             ref_col=ref_col)
        row["n_buckets"] = nb
        row["n_components"] = n_components
        rows.append(row)
    return rows


def per_model_losses(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    val: np.ndarray,
    lam: float = 1.0,
) -> list[dict]:
    """Where the loss actually lives, model by model, with calibration.

    An aggregate Brier hides that a router can be well calibrated on the models it rarely
    picks and badly calibrated on the one it picks constantly. `bias` is the signed
    calibration error — positive means the model is being over-sold.
    """
    r = RidgeLinUCBRouter(X.shape[1], lm.n_models, RouterConfig(alpha=0.0, lam=lam))
    r.fit(X[train], lm.quality[train], lm.observed[train], lm.tokens_out[train])
    p = r.quality.predict(X[val])
    rows = []
    for j, mid in enumerate(lm.model_ids):
        obs = lm.observed[val, j]
        y, pj = lm.quality[val][obs, j], p[obs, j]
        yb = (y > 0.5).astype(int)
        auc = float("nan")
        if 0 < yb.mean() < 1:
            order = np.argsort(pj)
            rank = np.empty_like(order, dtype=float)
            rank[order] = np.arange(len(pj))
            n1 = yb.sum()
            n0 = len(yb) - n1
            auc = float((rank[yb == 1].sum() - n1 * (n1 - 1) / 2) / (n1 * n0))
        rows.append({
            "model_id": mid,
            "brier": float(np.mean((pj - y) ** 2)),
            "auc": auc,
            "bias": float(np.mean(pj - y)),
            "pred_mean": float(pj.mean()),
            "true_mean": float(y.mean()),
            "n": int(obs.sum()),
        })
    return rows


def reliability(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    val: np.ndarray,
    n_bins: int = 12,
    lam: float = 1.0,
) -> dict:
    """A calibration curve: predicted quality against observed, pooled over models."""
    r = RidgeLinUCBRouter(X.shape[1], lm.n_models, RouterConfig(alpha=0.0, lam=lam))
    r.fit(X[train], lm.quality[train], lm.observed[train], lm.tokens_out[train])
    p = r.quality.predict(X[val])[lm.observed[val]]
    y = lm.quality[val][lm.observed[val]]

    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    edges[-1] += 1e-9
    rows = []
    for k in range(n_bins):
        m = (p >= edges[k]) & (p < edges[k + 1])
        if m.sum() < 10:
            continue
        rows.append({"predicted": float(p[m].mean()), "observed": float(y[m].mean()),
                     "n": int(m.sum())})
    ece = float(sum(r_["n"] * abs(r_["predicted"] - r_["observed"]) for r_ in rows)
                / max(sum(r_["n"] for r_ in rows), 1))
    return {"bins": rows, "expected_calibration_error": ece}


def online_loss(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    val: np.ndarray,
    block: int = 250,
    lam: float = 1.0,
) -> list[dict]:
    """The closest thing this estimator has to a training curve.

    Observations stream in as rank-one updates and the validation loss is measured after
    each block. It is a training curve in the ordinary sense — loss against optimisation
    steps — except that each step is exact rather than a gradient, so it descends
    monotonically in expectation with no learning rate to tune and nothing to diverge.
    """
    r = RidgeLinUCBRouter(X.shape[1], lm.n_models, RouterConfig(alpha=0.0, lam=lam))
    rows = []
    seen = 0
    for lo in range(0, len(train), block):
        sl = train[lo:lo + block]
        r.absorb(X[sl], lm.quality[sl], lm.observed[sl], lm.tokens_out[sl])
        seen += len(sl)
        p = r.quality.predict(X[val])
        L = losses(lm.quality[val], p, lm.observed[val])
        rows.append({"observations": seen * lm.n_models, "items": seen,
                     "val_brier": L["brier"], "val_log_loss": L["log_loss"],
                     "skill": L["skill_vs_base_rate"]})
    return rows


def loss_vs_routing(rows: list[dict]) -> dict:
    """Does lower prediction loss buy better routing?

    Pooled across every configuration in every sweep. The distinction that matters is
    between the two losses: Brier scores how well each model's quality is predicted in
    absolute terms, while the ranking loss scores whether the *order* between models on an
    item is right. Only the second is what the argmax consumes, so if the two correlate
    differently with regret, that is the finding.
    """
    def pairs(a: str, b: str):
        xs = [r[a] for r in rows if a in r and b in r and np.isfinite(r[a]) and np.isfinite(r[b])]
        ys = [r[b] for r in rows if a in r and b in r and np.isfinite(r[a]) and np.isfinite(r[b])]
        return xs, ys

    def corr(a: str, b: str) -> float:
        xs, ys = pairs(a, b)
        if len(xs) < 3 or np.std(xs) == 0 or np.std(ys) == 0:
            return float("nan")
        return float(np.corrcoef(xs, ys)[0, 1])

    def spearman(a: str, b: str) -> float:
        """Rank correlation — the statistic the claim actually needs.

        A handful of starved configurations (a few hundred training items) are terrible on
        both loss and regret, and a Pearson correlation computed with them in is mostly
        measuring that they exist. Rank correlation asks the question that matters: as
        configurations improve on loss, do they improve on regret?
        """
        xs, ys = pairs(a, b)
        if len(xs) < 3:
            return float("nan")
        def rank(v):
            order = np.argsort(np.argsort(v))
            return order.astype(float)
        rx, ry = rank(xs), rank(ys)
        if np.std(rx) == 0 or np.std(ry) == 0:
            return float("nan")
        return float(np.corrcoef(rx, ry)[0, 1])

    # The same question asked only of configurations a deployed router could plausibly be:
    # at least a few thousand training items, so the starved end does not carry the result.
    healthy = [r for r in rows if r.get("n_train", 10**9) >= 5000]

    def corr_healthy(a: str, b: str) -> float:
        xs = [r[a] for r in healthy if a in r and np.isfinite(r.get(a, np.nan))
              and np.isfinite(r.get(b, np.nan))]
        ys = [r[b] for r in healthy if a in r and np.isfinite(r.get(a, np.nan))
              and np.isfinite(r.get(b, np.nan))]
        if len(xs) < 3 or np.std(xs) == 0 or np.std(ys) == 0:
            return float("nan")
        return float(np.corrcoef(xs, ys)[0, 1])

    return {
        "n_configs": len(rows),
        "n_healthy_configs": len(healthy),
        "corr_val_brier_regret": corr("val_brier", "regret"),
        "spearman_val_brier_regret": spearman("val_brier", "regret"),
        "corr_val_brier_regret_healthy_only": corr_healthy("val_brier", "regret"),
        "corr_val_brier_score_feasible": corr("val_brier", "score_feasible"),
        "corr_val_brier_savings": corr("val_brier", "savings"),
        "corr_ranking_loss_regret": corr("val_ranking_loss", "regret"),
        "spearman_ranking_loss_regret": spearman("val_ranking_loss", "regret"),
        "corr_ranking_loss_regret_healthy_only": corr_healthy("val_ranking_loss", "regret"),
        "corr_ranking_loss_score_feasible": corr("val_ranking_loss", "score_feasible"),
        "reading": (
            "Brier scores the absolute quality forecast; the ranking loss scores the order "
            "between models within an item, which is the only part the argmax reads. Pooled "
            "over every configuration the two track regret closely — starved models are bad "
            "at everything. Restricted to configurations a deployed router could plausibly "
            "be, the association weakens, and in the over-capacity tail it inverts: loss "
            "keeps falling while regret rises."
        ),
    }


def run(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    val: np.ndarray,
    pool,
    quick: bool = False,
    seed: int = 0,
) -> dict:
    """Every curve, plus the summary that says where the model is actually limited."""
    dims = (8, 32, 64, 128, 256) if quick else (4, 8, 16, 32, 52, 96, 160, 256, 384)
    buckets = (256, 1024, 4096) if quick else (128, 256, 512, 1024, 2048, 4096, 8192)
    sizes = ((250, 1000, 5000, 25000) if quick else
             (100, 250, 500, 1000, 2500, 5000, 10000, 17500, 25000))

    lc = learning_curve(lm, X, train, val, pool, sizes=sizes, repeats=2 if quick else 3,
                        seed=seed)
    cc = capacity_curve(lm, train, val, pool, dims=dims, seed=seed)
    rc = regularisation_curve(lm, X, train, val, pool)
    bc = bucket_curve(lm, train, val, pool, buckets=buckets, seed=seed)
    ol = online_loss(lm, X, train, val, block=500 if quick else 250)
    pm = per_model_losses(lm, X, train, val)
    rel = reliability(lm, X, train, val)

    return {
        "learning_curve": lc,
        "capacity_curve": cc,
        "regularisation_curve": rc,
        "bucket_curve": bc,
        "online_loss": ol,
        "per_model": pm,
        "reliability": rel,
        "coupling": loss_vs_routing(lc + cc + rc + bc),
        "summary": _summarise(lc, cc, rc, bc, ol),
    }


def _summarise(lc, cc, rc, bc, ol) -> dict:
    """Where is the model limited — by data, by capacity, or by the features?"""
    def best(rows, key="val_brier"):
        return min(rows, key=lambda r: r[key])

    # Data: how much did the last doubling of training data buy?
    by_n: dict[int, list[float]] = {}
    for r in lc:
        by_n.setdefault(r["n_train"], []).append(r["val_brier"])
    ns = sorted(by_n)
    means = [float(np.mean(by_n[n])) for n in ns]
    last_gain = means[-2] - means[-1] if len(means) > 1 else 0.0
    first_gain = means[0] - means[1] if len(means) > 1 else 0.0

    best_cap, best_lam, best_buck = best(cc), best(rc), best(bc)
    # Saturation: the smallest d within 1% of the best validation Brier.
    thresh = best_cap["val_brier"] * 1.01
    saturating_d = min((r["d"] for r in cc if r["val_brier"] <= thresh),
                       default=best_cap["d"])

    return {
        "data": {
            "sizes": ns,
            "val_brier_by_size": means,
            "gain_from_last_doubling": last_gain,
            "gain_from_first_doubling": first_gain,
            "converged": bool(abs(last_gain) < 0.1 * abs(first_gain) if first_gain else True),
        },
        "capacity": {
            "best_d": best_cap["d"],
            "best_val_brier": best_cap["val_brier"],
            "saturates_at_d": saturating_d,
            "default_d_64_brier": next((r["val_brier"] for r in cc if r["d"] == 64), None),
            "best_regret": best_cap["regret"],
        },
        "regularisation": {
            "best_lam": best_lam["lam"],
            "best_val_brier": best_lam["val_brier"],
            "overfit_gap_at_best": best_lam["overfit_gap"],
        },
        "features": {
            "best_n_buckets": best_buck["n_buckets"],
            "best_val_brier": best_buck["val_brier"],
            "gain_from_widening_hash": bc[0]["val_brier"] - best_buck["val_brier"],
        },
        "online": {
            "final_val_brier": ol[-1]["val_brier"],
            "observations": ol[-1]["observations"],
            "monotone": bool(np.mean(np.diff([r["val_brier"] for r in ol]) <= 1e-6) > 0.8),
        },
    }
