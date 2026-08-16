#!/usr/bin/env python
"""Generate the analysis notebooks from the cell definitions below.

Authoring notebooks as .ipynb JSON by hand is unpleasant and diffs badly, so the source
of truth is this file and the .ipynb files are build output. Run it, then execute the
notebooks to bake in their outputs:

    python scripts/build_notebooks.py
    python scripts/execute_notebooks.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "notebooks"


def nb(cells: list[tuple[str, str]], title: str) -> dict:
    out = []
    for i, (kind, src) in enumerate(cells):
        lines = src.strip("\n").split("\n")
        source = [l + "\n" for l in lines[:-1]] + [lines[-1]] if lines else []
        # Stable ids: nbformat 4.5+ requires them, and deriving them from the index
        # keeps a rebuilt notebook diffing cleanly against the previous build.
        cell_id = f"c{i:03d}"
        if kind == "md":
            out.append({"cell_type": "markdown", "id": cell_id, "metadata": {},
                        "source": source})
        else:
            out.append({"cell_type": "code", "id": cell_id, "execution_count": None,
                        "metadata": {}, "outputs": [], "source": source})
    return {
        "cells": out,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.13"},
            "title": title,
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


PRELUDE = """
import sys; sys.path.insert(0, "..")
from notebooks.nbhelp import load, table, pct, show, md, finding
import numpy as np, pandas as pd
"""

# ============================================================ 01 · data and pool ==
N1 = [
    ("md", """
# 01 · The data, and the pool

Before any router: what is being routed over, and is there anything to route between?

Every number in this notebook comes from **RouterBench** (`withmartian/routerbench`,
0-shot split) — 36,497 real prompts, each answered by 11 real commercial models, with
the graded outcome and the realised dollar cost of every call. 401,467 measured cells,
about $334 of inference someone else already paid for. Nothing here is simulated.

The three questions, in order:

1. Do most queries really not need the strongest model? (The savings pool.)
2. Are the models actually different from each other? (Is routing possible at all?)
3. Where does each model win? (Is there a reason to keep more than two?)
"""),
    ("code", PRELUDE),
    ("code", """
