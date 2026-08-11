"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  BarChart3,
  KeyRound,
  MessageSquarePlus,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { LogoMarkCompact, Wordmark } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { cx } from "@/components/ui/primitives";
import { Composer, Message } from "@/components/dashboard/chat";
import {
  ByokPanel,
  TeePanel,
  ToolsPanel,
  UsagePanel,
} from "@/components/dashboard/panels";
import { useSession } from "@/lib/dashboard/session";

const PANELS = [
  { key: "usage", label: "Usage", Icon: BarChart3 },
  { key: "tools", label: "Tools", Icon: Wrench },
  { key: "byok", label: "Keys", Icon: KeyRound },
  { key: "tee", label: "Private", Icon: ShieldCheck },
] as const;

type PanelKey = (typeof PANELS)[number]["key"];

/**
 * Two soft colour fields, fixed behind everything.
 *
 * They are not decoration — translucent panels have nothing to separate them
 * from a flat canvas, so without something behind them the whole glass layer
 * collapses into tinted grey. Kept static and very low contrast: enough for the
 * blur to have material to work with, not enough to notice on its own.
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
      <div
        className="absolute -bottom-[20rem] left-[36%] size-[40rem] rounded-full opacity-[0.09] blur-[140px] dark:opacity-[0.13]"
        style={{ background: "var(--tier-3)" }}
      />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center text-center">
      <div className="relative">
        <div
          aria-hidden
          className="absolute inset-0 -z-10 scale-[2.6] rounded-full opacity-30 blur-2xl"
          style={{ background: "var(--glow)" }}
        />
        <LogoMarkCompact className="h-11 w-11" />
      </div>

      <h1 className="mt-7 text-[1.75rem] leading-tight font-semibold tracking-[-0.035em] text-balance sm:text-[2.125rem]">
        What do you need answered?
      </h1>
      <p className="mt-3.5 max-w-md text-[0.9375rem] leading-relaxed text-balance text-ink-muted">
        Every question is classified, routed to the cheapest model that can
        answer it properly, and priced against what one frontier model would
        have charged.
      </p>
    </div>
  );
}

export function DashboardShell() {
  const { turns, busy, ask, reset, totals, live } = useSession();
  const [draft, setDraft] = useState("");
  const [panel, setPanel] = useState<PanelKey>("usage");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  function send(q: string) {
    setDraft("");
    void ask(q);
  }

  const empty = turns.length === 0;

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden lg:flex-row">
      <Ambient />

      {/* ---------------------------------------------------------- rail -- */}
      <aside className="glass glass-line z-20 flex shrink-0 items-center gap-3 border-b px-4 py-3 lg:w-[15.5rem] lg:flex-col lg:items-stretch lg:border-r lg:border-b-0 lg:px-3.5 lg:py-5">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2.5 rounded-xl px-1.5 py-1 transition-opacity hover:opacity-70"
        >
          <LogoMarkCompact className="h-[26px] w-[26px]" />
          <Wordmark />
        </Link>

        <button
          type="button"
          onClick={reset}
          className="glass-strong glass-line edge-lit ml-auto inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-[0.8125rem] font-medium transition-transform hover:-translate-y-px active:translate-y-0 lg:mt-7 lg:ml-0 lg:justify-center"
        >
          <MessageSquarePlus size={15} strokeWidth={2.2} />
          <span className="hidden lg:inline">New chat</span>
        </button>

        <div className="hidden lg:mt-auto lg:flex lg:flex-col lg:gap-3">
          <div className="glass-line flex items-center gap-2 rounded-xl border px-3 py-2.5">
            <span
              aria-hidden
              className={cx(
                "size-1.5 shrink-0 rounded-full",
                live ? "bg-accent" : "bg-ink-faint",
              )}
            />
            <span className="text-[0.75rem] leading-snug text-ink-muted">
              {live ? "Live — real Gemini calls" : "Simulated — add a key"}
            </span>
          </div>

          <div className="flex items-center justify-between px-1">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-[0.8125rem] text-ink-faint transition-colors hover:text-ink"
            >
              <ArrowLeft size={14} />
              Site
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      {/* ---------------------------------------------------------- chat -- */}
      <div className="relative flex min-w-0 flex-1 flex-col">
        {empty ? (
          /* Nothing to scroll yet, so the composer rises to meet the greeting
             rather than sitting at the bottom with dead space between them. */
          <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto">
            <div className="mx-auto w-full max-w-2xl px-5 py-10 sm:px-8">
              <EmptyState />
              <div className="mt-9">
                <Composer
                  value={draft}
                  onChange={setDraft}
                  onSubmit={send}
                  busy={busy}
                  showSuggestions
                />
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <div className="mx-auto flex max-w-3xl flex-col gap-12 px-5 pt-8 pb-6 sm:px-8">
                {turns.map((t) => (
                  <Message key={t.id} turn={t} />
                ))}
                <div ref={bottom} />
              </div>
            </div>

            <div className="relative shrink-0">
              <div
                aria-hidden
                className="pointer-events-none absolute inset-x-0 -top-14 h-14 bg-gradient-to-t from-canvas to-transparent"
              />
              <div className="mx-auto max-w-3xl px-5 pb-4 sm:px-8">
                <Composer
                  value={draft}
                  onChange={setDraft}
                  onSubmit={send}
                  busy={busy}
                  showSuggestions={false}
                />
                <p className="mt-3 text-center text-[0.6875rem] text-ink-faint">
                  Orchestrated with LangGraph in your browser.{" "}
                  {live ? "Answers are real." : "Answers are simulated."} Costs
                  are list-price estimates.
                </p>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ------------------------------------------------------ inspector -- */}
      <aside className="glass glass-line z-20 hidden shrink-0 border-l xl:flex xl:w-[20.5rem] xl:flex-col">
        <div className="glass-line shrink-0 border-b p-3">
          <div className="edge-sunk flex gap-0.5 rounded-xl bg-ink/[0.03] p-1 dark:bg-black/20">
            {PANELS.map(({ key, label, Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setPanel(key)}
                className={cx(
                  "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[0.75rem] font-medium transition-all",
                  panel === key
                    ? "glass-strong text-ink shadow-[inset_0_1px_0_0_var(--glass-highlight),0_1px_3px_0_rgb(0_0_0/0.12)]"
                    : "text-ink-faint hover:text-ink-muted",
                )}
              >
                <Icon size={13} strokeWidth={2.2} />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {panel === "usage" ? <UsagePanel {...totals} /> : null}
          {panel === "tools" ? <ToolsPanel /> : null}
          {panel === "byok" ? <ByokPanel /> : null}
          {panel === "tee" ? <TeePanel /> : null}
        </div>
      </aside>
    </div>
  );
}
