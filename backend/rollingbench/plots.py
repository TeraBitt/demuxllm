"""Figures. One function per figure, each taking a result dict and returning a Figure.

Kept separate from the experiments so that a result can be re-plotted without being
recomputed, and so the notebooks stay short — a notebook that carries three hundred
lines of matplotlib is a notebook nobody reads.

Styling is deliberately plain and colour-blind safe: the series are distinguished by
marker and label as well as by hue, because a reader printing this in greyscale should
still be able to tell the frozen router from the rolling one.
"""

from __future__ import annotations

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# The validated categorical palette, in its fixed slot order. Hues are assigned by slot
# and never cycled: a fourth series folds into "other" or gets its own facet rather than
# inventing a colour. Verified with the palette validator, light surface:
#   adjacent pairs (lines, bars) — all eight slots pass
#   all pairs (scatter) — the first three pass; scatter here never uses more than three
SLOT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
C = {
    "blue": SLOT[0],
    "orange": SLOT[1],
    "aqua": SLOT[2],
    "green": SLOT[2],       # kept as an alias so existing call sites read naturally
    "yellow": SLOT[3],
    "magenta": SLOT[4],
    "purple": SLOT[6],
    "red": SLOT[7],
    "grey": "#8a8a86",      # recessive ink, never a series
    "black": "#0b0b0b",     # text-primary
    "ink": "#52514e",       # text-secondary
    "surface": "#fcfcfb",
}
SERIES = SLOT
MARKERS = ["o", "s", "^", "D", "v", "P"]


