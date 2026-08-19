# backend — the router engine, and the experiments that test it

Python implementation of the RollingBench router (§8) and the Structured
Non-Stationarity extensions, plus the experiments each document specifies, run against a
real public label matrix.

The point of this directory is not to ship a router. It is to find out which of the
claims in the three proposals survive contact with data — including the ones that do not,
and there are several.

```bash
make setup          # venv + pinned deps
make data           # RouterBench, ~95 MB, once
make run            # every experiment (~15 min, CPU only)
make notebooks      # render the analysis
make test

make chutes-data       # parse LLMRouterBench into the 13-model cache (once, ~4 min)
make chutes            # train + analyse the router over the Chutes pool (~15 s)
make export-frontend   # artifacts/ → src/lib/measured.ts, which the site imports
```

Every figure the website quotes comes from `src/lib/measured.ts`, which is generated
and never hand-edited, so a number on a public page cannot drift from the run that
produced it. Re-run `make export-frontend` after any run that changes a headline.

Start with **`RESULTS.md`** — what was measured, what had to be corrected, and an
honest scoring of how close each piece is to shippable. Then **`PUBLISHABILITY.md`**,
which grades every finding by evidence tier and names the claims that are not yet
defensible — and **`RIGOR.md`**, which closes eight of its ten watch-list items: bootstrap
intervals on every headline, a family-wise correction that kills all five per-domain
claims, the coverage finding replicated on a disjoint pool, and the published-router
baselines that were missing. Two of those corrections contradicted earlier claims, and both
were fixed at source.

Then **`PUBLISHING.md`**, which re-ran all of that at n > 1 and is where the package
actually turned. The coverage finding stops being a replication and becomes a **cause**:
present in 15 of 15 pools with uneven coverage, absent in 4 of 4 without, still there with
the training-set size held fixed, and dialled up and down by changing nothing but the
observation mask. It is also twice the size first reported. Going the other way, it
retracts two things this repository had already published — a baseline that beat us on one
split and does not across eight, and a decay effect called significant by a rule that is
wrong at n = 8. Both fixed at source.

Then `notebooks/09_chutes_pool.ipynb` for the pool the product actually serves,
`07_verdicts.ipynb` for the research verdicts, `01`→`06` for the working, and `08` for
the loss curves and how the model was sized.

**On the 2023 models.** Notebooks 01–08 run on RouterBench — GPT-4 Turbo, Claude v1,
Llama 2. That pool is not the routing engine; it is the only public label matrix that
carries **release dates**, and without dates there is no way to replay a pool that grows
over calendar time. That replay is the staleness result. The engine itself is trained
entirely on current models (notebook 09), and 11 of its 13 stand-ins are open-weights
models of the kind Chutes actually serves.

---

## The data is real

Everything is measured on **RouterBench** (`withmartian/routerbench`, 0-shot split):

| | |
|---|---|
| items | 36,497 real prompts |
| models | 11 real commercial models (GPT-4 Turbo, Claude v1/v2/Instant, Mixtral, Yi-34B, Llama 2, Code Llama, Mistral 7B, WizardLM, GPT-3.5) |
| graded cells | 401,467 |
| realised inference cost | $333.79, already paid by whoever collected it |
| tasks | 79, from MMLU subjects to MBPP, GSM8K, HellaSwag and Chinese-language sets |

No inference was purchased to produce any result here. Every experiment replays graded
outcomes that are already on disk, which is what the proposals mean by "zero spend", and
it also means the numbers are reproducible on a laptop with no API keys.

Model **release dates** are attached in `rollingbench/catalog.py` from public
announcements, spanning March–December 2023. That is what makes the staleness study a
real retrospective rather than a simulation: the pool grows on the calendar it actually
grew on.

---

## Headline results

Full detail, with the measurement behind each one, in `notebooks/07_verdicts.ipynb`.

