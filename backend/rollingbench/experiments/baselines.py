"""Published routing strategies, reimplemented on this pool.

`PUBLISHABILITY.md` listed "zero comparisons to published routers" as the obvious
reviewer question with no answer. This is the answer. Six families are implemented
against the same held-out items, the same price table and the same feature map, so
the only thing that differs is the decision rule — and each is swept across its own
cost/quality dial, because comparing single operating points mostly measures where
each rule's threshold happened to land.

    cascade         FrugalGPT-style. Try models cheapest-first and stop when a
                    verifier accepts the answer. Crucially it *pays for every
                    attempt*, which is the cost the single-shot rules avoid.
    matrix_factor   RouteLLM-style. Complete the (item, model) outcome matrix by
                    low-rank factorisation and route on the completed row, rather
                    than fitting one regression per model.
    hybrid_llm      HybridLLM-style. Two models — cheapest and strongest — and a
                    learned predictor of the quality *gap* between them.
    classifier_router  Predict which model wins rather than how each will score.
                    Trained on the ordering, which is the half we estimate well.
    knn_router      Retrieval routing: let the k most similar graded questions vote.
                    No parameters; the outcome matrix is the model.
    cheapest_that_fits  The trivial policy a sensible engineer writes first: send
                    everything to the cheapest model above a fixed quality bar,
                    chosen on the training split.

These are reimplementations, not the authors' code, and the comparison is bounded by
that: each is the rule as described, tuned on the same training split, without the
engineering its authors put into it. A negative result here means "this rule, on this
pool" — not "this paper is wrong".

The cascade in particular is given a verifier it would not have in production. See
`cascade` for what that buys it and why the number is an upper bound.
"""

from __future__ import annotations

import numpy as np

from ..catalog import CHUTES_CATALOG
from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    frontier_reference_column,
    per_cell_utility,
)
from .chutes import _dense, _tokens_in_per_item, pool_state, train_router


def _price_order() -> np.ndarray:
    """Column indices cheapest-first, by blended price."""
    return np.argsort([m.blended_price for m in CHUTES_CATALOG])


def cascade(
    q_hat: np.ndarray,
    quality: np.ndarray,
    cost: np.ndarray,
    tau: float,
    *,
    verifier: str = "predicted",
) -> dict:
    """FrugalGPT-style cascade: cheapest first, escalate until accepted.

    Two verifiers, and the difference between them is the whole question.

    `predicted` — escalate while the router's own q̂ for the current model is below
    τ. This is implementable: it needs no answer, only a prediction.

    `oracle` — escalate while the *realised* outcome was wrong. This is not
    implementable (it requires knowing the answer was wrong, which is the problem
    routing exists to avoid) and is reported only as an upper bound on what a
    perfect answer-verifier would buy.

    Either way the cascade pays for every call it makes, which is what makes it a
    different economic object from a single-shot router: a chain that ends at the
    third model has paid for three answers and delivered one.
    """
    n, k = quality.shape
    order = _price_order()
    chosen = np.full(n, order[-1])
    spend = np.zeros(n)
    attempts = np.zeros(n, dtype=int)
    settled = np.zeros(n, dtype=bool)

    for j in order:
        live = ~settled
        if not live.any():
            break
        spend[live] += cost[live, j]
        attempts[live] += 1
        if verifier == "oracle":
            accept = quality[:, j] > 0.5
        else:
            accept = q_hat[:, j] >= tau
        take = live & accept
        chosen[take] = j
        settled |= take

    # Anything never accepted has run the whole ladder and keeps the dearest answer.
    chosen[~settled] = order[-1]
    rows = np.arange(n)
    return {
        "choice": chosen,
        # Per item, not just the mean: `publish.baseline_margin_intervals` resamples
        # items and a cascade's bill is not `cost[row, choice]` — it paid for every
        # attempt, so its spend has to travel with its choice.
        "spend": spend,
        "quality": float(quality[rows, chosen].mean()),
        "cost_per_call_usd": float(spend.mean()),
        "mean_attempts": float(attempts.mean()),
        "wasted_spend_share": float(
            1.0 - cost[rows, chosen].sum() / max(spend.sum(), 1e-12)),
    }


