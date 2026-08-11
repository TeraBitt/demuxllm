"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { Classification, SearchHit } from "./engine";
import { geminiEngine, simEngine } from "./engine";
import { type StepEvent, runDemux } from "./graph";
import { useKeys } from "./keys";
import type { CatalogModel } from "./models";

export type Turn = {
  id: string;
  question: string;
  answer: string;
  steps: StepEvent[];
  classification: Classification | null;
  chosen: CatalogModel | null;
  hits: SearchHit[];
  grade: { score: number; note: string } | null;
  costUsd: number;
  baselineUsd: number;
  status: "running" | "done" | "error";
  error?: string;
};

/**
 * One conversation, held in memory for the length of the visit.
 *
 * Streaming into React state is done by replacing the one turn being written
 * rather than the whole list, so a long answer does not re-render every earlier
 * message on each token.
 */
export function useSession() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const counter = useRef(0);
  const { geminiKey, hasGemini, hasChutes } = useKeys();

  const patch = useCallback((id: string, next: Partial<Turn>) => {
    setTurns((prev) =>
      prev.map((t) => (t.id === id ? { ...t, ...next } : t)),
    );
  }, []);

  const ask = useCallback(
    async (question: string) => {
      if (busy) return;
      setBusy(true);

      const id = `turn-${++counter.current}`;
      const turn: Turn = {
        id,
        question,
        answer: "",
        steps: [],
        classification: null,
        chosen: null,
        hits: [],
        grade: null,
        costUsd: 0,
        baselineUsd: 0,
        status: "running",
      };
      setTurns((prev) => [...prev, turn]);

      const engine = hasGemini ? geminiEngine(geminiKey) : simEngine();
      let streamed = "";

      try {
        const result = await runDemux({
          question,
          engine,
          allowChutes: hasChutes,
          onStep: (step) =>
            setTurns((prev) =>
              prev.map((t) => {
                if (t.id !== id) return t;
                const rest = t.steps.filter((s) => s.id !== step.id);
                return { ...t, steps: [...rest, step] };
              }),
            ),
          onToken: (token) => {
            streamed += token;
            patch(id, { answer: streamed });
          },
        });

        patch(id, {
          answer: result.answer || streamed,
          classification: result.classification,
          chosen: result.chosen,
          hits: result.hits,
          grade: result.grade,
          costUsd: result.costUsd,
          baselineUsd: result.baselineUsd,
          status: "done",
        });
      } catch (err) {
        patch(id, {
          status: "error",
          error:
            err instanceof Error
              ? err.message
              : "The provider rejected the request.",
        });
      } finally {
        setBusy(false);
      }
    },
    [busy, geminiKey, hasChutes, hasGemini, patch],
  );

  const reset = useCallback(() => setTurns([]), []);

  const totals = useMemo(
    () => ({
      runs: turns.filter((t) => t.status === "done").length,
      cost: turns.reduce((n, t) => n + t.costUsd, 0),
      baseline: turns.reduce((n, t) => n + t.baselineUsd, 0),
    }),
    [turns],
  );

  return { turns, busy, ask, reset, totals, live: hasGemini };
}