def _style(ax, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
    """Recessive chrome: hairline solid grid one shade off the surface, no top/right rule.

    Solid rather than dashed — a dashed grid reads as "threshold" or "projection" when it
    is only a grid.
    """
    ax.set_title(title, fontsize=10.5, loc="left", pad=9, color=C["black"])
    ax.set_xlabel(xlabel, fontsize=8.5, color=C["ink"])
    ax.set_ylabel(ylabel, fontsize=8.5, color=C["ink"])
    ax.tick_params(labelsize=8, colors=C["ink"])
    ax.grid(True, color="#e6e5e1", linewidth=0.7, linestyle="-")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d8d7d2")
        ax.spines[side].set_linewidth(0.8)


def model_comparison(rows: list[dict]) -> plt.Figure:
    """Quality against cost per model — is there anything to route between?"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

    order = sorted(rows, key=lambda r: -r["accuracy"])
    names = [r["label"] for r in order]
    tiers = {"open": C["green"], "mid": C["blue"], "frontier": C["red"], "?": C["grey"]}
    colors = [tiers.get(r["tier"], C["grey"]) for r in order]

    ax1.barh(range(len(order)), [r["accuracy"] for r in order], color=colors)
    ax1.set_yticks(range(len(order)))
    ax1.set_yticklabels(names, fontsize=8)
    ax1.invert_yaxis()
    _style(ax1, "Measured accuracy per model", "accuracy on graded cells")
    for i, r in enumerate(order):
        ax1.text(r["accuracy"] + 0.006, i, f"{r['accuracy']:.3f}", va="center", fontsize=7)
    ax1.set_xlim(0, max(r["accuracy"] for r in order) * 1.18)

    for r in rows:
        c = tiers.get(r["tier"], C["grey"])
        ax2.scatter(r["cost_per_call_usd"] * 1000, r["accuracy"], s=60, color=c,
                    edgecolor="white", linewidth=0.8, zorder=3)
        ax2.annotate(r["label"], (r["cost_per_call_usd"] * 1000, r["accuracy"]),
                     fontsize=6.5, xytext=(4, 3), textcoords="offset points")
    ax2.set_xscale("log")
    _style(ax2, "Accuracy against realised cost", "USD per call (×10⁻³, log)", "accuracy")
    handles = [plt.Line2D([], [], marker="o", ls="", color=v, label=k)
               for k, v in tiers.items() if k != "?"]
    ax2.legend(handles=handles, fontsize=7, frameon=False, loc="lower right")

    fig.tight_layout()
    return fig


def frontier(rows: list[dict], highlight: float | None = 0.05) -> plt.Figure:
    """The cost/quality dial: savings against quality retained, as λ_c sweeps."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.4))

    save = np.array([100 * r["savings_vs_frontier"] for r in rows])
    qual = np.array([100 * r["quality_vs_frontier"] for r in rows])
    lam = np.array([r["lam_cost"] for r in rows])

    ax1.plot(save, qual, "-", color=C["blue"], linewidth=1.6, zorder=2)
    ax1.scatter(save, qual, s=28, color=C["blue"], zorder=3)
    for s, q, l in zip(save, qual, lam):
        ax1.annotate(f"{l:g}", (s, q), fontsize=6.5, xytext=(4, -8),
                     textcoords="offset points", color=C["grey"])
    if highlight is not None:
        k = int(np.argmin(np.abs(lam - highlight)))
        ax1.scatter([save[k]], [qual[k]], s=150, facecolor="none",
                    edgecolor=C["red"], linewidth=1.8, zorder=4)
        ax1.annotate(f"λ_c={lam[k]:g}\n{save[k]:.0f}% saved\n{qual[k]:.1f}% quality",
                     (save[k], qual[k]), fontsize=7.5, color=C["red"],
                     xytext=(-70, -42), textcoords="offset points")
    ax1.axhline(100, color=C["grey"], ls=":", linewidth=1)
    ax1.annotate("frontier model's quality", (min(save), 100), fontsize=7,
                 color=C["grey"], xytext=(2, 4), textcoords="offset points")
    _style(ax1, "Cost/quality frontier (labels are λ_c)",
           "cost reduction vs frontier model (%)", "quality retained (%)")

    ax2.plot(lam, [r["score_feasible"] for r in rows], "-o", ms=4,
             color=C["green"], label="vs attainable oracle")
    ax2.plot(lam, [r["score_spec"] for r in rows], "-s", ms=4,
             color=C["orange"], label="vs per-item oracle (§8.8)")
    ax2.set_xscale("log")
    _style(ax2, "Score under both oracle definitions", "λ_c (log)",
           "share of gap captured")
    ax2.legend(fontsize=7.5, frameon=False)

    fig.tight_layout()
    return fig


def staleness(result: dict) -> plt.Figure:
    """The §14.1 decay curve — four arms, and where the pool grew."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.6),
                                   gridspec_kw={"height_ratios": [3, 1.1]}, sharex=True)
    weeks = result["weeks"]
    styles = {
        "rolling (B)": (C["blue"], "o", "rolling — keeps learning, takes new models"),
        "frozen (A)": (C["red"], "s", "frozen at T — the published workflow"),
        "refit, no new models (B')": (C["orange"], "^", "refit, but no new models (B′)"),
        "best single": (C["grey"], None, "best single, re-selected weekly"),
    }
    for arm, (color, marker, label) in styles.items():
        ax1.plot(weeks, result["arms"][arm]["score"], color=color, marker=marker,
                 ms=3.5, linewidth=1.5, label=label,
                 ls="--" if arm == "best single" else "-")

    ax1.axhline(0, color=C["black"], linewidth=1.1)
    # Placed in axes fractions rather than data coordinates: the curves reach different
    # depths on different corpora, and a data-anchored label lands on top of them.
    ax1.annotate("below this line, routing is worse than one good model",
                 (0.015, 0.50), xycoords="axes fraction", fontsize=7.5,
                 color=C["black"],
                 bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75,
                       "pad": 1.5})
    # Release markers alternate height so two nearby releases do not overprint.
    for k, (w, models) in enumerate(sorted(result["new_models"].items(),
                                           key=lambda kv: int(kv[0]))):
        wi = int(w)
        ax1.axvline(wi, color=C["green"], ls=":", linewidth=1, alpha=0.8)
        ax1.annotate(", ".join(m.split("/")[-1] for m in models),
                     (wi, 0.985 - 0.14 * (k % 2)), xycoords=("data", "axes fraction"),
                     fontsize=6.5, rotation=90, va="top", ha="right",
                     color=C["green"], xytext=(-2, 0), textcoords="offset points")
    _style(ax1, "A router trained once, as the pool moves underneath it",
           "", "share of the oracle-to-baseline gap captured")
    ax1.legend(fontsize=8, frameon=True, framealpha=0.85, edgecolor="none",
               loc="lower center", ncols=2)

    ax2.step(weeks, result["pool_size"], where="post", color=C["green"], linewidth=1.5)
    ax2.fill_between(weeks, 0, result["pool_size"], step="post",
                     color=C["green"], alpha=0.12)
    _style(ax2, "", "week of the replay", "models in pool")
    ax2.set_ylim(0, max(result["pool_size"]) + 1)

    fig.tight_layout()
    return fig


def staleness_quality(result: dict) -> plt.Figure:
    """The same divergence in units a customer would recognise."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2))
    weeks = result["weeks"]
    for arm, color in (("rolling (B)", C["blue"]), ("frozen (A)", C["red"]),
                       ("best single", C["grey"])):
        ax1.plot(weeks, result["arms"][arm]["quality"], color=color, linewidth=1.5,
                 label=arm, ls="--" if arm == "best single" else "-")
        ax2.plot(weeks, np.cumsum(result["arms"][arm]["cost"]), color=color,
                 linewidth=1.5, label=arm, ls="--" if arm == "best single" else "-")
    _style(ax1, "Answer quality delivered", "week", "mean graded quality")
    _style(ax2, "Cumulative spend", "week", "USD")
    ax1.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    return fig


def gram(result: dict) -> plt.Figure:
    """What the §8.3 shortcut costs as coverage thins."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2))
    rows = result["rows"]
    kinds = ["shared (§8.3)", "per-model (§8.5)"]
    colors = {kinds[0]: C["red"], kinds[1]: C["blue"]}

    for kind in kinds:
        sel = sorted([r for r in rows if r["gram"] == kind], key=lambda r: r["coverage"])
        cov = [100 * r["coverage"] for r in sel]
        ax1.plot(cov, [r["q_hat_thinned"] for r in sel], "-o", ms=4,
                 color=colors[kind], label=kind)
        ax2.plot(cov, [100 * r["share_thinned"] for r in sel], "-o", ms=4,
                 color=colors[kind], label=kind)

    truth = rows[0]["q_true_thinned"]
    ax1.axhline(truth, color=C["black"], ls=":", linewidth=1.2)
    ax1.annotate(f"true quality {truth:.3f}", (100, truth), fontsize=7.5,
                 xytext=(-90, 5), textcoords="offset points")
    for ax in (ax1, ax2):
        ax.set_xscale("log")
        ax.legend(fontsize=8, frameon=False)
    _style(ax1, f"Predicted quality of {result['thinned_model'].split('/')[-1]}",
           "share of its cells observed (%, log)", "predicted quality")
    _style(ax2, "Traffic it receives", "share of its cells observed (%, log)",
           "traffic share (%)")
    fig.tight_layout()
    return fig


def metric_degeneracy(result: dict) -> plt.Figure:
    """Both degeneracies: noise where information is scarce, and luck in the oracle."""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.1))
    bins = result["bins"]["bins"]
    info = [b["mean_info"] for b in bins]

    axes[0].plot(info, [b["raw_sd_mean"] for b in bins], "-o", ms=5,
                 color=C["red"], label="§8.8 as written")
    axes[0].plot(info, [b["shrunk_sd_mean"] for b in bins], "-s", ms=5,
                 color=C["blue"], label="with §6.1 shrinkage")
    _style(axes[0], "Score noise against batch information",
           "batch information (U_oracle − U_base)", "SD of batch score")
    axes[0].legend(fontsize=8, frameon=False)

    rank = result["ranking"]["by_bin"]
    ri = [b["mean_info"] for b in rank]
    axes[1].plot(ri, [b["raw_concordance"] for b in rank], "-o", ms=5,
                 color=C["red"], label="raw")
    axes[1].plot(ri, [b["shrunk_concordance"] for b in rank], "-s", ms=5,
                 color=C["blue"], label="shrunk")
    axes[1].axhline(0.5, color=C["grey"], ls=":", linewidth=1)
    axes[1].annotate("coin flip", (ri[0], 0.5), fontsize=7, color=C["grey"],
                     xytext=(2, 3), textcoords="offset points")
    _style(axes[1], "Does one batch rank policies correctly?",
           "batch information", "concordance with true order")
    axes[1].legend(fontsize=8, frameon=False)

    luck = [r["luck_share"] for r in result["records"]]
    axes[2].hist(luck, bins=30, color=C["orange"], edgecolor="white", linewidth=0.5)
    axes[2].axvline(float(np.mean(luck)), color=C["black"], linewidth=1.4)
    axes[2].annotate(f"mean {np.mean(luck):.1%}", (float(np.mean(luck)), 0),
                     fontsize=8, xytext=(6, 20), textcoords="offset points")
    _style(axes[2], "Share of the §8.8 oracle gap that is luck",
           "unattainable share of U_oracle − U_base", "batches")

    fig.tight_layout()
    return fig


def kappa_tradeoff(sensitivity: dict, tradeoff: dict) -> plt.Figure:
    """κ trades ranking accuracy against how fast a change is noticed.

    Two measures on different scales, so two panels rather than two y-axes. A twin axis
    would let either curve be slid up or down against the other by choosing limits, which
    is exactly the trap when the point is where one crosses the other.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.3), sharex=True)
    smap = {r["quantile"]: r for r in sensitivity["rows"]}
    rows = [r for r in tradeoff["rows"] if r["quantile"] in smap]
    kappa = [r["kappa"] for r in rows]

    ax1.plot(kappa, [smap[r["quantile"]]["concordance"] for r in rows], "-",
             color=SLOT[0], linewidth=2, marker="o", ms=5,
             markeredgecolor="white", markeredgewidth=1.2)
    ax1.axhline(sensitivity["raw_concordance"], color=C["grey"], linewidth=1)
    ax1.annotate(f"raw metric {sensitivity['raw_concordance']:.3f}",
                 (kappa[0], sensitivity["raw_concordance"]), fontsize=7.5,
                 color=C["ink"], xytext=(2, 4), textcoords="offset points")
    ax1.set_xscale("log")
    _style(ax1, "Higher κ ranks policies better…", "κ (log)",
           "concordance with the true order")

    ax2.plot(kappa, [r["detection_lag_batches"] for r in rows], "-",
             color=SLOT[1], linewidth=2, marker="s", ms=5,
             markeredgecolor="white", markeredgewidth=1.2)
    ax2.axhline(tradeoff["raw_detection_lag"], color=C["grey"], linewidth=1)
    ax2.annotate(f"raw metric {tradeoff['raw_detection_lag']:.0f}",
                 (kappa[0], tradeoff["raw_detection_lag"]), fontsize=7.5,
                 color=C["ink"], xytext=(2, 4), textcoords="offset points")
    ax2.set_xscale("log")
    _style(ax2, "…and takes longer to notice a policy change", "κ (log)",
           "batches until the change registers")

    fig.tight_layout(pad=1.4)
    return fig


