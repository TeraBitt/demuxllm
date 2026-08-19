# Rigor — closing the watch-list

`PUBLISHABILITY.md` ended with ten things to keep in mind and a six-row fix list. This is
what happened when they were actioned. Notebook `10_rigor.ipynb` runs all of it; the
artifacts are `chutes/16_bootstrap.json` through `chutes/19_baselines.json`.

**Three of the corrections contradict claims made earlier in this repository**, including
one in an earlier draft of this file. All three are fixed at source rather than noted here
and left standing:

1. Savings are **flat** across workload mix, not a conservative lower bound (§4).
2. **Zero** per-domain differences survive correction, not "one on the line" (§2).
3. A published baseline **does** beat us in the aggressive-savings region (§5) — an
   earlier run with fewer families and no dial sweep concluded nothing did.

That third one is the reason to sweep dials rather than compare operating points.

> **Update — every row here has since been re-run at n > 1, and two of them changed.**
> See `PUBLISHING.md`. Correction 3 above **does not survive**: it was measured on one
> split, and across eight the same family loses to us by 6.6 points on average and wins
> on two. §5 below is corrected in place. The coverage-bias replication in §3 got
> *stronger* — the effect is now shown to be caused by the coverage rather than by the
> extra data, and to be larger than reported here. Everything else in this document
> stands.

---

## Scorecard

| # | watch-list item | status | what it cost |
|---|---|---|---|
| 1 | Six headline numbers describe a pool nobody measured | **open** | needs a working key + ~tens of dollars |
| 2 | One model dominates the pool, capping everything | **quantified** | — |
| 3 | Eval set is 9 hard benchmarks, not product traffic | **measured — my claim was wrong** | 2 s |
| 4 | Only 3 of ~20 numbers had error bars | **closed** — k-fold added in `PUBLISHING.md` §2, and the two instruments disagree about parity | 2,000-draw bootstrap, 1 s |
| 5 | 15 claims, no multiple-comparison correction | **closed for the domain family**; the whole repository is audited in `PUBLISHING.md` §4 | 1 s |
| 6 | n = 1 corpus for the two most novel findings | **closed for the biggest one** — and see `PUBLISHING.md` §1, where it becomes causal | 2 s |
| 7 | Zero comparisons to published routers | **closed — the "we lose one" verdict is retracted, see §5** | 6 families, dials swept, 2 s |
| 8 | No latency in seconds | **open** | needs a timed endpoint |
| 9 | Release dates hand-entered | **acknowledged, bounded** | — |
| 10 | Science result was 2.4 SE on 58 items | **closed — it does not survive** | included in #5 |

Eight of ten closed or bounded. The two that remain both need spending, not arithmetic.

---

## 1. Error bars on every headline (item 4)

2,000 percentile bootstrap draws, resampling **items, not cells** — the same prompt
answered by thirteen models is one observation, and resampling cells would treat it as
thirteen and shrink every interval by roughly √13.

| quantity | mean | 95% CI | width |
|---|---|---|---|
| savings vs frontier model | 0.7971 | [0.7846, 0.8093] | 0.025 |
| quality vs frontier model | 0.9974 | [0.9723, 1.0234] | 0.051 |
| **savings vs best single** | **0.2018** | **[0.1584, 0.2458]** | **0.087** |
| **quality vs best single** | **0.9937** | **[0.9750, 1.0133]** | **0.038** |
| share of oracle captured | 0.8514 | [0.8319, 0.8696] | 0.038 |
| validation Brier | 0.1610 | [0.1554, 0.1669] | 0.011 |

Two things follow, and one of them is good news:

**The headline savings figure is ±4.4 points, not ±1.4.** The cross-validation SE of 1.4%
measures how much the number moves between *training splits*; the bootstrap measures how
precisely it is known on the *evaluation items*, which is the wider and more relevant
question. Quote **20.2% (95% CI 15.8–24.6%)**.

**The quality interval contains 1.0.** So "we match the best single model's quality" is
supported by the data, and the 98.6% point estimate should not be read as an established
shortfall. This is a rare case where the statistics *strengthen* the product claim.

---

## 2. Multiple comparisons (items 5 and 10) — nothing survives

