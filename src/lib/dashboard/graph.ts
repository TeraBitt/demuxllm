/**
 * The orchestration, as an actual LangGraph rather than a promise chain.
 *
 *      classify ─▶ route ─┬─▶ search ─▶ generate ─▶ verify ─▶ END
 *                         └───────────▶ generate
 *
 * Worth being explicit about why a graph earns its place here: the interesting
 * claim of the product is that ONE user request is many model calls of very
 * different value, and a graph is the honest shape of that. Each node is a
 * separately routed, separately priced step, and the conditional edge means the
 * expensive path is only walked when classification asked for it.
 *
 * Cost is accumulated per node against what the same node would have cost on
 * the frontier model with a deep reasoning budget — that difference is the only
 * number the product is really selling.
 */

import { Annotation, END, START, StateGraph } from "@langchain/langgraph/web";
import type { Classification, Engine, SearchHit } from "./engine";
import {
  CATALOG,
  type CatalogModel,
  type Thinking,
  baselineCost,
  byId,
  estimateTokens,
  stepCost,
} from "./models";

export type NodeName = "classify" | "route" | "search" | "generate" | "verify";

export type StepEvent = {
  id: string;
  node: NodeName;
  label: string;
  detail: string;
  model?: CatalogModel;
  thinking?: Thinking;
  costUsd: number;
  baselineUsd: number;
  ms: number;
  status: "running" | "done";
};

export type RunResult = {
  answer: string;
  classification: Classification | null;
  chosen: CatalogModel | null;
  hits: SearchHit[];
  grade: { score: number; note: string } | null;
  costUsd: number;
  baselineUsd: number;
};

/* ------------------------------------------------------------- the router -- */

/**
 * Pure, and deliberately readable: this is the decision the product is named
 * after, so it should be arguable from the source rather than buried in a model
 * call. Three axes, in the order they eliminate candidates.
 */
export function pickModel(c: Classification, allowChutes: boolean): CatalogModel {
  const pool = CATALOG.filter((m) => allowChutes || m.provider === "gemini");
  const pick = (id: string, fallback: string) =>
    pool.find((m) => m.id === id) ?? pool.find((m) => m.id === fallback) ?? pool[0];

  // Anything customer-facing or genuinely hard goes to the top of the ladder.
  if (c.qualityFloor >= 0.9 || c.complexity >= 4) {
    return pick("gemini-3.1-pro-preview", "gemini-3.1-pro-preview");
  }

  // Multi-step work: cheap reasoning beats expensive reasoning when the floor allows.
  if (c.complexity >= 3 || c.thinking !== "off") {
    return c.qualityFloor < 0.85
      ? pick("Qwen/Qwen3-235B-A22B", "gemini-3.6-flash")
      : pick("gemini-3.6-flash", "gemini-3.6-flash");
  }

  // Mechanical work goes to the floor. Tool-shaped steps need a model that calls tools.
  if (c.kind === "write" || c.kind === "extract") {
    return pick("meta-llama/Llama-3.3-70B-Instruct", "gemini-3.5-flash-lite");
  }
  return pick("gemini-3.5-flash-lite", "gemini-3.5-flash-lite");
}

/* --------------------------------------------------------------- the graph -- */

const DemuxState = Annotation.Root({
  question: Annotation<string>({ reducer: (_, b) => b, default: () => "" }),
  classification: Annotation<Classification | null>({
    reducer: (_, b) => b,
    default: () => null,
  }),
  chosenId: Annotation<string>({ reducer: (_, b) => b, default: () => "" }),
  hits: Annotation<SearchHit[]>({ reducer: (_, b) => b, default: () => [] }),
  answer: Annotation<string>({ reducer: (_, b) => b, default: () => "" }),
  grade: Annotation<{ score: number; note: string } | null>({
    reducer: (_, b) => b,
    default: () => null,
  }),
});

type Ctx = {
  engine: Engine;
  allowChutes: boolean;
  onStep: (s: StepEvent) => void;
  onToken: (t: string) => void;
  /** Mutated as nodes complete; read once at the end. */
  ledger: { cost: number; baseline: number };
};

