"use client";

import { Check, Loader2 } from "lucide-react";
import { cx } from "@/components/ui/primitives";
import type { StepEvent } from "@/lib/dashboard/graph";
import { TIER_VAR, usd } from "@/lib/dashboard/models";

/**
 * The LangGraph run, as it happens.
 *
 * This is the most important surface in the dashboard: it is the difference
 * between "a chatbot answered" and "six decisions were made on your behalf and
 * here is what each one cost". Each row is one graph node, and the bar behind
 * it is that node's cost against what the frontier model would have charged for
 * the same node.
 */
export function Trace({ steps }: { steps: StepEvent[] }) {
  if (steps.length === 0) return null;

  const widest = Math.max(...steps.map((s) => s.baselineUsd), 1e-9);

  return (
    <div className="glass glass-line edge-lit overflow-hidden rounded-2xl border">
      <div className="glass-line flex items-center gap-2 border-b px-3.5 py-2.5">
        <span className="text-[0.75rem] tracking-[0.06em] text-ink-faint uppercase">
          Run
        </span>
        <span className="ml-auto text-[0.75rem] text-ink-faint tabular-nums">
          {steps.filter((s) => s.status === "done").length}/{steps.length} steps
        </span>
      </div>

      <ul>
        {steps.map((s) => (
          <li
            key={s.id}
            className="glass-line relative overflow-hidden border-b last:border-b-0"
          >
            <span
              aria-hidden
              className="absolute inset-y-0 left-0 bg-ink/[0.035] dark:bg-white/[0.03]"
              style={{ width: `${(s.baselineUsd / widest) * 100}%` }}
            />
            <span
              aria-hidden
              className="absolute inset-y-0 left-0 bg-accent/[0.09]"
              style={{ width: `${(s.costUsd / widest) * 100}%` }}
            />

            <div className="relative flex items-center gap-3 px-3.5 py-2.5">
              <span className="flex size-4 shrink-0 items-center justify-center">
                {s.status === "running" ? (
                  <Loader2
                    size={13}
                    className="animate-spin text-ink-faint"
                    strokeWidth={2.4}
                  />
                ) : (
                  <Check size={13} className="text-accent" strokeWidth={2.8} />
                )}
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[0.8125rem] font-medium">{s.label}</span>
                  {s.model ? (
                    <span className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="size-1.5 shrink-0 rounded-full"
                        style={{ background: TIER_VAR[s.model.tier] }}
                      />
                      <span className="text-[0.75rem] text-ink-muted">
                        {s.model.label}
                      </span>
                    </span>
                  ) : null}
                </div>
                <p className="mt-0.5 truncate text-[0.75rem] text-ink-faint">
                  {s.detail}
                </p>
              </div>

              <div className="shrink-0 text-right tabular-nums">
                <div
                  className={cx(
                    "text-[0.8125rem] font-medium",
                    s.costUsd === 0 ? "text-ink-faint" : "text-ink",
                  )}
                >
                  {s.costUsd === 0 ? "free" : usd(s.costUsd, 5)}
                </div>
                <div className="text-[0.6875rem] text-ink-faint">
                  {s.status === "running" ? "…" : `${s.ms}ms`}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