def coldstart(result: dict) -> plt.Figure:
    """Onboarding curves per prior, and the τ² relationship §5.3 predicts."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.3))
    s = result["summary"]
    grid = result["probe_grid"]

    for i, (prior, series) in enumerate(s["mean_utility_by_prior_and_probe"].items()):
        xs = [max(g, 1) for g in grid]
        ax1.plot(xs, [series[str(g)] for g in grid], "-", marker=MARKERS[i], ms=4,
                 color=SERIES[i], label=prior)
    target = result["rows"][0]["utility_full_router"]
    ax1.axhline(target, color=C["black"], ls=":", linewidth=1.2)
    ax1.annotate("router that always had the model", (grid[1], target), fontsize=7.5,
                 xytext=(2, 4), textcoords="offset points")
    ax1.set_xscale("log")
    _style(ax1, "Onboarding a model the pool has never seen",
           "probe items (log; 1 = none)", "mean utility on held-out items")
    ax1.legend(fontsize=8, frameon=False, loc="lower right")

    material = set(s.get("material_models", []))
    for i, prior in enumerate(s["probe_items_needed"]):
        xs, ys = [], []
        for mid, n in s["probe_items_needed"][prior].items():
            if np.isfinite(n) and mid in material:
                xs.append(s["tau2_by_model"][mid])
                ys.append(n)
        if xs:
            ax2.scatter(xs, ys, s=55, color=SERIES[i], marker=MARKERS[i], label=prior,
                        edgecolor="white", linewidth=0.6)
    _style(ax2, "§5.3's prediction: probe count tracks τ²",
           "τ² (how poorly the pool's factors explain the new model)",
           "probe items needed")
    if ax2.get_legend_handles_labels()[0]:
        ax2.legend(fontsize=8, frameon=False)
    else:
        ax2.annotate("only one model in this pool had a material\nonboarding gap — "
                     "see the table for the per-model detail",
                     (0.5, 0.5), xycoords="axes fraction", fontsize=8.5,
                     ha="center", color=C["grey"])
    fig.tight_layout()
    return fig


def decomposition(result: dict, shock_model: str | None = None) -> plt.Figure:
    """Regret around each injected shock, plus traffic response to a price change."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True)
    weeks = result["weeks"]
    for i, (name, series) in enumerate(result["arms"].items()):
        ax1.plot(weeks, series["regret"], color=SERIES[i], linewidth=1.4, label=name)
    for s in result["shocks"]:
        ax1.axvline(s["week"], color=C["grey"], ls=":", linewidth=1)
        ax1.annotate(f"{s['kind']}", (s["week"], ax1.get_ylim()[1]), fontsize=6.5,
                     rotation=90, va="top", ha="right", color=C["grey"],
                     xytext=(-2, -3), textcoords="offset points")
    _style(ax1, "Regret through injected shocks", "", "normalised regret (§8.8)")
    ax1.legend(fontsize=8, frameon=False)

    shock_model = shock_model or next(iter(next(iter(result["arms"].values()))["share"]))
    for i, (name, series) in enumerate(result["arms"].items()):
        if shock_model in series["share"]:
            ax2.plot(weeks, [100 * v for v in series["share"][shock_model]],
                     color=SERIES[i], linewidth=1.4, label=name)
    for s in result["shocks"]:
        if s["model"] == shock_model:
            ax2.axvline(s["week"], color=C["red"], ls="--", linewidth=1.2)
            ax2.annotate(f"{s['kind']} ×{s['factor']:g}", (s["week"], ax2.get_ylim()[1]),
                         fontsize=7, va="top", color=C["red"],
                         xytext=(3, -3), textcoords="offset points")
    _style(ax2, f"Traffic to {shock_model.split('/')[-1]} — behaviour, not belief",
           "week of the replay", "traffic share (%)")
    fig.tight_layout()
    return fig


