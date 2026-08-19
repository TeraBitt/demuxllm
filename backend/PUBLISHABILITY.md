# Is this publishable? A quantitative self-assessment

Companion to `RESULTS.md`. That document says what was measured; this one says how much
weight each measurement will bear, what would survive review, and what would not.

Written to be uncomfortable rather than encouraging. Every claim below carries an n, a
standard error where one exists, and an explicit note where one does not.

---

## 1. The one-line answer

**The methodology and the corrections are publishable. The product numbers are not.**

> **Update — four of thirteen slots have now been graded on the real checkpoints.**
> See `GRADED_RUN.md`. It does not move the Tier C findings to Tier A: the run covers
> 4 of 13 slots, 55 items, and 4 of 9 benchmarks, so the pool the headline numbers
> describe is still not the pool anyone measured. What it does is put a size on the
> assumption, and the answer is uncomfortable in a way this document did not anticipate.
> Quality error is modest (mean 0.073, two of four resolving); **token-count error runs
> to 4×**, and every cost figure in the package is tokens × price. The audit is in §2b.

> **Update — §6's list has had a second pass, and it moved one finding and retracted
> two.** See `PUBLISHING.md`. The coverage-bias result is no longer merely replicated:
> it is present in every pool with uneven coverage, absent in every pool without, holds
> with the training-set size held fixed, and can be dialled up and down by changing
> nothing but the observation mask. It is also **larger** than reported — 24 points, not
> 12. Against that, a published baseline that this repository said beat us does not, and
> a per-component decay effect it called detectable is not. §6's table below records
> what is closed and what is left.

Split by what the finding is *about*:

| | count | status |
|---|---|---|
| Findings about **routers in general**, measured on real public data | 9 | publishable as a systems/empirical paper |
| Findings about **the Chutes product's economics** | 6 | **not publishable** — the labels are stand-ins |
| Findings about **the corpora themselves** (data-quality results) | 3 | publishable as short notes |

The blocker is not rigour. It is that six of the headline numbers describe a pool nobody
in this repository has measured.

---

## 2. Evidence grading, finding by finding

Tiers are defined by what a reviewer could not object to:

- **A** — real measured data, n > 10⁴ cells, effect is either replicated or carries an
  error bar, and the mechanism is identified.
- **B** — real measured data, single measurement, no error bar, but a large effect with a
  clear mechanism. Publishable as a negative result or methods note; a reviewer will ask
  for replication.
- **C** — proxy-backed, underpowered, or both. Not defensible as stated.

### Tier A — 7 findings

| finding | measurement | n | why it holds |
|---|---|---|---|
| Ties: 57.8% of model pairs score identically | RouterBench | **2,007,335 pairwise comparisons** | n is enormous; the quantity is a direct count, not a fit |
| §8.3's shared Gram is biased under uneven coverage | 14 coverage points | 36,497 items | under-prediction tracks (1 − coverage) to **3 decimal places**; the mechanism is provable and the data confirms it |
| 50.4% of §8.8's oracle-to-baseline gap is unattainable luck | RouterBench | 401,467 cells | a definitional result confirmed empirically; a clairvoyant per-task oracle scores 0.078 |
| A router trained once decays, and the cause is new-model access | **two independent pools** | 36,497 + 3,541 items | replicated: 99% and 93% attribution to new models, on model generations two years apart |
| **Uneven coverage, not data volume, is what costs a router its quality** | **19 pools + a controlled mask sweep** | 25,034 items | present in **15 of 15** asymmetric pools, absent in **4 of 4** uniform ones, **+23.7 points with the item count held fixed**, and monotone in a dose that varies nothing but the mask. `PUBLISHING.md` §1 |
| Component-wise γ_q/γ_t does not beat one shared γ | 8 seeds, 2 regimes | — | **−0.0005 ± 0.0006** (p = 0.41) and **+0.0021 ± 0.0010** (p = 0.081) over 8 seeds. Null in *both* regimes — the second was previously called supported by a 2-SE rule that is wrong at n = 8. `PUBLISHING.md` §5 |
| Information-aware shrinkage improves ranking concordance | RouterBench | 400 batches | 0.805 → 0.896, large and monotone |

