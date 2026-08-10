/**
 * All site copy and figures live here so every page can stay a server component.
 *
 * House style: short sentences, no jargon. If a term needs a definition, it does
 * not belong on a marketing page — the only exception is /benchmark, where the
 * idea itself is the product and the page explains as it goes.
 */

/* ------------------------------------------------------------------- nav -- */

export const ROUTES = [
  { label: "Models", href: "/models" },
  { label: "Why us", href: "/benchmark" },
  { label: "Pricing", href: "/pricing" },
  { label: "Docs", href: "/docs" },
] as const;

export const PROVIDERS = [
  "OpenAI",
  "Anthropic",
  "Google",
  "Meta",
  "Mistral",
  "DeepSeek",
  "Qwen",
  "xAI",
  "Cohere",
  "Groq",
] as const;

/* ------------------------------------------------------------------ home -- */

export const HERO_STATS = [
  { value: "40%", label: "average bill cut" },
  { value: "1", label: "line of code to switch" },
  { value: "24h", label: "to add a new model" },
  { value: "8ms", label: "added to a request" },
] as const;

export const STEPS = [
  {
    n: "01",
    title: "You send a question",
    body: "Exactly like you do today. Same code, same format — you just point it at us instead.",
  },
  {
    n: "02",
    title: "We pick the model",
    body: "We already know which models are good at what, and what each one charges today. We pick the cheapest one that will get it right.",
  },
  {
    n: "03",
    title: "You get the answer",
    body: "Same answer, smaller bill. Your dashboard shows exactly what you saved and how we chose.",
  },
] as const;