def save_all(figs: dict[str, plt.Figure], outdir) -> list[str]:
    """Write every figure as PNG at a size that survives being pasted into a doc."""
    from pathlib import Path

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fig in figs.items():
        path = outdir / f"{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        written.append(str(path))
    return written


# ------------------------------------------------------------------- scaling --
TRAIN_C, VAL_C = C["blue"], C["orange"]


def _log_ticks(ax, values) -> None:
    """Label a log axis at the values actually sampled, not at matplotlib's decades.

    A log scale spanning less than two decades emits minor ticks like "2x10^1 3x10^1
    4x10^1", which collide and read as noise. The sampled points are the meaningful
    positions, so they are the ticks.
    """
    from matplotlib.ticker import NullFormatter

    vals = sorted(set(values))
    ax.set_xticks(vals)
    ax.set_xticklabels([f"{v:g}" for v in vals], fontsize=7.5)
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.tick_params(axis="x", which="minor", length=0)


def _train_val(ax, x, train, val, xlabel, ylabel, title, logx=True,
               train_band=None, val_band=None, annotate_min=True):
    """One panel of a train/validation loss curve.

    Both series on one axis, in the same units — the point of a train/val pair is that the
    gap between them is readable, and a second y-scale would destroy that.
    """
    if logx:
        ax.set_xscale("log")
    if train_band is not None:
        ax.fill_between(x, *train_band, color=TRAIN_C, alpha=0.13, linewidth=0)
    if val_band is not None:
        ax.fill_between(x, *val_band, color=VAL_C, alpha=0.13, linewidth=0)
    ax.plot(x, train, "-", color=TRAIN_C, linewidth=2, marker="o", ms=4.5,
            markeredgecolor="white", markeredgewidth=1.2, label="train", zorder=3)
    ax.plot(x, val, "-", color=VAL_C, linewidth=2, marker="s", ms=4.5,
            markeredgecolor="white", markeredgewidth=1.2, label="validation", zorder=4)
    if annotate_min:
        k = int(np.argmin(val))
        ax.scatter([x[k]], [val[k]], s=150, facecolor="none", edgecolor=C["black"],
                   linewidth=1.4, zorder=5)
        ax.annotate(f"best {val[k]:.4f}\nat {x[k]:g}", (x[k], val[k]), fontsize=7.5,
                    color=C["black"], xytext=(6, 10), textcoords="offset points")
    _style(ax, title, xlabel, ylabel)


def loss_curves(scaling: dict) -> plt.Figure:
    """Six panels: where the loss goes as data, capacity, regularisation and time change."""
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.6))

    lc = scaling["learning_curve"]
    by: dict[int, list[dict]] = {}
    for r in lc:
        by.setdefault(r["n_train"], []).append(r)
    ns = sorted(by)
    tr_m = [float(np.mean([r["train_brier"] for r in by[n]])) for n in ns]
    va_m = [float(np.mean([r["val_brier"] for r in by[n]])) for n in ns]
    tr_s = [float(np.std([r["train_brier"] for r in by[n]])) for n in ns]
    va_s = [float(np.std([r["val_brier"] for r in by[n]])) for n in ns]
    _train_val(
        axes[0, 0], ns, tr_m, va_m, "training items (log)", "Brier score",
        "Loss against data — has the fit converged?",
        train_band=(np.array(tr_m) - np.array(tr_s), np.array(tr_m) + np.array(tr_s)),
        val_band=(np.array(va_m) - np.array(va_s), np.array(va_m) + np.array(va_s)),
        annotate_min=False)
    axes[0, 0].legend(fontsize=8, frameon=False, loc="upper right")
    last = va_m[-2] - va_m[-1] if len(va_m) > 1 else 0
    axes[0, 0].annotate(f"last doubling buys {last:+.5f}", (ns[-1], va_m[-1]),
                        fontsize=7.5, color=C["ink"], ha="right",
                        xytext=(-4, 18), textcoords="offset points")

    cc = sorted(scaling["capacity_curve"], key=lambda r: r["d"])
    _train_val(axes[0, 1], [r["d"] for r in cc], [r["train_brier"] for r in cc],
               [r["val_brier"] for r in cc], "feature dimension d (log)", "Brier score",
               "Loss against capacity — is d ≈ 64 right?")
    _log_ticks(axes[0, 1], [r["d"] for r in cc])
    axes[0, 1].legend(fontsize=8, frameon=False, loc="upper right")

    rc = sorted(scaling["regularisation_curve"], key=lambda r: r["lam"])
    _train_val(axes[0, 2], [r["lam"] for r in rc], [r["train_brier"] for r in rc],
               [r["val_brier"] for r in rc], "ridge penalty λ (log)", "Brier score",
               "Loss against regularisation")
    axes[0, 2].legend(fontsize=8, frameon=False, loc="upper left")

    ol = scaling["online_loss"]
    ax = axes[1, 0]
    ax.plot([r["observations"] for r in ol], [r["val_brier"] for r in ol], "-",
            color=VAL_C, linewidth=2)
    ax.set_xscale("log")
    _style(ax, "Loss as rank-one updates stream in",
           "graded observations absorbed (log)", "validation Brier")
    ax.annotate("each step is exact, not a gradient —\nno learning rate, nothing to diverge",
                (0.97, 0.92), xycoords="axes fraction", fontsize=7.5, color=C["ink"],
                ha="right", va="top")

    bc = sorted(scaling["bucket_curve"], key=lambda r: r["n_buckets"])
    ax = axes[1, 1]
    ax.plot([r["n_buckets"] for r in bc], [r["val_brier"] for r in bc], "-",
            color=VAL_C, linewidth=2, marker="s", ms=5,
            markeredgecolor="white", markeredgewidth=1.2)
    ax.set_xscale("log", base=2)
    _style(ax, "Loss against hash width — collisions the encoder pays for",
           "hash buckets (log₂)", "validation Brier")
    _log_ticks(ax, [r["n_buckets"] for r in bc])

    rel = scaling["reliability"]
    ax = axes[1, 2]
    xs = [b["predicted"] for b in rel["bins"]]
    ys = [b["observed"] for b in rel["bins"]]
    lo, hi = min(xs + ys), max(xs + ys)
    ax.plot([lo, hi], [lo, hi], "-", color=C["grey"], linewidth=1)
    ax.annotate("perfect calibration", (hi, hi), fontsize=7.5, color=C["ink"],
                ha="right", va="bottom")
    ax.plot(xs, ys, "-", color=TRAIN_C, linewidth=2, marker="o", ms=5,
            markeredgecolor="white", markeredgewidth=1.2)
    _style(ax, f"Calibration (ECE {rel['expected_calibration_error']:.4f})",
           "predicted quality", "observed quality")

    fig.tight_layout(pad=1.6)
    return fig