ov = load("overview")
c = ov["corpus"]
md(f\"\"\"
| | |
|---|---|
| corpus | {c['source']} |
| items | {c['items']:,} |
| models | {c['models']} |
| graded cells | {c['cells']:,} |
| density | {pct(c['density'])} (every model answered every item) |
| mean graded quality | {c['mean_quality']:.4f} |
| measured inference cost | ${c['total_cost_usd']:,.2f} |
\"\"\")
for n in c["notes"]:
    print("·", n)
"""),
    ("md", """
## 1. Most queries do not need the strongest model

RollingBench §3.1 leans on a published figure — pairwise comparisons between models were
ties 52.9% to 61.7% of the time — and treats that band as the size of the savings pool.
That figure came from a different study on 895 prompts. Here it is recomputed from
scratch on 401,467 cells of our own.
"""),
    ("code", """
t = ov["ties"]
md(f\"\"\"
| measurement | value |
|---|---|
| pairwise tie rate | **{pct(t['pairwise_tie_rate'])}** |
| model pairs compared | {t['pairs_compared']:,} |
| items where the whole pool agrees | {pct(t['unanimous_item_rate'])} |
\"\"\")
finding("supported",
        f"{pct(t['pairwise_tie_rate'])} of model pairs score identically on the same item — "
        f"inside the 52.9–61.7% band §3.1 quotes, measured independently on 2.0M pairs. "
        f"Over half of all traffic can move to a cheaper model with no measured quality change.")
"""),
    ("md", """
## 2. The models are genuinely different

A tie rate above 50% says *most* queries are easy. It does not say the models are
interchangeable. The spread below is what routing has to work with: accuracy from 0.20
to 0.78, and cost per call spanning nearly two orders of magnitude.

`uniquely_correct` is the column that justifies a model's slot in the pool — items where
that model is the *only* one in the pool to get it right. A model with none of those is
paying rent.
"""),
    ("code", """
df = pd.DataFrame(ov["models"]).sort_values("accuracy", ascending=False)
view = df[["label", "tier", "released", "accuracy", "cost_per_call_usd",
           "price_out_per_1m", "uniquely_correct", "uniquely_correct_share"]].copy()
view.columns = ["model", "tier", "released", "accuracy", "$/call",
                "$/1M out", "uniquely correct", "share"]
view
"""),
    ("code", """
show("01_model_comparison",
     "Left: measured accuracy. Right: accuracy against realised cost per call, log scale. "
     "The vertical spread at any given cost is the room a router has to work in.")
"""),
    ("code", """
best, worst = df.iloc[0], df.iloc[-1]
cheap = df.loc[df["cost_per_call_usd"].idxmin()]
md(f\"\"\"
- Strongest: **{best['label']}** at {best['accuracy']:.3f}, costing ${best['cost_per_call_usd']*1000:.3f} per call.
- Weakest: **{worst['label']}** at {worst['accuracy']:.3f}.
- Cheapest: **{cheap['label']}** at ${cheap['cost_per_call_usd']*1000:.3f} per call — {best['cost_per_call_usd']/cheap['cost_per_call_usd']:.0f}× cheaper than the strongest, at {cheap['accuracy']/best['accuracy']:.0%} of its accuracy.
\"\"\")
finding("supported",
        f"The pool spans {df['accuracy'].min():.2f}–{df['accuracy'].max():.2f} in accuracy and "
        f"{df['cost_per_call_usd'].max()/df['cost_per_call_usd'].min():.0f}× in price. "
        f"§14.3's advice to choose for complementary strengths and a wide price spread is "
        f"satisfied by this pool, so a routing result on it is not an artefact of a pool "
        f"where nothing could be decided.")
"""),
    ("md", """
## 3. Where each model wins

If one model won every domain there would be no case for a population of policies, and
§16.2's argument for rewarding specialists would collapse. The table below assigns each
domain to whichever model is best on it, and to whichever gives the most accuracy per
dollar — two different questions with two different answers.
"""),
    ("code", """
dom = pd.DataFrame(ov["domains"]).sort_values("items", ascending=False)
view = dom[["domain", "items", "best_quality_model", "best_quality",
            "best_value_model", "spread", "oracle_quality"]].copy()
view.columns = ["domain", "items", "best on quality", "its accuracy",
                "best per dollar", "pool spread", "per-item oracle"]
view
"""),
    ("code", """
n_q = dom["best_quality_model"].nunique(); n_v = dom["best_value_model"].nunique()
md(f\"\"\"
Across {len(dom)} domains, **{n_q}** different models are the best on quality and
**{n_v}** are the best per dollar. The two lists barely overlap.
\"\"\")
finding("supported",
        f"{n_q} models each win at least one domain on quality and {n_v} win on value. "
        f"A single global ranking would discard that, which is the concrete form of "
        f"§16.2's specialist argument.")
"""),
    ("md", """
## 4. The one number to carry forward

Look at the `per-item oracle` column: it is far above the best single model everywhere.
On the full corpus, some model gets **95.9%** of items right, while the best individual
model gets 78.1%.

That gap is not all available. Most of it is luck — a weak model guessing a
multiple-choice item correctly. Notebook 05 measures exactly how much (about half), and
that measurement turns out to matter for the scoring rule the whole incentive design
rests on. It is flagged here because it is the single easiest way to overstate what a
router can do.
"""),
    ("code", """
sr = ov["solve_rate_percentiles"]
md("Solve-rate distribution across items — the share of the pool that gets each item right:\\n\\n"
   + " · ".join(f"p{k}: {v:.2f}" for k, v in sr.items()))
"""),
]

# ======================================================= 02 · the router engine ==
N2 = [
    ("md", """
# 02 · The router engine, and what it saves

The estimator is RollingBench §8: a ridge regression per model over a 64-dimensional
frozen feature map, with a LinUCB uncertainty term, closed-form throughout. No gradient
descent, no GPU, no training job — one matrix solve, and rank-one updates as outcomes
arrive.

This notebook answers the commercial question: **routed against one strong model, what
does it cost and what does it deliver?**
"""),
    ("code", PRELUDE),
    ("md", """
## The dial, not the number

λ_c is the cost weight in §8.7's decision rule, and it is the frontend's cost/quality
control. Quoting a single savings figure without it would be picking a point on a curve
and calling it a result, so here is the whole curve. It reads as "how much quality am I
willing to give up to save the cost of one frontier call".
"""),
    ("code", """
fr = load("frontier")
sw = pd.DataFrame(fr["sweep"])
view = sw[["lam_cost", "quality", "quality_vs_frontier", "cost_usd",
           "savings_vs_frontier", "score_feasible", "regret_spec", "models_used"]].copy()
view.columns = ["λ_c", "quality", "vs frontier", "cost $", "saved",
                "score (attainable)", "regret (§8.8)", "models used"]
view.style.format({"λ_c": "{:g}", "quality": "{:.4f}", "vs frontier": "{:.1%}",
                   "cost $": "${:.2f}", "saved": "{:.1%}",
                   "score (attainable)": "{:+.3f}", "regret (§8.8)": "{:.3f}"})
"""),
    ("code", """
show("02_frontier",
     "Left: every operating point, labelled with its λ_c. Right: the same policies scored "
     "against both oracle definitions — the attainable per-task oracle and §8.8's per-item one.")
"""),
    ("code", """
op = sw.loc[(sw["lam_cost"] - 0.05).abs().idxmin()]
cheap40 = sw.iloc[(sw["savings_vs_frontier"] - 0.40).abs().idxmin()]
md(f\"\"\"
At **λ_c = {op['lam_cost']:g}** the router spends **${op['cost_usd']:.2f}** where sending
everything to the frontier model costs **${op['cost_usd']/(1-op['savings_vs_frontier']):.2f}** —
a **{pct(op['savings_vs_frontier'])} cost reduction** while delivering
**{pct(op['quality_vs_frontier'])}** of that model's measured quality, on
{int(load('manifest')['n_test']):,} held-out items it never saw during fitting.
\"\"\")
finding("supported",
        f"The frontend's headline — a ~40% cut on everyday traffic — is met and slightly "
        f"exceeded: {pct(cheap40['savings_vs_frontier'])} cheaper at "
        f"{pct(cheap40['quality_vs_frontier'])} of frontier quality. Pushed harder, "
        f"{pct(sw.iloc[-4]['savings_vs_frontier'])} cheaper is available at "
        f"{pct(sw.iloc[-4]['quality_vs_frontier'])} quality.")
"""),
    ("md", """
## Against every alternative, including the ones that make it look worse

A savings figure means nothing without the controls. `random` shows how much of the gap
comes from merely not always picking the dearest model. `per-task table` is a strong
non-ML baseline — one lookup table of best-model-per-benchmark, learned on the training
split — and a router that cannot beat it is not worth its complexity.
"""),
    ("code", """
pol = pd.DataFrame(fr["policies"])
view = pol[["policy", "kind", "quality", "cost_usd", "savings_vs_frontier",
            "utility", "score_spec", "score_feasible", "models_used"]].copy()
view.columns = ["policy", "kind", "quality", "cost $", "saved", "utility",
                "score (§8.8)", "score (attainable)", "models"]
view.style.format({"quality": "{:.4f}", "cost $": "${:.2f}", "saved": "{:.1%}",
                   "utility": "{:.4f}", "score (§8.8)": "{:.3f}",
                   "score (attainable)": "{:+.3f}"})
"""),
    ("code", """
r = pol.set_index("policy")
router = r.loc["router: §8 ridge+LinUCB"]
tbl = r.loc["per-task table (train)"]
qonly = r.loc["router: quality only"]
md(f\"\"\"
- The router captures **{router['score_feasible']:.1%}** of the gap between the best
  single model and the best attainable per-task assignment.
- It beats the per-task lookup table ({tbl['score_feasible']:.1%}) — so the per-item
  signal in the prompt is real, not just benchmark identity in disguise.
- With the cost term switched off it reaches {qonly['quality']:.4f} quality, *above* the
  frontier model's own {r.loc['frontier only']['quality']:.4f}, at
  {pct(qonly['savings_vs_frontier'])} of the saving. Routing improves quality and cost
  along different axes, and λ_c is how you choose between them.
\"\"\")
finding("supported",
        f"Routing beats the best single model on cost at near-equal quality, and beats a "
        f"strong non-ML baseline. AC-1's *direction* holds. Its threshold does not — see below.")
"""),
    ("md", """
## Where AC-1 cannot be met, and why that is the metric's fault

AC-1 asks for normalised regret below 0.6. The `regret (§8.8)` column never comes close:
the best operating point sits near 0.9. That is not the router failing.

§8.8 defines the oracle as the argmax of *realised* outcomes per item. On binary grading
that argmax banks luck. Notebook 05 measures the consequence — about **half** the
oracle-to-baseline gap is unreachable by any policy — and shows that a clairvoyant
per-task oracle also scores near zero under the same definition. A threshold no
achievable policy can reach is a threshold about the metric, not about the router.

The `score (attainable)` column is the same quantity measured against a ceiling a policy
could actually hit, and there the router reads 0.7–0.9 depending on the dial.
"""),
    ("code", """
man = load("manifest")
md(f\"\"\"
### Cost of running the thing

| | |
|---|---|
| feature dimension d | {man['feature_dim']} |
| policy artifact | {sw.iloc[0]['artifact_kb']:.0f} KB |
| fit | one pass, seconds, CPU only |
| update per observation | O(d²) ≈ 4,000 flops |
| GPU | none, at fit or serve time |

§8.9's claims about size and cost hold. The artifact is larger than the ~210 KB the
document quotes, for a reason worth knowing: that budget assumes one Gram matrix per
model shared across all three prediction targets, and giving quality and token-count
their own decay rates — Contribution 1 — makes them two matrices instead of one.
Notebook 06 returns to this.
\"\"\")
"""),
]

# ========================================================== 03 · the staleness ==
N3 = [
    ("md", """
# 03 · Does a router trained once actually decay?

This is the load-bearing experiment. RollingBench §14.1 is explicit that everything else
is downstream of it: *"There is no published experiment in which a router is trained at
time T and evaluated at T plus three months against a pool that has moved... that belief
is the load-bearing assumption of this proposal."*

The replay is retrospective and cost nothing to run. RouterBench's eleven models carry
real announcement dates from March to December 2023, so calendar time is a real axis:
pick a cut-off, let the pool grow as it actually grew, and watch four policies diverge.

| arm | what it is |
|---|---|
| **frozen (A)** | fitted once at T, never updated, cannot select a model released after T |
| **rolling (B)** | absorbs each week's outcomes; new models arrive with a cold-start probe |
| **refit, no new models (B′)** | keeps learning, but is never given the new models |
| **best single** | one model, everything sent to it, re-selected weekly |

B′ is the arm that makes the study conclusive. Without it, a frozen router losing ground
could be explained by stale data or by missing models, and those call for entirely
different engineering.
"""),
    ("code", PRELUDE),
    ("code", """
st = load("staleness"); res = st["result"]; s = st["summary"]
md(f"Replay: {len(res['weeks'])} weeks × {res['config']['batch_items']} fresh items per week, "
   f"cut-off **{res['config']['cutoff']}**, pool growing {min(res['pool_size'])} → "
   f"{max(res['pool_size'])} models.")
for n in res["notes"]:
    print("·", n)
"""),
    ("code", """
show("03_staleness",
     "Top: share of the oracle-to-baseline gap each arm captures, week by week. Green dotted "
     "lines mark real model releases. Bottom: the pool growing underneath all four arms.")
"""),
    ("code", """
rows = []
for arm in ["frozen (A)", "rolling (B)", "refit, no new models (B')", "best single"]:
    a = res["arms"][arm]
    rows.append({"arm": arm,
                 "score, first 4 weeks": np.mean(a["score"][:4]),
                 "score, last 4 weeks": np.mean(a["score"][-4:]),
                 "change": np.mean(a["score"][-4:]) - np.mean(a["score"][:4]),
                 "quality, first 4": np.mean(a["quality"][:4]),
                 "quality, last 4": np.mean(a["quality"][-4:]),
                 "total spend $": np.sum(a["cost"])})
pd.DataFrame(rows).set_index("arm")
"""),
    ("code", """
md(f\"\"\"
The frozen router falls from **{s['frozen_start']:+.3f}** to **{s['frozen_end']:+.3f}** —
a decay of **{s['frozen_decay']:.3f}** — and crosses below the "one good model" line at
week **{s['week_crossed_below_best_single']}**, after which routing is actively worse than
not routing. The rolling router over the same period moves
**{s['rolling_start']:+.3f} → {s['rolling_end']:+.3f}**: no decay at all.

The gap between them widens from **{s['gap_first_half']:+.3f}** in the first half of the
replay to **{s['gap_second_half']:+.3f}** in the second.
\"\"\")
finding("supported",
        f"A router trained once decays materially — {s['frozen_decay']:.3f} over "
        f"{len(res['weeks'])} weeks — and ends up worse than sending everything to one "
        f"good model. §14.1's decision gate is passed: the premise survives, so the rest "
        f"of the system has a reason to exist.")
"""),
    ("md", """
## The part the proposal did not predict

Arm B′ separates the two causes, and the split is not what the framing of the proposal
suggests. RollingBench's title is *RollingBench* — the pitch is continuous re-evaluation,
fresher data, a benchmark that never goes stale. But:
"""),
    ("code", """
tot = s["attribution_new_models"] + s["attribution_fresher_data"]
md(f\"\"\"
| cause | recovered score |
|---|---|
| access to models released after T | **{s['attribution_new_models']:+.3f}** ({s['attribution_new_models']/tot:.0%}) |
| fresher training data on the same models | {s['attribution_fresher_data']:+.3f} ({s['attribution_fresher_data']/tot:.0%}) |
\"\"\")
finding("new",
        f"Essentially all of the recoverable decay — {s['attribution_new_models']/tot:.0%} of it — "
        f"comes from being able to select models that did not exist at training time. "
        f"Continuously refitting on the same pool recovers almost nothing "
        f"({s['attribution_fresher_data']:+.3f}). The binding constraint is pool coverage and "
        f"cold start (FR-15's 24-hour onboarding), not evaluation freshness.")
"""),
    ("md", """
That reorders the engineering. If the value is in onboarding new models fast rather than
in re-grading old ones daily, then the expensive daily sweep of the whole pool over fresh
items is buying the less valuable half, and the catalogue watcher plus the cold-start
probe are buying the more valuable half. Notebook 04 is about whether that cold start
actually works, and finds the hard case is exactly the one that matters here.

A caveat on scope, stated plainly: this replay holds the item distribution fixed, so it
measures decay from the pool moving and from data ageing. It does not measure workload
drift or contamination, which are two of the five causes §3.3 lists. Those need a corpus
with dated items, which RouterBench is not.
"""),
    ("code", """
show("04_staleness_quality",
     "The same divergence in units a customer would recognise: delivered answer quality, "
     "and cumulative spend.")
"""),
    ("code", """
new = res["new_models"]
md("### When each model arrived, and what happened\\n\\n" + "\\n".join(
    f"- **week {w}** — {', '.join(m.split('/')[-1] for m in ms)}" for w, ms in sorted(new.items(), key=lambda kv: int(kv[0]))))
"""),
]

# ============================================================ 04 · cold start ==
N4 = [
    ("md", """
# 04 · Cold start: onboarding a model the pool has never seen

Notebook 03 found that nearly all recoverable decay comes from access to new models. So
this is the mechanism that matters most, and it is Contribution 2's territory.

RollingBench §8.6 warm-starts a new model by blending an IRT ability estimate with a
low-rank matrix completion, "down-weighted by a confidence factor" that the document
never writes down. Contribution 2 (§5) replaces that with one conjugate Bayesian step:
no free parameter, and a closed-form prediction of how many probe items a model needs as
a function of how well the existing pool explains it.

That derivation rests on a bridge — §5.1's assumption that the low-rank item factors are
approximately linear in the same feature map. The proposal is emphatic that checking it
comes first: *"Run it first; if the bridge doesn't hold, that contribution needs rework
or drops from the paper before more time is spent on it."*

So: the bridge, then the sample complexity.
"""),
    ("code", PRELUDE),
    ("md", """
## 7.4 — the precondition

Fit Φ once on the existing pool by regressing each model's known low-rank column onto its
known feature-space weights, and measure the residual. If a single Φ carries all eleven
models, the bridge holds.
"""),
    ("code", """
cs = load("coldstart"); b = cs["bridge"]
md(f\"\"\"
| | |
|---|---|
| bridge R² | **{b['bridge_r2']:.3f}** |
| unexplained variance | {pct(b['bridge_residual_ratio'])} |
| τ² (fitted residual variance) | {b['tau2']:.5f} |
| rank r | {b['rank']} |
| items fitted on | {b['n_items_fitted']:,} |
\"\"\")
finding("not-supported", b["verdict"])
"""),
    ("md", """
An R² of 0.26 means the item-space prediction explains about a quarter of the variance in
the feature-space weights. The proposal's own gate says that is not enough to build on,
and it should be reported that way rather than pushed through.

But the per-model breakdown is where this becomes interesting rather than merely
negative. It asks a slightly different question — how well is each model's column
predicted by the *other* models' latent factors — and the answer varies enormously.
"""),
    ("code", """
ld = pd.DataFrame(b["per_model_loading"]).T.sort_values("r2", ascending=False)
ld.index.name = "held-out model"; ld.columns = ["R² from the other models", "residual variance"]
ld
"""),
    ("code", """
top, bottom = ld.index[0], ld.index[-1]
md(f\"\"\"
**{top}** is predicted at R² = {ld.iloc[0, 0]:.3f} by the rest of the pool — it is "another
model like the ones we have". **{bottom}** is predicted at R² = {ld.iloc[-1, 0]:.3f}:
*nothing in the pool anticipates it*.
\"\"\")
finding("new",
        f"Loading onto the pool's latent factors ranges from {ld.iloc[-1,0]:+.3f} to "
        f"{ld.iloc[0,0]:+.3f}. The variation §5.3 predicts is real and large. But it runs "
        f"the wrong way for the use case: the frontier outlier — the model whose arrival "
        f"caused all the decay in notebook 03 — is precisely the one the pool cannot "
        f"predict. Matrix-completion cold start works for models that resemble the pool "
        f"and fails for the ones that matter.")
"""),
    ("md", """
## 7.2 — sample complexity, measured

Leave-one-model-out, eleven times. Hide a model, fit the router on the other ten, then
onboard it with *n* probe items under three priors and route the held-out items.

The target is a router that had the model all along. Measuring the deficit against that
turns the answer into a sample complexity — how many probe items until onboarding has
paid for itself — rather than a statement about how valuable that model happened to be.
"""),
    ("code", """
lomo = cs["lomo"]; s = lomo["summary"]
u = pd.DataFrame(s["mean_utility_by_prior_and_probe"]).T
u.columns = [f"n={c}" for c in u.columns]; u.index.name = "prior"
md(f"Mean utility on held-out items. Target (router that always had the model): "
   f"**{lomo['rows'][0]['utility_full_router']:.4f}**")
u
"""),
    ("code", """
show("08_coldstart",
     "Left: onboarding curves. Right: probe items needed against τ² — §5.3's prediction that "
     "the count should track how poorly the pool explains the new model.")
"""),
    ("md", """
Two things in that table are worth stopping on.

**The dip.** Every prior gets *worse* between 10 and 50 probe items than at zero, before
recovering. A partially-learned column is worse than an absent one: the estimate is
confident enough to be selected and wrong enough to hurt. That is a real operational
hazard for FR-15's 24-hour onboarding promise, and it argues for gating a new model on a
minimum probe size rather than making it selectable as soon as it has any data.

**Most models do not matter.** The per-model gaps below show that only one of eleven had
a material onboarding gap at all.
"""),
    ("code", """
gap = pd.Series(s["onboarding_gap_at_zero_probe"]).sort_values(ascending=False)
need = pd.DataFrame(s["probe_items_needed"])
tau = pd.Series(s["tau2_by_model"])
out = pd.concat([gap.rename("gap at n=0"), need], axis=1).sort_values("gap at n=0", ascending=False)
out
"""),
    ("code", """
mat = s["material_models"]
md(f\"\"\"
Only **{', '.join(mat)}** had an onboarding gap worth closing ({gap.iloc[0]:.4f}); every
other model's arrival left the pool's achievable utility essentially unchanged.

For that one model, the priors do differ: **{int(need.loc[mat[0], 'derived (§5.2)'])}** probe
items with the derived prior and **{int(need.loc[mat[0], 'blend (§8.6)'])}** with the informal
blend, against **{int(need.loc[mat[0], 'no prior'])}** with none.
\"\"\")
finding("mixed",
        f"The derived prior halves the probe requirement for the one model whose onboarding "
        f"mattered ({int(need.loc[mat[0], 'derived (§5.2)'])} vs "
        f"{int(need.loc[mat[0], 'no prior'])} items), and τ² correlates with probe count at "
        f"{s['tau2_vs_probe_correlation']['derived (§5.2)']:+.2f} — so §5.3's shape is right. "
        f"But the bridge it is derived through explains only 26% of the variance, and n=1 "
        f"material model is not a sample. Directionally supported, not established.")
"""),
    ("code", """
md("### τ² against probe count, per prior\\n\\n" + "\\n".join(
    f"- {k}: r = {v:+.3f}" for k, v in s["tau2_vs_probe_correlation"].items())
   + "\\n\\nPositive correlations mean a model the pool explains poorly needs more probing, "
     "which is the direction §5.3 predicts.")
"""),
]

# ================================================================ 05 · metric ==
N5 = [
    ("md", """
# 05 · The scoring rule, and two ways it breaks

§8.8's normalised regret is what the whole incentive design pays on. Miners earn
emissions in proportion to it (§16.1), so a defect in this formula is not an academic
matter — it is money moving to the wrong participant.

    regret = (U_oracle − U_policy) / (U_oracle − U_base + eps)

Contribution 3 (§6) identifies one defect: on an uninformative batch, where every model
performs about the same, U_oracle and U_base converge, the denominator collapses toward
`eps`, and the score becomes noise wearing a confident-looking number. Given the tie rate
from notebook 01, that should be common rather than rare.

Reproducing it turned up a second defect that neither document mentions.
"""),
    ("code", PRELUDE),
    ("code", """
mt = load("metric"); res = mt["result"]
md(f"{res['config']['n_batches']} batches of {res['config']['batch_items']} real held-out "
   f"items each, four policies of genuinely different strength (different amounts of "
   f"training data, so the true ordering is known by construction), κ calibrated at "
   f"{res['config']['kappa']:.4f}.")
pd.Series(res["true_utility"]).sort_values(ascending=False).rename("true utility over the full test split").to_frame()
"""),
    ("md", """
## Defect 1 — score noise where information is scarce

Bin the batches by how much they actually discriminate (`U_oracle − U_base`) and measure
the spread of each policy's score within each bin.
"""),
    ("code", """
bins = pd.DataFrame([{ "bin": b["bin"], "mean information": b["mean_info"],
                       "batches": b["n_batches"], "raw SD": b["raw_sd_mean"],
                       "shrunk SD": b["shrunk_sd_mean"], "reduction": b["sd_reduction"]}
                     for b in res["bins"]["bins"]])
bins.set_index("bin")
"""),
    ("code", """
lo, hi = bins.iloc[0], bins.iloc[-1]
md(f\"\"\"
Score SD is **{lo['raw SD']:.4f}** in the least informative bin against
**{hi['raw SD']:.4f}** in the most — **{lo['raw SD']/hi['raw SD']:.0%}** as noisy, on the
same policies, differing only in which items the batch happened to contain.
\"\"\")
finding("supported",
        f"Contribution 3's premise holds: batch score noise rises monotonically as batch "
        f"information falls ({lo['raw SD']/hi['raw SD']:.0%} more noise in the lowest bin). "
        f"A miner scored on an uninformative batch is being ranked on luck.")
"""),
    ("md", """
### Does the fix work? Ask the question that decides emissions

Reducing variance is easy — always report the same number and the variance is zero. The
question that matters for §16 is whether a single batch *ranks the policies correctly*,
because that ranking is what the payout is computed from.
"""),
    ("code", """
rank = pd.DataFrame([{ "bin": b["bin"], "mean information": b["mean_info"],
                       "raw concordance": b["raw_concordance"],
                       "shrunk concordance": b["shrunk_concordance"],
                       "raw top-1": b["raw_top1_accuracy"],
                       "shrunk top-1": b["shrunk_top1_accuracy"]}
                     for b in res["ranking"]["by_bin"]])
rank.set_index("bin")
"""),
    ("code", """
show("06_metric",
     "Left: score noise against batch information, before and after shrinkage. Middle: whether "
     "one batch recovers the true policy ordering. Right: how much of the §8.8 oracle gap is luck.")
"""),
    ("code", """
o = res["ranking"]["overall"]
md(f\"\"\"
Concordance with the true ordering rises from **{o['raw_concordance']:.3f}** to
**{o['shrunk_concordance']:.3f}**. Top-1 accuracy — does the batch identify the single best
policy — goes from {rank['raw top-1'].mean():.1%} to {rank['shrunk top-1'].mean():.1%}.
\"\"\")
finding("supported",
        f"The §6.1 shrinkage improves what the payout actually depends on: ranking "
        f"concordance {o['raw_concordance']:.3f} → {o['shrunk_concordance']:.3f}. It does not "
        f"behave quite as §6 describes, though — it reduces noise in the high-information "
        f"bins too, because on this corpus batch information varies too little for the "
        f"weight to saturate near 1. It is a general smoother here, not a targeted fix.")
"""),
    ("code", """
md(f\"\"\"
One number worth sitting with: even under the best configuration, a single
{res['config']['batch_items']}-item batch identifies the genuinely best of four policies
only **{rank['shrunk top-1'].max():.0%}** of the time. §16.2 smooths scores across rounds
with β ≈ 0.8, which helps — but paying emissions on single-batch scores means paying
substantially on noise, and the batch would need to be far larger for that not to be true.
\"\"\")
"""),
    ("code", """
dg = res["diagnosis"]
md(f\"\"\"
### But §6 is wrong about *why*

The fix works. Its stated diagnosis does not, and the difference changes what an operator
should do about it.

| | |
|---|---|
| §6's account | {dg['section_6_predicts']} |
| measured | **{dg['measured']}** |
| corr(information, best-minus-worst model) | **{dg['corr_info_vs_model_spread']:+.2f}** |
| corr(information, best-minus-second model) | **{dg['corr_info_vs_dominance']:+.2f}** |
\"\"\")
finding("correction", dg["reading"])
"""),
    ("md", """
The mechanism is the same luck that shows up again below. When every model performs about
the same, per-item noise lets the realised-outcome oracle beat *any* single model by a wide
margin — so the denominator is large and the score is stable. The denominator collapses
when one model dominates, because then the best single model is already nearly as good as
the oracle and there is almost no gap to normalise by.

This matters practically: §6's account suggests helping the metric by keeping challenge
batches hard and filtering out the easy ones. On this data that would discard the
informative batches and keep the degenerate ones.
"""),
    ("md", """
## Defect 3 — half the oracle is luck

This one is not in either document.

§8.8's oracle is the argmax of *realised* outcomes per item. On binary grading, that
argmax banks luck: if any model in the pool happened to answer an item correctly, the
oracle takes the credit, and no policy could have predicted which one. Notebook 01 showed
95.9% of items have at least one model correct while the best individual model manages
78.1%.

The measurement: compare §8.8's per-item oracle against the best attainable per-task
assignment on the same batch, and take the difference as a share of the gap the metric
divides by.
"""),
    ("code", """
lk = res["oracle_luck"]
md(f\"\"\"
| | |
|---|---|
| mean luck share of the gap | **{pct(lk['mean_luck_share_of_gap'])}** |
| median | {pct(lk['median_luck_share_of_gap'])} |
| 5th–95th percentile | {pct(lk['p5'])} – {pct(lk['p95'])} |
\"\"\")
finding("new",
        f"About {pct(lk['mean_luck_share_of_gap'])} of the oracle-to-baseline gap that §8.8 "
        f"divides by is unattainable by any policy. Every score is deflated by roughly that "
        f"factor, which is why a clairvoyant per-task oracle scores 0.078 under this metric "
        f"and why AC-1's 'regret below 0.6' cannot be met by any router. The threshold is "
        f"unreachable by construction, not by weakness.")
"""),
    ("md", """
The fix is not complicated: define the oracle over *conditionally expected* outcomes, or
over item groups, rather than over realised ones. Both are implemented in
`rollingbench/metrics.py` and reported side by side throughout. What matters is that a
scoring rule paying real money should not have half its denominator made of noise, and
that AC-1's threshold should be restated against a reachable ceiling.

## Choosing κ honestly

κ is the one constant the shrinkage fix introduces. §12 of the implementation plan asks
for an ablation "not hiding". Here it is — and the first half of it is misleading on its
own.
"""),
    ("code", """
sens = pd.DataFrame(mt["kappa_sensitivity"]["rows"])
trade = pd.DataFrame(mt["kappa_tradeoff"]["rows"])
both = sens.merge(trade[["quantile", "detection_lag_batches"]], on="quantile", how="outer")
view = both[["quantile", "kappa", "mean_weight", "concordance", "top1_accuracy",
             "mean_score_sd", "detection_lag_batches"]]
view.columns = ["info quantile", "κ", "mean weight", "concordance", "top-1",
                "score SD", "lag (batches)"]
view
"""),
    ("code", """
show("07_kappa", "κ trades ranking accuracy against how long the score takes to notice that a "
                 "policy changed. Neither axis alone identifies an operating point.")
"""),
    ("code", """
md(f\"\"\"
Ranking accuracy improves monotonically with κ, which looks like "shrink as hard as
possible" — but that is an artefact of testing a static set of policies. As κ grows the
weight goes to zero, every score becomes the pooled running average, and pooling is
unbeatable at ranking policies that never change.

§16.2's payout is not applied to a static set: miners submit new policies, and a score
that cannot notice an improvement stops paying for one. The second axis measures that
directly — swap a policy from worst to best halfway through and count the batches until
the score catches up.

{mt['kappa_tradeoff']['reading']}
\"\"\")
finding("correction",
        f"κ at the 25th percentile of observed batch information buys "
        f"{sens.iloc[2]['concordance'] - mt['kappa_sensitivity']['raw_concordance']:+.3f} "
        f"concordance for a {trade.iloc[1]['detection_lag_batches']:.0f}-batch detection lag, "
        f"against {mt['kappa_tradeoff']['raw_detection_lag']:.0f} batches raw. Larger κ scores "
        f"better on ranking and takes up to "
        f"{trade.iloc[-1]['detection_lag_batches']:.0f} batches to notice a change. "
        f"'Calibrated once' needs to name which of the two it is calibrated for.")
"""),
]

# ========================================================= 06 · non-stationarity ==
N6 = [
    ("md", """
# 06 · Structured non-stationarity: does the decomposition earn its keep?

The follow-up proposal's central claim: because different components of a routing
decision drift at different known rates, one shared forgetting factor is the wrong
structure. Quality and token-count should get their own γ, and anything observable at
decision time — price above all — should be read live and never fitted.

Three things get tested here, and they do not all land the same way. Two of them are
tested by injecting synthetic shocks, because RouterBench is a static snapshot with no
real drift in it — which is also why the proposal asks for injection rather than a
retrospective read.
"""),
    ("code", PRELUDE),
    ("code", """
dc = load("decomposition"); rep = dc["replication"]; replay = dc["replay"]
md("Shocks injected into the replay (all synthetic, all labelled):\\n\\n" + "\\n".join(
    f"- week **{s['week']}** — {s['kind']} ×{s['factor']:g} on `{s['model'].split('/')[-1]}` — {s['note']}"
    for s in replay["shocks"]) + f"\\n\\nc_ref (the cost numeraire, deliberately never shocked): "
    f"`{replay['ref_model']}`")
"""),
    ("code", """
show("09_decomposition",
     "Top: regret through the shocks for all three arms. Bottom: traffic share to a shocked "
     "model — behaviour rather than belief, which is where a price change is visible.")
"""),
    ("md", """
## First: is §8.4's suggested γ any good?

Before comparing one γ against two, it is worth asking whether forgetting helps at all.
§8.4 suggests γ ≈ 0.999, "an effective window of about 1/(1−γ) recent observations".
"""),
    ("code", """
tun = dc.get("gamma_tuning")
if tun:
    sh = pd.DataFrame(tun["shared"])[["gamma", "mean_regret", "steady_state_regret",
                                      "mean_score_feasible"]]
    sh.columns = ["γ", "mean regret", "steady-state regret", "score (attainable)"]
    display(sh.set_index("γ"))
else:
    md("*γ tuning was skipped (run without `--quick` to include it).*")
"""),
    ("code", """
if tun:
    best = tun["best_shared"]
    at999 = next((r for r in tun["shared"] if abs(r["gamma"] - 0.999) < 1e-9), None)
    md(f\"\"\"
The best shared γ is **{best['gamma']:g}** — no forgetting at all. §8.4's suggested
0.999 scores {at999['mean_regret']:.4f} against {best['mean_regret']:.4f}, i.e.
**{at999['mean_regret'] - best['mean_regret']:+.4f} worse regret**.
\"\"\")
    finding("correction",
            f"On this corpus γ ≈ 0.999 is actively harmful: it costs "
            f"{at999['mean_regret'] - best['mean_regret']:+.4f} regret against γ = 1.0. "
            f"Discarding old observations to track occasional drift is a bad trade when the "
            f"pool is mostly stationary — the estimator's appetite for data beats its need "
            f"to forget. A forgetting factor should be triggered by detected drift, not left "
            f"on by default.")
"""),
    ("md", """
## Claim 1a — per-component decay, best against best

Both arms get their decay tuned on the same replay first, so this is not two dials
against one default. And because a 40-week replay of 400-item batches is noisy, the
comparison is paired across seeds: both arms see the same weeks, so the batch noise that
dominates the absolute level cancels.
"""),
    ("code", """
rows = []
for regime, r in rep.items():
    for arm, s in r["per_arm"].items():
        rows.append({"regime": regime, "arm": arm,
                     "mean regret": s["mean_regret_mean"], "± sd": s["mean_regret_sd"],
                     "score (attainable)": s["feasible_mean"], "seeds": s["n_seeds"]})
pd.DataFrame(rows).set_index(["regime", "arm"])
"""),
    ("code", """
for regime, r in rep.items():
    md(f"**{regime}** — {r['decomposition']['reading']}")

hi, lo = rep["high_drift"]["decomposition"], rep["default"]["decomposition"]
base = rep["high_drift"]["per_arm"]["live-read price, shared \u03b3"]["mean_regret_mean"]
if hi["supported"] and not lo["supported"]:
    finding("mixed",
            f"Detectable only where the premise is engineered to hold. Under continuous "
            f"drift the paired improvement is {hi['mean_regret_reduction']:+.4f} \u00b1 "
            f"{hi['std_error']:.4f} ({hi['mean_regret_reduction']/hi['std_error']:.1f} SE) \u2014 "
            f"real, but {hi['mean_regret_reduction']/base:.2%} of the regret it is improving. "
            f"Under the isolated-shock regime there is nothing: {lo['mean_regret_reduction']:+.4f} "
            f"\u00b1 {lo['std_error']:.4f}. So the mechanism works and the effect size does not "
            f"pay for the doubled Gram state (below).")
elif hi["supported"] or lo["supported"]:
    finding("mixed",
            f"Supported in one regime only: high-drift {hi['mean_regret_reduction']:+.4f} \u00b1 "
            f"{hi['std_error']:.4f}, default {lo['mean_regret_reduction']:+.4f} \u00b1 "
            f"{lo['std_error']:.4f}.")
else:
    finding("not-supported",
            f"No measurable improvement in aggregate regret in either regime: high-drift "
            f"{hi['mean_regret_reduction']:+.4f} \u00b1 {hi['std_error']:.4f}, default "
            f"{lo['mean_regret_reduction']:+.4f} \u00b1 {lo['std_error']:.4f} \u2014 even under "
            f"drift built specifically to favour it. The proposal's own risk register "
            f"anticipated this: a null result here is itself the finding.")
"""),
    ("md", """
### But a transient effect does survive

Mean regret over forty weeks dilutes a two-week transient into nothing. A claim about how
fast an arm *reacts* has to be measured in the shock window or not at all.
"""),
    ("code", """
rows = []
for regime, r in rep.items():
    for kind, v in r["transient_by_shock_kind"].items():
        rows.append({"regime": regime, "shock": kind, "n": v["n"],
                     "learned-cost": v["excess_learned_cost"],
                     "live-read": v["excess_live_read"],
                     "decomposed": v["excess_decomposed"],
                     "live-read advantage": v["live_read_advantage"],
                     "± SE": v["live_read_se"],
                     "decomposed advantage": v["decomposed_advantage"],
                     "± SE ": v["decomposed_se"]})
pd.DataFrame(rows).set_index(["regime", "shock"])
"""),
    ("code", """
d = rep["default"]["transient_by_shock_kind"]["quality"]
h = rep["high_drift"]["transient_by_shock_kind"]["price"]
md(f\"\"\"
Two effects clear the noise floor:

- Reading price live rather than fitting it absorbs a **quality** shock with
  **{d['live_read_advantage']:+.4f} ± {d['live_read_se']:.4f}** less excess regret —
  {d['live_read_advantage']/d['live_read_se']:.1f} standard errors.
- Component-wise decay absorbs **price** shocks under continuous drift with
  **{h['decomposed_advantage']:+.4f} ± {h['decomposed_se']:.4f}** less excess regret —
  {h['decomposed_advantage']/h['decomposed_se']:.1f} standard errors.
\"\"\")
finding("mixed",
        f"Claim 1b is supported, but by a different mechanism than argued. §8.7 justifies "
        f"reading price live on adaptation speed; the effect that actually shows up is that "
        f"a learned-cost target *conflates* quality and cost, so a quality regression "
        f"contaminates the cost belief too. Both point the same way — do not fit what you "
        f"can read — for different reasons, and the reason matters because it generalises to "
        f"every component, not just to fast-changing ones.")
"""),
    ("md", """
## Claim 1b, the version that is not about regret at all

There is a cleaner way to see the read-vs-learn distinction, and it needs no statistics.
FR-16 promises that a price change reaches routing decisions within five minutes. The
traffic-share panel in the figure above is that promise, measured: the live-read arms
re-route on the *first batch* after a price cut, because the price is a table lookup at
decision time. The learned-cost arm can only get there by re-observing, which takes as
many observations as its γ window implies.

That is not a small effect measured against noise; it is a structural difference. A
router that fits price cannot satisfy FR-16 at any γ, and one that reads it satisfies it
trivially. The regret metric is simply too blunt to show it, because a price cut on one
model of eleven moves aggregate regret by less than batch noise.
"""),
    ("code", """
lag_rows = []
for arm, series in replay["arms"].items():
    for shock in replay["shocks"]:
        if shock["kind"] != "price":
            continue
        key = f"price@w{shock['week']}"
        by = replay["summary"][arm]["by_shock"].get(key, {})
        if "adaptation_lag_weeks" in by:
            lag_rows.append({"arm": arm, "shock": key,
                             "lag (weeks)": by["adaptation_lag_weeks"],
                             "share before": by.get("share_before"),
                             "share after": by.get("share_after")})
pd.DataFrame(lag_rows).set_index(["shock", "arm"])
"""),
    ("md", """
## The §8.3 shortcut, and why it was found here

This was not on the list. It came out of trying to make notebook 03's rolling arm work:
with one shared Gram matrix, the arm could not exploit GPT-4 after it arrived, and the
cause turned out to be structural.

§8.3 keeps one Gram matrix for the whole pool — *"A depends only on the queries, not on
which model answered them. So one 64×64 inverse serves every model"* — which makes the
pool hot-swappable. That is exact when every model has been run on the same items. §8.5
writes the opposite (`σ_m(x) = sqrt(xᵀA_m⁻¹x)`), and §8.9's own budget of "state per
model: A 64×64" agrees with §8.5.

The two cases the system cares about most are both unevenly covered: a model onboarded
yesterday, and §18.2's sampling plan that runs reasoning models on a 25% subset.
"""),
    ("code", """
gr = load("gram")
g = pd.DataFrame(gr["rows"])
piv = g.pivot_table(index="coverage", columns="gram",
                    values=["q_hat_thinned", "share_thinned", "utility"])
md(f"Thinning coverage of **{gr['thinned_model']}** (true quality "
   f"{g.iloc[0]['q_true_thinned']:.3f}) and watching both estimators:")
piv.sort_index(ascending=False)
"""),
    ("code", """
show("05_gram",
     "Left: what each estimator believes the thinned model can do, against the truth. "
     "Right: how much traffic it therefore receives.")
"""),
    ("code", """
sm = pd.DataFrame(gr["summary"]["by_coverage"])
view = sm[["coverage", "utility_gap", "share_gap", "shared_underprediction",
           "per_model_underprediction"]]
view.columns = ["coverage", "utility gap", "traffic-share gap",
                "shared: under-prediction", "per-model: under-prediction"]
view.set_index("coverage")
"""),
    ("code", """
md(f\"\"\"
At full coverage the two are **identical** — which is why §8.3's argument reads correctly.
Thin coverage to 50% and the shared-Gram router's estimate of
{gr['thinned_model'].split('/')[-1]} collapses from {g.iloc[0]['q_hat_thinned']:.3f} to
{g[(g['coverage']==0.5) & (g['gram'].str.startswith('shared'))].iloc[0]['q_hat_thinned']:.3f},
and its traffic share to that model falls from
{pct(g.iloc[0]['share_thinned'])} to
{pct(g[(g['coverage']==0.5) & (g['gram'].str.startswith('shared'))].iloc[0]['share_thinned'])}.
It stops selecting the best model in the pool entirely.

The under-prediction tracks (1 − coverage) almost exactly — 0.502 at 50% coverage, 0.747
at 25%, 0.897 at 10%, 0.989 at 1% — which identifies the mechanism precisely: w = A⁻¹b
with a shared A carries every item in A and only the covered fraction in b.
\"\"\")
finding("correction",
        f"§8.3's shared-Gram shortcut is exact only under uniform coverage. Under uneven "
        f"coverage it under-predicts the sparse model by (1 − coverage) and stops selecting "
        f"it — costing up to {gr['summary']['worst_utility_gap']:.4f} utility, which is larger "
        f"than every effect in this notebook combined. Per-model Gram matrices, as §8.5 and "
        f"§8.9 imply, are unbiased at every coverage and cost K solves of a 64×64 system. "
        f"This is the highest-value correction found.")
"""),
    ("md", """
### The artifact-size consequence

§8.9's ~210 KB budget describes one Gram matrix per model shared across all three
prediction targets, which is sound — A depends only on x, not on which target is being
predicted. But per-component decay means the quality and token lanes age at different
rates, and two differently-decayed matrices are not the same matrix.

So Contribution 1 doubles the Gram state: 358 KB here at d = 64, K = 11, against 180 KB
if the lanes shared one. Still far inside NFR-4's 5 MB, but §8.9's budget quietly assumes
the cost is not paid — and given that 1a shows no measurable aggregate benefit, it is a
cost without a demonstrated return.
"""),
]

# ================================================================ 07 · verdicts ==
N7 = [
    ("md", """
# 07 · What held, what did not, and what to do about it

Every claim in the two proposals that could be tested against a public label matrix, with
the measurement and the verdict. Nothing here is a plan; it is what the numbers said.

The corpus throughout is RouterBench — 36,497 real prompts × 11 real commercial models,
401,467 graded cells with realised costs. Zero new inference was purchased. Held-out
evaluation is by item, never by row.
"""),
    ("code", PRELUDE),
    ("code", """
ov, fr, st, cs, mt, dc, gr = (load(n) for n in
    ["overview", "frontier", "staleness", "coldstart", "metric", "decomposition", "gram"])
man = load("manifest")
sw = pd.DataFrame(fr["sweep"]); s5 = sw.loc[(sw["lam_cost"]-0.05).abs().idxmin()]
sts = st["summary"]; lk = mt["result"]["oracle_luck"]
rk = mt["result"]["ranking"]["overall"]; bins = mt["result"]["bins"]["bins"]
rep = dc["replication"]

md(f\"\"\"
| # | claim | source | verdict | the measurement |
|---|---|---|---|---|
| 1 | Most queries do not need the strongest model | §3.1 | **supported** | {pct(ov['ties']['pairwise_tie_rate'])} pairwise tie rate over {ov['ties']['pairs_compared']:,} comparisons |
| 2 | Routing beats one good model on cost at near-equal quality | AC-1 | **supported** | {pct(s5['savings_vs_frontier'])} cheaper at {pct(s5['quality_vs_frontier'])} of frontier quality |
| 3 | A router trained once measurably decays | §14.1 | **supported** | {sts['frozen_decay']:.3f} decay over {len(st['result']['weeks'])} weeks; crosses below best-single at week {sts['week_crossed_below_best_single']} |
| 4 | The decay is about evaluation freshness | §1 framing | **not supported** | {sts['attribution_new_models']/(sts['attribution_new_models']+sts['attribution_fresher_data']):.0%} of it is new-model access; refitting recovers {sts['attribution_fresher_data']:+.3f} |
| 5 | A useful router needs under 1 MB and no GPU | O3 | **supported** | {sw.iloc[0]['artifact_kb']:.0f} KB, CPU only, O(d²) updates |
| 6 | Uninformative batches make the score noise | §6 | **supported** | SD {bins[0]['raw_sd_mean']:.4f} vs {bins[-1]['raw_sd_mean']:.4f}, low vs high information |
| 6b | ...because similar models converge oracle and baseline | §6 | **not supported** | information correlates {mt['result']['diagnosis']['corr_info_vs_model_spread']:+.2f} with model spread — the causal story is inverted |
| 7 | Information-aware shrinkage fixes it | §6.1 | **supported** | ranking concordance {rk['raw_concordance']:.3f} → {rk['shrunk_concordance']:.3f} |
| 8 | Normalised regret below 0.6 is achievable | AC-1 | **not supported** | {pct(lk['mean_luck_share_of_gap'])} of the oracle gap is unattainable luck; a clairvoyant per-task oracle scores 0.078 |
| 9 | Low-rank item factors bridge to a feature-space prior | §5.1 | **not supported** | bridge R² = {cs['bridge']['bridge_r2']:.3f}; the proposal's own gate fails |
| 10 | Probe count tracks how well the pool explains a new model | §5.3 | **mixed** | τ² vs probe count r = {cs['lomo']['summary']['tau2_vs_probe_correlation']['derived (§5.2)']:+.2f}, but n = 1 material model |
| 11 | Component-wise γ_q/γ_t beats one shared γ | §4 | **{'mixed' if rep['high_drift']['decomposition']['supported'] != rep['default']['decomposition']['supported'] else ('supported' if rep['high_drift']['decomposition']['supported'] else 'not supported')}** | {rep['high_drift']['decomposition']['mean_regret_reduction']:+.4f} ± {rep['high_drift']['decomposition']['std_error']:.4f} under engineered drift; {rep['default']['decomposition']['mean_regret_reduction']:+.4f} ± {rep['default']['decomposition']['std_error']:.4f} otherwise |
| 12 | Price should be read, not fitted | §8.7 | **supported** | live-read absorbs a quality shock {rep['default']['transient_by_shock_kind']['quality']['live_read_advantage']:+.4f} ± {rep['default']['transient_by_shock_kind']['quality']['live_read_se']:.4f} better; and FR-16 is unsatisfiable by a fitted-price router at any γ |
| 13 | γ ≈ 0.999 is a sensible default | §8.4 | **not supported** | γ = 1.0 beats it by {(next(r for r in dc['gamma_tuning']['shared'] if abs(r['gamma']-0.999)<1e-9)['mean_regret'] - dc['gamma_tuning']['best_shared']['mean_regret']):+.4f} regret |
| 14 | One shared Gram matrix serves every model | §8.3 | **not supported** | exact at uniform coverage; under-predicts by (1−coverage) otherwise, costing {gr['summary']['worst_utility_gap']:.4f} utility |
\"\"\")
"""),
    ("md", """
## The four findings that change what should be built

**1. Onboarding beats re-grading.** The decay is real, and it is almost entirely about
being able to select models that did not exist at training time — not about the freshness
of the data on the models you already have. That inverts the cost priority in §18.2: the
daily full-pool sweep over fresh items is buying the less valuable half. A catalogue
watcher plus a fast, reliable cold-start probe is buying the more valuable half, and it
is far cheaper.

**2. Per-model Gram matrices, not one shared.** Worth more than every other estimator
change measured here, combined. The shared-matrix shortcut is exact under uniform
coverage and silently stops selecting a model whose coverage is thin — which is precisely
the new-model case that finding 1 says matters most, and precisely the sampling-plan case
§18.2 recommends. The fix costs K solves of a 64×64 system and one extra matrix per
model.

**3. The scoring rule needs a reachable ceiling.** Half of §8.8's denominator is luck no
policy can capture. That deflates every score, makes AC-1's threshold unreachable by
construction, and — because §16.1 pays emissions in proportion to these scores — pays
partly on noise. Define the oracle over grouped or conditionally-expected outcomes, and
restate AC-1 against it.

**4. Cold start fails on the model you most need it for.** Matrix-completion priors work
for a model that resembles the pool and fail for the frontier outlier: loading R² ranges
from 0.43 down to −0.008, and the −0.008 is GPT-4, whose arrival caused all the decay in
finding 1. Onboarding the models that matter needs real probing, and the probe budget
should be set by measured loading rather than by a flat ~250.

## What to drop

Contribution 1's per-component decay is detectable only under continuous drift built to
favour it, and even there the improvement is a fraction of a percent of the regret it is
improving — while doubling the Gram state the artifact has to carry. The read-versus-learn
half of it (1b) is worth keeping — for FR-16, and because a learned-cost target conflates
signals that should stay separate — but the two-γ machinery is not carrying its weight. §8.4's γ ≈ 0.999 default should be replaced by γ = 1.0 with
drift-triggered forgetting, since always-on forgetting measurably costs regret on a pool
that is mostly stationary.

Contribution 2's bridge fails its own precondition. The *idea* behind §5.3 — that probe
budget should be a function of measured loading rather than a constant — survives and is
worth keeping; the specific item-space-to-feature-space derivation does not.
"""),
    ("md", """
## Limits of this evidence

Stated plainly, because several of them bound the conclusions above.

- **One corpus, eleven models, 2023 vintage.** RouterBench's pool ends in December 2023.
  The staleness result is one trajectory through one pool's history, not a distribution
  over them.
- **Binary grading.** Most items are multiple-choice, so per-item outcomes carry a lot of
  luck. That is the direct cause of finding 3 and it also caps how much per-item signal
  any router can extract.
- **No item dates.** RouterBench does not date its prompts, so the replay holds the item
  distribution fixed. Workload drift and contamination — two of the five causes §3.3
  lists — are not measured here at all.
- **Synthetic shocks.** Every drift result in notebook 06 rests on injected changes,
  because a static snapshot contains no real drift. The magnitudes are plausible; they are
  not observed.
- **n = 1 on the case that matters.** Only one of eleven models had a material onboarding
  gap, so findings 4 and 10 rest on a single instance.
- **Feature map is deliberately cheap.** Hashed n-grams plus surface features, not a
  sentence encoder. §3.1 says encoder scale barely moves routing accuracy; that was taken
  on trust here rather than verified, so the absolute scores are a floor.
"""),
    ("code", """
md(f\"\"\"
### Reproducing this

```
python scripts/fetch_data.py            # ~95 MB, once
python scripts/run_all.py               # ~{man['elapsed_seconds']/60:.0f} min, CPU only
python scripts/execute_notebooks.py     # re-renders these notebooks
```

Seed {man['seed']}, d = {man['feature_dim']}, {man['n_train']:,} train / {man['n_test']:,} test
items disjoint by item. Every experiment reads files on disk and touches no network, so
two runs produce the same numbers.
\"\"\")
"""),
]


# ============================================================ 08 · loss & scale ==
N8 = [
    ("md", """
# 08 · Loss, and what it buys

There is no epoch loop here. The estimator is closed-form, so nothing anneals and there is
no training loss ticking down. That does not mean there is no loss: the quality head is a
regression onto a binary outcome, so it has a Brier score and a log-loss like any
classifier, and those are the numbers the decision rule is built on.

The questions a training curve would normally answer are still worth answering, and three
of them decide how much to spend:

1. **Data** — has the fit converged, or is the daily evaluation bill still buying accuracy?
2. **Capacity** — §8.2 asserts d ≈ 64 and never says why. Is it right?
3. **Regularisation** — λ is a free parameter neither document discusses.
4. **Coupling** — does lower loss actually produce better routing? This one turns out to
   have an uncomfortable answer.
"""),
    ("code", PRELUDE),
    ("code", """
sc = load("scaling"); man = load("manifest")
s = sc["summary"]
md(f\"\"\"
Every curve below is train **and** validation. A validation curve alone cannot tell
"more data would help" apart from "the model is too small", and those call for opposite
spending decisions.

Fitted on {man['n_train']:,} items, validated on {man['n_test']:,} held-out items,
disjoint by item.
\"\"\")
"""),
    ("code", """
show("10_loss_curves",
     "Six views of the same estimator. Top row: loss against data, capacity and "
     "regularisation. Bottom: loss as updates stream in, loss against hash width, and "
     "calibration.")
"""),
    ("md", """
## 1. Data — the fit has essentially converged

The learning curve is the classic shape: train and validation start far apart and close as
data arrives. What matters is the right-hand end.
"""),
    ("code", """
d = s["data"]
lc = pd.DataFrame([{"items": n, "observations": n * load("overview")["corpus"]["models"],
                    "val_brier": b} for n, b in zip(d["sizes"], d["val_brier_by_size"])])
display(lc.set_index("items"))
md(f\"\"\"
The first doubling of data buys **{d['gain_from_first_doubling']:.5f}** of Brier. The last
one buys **{d['gain_from_last_doubling']:.5f}** — roughly
{abs(d['gain_from_last_doubling'] / max(abs(d['gain_from_first_doubling']), 1e-9)):.1%} as much.
\"\"\")
finding("supported" if d["converged"] else "mixed",
        f"On this corpus the quality head has essentially converged by ~25k items "
        f"({lc['observations'].iloc[-1]:,} graded cells). Doubling the data again would buy "
        f"about {abs(d['gain_from_last_doubling']):.5f} Brier — real but small. That is a "
        f"direct answer to how much the §18.2 evaluation budget is still buying on a "
        f"*static* pool, and it is the strongest argument for spending it on new models "
        f"instead, which is what notebook 03 found independently.")
"""),
    ("md", """
## 2. Capacity — §8.2's d ≈ 64 survives, but the loss minimum is not where to stop

§8.2 asserts "roughly 64 dimensions" and never says why, so it was measured. The first
answer was wrong and worth recording: on a 512-bucket hash the sweep put the routing
optimum at d ≈ 108, and adopting it looked like a 53% improvement. Widening the hash and
re-running across four splits showed the gain was the *hash*, not the dimension — at 4,096
buckets d = 64 and d = 108 are tied on routing and d = 64 costs a third of the artifact.

The lesson is the one this notebook is about: a single split plus a plausible story is not
a result.
"""),
    ("code", """
cc = pd.DataFrame(sorted(sc["capacity_curve"], key=lambda r: r["d"]))
view = cc[["d", "train_brier", "val_brier", "overfit_gap", "val_ranking_loss",
           "regret", "score_feasible", "savings", "artifact_kb", "fit_ms"]].copy()
view.columns = ["d", "train Brier", "val Brier", "gap", "ranking loss", "regret",
                "score (attainable)", "savings", "artifact KB", "fit ms"]
view.style.format({"train Brier": "{:.5f}", "val Brier": "{:.5f}", "gap": "{:+.5f}",
                   "ranking loss": "{:.4f}", "regret": "{:.4f}",
                   "score (attainable)": "{:+.3f}", "savings": "{:.1%}",
                   "artifact KB": "{:,.0f}", "fit ms": "{:,.0f}"})
"""),
    ("code", """
c = s["capacity"]
best_route = min(sc["capacity_curve"], key=lambda r: r["regret"])
md(f\"\"\"
| | |
|---|---|
| lowest validation loss at | d = **{c['best_d']}** (Brier {c['best_val_brier']:.5f}) |
| lowest routing regret at | d = **{best_route['d']}** (regret {best_route['regret']:.4f}) |
| §8.2's default d = 64 | Brier {c['default_d_64_brier'] or float('nan'):.5f} |
\"\"\")
finding("new",
        f"The loss and the routing disagree about how big the model should be. Validation "
        f"Brier keeps improving out to d = {c['best_d']} and beyond, while routing regret is "
        f"best at d = {best_route['d']} and degrades past it. Tuning this router on its "
        f"prediction loss would pick a model that routes worse — and the artifact grows "
        f"quadratically in d, so the wrong choice costs memory as well as quality.")
"""),
    ("md", """
Why that happens is worth being precise about. Ridge with more directions fits each
model's quality curve more closely, which lowers Brier for every column at once. But the
argmax only reads the *ordering* between columns on a given item, and an equal improvement
across all of them leaves the ordering untouched. Past a point, the extra directions start
fitting per-model noise, which does move the ordering — in the wrong direction.

## 3. Regularisation — the model is under-fit, not over-fit
"""),
    ("code", """
rc = pd.DataFrame(sorted(sc["regularisation_curve"], key=lambda r: r["lam"]))
view = rc[["lam", "train_brier", "val_brier", "overfit_gap", "regret", "savings"]].copy()
view.columns = ["λ", "train Brier", "val Brier", "gap (val − train)", "regret", "savings"]
view.style.format({"λ": "{:g}", "train Brier": "{:.5f}", "val Brier": "{:.5f}",
                   "gap (val − train)": "{:+.6f}", "regret": "{:.4f}", "savings": "{:.1%}"})
"""),
    ("code", """
r = s["regularisation"]
gap = r["overfit_gap_at_best"]
n_obs = man["n_train"] * load("overview")["corpus"]["models"]
md(f\"\"\"
The train/validation gap at the chosen λ is **{gap:+.6f}** — orders of magnitude smaller
than the loss itself. There is no overfitting here to regularise away.
\"\"\")
finding("new",
        f"λ barely matters across four orders of magnitude, because at d = {man['feature_dim']} "
        f"with {n_obs:,} observations the fit is heavily over-determined. The model was "
        f"capacity-limited, not variance-limited — which is why raising d was the lever that "
        f"worked and tuning λ was not. Best λ = {r['best_lam']:g}, and anything from 0.01 to "
        f"100 is indistinguishable.")
"""),
    ("md", """
## 4. Coupling — the loss you can measure is not the loss you want

The router is never scored on its Brier. It is scored on where it routes. So: across every
configuration in every sweep above, does lower loss mean lower regret?
"""),
    ("code", """
show("11_loss_vs_routing",
     "Left and middle: each fitted configuration as one point, loss against regret. Right: "
     "the capacity sweep with both curves indexed to their own range, so the disagreement "
     "about d is visible on one axis without a second scale.")
"""),
    ("code", """
cp = sc["coupling"]
md(f\"\"\"
| association with routing regret | all configs (rank) | well-fed configs only |
|---|---|---|
| validation Brier — absolute forecast | {cp['spearman_val_brier_regret']:+.2f} | **{cp['corr_val_brier_regret_healthy_only']:+.2f}** |
| ranking loss — order within an item | {cp['spearman_ranking_loss_regret']:+.2f} | **{cp['corr_ranking_loss_regret_healthy_only']:+.2f}** |
\"\"\")
finding("new",
        f"Among configurations a deployed router could plausibly be, the ranking loss "
        f"predicts regret at r = {cp['corr_ranking_loss_regret_healthy_only']:+.2f} while the "
        f"Brier score manages only {cp['corr_val_brier_regret_healthy_only']:+.2f}. The "
        f"argmax consumes the ordering between models and discards the level, so the "
        f"absolute forecast is largely wasted effort. Pooled over *all* configurations both "
        f"look excellent (r > 0.9), but that number is mostly reporting that starved models "
        f"are bad at everything.")
"""),
    ("md", """
The practical consequence: the loss to minimise is a **ranking** loss, not a squared error.
That is a different estimator — a pairwise or listwise objective within each item — and it
is no longer closed-form, which is a genuine tension with §8.1's rule about exact
solutions. It is the most promising direction this analysis turned up and it is not in
either proposal.

## 5. Calibration, and where the loss actually lives
"""),
    ("code", """
show("12_per_model_loss",
     "Left: prediction loss per model, with the AUC beside it. Right: signed calibration "
     "error — which models the router systematically over- or under-sells.")
"""),
    ("code", """
pm = pd.DataFrame(sc["per_model"]).sort_values("brier", ascending=False)
view = pm[["model_id", "brier", "auc", "bias", "pred_mean", "true_mean", "n"]].copy()
view.columns = ["model", "Brier", "AUC", "bias (pred − true)", "predicted", "observed", "cells"]
view
"""),
    ("code", """
worst = pm.iloc[0]; best_auc = pm.loc[pm["auc"].idxmax()]
rel = sc["reliability"]
md(f\"\"\"
Calibration is good in aggregate — expected calibration error
**{rel['expected_calibration_error']:.4f}** — so the predicted quality can be read as a
probability, which is what the quality-floor filter in FR-21 needs to be meaningful.

Per model it is uneven: **{worst['model_id']}** carries the most loss
(Brier {worst['brier']:.3f}), and **{best_auc['model_id']}** is the most predictable
(AUC {best_auc['auc']:.2f}).
\"\"\")
finding("supported",
        f"The router separates good from bad answers per model at AUC "
        f"{pm['auc'].min():.2f}–{pm['auc'].max():.2f}, well above chance, and is calibrated "
        f"to within {rel['expected_calibration_error']:.4f}. The per-model spread is the "
        f"useful part: the models the router predicts worst are the ones whose behaviour is "
        f"least explained by prompt text alone.")
"""),
    ("md", """
## What this changed

| | before | after |
|---|---|---|
| feature dimension d | 64 (asserted in §8.2) | **64** — confirmed, not changed |
| hash buckets | 512 | **4,096** |
| λ | 1.0 | 1.0 (confirmed: it does not matter) |

One change, and it is not the one that looked obvious. Validated across four independent
train/validation splits, because the routing score is a ratio and a single split is noisy
enough to have sent this in the wrong direction once already.
"""),
    ("code", """
md(\"\"\"
Four splits, mean ± standard error. The top row is §8.2 as written; the rest hold the hash
at 4,096 and vary only d:

| config | val Brier | regret | score (attainable) | artifact |
|---|---|---|---|---|
| d=64, 512 buckets (§8.2 as written) | 0.15878 ± 0.00074 | 0.9693 ± 0.0039 | +0.589 ± 0.101 | 358 KB |
| d=44, 4,096 | 0.15776 ± 0.00044 | 0.9566 ± 0.0004 | +0.801 ± 0.078 | 170 KB |
| **d=64, 4,096 (adopted)** | 0.15689 ± 0.00038 | **0.9530 ± 0.0045** | **+0.836 ± 0.030** | 358 KB |
| d=108, 4,096 | 0.15591 ± 0.00033 | 0.9547 ± 0.0030 | +0.833 ± 0.091 | 1,012 KB |
| d=172, 4,096 | **0.15543 ± 0.00027** | 0.9588 ± 0.0014 | +0.753 ± 0.055 | 2,557 KB |

Read the last two columns against each other. Validation Brier falls monotonically all the
way down the table; routing quality peaks in the middle and then declines. The bottom row
has the **best loss of any configuration tested** and routes worse than every row above it.
\"\"\")
finding("correction",
        "Widening the hash from 512 to 4,096 buckets lifts the share of the attainable gap "
        "captured from +0.589 to +0.836 at an unchanged d = 64 and an unchanged 358 KB "
        "artifact — collisions were destroying signal before the projection ever saw it. "
        "§8.2's d ≈ 64 is vindicated; the encoder width it never mentions was the problem. "
        "Raising d further buys lower loss and worse routing.")
"""),
    ("md", """
## Cost of the compute

Worth stating plainly, since the whole system is premised on the router being cheap.
"""),
    ("code", """
cc = sorted(sc["capacity_curve"], key=lambda r: r["d"])
adopted = min(cc, key=lambda r: abs(r["d"] - man["feature_dim"]))
md(f\"\"\"
| | |
|---|---|
| fit, one pass over 25,000 items | {adopted['fit_ms']:,.0f} ms |
| artifact | {adopted['artifact_kb']:,.0f} KB |
| per-observation update | O(d²) ≈ {man['feature_dim']**2:,} flops |
| GPU | none, at fit or serve time |

Fitting the whole thing costs under a second of one CPU core. §18.2's estimate that router
fitting is single-digit dollars a month, against ~99% of the platform bill going to
evaluation inference, is confirmed — and the compute spent in this notebook was spent on
*choosing* the model, which happens once.
\"\"\")
"""),
]

# ================================================== 09 · the product's pool ==
N9 = [
    ("md", """
# 09 · The pool the product actually serves

Notebooks 01–08 all run on RouterBench: eleven commercial models from 2023, GPT-4 Turbo
and Claude v1 among them. That is the right corpus for the questions those notebooks ask,
because it is the only public label matrix that carries **release dates** — and without
dates there is no way to replay a pool that grows, which is what the staleness study needs.

It is the wrong pool for the product. A customer's request goes to one of thirteen Chutes
models, none of which are in RouterBench, all of which are current, and all of which are
open-weights. This notebook is that pool.

**Read the binding table before the numbers.** No public benchmark grades the Chutes
checkpoints, so each slot is bound to a model LLMRouterBench *did* grade and the router is
trained on that column's real per-item outcomes. Quality and token counts are measured;
prices are the live Chutes list; the binding itself is an assumption.
"""),
    ("code", PRELUDE),
    ("code", """
pool = load("chutes/01_pool"); binds = load("chutes/01b_bindings")
man = load("chutes/manifest")
md(f\"\"\"
**{pool['corpus']['items']:,} items x {pool['corpus']['models']} models**,
{pool['corpus']['cells']:,} graded cells. Every comparison below uses the
**fully-observed core of {pool['dense_core_items']:,} items** across
{len(load('chutes/07_analytics')['tasks'])} benchmarks — the questions every one of the
thirteen answered, because a cost/quality frontier only means something when every policy
had the same menu on every item.
\"\"\")
"""),
    ("code", """
display(table(
    [{"Chutes model": b["label"], "tier": b["tier"], "stands in for": b["proxy_id"],
      "match": "identical checkpoint" if b["exact"] else ("same family" if b["same_family"] else "capability only")}
     for b in pool["bindings"]]))
"""),
    ("md", """
## Why two slots lean on closed-weight models

Every model Chutes serves is open-weights, so a stand-in that is not is a weaker analogue
than its score suggests. Eleven of thirteen are open. The two frontier slots are not, and
that is a choice worth testing rather than defending.
"""),
    ("code", """
sw = binds["swaps"]
display(table([{"slot": s["label"], "tier": s["tier"],
                "closed anchor": s["was"], "its score": round(s["was_accuracy"], 3),
                "best open substitute": s["now"], "its score": round(s["now_accuracy"], 3)}
               for s in sw]))
finding("correction", binds["reading"])
"""),
    ("md", """
Both candidates are ranked on the **shared task set**, not on their own coverage. Ranked
the sloppy way the small open models look stronger than the frontier ones, purely because
they were asked easier questions — the same coverage trap that costs twelve points of
quality retention below.
"""),
    ("code", """
show("chutes_01_pool", "The thirteen slots: measured accuracy, and cost at published "
     "Chutes prices. Labels give the stand-in behind each one.")
"""),
    ("md", """
## The result, against the baseline that can actually win

Two baselines are reported everywhere, and the order matters. The **frontier model** is
what a team does today by wiring everything to the strongest model. The **best single
model** is the one that is already optimal on this pool once price is counted — a much
harder opponent, and on this pool it beats the frontier model on quality *and* price.
"""),
    ("code", """
cv = load("chutes/11_crossval"); pol = load("chutes/06_policies")
md(f\"\"\"
Over {len(cv['seeds'])} random splits at the calibrated dial:

| against | cheaper by | quality kept |
|---|---|---|
| {pol['frontier_model']} (strongest) | **{pct(cv['savings_vs_frontier']['mean'])}** ± {pct(cv['savings_vs_frontier']['se'])} | {pct(cv['quality_vs_frontier']['mean'])} |
| {pol['best_single_model']} (best value) | **{pct(cv['savings_vs_best_single']['mean'])}** ± {pct(cv['savings_vs_best_single']['se'])} | {pct(cv['quality_vs_best_single']['mean'])} |

The second row is the number to quote.
\"\"\")
"""),
    ("code", """
display(table([{"policy": p["policy"], "quality": round(p["quality"], 4),
                "$ / call": round(p["cost_per_call_usd"], 6),
                "vs frontier": pct(p["savings_vs_frontier_pct"]),
                "vs best single": pct(p["savings_vs_best_single_pct"])}
               for p in pol["policies"]]))
finding("correction",
        f"{pol['frontier_model']} is the highest-quality model and is beaten outright on "
        f"both axes by {', '.join(pol['models_beating_the_frontier_model'])}. Savings "
        f"quoted against it are inflated by a gap the router had nothing to do with.")
"""),
    ("code", """
show("chutes_02_frontier", "The dial. Left: what each lambda_c buys. Right: where the "
     "traffic goes as it turns.")
"""),
    ("md", """
## Three things that had to be fixed before any of this was true

### 1. The inherited operating point was wrong by more than the whole result
"""),
    ("code", """
cal = load("chutes/04_calibration")
at05 = next(g for g in cal["grid"] if abs(g["lam_cost"] - 0.05) < 1e-9)
finding("correction",
        f"lambda_c = 0.05 is this package's calibrated dial on RouterBench. Carried over "
        f"unexamined it spends {abs(at05['savings_vs_best_single']):.0%} MORE than doing "
        f"nothing, for less quality. It weights a cost *ratio*, and this pool's ratios "
        f"span three orders of magnitude where RouterBench's span one. "
        f"Calibrated here: lambda_c = {cal['chosen_lam_cost']}.")
display(table([{"lambda_c": g["lam_cost"], "quality vs best single": pct(g["quality_vs_best_single"]),
                "cheaper by": pct(g["savings_vs_best_single"])} for g in cal["grid"]]))
"""),
    ("md", """
### 2. Ten times more training data made the router worse
"""),
    ("code", """
ab = load("chutes/03_ablation")
finding("new", ab["reading"])
show("chutes_05_coverage", "Same held-out items in both arms; only the training set "
     "differs. Uneven coverage across columns costs more than the extra data buys.")
"""),
    ("md", """
### 3. Four hundred and seventy 'measurements' were failed calls

Zero input tokens, zero output tokens, and a score of exactly 0.0 where every other cell
averages 0.60. Left in, the quality lane learns a reliability failure as an inability to
answer and the cost lane learns the model was free — and on the two items where the
*reference* model failed, c_ref lands in a denominator and mean utility goes to −439,045.
They are marked unobserved. The 31 cells that were billed for input and returned nothing
are real failures and stay.
"""),
    ("md", """
## How much model, and how much data

No epoch loop here either — the estimator is closed-form. But the two questions that
decide the bill still have answers, and they disagree with each other.
"""),
    ("code", """
sc = load("chutes/09_scaling")
show("chutes_06_loss", "Loss against data and against capacity, each beside what it buys.")
finding("new",
        f"Validation loss is still falling at d = {sc['coupling']['best_d_by_loss']} while "
        f"savings peak at d = {sc['coupling']['best_d_by_savings']}. Sizing on the loss "
        f"curve alone ships a five-times-larger artifact that routes slightly worse — the "
        f"same split notebook 08 found on a different corpus and a different pool.")
"""),
    ("md", """
## Price is read, never fitted

The one claim here a competitor cannot answer by training harder. Price, latency and
availability are read from a live table at decision time, so a price change reaches
routing with no refit and no redeploy. That is testable, so it is tested: the fitted
weights are hashed either side of the change.
"""),
    ("code", """
pr = load("chutes/10_prices"); sh = pr["shock"]
md(f"Live list read from `llm.chutes.ai/v1/models`: "
   f"**{'in sync' if pr.get('diff', {}).get('in_sync') else 'DRIFTED'}** with the shipped catalogue.")
display(table([{"price": f"{p['factor']}x", "its traffic share": pct(p["target_share_after"]),
                "bill, reacting": round(p["spend_after_usd"], 2),
                "bill, frozen": round(p["spend_if_frozen_usd"], 2),
                "saved": round(p["saved_by_reacting_usd"], 2)} for p in sh["points"]]))
finding("supported", sh["reading"])
"""),
    ("code", """
show("chutes_07_prices", "Traffic follows price, and the bill follows with it — with the "
     "trained model byte-identical at every point.")
"""),
    ("md", """
## Where the headroom is
"""),
    ("code", """
an = load("chutes/07_analytics")
sav = load("chutes/06_policies")
r = next(p for p in sav["policies"] if p["policy"] == "router")
o = next(p for p in sav["policies"] if p["policy"] == "oracle (per item, quality)")
md(f\"\"\"
The router scores **{r['quality']:.3f}**. A per-item oracle scores **{o['quality']:.3f}**.
So the decision rule is capturing {r['quality'] / o['quality']:.1%} of what perfect
per-question knowledge would get — the ceiling here is the quality prediction
(Brier skill {an['prediction_quality']['brier_skill_score']:+.3f}, pairwise ranking
concordance {an['prediction_quality']['pairwise_ranking_concordance']:.3f}), not the argmax.

Two of thirteen slots never win a request: {', '.join(an['unused_models'])}.
\"\"\")
display(table(an["domains"], ["domain", "items", "best_quality_model", "router_quality",
                              "oracle_quality", "router_top_model"]))
"""),
    ("code", """
show("chutes_04_domains", "Router against the best single model per domain, and against "
     "the per-item ceiling.")
show("chutes_03_traffic", "Who gets the requests, and which slots earn theirs.")
"""),
    ("md", """
## The two slots that never win

They take 0% of traffic at every dial setting. The first instinct is to retire them. The
measurement says the opposite.
"""),
    ("code", """
sl = load("chutes/12_slots")
orc, rtr = sl["oracle_share"], sl["router_share"]
display(table([{"model": k.split("/")[-1], "oracle would send": pct(orc[k]),
                "router sends": pct(rtr.get(k, 0.0))}
               for k in sorted(orc, key=lambda x: -orc[x])]))
finding("new", sl["reading"])
show("chutes_09_slots", "Green: what a per-item oracle would send each slot. Blue: what "
     "the router sends. The gap on the top row is the largest unclaimed value in the pool.")
"""),
    ("md", """
The reason is arithmetic, not preference. Mistral Nemo's predicted quality averages 0.215
with a per-item spread of 0.160; Qwen3 235B Thinking averages 0.830 with a spread of 0.078.
Under an argmax the cheap model needs a four-sigma excursion to win, so it never does.

The rule the product advertises — *cheapest model that will get this right* — is a
threshold, not an argmax, and a threshold **can** pick a cheap model whenever it is good
enough. So it was implemented and swept. It loses.
"""),
    ("code", """
th = sl["threshold_rule"]
rows = [{"rule": "argmax (current)", "quality vs best single": pct(th["argmax"]["quality_vs_best_single"]),
         "cheaper by": pct(th["argmax"]["savings_vs_best_single"]),
         "open-tier share": pct(th["argmax"]["open_tier_share"])}]
rows += [{"rule": f"threshold tau={g['tau']:g}", "quality vs best single": pct(g["quality_vs_best_single"]),
          "cheaper by": pct(g["savings_vs_best_single"]),
          "open-tier share": pct(g["open_tier_share"])} for g in th["grid"]]
display(table(rows))
finding("not-supported",
        "An argmax needs only the ORDER between models to be right; a threshold needs the "
        "LEVEL. The level is the badly-estimated half (Brier skill +0.257), so the simpler "
        "rule wins. Keep both slots, and fix the estimator rather than the decision rule.")
"""),
    ("md", """
## Does this pool go stale too?

Notebook 03 measured decay on 2023 commercial models. Repeating it here is the closest
thing to an independent replication: different models, different generation, different
corpus, same question. Release dates are attached by hand from the labs' announcements —
the one hand-entered input in this half of the package.
"""),
    ("code", """
cst = load("chutes/13_staleness")["summary"]
rb = load("staleness")["summary"]
share = lambda s: abs(s["attribution_new_models"]) / (abs(s["attribution_new_models"]) + abs(s["attribution_fresher_data"]))
display(table([
    {"": "frozen, start -> end", "RouterBench (2023)": f"{rb['frozen_start']:+.3f} -> {rb['frozen_end']:+.3f}",
     "Chutes pool (current)": f"{cst['frozen_start']:+.3f} -> {cst['frozen_end']:+.3f}"},
    {"": "rolling, start -> end", "RouterBench (2023)": f"{rb['rolling_start']:+.3f} -> {rb['rolling_end']:+.3f}",
     "Chutes pool (current)": f"{cst['rolling_start']:+.3f} -> {cst['rolling_end']:+.3f}"},
    {"": "crosses below best single", "RouterBench (2023)": f"week {rb['week_crossed_below_best_single']}",
     "Chutes pool (current)": f"week {cst['week_crossed_below_best_single']}"},
    {"": "share of gap from NEW MODELS", "RouterBench (2023)": pct(share(rb)),
     "Chutes pool (current)": pct(share(cst))},
]))
finding("supported",
        "The decay replicates on the current pool, and so does its cause. Fresh data on "
        "models you already have is worth almost nothing; access to models that just "
        "shipped is worth almost everything.")
show("chutes_08_staleness", "The same four-arm replay on the models the product serves.")
"""),
    ("md", """
### And onboarding a new model has a price
"""),
    ("code", """
cs = load("chutes/14_coldstart")["summary"]
md(f\"\"\"
{len(cs['material_models'])} of 13 slots have a material gap when introduced cold. For
those, probe items needed before the router can use them:

{chr(10).join(f'- **{k}** — {v}' for k, v in cs['median_probe_items_material'].items())}

So a newly-shipped model costs roughly **1,000 graded questions** before it is selectable,
and only the informative prior gets there at all. That is what makes the 93% above
expensive to capture rather than free — and it is also the moat: an incumbent onboards in a
day, a newcomer needs 1,000 questions per model before its router is even correct.
\"\"\")
"""),
    ("md", """
## Latency — what the corpus supports, and what it does not

The corpus publishes wall-clock per *run*, never per record. The obvious move is to fit
throughput per model and divide. That was implemented, and then checked.
"""),
    ("code", """
lat = load("chutes/15_latency")
tf = lat["throughput_fit"]
md(f"Fitted throughputs: median **{tf['median_tok_s']:,.0f} tok/s**, max "
   f"**{tf['max_tok_s']:,.0f} tok/s** across {tf['models_fitted']} models.")
finding("not-supported", tf["verdict"])
"""),
    ("md", """
So latency is routed on **measured output tokens** — exactly measured, rather than
seconds roughly invented. Within a model, that is what decides how long a request takes.
"""),
    ("code", """
display(table([{"lambda_l": s["lam_latency"], "quality": round(s["quality"], 4),
                "p50 tokens": f"{s['p50_tokens']:,.0f}", "p95 tokens": f"{s['p95_tokens']:,.0f}",
                "p99 tokens": f"{s['p99_tokens']:,.0f}",
                "cheaper vs frontier": pct(s["savings_vs_frontier"])}
               for s in lat["lam_latency_sweep"]]))
off = lat["lam_latency_sweep"][0]
at = min(lat["lam_latency_sweep"], key=lambda s: abs(s["lam_latency"] - 0.1))
finding("new",
        f"Turning the latency term on at lambda_l=0.1 cuts routed p95 by "
        f"{1 - at['p95_tokens'] / off['p95_tokens']:.0%} AND raises savings from "
        f"{off['savings_vs_frontier']:.1%} to {at['savings_vs_frontier']:.1%}, for "
        f"{at['quality'] - off['quality']:+.4f} of quality. A shorter answer is both "
        f"faster and cheaper, so the two objectives point the same way — which nothing in "
        f"the source documents anticipates.")
show("chutes_10_latency", "Left: output length per slot, bar is p95 and tick is p50. "
     "Right: the latency term switched on for the first time.")
"""),
    ("md", """
## What this notebook does not show

- **The release dates are hand-entered** from public announcements, at month resolution.
  They can move *when* a model joins the replay; they cannot change any model's quality or
  price. RouterBench's dates are the ones that need no such caveat, which is why its 2023
  models are still in this repository.
- **No per-request latency exists anywhere in the corpus.** Seconds appear only at a stated
  assumed decode rate, and queueing is invisible to all of it.
- **3,541 items, nine benchmarks**, all of them hard — AIME, GPQA, LiveCodeBench, MMLU-Pro,
  Arena-Hard. RouterBench's 36,497 are mostly multiple-choice, so difficulty and headroom
  are not comparable between the two halves of this repo.
- **The bindings are the result.** Change one and the numbers move. The dominant-model
  finding in particular is a joint property of measured stand-in quality and real Chutes
  prices.
"""),
]


# ================================================================ 10 · rigor ==
N10 = [
    ("md", """
# 10 · Error bars, corrections, replication, and the baselines we were missing

`PUBLISHABILITY.md` graded every finding in this repository and the complaint was always
the same shape: large effects, clear mechanisms, almost no statistics. Three of roughly
twenty headline numbers carried an error bar. Fifteen claims were adjudicated with no
correction for having tested fifteen things. No published router appeared anywhere as a
baseline.

This notebook is the repair. Four things are fixed with compute; two cannot be fixed
without spending money, and are named at the end rather than glossed.

**Two results here contradict earlier claims in `RESULTS.md`, and both are corrected
there.** That is the point of running the statistics rather than asserting them.
"""),
    ("code", PRELUDE),
    ("md", """
## 1. Confidence intervals on every headline

Items are resampled, not cells: the same prompt answered by thirteen models is **one**
observation, and resampling cells would treat it as thirteen and shrink every interval by
roughly sqrt(13). 2,000 percentile bootstrap draws over the held-out items, with the
router fitted once and held fixed.
"""),
    ("code", """
b = load("chutes/16_bootstrap")
keys = ["savings_vs_frontier", "quality_vs_frontier", "savings_vs_best_single",
        "quality_vs_best_single", "share_of_oracle_captured", "val_brier"]
display(table([{"quantity": k, "mean": round(b[k]["mean"], 4),
                "95% CI": f"[{b[k]['lo']:.4f}, {b[k]['hi']:.4f}]",
                "width": round(b[k]["hi"] - b[k]["lo"], 4)} for k in keys]))
md(f"On **{b['n_test_items']:,}** held-out items, {b['n_boot']:,} bootstrap draws.")
"""),
    ("code", """
qb = b["quality_vs_best_single"]
finding("correction",
        f"The quality interval is [{qb['lo']:.3f}, {qb['hi']:.3f}] and it CONTAINS 1.0. "
        f"So 'we match the best single model's quality' is supported, and the 98.6% "
        f"point estimate should not be read as an established shortfall. The savings "
        f"interval is [{b['savings_vs_best_single']['lo']:.1%}, "
        f"{b['savings_vs_best_single']['hi']:.1%}] — nearly nine points wide, which is "
        f"the honest precision of the headline number.")
"""),
    ("md", """
## 2. The per-domain table, corrected

Five comparisons were being read as five findings. Paired standard errors — the same
question answered by both policies, so the SE is of the *difference* — with
Holm-Bonferroni across the family.
"""),
    ("code", """
d = load("chutes/17_domains")
display(table([{"domain": r["domain"], "n": r["items"],
                "delta": round(r["delta"], 4), "SE": round(r["se"], 4),
                "p": round(r["p_uncorrected"], 4),
                "Holm threshold": round(r["holm_threshold"], 4),
                "survives": r["significant"]} for r in d["rows"]]))
finding("correction", d["reading"])
"""),
    ("md", """
`RESULTS.md` previously described the knowledge result as sitting "exactly on the line".
It does not: p = 0.0112 against a Holm threshold of 0.0100. **Nothing in the per-domain
table survives correction**, including the router's apparent win on open-ended work. The
one thing that does survive is the observation that needs no test: the per-item oracle
scores 0.95-1.00 in every domain, so the headroom is real even where the wins are not.
"""),
    ("md", """
## 3. The most novel finding, replicated on a disjoint pool

Coverage bias — training on ten times the data costing twelve points of quality retention
— was measured once, on one pool. Here it is again on **thirteen models sharing no column
with the first set**, same corpus, same code path.
"""),
    ("code", """
rep = load("chutes/18_replication")["coverage_bias"]
display(table([{"arm": a["train_on"], "ridge lambda": a["ridge_lam"],
                "train items": f"{a['train_items']:,}",
                "val Brier": round(a["val_brier"], 4),
                "quality retained": pct(a["quality_vs_frontier"])}
               for a in rep["arms"]]))
finding("supported", rep["reading"])
"""),
    ("md", """
The gap is **larger** on the replication pool than on the original (+19.1% against
+12.2%), on a dense core of a comparable size. This moves the finding from "one corpus,
one pool" to a replicated result, and it is the strongest candidate here for something
publishable on its own.
"""),
    ("md", """
## 4. Are the savings an artefact of hard benchmarks?

Every headline is measured on nine hard benchmarks. Real traffic is mostly routine, and
`PUBLISHABILITY.md` asserted the figures were therefore a conservative *lower bound*. That
assertion was never measured. Here it is: the held-out set is reweighted toward items the
pool finds easy, where "easy" is a property of the item (pool solve rate) and not of any
policy, so the reweighting cannot flatter the router by construction.
"""),
    ("code", """
mix = load("chutes/18_replication")["workload_mix"]
display(table([{"easy share": pct(r["easy_share"], 0), "quality": round(r["quality"], 4),
                "$/call": round(r["cost_per_call_usd"], 6),
                "cheaper vs best single": pct(r["savings_vs_best_single"]),
                "open-tier share": pct(r["open_tier_share"])} for r in mix["rows"]]))
finding("not-supported",
        "The savings figure is FLAT across the workload mix - 20.3% on the benchmark mix "
        "as measured, 18.8% at 90% easy traffic. The earlier claim that these numbers are "
        "a conservative lower bound for real traffic is wrong and has been removed. What "
        "does change is quality (0.69 -> 0.94) and the open tier's share (3.0% -> 11.6%): "
        "easier traffic is answered better and by cheaper models, but the router does not "
        "convert that into proportionally more savings.")
"""),
    ("md", """
## 5. The baselines we did not have

Three families from the literature, reimplemented against the same held-out items, the
same price table and the same feature map. These are reimplementations rather than the
authors' code, so a loss here means "this rule, on this pool" — not "this paper is wrong".
"""),
    ("code", """
base = load("chutes/19_baselines")
display(table([{"policy": r["policy"], "quality vs best single": pct(r["quality_vs_best_single"]),
                "cheaper by": pct(r["savings_vs_best_single"]),
                "ours at same quality": (pct(r["our_savings_at_matched_quality"])
                                         if r.get("our_savings_at_matched_quality") is not None else "-"),
                "verdict": r.get("verdict", "")} for r in base["rows"][1:]]))
finding("supported", base["reading"])
"""),
    ("code", """
show("chutes_11_baselines", "Every strategy on the same items. The line is our dial; the "
     "markers are the reimplementations. Anything below zero spends more than sending "
     "everything to the best single model.")
"""),
    ("md", """
Read the comparison at **matched quality**, not against a fixed bar — each rule sits at its
own point on a cost/quality curve, and a fixed bar mostly measures where a rule's threshold
happened to land.

- **Cascades lose badly, and structurally.** A cascade pays for every attempt, so a chain
  ending at the third model has bought three answers and delivered one. At tau=0.8 it holds
  98.5% of quality and spends **4.6x** what we do. Even given an *oracle* verifier it
  cannot buy — one that knows the answer was wrong — it still spends 67% more than doing
  nothing.
- **Matrix factorisation ties us.** Rank 8 and 16 land within 1 point of our dial at the
  same quality. This is the honest headline of this section: a different, equally
  reasonable rule performs the same, so our estimator is not the source of the advantage.
- **Nothing beats us**, but "ties with a rank-8 SVD" is a more useful thing to know than a
  win would have been.
"""),
    ("md", """
## What is still missing, and why

Two items on the list cannot be closed with compute:

1. **The labels are still stand-ins.** Every number in this notebook describes a pool
   measured through proxy models. One graded run against the real endpoint fixes it -
   roughly 2,000 questions across 13 models, tens of dollars.
2. **There is still no timed endpoint.** Latency is routed on measured output tokens
   because the corpus's wall-clock is concurrent; seconds require one timed run.

Everything else on `PUBLISHABILITY.md`'s watch-list is now measured rather than asserted.
"""),
]


NOTEBOOKS = {
    "01_data_and_pool.ipynb": ("01 · The data, and the pool", N1),
    "02_router_engine.ipynb": ("02 · The router engine, and what it saves", N2),
    "03_staleness.ipynb": ("03 · Does a router trained once decay?", N3),
    "04_cold_start.ipynb": ("04 · Cold start", N4),
    "05_scoring_rule.ipynb": ("05 · The scoring rule, and two ways it breaks", N5),
    "06_non_stationarity.ipynb": ("06 · Structured non-stationarity", N6),
    "07_verdicts.ipynb": ("07 · What held, what did not", N7),
    "08_loss_and_scale.ipynb": ("08 · Loss, and what it buys", N8),
    "09_chutes_pool.ipynb": ("09 · The pool the product serves", N9),
    "10_rigor.ipynb": ("10 · Error bars, corrections, replication", N10),
}


def main() -> int:
    NB.mkdir(parents=True, exist_ok=True)
    for name, (title, cells) in NOTEBOOKS.items():
        path = NB / name
        path.write_text(json.dumps(nb(cells, title), indent=1))
        print(f"wrote {path.relative_to(ROOT)} ({len(cells)} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
