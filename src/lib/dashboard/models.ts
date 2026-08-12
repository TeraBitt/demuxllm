/**
 * The routing pool: every LLM Chutes serves, and nothing else.
 *
 * This list is not invented. It mirrors `GET https://llm.chutes.ai/v1/models`
 * field for field — ids are the exact strings the API expects as `model`, and
 * prices are the USD figures Chutes publishes per million tokens. Anything a
 * request cannot actually be sent to does not belong here, because a router
 * that scores a model it cannot call is scoring a rumour.
 *
 * Prices move. `npm run sync:catalog` diffs this file against the live endpoint
 * and names what drifted; tier and goodAt are judgements, so it reports rather
 * than rewrites.
 */

export type Tier = "open" | "mid" | "frontier";

/** Who trained the weights. Chutes is the only place any of them are served. */
export type Family = "qwen" | "deepseek" | "moonshot" | "zai" | "google" | "mistral" | "nvidia";

export type CatalogModel = {
  /** Exactly what goes in the `model` field of a Chutes request. */
  id: string;
  label: string;
  family: Family;
  tier: Tier;
  /** USD per 1M tokens. */
  inPer1M: number;
  outPer1M: number;
  /** USD per 1M tokens read from cache. */
  cachedInPer1M: number;
  /** Context window in tokens. null where Chutes does not report one. */
  ctx: number | null;
  /** What the model accepts beyond text. */
  vision: boolean;
  video: boolean;
  /** Can be trusted with tool calls and JSON schemas. */
  structured: boolean;
  /** Spends tokens thinking before it answers. */
  thinks: boolean;
  /** Shown under the answer: why this one was picked. */
  goodAt: string;
};

export const CATALOG: readonly CatalogModel[] = [
  {
    id: "Nemotron-3-Nano-Omni-30B-TEE",
    label: "Nemotron 3 Nano Omni 30B",
    family: "nvidia",
    tier: "open",
    inPer1M: 0.0245,
    outPer1M: 0.0978,
    cachedInPer1M: 0.0025,
    ctx: null,
    vision: false,
    video: false,
    structured: false,
    thinks: false,
    goodAt: "Extraction, tagging and cleanup",
  },
  {
    id: "unsloth/Mistral-Nemo-Instruct-2407-TEE",
    label: "Mistral Nemo Instruct",
    family: "mistral",
    tier: "open",
    inPer1M: 0.0245,
    outPer1M: 0.0978,
    cachedInPer1M: 0.0025,
    ctx: null,
    vision: false,
    video: false,
    structured: false,
    thinks: false,
    goodAt: "Rewriting and short everyday replies",
  },
  {
    id: "deepseek-ai/DeepSeek-V4-Flash-0731-TEE",
    label: "DeepSeek V4 Flash",
    family: "deepseek",
    tier: "open",
    inPer1M: 0.14,
    outPer1M: 0.28,
    cachedInPer1M: 0.014,
    ctx: 1_048_576,
    vision: false,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Very long documents on a budget",
  },
  {
    id: "google/gemma-4-31B-turbo-TEE",
    label: "Gemma 4 31B Turbo",
    family: "google",
    tier: "open",
    inPer1M: 0.12,
    outPer1M: 0.37,
    cachedInPer1M: 0.012,
    ctx: 131_072,
    vision: true,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Everyday questions and image input",
  },
  {
    id: "Qwen/Qwen3-32B-TEE",
    label: "Qwen3 32B",
    family: "qwen",
    tier: "open",
    inPer1M: 0.104,
    outPer1M: 0.416,
    cachedInPer1M: 0.0104,
    ctx: 40_960,
    vision: false,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Classifying, routing and structured output",
  },
  {
    id: "Qwen/Qwen3-235B-A22B-Thinking-2507-TEE",
    label: "Qwen3 235B Thinking",
    family: "qwen",
    tier: "mid",
    inPer1M: 0.2989,
    outPer1M: 1.1957,
    cachedInPer1M: 0.0299,
    ctx: 262_144,
    vision: false,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Maths and step-by-step analysis",
  },
  {
    id: "deepseek-ai/DeepSeek-V3.2-TEE",
    label: "DeepSeek V3.2",
    family: "deepseek",
    tier: "mid",
    inPer1M: 1,
    outPer1M: 1,
    cachedInPer1M: 0.1,
    ctx: 131_072,
    vision: false,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Code and long answers at a flat rate",
  },
  {
    id: "Qwen/Qwen3.6-27B-TEE",
    label: "Qwen3.6 27B",
    family: "qwen",
    tier: "mid",
    inPer1M: 0.3,
    outPer1M: 2,
    cachedInPer1M: 0.03,
    ctx: 262_144,
    vision: true,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Balanced everyday work with images",
  },
  {
    id: "Qwen/Qwen3.5-397B-A17B-TEE",
    label: "Qwen3.5 397B",
    family: "qwen",
    tier: "mid",
    inPer1M: 0.45,
    outPer1M: 3,
    cachedInPer1M: 0.045,
    ctx: 262_144,
    vision: true,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Hard reasoning and long code",
  },
  {
    id: "zai-org/GLM-5.1-TEE",
    label: "GLM 5.1",
    family: "zai",
    tier: "mid",
    inPer1M: 0.98,
    outPer1M: 3.08,
    cachedInPer1M: 0.098,
    ctx: 202_752,
    vision: false,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Agent loops and tool calling",
  },
  {
    id: "moonshotai/Kimi-K2.6-TEE",
    label: "Kimi K2.6",
    family: "moonshot",
    tier: "mid",
    inPer1M: 0.58,
    outPer1M: 3.4,
    cachedInPer1M: 0.058,
    ctx: 262_144,
    vision: true,
    video: true,
    structured: true,
    thinks: true,
    goodAt: "Agentic work, image and video input",
  },
  {
    id: "zai-org/GLM-5.2-TEE",
    label: "GLM 5.2",
    family: "zai",
    tier: "frontier",
    inPer1M: 1.25,
    outPer1M: 3.95,
    cachedInPer1M: 0.125,
    ctx: 1_048_576,
    vision: false,
    video: false,
    structured: true,
    thinks: true,
    goodAt: "Long-context reasoning and code review",
  },
  {
    id: "moonshotai/Kimi-K3-TEE",
    label: "Kimi K3",
    family: "moonshot",
    tier: "frontier",
    inPer1M: 3,
    outPer1M: 15,
    cachedInPer1M: 0.3,
    ctx: 1_048_576,
    vision: true,
    video: true,
    structured: true,
    thinks: true,
    goodAt: "The hardest work, when nothing cheaper clears",
  },
] as const;

