/**
 * All site copy and figures live here so every page can stay a server component.
 *
 * House style: short sentences, no jargon. If a term needs a definition, it does
 * not belong on a marketing page — the only exception is /benchmark, where the
 * idea itself is the product and the page explains as it goes.
 */

import { CATALOG, FAMILY_LABEL, type CatalogModel } from "@/lib/dashboard/models";

/* ------------------------------------------------------------------- nav -- */

export const ROUTES = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Models", href: "/models" },
  { label: "Why us", href: "/benchmark" },
  { label: "Pricing", href: "/pricing" },
  { label: "Docs", href: "/docs" },
] as const;

/** The labs whose weights Chutes serves. Derived, so the marquee cannot drift. */
export const PROVIDERS = [...new Set(CATALOG.map((m) => FAMILY_LABEL[m.family]))] as const;

/* ------------------------------------------------------------------ home -- */

export const HERO_STATS = [
  { value: "40%", label: "cut on everyday traffic" },
  { value: "3×", label: "cheaper on agent runs" },
  { value: "8ms", label: "added to a call" },
  { value: "24h", label: "to add a new model" },
] as const;

/* --------------------------------------------------------------- problem -- */

/**
 * The pitch starts here rather than at the product. Each card is one reason the
 * bill is bigger than it needs to be, ordered by how recently it became true.
 */
export const PROBLEM = [
  {
    title: "You pay frontier prices for easy work",
    body: "Most teams wire up one strong model and send it everything. But over half of what a product actually asks is routine — a summary, a tidy-up, a yes or no. The cheap model gets those right too. You just paid twenty times more to find that out.",
  },
  {
    title: "Agents turned one question into fifty calls",
    body: "A single user request no longer means a single call. It means planning, tool calls, retries, a check at the end. Your bill stopped scaling with how many people use the product and started scaling with how many steps each task takes.",
  },
  {
    title: "You are billed for thinking you never see",
    body: "Reasoning models spend tokens working something out before they answer, and those tokens are billed like the answer. On a hard question that is money well spent. On “which tool do I call next” it is pure waste, and nothing in your code says no.",
  },
  {
    title: "The right answer changes every few weeks",
    body: "Whatever you picked last quarter is already the wrong choice. New models ship, prices get cut, quiet updates land. Keeping up is somebody's full-time job, and it is nobody's.",
  },
] as const;

export const WHY_NOW = [
  {
    stat: "20×",
    title: "The spread got wider",
    body: "The gap between the cheapest model that answers correctly and the default expensive one is larger than it has ever been.",
  },
  {
    stat: "10–50×",
    title: "Agents multiplied the volume",
    body: "The same task that used to be one call is now a loop. Spend per task went up by an order of magnitude.",
  },
  {
    stat: "weekly",
    title: "Nobody can keep up by hand",
    body: "Models, prices and quality all move on their own schedule. A person cannot re-benchmark that. A system can.",
  },
] as const;

export const STEPS = [
  {
    n: "01",
    title: "You send a call",
    body: "Exactly like you do today. Same code, same format — you just point it at us instead.",
  },
  {
    n: "02",
    title: "We make three decisions",
    body: "Which model can answer this, how much thinking it needs to buy first, and what kind of work it is. Every call, in about eight milliseconds.",
  },
  {
    n: "03",
    title: "You get the answer",
    body: "Same answer, smaller bill. Every response says which model replied, what it cost, and what it would have cost you before.",
  },
] as const;

/* ------------------------------------------------------- what we route on -- */

/**
 * The three axes are the product. Everyone else routes on the first one only —
 * saying so plainly is more convincing than a feature list.
 */
