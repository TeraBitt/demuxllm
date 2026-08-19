# Update for the PM — the router, step by step

A walkthrough, in the order I'd say it out loud. Roughly 15 minutes with questions.
Every number is measured and traceable to a file; nothing is projected.

**If you read one line:** the engine is done and independently sanity-checked, the
evidence behind the savings claim is borrowed rather than owned, and closing that costs
tens of dollars and an afternoon. That is the only real blocker, and I need one decision
from you to unblock it (§7).

---

## Step 1 — What I set out to do, and what I found instead

**The ask:** train the backend on our 13 Chutes models, so the product's numbers come from
the models we actually serve.

**The problem I hit immediately:** no public benchmark grades our exact models, and the
Chutes API key in the repo is empty. So there was nothing to train on.

**What I did about it:** found a 1.2 GB benchmark already sitting unused on disk
(LLMRouterBench) with real graded results for 40 current models across 27 tasks. I bound
each of our 13 slots to a measured stand-in — 11 of 13 are open-weight models of the same
kind Chutes serves, and one is the *identical* checkpoint.

**What that means for you:** every quality number we now publish is real data about a real
model — just not, yet, about *our* endpoint. Everything downstream recomputes automatically
once we grade the real thing.

---

## Step 2 — The headline, and why there are two of them

| against | cheaper by | quality kept |
|---|---|---|
| the strongest model (what teams do today) | **79.6%** | 97.8% |
| the *best-value* single model | **20.2%** (95% CI 15.8–24.6%) | 99.4% |

**Lead with the second number.** The first one is technically true and I'd rather not be
caught leaning on it: our strongest model (GLM 5.2) is beaten outright on both price *and*
quality by Qwen3 235B Thinking. Quoting savings against a model that another single model
already beats inflates our figure with a gap we had nothing to do with.

The honest pitch is stronger than it sounds: *"we find the best model for you, and then
beat it by 20%."* Most teams never find it.

One good surprise from the statistics: the quality confidence interval **includes 100%**,
so "we match the best single model's quality" is supported by the data. We are not
trading quality away.

---

## Step 3 — The strongest thing we have is not the savings

It's the decay result, and it's now measured **twice on two disjoint sets of models**:

| | 2023 models | our current pool |
|---|---|---|
| a router built once, after 26 weeks | +0.01 → **−1.01** | +0.13 → **−1.06** |
| falls below "no routing at all" at | week 5 | **week 9** |
| share of the damage from *new models arriving* | **99%** | **93%** |

Read that last row twice. It says the expensive part is **not** keeping evaluations fresh
— it's being able to reach models that shipped after you built the thing. That inverts
what our own product docs assumed, and it's the clearest argument for why this is a
service and not a one-off script.

The 2023 half of that result uses no stand-ins at all. It is the one headline nobody can
poke a hole in.

---

## Step 4 — Five things that were wrong, and are now fixed

I'd rather you hear these from me. Each was found by measuring something we had assumed.

1. **Our operating point was set from the wrong benchmark.** Carried over unexamined, it
   made the router spend **84% more** than doing nothing. Now calibrated per pool.
2. **Ten times more training data made the router worse** — by 12 points. Uneven coverage
   across models breaks the comparison. (Replicated since; see step 5.)
3. **470 "measurements" were failed API calls** — zero tokens, zero score. They taught the
   cost model that some models were free.
4. **A "dominant model" in the pool** caps what routing can be worth. That's why the honest
   number is 20% and not 80%.
5. **Sizing the model on prediction accuracy picks the wrong size.** Loss says d=64, money
   says d=28 — a 5× bigger artifact that routes slightly worse.

None of these came from a bigger model. All five came from checking the data. Each is now
a test that fails if it comes back.

---

## Step 5 — Then I tried to break my own results

This is the part I'd want a PM to push on, so I did it first. It found three things I had
wrong.

- **I claimed our savings were a conservative lower bound** because we test on hard
  questions. Measured: they're **flat** (18.8%–22.2%) across the whole easy/hard mix. The
  honest version is better — the number is *robust*, not conservative.
- **I claimed one of five per-domain results was significant.** Corrected for testing five
  things at once: **zero of five** survive. We should not claim we're better or worse at
  any particular domain.
- **I claimed no published competitor beat us, then claimed one did. Both were too
  strong.** After implementing six published approaches and sweeping each one's settings,
  a RouteLLM-style method came out 3.6 points ahead in the aggressive-savings region — on
  **one** train/test split. Re-run on eight, it is **6.6 points behind us on average** and
  ahead on two. The split I first reported was one of the two favourable ones.

