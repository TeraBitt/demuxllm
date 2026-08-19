# Business review — can we do it?

Companion to `PM_UPDATE.md`. That document asks for one decision. This one checks the
technicalities behind it and behind the two larger questions nobody has asked yet.

Every number below was re-derived from the repository, not copied from the other
documents. Where I contradict `PM_UPDATE.md`, the working is shown.

---

## 1. The verdict, in one table

There are three different "can we do it" questions hiding behind one phrase. They have
different answers.

| # | the question | answer |
|---|---|---|
| 1 | Can we grade our 13 models on a real endpoint? | **Four of thirteen — done. The other nine, no**, and the blocker is access, not money |
| 2 | Can we publish the numbers we have? | **Partly** — methodology yes, product economics no, and now for a worse reason |
| 3 | Can we sell this at the pricing on the site? | **No** — the pricing arithmetic does not survive our own honest baseline |

**Since the first draft, row 1 has been run.** $13.63 bought 55 items across the four
slots a real endpoint would serve, and the result changes what row 2 means. The problem
was never that the numbers were unverified. It is that the verified part is wrong in the
**cost** lane — the one the product sells — by up to 4× on token counts, while the quality
lane it was chosen for is roughly right. Details in §5c; method in `GRADED_RUN.md`.

**Item 3 is the real blocker, and it is not on any roadmap in this repository.** It is not
a data problem and no amount of inference spend fixes it. It should be settled before we
spend a dollar on item 1, because it changes which number we are buying.

---

## 2. What is genuinely done

Stated first, because the rest of this document is critical and the engineering here is
not the weak part.

- **101 tests pass** (verified: `pytest tests/ -q` → `101 passed`), 28 of them added with the
  grading harness and the engine artifact.
- **All 13 catalogue slots are real.** I re-fetched `llm.chutes.ai/v1/models` live during
  this review: 14 chat models listed, **13 of 13** of our slots present and priced. The
  pool is not aspirational, the endpoint is public, and the price list needs no key.
- **The proxy binding is isolated in one table** (`catalog.CHUTES_PROXY`) with a
  `check_proxy_table()` guard, and every artifact carries `proxy_backed: true`. The claim
  that downstream numbers recompute from one edit is structurally true.
- **The disclosure discipline on the dense core is good.** `measured.ts` deliberately
  exports the 9-task dense core rather than the 27-task corpus list, with a comment saying
  why. That is the kind of thing that gets caught in diligence, and it was handled.

---

## 3. Blocker — the pricing model contradicts our own analysis

This is the finding that matters most and it is new.

The site sells **"20% of what we save you"**, and the FAQ defines the baseline:

> *"We show you what the same questions would have cost on the biggest model in the pool,
> next to what you actually paid."* — `src/lib/data.ts:293`

So we bill against **GLM 5.2**, the frontier slot. `PM_UPDATE.md` §2 already says leading
with that baseline is indefensible, because GLM 5.2 is beaten on **both** price and quality
by Qwen3 235B Thinking. What nobody carried through is what that does to the invoice.

Normalising on routed spend = 1.000, using the measured savings in `measured.ts`
(79.57% vs frontier, 19.5% vs best single):

| | cost |
|---|---|
| routed spend (what the customer pays Chutes through us) | 1.000 |
| GLM 5.2 baseline — what we bill against | 4.895 |
| Qwen3 235B Thinking — what a customer could just *pick* | 1.242 |

| billing baseline | our fee | customer all-in | vs just picking the best single model |
|---|---|---|---|
| frontier (what the FAQ describes) | 0.779 | **1.779** | **+43.2% worse off** |
| best-value single (the honest one) | 0.048 | 1.048 | −15.6% better off |

**A customer on our advertised pricing pays 43% more than if they had simply sent
everything to Qwen3 235B Thinking.** Our fee (0.779) is more than three times the entire
saving that routing actually creates (0.242).

The break-even fee against the frontier baseline is **6.2%** — and only **4.8%** at the low
end of the bootstrap CI. Any fee above that and the customer is paying us to be worse off.

Three consequences, none optional:

1. **20% is not a viable rate against the frontier baseline.** The defensible ceiling is
   ~6%, and it should be quoted against the CI's low end, not its point estimate.
2. **Billing against the honest baseline works but is a much smaller business.** At 20% of
   the *real* saving, revenue is 4.8% of routed spend — $39k per $1M of customer baseline
   spend, against the $159k the current page implies. That is a different company.