Paired standard errors per domain, Holm–Bonferroni across the family of five.

| domain | n | delta | SE | p | Holm threshold | survives |
|---|---|---|---|---|---|---|
| knowledge | 343 | −0.0466 | 0.0183 | 0.0112 | 0.0100 | **no** |
| science | 58 | −0.1379 | 0.0574 | 0.0196 | 0.0125 | **no** |
| open-ended | 326 | +0.0230 | 0.0163 | 0.1585 | 0.0167 | no |
| code | 395 | −0.0253 | 0.0206 | 0.2205 | 0.0250 | no |
| maths | 117 | +0.0000 | 0.0321 | 1.0000 | 0.0500 | no |

**Zero of five survive.** `PUBLISHABILITY.md` described knowledge as "sitting exactly on
the line"; it does not — p = 0.0112 against a threshold of 0.0100. And the router's
apparent win on open-ended work (1.4 SE) was never a result.

What survives without needing a test is the thing that matters: the per-item oracle scores
**0.95–1.00 in every domain**, so the headroom is real even where the wins are not.

---

## 3. Replication of the coverage-bias finding (item 6)

The most novel result in the repository — training on ten times the data costs twelve
points of quality retention — was measured once, on one pool. Re-run on **thirteen models
sharing no column with the first set**, same corpus, same code path, dense core of 3,920
items:

| arm | train items | val Brier | quality retained |
|---|---|---|---|
| dense core | 2,548 | 0.1706 | **103.3%** |
| union | 23,663 | 0.2246 | **84.2%** |

**It replicates, and larger: a +19.1 point gap against the original +12.2.** Ten times the
data costs nineteen points of quality retention on a pool that shares nothing with the one
where the effect was found. This moves the finding from Tier B to Tier A and makes it the
strongest candidate here for something publishable on its own.

**And the framing here is wrong, in a way that understates it.** A two-arm comparison
cannot say whether the damage comes from the uneven coverage or from the extra data,
because the union arm has both. A third arm settles it: train on a random subset of the
union items *of exactly the dense arm's size*, so only the coverage differs. That arm
retains **79.5%**, and the gap is **+23.7 points** — larger than with ten times the data.
More data is not the cause; it is a partial compensation, buying back about a fifth of
what uneven coverage costs. The full argument, including nineteen pools, two negative
controls and a mask sweep that dials the effect up and down at will, is `PUBLISHING.md`
§1.

---

## 4. Is the benchmark mix flattering us? (item 3) — my claim was wrong

I asserted in `PUBLISHABILITY.md` that because the evaluation set is nine hard benchmarks,
every savings figure is a conservative **lower bound** for real traffic. That was never
measured. It is now, by reweighting the held-out set toward items the pool finds easy —
where "easy" is a property of the item (pool solve rate), not of any policy, so it cannot
flatter the router by construction.

| easy share of traffic | quality | $/call | cheaper vs best single | open-tier share |
|---|---|---|---|---|
| 0% (as measured) | 0.6885 | 0.006546 | **20.3%** | 3.0% |
| 50% | 0.8245 | 0.005332 | **22.2%** | 6.1% |
| 90% | 0.9407 | 0.004975 | **18.8%** | 11.6% |

**The savings figure is flat — 18.8% to 22.2% across the whole range.** The "conservative
lower bound" claim is false and has been removed from `PUBLISHABILITY.md`.

What *does* move is quality (0.69 → 0.94) and the open tier's share of traffic (3.0% →
11.6%): easier traffic is answered better and by cheaper models, but the router does not
convert that into proportionally more savings. That is the same unreachability result from
`RESULTS.md` §4b seen from another angle — on easy items the cheap models become correct,
and the router still under-selects them.

The honest version of the claim is better than the one I made: **the headline is robust to
workload mix**, rather than conservative.

---

## 5. Published routers as baselines (item 7)

**Six** families reimplemented against the same held-out items, the same price table and
the same feature map — cascade (FrugalGPT-style), matrix factorisation (RouteLLM-style),
HybridLLM-style two-model gap routing, a classification router, k-NN retrieval, and
no-routing. Each is **swept across its own cost/quality dial**, because comparing single
operating points mostly measures where a rule's threshold happened to land.