The commercially relevant version, stated at the strength the evidence supports:
**our routing algorithm is probably not our advantage, but no published method reliably
beats it either.** A rank-8 matrix method and even a parameter-free nearest-neighbour rule
land in the same neighbourhood, which says the estimator is not doing the heavy lifting.
Our advantage is the calibration, the coverage fix, the live pricing and the evidence
base — and those would improve their algorithm too. We should not pitch the algorithm, and
we should not concede it either.

The good news in the same table is the part that *did* hold up across all eight splits:
two well-known approaches (cascades, HybridLLM) have **no useful setting at all** on our
pool, in **8 of 8**. Cascades pay for every attempt — at matched quality one spends
**4.6× what we do**. That result is structural rather than statistical, which is why it
does not move with the split.

---

## Step 6 — What's built and shipping

- **The engine**: 36 KB, trains in under a second, no GPU. 73 tests.
- **Live pricing**: we read Chutes prices at request time, never bake them in. Tested by
  hashing the model before and after a price change — byte-identical. When we simulated a
  4× price rise it held the bill at **$7.61 against $20.75** for a system that couldn't
  react. That's a real differentiator and no competitor's *algorithm* gives it to them.
- **Latency**: I could not measure real latency — the benchmark's timings are from
  concurrent runs, so they're throughput, not response time. I did not ship a fake number.
  We route on *measured output length* instead, and turning that on cuts our p95 by **52%
  while savings go up**, because shorter answers are both faster and cheaper.
- **The website now only quotes measured numbers.** The decay chart was illustrative; it's
  real now. Per-model quality and traffic were invented; they're measured. The only
  invented column left is latency, and it's labelled as such in the code.

---

## Step 7 — What I need from you

**One decision, and it's cheap.** To grade our 13 models on the real Chutes endpoint I
need a working API key and sign-off on roughly **$20–150** of inference (~2,000 questions
× 13 models; the range is because reasoning models bill for thinking tokens).

That single run:
- converts six headline numbers from "if each model behaves like its stand-in" into
  measurements of our product,
- lets us publish the benchmark, which is the marketing asset,
- and needs **no code changes** — the mapping lives in one table and everything reads
  through it.

It's the highest-value item on the list by a wide margin, and the cheapest.

Second, smaller ask: **is latency a product requirement?** If yes I need one timed run
against the endpoint. If it's not on the roadmap, I'll leave it as-is and stop paying it
attention.

---

## Step 8 — What I'd do next, in order

| # | what | why | cost |
|---|---|---|---|
| 1 | Grade the real endpoint | removes the only assumption in the whole system | ~$20–150, one afternoon |
| 2 | Better question encoder | the real ceiling — see below | ~1 week |
| ~~3~~ | ~~Adopt or hybridise the matrix method~~ **dropped** | it does not beat us — that was one split; over eight it is 6.6 points behind | — |
| 4 | Timed latency run | the last invented column | hours, needs #1's key |
| 5 | Learn from live traffic | the asset that compounds | needs customers |

**On #2 — where the remaining money is.** Two of our cheapest models currently get *zero*
traffic. I nearly recommended dropping them. Then I measured what a perfect router would
do: it sends them **30.8% of all requests**. They're not bad models, we just can't tell
*when* they'll be right. The gap between model averages (0.62) is four times our per-item
prediction spread (0.16), so a cheap model can never win. Fixing the question encoder is
what unlocks that 30.8%, and it's the single biggest piece of value left on the table.

I also tested the rule our marketing describes — *"the cheapest model that will get this
right"* — and it performs **worse** than what we ship. Worth knowing before it appears on
a slide.

---

## Step 9 — Risks, stated plainly

| risk | how bad | mitigation |
|---|---|---|
| Savings claims rest on stand-in models | **high** — a technical customer will ask | step 7, item 1 |
| Our algorithm is not differentiated | **medium** — a competitor can match it | pitch the evidence and price lane, not the algorithm |
| One model dominating the pool caps the upside | medium | re-check whenever Chutes changes prices; it's automated |
| The 20% number is ±4.4 points, not ±1.4 | low | quote the range |
| Two models earn no traffic today | low | keep them; the fix is the encoder, not the catalogue |

---

## Where to look

| you want | open |
|---|---|
| the numbers and what they mean | `backend/RESULTS.md` |
| how much weight each number bears | `backend/PUBLISHABILITY.md` |
| the statistics and the corrections | `backend/RIGOR.md` |
| to run it yourself | `cd backend && make chutes` (15 s) |
| the analysis with charts | `backend/notebooks/09` and `10` |