def matrix_factor(
    lm: LabelMatrix,
    train: np.ndarray,
    test: np.ndarray,
    X: np.ndarray,
    rank: int = 8,
    lam_cost: float = 0.2,
    seed: int = 0,
) -> dict:
    """RouteLLM-style: complete the outcome matrix, then route on the completed row.

    Item factors are learned on the training split by truncated SVD of the observed
    outcome matrix; a new item's factors are unavailable at serving time, so they
    are predicted from φ(q) by ridge — which is exactly the §5.1 bridge, and it is
    the step that decides whether this family works at all.
    """
    obs_tr = lm.observed[train]
    Q = np.where(obs_tr, lm.quality[train], np.nan)
    col_mean = np.nanmean(Q, axis=0)
    Q = np.where(np.isnan(Q), col_mean[None, :], Q)
    Qc = Q - col_mean[None, :]

    U, S, Vt = np.linalg.svd(Qc, full_matrices=False)
    U, S, Vt = U[:, :rank], S[:rank], Vt[:rank]
    item_factors = U * S                       # (n_train, rank)

    # Bridge: features -> item factors, so an unseen item can be placed.
    Xtr = X[train]
    A = Xtr.T @ Xtr + 1.0 * np.eye(Xtr.shape[1])
    W = np.linalg.solve(A, Xtr.T @ item_factors)
    r2 = float(1.0 - ((item_factors - Xtr @ W) ** 2).sum()
               / max(((item_factors - item_factors.mean(0)) ** 2).sum(), 1e-12))

    pred = (X[test] @ W) @ Vt + col_mean[None, :]

    q, c = lm.quality[test], lm.cost[test]
    rows = np.arange(len(test))
    fc = frontier_reference_column(lm.quality[_dense(lm, train)])
    cost_ref = np.maximum(c[:, [fc]], 1e-12)
    choice = (pred - lam_cost * (c / cost_ref)).argmax(axis=1)
    return {
        "choice": choice,
        "rank": rank,
        "bridge_r2": r2,
        "quality": float(q[rows, choice].mean()),
        "cost_per_call_usd": float(c[rows, choice].mean()),
    }


def hybrid_llm(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    threshold: float,
    *,
    seed: int = 0,
) -> dict:
    """HybridLLM-style: one small model, one large, and a learned gap predictor.

    The published form routes between exactly two models by predicting the *quality
    gap* between them and sending the query to the large one only when the gap is
    expected to matter. The pair is chosen the way the paper's setting implies —
    the cheapest model and the highest-quality one — and the gap regressor is a
    ridge on the same φ, so nothing but the decision rule differs from our router.

    Included because it is the strongest argument that a thirteen-way router is
    over-engineered: if two models capture most of the value, the other eleven are
    inventory rather than product.
    """
    small = int(np.argmin([m.blended_price for m in CHUTES_CATALOG]))
    large = int(np.argmax(lm.quality[_dense(lm, train)].mean(axis=0)))

    gap_tr = lm.quality[train][:, large] - lm.quality[train][:, small]
    Xtr = X[train]
    w = np.linalg.solve(Xtr.T @ Xtr + 1.0 * np.eye(Xtr.shape[1]), Xtr.T @ gap_tr)
    gap_hat = X[test] @ w

    choice = np.where(gap_hat >= threshold, large, small)
    q, c = lm.quality[test], lm.cost[test]
    rows = np.arange(len(test))
    return {
        "choice": choice,
        "threshold": threshold,
        "small": lm.model_ids[small], "large": lm.model_ids[large],
        "large_share": float((choice == large).mean()),
        "quality": float(q[rows, choice].mean()),
        "cost_per_call_usd": float(c[rows, choice].mean()),
    }