/** Emits a running step, runs the body, then emits the finished step. */
async function tracked<T>(
  ctx: Ctx,
  init: Omit<StepEvent, "costUsd" | "baselineUsd" | "ms" | "status">,
  body: () => Promise<{ value: T; inTok: number; outTok: number }>,
): Promise<T> {
  const startedAt = performance.now();
  ctx.onStep({ ...init, costUsd: 0, baselineUsd: 0, ms: 0, status: "running" });

  const { value, inTok, outTok } = await body();

  const thinking: Thinking = init.thinking ?? "off";
  const cost = init.model ? stepCost(init.model, inTok, outTok, thinking) : 0;
  const base = baselineCost(inTok, outTok, thinking);

  ctx.ledger.cost += cost;
  ctx.ledger.baseline += base;

  ctx.onStep({
    ...init,
    costUsd: cost,
    baselineUsd: base,
    ms: Math.round(performance.now() - startedAt),
    status: "done",
  });
  return value;
}

export function buildGraph(ctx: Ctx) {
  const classifier = byId("gemini-3.5-flash-lite")!;

  return new StateGraph(DemuxState)
    .addNode("classify", async (s) => {
      const classification = await tracked(
        ctx,
        {
          id: "classify",
          node: "classify",
          label: "Classify the request",
          detail: "What kind of work is this, and how good must the answer be?",
          model: classifier,
          thinking: "off",
        },
        async () => {
          const value = await ctx.engine.classify(s.question);
          return { value, inTok: estimateTokens(s.question) + 180, outTok: 60 };
        },
      );
      return { classification };
    })

    .addNode("route", async (s) => {
      const c = s.classification!;
      const chosen = pickModel(c, ctx.allowChutes);
      // Routing is arithmetic on our side, not a model call — it costs nothing,
      // and showing that as a zero-cost step is the point.
      await tracked(
        ctx,
        {
          id: "route",
          node: "route",
          label: "Pick the model",
          detail: c.rationale,
          thinking: "off",
        },
        async () => ({ value: null, inTok: 0, outTok: 0 }),
      );
      return { chosenId: chosen.id };
    })

    .addNode("search", async (s) => {
      const hits = await tracked(
        ctx,
        {
          id: "search",
          node: "search",
          label: "Search the web",
          detail: "Answer depends on information newer than training.",
          model: classifier,
          thinking: "off",
        },
        async () => {
          const value = await ctx.engine.search(s.question);
          return { value, inTok: estimateTokens(s.question) + 40, outTok: 220 };
        },
      );
      return { hits };
    })

    .addNode("generate", async (s) => {
      const model = byId(s.chosenId)!;
      const c = s.classification!;
      const context = s.hits
        .map((h) => `- ${h.title}: ${h.snippet}${h.url ? ` (${h.url})` : ""}`)
        .join("\n");

      const answer = await tracked(
        ctx,
        {
          id: "generate",
          node: "generate",
          label: "Answer",
          detail: `${model.label} · thinking ${c.thinking}`,
          model,
          thinking: c.thinking,
        },
        async () => {
          const value = await ctx.engine.answer(
            model.id,
            s.question,
            context,
            ctx.onToken,
          );
          return {
            value,
            inTok: estimateTokens(s.question + context) + 120,
            outTok: estimateTokens(value),
          };
        },
      );
      return { answer };
    })

    .addNode("verify", async (s) => {
      const grade = await tracked(
        ctx,
        {
          id: "verify",
          node: "verify",
          label: "Grade the answer",
          detail: "Cheap second opinion against the floor set at classification.",
          model: classifier,
          thinking: "off",
        },
        async () => {
          const value = await ctx.engine.verify(s.question, s.answer);
          return { value, inTok: estimateTokens(s.answer) + 80, outTok: 40 };
        },
      );
      return { grade };
    })

    .addEdge(START, "classify")
    .addEdge("classify", "route")
    .addConditionalEdges("route", (s) =>
      s.classification?.needsFreshData ? "search" : "generate",
    )
    .addEdge("search", "generate")
    .addEdge("generate", "verify")
    .addEdge("verify", END)
    .compile();
}

export async function runDemux(opts: {
  question: string;
  engine: Engine;
  allowChutes: boolean;
  onStep: (s: StepEvent) => void;
  onToken: (t: string) => void;
}): Promise<RunResult> {
  const ctx: Ctx = { ...opts, ledger: { cost: 0, baseline: 0 } };
  const graph = buildGraph(ctx);
  const final = await graph.invoke({ question: opts.question });

  return {
    answer: final.answer,
    classification: final.classification,
    chosen: byId(final.chosenId) ?? null,
    hits: final.hits,
    grade: final.grade,
    costUsd: ctx.ledger.cost,
    baselineUsd: ctx.ledger.baseline,
  };
}