3. **This is the churn mechanism.** The first technical customer who benchmarks
   Qwen3 235B Thinking on their own traffic cancels, and they are right to. We would be
   charging for a gap we did not create.

The product still has a real value story — price reactivity, onboarding new models, the
decay result. It is just not worth 20% of a baseline nobody should be using.

---

## 4. Blocker — there is no product to sell yet

`/docs` advertises a drop-in OpenAI-compatible endpoint and two SDKs:

```
base_url="https://api.demuxllm.com/v1"     # src/lib/data.ts:565
pip install demuxllm  /  npm i demuxllm    # src/lib/data.ts:733-734
```

**None of it exists in this repository.** `find src/app -name route.ts` returns nothing —
there are zero API routes. What works today is the marketing site plus a browser-side BYOK
dashboard that calls Chutes directly from the user's own key.

Everything a paid gateway needs is absent: auth and key issuance, request proxying,
metering, the savings-attribution accounting the entire pricing model is defined in terms
of, invoicing, and rate limiting. That is the bulk of the remaining engineering, and none
of it is in the roadmap in `PM_UPDATE.md` §8, which is entirely research tasks.

This does not make the work wrong — it makes the sequencing wrong. We are polishing
evidence for a product that cannot yet take a request.

---

## 5. The graded run — yes, but recost and rescope it

`PM_UPDATE.md` §7 asks for **$20–150 and an afternoon**, with **no code changes**. The
first two are wrong and the third is only half true.

### 5a. What it actually costs

Computed from the corpus's own **measured** token counts on the dense core, priced at the
**live** Chutes list:

| task group | items | grading method | inference cost (×13 models) |
|---|---|---|---|
| mmlupro, gpqa, aime, livemathbench | 1,377 | exact match | **$133** |
| livecodebench | 1,055 | sandboxed execution | **$207** |
| arenahard ×4 | 1,500 | LLM judge | **$164** |
| **full dense core** | **3,932** | | **$504** |

At the 2,000 items §7 proposes: **$256**. Not $20–150.

The driver is that our pool is reasoning-heavy — mean **4,135 output tokens per cell**, and
26,000 calls totalling ~107M output tokens at 2,000 items. Kimi K3 alone is $0.054/item.

**And the judge is missing from the estimate entirely.** Arena-Hard is graded pairwise by an
LLM, so 1,500 items × 13 models = **19,500 judge calls** at ~6,300 input tokens each:

| judge model | added cost |
|---|---|
| Kimi K3 | $544 |
| GLM 5.2 | $200 |
| Qwen3 235B Thinking | $51 |

**Realistic all-in for a full de-proxy: $550–$1,050.** Still cheap in absolute terms — the
point is not that we cannot afford it, it is that a number quoted 5–50× low is the kind of
thing that erodes trust in the rest of the estimates.

### 5b. Why it is not an afternoon, and not "no code changes"

The claim that everything recomputes from one table is true *downstream*. But nothing in
this repository could **produce** a graded matrix. The only HTTP calls in the whole backend
were the public price list and the dataset downloader — no chat client, no concurrency or
retry layer, no token accounting, and **no graders**.

*Since built: `scripts/grade_fireworks.py` and its graders now exist, calibrated to 99.95%
agreement against 13,312 records the corpus had already graded, with 25 tests. That was
roughly a day, not an afternoon, and it covers only the exact-match third of the set — the
two harder thirds below are still unbuilt.*

And the graders cannot be borrowed. The 1.28 GB corpus archive contains **zero `.py`
files** — it ships results, not the code that produced them. So every grader is a
reimplementation:

| group | what has to be built | risk |
|---|---|---|
| exact match (35%) | answer extraction, `\boxed{}` parsing, MC normalisation | low |
| code execution (27%) | sandboxed runner, test harness, timeouts | medium — this is real infrastructure |
| LLM judge (38%) | Arena-Hard protocol, baseline answers, judge prompt | **high — see below** |

Two technicalities that decide whether the run is even *comparable*:

1. **Arena-Hard items have no ground truth.** I checked a raw record: `ground_truth` is
   literally `'None'` and the score comes from a judge. To regrade we must reproduce the
   baseline answers and the judge protocol. A judge that is stricter or looser than
   LLMRouterBench's produces numbers that **cannot be compared to the proxy baseline** —
   which destroys the "everything recomputes and we see what changed" story for 38% of the
   set.
