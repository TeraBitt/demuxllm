# The graded run — replacing the proxy with measurements

`PUBLISHABILITY.md` graded six headline numbers Tier C for one reason: they describe a
pool nobody had measured. `RIGOR.md` closed eight of ten watch-list items and left that
one open, because it needed spending rather than arithmetic.

This is what the spending bought.

**Method sections are final; §6 carries the results.**

---

## 1. What was actually run

Thirteen Chutes slots, four of them reachable. Fireworks serves the same open-weights
checkpoints and is the endpoint we hold a key for, but only 24 of its 283 library models
are *serverless* — the rest need a dedicated GPU deployment. Every one of the other nine
slot ids was probed directly and returned `404 Model not found, inaccessible, and/or not
deployed`.

| Chutes slot | Fireworks model | had been standing in for | binding it replaces |
|---|---|---|---|
| `deepseek-ai/DeepSeek-V4-Flash-0731-TEE` | `deepseek-v4-flash-0731` | DeepSeek-R1-0528-Qwen3-8B | same family, one size class down |
| `moonshotai/Kimi-K2.6-TEE` | `kimi-k2p6` | kimi-k2-0905 | earlier point release |
| `zai-org/GLM-5.2-TEE` | `glm-5p2` | **gemini-2.5-pro** | family unmatched — capability only |
| `moonshotai/Kimi-K3-TEE` | `kimi-k3` | **gpt-5** | family unmatched — capability only |

The two bindings the catalogue itself flags as weakest are both in this set, which is
the useful accident here: the four slots we could reach include the two whose
assumptions were carrying the most weight.

**What the run does and does not remove.** It replaces *"DeepSeek V4 Flash behaves like
an 8B distill of R1"* with *"the same weights answer the same way on two hosts"*. That is
a far weaker assumption, but it is not zero: a host can differ in quantisation, serving
stack and default sampling. Prices remain the Chutes list, exactly as the architecture
requires — price is read, never fitted.

## 2. Which items, and why those

1,377 items, drawn from the intersection of two constraints:

- **In the dense core.** Every one is an item all thirteen stand-ins answered. That is
  what makes the audit in §6 a *paired* comparison: the same question, the stand-in's
  score beside the real checkpoint's. A run on fresh items would say how the models
  score; this says how wrong the proxy was.
- **Gradeable without a judge.** `mmlupro` and `gpqa` end in `Answer: $LETTER`; `aime`
  and `livemathbench` end in `\boxed{}`. Both settle by exact match against a
  `ground_truth` the corpus ships.

Excluded on purpose:

- **The arenahard family (1,500 items).** Its `ground_truth` field is literally `None` —
  scores come from a pairwise LLM judge. Regrading means reproducing a judge protocol,
  and any drift in that judge lands in the numbers looking exactly like a model
  difference.
- **livecodebench (1,055 items).** Grading it means executing untrusted model output.

Prompts are read from the extracted release, not `data/cache`, which truncates at 4,000
characters — re-serving a truncated prompt asks a different question than the corpus
asked. Items are keyed on `origin_query` and `dataset_name`, matching `build_cache`
exactly; a test pins the two key functions together.

## 3. The grader, and how far it can be trusted

The corpus ships results, not code — there are **zero `.py` files** in the 1.28 GB
archive — so every grader here is a reimplementation, and a reimplementation that is
stricter or looser than the original silently turns a grading difference into an
apparent model difference.

So it was calibrated rather than asserted. Replaying this comparison over **13,312
records the corpus had already graded** gives **99.95% agreement**:

| task | agreement |
|---|---|
| mmlupro | 100.00% |
| aime | 100.00% |
| gpqa | 99.94% |
| livemathbench | 99.56% |

It started at 99.80%. The gap was closed by normalising notation the corpus's symbolic
checker already treats as equal — `336^\circ` vs `336`, `\frac{5}{2}` vs `2.5`,
`\{2,5\}` vs `2,5`, `10^{2^n}` vs `10^{2^{n}}`. The six remaining disagreements are
genuine algebraic equivalences (`8\sqrt{5}-16` vs `8(\sqrt{5}-2)`); doing algebra to
close those would need a symbolic engine, and guessing at it risks calling two different
answers the same. Every rule is pinned by a test, including a test that the rules do
*not* collapse two genuinely different answers.

## 4. Three properties the harness holds

Each one is a mistake this repository has already paid for once.

**The output is dense.** Items are the outer loop; every model answers an item before
the next begins. Any prefix of the run is therefore a complete matrix, so a budget that
stops mid-run cannot reintroduce the uneven coverage that cost twelve points of quality
retention in `RESULTS.md` §4.2.

