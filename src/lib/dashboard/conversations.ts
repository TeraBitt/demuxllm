"use client";

import { useCallback, useSyncExternalStore } from "react";
import type { Turn } from "./session";

/**
 * Chats, kept in this browser so a demo survives a refresh.
 *
 * What is *not* kept is deliberate. Reasoning traces are the largest thing a
 * turn produces and the least useful to re-read, so they are truncated on the
 * way in; the trace rows are dropped entirely because they describe a run that
 * has already finished. Between them that is the difference between a handful
 * of chats fitting in localStorage and the quota erroring out mid-demo.
 */

const STORAGE_KEY = "demux.chats";
const MAX_CHATS = 40;
const MAX_REASONING = 4000;

export type Chat = {
  id: string;
  title: string;
  /** Last touched, newest first in the list. */
  at: number;
  turns: Turn[];
};

export function titleFor(question: string) {
  const clean = question.replace(/\s+/g, " ").trim();
  return clean.length > 48 ? `${clean.slice(0, 48).trimEnd()}…` : clean || "New chat";
}

/** Strip a chat down to what is worth persisting. */
function slim(chat: Chat): Chat {
  return {
    ...chat,
    turns: chat.turns.map((t) => ({
      ...t,
      steps: [],
      parts: t.parts.map((p) =>
        p.kind === "reasoning" && p.text.length > MAX_REASONING
          ? { ...p, text: `${p.text.slice(0, MAX_REASONING)}\n…` }
          : p,
      ),
    })),
  };
}

/* ------------------------------------------------------------------ store -- */

let snapshot: Chat[] | null = null;
const listeners = new Set<() => void>();
const EMPTY: Chat[] = [];

function read(): Chat[] {
  if (snapshot) return snapshot;
  if (typeof window === "undefined") return EMPTY;
  let next: Chat[];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    next = Array.isArray(parsed) ? (parsed as Chat[]) : EMPTY;
  } catch {
    next = EMPTY;
  }
  snapshot = next;
  return next;
}

function commit(next: Chat[]) {
  snapshot = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Quota, or private browsing. The in-memory copy still drives this session,
    // so the demo keeps working; only the refresh survives less.
  }
  listeners.forEach((l) => l());
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

export function saveChat(chat: Chat) {
  if (!chat.turns.length) return;
  const rest = read().filter((c) => c.id !== chat.id);
  commit([slim(chat), ...rest].slice(0, MAX_CHATS));
}

export function readChats() {
  return read();
}

export function useChats() {
  const chats = useSyncExternalStore(subscribe, read, () => EMPTY);

  const remove = useCallback((id: string) => {
    commit(read().filter((c) => c.id !== id));
  }, []);

  const rename = useCallback((id: string, title: string) => {
    commit(read().map((c) => (c.id === id ? { ...c, title: title.trim() || c.title } : c)));
  }, []);

  const clear = useCallback(() => commit([]), []);

  return { chats, remove, rename, clear };
}