2. **The cache truncates prompts to 4,000 chars.** Re-serving must read the raw tarball,
   not `data/cache/`. Minor, but it is a code change on day one.

Decoding parameters (temperature, max_tokens) also have to match the corpus's, or the
token counts our cost model is fitted on stop being the token counts we observe.

### 5c. What the graded run actually found — and why it is worse news than "unverified"

$13.63 spent. 55 items, four slots, paired against the same items the stand-ins answered.
Nine slots — including **all five Qwen slots** — are not available serverless on any
endpoint we hold a key for, so they stay proxy-backed. Full caveats in `GRADED_RUN.md` §6e;
n = 55 and the sample skews easy.

**Quality: roughly right.** Mean absolute error 0.073. Two of four resolve, both
*understating* the real model — GLM 5.2 by 16.4 points, Kimi K2.6 by 10.9.

**Cost: badly wrong.** Cost is tokens × price, and the token counts are off by up to 4× in
both directions:

| slot | proxy tokens/call | real tokens/call | ratio |
|---|---|---|---|
| DeepSeek V4 Flash | 6,063 | 1,527 | **0.25×** |
| Kimi K2.6 | 1,214 | 4,212 | **3.47×** |
| GLM 5.2 | 5,350 | 3,535 | 0.66× |
| Kimi K3 | 1,456 | 1,114 | 0.77× |

The stand-ins were picked for capability match, and capability is what they got right.
Nobody checked whether a stand-in was as *verbose* as the model it replaced — and verbosity
is what the bill is made of.

**What it does to the shipped router.** Fitted on stand-in data with every graded item held
out, then scored on what really happened: the routing decisions are unchanged (quality
0.8545 either way), but the realised bill is **28.6% higher than the model predicts**. Only
22% of traffic reaches a measured slot, so that is a floor.

**Three commercial consequences, in order of how much they cost us.**

1. **The savings claim is measured against a cost model that is 28.6% optimistic** on the
   third of the pool we can check. Savings are a *difference* of two costs, so an error in
   the cost lane goes straight into the headline. Nothing on the website should quote a
   savings figure to one decimal place until the nine remaining slots are measured.
2. **The best-single baseline moves when real data is used** — from Kimi K3 to Kimi K2.6 in
   the arm-C test, and from DeepSeek V4 Flash to Qwen3 235B Thinking in the retrain. That is
   the baseline §3 shows the entire pricing model is quoted against, and it is not stable
   under better data.
3. **"Grade the endpoint and six numbers become measurements" was wrong.** Four slots were
   graded and *nothing* moved to Tier A. The remaining nine are blocked on access rather
   than budget, and no amount of spending fixes that this quarter.

### 5d. What I would actually authorise

Staged, with stage 0 now run — and it did not cost what this table predicted, because it
could only reach 4 of 13 slots:

| stage | scope | cost | status |
|---|---|---|---|
| **0** | exact-match — mmlupro, gpqa, aime, livemathbench | est. $133 for 13 slots | **run for 4 slots: $13.63, 55 items.** The other 9 are not serverless anywhere we hold a key |
| 1 | + livecodebench | $207 | not started — needs a sandbox runner |
| 2 | + arenahard | $164 + $51–544 | not started — needs the judge protocol, carries comparability risk |

**The caveat stage 0 was supposed to carry turned out to be the smaller problem.** The
warning here was that a knowledge-and-maths subset is a different mix from the full core,
so the headline would move. True, and still true. But the run surfaced something this table
did not anticipate: the cost lane is wrong by up to 4× (§5c), which affects every figure
regardless of which items are in the mix.

**The binding constraint is no longer money.** Nine slots — every Qwen slot among them —
have no serverless endpoint we can reach. Thirteen Fireworks model-id variants were probed;
all returned `404 not deployed`. Stage 1 and 2 buy breadth on four columns we have already
bounded. Getting the other nine columns at all is worth more than either.

Onboarding economics are fine, incidentally: 1,000 probe items for one new model costs
**$0.12–$54** depending on the model. The "new models within 24 hours" promise is
affordable. It just has no harness behind it.

---

## 6. Claims on the public site that need changing before launch

These are live on a public marketing site today.

