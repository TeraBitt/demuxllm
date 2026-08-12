"use client";

import { useCallback, useRef, useState } from "react";
import { useKeys } from "./keys";
import { recordRun, topicFor } from "./history";
import { usePrefs } from "./prefs";
import type { CatalogModel } from "./models";
import type { Decision } from "./router";
import { type StepEvent, runOnce } from "./run";

export type Turn = {
  id: string;
  question: string;
  answer: string;
  steps: StepEvent[];
  decision: Decision | null;
  chosen: CatalogModel | null;
  serving: string | null;
  costUsd: number;
  baselineUsd: number;
  status: "running" | "done" | "error";
  error?: string;
};

/** One conversation, held in memory for the length of the visit. */
export function useSession() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const counter = useRef(0);
  const { chutesKey, hasChutes } = useKeys();
  const { prefs } = usePrefs();

  const patch = useCallback((id: string, next: Partial<Turn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...next } : t)));
  }, []);

  const ask = useCallback(
    async (question: string) => {
      if (busy) return;
      setBusy(true);

      const id = `turn-${++counter.current}`;
      setTurns((prev) => [
        ...prev,
        {
          id,
          question,
          answer: "",
          steps: [],
          decision: null,
          chosen: null,
          serving: null,
          costUsd: 0,
          baselineUsd: 0,
          status: "running",
        },
      ]);

      if (!hasChutes) {
        patch(id, {
          status: "error",
          error: "Add a Chutes key under Settings — the router runs on a real model call.",
        });
        setBusy(false);
        return;
      }

      const startedAt = Date.now();
      let streamed = "";
      try {
        const result = await runOnce({
          apiKey: chutesKey,
          question,
          prefs,
          onStep: (step) =>
            setTurns((prev) =>
              prev.map((t) =>
                t.id === id
                  ? { ...t, steps: [...t.steps.filter((s) => s.id !== step.id), step] }
                  : t,
              ),
            ),
          onDecision: (decision) => patch(id, { decision, chosen: decision.chosen }),
          onToken: (token) => {
            streamed += token;
            patch(id, { answer: streamed });
          },
        });

        patch(id, {
          answer: result.answer || streamed,
          decision: result.decision,
          chosen: result.decision.chosen,
          serving: result.serving,
          costUsd: result.costUsd,
          baselineUsd: result.baselineUsd,
          status: "done",
        });

        const chosen = result.decision.chosen;
        const { intent } = result.decision;
        recordRun({
          at: Date.now(),
          modelId: chosen.id,
          modelLabel: chosen.label,
          tier: chosen.tier,
          topic: topicFor(question, intent.sensitive, intent.why),
          bar: result.decision.bar,
          quality:
            result.decision.scores.find((s) => s.modelId === chosen.id)?.quality ?? 0,
          costUsd: result.costUsd,
          baselineUsd: result.baselineUsd,
          ms: Date.now() - startedAt,
          scope: intent.scope,
          category: intent.category,
          confidence: intent.confidence,
          sensitive: intent.sensitive,
        });
      } catch (err) {
        patch(id, {
          status: "error",
          error: err instanceof Error ? err.message : "The provider rejected the request.",
        });
      } finally {
        setBusy(false);
      }
    },
    [busy, chutesKey, hasChutes, patch, prefs],
  );

  const reset = useCallback(() => setTurns([]), []);

  return { turns, busy, ask, reset, live: hasChutes };
}
