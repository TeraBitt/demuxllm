"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * One key, for one provider.
 *
 * Every model in the pool is served by Chutes, so a single Chutes key reaches
 * all of them. That is the whole reason the pool is Chutes-only: a router that
 * spans providers needs a credential per provider, and the ones a browser can
 * hold are the ones a visitor can read.
 *
 * BYOK is the demo's answer to that. The key belongs to the visitor, it stays
 * in their browser, and it is read only to build a request straight to Chutes
 * from their machine. Metered credits are the product's answer, and that path
 * moves the key to a server where a browser can never read it.
 *
 * `NEXT_PUBLIC_CHUTES_API_KEY` exists only so a local demo can run without
 * typing a key, and anything in it is public the moment it ships.
 */

const STORAGE_KEY = "demux.byok";

export type Keys = { chutes: string };

const EMPTY: Keys = { chutes: "" };

/** One shared snapshot, so every subscriber compares by reference. */
let snapshot: Keys | null = null;
const listeners = new Set<() => void>();

function read(): Keys {
  if (snapshot) return snapshot;
  if (typeof window === "undefined") return EMPTY;
  let next: Keys;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    next = raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY;
  } catch {
    next = EMPTY;
  }
  snapshot = next;
  return next;
}

function write(next: Keys) {
  snapshot = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Private browsing. The key still works for this session.
  }
  listeners.forEach((l) => l());
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

export function useKeys() {
  const keys = useSyncExternalStore(subscribe, read, () => EMPTY);

  const setKey = useCallback((provider: keyof Keys, value: string) => {
    write({ ...read(), [provider]: value.trim() });
  }, []);

  const clear = useCallback(() => write(EMPTY), []);

  /** The env fallback only exists for local demos; it is bundled and public. */
  const chutesKey = keys.chutes || process.env.NEXT_PUBLIC_CHUTES_API_KEY || "";

  return {
    keys,
    setKey,
    clear,
    chutesKey,
    hasChutes: Boolean(chutesKey),
  };
}