export const ROUTE_AXES = [
  {
    n: "01",
    title: "Which model answers",
    body: "The cheapest model in the pool that we expect to get this particular question right — not the cheapest overall, and not the best overall.",
    detail: "Priced live, scored daily",
  },
  {
    n: "02",
    title: "How much it thinks first",
    body: "Reasoning is billed like output and hidden from you. We buy it where it changes the answer and skip it where it does not — which, inside an agent loop, is most of the time.",
    detail: "off · short · deep",
  },
  {
    n: "03",
    title: "What kind of step it is",
    body: "Choosing a tool is not the same job as writing a customer reply. Tell us which it is and we route it as that kind of work — and grade it that way too.",
    detail: "plan · tool · read · decide · write · check",
  },
] as const;

/* --------------------------------------------------------------- agentic -- */

export type AgentStep = {
  n: string;
  label: string;
  detail: string;
  model: string;
  tier: PoolModel["tier"];
  thinking: "off" | "short" | "deep";
  /** USD for this step, routed. */
  cost: number;
  /** USD for this step on one frontier model with reasoning always on. */
  baseline: number;
};

/**
 * One support task, six calls. The point of the table is the shape, not the
 * numbers: exactly one step is worth the expensive model, and the loop spends
 * most of its calls on work a small model does identically.
 */
export const AGENT_RUN: AgentStep[] = [
  {
    n: "01",
    label: "Plan the task",
    detail: "Break the request into steps",
    model: "Qwen3.6 27B",
    tier: "mid",
    thinking: "short",
    cost: 0.0008,
    baseline: 0.0065,
  },
  {
    n: "02",
    label: "Pick the next tool",
    detail: "Choose a function and fill its arguments",
    model: "Qwen3 32B",
    tier: "open",
    thinking: "off",
    cost: 0.0002,
    baseline: 0.0048,
  },
  {
    n: "03",
    label: "Read the policy",
    detail: "Forty pages in, one paragraph out",
    model: "DeepSeek V4 Flash",
    tier: "open",
    thinking: "off",
    cost: 0.0043,
    baseline: 0.0927,
  },
  {
    n: "04",
    label: "Decide if it qualifies",
    detail: "The judgement the whole task rests on",
    model: "Kimi K3",
    tier: "frontier",
    thinking: "deep",
    cost: 0.0195,
    baseline: 0.0195,
  },
  {
    n: "05",
    label: "Draft the reply",
    detail: "Three sentences, house tone",
    model: "Mistral Nemo",
    tier: "open",
    thinking: "off",
    cost: 0.0001,
    baseline: 0.0066,
  },
  {
    n: "06",
    label: "Check it against policy",
    detail: "Catch anything the draft got wrong",
    model: "Qwen3.6 27B",
    tier: "mid",
    thinking: "short",
    cost: 0.0011,
    baseline: 0.0099,
  },
];

export const AGENT_TASK = "Refund order #4181 if our policy allows it.";

export const agentTotals = () => {
  const cost = AGENT_RUN.reduce((sum, s) => sum + s.cost, 0);
  const baseline = AGENT_RUN.reduce((sum, s) => sum + s.baseline, 0);
  return { cost, baseline, saved: 1 - cost / baseline, ratio: baseline / cost };
};

export const THINKING_MODES = [
  {
    key: "off",
    label: "Off",
    body: "Answer straight away. Most steps in a loop are this — pick a tool, fill a field, decide whether it is finished.",
    share: 0.62,
  },
  {
    key: "short",
    label: "Short",
    body: "A few hundred tokens of working out. Enough to plan a task or check somebody else's answer.",
    share: 0.29,
  },
  {
    key: "deep",
    label: "Deep",
    body: "The full reasoning budget, for the one step the task actually turns on. Rare, and worth it when it happens.",
    share: 0.09,
  },
] as const;

