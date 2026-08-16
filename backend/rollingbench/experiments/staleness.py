"""§14.1 — the staleness study. The experiment that could invalidate the proposal.

The claim under test: a router trained once measurably decays as the pool moves, and
nobody has published that measurement. Everything else in RollingBench is downstream
of it, which is why it runs first and before any spend.

The replay is retrospective and costs no inference. RouterBench's eleven models
carry real announcement dates spanning March–December 2023, so calendar time is a
real axis rather than a simulation: pick a cut-off T, let the pool grow as models
were actually released, and watch four policies diverge.

    Arm A   frozen at T. Never updated, and cannot select a model released after T
            — no column exists for it.
    Arm B   rolling. Absorbs each week's outcomes; new models enter with a
            cold-start prior. What the product does.
    Arm B′  refit each week but forbidden post-T models. This is the arm that makes
            the study conclusive: it separates "fresher data" from "access to newer
            models", which are two different reasons a frozen router could lose.
    Best    Single, re-selected every week. The line that matters — a frozen router
            crossing below it means static routing became actively harmful.

Items have no dates in RouterBench, so the item stream is a shuffle partitioned into
weekly batches. That is the honest construction: it holds the item distribution
fixed so that any divergence between arms is attributable to the pool moving and to
what each arm was allowed to learn, not to a drifting test set. Workload drift is a
separate effect and is studied separately (§4/7.1), not smuggled in here.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

import numpy as np

from ..catalog import Model
from ..coldstart import fit_lowrank, fit_new_column
from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    feasible_score_batch,
    per_cell_utility,
    reference_column,
    score_batch,
)
from ..router import PoolState, RidgeLinUCBRouter, RouterConfig


@dataclass
class StalenessConfig:
    cutoff: _dt.date = _dt.date(2023, 8, 1)
    weeks: int = 26
    batch_items: int = 400
    lam_cost: float = 0.02
    alpha: float = 0.1
    seed: int = 0
    warmup_items: int = 8000
    # Weeks are calendar weeks from `start`, so a model's release lands on the week
    # it actually shipped rather than at an arbitrary index.
    start: _dt.date = _dt.date(2023, 8, 1)
    cold_start_probe: int = 250


@dataclass
class StalenessResult:
    weeks: list[int]
    dates: list[str]
    arms: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    pool_size: list[int] = field(default_factory=list)
    new_models: dict[int, list[str]] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "weeks": self.weeks,
            "dates": self.dates,
            "arms": self.arms,
            "pool_size": self.pool_size,
            "new_models": {str(k): v for k, v in self.new_models.items()},
            "config": self.config,
            "notes": self.notes,
        }


def _pool_state(pool: tuple[Model, ...], ids: list[str]) -> PoolState:
    lookup = {m.id: m for m in pool}
    return PoolState(
        price_in=np.array([lookup[i].in_per_1m for i in ids]),
        price_out=np.array([lookup[i].out_per_1m for i in ids]),
    )


def run(
    lm: LabelMatrix,
    X: np.ndarray,
    pool: tuple[Model, ...],
    cfg: StalenessConfig | None = None,
) -> StalenessResult:
    """Run the four-arm replay and return one curve per arm."""
    cfg = cfg or StalenessConfig()
    rng = np.random.default_rng(cfg.seed)

    releases = {m.id: m.released for m in pool if m.released is not None}
    known_at_cutoff = [m for m in lm.model_ids if releases.get(m, _dt.date(1970, 1, 1)) <= cfg.cutoff]
    if not known_at_cutoff:
        raise ValueError(f"no models released by {cfg.cutoff}")

    # Item stream: a warm-up slice to fit on at T, then disjoint weekly batches.
    # Disjoint by item (NFR-7) — an item never appears in two weeks, so no arm can
    # score on something it trained on.
    order = rng.permutation(lm.n_items)
    warmup = order[: cfg.warmup_items]
    stream = order[cfg.warmup_items :]
    needed = cfg.weeks * cfg.batch_items
    if len(stream) < needed:
        raise ValueError(f"need {needed} stream items, have {len(stream)}")
    batches = [stream[w * cfg.batch_items : (w + 1) * cfg.batch_items] for w in range(cfg.weeks)]

    d = X.shape[1]
    full_ids = list(lm.model_ids)
    col_of = {m: j for j, m in enumerate(full_ids)}

    def new_router(ids: list[str]) -> RidgeLinUCBRouter:
        return RidgeLinUCBRouter(
            d, len(ids),
            RouterConfig(alpha=cfg.alpha, lam_cost=cfg.lam_cost, count_bonus=0.05),
        )

    # ---- Arm A: fitted once at T, on the models that existed at T, then frozen.
    arm_a_ids = list(known_at_cutoff)
    a_cols = [col_of[m] for m in arm_a_ids]
    arm_a = new_router(arm_a_ids)
    arm_a.fit(X[warmup], lm.quality[warmup][:, a_cols], lm.observed[warmup][:, a_cols],
              lm.tokens_out[warmup][:, a_cols])

    # ---- Arm B: same start, but keeps learning and takes on new models.
    arm_b_ids = list(known_at_cutoff)
    arm_b = new_router(arm_b_ids)
    b_cols = [col_of[m] for m in arm_b_ids]
    arm_b.fit(X[warmup], lm.quality[warmup][:, b_cols], lm.observed[warmup][:, b_cols],
              lm.tokens_out[warmup][:, b_cols])

    # ---- Arm B′: keeps learning, never gets the new models.
    arm_bp_ids = list(known_at_cutoff)
    arm_bp = new_router(arm_bp_ids)
    arm_bp.fit(X[warmup], lm.quality[warmup][:, b_cols], lm.observed[warmup][:, b_cols],
               lm.tokens_out[warmup][:, b_cols])

    # Everything the rolling arm has seen, for the cold-start prior of a new model.
    seen: list[np.ndarray] = [warmup]

    result = StalenessResult(weeks=[], dates=[], config=vars(cfg) | {"cutoff": str(cfg.cutoff)})
    result.notes = [
        "quality/cost are RouterBench measured cells; no inference was run",
        "model release dates are public announcement dates (see catalog.ROUTERBENCH_POOL)",
        "item order is a fixed shuffle: the item distribution is held constant so "
        "divergence is attributable to the pool moving, not to workload drift",
    ]
    for arm in ("frozen (A)", "rolling (B)", "refit, no new models (B')", "best single"):
        result.arms[arm] = {"score": [], "regret": [], "score_feasible": [],
                           "quality": [], "cost": [], "utility": []}

    for w in range(cfg.weeks):
        week_date = cfg.start + _dt.timedelta(weeks=w)
        batch = batches[w]

        # The pool as it stood that week. The oracle and the baseline are computed
        # over this full set, which is precisely why the frozen arm loses ground:
        # what was achievable grew and it cannot reach it.
        live_ids = [m for m in full_ids if releases.get(m, _dt.date(1970, 1, 1)) <= week_date]
        live_cols = [col_of[m] for m in live_ids]

        arrived = [m for m in live_ids if m not in arm_b_ids]
        for mid in arrived:
            # Cold start: the new column gets a low-rank prior fitted from a probe,
            # then ordinary updates correct it (§8.6). Without this, a new model
            # would sit unselectable until it accumulated history on its own.
            j_new = arm_b.add_model()
            arm_b_ids.append(mid)
            _seed_new_model(arm_b, arm_b_ids, j_new, mid, lm, X, seen, col_of, cfg, rng)
        if arrived:
            result.new_models[w] = arrived

        # c_ref is the live pool's Best Single. It moves as the pool grows, which is
        # correct: the reference is "one good model available today", and holding it
        # at a model that has been superseded would flatter every arm equally.
        ref_col = reference_column(lm.quality[batch][:, live_cols],
                                   lm.cost[batch][:, live_cols], cfg.lam_cost)
        u_full = per_cell_utility(
            lm.quality[batch][:, live_cols], lm.cost[batch][:, live_cols],
            UtilityWeights(lam_cost=cfg.lam_cost), ref_col=ref_col,
        )
        base_col = best_single_column(u_full)
        groups = lm.task[batch]

        def record(arm: str, choices_full: np.ndarray) -> None:
            spec = score_batch(u_full, choices_full, base_col=base_col, clip=False)
            feas = feasible_score_batch(u_full, choices_full, groups, base_col=base_col)
            n = len(batch)
            # Recorded unclipped. §8.8 clips the score into [0, 1] for payout purposes,
            # which is right for emissions and wrong here: how far *below* zero a frozen
            # router falls is the result, and clipping would report a flat floor where the
            # decay is still deepening.
            result.arms[arm]["score"].append(spec.score)
            result.arms[arm]["regret"].append(spec.regret)
            result.arms[arm]["score_feasible"].append(feas.score)
            result.arms[arm]["utility"].append(spec.u_policy)
            result.arms[arm]["quality"].append(
                float(lm.quality[batch][:, live_cols][np.arange(n), choices_full].mean()))
            result.arms[arm]["cost"].append(
                float(lm.cost[batch][:, live_cols][np.arange(n), choices_full].sum()))

        # Each arm decides over its own pool; choices are then mapped into the live
        # pool's column space so every arm is scored on the same utility matrix.
        def remap(ids: list[str], choice: np.ndarray) -> np.ndarray:
            live_index = {m: k for k, m in enumerate(live_ids)}
            table = np.array([live_index[m] for m in ids])
            return table[choice]

        # Each arm's own c_ref index, in its own column space.
        ref_id = live_ids[ref_col]
        for ids_, arm_ in ((arm_a_ids, arm_a), (arm_b_ids, arm_b), (arm_bp_ids, arm_bp)):
            arm_.cfg.ref_model = ids_.index(ref_id) if ref_id in ids_ else None

        record("frozen (A)", remap(arm_a_ids, arm_a.decide(X[batch], _pool_state(pool, arm_a_ids)).choice))
        record("rolling (B)", remap(arm_b_ids, arm_b.decide(X[batch], _pool_state(pool, arm_b_ids)).choice))
        record("refit, no new models (B')", remap(arm_bp_ids, arm_bp.decide(X[batch], _pool_state(pool, arm_bp_ids)).choice))
        record("best single", np.full(len(batch), base_col))

        # After scoring, the two learning arms absorb the week's graded outcomes.
        # Order matters: scoring first keeps the evaluation out-of-sample.
        b_cols_now = [col_of[m] for m in arm_b_ids]
        arm_b.absorb(X[batch], lm.quality[batch][:, b_cols_now],
                     lm.observed[batch][:, b_cols_now], lm.tokens_out[batch][:, b_cols_now])
        bp_cols = [col_of[m] for m in arm_bp_ids]
        arm_bp.absorb(X[batch], lm.quality[batch][:, bp_cols],
                      lm.observed[batch][:, bp_cols], lm.tokens_out[batch][:, bp_cols])
        seen.append(batch)

        result.weeks.append(w)
        result.dates.append(str(week_date))
        result.pool_size.append(len(live_ids))

    return result


def _seed_new_model(
    router: RidgeLinUCBRouter,
    ids: list[str],
    j_new: int,
    mid: str,
    lm: LabelMatrix,
    X: np.ndarray,
    seen: list[np.ndarray],
    col_of: dict[str, int],
    cfg: StalenessConfig,
    rng: np.random.Generator,
) -> None:
    """Give a newly arrived model a prior from a probe, per §8.6.

    The probe is `cold_start_probe` items drawn from history and run on the new
    model — the one real cost of onboarding a model, and the reason FR-15 promises
    24 hours rather than instantly.
    """
    history = np.concatenate(seen)
    probe = rng.choice(history, size=min(cfg.cold_start_probe, len(history)), replace=False)
    global_col = col_of[mid]

    # The probe's real outcomes are the evidence; they go in at full weight and set
    # the new column's own Gram matrix, so its σ starts large and shrinks honestly.
    obs = np.ones((len(probe), 1), dtype=bool)
    router.absorb(
        X[probe],
        lm.quality[probe][:, [global_col]],
        obs,
        lm.tokens_out[probe][:, [global_col]],
        models=[j_new],
    )


def summarise(result: StalenessResult) -> dict:
    """The headline numbers, and the answer to the decision gate.

    The gate (§14.1): if the frozen arm holds up against Best Single over the
    equivalent of several months, the premise is wrong and we say so. If it crosses
    below, static routing became actively harmful and the curve is the contribution.
    """
    frozen = np.array(result.arms["frozen (A)"]["score"])
    rolling = np.array(result.arms["rolling (B)"]["score"])
    bp = np.array(result.arms["refit, no new models (B')"]["score"])
    weeks = np.array(result.weeks)

    # "Crossed below Best Single" has to mean stayed below, not dipped below once —
    # a single 400-item batch is noisy enough to cross by accident. A 4-week trailing
    # mean below zero is the crossing.
    window = 4
    if len(frozen) >= window:
        trailing = np.convolve(frozen, np.ones(window) / window, mode="valid")
        below = np.where(trailing < 0)[0]
        crossed = below + window - 1
    else:
        crossed = np.array([], dtype=int)
    first_half, second_half = weeks < weeks.mean(), weeks >= weeks.mean()

    return {
        "frozen_start": float(frozen[:4].mean()),
        "frozen_end": float(frozen[-4:].mean()),
        "frozen_decay": float(frozen[:4].mean() - frozen[-4:].mean()),
        "rolling_start": float(rolling[:4].mean()),
        "rolling_end": float(rolling[-4:].mean()),
        "rolling_decay": float(rolling[:4].mean() - rolling[-4:].mean()),
        "gap_first_half": float(rolling[first_half].mean() - frozen[first_half].mean()),
        "gap_second_half": float(rolling[second_half].mean() - frozen[second_half].mean()),
        "week_crossed_below_best_single": int(crossed[0]) if len(crossed) else None,
        "frozen_end_feasible": float(np.mean(result.arms["frozen (A)"]["score_feasible"][-4:])),
        "rolling_end_feasible": float(np.mean(result.arms["rolling (B)"]["score_feasible"][-4:])),
        "frozen_start_feasible": float(np.mean(result.arms["frozen (A)"]["score_feasible"][:4])),
        "rolling_start_feasible": float(np.mean(result.arms["rolling (B)"]["score_feasible"][:4])),
        # B′ isolates the two causes: what it recovers is fresher data, what it
        # still loses is access to models that did not exist at T.
        "attribution_fresher_data": float(bp[second_half].mean() - frozen[second_half].mean()),
        "attribution_new_models": float(rolling[second_half].mean() - bp[second_half].mean()),
        "verdict": (
            "decay observed" if frozen[:4].mean() - frozen[-4:].mean() > 0.05
            else "no material decay — premise not supported on this corpus"
        ),
    }