| where | claim | problem |
|---|---|---|
| Hero badge | "Re-tested against every model, every day" | No such pipeline exists. Present tense, operational, false |
| Hero stat 1 | "80% cut against one strong model" | The frontier baseline `PM_UPDATE.md` §2 says not to lead with — and it leads the home page. No proxy caveat anywhere on `/` |
| Hero stats 3–4 | "8ms added to a call", "24h to add a new model" | Targets, not measurements. `data.ts` says so in a code comment; **the page does not tell the visitor** |
| FAQ | "We test it against thousands of questions the same day it launches" | No harness. See §5b |
| FAQ | billing baseline = "the biggest model in the pool" | See §3 |
| `measured.ts` | exports `savingsSe: 0.0137`, rendered as "±1.4%" | `RIGOR.md` §1 says quote the bootstrap CI, **±4.4 points**. The exporter carries no CI fields at all |

The last one is a code gap, not staleness — I re-ran `export_measured.py` and the output is
byte-identical to the committed file. `scripts/export_measured.py` needs to learn about
`16_bootstrap.json`; re-running it will not help.

Credit where due: `/benchmark` does disclose the stand-ins in two places. The problem is
that the home page carries the biggest number with none of the caveats, and most visitors
never reach `/benchmark`.

---

## 6b. Competitors — the algorithm, and then the business

Two different competitive questions, and the repository has only ever answered the first.

### 6b.i The algorithms, measured on our own items

`RIGOR.md` §5 reimplements six published families against the same held-out items, the
same prices and the same feature map, each swept across its own dial. Only points that
save money at ≥95% quality count. Refreshed with the current run:

| family | on one split | **over 8 splits** | beats us in | verdict |
|---|---|---|---|---|
| matrix factorisation (RouteLLM-style) | +3.6 pts | **−6.6 ± 7.8 pts** | 2 of 7 | **too noisy to call either way** |
| k-NN retrieval, k=32 | −3.7 pts | **−0.1 ± 18.4 pts** | 2 of 8 | too noisy to call either way |
| cascade (FrugalGPT-style) | no useful point | **no useful point** | 0 of 8 | **loses, structurally** |
| HybridLLM-style | no useful point | **no useful point** | 0 of 8 | **loses, structurally** |

> **Corrected.** This table previously reported "matrix factorisation beats us by 3.6
> points" as a finding. That was a single train/test split. Across eight it is 6.6 points
> *behind* us on average and ahead on two, and the split originally reported was one of
> the two favourable ones. `PUBLISHING.md` §3.

The commercially relevant readings:

- **No published method reliably beats our estimator, and we cannot claim ours reliably
  beats theirs either.** A rank-8 matrix completion and a parameter-free nearest-neighbour
  rule both land in the same neighbourhood across eight splits, with spreads far wider
  than the gaps. That bounds what the ridge machinery is contributing, and the bound is
  small — which is the same conclusion, reached honestly.
- **Cascades lose structurally.** At τ=0.8 a cascade makes 6.9 attempts per answer and
  **58% of its spend is on answers it discards**. That is a real moat against one specific
  competitor design, and worth saying out loud.

### 6b.ii The businesses — and this is where the problem is

The algorithmic comparison is the one we ran. The commercial one we never did, and it is
much worse. Figures below are from public pricing as of August 2026 and will move.

| | what they charge | routing itself |
|---|---|---|
| **OpenRouter** | no markup on inference; **5.5%** on card credit purchases ($0.80 min); BYOK free to **$25k/mo**, then 5% | **free** — the Auto Router exposes a cost/quality dial at **no surcharge** |
| **Not Diamond** | undisclosed; "a small fixed fee per million tokens, cheaper than the cheapest LLM" | metered, small |
| **Martian** | passthrough + ~5.5%; ~$1.3B valuation reported | bundled |
| **LiteLLM / RouteLLM** | open source | free |
| **DemuxLLM (proposed)** | **20% of savings**, billed against the frontier model | the entire product |

**The incumbent gives routing away.** OpenRouter monetises payments and aggregation and
treats the router as an acquisition feature. We propose to charge for the router itself,
which is the one component our own benchmark says is not differentiated.

What that does to a customer spending $100k/year on one strong model:

