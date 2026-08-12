/**
 * One run: orchestrate, pick, answer. Both model calls are real, and both are
 * priced on the token counts Chutes reports rather than on a guess.
 */

import { type CatalogModel, baselineCost, costOf, orchestrator } from "./models";
import type { Prefs } from "./prefs";
import { type Decision, decideRoute, streamAnswer } from "./router";

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
  decision: Decision;
  /** The Chutes model that produced the text. Always the one that was picked. */
  serving: string;
  costUsd: number;
  baselineUsd: number;
};

const SCOPE_DETAIL: Record<Decision["intent"]["scope"], string> = {
  work: "Company work",
  outside: "Outside company work",
  unclear: "Scope unclear",
};

export async function runOnce(opts: {
  apiKey: string;
  question: string;
  prefs: Prefs;
  onStep: (s: StepEvent) => void;
  onDecision: (d: Decision) => void;
  onToken: (t: string) => void;
}): Promise<RunResult> {
  const { apiKey, question, prefs, onStep, onDecision, onToken } = opts;

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
  const decision = await decideRoute(apiKey, question, prefs);
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
    label: "Pick the model",
    detail: cheaperRejects
      ? `Cheapest of ${cheaperRejects + 1} that clear the bar`
      : `Only model clearing ${decision.bar}/100`,
    model: decision.chosen,
    costUsd: 0,
    baselineUsd: 0,
    ms: 0,
    status: "done",
  });

  /* 4. Answer, on the model that was picked. */
  onStep({
    id: "answer",
    label: "Answer",
    detail: `Served by ${decision.chosen.label}`,
    model: decision.chosen,
    costUsd: 0,
    baselineUsd: 0,
    ms: 0,
    status: "running",
  });

  startedAt = performance.now();
  const { text: answer, usage } = await streamAnswer(
    apiKey,
    decision.chosen,
    question,
    onToken,
  );

  const cost = costOf(decision.chosen, usage.inTok, usage.outTok);
  const base = baselineCost(usage.inTok, usage.outTok);

  onStep({
    id: "answer",
    label: "Answer",
    detail: `Served by ${decision.chosen.label}`,
    model: decision.chosen,
    costUsd: cost,
    baselineUsd: base,
    ms: Math.round(performance.now() - startedAt),
    status: "done",
  });

  return {
    answer,
    decision,
    serving: decision.chosen.id,
    costUsd: scoreCost + cost,
    baselineUsd: scoreBaseline + base,
  };
}