def classifier_router(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    lam_cost: float,
    *,
    ridge: float = 1.0,
) -> dict:
    """Classification-style: predict *which model wins*, not how each will score.

    The other large published family. Instead of K regressions onto per-model
    quality and an argmax over them, one one-vs-rest problem is fitted onto the
    label "was this model the utility-argmax for this item", and serving takes the
    argmax of those scores.

    Worth testing precisely because of §4b: a classifier is trained on the *order*,
    which is the half our estimator predicts well, so in principle it should be
    better placed to select the cheap models the regression can never reach.
    """
    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    u_tr = per_cell_utility(lm.quality[train], lm.cost[train],
                            UtilityWeights(lam_cost=lam_cost), ref_col=fc)
    # One-hot of the winner per training item; unobserved cells cannot win.
    u_tr = np.where(lm.observed[train], u_tr, -np.inf)
    Y = np.zeros_like(u_tr)
    Y[np.arange(len(train)), u_tr.argmax(axis=1)] = 1.0

    Xtr = X[train]
    W = np.linalg.solve(Xtr.T @ Xtr + ridge * np.eye(Xtr.shape[1]), Xtr.T @ Y)
    scores = X[test] @ W
    choice = scores.argmax(axis=1)

    q, c = lm.quality[test], lm.cost[test]
    rows = np.arange(len(test))
    return {
        "choice": choice,
        "quality": float(q[rows, choice].mean()),
        "cost_per_call_usd": float(c[rows, choice].mean()),
        "models_used": int(len(np.unique(choice))),
    }


def knn_router(
    lm: LabelMatrix,
    X: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    lam_cost: float,
    *,
    k: int = 32,
) -> dict:
    """Retrieval routing: let the k most similar graded questions vote.

    No parameters at all beyond k — the outcome matrix *is* the model. It is the
    natural non-parametric competitor to a ridge fit, and it is what a team with a
    vector store and no ML would build first.

    Cosine similarity on the same φ, so the comparison isolates the decision rule
    rather than the representation.
    """
    Xtr = X[train]
    ntr = Xtr / np.maximum(np.linalg.norm(Xtr, axis=1, keepdims=True), 1e-12)
    nte = X[test] / np.maximum(np.linalg.norm(X[test], axis=1, keepdims=True), 1e-12)

    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    q_tr, obs_tr = lm.quality[train], lm.observed[train]

    q, c = lm.quality[test], lm.cost[test]
    cost_ref = np.maximum(c[:, [fc]], 1e-12)
    choice = np.empty(len(test), dtype=int)

    # Blocked to keep the similarity matrix off the heap for large splits.
    for lo in range(0, len(test), 512):
        hi = min(lo + 512, len(test))
        sim = nte[lo:hi] @ ntr.T
        top = np.argpartition(-sim, kth=min(k, sim.shape[1] - 1), axis=1)[:, :k]
        for r, idx in enumerate(top):
            seen = obs_tr[idx]
            vals = np.where(seen, q_tr[idx], np.nan)
            with np.errstate(invalid="ignore"):
                q_hat = np.nanmean(vals, axis=0)
            q_hat = np.nan_to_num(q_hat, nan=0.0)
            util = q_hat - lam_cost * (c[lo + r] / cost_ref[lo + r])
            choice[lo + r] = int(util.argmax())

    rows = np.arange(len(test))
    return {
        "choice": choice, "k": k,
        "quality": float(q[rows, choice].mean()),
        "cost_per_call_usd": float(c[rows, choice].mean()),
        "models_used": int(len(np.unique(choice))),
    }


def cheapest_that_fits(lm: LabelMatrix, train: np.ndarray, test: np.ndarray,
                       bar: float) -> dict:
    """The policy a sensible engineer writes first: one model, cheapest above a bar.

    No per-item anything. Included because a router that cannot beat it is not
    earning its complexity.
    """
    acc = lm.quality[_dense(lm, train)].mean(axis=0)
    order = _price_order()
    pick = next((j for j in order if acc[j] >= bar), int(np.argmax(acc)))
    n = len(test)
    q, c = lm.quality[test], lm.cost[test]
    return {
        "choice": np.full(n, pick),
        "model": lm.model_ids[pick],
        "bar": bar,
        "quality": float(q[:, pick].mean()),
        "cost_per_call_usd": float(c[:, pick].mean()),
    }