**Routing works, and the product's numbers hold.** 57.8% of model pairs score identically
on the same item — inside the 52.9–61.7% band §3.1 quotes, recomputed here on 2.0M
comparisons. At the calibrated operating point the router costs **44.5% less** than
sending everything to the strongest model while delivering **99.4%** of its measured
quality on 11,497 held-out items. The frontend's "40% cut" claim is met.

**A router trained once decays, badly.** Over a 26-week replay the frozen router falls
from -0.03 to **-1.03** and crosses below "one good model" — after which routing is worse
than not routing. The rolling router does not decay. §14.1's decision gate is passed and
the premise survives.

**But not for the reason the proposal implies.** The fourth arm (B′ — refits weekly, never
receives new models) separates the causes: **99%** of the recoverable gap comes from being
able to select models that did not exist at training time, and almost none from fresher
data on the models you already have. The binding constraint is pool coverage and cold
start, not evaluation freshness — which inverts the cost priority in §18.2.

**§8.3's shared Gram matrix is wrong where it matters most.** One shared A is exact under
uniform coverage. Thin one model's coverage to 50% and the shared-Gram router's estimate
of GPT-4 collapses and its traffic share falls to near zero — it stops
selecting the best model in the pool. Under-prediction tracks (1 − coverage) to three
decimals. Per-model Gram matrices, which is what §8.5 and §8.9 actually imply, are
unbiased at every coverage. This is the highest-value correction found, and it is exactly
the cold-start and sampling-plan regime the system depends on.

**Half of the scoring rule's denominator is luck.** §8.8 defines the oracle as the argmax
of realised outcomes, and 50.4% of the resulting oracle-to-baseline gap is unattainable by
any policy. That deflates every score, makes AC-1's "regret below 0.6" unreachable by
construction — a clairvoyant per-task oracle scores 0.078 — and, since §16.1 pays
emissions in proportion to these scores, pays partly on noise.

**Contribution 3's fix works; its diagnosis is inverted.** Information-aware shrinkage
improves what the payout depends on: ranking concordance 0.805 → 0.896. But §6 says the
denominator collapses when "every model performs about the same", and the measurement says
the opposite — batch information correlates **-0.55** with the spread between best and
worst model. The degenerate batches are the ones where models differ *most*. An operator
following §6's account would filter out easy batches and make it worse.

**Contribution 2 fails its own precondition.** The §5.1 bridge from item-space low-rank
factors to a feature-space prior explains R² = 0.29. The proposal's gate says that is not
enough to build on. The per-model breakdown is more interesting than the failure: loading
onto the pool's latent factors ranges from 0.43 down to **+0.004**, and the −0.008 is
GPT-4 — the frontier outlier whose arrival caused all the decay above. Matrix-completion
cold start works for models resembling the pool and fails for the ones that matter.

**Prediction loss is the wrong thing to size the model by.** §8.2 asserts d ≈ 64 without
justification, so it was swept. Validation Brier falls monotonically with d; *routing
regret* bottoms at d ≈ 64 and rises after. The largest model tested has the **best loss of
any configuration and routes worse than every smaller one**. The same split shows up in the
correlations: among plausibly-configured routers a **ranking** loss predicts regret at
r = +0.78 while the Brier score manages +0.35. The argmax reads the order between models
and throws the level away, so most of what the squared error optimises is wasted.

What *was* wrong is the part §8.2 never mentions. Widening the hash from 512 to 4,096
buckets lifts the share of the attainable gap captured from **+0.589 to +0.836** at an
unchanged d = 64 and an unchanged 358 KB artifact — collisions were destroying signal
before the projection ever saw it. (The first pass at this got it wrong: on a narrow hash
the sweep pointed at d ≈ 108 and it took four splits at the wider hash to show the gain
belonged to the encoder, not the dimension. Notebook 08 records both.)