### Tier B — 6 findings

| finding | measurement | what a reviewer will ask |
|---|---|---|
| ~~Uneven coverage costs more than 10× the data buys~~ | **promoted to Tier A** | and the framing was wrong: with the item count held fixed the cost is **+23.7 points**, so extra data was *masking* a fifth of it. `PUBLISHING.md` §1 |
| Prediction loss and routing quality peak at different capacity (d=64 vs d=28) | **2 corpora** | replicated across RouterBench and the Chutes pool — the strongest of the B tier, arguably A once the proxy is removed |
| An argmax needs the ordering; a threshold needs the level | 1 corpus | clean mechanism, large effect (+20.1% vs −78.7% at matched quality), but a single pool |
| §5.1's item-space→feature-space bridge fails its own gate (R² = 0.29) | RouterBench | fine as stated; it is the proposal's own criterion |
| Wall-clock in LLMRouterBench cannot yield per-request latency | 38 models | **26 of 38** fits above 500 tok/s (max 10,810), **22 of 38** with R² < 0.3. A data-quality note, useful and short |
| Widening the hash 512 → 4,096 lifts captured gap +0.589 → +0.836 | 4 splits | a tuning result; needs the splits reported, which they are |

### Tier C — 5 findings, not defensible as stated

| finding | why not |
|---|---|
| "19.5% ± 1.4% cheaper at 98.6% of the best single model" | **proxy-backed.** This is a claim about Chutes economics derived from stand-in models. No venue accepts it, and neither should a customer |
| "79.6% cheaper than the strongest model" | same, and the baseline is additionally soft (that model is dominated) |
| Two slots are worth 30.8% of traffic to an oracle | proxy-backed, and the number depends on the binding for those two slots specifically |
| Cold start costs ~1,000 probe items | proxy-backed, **n = 4 models** with a material gap out of 13 |
| Per-domain wins and losses | **underpowered — see §3** |

---

## 2b. The proxy audit — how wrong the stand-ins actually were

55 items, four slots, paired bootstrap on the per-item difference. Paired because both
columns answered the same questions, which is the only reason anything resolves at this n.

| slot | stood in by | binding quality | proxy | real | error (95% CI) |
|---|---|---|---|---|---|
| DeepSeek V4 Flash | DeepSeek-R1-0528-Qwen3-8B | same family | 0.818 | 0.818 | +0.000 [−0.091, +0.091] |
| Kimi K2.6 | kimi-k2-0905 | same line | 0.782 | 0.891 | **−0.109** [−0.200, −0.036] |
| Kimi K3 | gpt-5 | capability only | 0.891 | 0.873 | +0.018 [−0.054, +0.091] |
| GLM 5.2 | gemini-2.5-pro | capability only | 0.727 | 0.891 | **−0.164** [−0.255, −0.073] |

Three things follow, and only the first is comforting:

**The binding taxonomy does not predict the error.** §5's watch-list implicitly ranked
risk by how close the stand-in was — identical checkpoint, then same family, then
capability-matched. It does not hold. One capability-only binding (`Kimi K3 ← gpt-5`) is
the second most accurate in the table; the other (`GLM 5.2 ← gemini-2.5-pro`) is the
worst. A same-line binding (`Kimi K2.6 ← kimi-k2-0905`, an earlier point release of the
same weights) is significantly wrong. Closeness of family was not the variable.

**Both resolved errors understate the real model.** The pool's frontier is better than the
package assumes — which cuts against the product, not for it: a stronger best-single model
is a harder baseline to beat.

**The quality lane was the wrong thing to worry about.** Token counts are wrong by 0.25×
to 3.47×, and cost per cell is tokens × published price. `RESULTS.md` §7 lists quality and
output tokens side by side as equally real. They are equally *measured* — of the stand-in
— but the stand-ins were selected on capability, and nobody checked verbosity.

Consequence for the shipped router, measured: decisions unchanged, realised bill **+28.6%**
against what the model predicted, with only 22% of traffic reaching a measured slot.

**What this does to the evidence tiers.** Nothing moves to Tier A. The Tier C findings in
§2 stay Tier C — 4 of 13 slots on 55 items cannot carry a claim about a 13-model pool. But
the reason has changed: it is no longer "the labels are unverified", it is "the labels are
verified to be wrong in the cost lane, by an amount we have bounded on a third of the pool
and not on the rest."

