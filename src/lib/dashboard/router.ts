/**
 * The orchestrator: one small model call that decides everything, then policy
 * in code that turns the decision into a pick.
 *
 * The split of labour matters. A 32B model on Chutes judges only what cannot be
 * computed — how well each candidate would handle THIS request, how good the
 * answer actually has to be, and whether the request is company work or
 * something the sender brought from outside. The choice itself is arithmetic:
 * take the cheapest model that clears the bar. Judgement from the model, policy
 * from the code, so the decision is auditable and cannot drift on a whim.
 *
 * Routing and prompt analytics ride the same call on purpose. Both need the
 * same thing — the request, read once, by something cheap — and a second call
 * would double the orchestration bill to learn what the first already knew.
 */

import {
  ORCHESTRATOR_ID,
  type CatalogModel,
  byId,
  formatCtx,
  orchestrator,
} from "./models";
import { type Prefs, blendedPrice, poolFor } from "./prefs";
import { type Usage, chutes, parseJson, readUsage } from "./chutes";

export type { Usage };

export type Score = {
  modelId: string;
  /** 0-100: how well this model would handle this specific request. */
  quality: number;
  note: string;
};

/** Buckets are fixed so a month of runs can be grouped without a taxonomy job. */
export const CATEGORIES = [
  "engineering",
  "data",
  "support",
  "sales-marketing",
  "operations",
  "legal-finance",
  "research",
  "writing",
  "personal",
  "other",
] as const;

export type Category = (typeof CATEGORIES)[number];

export type Scope = "work" | "outside" | "unclear";

/** What prompt analytics records about a request. Never the request itself. */
export type Intent = {
  scope: Scope;
  category: Category;
  /** 0-100 in the scope call. Low confidence is reported, not hidden. */
  confidence: number;
  /** Secrets, customer data or personal details visible in the request. */
  sensitive: boolean;
  /** One short line an admin can read in a list. */
  why: string;
};

export type Decision = {
  /** 0-100: how good the answer has to be for this request. */
  bar: number;
  reason: string;
  scores: Score[];
  intent: Intent;
  chosen: CatalogModel;
  /** Models that cleared the bar but cost more than the one picked. */
  rejected: { model: CatalogModel; quality: number }[];
  /** What the orchestrator call itself burned, as reported by Chutes. */
  usage: Usage;
  /** True when the user pinned a model and the pick was theirs, not ours. */
  pinned: boolean;
};

const SCHEMA = {
  type: "object",
  properties: {
    bar: { type: "integer" },
    reason: { type: "string" },
    scores: {
      type: "array",
      items: {
        type: "object",
        properties: {
          modelId: { type: "string" },
          quality: { type: "integer" },
          note: { type: "string" },
        },
        required: ["modelId", "quality", "note"],
        additionalProperties: false,
      },
    },
    intent: {
      type: "object",
      properties: {
        scope: { type: "string", enum: ["work", "outside", "unclear"] },
        category: { type: "string", enum: [...CATEGORIES] },
        confidence: { type: "integer" },
        sensitive: { type: "boolean" },
        why: { type: "string" },
      },
      required: ["scope", "category", "confidence", "sensitive", "why"],
      additionalProperties: false,
    },
  },
  required: ["bar", "reason", "scores", "intent"],
  additionalProperties: false,
};

function orgClause(prefs: Prefs) {
  const name = prefs.orgName.trim() || "the organisation";
  const what = prefs.orgContext.trim();

  if (!what) {
    return `You do not know what ${name} works on — no workspace description has been set. Judge "scope" only from the request itself, and say "unclear" whenever a request could plausibly belong to either side. Do not invent a company to test the request against.`;
  }

  return `${name} describes its work like this:

"""
${what}
"""

Judge "scope" against that description and nothing else.`;
}

function prompt(question: string, pool: CatalogModel[], prefs: Prefs, context: string) {
  const roster = pool
    .map((m) => {
      const traits = [
        `${m.tier} tier`,
        `$${m.inPer1M}/$${m.outPer1M} per 1M`,
        `${formatCtx(m.ctx)} context`,
        m.vision ? "vision" : null,
        m.video ? "video" : null,
        m.structured ? "tools + JSON" : "no tools, no JSON",
      ]
        .filter(Boolean)
        .join(", ");
      return `- ${m.id} (${m.label}; ${traits}) — ${m.goodAt}`;
    })
    .join("\n");

  return `You are the orchestrator of DemuxLLM. Every model below is served by Chutes, and they are the only models that exist for you — never name, suggest or score anything else.
${
  context
    ? `
Earlier in this conversation:

"""
${context}
"""

The request below may be a follow-up to that. Judge it in context — "now make it faster" inherits the difficulty of whatever came before it, and a bare "thanks" does not.
`
    : ""
}
A user has sent this request:

"""
${question}
"""

Candidate models:
${roster}

FIRST, score every candidate 0-100 on how well it would handle THIS specific request — capability fit only, ignore price entirely. A model that cannot hold a JSON schema or call a tool scores near zero on a request that needs one, however good its prose is. A model whose context window cannot hold the request scores zero.

SECOND, set "bar": the minimum score an answer to this request actually needs. Use these anchors, and do not drift below them:

- 90-100 — the answer will be executed or acted on, and being subtly wrong is expensive: code, queries, migrations, security, money, medical, legal, anything a customer sees unedited.
- 70-85 — the answer is read and judged by a person before it matters: explanation, analysis, design and UI advice, planning, comparison.
- 40-65 — conversation, greetings, simple lookups, formatting, rewording.

Difficulty counts as much as category. A one-line rename, a print statement, or a for-loop is not high-stakes merely because it is code — grade the request in front of you, not the field it belongs to. The top band is for work that is both consequential AND hard enough that a weaker model plausibly gets it wrong.

Two failure modes, both costly. A bar set too high spends frontier money on work any model finishes identically. A bar set too low ships a broken answer someone has to find later. When a request genuinely spans two bands, take the higher one.

THIRD, classify the request for the workspace's prompt analytics.

${orgClause(prefs)}

- "scope": "work" if the request is plainly part of that organisation's work, "outside" if it is personal or belongs to some other line of work entirely, "unclear" if an honest reader could not tell. Generic technical questions with no company detail in them are "unclear", not "work" — guessing costs an employee their benefit of the doubt.
- "category": the single closest bucket from the enum.
- "confidence": 0-100 on the scope call alone.
- "sensitive": true only if the request itself carries a credential, a customer's data, or a named person's private details. Discussing a sensitive topic is not the same as pasting sensitive data.
- "why": at most twelve words, addressed to an admin reading a list, and describing the KIND of request rather than quoting it.

"reason" is one short sentence, addressed to an engineer, explaining the bar. Each "note" is at most six words.`;
}

