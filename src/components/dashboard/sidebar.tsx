"use client";

import Link from "next/link";
import { LayoutDashboard, PanelLeftClose, Plus, Settings2, Trash2 } from "lucide-react";
import { Logo } from "@/components/brand";
import { cx } from "@/components/ui/primitives";
import { type Chat, useChats } from "@/lib/dashboard/conversations";

/**
 * Conversations, newest first.
 *
 * Kept deliberately plain: the interesting surface in this product is the one
 * that shows what a request cost and why, and a sidebar competing with it for
 * attention would be the wrong kind of busy. It exists so a demo can jump back
 * to the run that made the point, and for nothing else.
 */

function relative(at: number) {
  const mins = Math.round((Date.now() - at) / 60_000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

export function Sidebar({
  activeId,
  onNew,
  onOpen,
  onSettings,
  onCollapse,
}: {
  activeId: string;
  onNew: () => void;
  onOpen: (chat: Chat) => void;
  onSettings: () => void;
  onCollapse: () => void;
}) {
  const { chats, remove } = useChats();

  return (
    <aside className="glass glass-line flex h-full w-64 shrink-0 flex-col border-r">
      <div className="flex items-center gap-1 px-3 py-3.5">
        <Link href="/" className="rounded-lg transition-opacity hover:opacity-70">
          <Logo />
        </Link>
        <button
          type="button"
          onClick={onCollapse}
          aria-label="Hide sidebar"
          title="Hide sidebar"
          className="ml-auto flex size-8 items-center justify-center rounded-lg text-ink-faint transition-colors hover:bg-ink/[0.05] hover:text-ink dark:hover:bg-white/[0.06]"
        >
          <PanelLeftClose size={15} />
        </button>
      </div>

      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={onNew}
          // The shortcut lives in the tooltip rather than a visible kbd: which
          // modifier to draw depends on the platform, and reading that during
          // render is exactly the sort of thing that mismatches on hydration.
          title="New chat (⌘K / Ctrl K)"
          className="glass-strong glass-line edge-lit flex w-full items-center gap-2 rounded-xl border px-3 py-2 text-[0.8125rem] font-medium transition-transform hover:-translate-y-px"
        >
          <Plus size={14} strokeWidth={2.4} />
          New chat
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {chats.length ? (
          <ul className="flex flex-col gap-0.5">
            {chats.map((c) => (
              <li key={c.id} className="group/chat relative">
                <button
                  type="button"
                  onClick={() => onOpen(c)}
                  className={cx(
                    "flex w-full items-center gap-2 rounded-lg py-2 pr-8 pl-2.5 text-left transition-colors",
                    c.id === activeId
                      ? "glass-strong text-ink"
                      : "text-ink-muted hover:bg-ink/[0.04] dark:hover:bg-white/[0.05]",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate text-[0.8125rem]">{c.title}</span>
                  <span className="shrink-0 text-[0.6875rem] text-ink-faint tabular-nums">
                    {relative(c.at)}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => remove(c.id)}
                  aria-label={`Delete ${c.title}`}
                  className="absolute top-1/2 right-1 flex size-6 -translate-y-1/2 items-center justify-center rounded-md text-ink-faint opacity-0 transition-opacity group-hover/chat:opacity-100 hover:text-ink focus-visible:opacity-100"
                >
                  <Trash2 size={12} />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-2.5 py-3 text-[0.75rem] leading-relaxed text-ink-faint">
            Conversations you have on this device show up here.
          </p>
        )}
      </div>

      <div className="glass-line flex items-center gap-1 border-t px-3 py-2.5">
        <Link
          href="/dashboard"
          className="flex flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-[0.8125rem] text-ink-muted transition-colors hover:bg-ink/[0.04] hover:text-ink dark:hover:bg-white/[0.05]"
        >
          <LayoutDashboard size={14} />
          Metrics
        </Link>
        <button
          type="button"
          onClick={onSettings}
          aria-label="Settings"
          title="Settings"
          className="flex size-8 items-center justify-center rounded-lg text-ink-faint transition-colors hover:bg-ink/[0.05] hover:text-ink dark:hover:bg-white/[0.06]"
        >
          <Settings2 size={15} />
        </button>
      </div>
    </aside>
  );
}