def loss_vs_routing(scaling: dict) -> plt.Figure:
    """Does lower loss buy better routing? Three views, no dual axes anywhere."""
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6))
    cp = scaling["coupling"]

    # Capped at three sweeps: the all-pairs CVD gate passes for the first three slots.
    sweeps = [
        ("data", scaling["learning_curve"], SLOT[0], "o"),
        ("capacity", scaling["capacity_curve"], SLOT[1], "s"),
        ("λ", scaling["regularisation_curve"], SLOT[2], "^"),
    ]

    for ax, xkey, xlabel, corr_key, kind in (
        (axes[0], "val_brier", "validation Brier (absolute forecast)",
         "spearman_val_brier_regret", "Prediction"),
        (axes[1], "val_ranking_loss", "ranking loss (order within an item)",
         "spearman_ranking_loss_regret", "Ranking"),
    ):
        # Starved configurations — a few hundred training items — are terrible on both
        # axes and sit far from everything else. Plotting them compresses the region that
        # carries the answer into one corner, and a log scale over less than a decade only
        # trades that for colliding ticks. They are excluded from the panel and their range
        # is stated instead, which is also the subset the quoted correlation uses.
        excluded = []
        for name, rows, color, marker in sweeps:
            pts, out = [], []
            for r_ in rows:
                if xkey not in r_ or not np.isfinite(r_.get(xkey, np.nan)):
                    continue
                (pts if r_.get("n_train", 10**9) >= 5000 else out).append(
                    (r_[xkey], r_["regret"]))
            excluded += out
            if pts:
                ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=52, color=color,
                           marker=marker, alpha=0.85, edgecolor="white", linewidth=1.2,
                           label=f"{name} sweep", zorder=3)
        rh = cp.get(corr_key.replace("spearman_", "corr_") + "_healthy_only", float("nan"))
        _style(ax, f"{kind} loss against regret   (r = {rh:+.2f})", xlabel,
               "routing regret (§8.8)")
        if excluded:
            lo = min(p[1] for p in excluded)
            hi = max(p[1] for p in excluded)
            ax.annotate(f"{len(excluded)} starved configs (<5k items) off-plot, "
                        f"regret {lo:.2f}–{hi:.2f}", (0.5, 0.02),
                        xycoords="axes fraction", fontsize=7.5, color=C["ink"], ha="center")
        ax.legend(fontsize=8, frameon=False, loc="best")

    cc = sorted(scaling["capacity_curve"], key=lambda r: r["d"])
    d = [r["d"] for r in cc]

    def index01(vals):
        v = np.asarray(vals, dtype=float)
        return (v - v.min()) / max(v.max() - v.min(), 1e-12)

    ax = axes[2]
    ax.set_xscale("log")
    ax.plot(d, index01([r["val_brier"] for r in cc]), "-", color=VAL_C, linewidth=2,
            marker="s", ms=5, markeredgecolor="white", markeredgewidth=1.2,
            label="validation Brier")
    ax.plot(d, index01([r["regret"] for r in cc]), "-", color=SLOT[2], linewidth=2,
            marker="^", ms=5, markeredgecolor="white", markeredgewidth=1.2,
            label="routing regret")
    b_min = d[int(np.argmin([r["val_brier"] for r in cc]))]
    r_min = d[int(np.argmin([r["regret"] for r in cc]))]
    for x, color, label, ypos in ((b_min, VAL_C, f"loss best\nd={b_min}", 0.86),
                                  (r_min, SLOT[2], f"routing best\nd={r_min}", 0.62)):
        ax.axvline(x, color=color, linewidth=1, alpha=0.55)
        ax.annotate(label, (x, ypos), xycoords=("data", "axes fraction"), fontsize=7.5,
                    color=color, ha="center", va="top",
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8,
                          "pad": 1.5})
    _log_ticks(ax, d)
    _style(ax, "They do not agree on the same d",
           "feature dimension d (log)", "each curve indexed to its own 0–1 range")
    ax.legend(fontsize=8, frameon=False, loc="center right")

    fig.tight_layout(pad=1.6)
    return fig


