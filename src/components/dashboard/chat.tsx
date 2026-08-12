"use client";

import { type FormEvent, type KeyboardEvent, useEffect, useRef } from "react";
import { ArrowUp, Square } from "lucide-react";
import { LogoMarkCompact } from "@/components/brand";
import { cx } from "@/components/ui/primitives";
import { Trace } from "@/components/dashboard/trace";
import { Scores } from "@/components/dashboard/scores";
import { TIER_VAR, usd } from "@/lib/dashboard/models";
import type { Turn } from "@/lib/dashboard/session";

/* -------------------------------------------------------------- markdown -- */

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_)/g;

/** Just enough markdown for model output. Text nodes only — nothing is parsed as HTML. */
function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(INLINE).map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={i} className="font-semibold text-ink">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={i}
              className="rounded bg-surface px-1 py-0.5 font-mono text-[0.8125em] text-accent"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        if (part.startsWith("_") && part.endsWith("_")) {
          return (
            <em key={i} className="text-ink-muted italic">
              {part.slice(1, -1)}
            </em>
          );
        }
        return part;
      })}
    </>
  );
}

const FENCE = /(```[\s\S]*?(?:```|$))/g;

/** A fenced code block. Split out before paragraphs, since it owns its newlines. */
function CodeFence({ raw }: { raw: string }) {
  const body = raw.replace(/^```[a-zA-Z0-9+#-]*\n?/, "").replace(/```$/, "");
  return (
    <pre className="glass glass-line overflow-x-auto rounded-xl border p-3.5 font-mono text-[0.8125rem] leading-relaxed text-ink">
      <code>{body.replace(/\n$/, "")}</code>
    </pre>
  );
}

const HEADING = /^(#{1,4})\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;

/**
 * Renders a block line by line rather than matching the block as a whole.
 * Models freely mix a heading, a sentence and a list inside one paragraph with
 * single newlines between them; a block-level match drops the markers and the
 * reader sees a literal "###".
 */
function Block({ block }: { block: string }) {
  const out: React.ReactNode[] = [];
  let para: string[] = [];
  let list: string[] = [];

  const flushPara = () => {
    if (!para.length) return;
    out.push(
      <p key={`p${out.length}`} className="leading-relaxed">
        <Inline text={para.join(" ")} />
      </p>,
    );
    para = [];
  };
  const flushList = () => {
    if (!list.length) return;
    out.push(
      <ul key={`u${out.length}`} className="flex flex-col gap-1.5 pl-1">
        {list.map((item, i) => (
          <li key={i} className="flex gap-2.5">
            <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-ink-faint" />
            <span className="min-w-0">
              <Inline text={item} />
            </span>
          </li>
        ))}
      </ul>,
    );
    list = [];
  };

  for (const line of block.split("\n")) {
    const heading = HEADING.exec(line);
    if (heading) {
      flushPara();
      flushList();
      out.push(
        <h3 key={`h${out.length}`} className="text-[0.9375rem] font-semibold text-ink">
          <Inline text={heading[2]} />
        </h3>,
      );
      continue;
    }

    const item = BULLET.exec(line) ?? NUMBERED.exec(line);
    if (item) {
      flushPara();
      list.push(item[1]);
      continue;
    }

    if (!line.trim()) {
      flushPara();
      flushList();
      continue;
    }
    flushList();
    para.push(line);
  }

  flushPara();
  flushList();
  return <>{out}</>;
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="flex flex-col gap-3.5">
      {text.split(FENCE).map((section, i) => {
        if (section.startsWith("```")) return <CodeFence key={i} raw={section} />;
        if (!section.trim()) return null;
        return <Block key={i} block={section.trim()} />;
      })}
    </div>
  );
}

/* --------------------------------------------------------------- message -- */

function RouteBadge({ turn }: { turn: Turn }) {
  if (!turn.chosen || !turn.decision) return null;

  const saved = turn.baselineUsd > 0 ? 1 - turn.costUsd / turn.baselineUsd : 0;
  const score = turn.decision.scores.find((s) => s.modelId === turn.chosen!.id);
  // The pool spans providers; this demo holds one key. When the routed model
  // and the endpoint that answered differ, say so here rather than let the
  // model name imply something untrue.
  const elsewhere = turn.serving && turn.serving !== turn.chosen.id;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[0.8125rem]">
      <span className="flex items-center gap-1.5">
        <span
          aria-hidden
          className="size-1.5 rounded-full"
          style={{ background: TIER_VAR[turn.chosen.tier] }}
        />
        <span className="font-medium">{turn.chosen.label}</span>
      </span>

      {score ? (
        <span className="text-ink-faint tabular-nums">
          scored {score.quality}, needed {turn.decision.bar}
        </span>
      ) : null}

      {saved > 0.005 ? (
        <span className="font-medium text-accent tabular-nums">
          {Math.round(saved * 100)}% cheaper than the top model
        </span>
      ) : (
        <span className="text-ink-faint tabular-nums">{usd(turn.costUsd, 4)}</span>
      )}

      {elsewhere ? (
        <span className="text-ink-faint">answered by {turn.serving}</span>
      ) : null}
    </div>
  );
}