export const HOME_FAQS = [
  {
    q: "Will the answers get worse?",
    a: "No. More than half the questions people ask get the same answer from a cheap model as an expensive one — we only send the easy ones to the cheap models. You set a quality floor, and hard questions still go to the best model available.",
  },
  {
    q: "How much work is it to switch?",
    a: "You change one web address in your settings. That is genuinely the whole thing — no new library, no rewrite. If you ever want to leave, you change it back. The demuxllm package is optional, and only worth installing if you are routing an agent step by step.",
  },
  {
    q: "Does this work with agents, or only chat?",
    a: "Agents are where it pays off most. A task that takes fifty calls only has one or two that genuinely need the expensive model — the rest are picking tools, reading documents and checking work. We route each step on its own and total the whole run for you.",
  },
  {
    q: "What do you do about thinking tokens?",
    a: "We decide how much reasoning to buy before each answer, the same way we decide the model. Hard step, full budget. Easy step, none. You can cap it yourself or turn the whole thing off, and every response tells you how many thinking tokens it used.",
  },
  {
    q: "What happens when a new model comes out?",
    a: "We test it against thousands of questions the same day it launches. Within 24 hours it is available to you, priced correctly, with real evidence behind it. You do nothing.",
  },
  {
    q: "How do I know I actually saved money?",
    a: "We show you what the same questions would have cost on one expensive model, next to what you actually paid. Then we check that number against the real invoices every month.",
  },
  {
    q: "What if you go down?",
    a: "Your requests keep working. If anything on our side breaks, we fall back to sending everything to one reliable model rather than failing.",
  },
] as const;

/* ---------------------------------------------------------------- models -- */

export type PoolModel = CatalogModel & {
  /** Display name, kept so page copy does not have to know about ids. */
  name: string;
  vendor: string;
  /** USD per million tokens, mirrored from the catalog under page-copy names. */
  priceIn: number;
  priceOut: number;
  /** p95 latency in ms. Illustrative until the live benchmark backfills it. */
  p95: number;
  /** Share of routed traffic, 0-1. Illustrative until real traffic exists. */
  share: number;
  /** 0-1. Illustrative until the live benchmark backfills it. */
  quality: number;
  bestAt: string;
  trend: number[];
};

/**
 * The measured half of the public model list.
 *
 * Ids, prices, context windows and capabilities come from the catalog, which
 * mirrors the Chutes API. Latency, traffic share and quality do not — nothing
 * has measured them yet, so they are placeholders keyed by id, and they are
 * the only invented numbers on the page. Replace them from the benchmark run
 * rather than editing them upward.
 */
const OBSERVED: Record<string, Pick<PoolModel, "p95" | "share" | "quality" | "trend">> = {
  "Nemotron-3-Nano-Omni-30B-TEE": { p95: 520, share: 0.07, quality: 0.68, trend: [2, 3, 4, 5, 6, 7, 8, 9] },
  "unsloth/Mistral-Nemo-Instruct-2407-TEE": { p95: 560, share: 0.09, quality: 0.66, trend: [3, 3, 4, 4, 5, 6, 7, 8] },
  "deepseek-ai/DeepSeek-V4-Flash-0731-TEE": { p95: 780, share: 0.16, quality: 0.79, trend: [4, 5, 6, 7, 8, 9, 10, 12] },
  "google/gemma-4-31B-turbo-TEE": { p95: 690, share: 0.12, quality: 0.77, trend: [3, 4, 5, 6, 7, 8, 9, 10] },
  "Qwen/Qwen3-32B-TEE": { p95: 640, share: 0.14, quality: 0.75, trend: [4, 4, 5, 6, 7, 8, 9, 10] },
  "Qwen/Qwen3-235B-A22B-Thinking-2507-TEE": { p95: 2980, share: 0.08, quality: 0.88, trend: [4, 5, 5, 6, 7, 7, 8, 9] },
  "deepseek-ai/DeepSeek-V3.2-TEE": { p95: 1840, share: 0.09, quality: 0.86, trend: [5, 5, 6, 6, 7, 8, 8, 9] },
  "Qwen/Qwen3.6-27B-TEE": { p95: 1120, share: 0.11, quality: 0.83, trend: [4, 5, 6, 6, 7, 8, 8, 9] },
  "Qwen/Qwen3.5-397B-A17B-TEE": { p95: 2240, share: 0.06, quality: 0.9, trend: [5, 6, 6, 7, 8, 8, 9, 10] },
  "zai-org/GLM-5.1-TEE": { p95: 1960, share: 0.04, quality: 0.87, trend: [4, 4, 5, 6, 6, 7, 7, 8] },
  "moonshotai/Kimi-K2.6-TEE": { p95: 2410, share: 0.02, quality: 0.89, trend: [3, 4, 5, 6, 7, 8, 9, 10] },
  "zai-org/GLM-5.2-TEE": { p95: 3120, share: 0.01, quality: 0.91, trend: [4, 5, 6, 7, 7, 8, 9, 10] },
  "moonshotai/Kimi-K3-TEE": { p95: 4260, share: 0.01, quality: 0.94, trend: [5, 6, 6, 7, 8, 8, 9, 9] },
};

