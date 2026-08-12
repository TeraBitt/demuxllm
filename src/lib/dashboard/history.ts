"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * Completed runs, kept in localStorage so the dashboard has something true to
 * show. Recording only what a chart needs — no prompts, no answers — keeps a
 * shared browser from turning an analytics view into a transcript leak.
 *
 * Prompt analytics is the sharp edge here. An admin needs to know how much of
 * the workspace's spend is company work; they do not need to read the requests
 * to find out. So the classification is stored and the request is not, and a
 * request the orchestrator flagged as carrying sensitive data loses even its
 * opening words in favour of the orchestrator's paraphrase.
 */

import type { Category, Scope } from "./router";

const STORAGE_KEY = "demux.history";
const LIMIT = 500;

export type RunRecord = {
  at: number;
  modelId: string;
  modelLabel: string;
  tier: "open" | "mid" | "frontier";
  /** First few words of the request, or a paraphrase where it was sensitive. */
  topic: string;
  bar: number;
  quality: number;
  costUsd: number;
  baselineUsd: number;
  ms: number;
  scope: Scope;
  category: Category;
  /** Confidence in the scope call, 0-100. */
  confidence: number;
  sensitive: boolean;
};

/** What lands in the recent-routes list. Never a sensitive request's own words. */
export function topicFor(question: string, sensitive: boolean, why: string) {
  if (sensitive) return why || "Redacted — flagged as sensitive";
  return question.split(/\s+/).slice(0, 7).join(" ");
}

let snapshot: RunRecord[] | null = null;
const listeners = new Set<() => void>();
const EMPTY: RunRecord[] = [];

function read(): RunRecord[] {
  if (snapshot) return snapshot;
  if (typeof window === "undefined") return EMPTY;
  let next: RunRecord[];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    next = raw ? (JSON.parse(raw) as RunRecord[]) : EMPTY;
  } catch {
    next = EMPTY;
  }
  snapshot = next;
  return next;
}

function commit(next: RunRecord[]) {
  snapshot = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* private browsing — the in-memory copy still drives this session */
  }
  listeners.forEach((l) => l());
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

export function recordRun(run: RunRecord) {
  commit([...read(), run].slice(-LIMIT));
}

export function useHistory() {
  const runs = useSyncExternalStore(subscribe, read, () => EMPTY);
  const clear = useCallback(() => commit([]), []);
  return { runs, clear };
}

/** Bucket runs into the last `days` calendar days, oldest first. */
export function byDay(runs: RunRecord[], days: number, now: number) {
  const day = 86_400_000;
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);

  return Array.from({ length: days }, (_, i) => {
    const from = start.getTime() - (days - 1 - i) * day;
    const inDay = runs.filter((r) => r.at >= from && r.at < from + day);
    return {
      at: from,
      runs: inDay.length,
      cost: inDay.reduce((n, r) => n + r.costUsd, 0),
      baseline: inDay.reduce((n, r) => n + r.baselineUsd, 0),
    };
  });
}

/**
 * The prompt-analytics roll-up: where the workspace's money went, split by
 * whether the request was company work. Spend is the unit rather than counts,
 * because a hundred greetings and one migration are not the same question.
 */
export function analyse(runs: RunRecord[]) {
  const spend = (rs: RunRecord[]) => rs.reduce((n, r) => n + r.costUsd, 0);

  const byScope = (["work", "outside", "unclear"] as const).map((scope) => {
    const rs = runs.filter((r) => r.scope === scope);
    return { scope, runs: rs.length, cost: spend(rs) };
  });

  const categories = new Map<Category, { runs: number; cost: number }>();
  for (const r of runs) {
    const cur = categories.get(r.category) ?? { runs: 0, cost: 0 };
    categories.set(r.category, { runs: cur.runs + 1, cost: cur.cost + r.costUsd });
  }

  return {
    total: spend(runs),
    byScope,
    byCategory: [...categories.entries()]
      .map(([category, v]) => ({ category, ...v }))
      .sort((a, b) => b.cost - a.cost),
    sensitive: runs.filter((r) => r.sensitive).length,
    /** Calls the orchestrator itself would not stand behind. */
    lowConfidence: runs.filter((r) => r.scope !== "unclear" && r.confidence < 60).length,
  };
}