**Contribution 1 is not carrying its weight.** Per-component decay (γ_q, γ_t) is not
detectable in either regime — +0.0021 ± 0.0010 under continuous drift engineered to
favour it, −0.0005 ± 0.0006 under the isolated-shock schedule — while doubling the Gram
state the artifact must carry. *Corrected: the drift arm was previously reported as
detectable at "2.0 SE". That used a normal approximation on eight seeds, where the
critical value is t(0.975, 7) = 2.365; the two-sided t-test gives p = 0.081. See
`PUBLISHING.md` §5.*
Separately, §8.4's suggested γ ≈ 0.999 is *worse* than no forgetting at all on this corpus.
The read-versus-learn half (1b) is worth keeping, for a reason the proposal does not give: a
learned-cost target conflates quality and cost, so a quality regression contaminates the
cost belief.

---

---

## The Chutes pool — the thirteen models the product actually serves

Everything above runs on RouterBench, which is the right corpus for the research
questions and the wrong pool for the product: a customer's request goes to one of the
thirteen Chutes models and none of them are in RouterBench. `make chutes` closes that
gap and trains the same §8 estimator over the pool the dashboard routes across.

**Where the data comes from, and what is assumed.** No public label matrix grades the
Chutes checkpoints, and the key in `.env.local` is empty, so nothing here can measure
a Chutes endpoint. Each of the thirteen slots is instead bound to a model
**LLMRouterBench did grade** — 700 graded runs over 27 tasks, already on disk — and the
router is trained on that column's real per-item outcomes. The split is:

| | |
|---|---|
| quality, output tokens | **measured**, per item, by the corpus's own graders |
| price | **real**, the published Chutes rate |
| cost per cell | measured tokens × published price — never the stand-in's own bill |
| the binding itself | **an assumption**, one per slot, argued in `catalog.CHUTES_PROXY` |

Ten of the thirteen bindings are same-family or better; one (Qwen3 235B Thinking) is
the *identical checkpoint*. Three are capability-matched only and are named as such in
the table, including the weakest — Qwen3.6 27B, where no Qwen checkpoint was left. Every
artifact carries `proxy_backed: true` and every figure carries the caveat in its
footer, so no number here can be mistaken for a measurement of Chutes itself. Swap in a
real graded run and everything downstream recomputes with no other edit.

The matrix is 25,034 items × 13 models, 185,285 graded cells, with a fully-observed
core of 3,541 items across nine tasks (AIME, GPQA, LiveCodeBench, MMLU-Pro, Arena-Hard
and its splits, LiveMathBench).

### What it found

**The product's own counterfactual is the wrong opponent on this pool.** The savings
claim is quoted against the frontier model — "what this traffic would have cost on one
strong model" — and here that model, GLM 5.2, is *beaten outright on both axes* by
Qwen3 235B Thinking: higher quality (0.834 against 0.831) at a quarter of the cost.
Savings measured against a model that a single cheaper model already dominates are
inflated by the gap between two models the router had nothing to do with. Both are
therefore reported everywhere, and the pipeline says so in its own output. Against the
frontier model the router is **79.6% ± 0.3% cheaper at 97.8% ± 0.4% of its quality**;
against the best single model it is **19.5% ± 1.4% cheaper at 98.6% ± 0.4%**, over
eight splits. The second is the number to quote.

That second number is also the ceiling on what routing is worth here, and it is a
modest one: a pool containing a model that is both near-best and cheap leaves a router
little to arbitrage. Nothing dominates the pool outright — the cheapest column is never
beaten on price — but one strong, cheap model compresses the opportunity a long way.

**The inherited operating point is wrong on this pool, badly.** λ_c = 0.05 is this
package's calibrated dial *on RouterBench*, and carried over unexamined it makes the
router spend **84% more** than simply sending everything to the best single model, for
slightly less quality. λ_c weights a cost *ratio*, and this pool's ratios span three
orders of magnitude where RouterBench's span one, so at 0.05 the cost term barely
enters the argmax. Calibration is a pipeline stage now, not a constant: the dial is set
to the loosest value that still holds 99% of the best single model's quality, which is
λ_c = 0.2 here. `tests/test_chutes.py` pins the failure so it cannot quietly return.