---

## 3. Where the statistics are too thin, with numbers

The per-domain table in `RESULTS.md` §8.2 is the weakest thing in the document. Paired
standard errors on the router-minus-best-single difference:

| domain | n | delta | SE | |delta| / SE |
|---|---|---|---|---|
| knowledge | 343 | −0.0466 | 0.0183 | **2.6** |
| science | 58 | −0.1379 | 0.0574 | **2.4** |
| openended | 326 | +0.0230 | 0.0163 | 1.4 |
| code | 395 | −0.0253 | 0.0206 | 1.2 |
| math | 117 | +0.0000 | 0.0321 | 0.0 |

Read honestly:

- **None of the five domains survives correction.** Run properly in `RIGOR.md` §2 with
  Holm–Bonferroni: knowledge p = 0.0112 against a threshold of 0.0100 — it does *not* sit
  "exactly on the line" as this document first said, it fails. Science is p = 0.0196
  against 0.0125. **Zero of five survive.**
- **"The router beats the best single model on open-ended work" is 1.4 SE.** That was not a
  finding. It was stated as one in `RESULTS.md` and has since been corrected there.
- ~~**15 claims are tested across the repository with no multiple-comparison
  correction.** At α = 0.05 and 15 tests, roughly one false positive is expected by
  construction.~~ **Corrected — this was wrong in both directions.** Only **2 of the 15**
  claims are hypothesis tests at all; 4 are counts over a census, which have no null to
  correct, and 9 are point estimates with no standard error, which need an *interval* and
  not a correction. But those 2 claims rest on **15 separate comparisons** across two
  drift regimes and three shock kinds, which the claim count hid. Corrected properly:
  **1 survives Holm inside its family, 0 survive Benjamini–Hochberg across all of them.**
  `PUBLISHING.md` §4.

**Error bars: closed, on two instruments.** Every headline carries a 2,000-draw bootstrap
interval (`RIGOR.md` §1) and a k-fold spread at k = 3, 5 and 10 (`PUBLISHING.md` §2). The
consequential part: the savings figure is **20.2% (95% CI 15.8–24.6%)** — ±4.4 points, not
the ±1.4 the cross-validation SE implied, because the two measure different things. k-fold
puts the same figure at **21.4–23.0%** depending on k, so the level is not in doubt.

And the quality interval **contains 1.0**, so matching the best single model is supported
and the 98.6% point estimate is not an established shortfall — *but quote the bootstrap
interval, not the k-fold one, when saying so.* The k-fold interval answers the parity
question **differently at k = 3, 5 and 10**, because its folds share training items and its
width therefore has no coverage guarantee. That is a good demonstration of why the two
instruments are labelled with which question they answer.

---

## 4. How RollingBench is preserved

This is the part that *is* in good shape, and it is unusual. The specification is not
paraphrased and then abandoned — it is tracked, cited, and contradicted in public.

### Coverage, counted

| | count |
|---|---|
| Distinct § sections cited in code and tests | **35** |
| Named requirements referenced (FR / NFR / AC / O) | **12** — AC-1, FR-5, FR-14, FR-15, FR-16, FR-21, FR-23, FR-25, NFR-1, NFR-4, NFR-7, NFR-12 |
| Testable claims extracted and adjudicated | **15** |
| Verdicts: supported / not supported / mixed | **7 / 7 / 1** — claim 11 moved from *mixed* to *not supported* when its significance rule was corrected (`PUBLISHING.md` §5) |
| Of those 15, how many are actually hypothesis tests | **2** — the rest are 4 censuses and 9 point estimates. `PUBLISHING.md` §4 |
| Documented deviations from the spec, each with a measured cost | **6** |
| Test functions pinning a property some claim depends on | **119** |

The most-cited sections are the ones the product rests on: §8.8 (36 references), §8.3
(25), §8.7 (20), §6 (18).

### The preservation mechanism, and why it matters more than the count

Four rules are followed everywhere, and together they are the reason this survives contact
with a reviewer:

