"use client";

import { useCallback, useSyncExternalStore } from "react";
import { CATALOG, type CatalogModel, type Family } from "./models";

/**
 * Routing preferences. These are controls, not decoration — every field here is
 * read by `decideRoute` before it picks, so moving a slider changes the next
 * answer. Anything that could not change an outcome was left out.
 */

const STORAGE_KEY = "demux.prefs";

export type Preset = "cheapest" | "balanced" | "best";

export type Prefs = {
  preset: Preset;
  /** Hard ceiling on the blended price of the model that answers. */
  maxCostPer1M: number;
  /** 0-1. Raises the bar the orchestrator sets; never lowers it. */
  qualityFloor: number;
  /** Model families excluded from the pool entirely. */
  disallowed: Family[];
  /** Named in the analytics view so a report says whose work it describes. */
  orgName: string;
  /**
   * What this workspace works on, in the admin's own words. The orchestrator
   * has nothing else to judge "is this company work" against — with this empty
   * every request is classified "unclear", which is the honest answer.
   */
  orgContext: string;
};

export const DEFAULT_PREFS: Prefs = {
  preset: "balanced",
  maxCostPer1M: 12,
  qualityFloor: 0.6,
  disallowed: [],
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

  const reset = useCallback(() => write(DEFAULT_PREFS), []);

  return { prefs, set, toggleFamily, reset, pool: poolFor(prefs) };
}