**Uneven coverage made the router worse, and ten times the data did not save it.**
Training on every graded item (23,795) instead of the fully-observed core (2,302) costs
**twelve points** of quality retention — 88.1% against 100.3%. The columns are graded on
different task mixes, so their weights are fitted over different regions of feature space
and stop being comparable at the argmax, and the small open models — run on 22 tasks
including easy ones the large models never saw — extrapolate confidently onto hard items.
This is the same coverage pathology the shared-Gram result above is about, arriving
through the training set instead of through the Gram matrix.

The framing above was originally "ten times the data made it worse", which conflated two
effects with opposite signs. A third arm — the same unevenly covered items, **cut to the
dense arm's size** — retains 85.9%, so the gap is **+14.5 points at equal n**, larger than
with ten times the data. The volume was partly *compensating*. On two further pools the
same holds, and the effect can be dialled up and down by changing nothing but the
observation mask: `PUBLISHING.md` §1.

**470 cells were failed calls wearing the costume of measurements.** Zero input tokens,
zero output tokens, and a score of exactly 0.0 where every other cell averages 0.60.
Left in, they teach the quality lane that a reliability failure is an inability to
answer, and the cost lane that the model was free — and on the two items where the
*reference* model failed, c_ref lands in a denominator and the mean utility goes to
−439,045. They are marked unobserved. Cells billed for input that returned nothing (31
of them) are real failures and stay.

**Two of the thirteen slots never win a request — and they are not dominated.** Mistral
Nemo Instruct and Gemma 4 31B Turbo take 0% of traffic at every λ_c, while a per-item
oracle sends them **30.8%**. They are unreachable, not worthless: the gap between model
means (0.615) is four times the router's per-item prediction spread (0.160), so a cheap
column can never win an argmax. The threshold rule the product advertises — "cheapest model
that will get this right" — was implemented and loses at every matched quality, because a
threshold needs the predicted *level* to be right where an argmax needs only the *order*.
Keep the slots; fix the estimator.

**The decay result replicates on the current pool.** Release dates attached by hand from
the labs' announcements let the growing-pool replay run where the product lives: 5 → 13
models, frozen router +0.127 → **−1.062**, crossing below "one good model" at **week 9**,
with **93%** of the gap from new-model access against RouterBench's 99%. Cold start prices
it: a newly-shipped model needs about **1,000 probe items** before the router can use it,
and only the informative prior gets there at all.

**Latency is not measurable from this corpus, and the code says so.** Wall-clock is
published per run, not per record; fitting throughput from it puts 26 of 38 models above
500 tok/s (one at 10,810) with 22 of 38 fits below R² 0.3 — the runs were concurrent, so it
measures harness throughput, not request latency. Routing instead uses **measured output
tokens**, and switching §8.7's latency term on for the first time cuts routed p95 by **52%**
while *raising* savings from 79.7% to 83.9%: a shorter answer is both faster and cheaper, so
the two objectives point the same way. The per-item oracle reaches 0.973 against
the router's 0.829, so most of the available signal is still on the table — the ceiling
is the per-item quality prediction (Brier skill +0.257, pairwise ranking concordance
0.826), not the decision rule.

**Prediction loss is the wrong thing to size this model by, here too.** The capacity
sweep reports validation Brier and realised savings from the same fits, and they do not
peak together: loss is still falling at d = 64 while savings peak at **d = 28**. Sizing
on the loss curve alone ships a model five times the artifact size that routes slightly
worse. Same split this repository's RouterBench study found, arrived at independently on
a different corpus and a different pool. The learning curve converges by roughly **2,000
graded items** — which is the number that matters operationally, because it sets how
much probing a new model needs before it can be trusted in the pool.

**A price change reaches routing with no refit, and it is worth a lot.** Price is a
live-read lane, never fitted, so `experiments/prices.py` tests the claim rather than
repeating it: it reads the published list from `llm.chutes.ai/v1/models` (public, no key)
and re-decides held-out traffic under a changed table, hashing the fitted weights either
side. They are byte-identical at every point. The elasticity is the interesting part —
quadrupling the price of the model that carries 42.6% of traffic moves it to 3.3%, and
holds the bill at **$7.61 against the $20.75** a router that could not react would have
paid. That is a 63% saving from a lane that costs nothing to update.