def run(
    lm: LabelMatrix,
    X: np.ndarray,
    tokens_in: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    *,
    lam_cost: float,
    seed: int = 0,
    vectors: dict | None = None,
) -> dict:
    """Every strategy across its own dial, compared frontier to frontier.

    A single operating point per family would mostly measure where each rule's
    threshold happened to land. So each is swept over the parameter that trades its
    cost against its quality, and the comparison is: at the quality this family
    reached, what did ours cost?

    `vectors`, if given, is filled with `{policy name: {choice, spend}}` — the
    per-item arrays behind every row. They are handed back out of band rather than
    put in the returned dict because they are ~40,000 numbers and the return value is
    written to an artifact, but a margin cannot be given an error bar without them.
    """
    ps = pool_state()
    tin = _tokens_in_per_item(tokens_in, lm.observed)[test]
    q, c = lm.quality[test], lm.cost[test]
    n = len(test)
    rows = np.arange(n)
    dtr = _dense(lm, train)
    fc = frontier_reference_column(lm.quality[dtr])
    bs = best_single_column(per_cell_utility(
        lm.quality[dtr], lm.cost[dtr], UtilityWeights(lam_cost=lam_cost), ref_col=fc))
    bs_q, bs_c = float(q[:, bs].mean()), float(c[:, bs].mean())

    def score(name: str, family: str, choice: np.ndarray, cost_pc=None,
              *, spend: np.ndarray | None = None, **extra) -> dict:
        rq = float(q[rows, choice].mean())
        per_item_spend = c[rows, choice] if spend is None else np.asarray(spend)
        rc = cost_pc if cost_pc is not None else float(per_item_spend.mean())
        if vectors is not None:
            vectors[name] = {"family": family,
                             "choice": np.asarray(choice).copy(),
                             "quality": q[rows, choice].copy(),
                             "spend": per_item_spend.copy()}
        return {
            "policy": name, "family": family,
            "quality": rq, "cost_per_call_usd": rc,
            "quality_vs_best_single": rq / max(bs_q, 1e-12),
            "savings_vs_best_single": 1.0 - rc / max(bs_c, 1e-12),
            **extra,
        }

    # ------------------------------------------------------------ our dial --
    ours = []
    for lc in (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7, 1.0):
        rr, _ = train_router(lm, X, train, lam_cost=lc)
        ch = rr.decide(X[test], ps, tokens_in=tin).choice
        ours.append(score(f"this router, lam_c={lc:g}", "ours", ch, lam_cost=lc,
                          models_used=int(len(np.unique(ch)))))
    ours.sort(key=lambda p_: p_["quality_vs_best_single"])

    def ours_at(quality_ratio: float):
        xs = [p_["quality_vs_best_single"] for p_ in ours]
        ys = [p_["savings_vs_best_single"] for p_ in ours]
        if quality_ratio < xs[0] or quality_ratio > xs[-1]:
            return None
        return float(np.interp(quality_ratio, xs, ys))

    # ------------------------------------------------------- the baselines --
    r0, _ = train_router(lm, X, train, lam_cost=lam_cost)
    dec = r0.decide(X[test], ps, tokens_in=tin)

    others = []
    for tau in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        cas = cascade(dec.q_hat, q, c, tau, verifier="predicted")
        others.append(score(f"cascade (FrugalGPT-style), tau={tau:g}", "cascade",
                            cas["choice"], cas["cost_per_call_usd"],
                            spend=cas["spend"], tau=tau,
                            mean_attempts=cas["mean_attempts"],
                            wasted_spend_share=cas["wasted_spend_share"]))
    cas_o = cascade(dec.q_hat, q, c, 0.0, verifier="oracle")
    others.append(score("cascade, ORACLE verifier (not implementable)", "cascade-oracle",
                        cas_o["choice"], cas_o["cost_per_call_usd"],
                        spend=cas_o["spend"], mean_attempts=cas_o["mean_attempts"]))

    for lc in (0.05, 0.2, 0.5, 1.0):
        mf = matrix_factor(lm, train, test, X, rank=8, lam_cost=lc, seed=seed)
        others.append(score(f"matrix factorisation (RouteLLM-style), lam_c={lc:g}",
                            "matrix", mf["choice"], lam_cost=lc,
                            bridge_r2=mf["bridge_r2"]))

    for thr in (-0.05, 0.0, 0.05, 0.1, 0.2, 0.35):
        hy = hybrid_llm(lm, X, train, test, thr, seed=seed)
        others.append(score(f"HybridLLM-style, gap >= {thr:g}", "hybrid",
                            hy["choice"], threshold=thr,
                            large_share=hy["large_share"]))

    for lc in (0.05, 0.2, 0.5, 1.0):
        cl = classifier_router(lm, X, train, test, lam_cost=lc)
        others.append(score(f"classification router, lam_c={lc:g}", "classifier",
                            cl["choice"], lam_cost=lc, models_used=cl["models_used"]))

    for lc in (0.05, 0.2, 0.5):
        kn = knn_router(lm, X, train, test, lam_cost=lc, k=32)
        others.append(score(f"k-NN retrieval (k=32), lam_c={lc:g}", "knn",
                            kn["choice"], lam_cost=lc, models_used=kn["models_used"]))

    for bar in (0.5, 0.7, 0.8):
        cf = cheapest_that_fits(lm, train, test, bar)
        others.append(score(f"cheapest above {bar:g} (no routing)", "no-routing",
                            cf["choice"], bar=bar, model=cf["model"]))

    for o in others:
        here = ours_at(o["quality_vs_best_single"])
        o["our_savings_at_matched_quality"] = here
        if here is None:
            o["verdict"] = "outside our dial's range"
        else:
            o["margin_vs_us"] = o["savings_vs_best_single"] - here
            o["verdict"] = ("beats us" if o["margin_vs_us"] > 0.02 else
                            "tied" if o["margin_vs_us"] >= -0.02 else "loses to us")

    # Only the *useful* region counts. A strategy that spends more than sending
    # everything to the best single model has not routed, it has just spent; and
    # "beats us" inside that region means beating us at losing money, which is not a
    # comparison anyone should act on. So a family's best point is its best margin
    # among points that both save money and hold a sane quality floor.
    USEFUL_QUALITY_FLOOR = 0.95
    families, families_unrestricted = {}, {}
    for o in others:
        if o.get("margin_vs_us") is None:
            continue
        f = o["family"]
        if f not in families_unrestricted or (
                o["margin_vs_us"] > families_unrestricted[f]["margin_vs_us"]):
            families_unrestricted[f] = o
        if o["savings_vs_best_single"] <= 0 or (
                o["quality_vs_best_single"] < USEFUL_QUALITY_FLOOR):
            continue
        if f not in families or o["margin_vs_us"] > families[f]["margin_vs_us"]:
            families[f] = o

    no_useful_point = sorted(
        {o["family"] for o in others if o.get("margin_vs_us") is not None}
        - set(families))
    beats = [f for f, o in families.items() if o["margin_vs_us"] > 0.02]
    tied = [f for f, o in families.items() if -0.02 <= o["margin_vs_us"] <= 0.02]
    return {
        "our_dial": ours,
        "rows": others,
        "best_by_family": families,
        "best_by_family_unrestricted": families_unrestricted,
        "useful_quality_floor": USEFUL_QUALITY_FLOOR,
        "families_with_no_useful_point": no_useful_point,
        "best_single_model": lm.model_ids[bs],
        "n_test_items": int(n),
        "families_compared": sorted({o["family"] for o in others}),
        "beaten_by": beats,
        "tied_with": tied,
        "reading": (
            "Six published families swept across their own dials and compared to ours at "
            "matched quality. "
            + "Only points that actually save money at >=95% quality count — beating us "
              "while spending more than the do-nothing policy is not a comparison. "
            + (f"Beaten by: {', '.join(beats)}. " if beats else "None beats this router. ")
            + (f"Tied: {', '.join(tied)}. " if tied else "None ties it. ")
            + (f"No useful operating point at all: {', '.join(no_useful_point)}. "
               if no_useful_point else "")
            + "Cascades lose structurally because they pay for every attempt. "
            + "ONE SPLIT: the beaten-by and tied verdicts here are a single train/test "
              "split and do not survive on their own — over eight splits the margins "
              "move by more than they are worth. Read chutes/22_baseline_margins.json "
              "before quoting either. The 'no useful operating point' verdicts are the "
              "ones that hold on every split, because their cause is structural."
        ),
        "single_split_caveat": (
            "beats/ties verdicts are measured on one split; see "
            "chutes/22_baseline_margins.json for the interval and the split spread"),
    }
