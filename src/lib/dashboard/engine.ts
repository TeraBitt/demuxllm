/**
 * The one place that knows whether this dashboard is talking to a real model.
 *
 * Everything above this file — the LangGraph orchestration, the trace, the cost
 * arithmetic, the UI — runs identically in both modes. Only the four methods
 * below change. That is deliberate: the demo has to be honest when it is
 * simulating, and the way to keep it honest is to make simulation a swap of the
 * leaf calls rather than a separate code path that can drift.
 *
 * `simEngine` is deterministic. Same question in, same route and same answer
 * out, so a demo can be rehearsed. It seeds off the question text rather than
 * a clock or a random source.
 */

import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import * as z from "zod";
import { CATALOG, type Thinking } from "./models";

export type Kind = "chat" | "extract" | "reason" | "write" | "code" | "lookup";

export type Classification = {
  kind: Kind;
  /** 1 trivial … 5 genuinely hard. */
  complexity: number;
  needsFreshData: boolean;
  qualityFloor: number;
  thinking: Thinking;
  rationale: string;
};

export type SearchHit = { title: string; snippet: string; url: string };

export type Engine = {
  /** True when a real provider is behind this. */
  live: boolean;
  classify(question: string): Promise<Classification>;
  search(query: string): Promise<SearchHit[]>;
  answer(
    modelId: string,
    question: string,
    context: string,
    onToken: (t: string) => void,
  ): Promise<string>;
  verify(question: string, answer: string): Promise<{ score: number; note: string }>;
};

/* ----------------------------------------------------------------- schema -- */

const ClassificationSchema = z.object({
  kind: z
    .enum(["chat", "extract", "reason", "write", "code", "lookup"])
    .describe("What kind of work this request actually is"),
  complexity: z.number().min(1).max(5).describe("1 trivial, 5 genuinely hard"),
  needsFreshData: z
    .boolean()
    .describe("True only if answering well needs information from after training"),
  qualityFloor: z
    .number()
    .min(0)
    .max(1)
    .describe("How good the answer has to be. Customer-facing work is 0.9+"),
  thinking: z
    .enum(["off", "short", "deep"])
    .describe("Reasoning budget to buy before answering"),
  rationale: z.string().describe("One short sentence, addressed to an engineer"),
});

const CLASSIFY_PROMPT = `You are the routing layer of DemuxLLM. Classify the user's request so a cheaper model can be chosen for it. Be strict: most requests are simpler than they look, and buying reasoning that does not change the answer is the most common way to waste money. Only set needsFreshData when the answer genuinely depends on information newer than your training data.`;

/* -------------------------------------------------------------- simulated -- */

/** Deterministic 32-bit hash, so a given question always demos the same way. */
function seed(text: string) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const FRESH = /price|pricing|cost|latest|today|current|new|release|2025|2026|news|benchmark/i;
const CODE = /code|function|bug|typescript|python|sql|regex|refactor|stack trace/i;
const WRITE = /write|draft|email|post|summar|rewrite|translate/i;
const HARD = /why|prove|design|architect|trade-?off|compare|analy|strategy/i;

function simClassify(q: string): Classification {
  const s = seed(q);
  const needsFreshData = FRESH.test(q);
  const kind: Kind = CODE.test(q)
    ? "code"
    : needsFreshData
      ? "lookup"
      : WRITE.test(q)
        ? "write"
        : HARD.test(q)
          ? "reason"
          : q.length < 60
            ? "chat"
            : "extract";

  const complexity =
    kind === "reason" || kind === "code" ? 3 + (s % 2) : kind === "chat" ? 1 : 2;

  return {
    kind,
    complexity,
    needsFreshData,
    qualityFloor: kind === "write" || kind === "reason" ? 0.88 : 0.72,
    thinking: complexity >= 4 ? "deep" : complexity >= 3 ? "short" : "off",
    rationale:
      kind === "chat"
        ? "Short conversational turn — no reasoning budget needed."
        : kind === "lookup"
          ? "Depends on information newer than training; search first, then answer small."
          : kind === "code"
            ? "Code work: correctness matters more than prose, so quality floor stays mid."
            : kind === "write"
              ? "Customer-facing prose — floor raised, reasoning kept short."
              : "Multi-step reasoning; worth buying a thinking budget.",
  };
}

const SIM_HITS: SearchHit[] = [
  {
    title: "Gemini API pricing",
    snippet:
      "Gemini 3 Flash is $0.50 per 1M input tokens and $3.00 per 1M output. Flash Lite is $0.10 / $0.40. 3.1 Pro is $1.40 / $11.00.",
    url: "https://ai.google.dev/gemini-api/docs/pricing",
  },
  {
    title: "Chutes — open model inference",
    snippet:
      "DeepSeek V3 at $0.27 / $1.10 per 1M tokens; Qwen3 235B at $0.20 / $0.60; Llama 3.3 70B at $0.10 / $0.28.",
    url: "https://chutes.ai",
  },
  {
    title: "Routing economics",
    snippet:
      "Across mixed workloads, 60-80% of calls are answered identically by a mid-tier model, and reasoning budget is the larger share of the bill on agent traffic.",
    url: "https://demuxllm.com/benchmark",
  },
];