### Limits, beyond the ones the rest of this README already states

- **The bindings are the result.** Change one and the numbers move. The dominant-model
  finding in particular is a joint property of measured proxy quality and real Chutes
  prices, and a different plausible binding could remove it.
- **3,541 dense items, nine tasks**, all of them hard benchmarks. RouterBench's 36,497
  items are mostly multiple-choice; this pool is AIME and LiveCodeBench, so the
  difficulty mix — and the headroom — is not comparable between the two halves of this
  repository.
- **No release dates**, so none of the staleness or cold-start work above runs on this
  pool. It answers "does routing pay here", not "does it keep paying".

---

## Layout

```
rollingbench/
  catalog.py            the two pools, and CHUTES_PROXY — the bridge between them
  features.py           φ(q) — frozen hashed n-grams (4,096) + surface features + PCA, d = 64
  router.py             the estimator: §8 baseline and the §4 decomposition
  coldstart.py          IRT, low-rank completion, the §5.2 derived prior, the §5.1 bridge
  metrics.py            §8.8 regret, the §6.1 shrinkage, and the feasible-oracle variant
  plots.py              one function per figure
  data/
    labelmatrix.py      the one object everything reads
    routerbench.py      corpus adapter
    llmrouterbench.py   the other one — streams the archive, never extracts it
    cache.py            feature cache (φ is fit-once, so it is computed once)
  experiments/
    chutes.py           the product's pool: build, calibrate, train, analyse, size
    prices.py           the live price list, and FR-16 as a test rather than a claim
    latency.py          why wall-clock here is not latency, and what to route on instead
    rigor.py            bootstrap CIs, Holm correction, replication, workload mix
    baselines.py        cascade and matrix-factorisation routers, reimplemented
    scaling.py          loss against data, capacity, regularisation — and against regret
    frontier.py         the cost/quality dial; every policy compared
    staleness.py        §14.1, the four-arm replay
    coldstart_sc.py     7.4 the bridge check, then 7.2 leave-one-model-out
    metric.py           7.3, both degeneracies, plus the κ ablation
    decomposition.py    7.1, shocks and per-component decay
    gram.py             shared vs per-model Gram — not in the proposals, found here
scripts/
  fetch_data.py         download corpora
  build_chutes_matrix.py  LLMRouterBench → data/cache/llmrouterbench.npz
  train_chutes.py       the Chutes pool, stage by stage → artifacts/chutes/
  export_measured.py    artifacts/ → src/lib/measured.ts, the site's only figures
  run_all.py            run everything → artifacts/*.json + figures
  build_notebooks.py    notebooks are build output; this file is their source
  execute_notebooks.py  run them, baking outputs in
  export_frontend.py    emit the measured DECAY_SERIES for src/lib/data.ts
notebooks/              01…10, executed, with figures embedded
                        09 is the product's pool, 10 the statistics; 01–08 RouterBench
  publish_close.py      the second pass over PUBLISHABILITY.md §6 (`make publish`)
  measure_latency.py    timed endpoint probe — latency in seconds, not tokens
RESULTS.md              what we got, and how far it is from shippable
PUBLISHABILITY.md       what each finding will bear, graded by evidence tier
RIGOR.md                the watch-list, actioned — CIs, corrections, replication
PUBLISHING.md           the same list re-run at n > 1: one cause found, two retractions
GRADED_RUN.md           the paid run — 4 of 13 slots measured on a real endpoint
PM_UPDATE.md            the same story for a product manager, step by step
artifacts/              every number the analysis quotes, as JSON
  chutes/               the Chutes pool, one artifact per pipeline stage
tests/                  119 tests, each pinning a property a claim depends on
```

The compute split matters: `run_all.py` does the work once and writes JSON; the notebooks
read that JSON. So the analysis cannot disagree with the artifacts, and re-reading it
costs seconds.