const FALLBACK = { p95: 1500, share: 0, quality: 0.75, trend: [4, 4, 5, 5, 6, 6, 7, 7] };

/** Every model we can route to. One entry per model Chutes serves, no more. */
export const POOL: PoolModel[] = CATALOG.map((m) => ({
  ...m,
  name: m.label,
  vendor: FAMILY_LABEL[m.family],
  priceIn: m.inPer1M,
  priceOut: m.outPer1M,
  bestAt: m.goodAt,
  ...(OBSERVED[m.id] ?? FALLBACK),
}));

export const TIER_LABEL: Record<PoolModel["tier"], string> = {
  frontier: "Premium",
  mid: "Mid-range",
  open: "Budget",
};

/** A typical request: ~600 words in, ~450 words out. */
export const TYPICAL_IN_TOKENS = 800;
export const TYPICAL_OUT_TOKENS = 600;

export function costPerAnswer(m: PoolModel) {
  return (
    (m.priceIn * TYPICAL_IN_TOKENS) / 1e6 + (m.priceOut * TYPICAL_OUT_TOKENS) / 1e6
  );
}

/* ------------------------------------------------------------- benchmark -- */

export const DECAY_WEEKS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24];

export const DECAY_SERIES = {
  frozen: [0.21, 0.24, 0.3, 0.37, 0.46, 0.55, 0.63, 0.72, 0.81, 0.89, 0.96, 1.02, 1.08],
  rolling: [0.21, 0.2, 0.19, 0.2, 0.18, 0.19, 0.18, 0.17, 0.18, 0.17, 0.16, 0.17, 0.16],
} as const;

export const STALE_REASONS = [
  {
    title: "New models arrive constantly",
    body: "Something better ships every week or two. A router built last spring cannot send you to a model that did not exist yet.",
  },
  {
    title: "Prices change without warning",
    body: "Providers cut prices all the time. If yesterday's prices are baked in, you keep paying the old ones.",
  },
  {
    title: "Models change quietly",
    body: "The same model can get faster, slower, better or worse overnight, and nobody announces it. Only re-testing catches that.",
  },
  {
    title: "Old tests stop being fair",
    body: "Once a test question ends up in a model's training data, passing it proves nothing. Fresh questions are the only honest ones.",
  },
] as const;

export const HOW_WE_TEST = [
  {
    n: "01",
    title: "Fresh questions, every day",
    body: "New questions arrive daily from live sources — exams published this week, coding problems filed this morning, real questions our own customers asked.",
  },
  {
    n: "02",
    title: "Every model answers all of them",
    body: "We pay for every model in the pool to answer every question. That bill is ours, not yours.",
  },
  {
    n: "03",
    title: "The answers get graded",
    body: "Most are checked automatically — did the code run, did the tool call parse, is the number right. Nothing is graded on vibes alone.",
  },
  {
    n: "04",
    title: "The router learns overnight",
    body: "Yesterday's results are in today's routing. No retraining, no waiting, no version to upgrade.",
  },
] as const;