1. **Every deviation is argued at the point of change.** `router.py`'s `_RidgeLane`
   docstring quotes §8.3 and §8.5 against each other before choosing; `metrics.py`'s
   `reference_column` quotes §8.7 and explains why the literal reading is
   self-referential. A reader who disagrees can find the reasoning without leaving the
   file.
2. **Every deviation carries the cost of taking it the other way.** `shared_gram=True`
   reproduces §8.3 as written so the shortcut can be *measured* (up to 0.058 utility)
   rather than asserted.
3. **Contradictions are reported at the same volume as confirmations.** 6 of 15 claims are
   marked not supported, including two the product's own marketing depends on.
4. **Every correction becomes a test.** All 6 deviations and all 5 process corrections in
   `RESULTS.md` §5 are pinned, so a future change cannot silently reintroduce them. The
   three corrections in `PUBLISHING.md` are pinned too — including a test that reconstructs
   the exact 2.04-SE sample that the old significance rule called supported.

### Where preservation is weakest

- **§14.1's decision gate is passed on RouterBench and replicated on a proxy pool.** The
  replication is real work, but the dates are hand-entered at month resolution.
- **§16 (emissions/payouts) and §12 are cited 2 and 2 times** and are essentially untested;
  the scoring-rule work touches §16.1 only indirectly through `metric.py`.
- **§18.2's sampling plan is discussed but not implemented.** The cold-start result implies
  it, but no experiment runs the plan as written.

---

## 5. What to keep in mind — the quantitative watch-list

Ordered by how much damage each does if forgotten.

**1. Six headline numbers describe a pool nobody measured.** 185,285 of the Chutes pool's
graded cells belong to stand-in models. `proxy_backed: true` is in every artifact for a
reason. Cost to fix: ~~**~2,000 graded questions × 13 models, tens of dollars**~~ —
*measured, and low by an order of magnitude: **~$256** for 2,000 items × 13 models at live
prices, **~$504** for the full dense core, plus **$51–544** of Arena-Hard judging the
estimate omitted. Partially actioned for four slots; see §2b.*

**2. One model dominates the pool, which caps everything.** Qwen3 235B Thinking beats the
strongest model on quality *and* costs a quarter as much. That single fact is why the
honest savings number is 19.5% and not 79.6%. If a future price change removes that
dominance, both numbers move a long way.

**3. The evaluation set is 9 hard benchmarks, not product traffic.** AIME, GPQA,
LiveCodeBench, MMLU-Pro, Arena-Hard. On these, cheap models score 0.22–0.51; on the
22-task set that includes routine work they score **0.44–0.67**.

*Corrected — this originally claimed the savings figures were therefore a conservative
lower bound. Measured in `RIGOR.md` §4, they are **flat**: 20.3% on the benchmark mix as
measured, 22.2% at 50% easy traffic, 18.8% at 90%. The honest statement is that the
headline is **robust** to workload mix, not conservative. Quality does move a long way
(0.69 → 0.94) and the open tier's share triples, but savings do not follow.*

**4. Three of twenty numbers have error bars.** *Closed on two instruments* — a
bootstrap over items (`RIGOR.md` §1) and k-fold at three values of k (`PUBLISHING.md` §2).
The residual, and it is real: **nine of the fifteen adjudicated claims are still point
estimates with no interval**, and that is a larger job than either. They are enumerated in
`PUBLISHING.md` §4 so the list cannot be lost again.

**5. 15 claims, no multiple-comparison correction.** *Closed, and the premise was wrong* —
only 2 of the 15 are hypothesis tests, but they rest on 15 comparisons. Holm inside each
family leaves **1**; Benjamini–Hochberg across all of them leaves **0**. `PUBLISHING.md` §4.

**6. n = 1 corpus for the two most novel findings.** *Half closed.* Coverage bias is now
measured on 19 pools with 4 negative controls, a size-matched arm and a mask sweep, and is
causal rather than correlational (`PUBLISHING.md` §1). **Argmax-vs-threshold is still one
pool** and is now the most under-evidenced novel claim in the repository.

