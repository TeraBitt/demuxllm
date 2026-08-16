"use client";

/**
 * One run: orchestrate, pick, then answer with whatever tools and reasoning the
 * preferences allow. Both model calls are real, and both are priced on the token
 * counts Chutes reports rather than on a guess.
 */

import { type AgentEvent, type ChatMessage, runAgent } from "./agent";
import { type CatalogModel, baselineCost, costOf, orchestrator } from "./models";
import { type Prefs, thinkingFor, toolsFor } from "./prefs";
import { type Decision, decideRoute } from "./router";
import { TOOL_BY_NAME } from "./tools";

export type StepEvent = {
  id: string;
  label: string;
  detail: string;
  model?: CatalogModel;
  costUsd: number;
  baselineUsd: number;
  ms: number;
  status: "running" | "done";
};

export type RunResult = {
  answer: string;
  reasoning: string;
  decision: Decision;
  /** The Chutes model that produced the text. Always the one that was picked. */
  serving: string;
  costUsd: number;
  baselineUsd: number;
  toolRounds: number;
};

const SCOPE_DETAIL: Record<Decision["intent"]["scope"], string> = {
  work: "Company work",
  outside: "Outside company work",
  unclear: "Scope unclear",
};

export async function runOnce(opts: {
  apiKey: string;
  question: string;
  /** Prior turns, oldest first, already trimmed to the history window. */
  history: ChatMessage[];
  /** A short transcript tail the router reads so follow-ups route in context. */
  routerContext: string;
  prefs: Prefs;
  signal?: AbortSignal;
  onStep: (s: StepEvent) => void;
  onDecision: (d: Decision) => void;
  onEvent: (e: AgentEvent) => void;
}): Promise<RunResult> {
  const { apiKey, question, prefs, signal, onStep, onDecision, onEvent } = opts;

  /* 1. One small-model call: score the pool and classify the request. */
  onStep({
    id: "score",
    label: "Orchestrate",
    detail: `Reading the request on ${orchestrator().label}`,
    costUsd: 0,
    baselineUsd: 0,
    ms: 0,
    status: "running",
  });

  let startedAt = performance.now();
  const decision = await decideRoute(apiKey, question, prefs, {
    context: opts.routerContext,
    signal,
  });
  onDecision(decision);

  const { inTok: scoreIn, outTok: scoreOut } = decision.usage;
  const scoreCost = costOf(orchestrator(), scoreIn, scoreOut);
  const scoreBaseline = baselineCost(scoreIn, scoreOut);

  onStep({
    id: "score",
    label: "Orchestrate",
    detail: `Needs ${decision.bar}/100 — ${decision.reason}`,
    costUsd: scoreCost,
    baselineUsd: scoreBaseline,
    ms: Math.round(performance.now() - startedAt),
    status: "done",
  });

  /* 2. Classify — the same call already paid for, reported separately. */
  const { intent } = decision;
  onStep({
    id: "classify",
    label: "Classify",
    detail: `${SCOPE_DETAIL[intent.scope]} · ${intent.category}${
      intent.sensitive ? " · sensitive data in prompt" : ""
    }`,
    costUsd: 0,
    baselineUsd: 0,
    ms: 0,
    status: "done",
  });

  /* 3. Pick — arithmetic, so it costs nothing. */
  const cheaperRejects = decision.rejected.length;
  onStep({
    id: "pick",
    label: decision.pinned ? "Pinned model" : "Pick the model",
    detail: decision.pinned
      ? "Routing bypassed — you pinned this model"
      : cheaperRejects
        ? `Cheapest of ${cheaperRejects + 1} that clear the bar`
        : `Only model clearing ${decision.bar}/100`,
    model: decision.chosen,
    costUsd: 0,
    baselineUsd: 0,
    ms: 0,
    status: "done",
  });

  /* 4. Answer, on the model that was picked, with whatever it is allowed. */
  const tools = toolsFor(prefs, decision.chosen);
  const thinking = thinkingFor(prefs, decision.chosen, decision.bar);
  const equipment = [
    thinking ? "reasoning on" : "reasoning off",
    tools.length ? `${tools.length} tools` : "no tools",
  ].join(" · ");

  onStep({
    id: "answer",
    label: "Answer",
    detail: `${decision.chosen.label} — ${equipment}`,
    model: decision.chosen,
    costUsd: 0,
    baselineUsd: 0,
    ms: 0,
    status: "running",
  });

  startedAt = performance.now();

  // Tool calls get their own trace rows, so the run reads as what happened
  // rather than as one long "Answer" that silently did five things.
  const toolNames = new Map<string, string>();

  const {
    text: answer,
    reasoning,
    usage,
    toolRounds,
    truncated,
  } = await runAgent({
    apiKey,
    model: decision.chosen,
    messages: [...opts.history, { role: "user", content: question }],
    prefs,
    bar: decision.bar,
    signal,
    onEvent: (e) => {
      if (e.kind === "tool_start") {
        toolNames.set(e.id, e.name);
        onStep({
          id: `tool-${e.id}`,
          label: TOOL_BY_NAME.get(e.name)?.label ?? e.name,
          detail: TOOL_BY_NAME.get(e.name)?.running ?? "Running a tool",
          costUsd: 0,
          baselineUsd: 0,
          ms: 0,
          status: "running",
        });
      } else if (e.kind === "tool_end") {
        const name = toolNames.get(e.id) ?? "";
        onStep({
          id: `tool-${e.id}`,
          label: TOOL_BY_NAME.get(name)?.label ?? (name || "Tool"),
          detail: e.result.ok ? "Returned" : e.result.summary.slice(0, 90),
          costUsd: 0,
          baselineUsd: 0,
          ms: e.ms,
          status: "done",
        });
      }
      onEvent(e);
    },
  });

  const cost = costOf(decision.chosen, usage.inTok, usage.outTok);
  const base = baselineCost(usage.inTok, usage.outTok);

  onStep({
    id: "answer",
    label: "Answer",
    detail: truncated
      ? `${decision.chosen.label} — stopped after ${prefs.maxToolRounds} tool rounds`
      : `${decision.chosen.label} — ${equipment}${
          toolRounds ? ` · ${toolRounds} tool round${toolRounds === 1 ? "" : "s"}` : ""
        }`,
    model: decision.chosen,
    costUsd: cost,
    baselineUsd: base,
    ms: Math.round(performance.now() - startedAt),
    status: "done",
  });

  return {
    answer,
    reasoning,
    decision,
    serving: decision.chosen.id,
    costUsd: scoreCost + cost,
    baselineUsd: scoreBaseline + base,
    toolRounds,
  };
}