export function Message({ turn }: { turn: Turn }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-end">
        <div className="glass-strong glass-line edge-lit max-w-[85%] rounded-2xl rounded-br-lg border px-4 py-2.5 text-[0.9375rem] leading-relaxed">
          {turn.question}
        </div>
      </div>

      <div className="flex gap-3">
        <LogoMarkCompact className="mt-0.5 h-6 w-6 shrink-0" />

        <div className="flex min-w-0 flex-1 flex-col gap-3.5">
          {turn.status !== "done" ? (
            <>
              {turn.steps.length > 0 ? <Trace steps={turn.steps} /> : null}
              {turn.decision ? <Scores decision={turn.decision} /> : null}
            </>
          ) : null}

          {turn.error ? (
            <div className="glass glass-line rounded-2xl border p-3.5 text-[0.8125rem] text-ink-muted">
              <span className="font-medium text-ink">That run failed. </span>
              {turn.error}
            </div>
          ) : null}

          {turn.answer ? (
            <div className="text-[0.9375rem] text-ink-muted">
              <Markdown text={turn.answer} />
            </div>
          ) : turn.status === "running" ? (
            <p className="text-[0.9375rem] text-ink-faint">Routing…</p>
          ) : null}


          {turn.status === "done" ? (
            <>
              <RouteBadge turn={turn} />
              <details className="group">
                <summary className="cursor-pointer list-none text-[0.75rem] text-ink-faint transition-colors hover:text-ink-muted">
                  Show the scores
                </summary>
                <div className="mt-2.5 flex flex-col gap-2.5">
                  {turn.decision ? <Scores decision={turn.decision} /> : null}
                  <Trace steps={turn.steps} />
                </div>
              </details>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- composer -- */

const SUGGESTIONS = [
  "Fix a race condition in a Go worker pool that drops results",
  "How should I lay out a dark mode dashboard?",
  "Draft a three-line changelog entry",
];

export function Composer({
  value,
  onChange,
  onSubmit,
  busy,
  showSuggestions,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: (q: string) => void;
  busy: boolean;
  showSuggestions: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const q = value.trim();
    if (!q || busy) return;
    onSubmit(q);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex flex-col gap-3.5">
      <form
        onSubmit={submit}
        className="glass-strong glass-line flex items-end gap-2 rounded-[1.375rem] border p-2 pl-4 shadow-[inset_0_1px_0_0_var(--glass-highlight),0_8px_24px_-12px_rgb(0_0_0/0.28)] transition-shadow focus-within:shadow-[inset_0_1px_0_0_var(--glass-highlight),0_14px_36px_-12px_rgb(0_0_0/0.42)]"
      >
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask anything — the router picks the model"
          className="max-h-50 min-w-0 flex-1 resize-none bg-transparent py-2.5 text-[0.9375rem] leading-relaxed text-ink outline-none placeholder:text-ink-faint"
        />
        <button
          type="submit"
          disabled={busy || !value.trim()}
          aria-label="Send"
          className={cx(
            "flex size-9 shrink-0 items-center justify-center rounded-full transition-all duration-200",
            busy || !value.trim()
              ? "bg-ink/[0.06] text-ink-faint dark:bg-white/[0.07]"
              : "bg-accent text-canvas shadow-md shadow-accent/25 hover:scale-105 active:scale-95",
          )}
        >
          {busy ? <Square size={12} fill="currentColor" /> : <ArrowUp size={17} strokeWidth={2.6} />}
        </button>
      </form>

      {showSuggestions ? (
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onSubmit(s)}
              className="glass glass-line rounded-full border px-3.5 py-1.5 text-[0.8125rem] text-ink-muted transition-all duration-200 hover:-translate-y-px hover:text-ink hover:shadow-md hover:shadow-black/10 dark:hover:shadow-black/40"
            >
              {s}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