| option | fee | customer pays | vs doing nothing |
|---|---|---|---|
| do nothing | $0 | $100,000 | — |
| **OpenRouter auto-router, BYOK** | $0 | **$20,430** | −79.6% |
| **OpenRouter auto-router, card credits** | $1,124 | **$21,554** | −78.4% |
| pick the best-value model yourself | $0 | $25,602 | −74.4% |
| **DemuxLLM @ 20% of savings vs frontier** | **$15,914** | **$36,344** | −63.7% |
| DemuxLLM @ 20% of savings vs best single | $1,034 | $21,464 | −78.5% |

**On our advertised pricing the customer pays 69% more than they would on OpenRouter's
free auto-router.** As a take rate on routed spend:

| | take rate |
|---|---|
| OpenRouter, BYOK under $25k/mo | 0% |
| OpenRouter, card credits | 5.5% |
| **DemuxLLM, billed against the frontier** | **77.9%** |
| DemuxLLM, billed against best single | 5.1% |

Two conclusions, and the second is the constructive one:

1. **77.9% is not a price, it is a mispricing.** It is 14× the incumbent's take rate for a
   feature the incumbent bundles free, sold on a savings figure our own §3 shows is mostly
   not attributable to routing.
2. **Billing 20% of the *honest* saving lands at 5.1% — within noise of OpenRouter's
   5.5%.** That is a real business at a defensible rate. It is also a commodity rate, which
   means the differentiator has to be something other than the router: the live price lane,
   the onboarding evidence, the decay result. Those are the assets §3 already identified,
   and they are the ones nobody is pricing.

**What we cannot claim against these competitors.** Our four-model graded pool routes to a
single model 99.1% of the time and saves −0.3% ± 0.9% (`GRADED_RUN.md` §6f). We have no
measured evidence that our routing beats anyone's on real endpoints — only on stand-ins,
where the comparison is too noisy to resolve in either direction (§6b.i).

---

## 7. What I would do, in order

1. **Decide the pricing model — and the ceiling is now known.** §6b prices the market: the
   incumbent bundles routing free and takes 0–5.5%. Billing 20% of the *honest* saving puts
   us at 5.1%, which is viable and commodity; billing against the frontier puts us at 77.9%,
   which loses to a free competitor by 69%. *No cost, one meeting.*
2. **Fix the six site claims in §6, and stop quoting savings to one decimal.** §5c shows
   the cost lane is 28.6% optimistic where we can check it. *Hours.*
3. **Get an endpoint that serves the other nine slots.** This is now the binding
   constraint and it is commercial, not technical: a working Chutes key, or a provider
   that serves the Qwen slots serverless. Until then two thirds of the pool is unmeasured
   and unmeasurable. *Days, and it is someone's phone call, not an engineering task.*
4. **Re-measure token counts before quality.** §5c says verbosity is where the error is.
   Token counts are far cheaper to measure than accuracy — a handful of calls per model,
   no grader, no ground truth — so this is the highest value per dollar left on the list.
   *~$5 and an afternoon, once row 3 lands.*
5. **Scope the gateway.** Auth, metering, savings attribution, billing. This is the product
   and it is not started. *Weeks — needs its own estimate.*
6. Extend the graded set past 55 items and onto arenahard/livecodebench (65% of the core),
   and the research roadmap in `PM_UPDATE.md` §8.

## 8. So — can we do it?

**Technically, partly — and the part we could not do is the part that matters.** The
engine works, the tests pass (98 of them), the evidence pipeline is unusually honest, and
the grading harness now exists and is calibrated to 99.95% against the corpus's own
verdicts. But only 4 of 13 slots are reachable on any endpoint we hold a key for, and the
$13.63 that bought those four found the cost model wrong by up to 4× on token counts. The
remaining nine are blocked on **access, not budget** — spending more money does not fix
it.

**Commercially, not as currently designed.** The 20%-of-savings pricing billed against the
frontier model makes customers 43% worse off than a single well-chosen model, and there is
no gateway to bill through. Both are fixable, neither is a research problem, and neither is
on the roadmap.

The honest summary is the one `PM_UPDATE.md` §5 already reached and then did not follow to
its conclusion: **the algorithm is not the advantage, so the business cannot be priced as
if it were.** The graded run adds a second: **the evidence base is not the advantage
either, until the cost lane is measured rather than assumed.** And the market adds a third:
**the incumbent already gives the router away**, so whatever we charge for has to be the
thing they are not doing — reacting to price, onboarding new models, and proving it. Both are fixable. Neither is
fixed by writing more analysis, which is what this repository is currently good at.
