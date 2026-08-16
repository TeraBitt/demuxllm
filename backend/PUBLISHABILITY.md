# Is this publishable? A quantitative self-assessment

Companion to `RESULTS.md`. That document says what was measured; this one says how much
weight each measurement will bear, what would survive review, and what would not.

Written to be uncomfortable rather than encouraging. Every claim below carries an n, a
standard error where one exists, and an explicit note where one does not.

---

## 1. The one-line answer

**The methodology and the corrections are publishable. The product numbers are not.**

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

### Tier A — 6 findings

| finding | measurement | n | why it holds |
|---|---|---|---|
| Ties: 57.8% of model pairs score identically | RouterBench | **2,007,335 pairwise comparisons** | n is enormous; the quantity is a direct count, not a fit |
| §8.3's shared Gram is biased under uneven coverage | 14 coverage points | 36,497 items | under-prediction tracks (1 − coverage) to **3 decimal places**; the mechanism is provable and the data confirms it |
| 50.4% of §8.8's oracle-to-baseline gap is unattainable luck | RouterBench | 401,467 cells | a definitional result confirmed empirically; a clairvoyant per-task oracle scores 0.078 |
| A router trained once decays, and the cause is new-model access | **two independent pools** | 36,497 + 3,541 items | replicated: 99% and 93% attribution to new models, on model generations two years apart |
| Component-wise γ_q/γ_t does not beat one shared γ | 8 seeds, 2 regimes | — | **−0.0005 ± 0.0006** and **+0.0021 ± 0.0010** (SE over 8 seeds). A null result with error bars is the strongest kind |
| Information-aware shrinkage improves ranking concordance | RouterBench | 400 batches | 0.805 → 0.896, large and monotone |

### Tier B — 6 findings

| finding | measurement | what a reviewer will ask |
|---|---|---|
| ~~Uneven coverage costs more than 10× the data buys~~ | **promoted to Tier A** | replicated on a disjoint 13-model pool: **+19.1 points** against the original +12.2. See `RIGOR.md` §3 |
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
- **15 claims are tested across the repository with no multiple-comparison correction.** At
  α = 0.05 and 15 tests, roughly one false positive is expected by construction. The
  per-domain family is now corrected (`RIGOR.md` §2); the other ten claims are not, and
  each rests on a different corpus or split so a single family-wise correction would be the
  wrong instrument.

**Error bars: closed.** Every headline now carries a 2,000-draw bootstrap interval
(`RIGOR.md` §1). The consequential part: the savings figure is **20.2% (95% CI
15.8–24.6%)** — ±4.4 points, not the ±1.4 the cross-validation SE implied, because the two
measure different things. And the quality interval **contains 1.0**, so matching the best
single model is supported and the 98.6% point estimate is not an established shortfall.

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
| Verdicts: supported / not supported / mixed | **7 / 6 / 2** |
| Documented deviations from the spec, each with a measured cost | **6** |
| Tests pinning a property some claim depends on | **63** |

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
   `RESULTS.md` §5 are pinned, so a future change cannot silently reintroduce them.

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
reason. Cost to fix: **~2,000 graded questions × 13 models, tens of dollars**.

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

**4. Three of twenty numbers have error bars.** Quoting a single-split figure to three
decimals implies a precision that was never measured.

**5. 15 claims, no multiple-comparison correction.** Expect ~1 false positive.

**6. n = 1 corpus for the two most novel findings.** Coverage bias (12 points) and
argmax-vs-threshold are both measured on one pool.

**7. Zero comparisons to published routers.** *Closed* — `RIGOR.md` §5 reimplements
cascade (FrugalGPT-style), matrix factorisation (RouteLLM-style) and a no-routing bar,
compared at matched quality. Cascades lose structurally (4.6× our spend at τ=0.8, because
they pay per attempt); **matrix factorisation ties us within 1 point**, which means the
estimator is not where our advantage comes from.

**8. No latency in seconds, anywhere.** The corpus's wall-clock is concurrent. The routed
p95 of 18,195 output tokens is real; converting it to seconds is not.

**9. The release dates are hand-entered.** They shift *when* a model joins the replay and
nothing else — no quality, no price — but the Chutes staleness arm depends on them.

**10. The science domain result is 2.4 SE on 58 items.** *Closed* — it does not survive
Holm–Bonferroni, and neither does anything else in that table.

---

## 6. What would make it publishable, in order

| step | cost | what it unlocks |
|---|---|---|
| Grade the 13 models on the real endpoint | ~2,000 items × 13, tens of dollars | moves 6 findings from Tier C to Tier A; removes the only assumption |
| Replicate coverage bias on a second pool | one afternoon, data already on disk (40 models available) | moves the most novel finding from B to A |
| Add error bars to every headline via k-fold | ~1 hour of compute | fixes watch-list items 4 and 5 |
| Add one published router as a baseline | days | answers the obvious reviewer question |
| One timed run against the endpoint | hours | replaces §4c entirely with measured seconds |
| Report per-domain results with SEs and a correction | minutes | fixes item 10 and the openended overclaim |

The first row is worth more than the other five combined: it converts the entire document
from "what this pool would do if each model behaves like its stand-in" into a measurement.

---

## 7. Verdict

- **As an internal engineering document**: strong. Every number traces to an artifact, 63
  tests pin the claims, and the corrections are documented with their costs.
- **As a systems/empirical paper about routing**: publishable at workshop level after the
  second and third rows of §6 — the coverage-bias and loss-vs-routing findings are novel,
  and the negative results are the interesting kind.
- **As evidence for the product's economics**: not yet. One graded run fixes that, and it
  is the cheapest item on the list.
