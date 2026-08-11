"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * BYOK, stored in localStorage and never sent anywhere but the provider.
 *
 * This is the one place a real secret touches this app, so the rules are worth
 * stating: the key belongs to the visitor, it stays in their browser, and it is
 * read only to build a request straight to the provider from their machine.
 * There is no DemuxLLM server in this demo's path at all.
 *
 * A key of ours could not live here — anything a browser can read, a visitor
 * can read. `NEXT_PUBLIC_GEMINI_API_KEY` exists only so a local demo can run
 * without typing a key, and anything in it is public the moment it ships.
 */

const STORAGE_KEY = "demux.byok";

export type Keys = { gemini: string; chutes: string };

const EMPTY: Keys = { gemini: "", chutes: "" };

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
    // Private browsing. The keys still work for this session.
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
  const geminiKey =
    keys.gemini || process.env.NEXT_PUBLIC_GEMINI_API_KEY || "";

  return {
    keys,
    setKey,
    clear,
    geminiKey,
    hasGemini: Boolean(geminiKey),
    hasChutes: Boolean(keys.chutes),
  };
}