Only points that **actually save money at ≥95% quality** are counted. Beating us while
spending more than sending everything to the best single model is not a comparison anyone
should act on.

| family | best useful point | quality vs best single | cheaper by | ours at same quality | margin, seed 0 | **margin over 8 splits** |
|---|---|---|---|---|---|---|
| matrix factorisation | λ_c = 1.0 | 95.5% | 59.4% | 55.8% | +3.6% | **−6.6% ± 7.8%, beats us in 2 of 7** |
| k-NN retrieval (k=32) | λ_c = 0.2 | 97.8% | 24.6% | 28.3% | −3.7% | **−0.1% ± 18.4%, beats us in 2 of 8** |
| cascade (FrugalGPT-style) | — | — | — | — | no useful point | **no useful point in 8 of 8** |
| HybridLLM-style | — | — | — | — | no useful point | **no useful point in 8 of 8** |

> **Corrected.** This section originally led with "matrix factorisation beats this router
> by 3.6 points", measured on a single split with no interval — the exact failure this
> document criticises elsewhere. With an interval it does not hold: the item bootstrap
> gives **[−5.3%, +26.0%]**, and across eight training splits the family *loses* to us by
> **6.6 points on average**, winning on two of them. Seed 0 was one of the two. The
> retraction and both instruments are in `PUBLISHING.md` §3.

Three results, and the first is no longer a negative for us:

**No published family reliably beats this router, and matrix factorisation is the one
that sometimes does.** A rank-8 low-rank completion of the outcome matrix, routed on the
completed row, reaches 59.4% savings at 95.5% quality on the split reported above, where
our dial gives 55.8%. Re-run on seven other splits it is behind us on five of them. The
weaker conclusion that survives is still worth having: a parameter-free or
nearly-parameter-free estimator lands in the same neighbourhood as ours, so **the ridge
estimator is not obviously where our advantage lives** — but the claim that a published
rule beats it is not supported.

**Cascades and HybridLLM have no useful operating point at all.** Neither ever both saves
money and holds 95% quality. For cascades the reason is structural: they pay for every
attempt, so a chain ending at the third model has bought three answers and delivered one.
At τ = 0.8 a cascade holds 98.5% of quality and spends **4.6×** what we do. Handed an
*oracle* verifier it cannot have — one that knows the answer was wrong, which is the
problem routing exists to solve — it still spends 67% more than doing nothing. HybridLLM's
two-model restriction is simply too coarse for a pool with a 404× price spread.

**k-NN is close, and very unstable.** A parameter-free retrieval router with no fitting at
all lands 3.7 points behind us on this split and −0.1% ± 18.4% across eight. The spread is
that wide because "at matched quality" means interpolating onto a ten-point dial, and a
family that lands on a steep part of it produces a noisy margin. That is a property of the
comparison method rather than of k-NN, and it is the reason `PUBLISHING.md` §3 reports the
split spread rather than any single interpolated point.

## What remains open, and what it costs

| item | why compute cannot close it | cost |
|---|---|---|
| The labels are stand-ins | needs a real Chutes endpoint | working key + ~tens of dollars, one afternoon |
| No latency in seconds | corpus wall-clock is concurrent | one timed run |

Everything else on the watch-list is now measured. The remaining two are the same two that
have been at the top of the roadmap since the beginning, and neither is expensive — they
are blocked on access, not on effort.

---

## Where each number lives

| claim | artifact | notebook |
|---|---|---|
| bootstrap CIs on every headline | `chutes/16_bootstrap.json` | 10 |
| per-domain SEs and Holm correction | `chutes/17_domains.json` | 10 |
| coverage-bias replication, workload mix | `chutes/18_replication.json` | 10 |
| published-router baselines | `chutes/19_baselines.json` | 10 |
| coverage bias made causal (pools, controls, mask sweep) | `chutes/20_dose_response.json` | — |
| k-fold intervals and the parity check | `chutes/21_kfold.json` | — |
| baseline margins with error bars | `chutes/22_baseline_margins.json` | — |
| the fifteen claims, classified and corrected | `chutes/23_multiplicity.json` | — |
