"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useKeys } from "./keys";
import { recordRun, topicFor } from "./history";
import { readPrefs, usePrefs } from "./prefs";
import { type Chat, saveChat, titleFor } from "./conversations";
import type { CatalogModel } from "./models";
import type { ChatMessage } from "./agent";
import type { Decision } from "./router";
import type { ToolResult } from "./tools";
import { type StepEvent, runOnce } from "./run";

/**
 * One conversation and the run loop that fills it.
 *
 * An answer is a *sequence*, not a string: the model may reason, call a tool,
 * say a sentence, call another tool and then finish. Storing it as ordered parts
 * is what lets the transcript show that sequence in the order it happened
 * instead of collapsing it into a paragraph with a spinner above it.
 *
 * Tokens arrive faster than the screen refreshes, so parts are mutated on a ref
 * and published once per animation frame. Setting state per token would rerender
 * the whole transcript sixty times a second and stutter exactly when the demo is
 * being watched.
 */

export type Part =
  | { kind: "reasoning"; text: string }
  | { kind: "text"; text: string }
  | {
      kind: "tool";
      id: string;
      name: string;
      args: string;
      result?: ToolResult;
      ms?: number;
    };

export type Turn = {
  id: string;
  question: string;
  parts: Part[];
  steps: StepEvent[];
  decision: Decision | null;
  chosen: CatalogModel | null;
  costUsd: number;
  baselineUsd: number;
  /** Wall-clock spent producing the reasoning trace, for the "thought for" line. */
  thinkingMs: number;
  status: "running" | "done" | "error" | "stopped";
  error?: string;
};

export const answerOf = (turn: Turn) =>
  turn.parts
    .filter((p): p is Extract<Part, { kind: "text" }> => p.kind === "text")
    .map((p) => p.text)
    .join("");

export const reasoningOf = (turn: Turn) =>
  turn.parts
    .filter((p): p is Extract<Part, { kind: "reasoning" }> => p.kind === "reasoning")
    .map((p) => p.text)
    .join("");

const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

/**
 * What the model is re-sent as context. Reasoning and tool chatter are dropped:
 * a model does not need last turn's private thinking, and re-sending it would
 * pay input tokens twice for something it already concluded.
 */
function toMessages(turns: Turn[], window: number): ChatMessage[] {
  if (window <= 0) return [];
  const out: ChatMessage[] = [];
  for (const t of turns.slice(-window)) {
    const answer = answerOf(t).trim();
    if (t.status !== "done" || !answer) continue;
    out.push({ role: "user", content: t.question });
    out.push({ role: "assistant", content: answer });
  }
  return out;
}

/** A short tail for the router, so a follow-up is graded as a follow-up. */
function routerContext(turns: Turn[]) {
  return turns
    .slice(-2)
    .filter((t) => t.status === "done")
    .map((t) => `User: ${t.question.slice(0, 300)}\nAssistant: ${answerOf(t).slice(0, 300)}`)
    .join("\n\n");
}

