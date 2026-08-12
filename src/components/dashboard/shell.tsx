"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { LayoutDashboard, Settings2, SlidersHorizontal } from "lucide-react";
import { LogoMarkCompact } from "@/components/brand";
import { Composer, Message } from "@/components/dashboard/chat";
import { RoutingControl, Settings } from "@/components/dashboard/controls";
import { useSession } from "@/lib/dashboard/session";

/**
 * The assistant. One column, nothing docked beside it.
 *
 * The routing detail that used to live in a right rail now rides with the
 * message that produced it — a score table belongs to its answer, not to a
 * panel showing whichever run happened last. What is left in the corner is only
 * what changes behaviour: the two overlays, and a way back to the metrics.
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

export function DashboardShell() {
  const { turns, busy, ask, reset, live } = useSession();
  const [draft, setDraft] = useState("");
  const [overlay, setOverlay] = useState<"settings" | "routing" | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const empty = turns.length === 0;

  function send(q: string) {
    setDraft("");
    void ask(q);
  }

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden">
      <Ambient />

      <header className="absolute inset-x-0 top-0 z-20 flex items-center gap-2 px-5 py-4 sm:px-6">
        <Link href="/" className="rounded-xl transition-opacity hover:opacity-70">
          <LogoMarkCompact className="h-[26px] w-[26px]" />
        </Link>

        {!empty ? (
          <button
            type="button"
            onClick={reset}
            className="glass glass-line rounded-full border px-3 py-1.5 text-[0.8125rem] text-ink-muted transition-colors hover:text-ink"
          >
            New chat
          </button>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          <Link href="/dashboard" aria-label="Dashboard" title="Dashboard" className={CORNER}>
            <LayoutDashboard size={15} />
          </Link>
          <button
            type="button"
            onClick={() => setOverlay("settings")}
            aria-label="Settings"
            title="Settings"
            className={CORNER}
          >
            <Settings2 size={15} />
          </button>
          <button
            type="button"
            onClick={() => setOverlay("routing")}
            aria-label="Routing control"
            title="Routing control"
            className={CORNER}
          >
            <SlidersHorizontal size={15} />
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
                busy={busy}
                showSuggestions
              />
            </div>
            <p className="mt-5 text-center text-[0.75rem] text-ink-faint">
              {live
                ? "Every request is scored across the model pool before it is answered."
                : "Add a provider key in Settings to start routing."}
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="min-h-0 flex-1 overflow-y-auto pt-16">
            <div className="mx-auto flex max-w-3xl flex-col gap-12 px-5 pt-6 pb-6 sm:px-8">
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
            </div>
          </div>
        </>
      )}

      {overlay === "settings" ? <Settings onClose={() => setOverlay(null)} /> : null}
      {overlay === "routing" ? <RoutingControl onClose={() => setOverlay(null)} /> : null}
    </div>
  );
}
