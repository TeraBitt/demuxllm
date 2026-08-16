"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowDown,
  Brain,
  LayoutDashboard,
  PanelLeft,
  Plus,
  Route,
  Settings2,
  Sparkles,
  Wrench,
} from "lucide-react";
import { LogoMarkCompact } from "@/components/brand";
import { cx } from "@/components/ui/primitives";
import { Composer, Message, SUGGESTIONS } from "@/components/dashboard/chat";
import { Settings, type Tab } from "@/components/dashboard/controls";
import { Sidebar } from "@/components/dashboard/sidebar";
import { byId } from "@/lib/dashboard/models";
import { PRESETS, THINKING_MODES, usePrefs } from "@/lib/dashboard/prefs";
import { useSession } from "@/lib/dashboard/session";

/**
 * The assistant. A transcript, a composer, and a strip of controls that says
 * what the next answer will be produced under.
 *
 * The routing detail that used to live in a right rail rides with the message
 * that produced it — a score table belongs to its answer, not to a panel showing
 * whichever run happened last. What is left in the chrome is only what changes
 * behaviour, and it reads its state out loud rather than hiding it behind a
 * cog: "balanced · reasoning auto · 5 tools" is the configuration, in the place
 * you would look for it.
 */

function Ambient() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div
        className="absolute -top-[24rem] left-[6%] size-[48rem] rounded-full opacity-[0.13] blur-[140px] dark:opacity-[0.20]"
        style={{ background: "var(--accent)" }}
      />
      <div
        className="absolute top-[8%] -right-[13rem] size-[42rem] rounded-full opacity-[0.10] blur-[140px] dark:opacity-[0.15]"
        style={{ background: "var(--tier-1)" }}
      />
    </div>
  );
}

const CORNER =
  "glass-strong glass-line edge-lit flex size-9 items-center justify-center rounded-full border text-ink-muted transition-all hover:-translate-y-px hover:text-ink";

/* -------------------------------------------------------------- controls -- */

/** A chip that both reports a setting and is the way to change it. */
function ConfigChip({
  icon: Icon,
  children,
  onClick,
  title,
}: {
  icon: typeof Route;
  children: React.ReactNode;
  onClick: () => void;
  title: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="flex items-center gap-1.5 rounded-full px-2 py-1 text-[0.75rem] text-ink-faint transition-colors hover:bg-ink/[0.05] hover:text-ink dark:hover:bg-white/[0.06]"
    >
      <Icon size={12} strokeWidth={2.2} />
      {children}
    </button>
  );
}

function ConfigStrip({ onOpen }: { onOpen: (tab: Tab) => void }) {
  const { prefs } = usePrefs();
  const pinned = prefs.pinnedModel ? byId(prefs.pinnedModel) : null;
  const tools = prefs.toolsEnabled ? prefs.enabledTools.length : 0;

  return (
    <div className="flex flex-wrap items-center justify-center gap-0.5">
      <ConfigChip icon={Route} onClick={() => onOpen("routing")} title="Routing strategy">
        {pinned
          ? `pinned to ${pinned.label}`
          : (PRESETS.find((p) => p.value === prefs.preset)?.label.split(" ")[0].toLowerCase() ??
            "balanced")}
      </ConfigChip>
      <span aria-hidden className="text-ink-faint/40">
        ·
      </span>
      <ConfigChip icon={Brain} onClick={() => onOpen("reasoning")} title="Reasoning">
        reasoning{" "}
        {THINKING_MODES.find((m) => m.value === prefs.thinking)?.label.toLowerCase() ?? "auto"}
      </ConfigChip>
      <span aria-hidden className="text-ink-faint/40">
        ·
      </span>
      <ConfigChip icon={Wrench} onClick={() => onOpen("tools")} title="Tools">
        {tools ? `${tools} tools` : "no tools"}
      </ConfigChip>
    </div>
  );
}

/* ----------------------------------------------------------------- shell -- */