const SIM_PARAGRAPHS = [
  "Short version: you are almost certainly paying frontier prices for work a mid-tier model finishes identically.",
  "The bill splits in two. There is which model answered, and there is how much reasoning it bought before answering — the second is billed at output rates and never appears in the response, so it is the half people miss.",
  "On this request the router picked below the frontier tier and kept the reasoning budget short, because nothing in the question needed a longer one. The saving on the right is that decision, priced.",
];

export function simEngine(): Engine {
  return {
    live: false,
    async classify(q) {
      await wait(260);
      return simClassify(q);
    },
    async search() {
      await wait(520);
      return SIM_HITS;
    },
    async answer(_modelId, q, context, onToken) {
      const intro = context
        ? `Working from what search returned:\n\n`
        : "";
      const body = [intro, ...SIM_PARAGRAPHS].join(context ? "" : "\n\n");
      const text = `${body}\n\n_Simulated answer — add a Gemini key in BYOK to get a real one for "${q.slice(0, 60)}"._`;
      for (const chunk of text.match(/\S+\s*/g) ?? []) {
        await wait(14);
        onToken(chunk);
      }
      return text;
    },
    async verify() {
      await wait(200);
      return { score: 0.91, note: "Meets the floor set at classification." };
    },
  };
}

/* ------------------------------------------------------------------ live -- */

function chat(apiKey: string, model: string, temperature = 0.4) {
  return new ChatGoogleGenerativeAI({ apiKey, model, temperature });
}

/**
 * Search is Gemini's own grounding rather than a separate search vendor, so the
 * demo needs exactly one key. Called through REST because the grounding tool
 * shape is a provider concern and pinning it here keeps it away from the
 * LangChain version.
 */
async function groundedSearch(apiKey: string, query: string): Promise<SearchHit[]> {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=${encodeURIComponent(apiKey)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: query }] }],
        tools: [{ google_search: {} }],
      }),
    },
  );
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  const data = await res.json();

  const chunks =
    data?.candidates?.[0]?.groundingMetadata?.groundingChunks ?? [];
  const hits: SearchHit[] = chunks
    .filter((c: { web?: unknown }) => c.web)
    .slice(0, 4)
    .map((c: { web: { title?: string; uri?: string } }) => ({
      title: c.web.title ?? "Source",
      snippet: "",
      url: c.web.uri ?? "",
    }));

  const summary: string =
    data?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text ?? "").join("") ?? "";

  if (hits.length === 0 && summary) {
    return [{ title: "Search result", snippet: summary.slice(0, 400), url: "" }];
  }
  if (hits.length && summary) hits[0].snippet = summary.slice(0, 400);
  return hits;
}

export function geminiEngine(apiKey: string): Engine {
  return {
    live: true,
    async classify(q) {
      const model = chat(apiKey, "gemini-3.5-flash-lite", 0);
      const structured = model.withStructuredOutput(ClassificationSchema, {
        name: "classify",
      });
      return (await structured.invoke([
        { role: "system", content: CLASSIFY_PROMPT },
        { role: "user", content: q },
      ])) as Classification;
    },

    search: (q) => groundedSearch(apiKey, q),

    async answer(modelId, q, context, onToken) {
      const known = CATALOG.find((m) => m.id === modelId);
      // Chutes models have no key path in this demo, so live answers always come
      // from the nearest Gemini rung. The trace still shows what was chosen.
      const geminiId =
        known?.provider === "gemini" ? modelId : "gemini-3.6-flash";

      const model = chat(apiKey, geminiId);

      // Gemini takes exactly one system instruction and it must come first, so
      // search context is folded into it rather than sent as a second system
      // turn — which is what "System message should be the first one" meant.
      const system = [
        "You are the assistant behind DemuxLLM's dashboard. Answer directly and concisely in markdown. No preamble, no restating the question.",
        context && `Use these search results, and cite them where relevant:\n${context}`,
      ]
        .filter(Boolean)
        .join("\n\n");

      const messages = [
        { role: "system" as const, content: system },
        { role: "user" as const, content: q },
      ];

      let out = "";
      for await (const chunk of await model.stream(messages)) {
        const t = typeof chunk.content === "string" ? chunk.content : "";
        if (t) {
          out += t;
          onToken(t);
        }
      }
      return out;
    },

    async verify(q, answer) {
      const model = chat(apiKey, "gemini-3.5-flash-lite", 0);
      const structured = model.withStructuredOutput(
        z.object({
          score: z.number().min(0).max(1),
          note: z.string().describe("One short clause"),
        }),
        { name: "grade" },
      );
      return (await structured.invoke([
        {
          role: "system",
          content:
            "Grade whether the answer actually addresses the question. Be terse.",
        },
        { role: "user", content: `Q: ${q}\n\nA: ${answer.slice(0, 2000)}` },
      ])) as { score: number; note: string };
    },
  };
}
