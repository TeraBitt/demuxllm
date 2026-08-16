"use client";

import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Brain,
  Check,
  Copy,
  Info,
  RefreshCw,
  Square,
  Wrench,
} from "lucide-react";
import { LogoMarkCompact } from "@/components/brand";
import { cx } from "@/components/ui/primitives";
import { Markdown } from "@/components/dashboard/markdown";
import { Thinking } from "@/components/dashboard/thinking";
import { ToolCall } from "@/components/dashboard/tool-call";
import { Trace } from "@/components/dashboard/trace";
import { Scores } from "@/components/dashboard/scores";
import { TIER_VAR, usd } from "@/lib/dashboard/models";
import { type Part, type Turn, answerOf } from "@/lib/dashboard/session";

/* ------------------------------------------------------------ route badge -- */

function RouteBadge({ turn }: { turn: Turn }) {
  if (!turn.chosen || !turn.decision) return null;

  const saved = turn.baselineUsd > 0 ? 1 - turn.costUsd / turn.baselineUsd : 0;
  const score = turn.decision.scores.find((s) => s.modelId === turn.chosen!.id);
  const thought = turn.parts.some((p) => p.kind === "reasoning");
  const tools = turn.parts.filter((p) => p.kind === "tool").length;

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

      {turn.decision.pinned ? (
        <span className="text-ink-faint">pinned</span>
      ) : score ? (
        <span className="text-ink-faint tabular-nums">
          scored {score.quality}, needed {turn.decision.bar}
        </span>
      ) : null}

      {thought ? (
        <span className="flex items-center gap-1 text-ink-faint">
          <Brain size={11} strokeWidth={2.2} />
          reasoned
        </span>
      ) : null}

      {tools ? (
        <span className="flex items-center gap-1 text-ink-faint">
          <Wrench size={11} strokeWidth={2.2} />
          {tools} tool {tools === 1 ? "call" : "calls"}
        </span>
      ) : null}

      {saved > 0.005 ? (
        <span className="font-medium text-accent tabular-nums">
          {Math.round(saved * 100)}% cheaper than the top model
        </span>
      ) : (
        <span className="text-ink-faint tabular-nums">{usd(turn.costUsd, 4)}</span>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- actions -- */

function Action({
  icon: Icon,
  label,
  onClick,
  active,
}: {
  icon: typeof Copy;
  label: string;
  onClick: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cx(
        "flex size-7 items-center justify-center rounded-lg transition-colors",
        active ? "text-accent" : "text-ink-faint hover:bg-ink/[0.05] hover:text-ink dark:hover:bg-white/[0.06]",
      )}
    >
      <Icon size={13} strokeWidth={2.2} />
    </button>
  );
}

function MessageActions({
  turn,
  onRegenerate,
  canRegenerate,
}: {
  turn: Turn;
  onRegenerate: () => void;
  canRegenerate: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [detail, setDetail] = useState(false);

  function copy() {
    navigator.clipboard?.writeText(answerOf(turn)).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      },
      () => {},
    );
  }

  return (
    <>
      <div className="flex items-center gap-0.5">
        <Action icon={copied ? Check : Copy} label="Copy answer" onClick={copy} active={copied} />
        <Action
          icon={Info}
          label="Show how it was routed"
          onClick={() => setDetail((d) => !d)}
          active={detail}
        />
        {canRegenerate ? (
          <Action icon={RefreshCw} label="Run again with current settings" onClick={onRegenerate} />
        ) : null}
      </div>

      {detail ? (
        <div className="flex flex-col gap-2.5">
          {turn.decision ? <Scores decision={turn.decision} /> : null}
          {turn.steps.length ? <Trace steps={turn.steps} /> : null}
        </div>
      ) : null}
    </>
  );
}

/* --------------------------------------------------------------- message -- */

function Parts({
  parts,
  streaming,
  thinkingMs,
}: {
  parts: Part[];
  streaming: boolean;
  thinkingMs: number;
}) {
  const lastText = [...parts].reverse().find((p) => p.kind === "text");

  return (
    <>
      {parts.map((part, i) => {
        if (part.kind === "reasoning") {
          // The trace is still being written only while it is the newest part.
          const isLast = i === parts.length - 1;
          return (
            <Thinking
              key={`r${i}`}
              text={part.text}
              streaming={streaming && isLast}
              ms={thinkingMs}
            />
          );
        }

        if (part.kind === "tool") {
          return (
            <ToolCall
              key={part.id}
              name={part.name}
              args={part.args}
              result={part.result}
              ms={part.ms}
            />
          );
        }

        return (
          <div key={`t${i}`} className="text-[0.9375rem] text-ink-muted">
            <Markdown text={part.text} />
            {streaming && part === lastText ? (
              <span
                aria-hidden
                className="ml-0.5 inline-block h-[0.95em] w-[2px] translate-y-[0.12em] animate-pulse bg-accent align-middle"
              />
            ) : null}
          </div>
        );
      })}
    </>
  );
}

export function Message({
  turn,
  onRegenerate,
  canRegenerate,
}: {
  turn: Turn;
  onRegenerate: () => void;
  canRegenerate: boolean;
}) {
  const streaming = turn.status === "running";
  const started = turn.parts.length > 0;

  return (
    <div className="group/turn flex flex-col gap-5">
      <div className="flex justify-end">
        <div className="glass-strong glass-line edge-lit max-w-[85%] rounded-2xl rounded-br-lg border px-4 py-2.5 text-[0.9375rem] leading-relaxed whitespace-pre-wrap">
          {turn.question}
        </div>
      </div>

      <div className="flex gap-3">
        <LogoMarkCompact className="mt-0.5 h-6 w-6 shrink-0" />

        <div className="flex min-w-0 flex-1 flex-col gap-3.5">
          {/* While the route is still being decided there is nothing else to
              show, so the trace stands in for the answer. */}
          {streaming && !started && turn.steps.length ? <Trace steps={turn.steps} /> : null}

          <Parts parts={turn.parts} streaming={streaming} thinkingMs={turn.thinkingMs} />

          {streaming && !started && !turn.steps.length ? (
            <p className="text-[0.9375rem] text-ink-faint">Routing…</p>
          ) : null}

          {/* A model can spend its whole budget on tool calls and never answer.
              Saying so beats a badge floating under nothing. */}
          {turn.status === "done" && !answerOf(turn).trim() && !turn.error ? (
            <p className="text-[0.9375rem] text-ink-faint">
              {turn.parts.some((p) => p.kind === "tool")
                ? "Ran the tools but stopped before writing an answer. Try again, or raise the tool-round ceiling under Settings."
                : "The model returned nothing. Try again."}
            </p>
          ) : null}

          {turn.status === "stopped" ? (
            <p className="text-[0.75rem] text-ink-faint">Stopped.</p>
          ) : null}

          {turn.error ? (
            <div className="glass glass-line rounded-2xl border p-3.5 text-[0.8125rem] text-ink-muted">
              <span className="font-medium text-ink">That run failed. </span>
              {turn.error}
              {canRegenerate ? (
                <button
                  type="button"
                  onClick={onRegenerate}
                  className="mt-2.5 flex items-center gap-1.5 text-[0.8125rem] text-accent transition-opacity hover:opacity-75"
                >
                  <RefreshCw size={12} strokeWidth={2.4} />
                  Try again
                </button>
              ) : null}
            </div>
          ) : null}

          {turn.status === "done" ? (
            <>
              <RouteBadge turn={turn} />
              <MessageActions
                turn={turn}
                onRegenerate={onRegenerate}
                canRegenerate={canRegenerate}
              />
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- composer -- */

export const SUGGESTIONS = [
  {
    label: "Cheapest model with vision",
    prompt: "Which model in the pool handles images for the least money? Show me the options.",
  },
  {
    label: "Price 50k requests",
    prompt:
      "We send 50,000 requests a month, roughly 900 tokens in and 400 out. What does that cost routed, versus running everything on the frontier model?",
  },
  {
    label: "Fix a Go race",
    prompt: "Fix a race condition in a Go worker pool that silently drops results.",
  },
  {
    label: "Where has my spend gone?",
    prompt: "Break down what I've spent so far by model, and tell me where the savings came from.",
  },
];

export function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  busy,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: (q: string) => void;
  onStop: () => void;
  busy: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  // Focus follows the run: the box is ready again the moment an answer lands.
  useEffect(() => {
    if (!busy) ref.current?.focus();
  }, [busy]);

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
    <div>
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
          type={busy ? "button" : "submit"}
          onClick={busy ? onStop : undefined}
          disabled={!busy && !value.trim()}
          aria-label={busy ? "Stop" : "Send"}
          title={busy ? "Stop (Esc)" : "Send"}
          className={cx(
            "flex size-9 shrink-0 items-center justify-center rounded-full transition-all duration-200",
            busy
              ? "bg-ink text-canvas hover:scale-105 active:scale-95"
              : value.trim()
                ? "bg-accent text-canvas shadow-md shadow-accent/25 hover:scale-105 active:scale-95"
                : "bg-ink/[0.06] text-ink-faint dark:bg-white/[0.07]",
          )}
        >
          {busy ? <Square size={11} fill="currentColor" /> : <ArrowUp size={17} strokeWidth={2.6} />}
        </button>
      </form>
    </div>
  );
}