/**
 * The model the orchestrator itself runs on: the cheapest thing on Chutes that
 * can be held to a JSON schema. Routing is a classification job, not a writing
 * job — paying reasoning prices to pick a model would undo the point.
 */
export const ORCHESTRATOR_ID = "Qwen/Qwen3-32B-TEE";

/** What it would have cost to send everything to the dearest model. */
export const BASELINE_ID = "moonshotai/Kimi-K3-TEE";

export const byId = (id: string) => CATALOG.find((m) => m.id === id);
export const baseline = () => byId(BASELINE_ID)!;
export const orchestrator = () => byId(ORCHESTRATOR_ID)!;

export function costOf(model: Pick<CatalogModel, "inPer1M" | "outPer1M">, inTok: number, outTok: number) {
  return (inTok / 1e6) * model.inPer1M + (outTok / 1e6) * model.outPer1M;
}

/** The same work, priced on the dearest model instead. */
export function baselineCost(inTok: number, outTok: number) {
  return costOf(baseline(), inTok, outTok);
}

export const usd = (n: number, places = 4) => `$${n.toFixed(places)}`;

/** Rough token estimate. Good enough to price a demo, wrong enough to say so. */
export const estimateTokens = (text: string) => Math.max(1, Math.ceil(text.length / 4));

export const TIER_LABEL: Record<Tier, string> = {
  open: "Cheap",
  mid: "Mid",
  frontier: "Top",
};

export const TIER_VAR: Record<Tier, string> = {
  open: "var(--tier-1)",
  mid: "var(--tier-2)",
  frontier: "var(--tier-3)",
};

export const FAMILY_LABEL: Record<Family, string> = {
  qwen: "Qwen",
  deepseek: "DeepSeek",
  moonshot: "Moonshot",
  zai: "Z.ai",
  google: "Google",
  mistral: "Mistral",
  nvidia: "NVIDIA",
};

/** 1048576 → "1M". Context windows are read, not calculated. */
export function formatCtx(ctx: number | null) {
  if (!ctx) return "—";
  return ctx >= 1e6 ? `${Math.round(ctx / 1e5) / 10}M` : `${Math.round(ctx / 1024)}K`;
}
