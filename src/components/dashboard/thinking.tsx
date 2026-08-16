"use client";

import { useEffect, useRef, useState } from "react";
import { Brain, ChevronRight } from "lucide-react";
import { cx } from "@/components/ui/primitives";

/**
 * The reasoning trace.
 *
 * Open while it is being produced and shut the moment the answer starts. That
 * ordering is the point: a trace is interesting exactly while it is the only
 * thing happening, and in the way once there is an answer to read. It stays one
 * click from being reopened, because the demo's whole argument is that you can
 * see what you paid for.
 */
export function Thinking({
  text,
  streaming,
  ms,
}: {
  text: string;
  /** True while tokens are still arriving on the reasoning channel. */
  streaming: boolean;
  /** Wall-clock the trace took, once it is finished. */
  ms: number;
}) {
  // Null until the reader takes the wheel; after that their choice sticks. Derived
  // rather than synced, so the panel cannot briefly disagree with itself.
  const [manual, setManual] = useState<boolean | null>(null);
  const open = manual ?? streaming;
  const scroller = useRef<HTMLDivElement>(null);

  // Follow the trace down while it writes.
  useEffect(() => {
    if (!open || !streaming) return;
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [open, streaming, text]);

  const seconds = ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : ms ? `${ms}ms` : "";

  return (
    <div className="glass glass-line edge-lit overflow-hidden rounded-2xl border">
      <button
        type="button"
        onClick={() => setManual(!open)}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left transition-colors hover:bg-ink/[0.02] dark:hover:bg-white/[0.03]"
      >
        <Brain
          size={14}
          className={cx("shrink-0 text-accent", streaming && "animate-pulse")}
          strokeWidth={2}
        />
        <span className="text-[0.8125rem] font-medium">
          {streaming ? "Thinking" : seconds ? `Thought for ${seconds}` : "Thought this through"}
        </span>
        {streaming ? (
          <span className="flex gap-1" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="size-1 animate-bounce rounded-full bg-accent/70"
                style={{ animationDelay: `${i * 140}ms`, animationDuration: "900ms" }}
              />
            ))}
          </span>
        ) : null}
        <ChevronRight
          size={14}
          className={cx(
            "ml-auto shrink-0 text-ink-faint transition-transform duration-200",
            open && "rotate-90",
          )}
        />
      </button>

      {open ? (
        <div
          ref={scroller}
          className="glass-line max-h-56 overflow-y-auto border-t px-3.5 py-3"
        >
          <p className="text-[0.8125rem] leading-relaxed whitespace-pre-wrap text-ink-faint">
            {text}
            {streaming ? (
              <span className="ml-0.5 inline-block h-[0.9em] w-[2px] translate-y-[0.1em] animate-pulse bg-accent align-middle" />
            ) : null}
          </p>
        </div>
      ) : null}
    </div>
  );
}