## The estimator, in brief

Closed-form throughout, as §8.1 requires — no gradient descent, no GPU, no training job.

- **φ** is frozen after one SVD fit: hashed word and character n-grams (4,096 buckets)
  projected to 52 components, plus 11 surface features and a bias, so **d = 64**. Both
  numbers were measured rather than assumed — see notebook 08. The encoder is deliberately
  cheap on §3.1's evidence that encoder scale barely moves routing accuracy.
- **Quality and expected output tokens** are ridge regressions with their own Gram matrix
  per model. Rank-one updates, O(d²) ≈ 4,000 flops per observation.
- **Uncertainty** is σ_m(x) = √(xᵀA_m⁻¹x), so cold start, drift absorption and exploration
  are one mechanism (§8.5) rather than three.
- **Price and latency** are read from a live table at decision time and never fitted, so a
  price change reaches decisions with no refit and no redeploy (FR-16).
- **Artifact**: 358 KB at d = 64, K = 11, float32 — inside O3's 1 MB and NFR-4's 5 MB.
- **Fit**: one pass over 25,000 items in under a second on one CPU core.

## Deviations from the documents, and why

Each is argued in the docstring at the point of change, and each is measured.

| what | why |
|---|---|
| Per-model Gram matrices by default, not §8.3's shared one | Exact only under uniform coverage; costs up to 0.053 utility otherwise. `shared_gram=True` reproduces §8.3 to measure the difference. |
| c_ref pinned to the highest-quality model, not §8.7's "Best Single" | Best Single is defined *from* c_ref, so the literal reading is self-referential; sweeping λ_c under it produces a discontinuity (19% → 93% savings) as the fixed point jumps. |
| γ applied as γⁿ per block of n observations | §8.4 defines the window in observations; applying γ once per batch makes its meaning depend on how the stream happens to be batched. |
| The ridge floor is held out of the decay | Scaling A by γ decays λI too; over a long replay the Gram matrix collapses and the solve raises `Singular matrix`. |
| 4,096 hash buckets, where §8.2 specifies only d | Measured: at 512 buckets collisions cost a third of the attainable gap, and buckets are free at serving time. d ≈ 64 itself is confirmed. |
| A feasible-oracle score reported beside §8.8's | Half of §8.8's denominator is unattainable luck, so it cannot rank policies on its own. Both are always reported. |

## Limits

Stated because several of them bound the conclusions above.

- **One corpus, 11 models, 2023 vintage.** The staleness result is one trajectory through
  one pool's history.
- **Binary grading.** Mostly multiple-choice, so per-item outcomes carry a lot of luck.
  That causes the oracle finding and caps how much per-item signal any router can extract.
- **No item dates.** RouterBench does not date its prompts, so the replay holds the item
  distribution fixed. Workload drift and contamination — two of §3.3's five causes — are
  not measured at all.
- **Synthetic shocks.** Every drift result rests on injected changes; a static snapshot
  contains no real drift. Magnitudes are plausible, not observed.
- **n = 1 where it counts.** Only one of eleven models had a material onboarding gap, so
  the cold-start conclusions rest on a single instance.
- **Cheap feature map.** Hashed n-grams, not a sentence encoder. §3.1's claim that encoder
  scale barely matters was taken on trust, so the absolute scores are a floor.

## Other corpora

LLMRouterBench is no longer an "obvious next step" — it is what the Chutes pool above is
built from. 40 models over 27 tasks, with *measured* token counts, which RouterBench does
not publish. `rollingbench/data/llmrouterbench.py` is the adapter; note that it streams
the archive rather than extracting it, because expanding 1.2 GB of compressed JSON whose
bulk is `raw_output` fills a normal disk and takes the machine down with it.

`scripts/fetch_data.py --corpus all` also fetches MixInstruct (pairwise preferences, for
a quality-label cross-check). It is not required and no result depends on it.

Replicating the *staleness* findings on a larger pool is still open: LLMRouterBench
carries no release dates, so the growing-pool replay cannot run against it.