def per_model_loss(scaling: dict) -> plt.Figure:
    """Where the loss actually lives, and which way each model is mis-forecast."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 4.8))
    rows = sorted(scaling["per_model"], key=lambda r: -r["brier"])
    names = [r["model_id"].split("/")[-1] for r in rows]
    y = np.arange(len(rows))

    ax1.barh(y, [r["brier"] for r in rows], color=SLOT[0], height=0.62)
    ax1.set_yticks(y)
    ax1.set_yticklabels(names, fontsize=8)
    ax1.invert_yaxis()
    for i, r in enumerate(rows):
        ax1.text(r["brier"] + 0.003, i, f"{r['brier']:.3f}   AUC {r['auc']:.2f}",
                 va="center", fontsize=7, color=C["ink"])
    ax1.set_xlim(0, max(r["brier"] for r in rows) * 1.48)
    _style(ax1, "Prediction loss per model", "Brier score")

    bias = [r["bias"] for r in rows]
    # Signed error is a diverging measure: two poles, neutral zero rule, no rainbow.
    colors = [SLOT[7] if b > 0 else SLOT[0] for b in bias]
    ax2.barh(y, bias, color=colors, height=0.62)
    ax2.axvline(0, color=C["black"], linewidth=1)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.invert_yaxis()
    _style(ax2, "Calibration bias — right of zero is over-sold",
           "predicted minus observed quality")
    for label, x, color in (("over-predicted →", 0.70, SLOT[7]),
                            ("← under-predicted", 0.04, SLOT[0])):
        ax2.annotate(label, (x, 0.015), xycoords="axes fraction", fontsize=8, color=color)
    fig.tight_layout(pad=1.6)
    return fig


# -------------------------------------------------------------------- chutes --
# Figures for the pool the product actually serves. Every one of these is drawn
# from proxy-backed data (see catalog.CHUTES_PROXY), so each carries the caveat in
# its subtitle rather than relying on the reader to remember it.

_TIER_COLOR = {"open": C["green"], "mid": C["blue"], "frontier": C["red"]}
_PROXY_NOTE = "quality measured on a stand-in model per slot — see catalog.CHUTES_PROXY"


def _footnote(fig, text: str = _PROXY_NOTE) -> None:
    fig.text(0.005, 0.005, text, fontsize=6.5, color=C["grey"], ha="left", va="bottom")


def chutes_pool(rows: list[dict]) -> plt.Figure:
    """What the thirteen models cost and what they score."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 5.0))

    order = sorted(rows, key=lambda r: -r["accuracy"])
    colors = [_TIER_COLOR.get(r["tier"], C["grey"]) for r in order]
    ax1.barh(range(len(order)), [r["accuracy"] for r in order], color=colors, height=0.68)
    ax1.set_yticks(range(len(order)))
    ax1.set_yticklabels([r["label"] for r in order], fontsize=8)
    ax1.invert_yaxis()
    for i, r in enumerate(order):
        mark = "=" if r["proxy_exact"] else ("~" if r["proxy_same_family"] else "?")
        ax1.text(r["accuracy"] + 0.006, i, f"{r['accuracy']:.3f}  {mark}{r['proxy_id']}",
                 va="center", fontsize=6.2, color=C["ink"])
    ax1.set_xlim(0, max(r["accuracy"] for r in order) * 1.72)
    _style(ax1, "Accuracy per Chutes slot (label: the measured stand-in)", "accuracy")

    for r in rows:
        c = _TIER_COLOR.get(r["tier"], C["grey"])
        ax2.scatter(r["cost_per_call_usd"] * 1000, r["accuracy"], s=64, color=c,
                    edgecolor="white", linewidth=0.8, zorder=3)
        ax2.annotate(r["label"], (r["cost_per_call_usd"] * 1000, r["accuracy"]),
                     fontsize=6.4, xytext=(4, 3), textcoords="offset points")
    ax2.set_xscale("log")
    _style(ax2, "Accuracy against cost at published Chutes prices",
           "USD per call (×10⁻³, log)", "accuracy")
    ax2.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=v, label=k)
                        for k, v in _TIER_COLOR.items()],
               fontsize=7.5, frameon=False, loc="lower right")
    fig.tight_layout(pad=1.5)
    _footnote(fig)
    return fig


def chutes_frontier(rows: list[dict], highlight: float = 0.05) -> plt.Figure:
    """The dial: what each λ_c buys and what it gives up."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.6))

    save = np.array([100 * r["savings_vs_frontier"] for r in rows])
    qual = np.array([100 * r["quality_vs_frontier"] for r in rows])
    lam = np.array([r["lam_cost"] for r in rows])

    ax1.plot(save, qual, "-", color=C["blue"], linewidth=1.7, zorder=2)
    ax1.scatter(save, qual, s=30, color=C["blue"], zorder=3)
    for s, q, l in zip(save, qual, lam):
        ax1.annotate(f"{l:g}", (s, q), fontsize=6.5, xytext=(4, -9),
                     textcoords="offset points", color=C["grey"])
    k = int(np.argmin(np.abs(lam - highlight)))
    ax1.scatter([save[k]], [qual[k]], s=165, facecolor="none", edgecolor=C["red"],
                linewidth=1.9, zorder=4)
    ax1.annotate(f"λ_c={lam[k]:g}\n{save[k]:.0f}% cheaper\n{qual[k]:.1f}% of frontier quality",
                 (save[k], qual[k]), fontsize=7.5, color=C["red"],
                 xytext=(12, -46), textcoords="offset points")
    ax1.axhline(100, color=C["grey"], ls=":", linewidth=1)
    _style(ax1, "Cost/quality frontier (labels are λ_c)",
           "cost reduction vs the frontier model (%)", "quality retained (%)")

    tiers = ["open", "mid", "frontier"]
    bottom = np.zeros(len(rows))
    for t in tiers:
        share = np.array([100 * r["tier_mix"][t] for r in rows])
        ax2.bar(range(len(rows)), share, bottom=bottom, color=_TIER_COLOR[t],
                label=t, width=0.72)
        bottom += share
    ax2.set_xticks(range(len(rows)))
    ax2.set_xticklabels([f"{r['lam_cost']:g}" for r in rows], fontsize=7, rotation=45)
    ax2.set_ylim(0, 100)
    _style(ax2, "Where the traffic goes as the dial turns", "λ_c", "share of requests (%)")
    ax2.legend(fontsize=7.5, frameon=False, ncol=3, loc="upper center")
    fig.tight_layout(pad=1.5)
    _footnote(fig)
    return fig


def chutes_traffic(rows: list[dict]) -> plt.Figure:
    """Who actually gets the requests at the operating point, and who earns the slot."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 5.0))

    order = sorted([r for r in rows if r["traffic_share"] is not None],
                   key=lambda r: -r["traffic_share"])
    colors = [_TIER_COLOR.get(r["tier"], C["grey"]) for r in order]
    ax1.barh(range(len(order)), [100 * r["traffic_share"] for r in order],
             color=colors, height=0.68)
    ax1.set_yticks(range(len(order)))
    ax1.set_yticklabels([r["label"] for r in order], fontsize=8)
    ax1.invert_yaxis()
    for i, r in enumerate(order):
        ax1.text(100 * r["traffic_share"] + 0.4, i, f"{100 * r['traffic_share']:.1f}%",
                 va="center", fontsize=7, color=C["ink"])
    ax1.set_xlim(0, max(100 * r["traffic_share"] for r in order) * 1.22)
    _style(ax1, "Share of routed requests at the operating point", "% of requests")

    o2 = sorted(rows, key=lambda r: -r["uniquely_correct_share"])
    ax2.barh(range(len(o2)), [100 * r["uniquely_correct_share"] for r in o2],
             color=[_TIER_COLOR.get(r["tier"], C["grey"]) for r in o2], height=0.68)
    ax2.set_yticks(range(len(o2)))
    ax2.set_yticklabels([r["label"] for r in o2], fontsize=8)
    ax2.invert_yaxis()
    _style(ax2, "Items only this model got right — why a slot is worth keeping",
           "% of held-out items")
    fig.tight_layout(pad=1.5)
    _footnote(fig)
    return fig