**7. Zero comparisons to published routers.** *Closed, and then partly retracted.*
`RIGOR.md` §5 reimplements six families and sweeps each across its own dial. Cascades and
HybridLLM lose structurally and do so in **8 of 8 splits** — cascades pay per attempt, 4.6×
our spend at τ = 0.8. But that document's headline, "matrix factorisation beats us by 3.6
points", was a single split: across eight it **loses to us by 6.6 ± 7.8 points** and wins on
two. The surviving claim is weaker in both directions — no published family reliably beats
this router, and a nearly parameter-free one lands close enough that the ridge estimator is
probably not where the advantage lives. `PUBLISHING.md` §3.

**8. No latency in seconds, anywhere.** The corpus's wall-clock is concurrent. The routed
p95 of 18,195 output tokens is real; converting it to seconds is not. *The harness that
would close this is written, exercised end to end against synthesised timings, and costs
about $1 to run* — `scripts/measure_latency.py`, `PUBLISHING.md` §6. It is blocked on a
key, not on effort.

**9. The release dates are hand-entered.** They shift *when* a model joins the replay and
nothing else — no quality, no price — but the Chutes staleness arm depends on them.

**10. The science domain result is 2.4 SE on 58 items.** *Closed* — it does not survive
Holm–Bonferroni, and neither does anything else in that table.

---

## 6. What would make it publishable, in order

| step | status | what it actually did |
|---|---|---|
| ~~Grade the 13 models on the real endpoint~~ | **done for 4 of 13** — $13.63 | did **not** move anything to Tier A (§2b). Bounded the assumption instead: quality error 0.073, **token error up to 4×** |
| ~~Replicate coverage bias on a second pool~~ | **done, and taken further** | not just replicated — 19 pools, 4 negative controls, a size-matched arm and a mask sweep. The finding is **causal** and **twice the size** the table assumed. `PUBLISHING.md` §1 |
| ~~Add error bars to every headline via k-fold~~ | **done** | k = 3, 5, 10 beside the bootstrap. The level is settled (21.4–23.0%); the *parity* claim turns out to be instrument-dependent, which is the finding. `PUBLISHING.md` §2 |
| ~~Add one published router as a baseline~~ | **done in `RIGOR.md` §5, headline retracted** | six families swept. Cascades and HybridLLM lose in 8 of 8 splits. The "matrix factorisation beats us" result was one split and does not survive. `PUBLISHING.md` §3 |
| ~~Report per-domain results with SEs and a correction~~ | **done in `RIGOR.md` §2, extended** | zero of five domains survive Holm; the whole repository is now classified and corrected, and zero of fifteen comparisons survive BH. `PUBLISHING.md` §4 |
| **Grade the remaining 9 slots** | **open — the binding constraint** | needs an endpoint that serves them. Fireworks has none serverless, including all 5 Qwen slots. This is access, not money |
| **Extend the graded set past 55 items and 4 benchmarks** | **open** | ~$25 of remaining credit buys ~170 more items on the four reachable slots. `arenahard` additionally needs a judge; `livecodebench` needs sandboxed execution |
| **One timed run against the endpoint** | **open — harness ready** | `scripts/measure_latency.py`, exercised end to end, ~$1. Replaces §4c with measured seconds |

Five of eight closed. **Every remaining row is blocked on endpoint access**, and the first
of them is the only thing standing between this package and a defensible claim about the
product.

The first row was written expecting a measurement that would convert six findings; what it
produced was a *bound* on four slots, and the news was that the error lives in the cost
lane rather than the quality lane. The four rows that followed it did more than the table
predicted — one of them moved a finding from "replicated" to "caused" and two of them
retracted claims this repository had already published.

---

## 7. Verdict

- **As an internal engineering document**: strong. Every number traces to an artifact, the
  test suite pins the claims, and the corrections are documented with their costs —
  including the three this repository has had to make against itself.
- **As a systems/empirical paper about routing**: **the coverage-bias result is now the
  paper**, and it no longer needs the rows §6 said it needed. It is causal rather than
  correlational, size-matched, dose-controlled, split-stable, and larger than first
  reported. The loss-vs-routing finding and the negative results are the supporting cast.
- **As evidence for the product's economics**: not yet, and not for want of arithmetic.
  Nine of thirteen slots describe models nobody has measured, and the only thing that
  closes that is an endpoint that serves them.
