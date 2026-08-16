"""7.1 — component-wise decay versus one shared γ, under injected shocks.

Two separate claims get tested here and it is worth keeping them apart.

1b, read-versus-learn (§4.2). RollingBench §8.7 asserts that price must be read at
decision time rather than fitted, and gives an example rather than a measurement.
The measurement is a controlled price shock: a router that folded cost into its
learned target has to unlearn it, and how long that takes is exactly what the
`learned-cost` arm below reports. Nothing in the source document tests this.

1a, per-component decay (§4.3). One γ has to serve two targets that drift at
different rates. Injecting a quality shock and a verbosity shock on independent
schedules forces the trade-off §4.4 predicts: fast enough to track one means noisy
on the other. Both arms get their γ tuned first, so the comparison is best-against-
best rather than tuned-against-default.

The shocks are synthetic and labelled as such. RouterBench is a static snapshot, so
there is no real drift in it to find — which is the same reason the proposal asks
for injection here instead of a retrospective read.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..catalog import Model
from ..data.labelmatrix import LabelMatrix
from ..metrics import (
    UtilityWeights,
    best_single_column,
    feasible_score_batch,
    per_cell_utility,
    reference_column,
    score_batch,
)
from ..router import DecomposedRouter, PoolState, RidgeLinUCBRouter, RouterConfig


@dataclass
class Shock:
    """One injected change to the world, at a known week and of a known size."""

    week: int
    kind: str                # "price" | "quality" | "verbosity"
    model_index: int
    factor: float
    note: str = ""


@dataclass
class ShockConfig:
    weeks: int = 40
    batch_items: int = 400
    lam_cost: float = 0.05
    seed: int = 0
    warmup_items: int = 6000
    shocks: list[Shock] = field(default_factory=list)

    @staticmethod
    def default(lm: LabelMatrix) -> "ShockConfig":
        """Shocks on three independent schedules — the adversarial design of §7.1.

        Independent on purpose: if price, quality and verbosity all moved together, a
        single γ would be the right model and the experiment could not distinguish
        the two arms. The rates here are drawn from what §3.3 says the real world
        does — price cuts in steps, silent quality drift unannounced, verbosity
        changing with a serving update.

        Deliberately none of them lands on the reference model whose cost is c_ref.
        Shocking the numeraire changes the units of the cost term rather than the
        thing being measured, and the effect on behaviour then partly cancels: every
        ratio in the pool moves together. The reference is the highest-quality model,
        so the shocks target the second-best, a mid-tier model, and the cheapest.
        """
        mean_q = lm.quality.mean(axis=0)
        ref = int(np.argmax(mean_q))                      # c_ref — left untouched
        order = np.argsort(mean_q)[::-1]
        runner_up = int(next(j for j in order if j != ref))
        cheap = int(np.argmin(lm.cost.mean(axis=0)))
        mid = int(next(j for j in np.argsort(mean_q)[::-1][len(mean_q) // 2:]
                       if j not in (ref, runner_up, cheap)))
        return ShockConfig(shocks=[
            Shock(8, "price", runner_up, 0.35,
                  "strong non-reference model cuts price 65% (a real 2023 pattern)"),
            Shock(16, "quality", mid, 0.80,
                  "silent 20% quality regression after a serving change"),
            Shock(24, "verbosity", cheap, 2.5, "cheap model becomes 2.5x more verbose"),
            Shock(32, "price", cheap, 3.0, "cheap model's price triples"),
        ])


    @staticmethod
    def high_drift(lm: LabelMatrix, seed: int = 0) -> "ShockConfig":
        """A regime where forgetting should actually pay for itself.

        The default schedule is four isolated step changes against an otherwise
        stationary corpus, and on that schedule forgetting cannot win: throwing away
        old observations to track one 20% shock on one model out of eleven is a bad
        trade, and the measurement says so. That is a real result about the default
        regime, but it does not test Contribution 1 — the claim is about components
        drifting at *different rates*, which requires drift to be continuous and
        materially different per component.

        So this schedule drifts every model's quality on a slow random walk and its
        verbosity on a fast one, an order of magnitude apart in rate. If
        component-wise decay ever helps, it helps here; if it does not help here
        either, the claim is not supported and the honest report says so.
        """
        rng = np.random.default_rng(seed)
        K = len(lm.model_ids)
        mean_q = lm.quality.mean(axis=0)
        ref = int(np.argmax(mean_q))
        shocks: list[Shock] = []
        for w in range(2, 40):
            # Quality: slow walk, one model per fortnight.
            if w % 2 == 0:
                j = int(rng.integers(0, K))
                if j != ref:
                    shocks.append(Shock(w, "quality", j, float(rng.uniform(0.92, 1.06)),
                                        "slow quality walk"))
            # Verbosity: fast walk, every week, larger steps — an order of magnitude
            # faster than the quality process.
            j = int(rng.integers(0, K))
            shocks.append(Shock(w, "verbosity", j, float(rng.uniform(0.6, 1.7)),
                                "fast verbosity walk"))
        shocks += [
            Shock(10, "price", int(np.argmin(lm.cost.mean(axis=0))), 0.4, "price cut"),
            Shock(28, "price", int(np.argmin(lm.cost.mean(axis=0))), 2.5, "price rise"),
        ]
        return ShockConfig(shocks=shocks)


class LearnedCostRouter(RidgeLinUCBRouter):
    """The arm that fits cost instead of reading it — what §8.7 warns against.

    Identical to the baseline except that the fitted target is utility rather than
    quality, so price is baked into the weights. This is how most published routers
    work, and it is the arm that has to relearn after a price change.
    """

    name = "learned-cost (price in the fit)"

    def decide(self, X, pool, tokens_in=None, allowed=None):  # noqa: ANN001, ANN201
        # The learned target already contains the cost penalty, so applying the live
        # cost term again would double-count it.
        q_hat = self.quality.predict(X)
        sigma = self._sigma(X)
        utility = q_hat + self.cfg.alpha * sigma
        tokens_hat = np.maximum(self.tokens.predict(X), 1.0)
        cost_hat = tokens_hat * pool.price_out[None, :] / 1e6
        mask = np.ones_like(utility, dtype=bool)
        if pool.available is not None:
            mask &= pool.available[None, :]
        utility = np.where(mask, utility, -np.inf)
        from ..router import Decision

        return Decision(np.argmax(utility, axis=1), utility, q_hat, sigma, cost_hat, tokens_hat)


def _apply_shocks(
    week: int,
    shocks: list[Shock],
    price_out: np.ndarray,
    quality_mult: np.ndarray,
    verbosity: np.ndarray,
) -> None:
    """Shocks are step changes and they persist, which is what makes them shocks."""
    for s in shocks:
        if s.week == week:
            if s.kind == "price":
                price_out[s.model_index] *= s.factor
            elif s.kind == "quality":
                quality_mult[s.model_index] *= s.factor
            elif s.kind == "verbosity":
                verbosity[s.model_index] *= s.factor


def run(
    lm: LabelMatrix,
    X: np.ndarray,
    pool: tuple[Model, ...],
    cfg: ShockConfig | None = None,
    gamma_shared: float = 0.999,
    gamma_quality: float = 0.995,
    gamma_tokens: float = 0.95,
) -> dict:
    """Replay with shocks; return one regret curve per arm."""
    cfg = cfg or ShockConfig.default(lm)
    rng = np.random.default_rng(cfg.seed)
    order = rng.permutation(lm.n_items)
    warmup, stream = order[: cfg.warmup_items], order[cfg.warmup_items :]
    need = cfg.weeks * cfg.batch_items
    if len(stream) < need:
        raise ValueError(f"need {need} stream items, have {len(stream)}")

    d, K = X.shape[1], lm.n_models
    base_price_in = np.array([m.in_per_1m for m in pool])
    base_price_out = np.array([m.out_per_1m for m in pool])

    arms: dict[str, RidgeLinUCBRouter] = {
        "learned-cost, shared γ": LearnedCostRouter(
            d, K, RouterConfig(alpha=0.0, gamma=gamma_shared, lam_cost=cfg.lam_cost)),
        "live-read price, shared γ": RidgeLinUCBRouter(
            d, K, RouterConfig(alpha=0.0, gamma=gamma_shared, lam_cost=cfg.lam_cost)),
        "live-read price, decomposed γ_q/γ_t": DecomposedRouter(
            d, K, RouterConfig(alpha=0.0, gamma_quality=gamma_quality,
                               gamma_tokens=gamma_tokens, lam_cost=cfg.lam_cost)),
    }

    # The reference model for c_ref (§8.7), fixed once from warm-up history. It is a
    # normalisation constant on the control plane's clock, so it does not chase the
    # shocks — which is the point: a fixed reference is what lets a price cut show up.
    ref_col = reference_column(lm.quality[warmup], lm.cost[warmup], cfg.lam_cost)
    for arm in arms.values():
        arm.cfg.ref_model = ref_col

    # Warm-up on unshocked history, so every arm starts from the same beliefs.
    q0, t0 = lm.quality[warmup], lm.tokens_out[warmup]
    u0 = per_cell_utility(q0, lm.cost[warmup], UtilityWeights(lam_cost=cfg.lam_cost),
                          ref_col=ref_col)
    for name, arm in arms.items():
        target = u0 if isinstance(arm, LearnedCostRouter) else q0
        arm.fit(X[warmup], target, lm.observed[warmup], t0)

    price_out = base_price_out.copy()
    quality_mult = np.ones(K)
    verbosity = np.ones(K)

    shocked_models = sorted({s.model_index for s in cfg.shocks})
    out: dict = {
        "weeks": [],
        "arms": {
            name: {
                "regret": [], "score": [], "score_feasible": [], "quality": [], "cost": [],
                # Traffic share to each shocked model, week by week. This is where a
                # price change is visible as behaviour rather than as belief: the
                # live-read arm re-routes on the first batch after a cut, a learned-
                # cost arm has to re-observe its way there.
                "share": {lm.model_ids[j]: [] for j in shocked_models},
            }
            for name in arms
        },
        "shocks": [vars(s) | {"model": lm.model_ids[s.model_index]} for s in cfg.shocks],
        "config": {k: v for k, v in vars(cfg).items() if k != "shocks"},
        "gammas": {"shared": gamma_shared, "quality": gamma_quality, "tokens": gamma_tokens},
        "ref_model": lm.model_ids[ref_col],
        "notes": ["shocks are SYNTHETIC and injected; RouterBench is a static snapshot"],
    }

    for w in range(cfg.weeks):
        _apply_shocks(w, cfg.shocks, price_out, quality_mult, verbosity)
        batch = stream[w * cfg.batch_items : (w + 1) * cfg.batch_items]

        # The shocked world for this week: quality scaled by the drift factor, tokens
        # by the verbosity factor, and cost recomputed from the live price so a price
        # cut shows up in the bill rather than only in the belief.
        q_w = np.clip(lm.quality[batch] * quality_mult[None, :], 0.0, 1.0)
        t_w = lm.tokens_out[batch] * verbosity[None, :]
        tokens_in = np.maximum(np.ceil([len(p) / 4 for p in lm.prompts[batch]]), 1.0)
        cost_w = (t_w * price_out[None, :] + tokens_in[:, None] * base_price_in[None, :]) / 1e6

        u_w = per_cell_utility(q_w, cost_w, UtilityWeights(lam_cost=cfg.lam_cost),
                               ref_col=ref_col)
        base_col = best_single_column(u_w)
        ps = PoolState(price_in=base_price_in, price_out=price_out)

        for name, arm in arms.items():
            ch = arm.decide(X[batch], ps, tokens_in=tokens_in).choice
            s = score_batch(u_w, ch, base_col=base_col, clip=False)
            feas = feasible_score_batch(u_w, ch, lm.task[batch], base_col=base_col)
            n = len(batch)
            out["arms"][name]["regret"].append(s.regret)
            out["arms"][name]["score"].append(float(np.clip(s.score, -2.0, 1.0)))
            out["arms"][name]["score_feasible"].append(feas.score)
            out["arms"][name]["quality"].append(float(q_w[np.arange(n), ch].mean()))
            out["arms"][name]["cost"].append(float(cost_w[np.arange(n), ch].sum()))
            for j in shocked_models:
                out["arms"][name]["share"][lm.model_ids[j]].append(float((ch == j).mean()))

            target = u_w if isinstance(arm, LearnedCostRouter) else q_w
            arm.absorb(X[batch], target, lm.observed[batch], t_w)

        out["weeks"].append(w)

    out["summary"] = _summarise(out, cfg)
    return out


def _summarise(out: dict, cfg: ShockConfig) -> dict:
    """Peak regret at each shock, and steady-state regret between shocks.

    Both halves matter and they can disagree: an arm that adapts fast may pay for it
    with a noisier baseline. Reporting only the shock response would hide that, which
    is the trade-off §4.4 is actually about.
    """
    weeks = np.array(out["weeks"])
    per_arm = {}
    shock_weeks = sorted({s.week for s in cfg.shocks})
    # Steady state = weeks at least 3 clear of any shock.
    quiet = np.ones(len(weeks), dtype=bool)
    for sw in shock_weeks:
        quiet &= np.abs(weeks - sw) > 3
    # Under a continuous-drift schedule there are no quiet weeks at all. Falling back
    # to the whole replay is the honest reading — "steady state" simply is the drift.
    if not quiet.any():
        quiet = np.ones(len(weeks), dtype=bool)

    for name, series in out["arms"].items():
        regret = np.array(series["regret"])
        by_shock = {}
        for s in cfg.shocks:
            window = (weeks >= s.week) & (weeks <= s.week + 3)
            pre = (weeks >= s.week - 3) & (weeks < s.week)
            by_shock[f"{s.kind}@w{s.week}"] = {
                "peak_regret": float(regret[window].max()) if window.any() else float("nan"),
                "excess_over_pre": float(regret[window].mean() - regret[pre].mean())
                if window.any() and pre.any() else float("nan"),
                # How many weeks until regret returns near its pre-shock level.
                "recovery_weeks": _recovery(regret, weeks, s.week),
            }
        # Adaptation lag: after a price shock, how many weeks before traffic to the
        # affected model settles at its new level. Reading the price live makes this
        # zero by construction; fitting the price makes it a function of γ. This is
        # the measurement FR-16 is really about.
        for s in cfg.shocks:
            if s.kind != "price":
                continue
            share = np.array(series["share"][out["shocks"][0]["model"]]
                             if False else series["share"][_model_of(out, s)])
            by_shock[f"{s.kind}@w{s.week}"]["adaptation_lag_weeks"] = _lag(share, weeks, s.week)
            by_shock[f"{s.kind}@w{s.week}"]["share_before"] = float(
                share[(weeks >= s.week - 3) & (weeks < s.week)].mean())
            by_shock[f"{s.kind}@w{s.week}"]["share_after"] = float(
                share[weeks >= s.week + 6].mean()) if (weeks >= s.week + 6).any() else float("nan")

        feasible = np.array(series["score_feasible"])
        per_arm[name] = {
            "mean_regret": float(regret.mean()),
            "steady_state_regret": float(regret[quiet].mean()),
            "worst_week_regret": float(regret.max()),
            "mean_score_feasible": float(feasible.mean()),
            "steady_state_feasible": float(feasible[quiet].mean()),
            "total_cost": float(np.sum(series["cost"])),
            "mean_quality": float(np.mean(series["quality"])),
            "by_shock": by_shock,
        }
    return per_arm


def _model_of(out: dict, shock: Shock) -> str:
    for rec in out["shocks"]:
        if rec["week"] == shock.week and rec["kind"] == shock.kind:
            return rec["model"]
    raise KeyError(shock)


def _lag(share: np.ndarray, weeks: np.ndarray, shock_week: int, frac: float = 0.9) -> float:
    """Weeks until traffic share reaches `frac` of the distance to its new level.

    Returns 0.0 when the very first post-shock batch is already there, which is what
    reading the price live should produce.
    """
    pre_mask = (weeks >= shock_week - 3) & (weeks < shock_week)
    post_mask = weeks >= shock_week + 6
    if not pre_mask.any() or not post_mask.any():
        return float("nan")
    before, after = share[pre_mask].mean(), share[post_mask].mean()
    if abs(after - before) < 0.01:
        return 0.0                      # the shock did not move behaviour at all
    target = before + frac * (after - before)
    for k, w in enumerate(weeks):
        if w < shock_week:
            continue
        moved_up = after > before and share[k] >= target
        moved_down = after < before and share[k] <= target
        if moved_up or moved_down:
            return float(w - shock_week)
    return float("inf")


def _recovery(regret: np.ndarray, weeks: np.ndarray, shock_week: int, tol: float = 0.02) -> float:
    pre = regret[(weeks >= shock_week - 3) & (weeks < shock_week)]
    if len(pre) == 0:
        return float("nan")
    target = pre.mean() + tol
    for k, w in enumerate(weeks):
        if w >= shock_week and regret[k] <= target:
            return float(w - shock_week)
    return float("inf")


def tune_gammas(
    lm: LabelMatrix,
    X: np.ndarray,
    pool: tuple[Model, ...],
    cfg: ShockConfig | None = None,
    shared_grid: tuple[float, ...] = (1.0, 0.9995, 0.999, 0.995, 0.99, 0.95),
    quality_grid: tuple[float, ...] = (1.0, 0.999, 0.995, 0.99),
    tokens_grid: tuple[float, ...] = (1.0, 0.99, 0.95, 0.9),
) -> dict:
    """Tune each arm's decay before comparing them.

    Without this the comparison is rigged: any decomposed router with two dials will
    beat a shared-γ router left at its default. The claim is only interesting if the
    best shared γ still loses to the best (γ_q, γ_t), so both are searched over the
    same replay and the winners are reported with their grids.
    """
    cfg = cfg or ShockConfig.default(lm)
    shared_rows = []
    for g in shared_grid:
        res = run(lm, X, pool, cfg, gamma_shared=g, gamma_quality=g, gamma_tokens=g)
        s = res["summary"]["live-read price, shared γ"]
        shared_rows.append({"gamma": g, **{k: v for k, v in s.items() if k != "by_shock"}})

    decomposed_rows = []
    for gq in quality_grid:
        for gt in tokens_grid:
            res = run(lm, X, pool, cfg, gamma_shared=1.0, gamma_quality=gq, gamma_tokens=gt)
            s = res["summary"]["live-read price, decomposed γ_q/γ_t"]
            decomposed_rows.append({"gamma_q": gq, "gamma_t": gt,
                                    **{k: v for k, v in s.items() if k != "by_shock"}})

    best_shared = min(shared_rows, key=lambda r: r["mean_regret"])
    best_dec = min(decomposed_rows, key=lambda r: r["mean_regret"])
    return {
        "shared": shared_rows,
        "decomposed": decomposed_rows,
        "best_shared": best_shared,
        "best_decomposed": best_dec,
        "improvement": best_shared["mean_regret"] - best_dec["mean_regret"],
        "verdict": (
            "decomposition helps" if best_dec["mean_regret"] < best_shared["mean_regret"] - 1e-4
            else "no measurable gain from decomposition on this replay"
        ),
    }


def replicate(
    lm: LabelMatrix,
    X: np.ndarray,
    pool: tuple[Model, ...],
    regime: str = "default",
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4),
    gamma_shared: float = 1.0,
    gamma_quality: float = 1.0,
    gamma_tokens: float = 0.99,
) -> dict:
    """Run one regime across several seeds and report the noise floor.

    Without this the comparison cannot be read: a 0.0004 difference in mean regret
    between two arms means nothing until the seed-to-seed spread is known. The
    verdict below is a claim about effect size relative to that spread, which is the
    only form of the claim worth putting in a paper.
    """
    per_arm: dict[str, list[float]] = {}
    per_arm_feasible: dict[str, list[float]] = {}
    # Per-shock transient excess regret, per arm. Mean regret over a 40-week replay
    # dilutes a two-week transient into nothing, so a claim about how fast an arm
    # *reacts* has to be measured in the shock window or not at all.
    per_shock: dict[str, dict[str, list[float]]] = {}
    for seed in seeds:
        cfg = (ShockConfig.high_drift(lm, seed=seed) if regime == "high_drift"
               else ShockConfig.default(lm))
        cfg.seed = seed
        res = run(lm, X, pool, cfg, gamma_shared=gamma_shared,
                  gamma_quality=gamma_quality, gamma_tokens=gamma_tokens)
        for name, s in res["summary"].items():
            per_arm.setdefault(name, []).append(s["mean_regret"])
            per_arm_feasible.setdefault(name, []).append(s["mean_score_feasible"])
            for shock_key, v in s["by_shock"].items():
                kind = shock_key.split("@")[0]
                if np.isfinite(v["excess_over_pre"]):
                    per_shock.setdefault(name, {}).setdefault(kind, []).append(
                        v["excess_over_pre"])

    stats = {
        name: {
            "mean_regret_mean": float(np.mean(v)),
            "mean_regret_sd": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0,
            "feasible_mean": float(np.mean(per_arm_feasible[name])),
            "feasible_sd": float(np.std(per_arm_feasible[name], ddof=1)) if len(v) > 1 else 0.0,
            "n_seeds": len(v),
        }
        for name, v in per_arm.items()
    }

    shared = "live-read price, shared γ"
    dec = "live-read price, decomposed γ_q/γ_t"
    learned = "learned-cost, shared γ"
    # Paired across seeds: both arms see the same replay, so the per-seed difference
    # cancels the batch noise that dominates the absolute level.
    paired_dec = np.array(per_arm[shared]) - np.array(per_arm[dec])
    paired_read = np.array(per_arm[learned]) - np.array(per_arm[shared])

    def verdict(diffs: np.ndarray, what: str) -> dict:
        mean, sd = float(diffs.mean()), float(diffs.std(ddof=1)) if len(diffs) > 1 else 0.0
        se = sd / np.sqrt(len(diffs)) if len(diffs) > 1 else float("inf")
        supported = bool(mean > 0 and sd > 0 and mean > 2 * se)
        return {
            "claim": what,
            "mean_regret_reduction": mean,
            "sd_across_seeds": sd,
            "std_error": float(se),
            "supported": supported,
            "reading": (
                f"{what}: reduces mean regret by {mean:+.4f} ± {se:.4f} (SE over "
                f"{len(diffs)} seeds) — {'supported' if supported else 'NOT distinguishable from noise'}"
            ),
        }

    # Paired transient comparison: for each shock kind, does one arm absorb it with
    # less excess regret than another, across seeds?
    transient = {}
    for kind in sorted({k for arm in per_shock.values() for k in arm}):
        def excess(arm: str) -> np.ndarray:
            return np.array(per_shock.get(arm, {}).get(kind, []), dtype=float)
        a_learned, a_shared, a_dec = excess(learned), excess(shared), excess(dec)
        n = min(len(a_learned), len(a_shared), len(a_dec))
        if n == 0:
            continue
        d_read = a_learned[:n] - a_shared[:n]        # >0 means live-read absorbed it better
        d_dec = a_shared[:n] - a_dec[:n]             # >0 means decomposed absorbed it better
        transient[kind] = {
            "n": int(n),
            "excess_learned_cost": float(a_learned[:n].mean()),
            "excess_live_read": float(a_shared[:n].mean()),
            "excess_decomposed": float(a_dec[:n].mean()),
            "live_read_advantage": float(d_read.mean()),
            "live_read_se": float(d_read.std(ddof=1) / np.sqrt(n)) if n > 1 else float("inf"),
            "decomposed_advantage": float(d_dec.mean()),
            "decomposed_se": float(d_dec.std(ddof=1) / np.sqrt(n)) if n > 1 else float("inf"),
        }

    return {
        "regime": regime,
        "gammas": {"shared": gamma_shared, "quality": gamma_quality, "tokens": gamma_tokens},
        "per_arm": stats,
        "transient_by_shock_kind": transient,
        "decomposition": verdict(paired_dec, "component-wise γ_q/γ_t vs one shared γ"),
        "read_vs_learn": verdict(paired_read, "reading price live vs fitting it"),
    }