**A failed call is not a zero.** `RESULTS.md` §4.3 — 470 failed calls scored 0.0 with
zero tokens taught the cost model that some models were free. Transport failures here
are written `observed: false` with no score.

**Truncation is recorded, not scored.** A reasoning model cut off at `max_tokens` has
not answered wrongly; it has not answered. Scoring those 0.0 would penalise exactly the
models that think longest.

## 5. Budget, and what actually bound it

The instruction was 100M tokens. That was not the binding constraint:

| | |
|---|---|
| 100M tokens on this four-model pool would cost | **~$556** |
| credits available | **$37.82** |
| so the real ceiling is | **credits, ~15× tighter** |

Kimi K3 alone accounts for $375 of that hypothetical $556 at list price. The run was
given both ceilings and stops on whichever binds first, on an item boundary.

**On "use the expensive models less" — measured, the ranking inverts.** Kimi K3 lists at
$15/M output, 3.75× GLM 5.2, but it is roughly 4× more token-efficient, so per item it
costs about the same as the mid-tier models and *less* than Kimi K2.6:

| model | mean output tokens | Fireworks $/item |
|---|---|---|
| DeepSeek V4 Flash | ~1,800 | $0.0005 |
| Kimi K3 | ~1,700 | ~$0.025 |
| Kimi K2.6 | ~5,200 | ~$0.021 |
| GLM 5.2 | ~5,600 | ~$0.025 |

Sampling fewer items for one model would also have rebuilt the uneven-coverage bug, so
all four were kept dense and the item count was cut instead.

## 6. Results

**55 items, four slots, 220 measured cells. $13.63 spent of $37.82.**

Read the sample size first: 55 items is small, and it is the *survivors* — items where all
four models produced a gradeable answer. Every interval below is a paired bootstrap on the
per-item difference, which is the only reason anything is resolvable at this n.

### 6a. The stand-ins were wrong about quality — two of four significantly

| slot | stood in by | proxy said | really is | error | 95% CI | resolved |
|---|---|---|---|---|---|---|
| DeepSeek V4 Flash | DeepSeek-R1-0528-Qwen3-8B | 0.818 | 0.818 | +0.000 | [−0.091, +0.091] | no |
| Kimi K2.6 | kimi-k2-0905 | 0.782 | 0.891 | **−0.109** | [−0.200, −0.036] | **yes** |
| Kimi K3 | gpt-5 | 0.891 | 0.873 | +0.018 | [−0.054, +0.091] | no |
| GLM 5.2 | **gemini-2.5-pro** | 0.727 | 0.891 | **−0.164** | [−0.255, −0.073] | **yes** |

Mean |error| **0.073**, max **0.164**. Both resolved errors point the same way: the
stand-in **understated** the real model. The pool's frontier is better than the repository
assumed.

The one genuinely reassuring result is `Kimi K3 ← gpt-5`: the catalogue flags it as a
capability-only match with the family deliberately unmatched, and it lands within 1.8
points. The binding that fails hardest is the other capability-only one.

### 6b. Token behaviour was wrong by more, and that is the expensive half

Quality was roughly right. Token counts were not — and cost is tokens × price, so this is
where the money was.

| slot | proxy tokens/call | real tokens/call | ratio |
|---|---|---|---|
| DeepSeek V4 Flash | 6,063 | 1,527 | **0.25×** — proxy overstated 4× |
| Kimi K2.6 | 1,214 | 4,212 | **3.47×** — proxy understated 3.5× |
| GLM 5.2 | 5,350 | 3,535 | 0.66× |
| Kimi K3 | 1,456 | 1,114 | 0.77× |

Errors of 4× in one direction and 3.5× in the other, on the input to every cost figure in
the package. This is the finding that most deserves to travel: the proxy table was chosen
for *capability* match, and capability is the thing it got approximately right. Nobody
checked whether the stand-in was as *verbose* as the model it stood in for, and verbosity
is what the bill is made of.

### 6c. The shipped router's decisions hold up. Its bill does not.

Arm C — the router as shipped, fitted on stand-in data with every graded item excluded
from training, then asked to route these 55 items and scored against what really happened:

| | as the proxy predicted | as it really is |
|---|---|---|
| router quality | 0.8545 | 0.8545 |
| router $/call | $0.006245 | **$0.008028** |
| best single model | Kimi K3 | Kimi K2.6 |

**The decisions were right; the price was understated by 28.6%.** Quality is identical
because only 22% of traffic reaches a slot we could measure — so this is a floor on the
error, not an estimate of it. If the nine unmeasured slots carry token errors of the same
size as the four measured ones, the understatement is larger.

The best-single model also changes, which matters more than it looks: that is the baseline
`BUSINESS_REVIEW.md` §3 shows the entire pricing model is quoted against.

