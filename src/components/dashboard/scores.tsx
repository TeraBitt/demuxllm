"use client";

import { Check } from "lucide-react";
import { cx } from "@/components/ui/primitives";
import { TIER_VAR, byId } from "@/lib/dashboard/models";
import type { Decision } from "@/lib/dashboard/router";

/**
 * The routing decision, shown as the numbers it was actually made from.
 *
 * The bar line is the load-bearing part: without it a reader sees five scores
 * and no reason the cheapest one was picked. With it the rule is visible —
 * clear the bar, then cost decides — and the choice becomes checkable rather
 * than something the product asserts.
 */
export function Scores({ decision }: { decision: Decision }) {
  const ranked = [...decision.scores].sort((a, b) => b.quality - a.quality);

  return (
    <div className="glass glass-line edge-lit overflow-hidden rounded-2xl border">
      <div className="glass-line flex items-baseline gap-2 border-b px-3.5 py-2.5">
        <span className="text-[0.75rem] tracking-[0.06em] text-ink-faint uppercase">
          Scored
        </span>
        <span className="ml-auto text-[0.75rem] text-ink-muted tabular-nums">
          {decision.pinned ? "pinned — bar not applied" : `needs ${decision.bar}/100`}
        </span>
      </div>

      <ul className="glass-line divide-y">
        {ranked.map((s) => {
          const model = byId(s.modelId);
          if (!model) return null;
          const passes = s.quality >= decision.bar;
          const isChosen = model.id === decision.chosen.id;

          return (
            <li
              key={s.modelId}
              className={cx(
                "relative flex items-center gap-3 px-3.5 py-2.5",
                // The pick is never dimmed, even when a pin put it below the bar.
                !passes && !isChosen && "opacity-45",
              )}
            >
              <span
                aria-hidden
                className="size-1.5 shrink-0 rounded-full"
                style={{ background: TIER_VAR[model.tier] }}
              />

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={cx(
                      "truncate text-[0.8125rem]",
                      isChosen ? "font-medium text-ink" : "text-ink-muted",
                    )}
                  >
                    {model.label}
                  </span>
                  {isChosen ? (
                    <span className="flex shrink-0 items-center gap-1 text-[0.6875rem] font-medium text-accent">
                      <Check size={11} strokeWidth={3} />
                      picked
                    </span>
                  ) : null}
                </div>
                {s.note ? (
                  <p className="mt-0.5 truncate text-[0.6875rem] text-ink-faint">
                    {s.note}
                  </p>
                ) : null}
              </div>

              <span className="w-16 shrink-0 text-right text-[0.6875rem] text-ink-faint tabular-nums">
                ${model.inPer1M}/${model.outPer1M}
              </span>

              {/* Quality against the bar, so "just cleared" is visible. */}
              <div className="relative hidden h-1 w-20 shrink-0 overflow-hidden rounded-full bg-ink/[0.07] sm:block dark:bg-white/[0.09]">
                <span
                  className={cx(
                    "block h-full rounded-full",
                    isChosen ? "bg-accent" : passes ? "bg-ink-muted" : "bg-ink-faint",
                  )}
                  style={{ width: `${s.quality}%` }}
                />
                <span
                  aria-hidden
                  className="absolute inset-y-0 w-px bg-ink/40 dark:bg-white/50"
                  style={{ left: `${decision.bar}%` }}
                />
              </div>

              <span
                className={cx(
                  "w-7 shrink-0 text-right text-[0.8125rem] tabular-nums",
                  isChosen ? "font-medium text-accent" : "text-ink-muted",
                )}
              >
                {s.quality}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