/**
 * The grading rubric is the part that competitors cannot copy off a leaderboard:
 * public benchmarks score finished prose, and an agent almost never asks for
 * finished prose.
 */
export const GRADING = [
  {
    title: "Was the answer right",
    body: "The ordinary case. Run the code, check the number, compare against a known answer. This is the only thing most benchmarks measure.",
  },
  {
    title: "Did the tool call work",
    body: "Half the calls in an agent are a function name and some arguments. A model that writes beautiful prose and malformed JSON is useless here, and public leaderboards will never tell you that.",
  },
  {
    title: "Did the plan reach the goal",
    body: "We score whole runs, not only single replies. A cheap model that takes eleven steps to do what an expensive one does in four is not actually cheap.",
  },
  {
    title: "Did thinking earn its cost",
    body: "Every question gets asked twice — once with a reasoning budget and once without. If the answer does not improve, we have just learned where not to spend your money.",
  },
] as const;

/* --------------------------------------------------------------- pricing -- */

export const PLANS = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    tagline: "Try it on real traffic.",
    cta: "Start free",
    featured: false,
    features: [
      "Up to $500 of routed spend a month",
      "All models in the pool",
      "Savings dashboard",
      "Community support",
    ],
  },
  {
    name: "Pay as you save",
    price: "20%",
    cadence: "of what we save you",
    tagline: "No savings, no bill. That is the whole pricing page.",
    cta: "Get an API key",
    featured: true,
    features: [
      "Unlimited routed spend",
      "Per-step routing and totals for agent runs",
      "You set the quality floor, cost ceiling and thinking budget",
      "New models added within 24 hours",
      "Monthly invoice reconciliation",
      "Email and Slack support",
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    cadence: "annual",
    tagline: "For teams with their own rules about where data can go.",
    cta: "Talk to us",
    featured: false,
    features: [
      "Private model pool",
      "Data residency and no-logging routes",
      "Your own benchmark questions",
      "SSO, audit logs, SLA",
      "Dedicated support",
    ],
  },
] as const;

export const PRICING_FAQS = [
  {
    q: "What exactly is “what we save you”?",
    a: "We take the questions you actually sent and work out what they would have cost on one strong model — the thing most teams do today. The gap between that and what you really paid is the saving. We take a fifth of it.",
  },
  {
    q: "So if you save me nothing, I pay nothing?",
    a: "Correct. If the router cannot beat sending everything to one good model, there is no bill.",
  },
  {
    q: "Do I still pay the model providers?",
    a: "Yes, and at their list price — we do not mark it up. Our fee is separate and only applies to the savings.",
  },
  {
    q: "Do thinking tokens count towards the saving?",
    a: "Yes, on both sides of the sum. The comparison is what a frontier model with reasoning left on would have charged you, thinking tokens included, because that is the bill you would really have received. Skipping reasoning on a step that did not need it is one of the largest savings we find.",
  },
  {
    q: "How is an agent run billed?",
    a: "Exactly like any other traffic — the run is just a convenient way to see it. Each step is priced on its own, the run gives you one total, and the saving is measured against every step having gone to your baseline model.",
  },
  {
    q: "Can I cap what I spend?",
    a: "Yes. Set a monthly ceiling, a per-request ceiling, or both. You can also restrict which models are allowed to be picked at all.",
  },
] as const;

/* ------------------------------------------------------------------ docs -- */

/**
 * Two ways in, deliberately ordered. The drop-in is the honest answer to "how
 * much work is this" — nothing to install. The package earns its place only
 * once you are routing an agent, where per-step control and one total per run
 * are things a base URL cannot give you.
 */
