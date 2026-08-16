"use client";

import { useCallback, useSyncExternalStore } from "react";
import { CATALOG, type CatalogModel, type Family } from "./models";

/**
 * Routing and behaviour preferences.
 *
 * These are controls, not decoration — every field here is read before the next
 * answer is produced, so moving anything changes an outcome. Anything that
 * could not change an outcome was left out: an inert switch is worse than a
 * missing one, because a missing one does not lie about what the product does.
 */

const STORAGE_KEY = "demux.prefs";

export type Preset = "cheapest" | "balanced" | "best";
export type Thinking = "auto" | "always" | "never";
export type Style = "concise" | "balanced" | "thorough";

export type Prefs = {
  /* -- routing ----------------------------------------------------------- */
  preset: Preset;
  /** Hard ceiling on the blended price of the model that answers. */
  maxCostPer1M: number;
  /** 0-1. Raises the bar the orchestrator sets; never lowers it. */
  qualityFloor: number;
  /** Model families excluded from the pool entirely. */
  disallowed: Family[];
  /** Exact model id to use for every answer, bypassing the pick. Empty = route. */
  pinnedModel: string;

  /* -- reasoning --------------------------------------------------------- */
  /**
   * "auto" buys a reasoning trace only where the orchestrator set a high bar,
   * which is the product's whole argument applied to reasoning rather than to
   * model choice. "always" and "never" override it in either direction.
   */
  thinking: Thinking;
  /** Bar at or above which "auto" turns thinking on. */
  thinkingThreshold: number;

  /* -- tools ------------------------------------------------------------- */
  toolsEnabled: boolean;
  /** Tool names the model may call. A tool not named here is never declared. */
  enabledTools: string[];
  /** How many times the model may call tools before it must answer. */
  maxToolRounds: number;

  /* -- answer ------------------------------------------------------------ */
  style: Style;
  /** Appended to the system prompt verbatim. The user's own standing rules. */
  systemPrompt: string;
  temperature: number;
  /** How many previous turns are re-sent as context. 0 = every message is new. */
  historyTurns: number;

  /* -- workspace --------------------------------------------------------- */
  /** Named in the analytics view so a report says whose work it describes. */
  orgName: string;
  /**
   * What this workspace works on, in the admin's own words. The orchestrator
   * has nothing else to judge "is this company work" against — with this empty
   * every request is classified "unclear", which is the honest answer.
   */
  orgContext: string;
};

export const ALL_TOOLS = [
  "search_models",
  "estimate_cost",
  "usage_stats",
  "run_javascript",
  "current_time",
];

export const DEFAULT_PREFS: Prefs = {
  preset: "balanced",
  maxCostPer1M: 12,
  qualityFloor: 0.6,
  disallowed: [],
  pinnedModel: "",

  thinking: "auto",
  thinkingThreshold: 75,

  toolsEnabled: true,
  enabledTools: [...ALL_TOOLS],
  maxToolRounds: 4,

  style: "balanced",
  systemPrompt: "",
  temperature: 0.4,
  historyTurns: 8,

  orgName: "",
  orgContext: "",
};

export const COST_CAPS = [
  { value: 2, label: "$2" },
  { value: 12, label: "$12" },
  { value: 60, label: "no cap" },
] as const;

export const PRESETS: { value: Preset; label: string; hint: string }[] = [
  { value: "cheapest", label: "Cheapest that clears", hint: "Lowest price at or above the bar" },
  { value: "balanced", label: "Balanced", hint: "Prefers a margin over the bar" },
  { value: "best", label: "Best available", hint: "Highest score, price ignored" },
];

export const THINKING_MODES: { value: Thinking; label: string; hint: string }[] = [
  {
    value: "auto",
    label: "Auto",
    hint: "Reasoning only where the router set a high bar — the same argument as model choice, applied to thinking.",
  },
  { value: "always", label: "Always", hint: "Every capable model reasons before it answers. Slower, dearer, steadier." },
  { value: "never", label: "Never", hint: "No reasoning trace is ever bought. Fastest and cheapest." },
];

export const STYLES: { value: Style; label: string; hint: string }[] = [
  { value: "concise", label: "Concise", hint: "Answer first, few words, no scaffolding" },
  { value: "balanced", label: "Balanced", hint: "Answer, then the reasoning worth keeping" },
  { value: "thorough", label: "Thorough", hint: "Alternatives, trade-offs and edge cases" },
];

/** Blended price used for every cost comparison. Output-weighted: that is where the spread lives. */
export const blendedPrice = (m: CatalogModel) => m.inPer1M + m.outPer1M * 3;

export function poolFor(prefs: Prefs): CatalogModel[] {
  const pool = CATALOG.filter(
    (m) => !prefs.disallowed.includes(m.family) && blendedPrice(m) <= prefs.maxCostPer1M,
  );
  // Never hand the router an empty pool — a cap tighter than everything still
  // has to answer, so fall back to the single cheapest model.
  if (pool.length) return pool;
  return [...CATALOG].sort((a, b) => blendedPrice(a) - blendedPrice(b)).slice(0, 1);
}

/** Tools the model may see this turn. A model that cannot hold a schema sees none. */
export function toolsFor(prefs: Prefs, model: CatalogModel): string[] {
  if (!prefs.toolsEnabled || !model.structured) return [];
  return prefs.enabledTools.filter((t) => ALL_TOOLS.includes(t));
}

/**
 * Whether to buy a reasoning trace for this answer. A model that cannot think
 * ignores the switch; one that can bills for the trace, which is why "auto"
 * spends it only where the bar says the answer has to be right.
 */
export function thinkingFor(prefs: Prefs, model: CatalogModel, bar: number): boolean {
  if (!model.thinks) return false;
  if (prefs.thinking === "never") return false;
  if (prefs.thinking === "always") return true;
  return bar >= prefs.thinkingThreshold;
}

/* ------------------------------------------------------------------ store -- */

let snapshot: Prefs | null = null;
const listeners = new Set<() => void>();

function read(): Prefs {
  if (snapshot) return snapshot;
  if (typeof window === "undefined") return DEFAULT_PREFS;
  let next: Prefs;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    next = raw ? { ...DEFAULT_PREFS, ...JSON.parse(raw) } : DEFAULT_PREFS;
  } catch {
    next = DEFAULT_PREFS;
  }
  snapshot = next;
  return next;
}

function write(next: Prefs) {
  snapshot = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* private browsing — still applies for this session */
  }
  listeners.forEach((l) => l());
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/** For callers outside React — the run loop reads prefs at send time, not render time. */
export const readPrefs = read;

export function usePrefs() {
  const prefs = useSyncExternalStore(subscribe, read, () => DEFAULT_PREFS);

  const set = useCallback(<K extends keyof Prefs>(key: K, value: Prefs[K]) => {
    write({ ...read(), [key]: value });
  }, []);

  const toggleFamily = useCallback((family: Family) => {
    const cur = read();
    const disallowed = cur.disallowed.includes(family)
      ? cur.disallowed.filter((f) => f !== family)
      : [...cur.disallowed, family];
    write({ ...cur, disallowed });
  }, []);

  const toggleTool = useCallback((tool: string) => {
    const cur = read();
    const enabledTools = cur.enabledTools.includes(tool)
      ? cur.enabledTools.filter((t) => t !== tool)
      : [...cur.enabledTools, tool];
    write({ ...cur, enabledTools });
  }, []);

  const reset = useCallback(() => write(DEFAULT_PREFS), []);

  return { prefs, set, toggleFamily, toggleTool, reset, pool: poolFor(prefs) };
}