### 6d. Routing the four-model pool is worth nothing

Best single is Kimi K2.6. Across the dial the router never beats it by more than 0.3%, and
between λ=0.1 and λ=0.2 it is **15.8% and 10.4% worse** while holding 105.9% of quality.

That is the expected result, not a failure: four models, three of them expensive, on 19
held-out items. A pool needs cheap models that are *sometimes right* for routing to have
anything to sell, and the six cheap slots in the real catalogue are exactly the ones
Fireworks would not serve. Read §6d as "this sub-pool cannot demonstrate routing value",
not "routing has none".

### 6e. What the numbers do not cover

- **n = 55**, on four of nine benchmarks and four of thirteen slots.
- **The dense set is 0.083 easier** than the items attempted, measured on the stand-ins
  which answered all of them. 82 cells were dropped for truncation, and truncation is not
  random — it removes what the verbose models found hardest. Accuracies here are therefore
  high (0.82–0.89) and should not be read as pool-level accuracy. The audit in §6a is
  unaffected: it is paired on identical items, so the selection cancels between the two
  sides of every comparison.
- **arenahard and livecodebench are absent**, which is 65% of the dense core.
- The residual assumption is **host, not model** — same weights, Fireworks rather than
  Chutes.

## 7. Reproducing

```bash
make grading-set                      # free, offline: selects the 1,377 items
FIREWORKS_API_KEY=... make grade      # spends money; resumable, hard budget ceilings
make grade-export                     # proxy audit + label matrix
.venv/bin/python scripts/analyze_graded.py   # routing over the real pool
```

The ledger at `artifacts/grading/cells.jsonl` is append-only and re-reading it is how a
re-run resumes, so no call is ever paid for twice.

### 6f. The engine, trained on our own outputs only

`scripts/train_real.py` fits the full engine on the 55×4 matrix with no stand-in anywhere
in the pipeline — calibrate the dial on this pool, size the ridge by held-out savings, fit,
ship a loadable artifact, score over 12 random splits.

**Calibrated to λ_c = 1.6, ridge = 10.0.** Note how far that is from the 0.05 inherited
from RouterBench and the 0.2 calibrated on the proxy pool. `RESULTS.md` §4.1 says λ_c
weights a cost *ratio* and ratios differ by pool; this pool's ratio spans 39×, and the dial
moves accordingly. Inheriting it would have been the same mistake for the third time.

| over 12 splits | mean ± sd |
|---|---|
| savings vs best single | **−0.32% ± 0.91%** |
| quality vs best single | 1.0049 ± 0.017 |
| router quality | 0.8421 ± 0.0744 |
| oracle quality | 0.9474 ± 0.0317 |

**Routing this pool is worth nothing, and the reason is worth knowing.** DeepSeek V4 Flash
was best-single in **12 of 12** splits, and the trained router sends it **99.1%** of
traffic. It is not a compromise — it is 0.818 accurate against the best model's 0.891, and
it costs **$0.00045/call against $0.0175**. Buying those 7 points of accuracy costs **39×**.
No cost-aware policy will ever do that, and the router correctly declines to.

The headroom is real but unreachable: a per-item oracle scores 0.947 against the router's
0.842. Ten points sit on the table and the router captures none of them, for exactly the
reason `RESULTS.md` §4b already identified on the proxy pool — the gap between model
averages swamps the per-item prediction spread, so a cheap model can never be *selectively*
beaten. Measuring the real models did not change that diagnosis. It sharpened it.

**Caveat that cuts against this specific result:** the dense set is 0.083 easier than the
items attempted (§6e), and easy items are exactly where a cheap model closes the gap. Some
of DeepSeek V4 Flash's dominance is the selection, not the model.

### 6g. Two defects the engine work exposed

Both were silent, and both would have shipped.

**The artifact was indexed by the catalogue, not by its own pool.** `save_artifact` wrote
`price_in`/`price_out` straight off `CHUTES_CATALOG`, so a four-model router shipped with
**thirteen** prices. Nothing raises on load — a gateway just pairs column 1 with slot 1's
price and bills the wrong model. Now resolved through `lm.model_ids`, with the lengths
asserted before the write and a test pinning it.

**The artifact could not compute its own inputs.** Weights were saved without the feature
map, and φ's rank depends on how many items it was fitted on — so a reload produced a
48-column weight matrix and 64-column features, surfacing as a shape error inside a request
path rather than at load. φ and the fitted config now travel with the weights, and
`load_artifact` refuses an artifact that lacks them rather than failing later.

The engine now cold-loads from a single 542 KB file and routes an arbitrary prompt:

```python
router, fm, pool, ids = load_artifact("router_real.npz")
choice = router.decide(fm.transform([prompt]), pool).choice
```