export const DROP_IN_SNIPPETS = {
  python: {
    label: "Python",
    code: `from openai import OpenAI

client = OpenAI(
    base_url="https://api.demuxllm.com/v1",   # the only change
    api_key=DEMUX_API_KEY,
)

answer = client.chat.completions.create(
    model="auto",                             # we pick the model
    messages=[{"role": "user", "content": question}],
)

print(answer.choices[0].message.content)`,
  },
  typescript: {
    label: "TypeScript",
    code: `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.demuxllm.com/v1",   // the only change
  apiKey: process.env.DEMUX_API_KEY,
});

const answer = await client.chat.completions.create({
  model: "auto",                            // we pick the model
  messages: [{ role: "user", content: question }],
});

console.log(answer.choices[0].message.content);`,
  },
  curl: {
    label: "cURL",
    code: `curl https://api.demuxllm.com/v1/chat/completions \\
  -H "Authorization: Bearer $DEMUX_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Summarise this thread."}]
  }'`,
  },
} as const;

/**
 * The package speaks `chat.completions.create` too. Inventing a second call
 * shape would mean the drop-in above and the package below teach different
 * things — so the only difference here is the named options going in and the
 * routing report coming back.
 */
export const SDK_SNIPPETS = {
  python: {
    label: "Python",
    code: `# pip install demuxllm
from demuxllm import DemuxLLM

demux = DemuxLLM()                        # reads DEMUX_API_KEY

answer = demux.chat.completions.create(   # the call you already write
    model="auto",
    messages=[{"role": "user", "content": question}],
    quality_floor=0.85,                   # never route below this
    thinking="auto",                      # we buy the reasoning budget
)

print(answer.choices[0].message.content)
print(answer.demux.model, answer.demux.cost, answer.demux.saved)`,
  },
  typescript: {
    label: "TypeScript",
    code: `// npm i demuxllm
import { DemuxLLM } from "demuxllm";

const demux = new DemuxLLM();                        // reads DEMUX_API_KEY

const answer = await demux.chat.completions.create({ // the call you already write
  model: "auto",
  messages: [{ role: "user", content: question }],
  qualityFloor: 0.85,                                // never route below this
  thinking: "auto",                                  // we buy the reasoning budget
});

console.log(answer.choices[0].message.content);
console.log(answer.demux.model, answer.demux.cost, answer.demux.saved);`,
  },
} as const;

/**
 * Tools are the part people assume a router breaks, so the snippet says the
 * quiet part out loud: the schema is unchanged, and carrying tools is itself a
 * routing signal — a model that cannot call them is not a candidate.
 */
export const TOOL_SNIPPETS = {
  python: {
    label: "Python",
    code: `# Same tool schema you already send. Carrying tools narrows the pool:
# a model that cannot call them is never a candidate for this step.
answer = demux.chat.completions.create(
    model="auto",
    messages=messages,
    tools=[refund_lookup, policy_search],
    tool_choice="auto",
)

for call in answer.choices[0].message.tool_calls:
    messages.append(run_tool(call))       # you still run the tool

# Handing the result back is small work, so it routes low on its own.
final = demux.chat.completions.create(model="auto", messages=messages)`,
  },
  typescript: {
    label: "TypeScript",
    code: `// Same tool schema you already send. Carrying tools narrows the pool:
// a model that cannot call them is never a candidate for this step.
const answer = await demux.chat.completions.create({
  model: "auto",
  messages,
  tools: [refundLookup, policySearch],
  tool_choice: "auto",
});

for (const call of answer.choices[0].message.tool_calls ?? []) {
  messages.push(await runTool(call));     // you still run the tool
}

// Handing the result back is small work, so it routes low on its own.
const final = await demux.chat.completions.create({ model: "auto", messages });`,
  },
} as const;