export function useSession() {
  const [chatId, setChatId] = useState(newId);
  const [title, setTitle] = useState("New chat");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const { chutesKey, hasChutes } = useKeys();
  const { prefs } = usePrefs();

  const abort = useRef<AbortController | null>(null);
  /** The live turn's parts, mutated per token and published per frame. */
  const live = useRef<{ id: string; parts: Part[]; frame: number | null }>({
    id: "",
    parts: [],
    frame: null,
  });
  // What `ask` and `regenerate` read when they fire, which is always after a
  // commit — so the effect that fills it has already run.
  const turnsRef = useRef<Turn[]>([]);
  useEffect(() => {
    turnsRef.current = turns;
  }, [turns]);

  useEffect(() => {
    return () => {
      abort.current?.abort();
      if (live.current.frame !== null) cancelAnimationFrame(live.current.frame);
    };
  }, []);

  const patch = useCallback((id: string, next: Partial<Turn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...next } : t)));
  }, []);

  /** Publish the mutated parts array at most once per frame. */
  const schedule = useCallback((id: string) => {
    if (live.current.frame !== null) return;
    live.current.frame = requestAnimationFrame(() => {
      live.current.frame = null;
      const parts = [...live.current.parts];
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, parts } : t)));
    });
  }, []);

  const flush = useCallback((id: string) => {
    if (live.current.frame !== null) {
      cancelAnimationFrame(live.current.frame);
      live.current.frame = null;
    }
    const parts = [...live.current.parts];
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, parts } : t)));
  }, []);

  const run = useCallback(
    async (question: string, priorTurns: Turn[]) => {
      // Read prefs at send time, not render time: a slider moved while an
      // answer was streaming should govern the next answer, not this one.
      const current = readPrefs();

      const id = newId();
      const turn: Turn = {
        id,
        question,
        parts: [],
        steps: [],
        decision: null,
        chosen: null,
        costUsd: 0,
        baselineUsd: 0,
        thinkingMs: 0,
        status: "running",
      };

      // Drop any frame the previous run left scheduled — it would publish this
      // run's parts under the last run's id.
      if (live.current.frame !== null) cancelAnimationFrame(live.current.frame);
      live.current = { id, parts: [], frame: null };
      setTurns([...priorTurns, turn]);
      setBusy(true);

      if (!hasChutes) {
        patch(id, {
          status: "error",
          error: "Add a Chutes key under Settings — the router runs on a real model call.",
        });
        setBusy(false);
        return;
      }

      const controller = new AbortController();
      abort.current = controller;

      const startedAt = Date.now();
      let thinkingStartedAt = 0;

      try {
        const result = await runOnce({
          apiKey: chutesKey,
          question,
          history: toMessages(priorTurns, current.historyTurns),
          routerContext: routerContext(priorTurns),
          prefs: current,
          signal: controller.signal,
          onStep: (step) =>
            setTurns((prev) =>
              prev.map((t) =>
                t.id === id
                  ? { ...t, steps: [...t.steps.filter((s) => s.id !== step.id), step] }
                  : t,
              ),
            ),
          onDecision: (decision) => patch(id, { decision, chosen: decision.chosen }),
          onEvent: (e) => {
            const parts = live.current.parts;
            const last = parts[parts.length - 1];

            if (e.kind === "reasoning") {
              if (!thinkingStartedAt) thinkingStartedAt = performance.now();
              if (last?.kind === "reasoning") last.text += e.text;
              else parts.push({ kind: "reasoning", text: e.text });
            } else if (e.kind === "text") {
              if (thinkingStartedAt) {
                patch(id, { thinkingMs: Math.round(performance.now() - thinkingStartedAt) });
                thinkingStartedAt = 0;
              }
              if (last?.kind === "text") last.text += e.text;
              else parts.push({ kind: "text", text: e.text });
            } else if (e.kind === "tool_start") {
              parts.push({ kind: "tool", id: e.id, name: e.name, args: e.args });
            } else if (e.kind === "tool_end") {
              const call = parts.find(
                (p): p is Extract<Part, { kind: "tool" }> => p.kind === "tool" && p.id === e.id,
              );
              if (call) {
                call.result = e.result;
                call.ms = e.ms;
              }
            } else {
              return;
            }
            schedule(id);
          },
        });

        flush(id);
        patch(id, {
          decision: result.decision,
          chosen: result.decision.chosen,
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
          thought: live.current.parts.some((p) => p.kind === "reasoning"),
          toolCalls: live.current.parts.filter((p) => p.kind === "tool").length,
        });
      } catch (err) {
        flush(id);
        const stopped = err instanceof DOMException && err.name === "AbortError";
        patch(id, {
          status: stopped ? "stopped" : "error",
          error: stopped
            ? undefined
            : err instanceof Error
              ? err.message
              : "The provider rejected the request.",
        });
      } finally {
        abort.current = null;
        setBusy(false);
      }
    },
    [chutesKey, flush, hasChutes, patch, schedule],
  );

  const ask = useCallback(
    (question: string) => {
      if (busy) return;
      if (!turnsRef.current.length) setTitle(titleFor(question));
      void run(question, turnsRef.current);
    },
    [busy, run],
  );

  /** Re-run the last question with whatever the settings say now. */
  const regenerate = useCallback(() => {
    if (busy) return;
    const all = turnsRef.current;
    const last = all[all.length - 1];
    if (!last) return;
    void run(last.question, all.slice(0, -1));
  }, [busy, run]);

  const stop = useCallback(() => abort.current?.abort(), []);

  /* Persist whenever a turn settles, so a refresh keeps the conversation. */
  useEffect(() => {
    if (!turns.length || busy) return;
    if (turns.every((t) => t.status === "running")) return;
    saveChat({ id: chatId, title, at: Date.now(), turns });
  }, [busy, chatId, title, turns]);

  const reset = useCallback(() => {
    abort.current?.abort();
    setChatId(newId());
    setTitle("New chat");
    setTurns([]);
  }, []);

  const open = useCallback((chat: Chat) => {
    abort.current?.abort();
    setChatId(chat.id);
    setTitle(chat.title);
    setTurns(chat.turns);
  }, []);

  return {
    chatId,
    title,
    turns,
    busy,
    ask,
    stop,
    regenerate,
    reset,
    open,
    live: hasChutes,
    prefs,
  };
}