export async function decideRoute(
  apiKey: string,
  question: string,
  prefs: Prefs,
  opts: { context?: string; signal?: AbortSignal } = {},
): Promise<Decision> {
  const pool = poolFor(prefs);
  const text = prompt(question, pool, prefs, opts.context ?? "");

  const res = await chutes(
    apiKey,
    {
      model: ORCHESTRATOR_ID,
      messages: [{ role: "user", content: text }],
      temperature: 0,
      max_tokens: 1600,
      response_format: {
        type: "json_schema",
        json_schema: { name: "route", schema: SCHEMA, strict: true },
      },
    },
    {
      // Routing is classification. Paying for a reasoning trace to pick a model
      // costs more than the difference between the models being picked between.
      thinking: false,
      signal: opts.signal,
    },
  );

  const data = await res.json();
  const parsed = parseJson(data?.choices?.[0]?.message?.content ?? "") as {
    bar: number;
    reason: string;
    scores: Score[];
    intent: Intent;
  };

  const usage = readUsage(data?.usage, {
    inTok: Math.ceil(text.length / 4),
    outTok: 320,
  });

  // Score every eligible model, whether or not the orchestrator named it.
  const scores: Score[] = pool.map((m) => {
    const hit = parsed.scores?.find((s) => s.modelId === m.id);
    return {
      modelId: m.id,
      quality: Math.max(0, Math.min(100, hit?.quality ?? 0)),
      note: hit?.note ?? "",
    };
  });

  // The floor raises the model's bar; it never lowers it. A user asking for
  // more care than the request needs should get it — the reverse would let a
  // setting quietly authorise a worse answer than the task requires.
  const modelBar = Math.max(0, Math.min(100, parsed.bar));
  const bar = Math.max(modelBar, Math.round(prefs.qualityFloor * 100));

  const ranked = [...scores].sort((a, b) => b.quality - a.quality);
  const passing = scores
    .filter((s) => s.quality >= bar)
    .map((s) => ({ model: byId(s.modelId)!, quality: s.quality }))
    .sort((a, b) => blendedPrice(a.model) - blendedPrice(b.model));

  // A pinned model overrides the pick but not the scoring: the bar, the scores
  // and the classification are all still worth having, and the panel says
  // plainly that the choice was the user's rather than ours.
  const pin = prefs.pinnedModel ? byId(prefs.pinnedModel) : undefined;

  let chosen: CatalogModel;
  if (pin) {
    chosen = pin;
  } else if (prefs.preset === "best" || passing.length === 0) {
    // Nothing cleared the bar, or the user asked for the top score outright.
    chosen = byId(ranked[0].modelId)!;
  } else if (prefs.preset === "balanced") {
    // Prefer a little headroom over the bar, but not at any price: take the
    // cheapest model that clears by 5 points, else the cheapest that clears.
    chosen = (passing.find((p) => p.quality >= bar + 5) ?? passing[0]).model;
  } else {
    chosen = passing[0].model;
  }

  return {
    bar,
    reason: parsed.reason,
    scores,
    intent: normaliseIntent(parsed.intent),
    chosen,
    rejected: passing.filter((p) => p.model.id !== chosen.id),
    usage,
    pinned: Boolean(pin),
  };
}

/** A malformed classification becomes "unclear", never a confident guess. */
function normaliseIntent(intent: Intent | undefined): Intent {
  const scope: Scope[] = ["work", "outside", "unclear"];
  return {
    scope: scope.includes(intent?.scope as Scope) ? intent!.scope : "unclear",
    category: (CATEGORIES as readonly string[]).includes(intent?.category as string)
      ? intent!.category
      : "other",
    confidence: Math.max(0, Math.min(100, intent?.confidence ?? 0)),
    sensitive: intent?.sensitive === true,
    why: intent?.why ?? "",
  };
}

/** What the orchestrator call cost, priced on the model that ran it. */
export const orchestratorModel = orchestrator;