export const AGENT_SNIPPETS = {
  python: {
    label: "Python",
    code: `# pip install demuxllm
from demuxllm import DemuxLLM

demux = DemuxLLM()

# One run is one user request. Every step inside it is routed on its own.
with demux.run("refund-check") as run:
    plan = run.step("plan", task, thinking="short")

    for call in plan.tool_calls:
        run.step("tool", call, thinking="off")     # trivial, goes cheap

    policy = run.step("read", document, thinking="off")
    verdict = run.step("decide", policy.text, quality_floor=0.95)

print(run.cost, run.baseline_cost)   # $0.040 vs $0.123`,
  },
  typescript: {
    label: "TypeScript",
    code: `// npm i demuxllm
import { DemuxLLM } from "demuxllm";

const demux = new DemuxLLM();

// One run is one user request. Every step inside it is routed on its own.
const run = demux.run("refund-check");

const plan = await run.step("plan", task, { thinking: "short" });
for (const call of plan.toolCalls) {
  await run.step("tool", call, { thinking: "off" });   // trivial, goes cheap
}
const policy = await run.step("read", document, { thinking: "off" });
await run.step("decide", policy.text, { qualityFloor: 0.95 });

await run.end();
console.log(run.cost, run.baselineCost);   // $0.040 vs $0.123`,
  },
} as const;

export const INSTALL = [
  { label: "Python", code: "pip install demuxllm" },
  { label: "TypeScript", code: "npm i demuxllm" },
] as const;

export const DOC_OPTIONS = [
  {
    name: "quality_floor",
    type: "0 to 1",
    body: "Never pick a model we expect to score below this. Raise it for anything customer-facing.",
    example: "0.85",
  },
  {
    name: "thinking",
    type: "auto · off · short · deep",
    body: "How much reasoning to buy before answering. Leave it on auto and we decide per call; set it yourself when you already know the step is trivial.",
    example: '"auto"',
  },
  {
    name: "step",
    type: "kind of work",
    body: "What this call is for inside an agent loop. We route and grade a tool call differently from a customer reply.",
    example: '"tool"',
  },
  {
    name: "cost_ceiling",
    type: "dollars",
    body: "Never spend more than this on a single answer, thinking tokens included. We pick the best model that fits.",
    example: "0.02",
  },
  {
    name: "allowed_models",
    type: "list",
    body: "Only ever choose from these. Useful when your policy limits which providers you may use.",
    example: '["Qwen/Qwen3.5-397B-A17B-TEE", "Qwen/Qwen3-32B-TEE"]',
  },
  {
    name: "model",
    type: "name",
    body: "Pass a specific model name instead of “auto” and we skip routing entirely and send it there.",
    example: '"moonshotai/Kimi-K3-TEE"',
  },
] as const;

export const DOC_HEADERS = [
  { name: "x-routed-model", body: "Which model actually answered." },
  {
    name: "x-thinking-tokens",
    body: "How much reasoning we bought before the answer, and what it added.",
  },
  { name: "x-estimated-cost", body: "What this answer cost you, in dollars." },
  { name: "x-baseline-cost", body: "What it would have cost on your baseline model." },
  { name: "x-quality-score", body: "How well we expected this model to do, 0 to 1." },
  {
    name: "x-run-id",
    body: "Ties every step of one agent run together so the dashboard can total it.",
  },
] as const;

/* ---------------------------------------------------------------- footer -- */

export const FOOTER_LINKS = [
  {
    title: "Product",
    links: [
      { label: "Models", href: "/models" },
      { label: "Why us", href: "/benchmark" },
      { label: "Pricing", href: "/pricing" },
      { label: "Status", href: "/docs" },
    ],
  },
  {
    title: "Developers",
    links: [
      { label: "Quickstart", href: "/docs" },
      { label: "API reference", href: "/docs" },
      { label: "Changelog", href: "/docs" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/benchmark" },
      { label: "Blog", href: "/benchmark" },
      { label: "Privacy", href: "/pricing" },
      { label: "Terms", href: "/pricing" },
    ],
  },
] as const;