export function DashboardShell() {
  const { chatId, turns, busy, ask, stop, regenerate, reset, open, live } = useSession();
  const [draft, setDraft] = useState("");
  const [settings, setSettings] = useState<Tab | null>(null);
  // Two states because they are two different objects: a rail that is part of
  // the layout on a wide screen, and a drawer that covers it on a narrow one.
  // One state cannot be both open-by-default and closed-by-default.
  const [rail, setRail] = useState(true);
  const [drawer, setDrawer] = useState(false);
  const [pinnedToBottom, setPinnedToBottom] = useState(true);

  const scroller = useRef<HTMLDivElement>(null);
  const bottom = useRef<HTMLDivElement>(null);

  /* Stick to the bottom while tokens arrive, unless the reader scrolled away. */
  const onScroll = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
    setPinnedToBottom(gap < 120);
  }, []);

  useEffect(() => {
    if (!pinnedToBottom) return;
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [pinnedToBottom, turns]);

  const jump = useCallback(() => {
    setPinnedToBottom(true);
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, []);

  const newChat = useCallback(() => {
    reset();
    setDraft("");
    setPinnedToBottom(true);
  }, [reset]);

  /* Keyboard: new chat, settings, and stop. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        newChat();
      } else if (meta && e.key === "/") {
        e.preventDefault();
        setSettings((s) => (s ? null : "routing"));
      } else if (e.key === "Escape" && busy && !settings) {
        // With the dialog open, Escape belongs to the dialog — closing it and
        // killing the run behind it on one keypress is one action too many.
        stop();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, newChat, settings, stop]);

  const empty = turns.length === 0;

  function send(q: string) {
    setDraft("");
    setPinnedToBottom(true);
    ask(q);
  }

  return (
    <div className="relative flex h-dvh overflow-hidden">
      <Ambient />

      {/* Wide screens: part of the layout. */}
      {rail ? (
        <div className="hidden lg:block">
          <Sidebar
            activeId={chatId}
            onNew={newChat}
            onOpen={open}
            onSettings={() => setSettings("provider")}
            onCollapse={() => setRail(false)}
          />
        </div>
      ) : null}

      {/* Narrow screens: over the top of it. */}
      {drawer ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => setDrawer(false)}
            className="absolute inset-0 cursor-default bg-ink/25 backdrop-blur-sm dark:bg-black/60"
          />
          <div className="relative h-full w-64">
            <Sidebar
              activeId={chatId}
              onNew={() => {
                newChat();
                setDrawer(false);
              }}
              onOpen={(c) => {
                open(c);
                setDrawer(false);
              }}
              onSettings={() => {
                setSettings("provider");
                setDrawer(false);
              }}
              onCollapse={() => setDrawer(false)}
            />
          </div>
        </div>
      ) : null}

      <div className="relative flex min-w-0 flex-1 flex-col">
        <header className="absolute inset-x-0 top-0 z-20 flex items-center gap-2 px-4 py-3.5 sm:px-6">
          {/* Always reachable on a narrow screen; on a wide one only when the
              rail it opens is not already there. */}
          <button
            type="button"
            onClick={() => {
              setRail(true);
              setDrawer(true);
            }}
            aria-label="Show conversations"
            title="Conversations"
            className={cx(CORNER, rail && "lg:hidden")}
          >
            <PanelLeft size={15} />
          </button>

          <Link
            href="/"
            className={cx("rounded-xl transition-opacity hover:opacity-70", rail && "lg:hidden")}
          >
            <LogoMarkCompact className="h-[26px] w-[26px]" />
          </Link>

          {!empty ? (
            <button
              type="button"
              onClick={newChat}
              className="glass glass-line flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[0.8125rem] text-ink-muted transition-colors hover:text-ink"
            >
              <Plus size={13} strokeWidth={2.4} />
              New chat
            </button>
          ) : null}

          <div className="ml-auto flex items-center gap-2">
            <Link href="/dashboard" aria-label="Metrics" title="Metrics" className={CORNER}>
              <LayoutDashboard size={15} />
            </Link>
            <button
              type="button"
              onClick={() => setSettings("provider")}
              aria-label="Settings"
              title="Settings (⌘/ or Ctrl /)"
              className={CORNER}
            >
              <Settings2 size={15} />
            </button>
          </div>
        </header>

        {empty ? (
          <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto">
            <div className="mx-auto w-full max-w-2xl px-5 py-10 sm:px-8">
              <h1 className="text-center text-[2.25rem] leading-[1.05] font-semibold tracking-[-0.04em] text-balance sm:text-[3rem]">
                How can I help you?
              </h1>

              <div className="mt-8">
                <Composer
                  value={draft}
                  onChange={setDraft}
                  onSubmit={send}
                  onStop={stop}
                  busy={busy}
                />
              </div>

              <div className="mt-4">
                <ConfigStrip onOpen={setSettings} />
              </div>

              <div className="mt-7 grid gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.label}
                    type="button"
                    onClick={() => send(s.prompt)}
                    className="glass glass-line group/s flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-left transition-all duration-200 hover:-translate-y-px hover:shadow-md hover:shadow-black/10 dark:hover:shadow-black/40"
                  >
                    <Sparkles
                      size={13}
                      className="mt-0.5 shrink-0 text-ink-faint transition-colors group-hover/s:text-accent"
                      strokeWidth={2.2}
                    />
                    <span className="text-[0.8125rem] leading-snug text-ink-muted transition-colors group-hover/s:text-ink">
                      {s.label}
                    </span>
                  </button>
                ))}
              </div>

              <p className="mt-6 text-center text-[0.75rem] text-ink-faint">
                {live
                  ? "Every request is scored across the model pool before it is answered."
                  : "Add a provider key in Settings to start routing."}
              </p>
            </div>
          </div>
        ) : (
          <>
            <div
              ref={scroller}
              onScroll={onScroll}
              className="min-h-0 flex-1 overflow-y-auto pt-16"
            >
              <div className="mx-auto flex max-w-3xl flex-col gap-12 px-5 pt-6 pb-6 sm:px-8">
                {turns.map((t, i) => (
                  <Message
                    key={t.id}
                    turn={t}
                    onRegenerate={regenerate}
                    canRegenerate={!busy && i === turns.length - 1}
                  />
                ))}
                <div ref={bottom} />
              </div>
            </div>

            <div className="relative shrink-0">
              <div
                aria-hidden
                className="pointer-events-none absolute inset-x-0 -top-14 h-14 bg-gradient-to-t from-canvas to-transparent"
              />

              {!pinnedToBottom ? (
                <button
                  type="button"
                  onClick={jump}
                  aria-label="Jump to latest"
                  className="glass-strong glass-line edge-lit absolute -top-11 left-1/2 flex size-8 -translate-x-1/2 items-center justify-center rounded-full border text-ink-muted shadow-lg shadow-black/10 transition-transform hover:scale-105 dark:shadow-black/50"
                >
                  <ArrowDown size={14} strokeWidth={2.4} />
                </button>
              ) : null}

              <div className="mx-auto max-w-3xl px-5 pb-3 sm:px-8">
                <Composer
                  value={draft}
                  onChange={setDraft}
                  onSubmit={send}
                  onStop={stop}
                  busy={busy}
                />
                <div className="mt-2">
                  <ConfigStrip onOpen={setSettings} />
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {settings ? (
        <Settings initialTab={settings} onClose={() => setSettings(null)} />
      ) : null}
    </div>
  );
}