export const HOME_FAQS = [
  {
    q: "Will the answers get worse?",
    a: "No. More than half the questions people ask get the same answer from a cheap model as an expensive one — we only send the easy ones to the cheap models. You set a quality floor, and hard questions still go to the best model available.",
  },
  {
    q: "How much work is it to switch?",
    a: "You change one web address in your settings. That is genuinely the whole thing — no new library, no rewrite. If you ever want to leave, you change it back.",
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

export type PoolModel = {
  id: string;
  name: string;
  vendor: string;
  tier: "frontier" | "mid" | "open";
  /** USD per million tokens. */
  priceIn: number;
  priceOut: number;
  /** Measured p95 latency, ms. */
  p95: number;
  /** Share of routed traffic, 0–1. */
  share: number;
  /** 0–1, measured on the live benchmark. */
  quality: number;
  bestAt: string;
  trend: number[];
};

export const POOL: PoolModel[] = [
  {
    id: "opus-4",
    name: "Opus 4",
    vendor: "Anthropic",
    tier: "frontier",
    priceIn: 15,
    priceOut: 75,
    p95: 4120,
    share: 0.06,
    quality: 0.94,
    bestAt: "Hard reasoning, long documents",
    trend: [4, 6, 5, 7, 6, 8, 7, 9],
  },
  {
    id: "gpt-5",
    name: "GPT-5",
    vendor: "OpenAI",
    tier: "frontier",
    priceIn: 10,
    priceOut: 40,
    p95: 3480,
    share: 0.08,
    quality: 0.93,
    bestAt: "Maths, planning, tricky edge cases",
    trend: [5, 5, 6, 6, 7, 7, 8, 8],
  },
  {
    id: "sonnet-4",
    name: "Sonnet 4",
    vendor: "Anthropic",
    tier: "mid",
    priceIn: 3,
    priceOut: 15,
    p95: 1980,
    share: 0.19,
    quality: 0.88,
    bestAt: "Writing code, following instructions",
    trend: [6, 7, 7, 8, 9, 9, 10, 11],
  },
  {
    id: "gemini-flash",
    name: "Gemini Flash",
    vendor: "Google",
    tier: "mid",
    priceIn: 1.25,
    priceOut: 10,
    p95: 1640,
    share: 0.14,
    quality: 0.86,
    bestAt: "Long context, other languages",
    trend: [5, 6, 6, 7, 7, 8, 8, 9],
  },
  {
    id: "mistral-large",
    name: "Mistral Large",
    vendor: "Mistral",
    tier: "mid",
    priceIn: 0.9,
    priceOut: 2.8,
    p95: 1210,
    share: 0.11,
    quality: 0.81,
    bestAt: "European languages, summarising",
    trend: [4, 5, 5, 5, 6, 6, 7, 7],
  },
  {
    id: "llama-70b",
    name: "Llama 70B",
    vendor: "Meta",
    tier: "open",
    priceIn: 0.18,
    priceOut: 0.6,
    p95: 740,
    share: 0.17,
    quality: 0.76,
    bestAt: "Everyday chat, rewriting",
    trend: [3, 4, 5, 6, 7, 8, 9, 10],
  },
  {
    id: "qwen-72b",
    name: "Qwen 72B",
    vendor: "Qwen",
    tier: "open",
    priceIn: 0.12,
    priceOut: 0.42,
    p95: 690,
    share: 0.14,
    quality: 0.74,
    bestAt: "Summarising, classifying, tagging",
    trend: [3, 3, 4, 5, 6, 7, 8, 9],
  },
  {
    id: "deepseek-v3",
    name: "DeepSeek V3",
    vendor: "DeepSeek",
    tier: "open",
    priceIn: 0.14,
    priceOut: 0.28,
    p95: 820,
    share: 0.11,
    quality: 0.75,
    bestAt: "Code, structured output",
    trend: [4, 4, 5, 5, 6, 7, 7, 8],
  },
  {
    id: "haiku-4",
    name: "Haiku 4",
    vendor: "Anthropic",
    tier: "open",
    priceIn: 0.25,
    priceOut: 1.25,
    p95: 620,
    share: 0.0,
    quality: 0.78,
    bestAt: "Fast replies, simple extraction",
    trend: [2, 3, 4, 5, 6, 7, 8, 9],
  },
  {
    id: "gemini-pro",
    name: "Gemini Pro",
    vendor: "Google",
    tier: "frontier",
    priceIn: 7,
    priceOut: 21,
    p95: 3010,
    share: 0.0,
    quality: 0.91,
    bestAt: "Research, very long inputs",
    trend: [5, 5, 6, 7, 7, 8, 9, 9],
  },
  {
    id: "grok-3",
    name: "Grok 3",
    vendor: "xAI",
    tier: "mid",
    priceIn: 2,
    priceOut: 10,
    p95: 1890,
    share: 0.0,
    quality: 0.84,
    bestAt: "Current events, conversation",
    trend: [4, 5, 5, 6, 6, 7, 7, 8],
  },
  {
    id: "command-r",
    name: "Command R+",
    vendor: "Cohere",
    tier: "mid",
    priceIn: 2.5,
    priceOut: 10,
    p95: 1520,
    share: 0.0,
    quality: 0.82,
    bestAt: "Search over your own documents",
    trend: [3, 4, 4, 5, 5, 6, 6, 7],
  },
];

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
    body: "Most are checked automatically — did the code run, is the number right. Nothing is graded on vibes alone.",
  },
  {
    n: "04",
    title: "The router learns overnight",
    body: "Yesterday's results are in today's routing. No retraining, no waiting, no version to upgrade.",
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
      "You set the quality floor and cost ceiling",
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
    q: "Can I cap what I spend?",
    a: "Yes. Set a monthly ceiling, a per-request ceiling, or both. You can also restrict which models are allowed to be picked at all.",
  },
] as const;

/* ------------------------------------------------------------------ docs -- */

export const DOC_SNIPPETS = {
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

export const DOC_OPTIONS = [
  {
    name: "quality_floor",
    type: "0 to 1",
    body: "Never pick a model we expect to score below this. Raise it for anything customer-facing.",
    example: "0.85",
  },
  {
    name: "cost_ceiling",
    type: "dollars",
    body: "Never spend more than this on a single answer. We pick the best model that fits.",
    example: "0.02",
  },
  {
    name: "allowed_models",
    type: "list",
    body: "Only ever choose from these. Useful when your policy limits which providers you may use.",
    example: '["sonnet-4", "llama-70b"]',
  },
  {
    name: "model",
    type: "name",
    body: "Pass a specific model name instead of “auto” and we skip routing entirely and send it there.",
    example: '"gpt-5"',
  },
] as const;

export const DOC_HEADERS = [
  { name: "x-routed-model", body: "Which model actually answered." },
  { name: "x-estimated-cost", body: "What this answer cost you, in dollars." },
  { name: "x-baseline-cost", body: "What it would have cost on your baseline model." },
  { name: "x-quality-score", body: "How well we expected this model to do, 0 to 1." },
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
