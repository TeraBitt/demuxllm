/**
 * The routing pool for the demo dashboard.
 *
 * Prices are published list prices in USD per million tokens, recorded by hand
 * and certain to drift — they exist so the cost arithmetic on screen is the
 * right shape and the right order of magnitude, not so it is invoiceable. The
 * dashboard says as much in the footer of the usage panel.
 *
 * Two providers, because they demonstrate different halves of the pitch:
 * Gemini is the hosted frontier ladder (real calls, when a key is present) and
 * Chutes is the open-weights floor that makes the saving large.
 */

export type Tier = "open" | "mid" | "frontier";
export type Provider = "gemini" | "chutes";
export type Thinking = "off" | "short" | "deep";

export type CatalogModel = {
  id: string;
  label: string;
  provider: Provider;
  tier: Tier;
  /** USD per 1M tokens. */
  inPer1M: number;
  outPer1M: number;
  contextK: number;
  thinking: boolean;
  tools: boolean;
  blurb: string;
};

export const CATALOG: readonly CatalogModel[] = [
  {
    id: "gemini-3.5-flash-lite",
    label: "Gemini 3.5 Flash Lite",
    provider: "gemini",
    tier: "open",
    inPer1M: 0.1,
    outPer1M: 0.4,
    contextK: 1000,
    thinking: false,
    tools: true,
    blurb: "Extraction, routing, tool arguments, anything mechanical.",
  },
  {
    id: "gemini-3.6-flash",
    label: "Gemini 3.6 Flash",
    provider: "gemini",
    tier: "mid",
    inPer1M: 0.5,
    outPer1M: 3,
    contextK: 1000,
    thinking: true,
    tools: true,
    blurb: "The default. Handles most real questions without the frontier bill.",
  },
  {
    id: "gemini-3.1-pro-preview",
    label: "Gemini 3.1 Pro",
    provider: "gemini",
    tier: "frontier",
    inPer1M: 1.4,
    outPer1M: 11,
    contextK: 2000,
    thinking: true,
    tools: true,
    blurb: "Held back for genuinely hard reasoning and anything customer-facing.",
  },
  {
    id: "deepseek-ai/DeepSeek-V3",
    label: "DeepSeek V3",
    provider: "chutes",
    tier: "mid",
    inPer1M: 0.27,
    outPer1M: 1.1,
    contextK: 128,
    thinking: false,
    tools: true,
    blurb: "Strong open general model. Good long-form writing per dollar.",
  },
  {
    id: "Qwen/Qwen3-235B-A22B",
    label: "Qwen3 235B",
    provider: "chutes",
    tier: "mid",
    inPer1M: 0.2,
    outPer1M: 0.6,
    contextK: 128,
    thinking: true,
    tools: true,
    blurb: "Cheap reasoning. Often the best value on multi-step work.",
  },
  {
    id: "meta-llama/Llama-3.3-70B-Instruct",
    label: "Llama 3.3 70B",
    provider: "chutes",
    tier: "open",
    inPer1M: 0.1,
    outPer1M: 0.28,
    contextK: 128,
    thinking: false,
    tools: false,
    blurb: "Summarising and classification at the floor price.",
  },
] as const;

/** What a frontier-only setup would have cost. Every saving is measured here. */
export const BASELINE_ID = "gemini-3.1-pro-preview";

export const byId = (id: string) => CATALOG.find((m) => m.id === id);

export const baseline = () => byId(BASELINE_ID)!;

export function costOf(model: CatalogModel, inTok: number, outTok: number) {
  return (inTok / 1e6) * model.inPer1M + (outTok / 1e6) * model.outPer1M;
}

/**
 * Thinking is billed at output rates and is invisible in the response, so a
 * routing demo that ignored it would understate the frontier bill it is
 * comparing against. These multipliers stand in for the reasoning tokens a
 * model spends before it answers.
 */
export const THINKING_MULT: Record<Thinking, number> = {
  off: 1,
  short: 1.7,
  deep: 3.4,
};

export function stepCost(
  model: CatalogModel,
  inTok: number,
  outTok: number,
  thinking: Thinking,
) {
  const billedOut = outTok * (model.thinking ? THINKING_MULT[thinking] : 1);
  return costOf(model, inTok, billedOut);
}

/**
 * The same step priced as if it had gone to the frontier model instead, holding
 * the reasoning budget constant.
 *
 * Holding thinking constant is the load-bearing decision. Price the baseline at
 * a fixed `deep` and every saving on screen roughly doubles — the flattering
 * option, and the one that loses the argument the moment a reader checks it.
 * Price it below what the router bought and a step that legitimately needed
 * deep reasoning reports a NEGATIVE saving, which reads as a bug rather than as
 * the honest statement it is.
 *
 * So the comparison isolates exactly one variable: which model answered. When
 * the router sends a step to the frontier anyway, the saving is 0% and the
 * dashboard says so. A router that claims to save on every single call is not
 * believable, and this one does not.
 */
export function baselineCost(inTok: number, outTok: number, thinking: Thinking) {
  return costOf(baseline(), inTok, outTok * THINKING_MULT[thinking]);
}

export const usd = (n: number, places = 4) => `$${n.toFixed(places)}`;

/** Rough token estimate. Good enough to price a demo, wrong enough to say so. */
export const estimateTokens = (text: string) => Math.max(1, Math.ceil(text.length / 4));

export const TIER_LABEL: Record<Tier, string> = {
  open: "Open",
  mid: "Mid",
  frontier: "Frontier",
};

export const TIER_VAR: Record<Tier, string> = {
  open: "var(--tier-1)",
  mid: "var(--tier-2)",
  frontier: "var(--tier-3)",
};