def chutes_domains(rows: list[dict]) -> plt.Figure:
    """Router against the best single model, per domain."""
    fig, ax = plt.subplots(figsize=(11.2, 4.8))
    rows = sorted(rows, key=lambda r: -r["items"])
    x = np.arange(len(rows))
    w = 0.27
    ax.bar(x - w, [r["best_quality"] for r in rows], w, color=C["grey"],
           label="best single model (per domain)")
    ax.bar(x, [r.get("router_quality", 0.0) for r in rows], w, color=C["blue"],
           label="router")
    ax.bar(x + w, [r["oracle_quality"] for r in rows], w, color=C["green"],
           label="per-item oracle")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['domain']}\nn={r['items']}" for r in rows], fontsize=7.5)
    _style(ax, "Quality by domain — the router against one model and against the ceiling",
           "", "mean quality")
    ax.legend(fontsize=8, frameon=False, ncol=3)
    fig.tight_layout(pad=1.5)
    _footnote(fig)
    return fig


def chutes_coverage(ablation: dict) -> plt.Figure:
    """More data, worse router — the coverage-bias result."""
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    for mode, color, marker in (("dense", C["blue"], "o"), ("union", C["orange"], "s")):
        arms = [a for a in ablation["arms"] if a["train_on"] == mode]
        arms.sort(key=lambda a: a["ridge_lam"])
        ax.plot([a["ridge_lam"] for a in arms],
                [100 * a["quality_vs_frontier"] for a in arms],
                "-", marker=marker, ms=5, color=color, linewidth=1.6,
                label=f"{mode} core ({arms[0]['train_items']:,} items)")
    ax.axhline(100, color=C["grey"], ls=":", linewidth=1)
    ax.annotate("frontier model's quality", (ax.get_xlim()[0], 100), fontsize=7,
                color=C["grey"], xytext=(4, 4), textcoords="offset points")
    ax.set_xscale("log")
    _style(ax, "Uneven coverage costs more than extra data buys",
           "ridge λ (log)", "quality retained vs frontier (%)")
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    fig.tight_layout(pad=1.5)
    _footnote(fig)
    return fig


def chutes_loss(scaling: dict) -> plt.Figure:
    """Loss against data and against capacity, each beside what it buys the product.

    Two axes rather than one because they disagree, and the disagreement is the
    point: validation loss keeps improving with capacity while savings peak earlier.
    Sizing the model on the loss curve alone would ship the wrong d.
    """
    import collections

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.7))

    by = collections.defaultdict(list)
    for r in scaling["learning_curve"]:
        by[r["n_train"]].append(r)
    ns = sorted(by)
    brier = [float(np.mean([x["val_brier"] for x in by[n]])) for n in ns]
    save = [100 * float(np.mean([x["savings_vs_best_single"] for x in by[n]])) for n in ns]

    ax1.plot(ns, brier, "-o", ms=4.5, color=C["blue"], linewidth=1.7, label="validation Brier")
    _style(ax1, "Learning curve — loss converges by ~2k items",
           "training items", "validation Brier (lower is better)")
    ax1b = ax1.twinx()
    ax1b.plot(ns, save, "-s", ms=4.5, color=C["orange"], linewidth=1.7,
              label="savings vs best single model")
    ax1b.set_ylabel("cost saved vs best single model (%)", fontsize=8.5, color=C["ink"])
    ax1b.tick_params(labelsize=8, colors=C["ink"])
    ax1b.grid(False)
    for s in ("top", "right", "left", "bottom"):
        ax1b.spines[s].set_visible(False)
    ax1.set_xscale("log")
    lines = ax1.get_lines() + ax1b.get_lines()
    ax1.legend(lines, [ln.get_label() for ln in lines], fontsize=7.5,
               frameon=False, loc="center right")

    cap = scaling["capacity_curve"]
    d = [r["d"] for r in cap]
    cb = [r["val_brier"] for r in cap]
    cs = [100 * r["savings_vs_best_single"] for r in cap]
    ax2.plot(d, cb, "-o", ms=4.5, color=C["blue"], linewidth=1.7, label="validation Brier")
    _style(ax2, "Capacity — loss and money do not peak at the same d",
           "feature dimension d", "validation Brier (lower is better)")
    ax2b = ax2.twinx()
    ax2b.plot(d, cs, "-s", ms=4.5, color=C["orange"], linewidth=1.7,
              label="savings vs best single model")
    ax2b.set_ylabel("cost saved vs best single model (%)", fontsize=8.5, color=C["ink"])
    ax2b.tick_params(labelsize=8, colors=C["ink"])
    ax2b.grid(False)
    for s in ("top", "right", "left", "bottom"):
        ax2b.spines[s].set_visible(False)
    bl, bs_ = scaling["coupling"]["best_d_by_loss"], scaling["coupling"]["best_d_by_savings"]
    ax2.axvline(bl, color=C["blue"], ls=":", linewidth=1.2)
    ax2b.axvline(bs_, color=C["orange"], ls=":", linewidth=1.2)
    ax2.annotate(f"best loss\nd={bl}", (bl, max(cb)), fontsize=7, color=C["blue"],
                 xytext=(-32, -6), textcoords="offset points")
    ax2.annotate(f"best savings\nd={bs_}", (bs_, max(cb)), fontsize=7, color=C["orange"],
                 xytext=(4, -6), textcoords="offset points")
    lines = ax2.get_lines()[:1] + ax2b.get_lines()[:1]
    ax2.legend(lines, [ln.get_label() for ln in lines], fontsize=7.5,
               frameon=False, loc="center right")

    fig.tight_layout(pad=1.6)
    _footnote(fig)
    return fig


def chutes_prices(shock: dict) -> plt.Figure:
    """What a price change does to traffic and to the bill, with no refit."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.6))
    pts = shock["points"]
    f = [p["factor"] for p in pts]
    share = [100 * p["target_share_after"] for p in pts]

    ax1.plot(f, share, "-o", ms=5, color=C["blue"], linewidth=1.8)
    ax1.axvline(1.0, color=C["grey"], ls=":", linewidth=1)
    ax1.annotate("today's price", (1.0, max(share)), fontsize=7, color=C["grey"],
                 xytext=(4, -4), textcoords="offset points")
    ax1.set_xscale("log")
    ax1.set_xticks(f)
    ax1.set_xticklabels([f"{x:g}x" for x in f], fontsize=7.5)
    # A log axis draws its own decade ticks underneath these, which collide with them.
    ax1.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax1.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    _style(ax1, f"Traffic follows price — {shock['target_label']}",
           "price multiplier applied to this one model",
           "its share of routed requests (%)")

    frozen = [p["spend_if_frozen_usd"] for p in pts]
    react = [p["spend_after_usd"] for p in pts]
    x = np.arange(len(pts))
    ax2.bar(x - 0.2, frozen, 0.4, color=C["grey"], label="a router that cannot react")
    ax2.bar(x + 0.2, react, 0.4, color=C["blue"], label="this router, no refit")
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{v:g}x" for v in f], fontsize=7.5)
    _style(ax2, "Bill on the same requests after the price change",
           "price multiplier", "spend on held-out traffic (USD)")
    ax2.legend(fontsize=7.5, frameon=False, loc="upper left")
    fig.tight_layout(pad=1.5)
    _footnote(fig, "prices read live from llm.chutes.ai/v1/models — the fitted state is "
                   "byte-identical at every point")
    return fig


def chutes_slots(slots: dict) -> plt.Figure:
    """What the router sends each slot against what a per-item oracle would."""
    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    orc, rtr = slots["oracle_share"], slots["router_share"]
    ids = sorted(orc, key=lambda k: -orc[k])
    short = [k.split("/")[-1].replace("-TEE", "") for k in ids]
    y = np.arange(len(ids))
    ax.barh(y - 0.2, [100 * orc[k] for k in ids], 0.4, color=C["green"],
            label="a per-item oracle would send")
    ax.barh(y + 0.2, [100 * rtr.get(k, 0.0) for k in ids], 0.4, color=C["blue"],
            label="this router sends")
    for i, k in enumerate(ids):
        if rtr.get(k, 0.0) == 0.0:
            ax.text(100 * orc[k] + 0.6, i, "never selected", va="center",
                    fontsize=7.5, color=C["red"])
    ax.set_yticks(y)
    ax.set_yticklabels(short, fontsize=8)
    ax.invert_yaxis()
    _style(ax, "Two slots the router never reaches — and the traffic they are owed",
           "% of held-out requests")
    ax.legend(fontsize=8, frameon=False, loc="lower right")
    fig.tight_layout(pad=1.5)
    _footnote(fig)
    return fig


def chutes_latency(lat: dict) -> plt.Figure:
    """The latency term, switched on for the first time, priced against quality."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.7))

    rows = sorted(lat["per_model"], key=lambda r: r["p95_tokens"])
    y = np.arange(len(rows))
    tiers = {"open": C["green"], "mid": C["blue"], "frontier": C["red"]}
    ax1.barh(y, [r["p95_tokens"] for r in rows],
             color=[tiers.get(r["tier"], C["grey"]) for r in rows], height=0.66)
    for i, r in enumerate(rows):
        ax1.plot([r["p50_tokens"]], [i], marker="|", ms=11, color=C["black"], zorder=3)
    ax1.set_yticks(y)
    ax1.set_yticklabels([r["label"] for r in rows], fontsize=8)
    ax1.invert_yaxis()
    ax1.set_xscale("log")
    _style(ax1, "Output length per model — bar is p95, tick is p50",
           "output tokens (log)")

    sw = lat["lam_latency_sweep"]
    p95 = [s["p95_tokens"] for s in sw]
    q = [s["quality"] for s in sw]
    ax2.plot(p95, q, "-o", ms=5, color=C["blue"], linewidth=1.7)
    for s in sw:
        ax2.annotate(f"λ_l={s['lam_latency']:g}", (s["p95_tokens"], s["quality"]),
                     fontsize=6.8, color=C["grey"], xytext=(5, 4),
                     textcoords="offset points")
    ax2.set_xscale("log")
    _style(ax2, "Turning the latency term on: p95 against quality",
           "routed p95 output tokens (log)", "mean quality")
    fig.tight_layout(pad=1.5)
    _footnote(fig, "output tokens are measured per item; per-request wall-clock is not "
                   "in the corpus — see experiments/latency.py")
    return fig


def chutes_baselines(base: dict) -> plt.Figure:
    """Published strategies on the same items — cost against quality, our dial behind."""
    fig, ax = plt.subplots(figsize=(9.8, 5.4))
    curve = base["our_dial"]
    ax.plot([100 * p["quality_vs_best_single"] for p in curve],
            [100 * p["savings_vs_best_single"] for p in curve],
            "-", color=C["blue"], linewidth=1.8, zorder=2,
            label="this router, across its dial")

    groups = {"cascade": (C["red"], "s"), "matrix": (C["green"], "^"),
              "cheapest": (C["grey"], "D")}
    seen = set()
    for r in base["rows"][1:]:
        key = next((k for k in groups if k in r["policy"]), None)
        if key is None:
            continue
        color, marker = groups[key]
        ax.scatter(100 * r["quality_vs_best_single"], 100 * r["savings_vs_best_single"],
                   s=62, color=color, marker=marker, edgecolor="white", linewidth=0.8,
                   zorder=3, label=key if key not in seen else None)
        seen.add(key)
    ax.axhline(0, color=C["grey"], ls=":", linewidth=1)
    ax.set_ylim(-100, 100)
    _style(ax, "Every strategy on the same held-out items",
           "quality retained vs the best single model (%)",
           "cost saved vs the best single model (%)")
    ax.annotate("cascades below the line spend MORE than doing nothing,\n"
                "because they pay for every attempt",
                (0.03, 0.06), xycoords="axes fraction", fontsize=7.5, color=C["ink"])
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    fig.tight_layout(pad=1.5)
    _footnote(fig)
    return fig
