"use client";

import { useMemo, useState } from "react";
import { m } from "@/components/ui/motion";
import { Section, SectionHeading } from "@/components/ui/primitives";

const SPEND_STEPS = [1_000, 5_000, 10_000, 50_000, 100_000, 500_000];

const TIERS = [
  { key: "budget", label: "Small models", color: "var(--tier-1)" },
  { key: "mid", label: "Mid-range", color: "var(--tier-2)" },
  { key: "premium", label: "Biggest", color: "var(--tier-3)" },
] as const;

/** Distribution and savings both follow from one setting: how careful to be. */
const MODES = [
  {
    key: "save",
    label: "Save the most",
    hint: "Best for internal tools and bulk work",
    rate: 0.58,
    split: { budget: 0.62, mid: 0.31, premium: 0.07 },
  },
  {
    key: "balanced",
    label: "Balanced",
    hint: "What most teams pick",
    rate: 0.4,
    split: { budget: 0.43, mid: 0.37, premium: 0.2 },
  },
  {
    key: "quality",
    label: "Play it safe",
    hint: "Best for anything a customer sees",
    rate: 0.24,
    split: { budget: 0.21, mid: 0.45, premium: 0.34 },
  },
] as const;

const usd = (n: number) =>
  n >= 1000 ? `$${(n / 1000).toFixed(n >= 100_000 ? 0 : 1)}k` : `$${Math.round(n)}`;

export function Savings() {
  const [spendIdx, setSpendIdx] = useState(2);
  const [modeIdx, setModeIdx] = useState(1);

  const spend = SPEND_STEPS[spendIdx];
  const mode = MODES[modeIdx];
  const saved = useMemo(() => spend * mode.rate, [spend, mode]);

  return (
    <Section>
      <SectionHeading
        eyebrow="Savings"
        title="See what it would save you."
        lede="Two questions: what do you spend on AI today, and how careful do you want us to be?"
      />

      <div className="mt-10 grid gap-3 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        {/* Controls */}
        <div className="flex flex-col gap-7 rounded-xl border border-line bg-elevated p-6">
          <div>
            <div className="flex items-baseline justify-between">
              <label htmlFor="spend" className="text-[0.9375rem] font-medium">
                You spend about
              </label>
              <span className="text-lg font-semibold tabular-nums">
                {usd(spend)}
                <span className="text-sm font-normal text-ink-muted"> / mo</span>
              </span>
            </div>
            <input
              id="spend"
              type="range"
              min={0}
              max={SPEND_STEPS.length - 1}
              step={1}
              value={spendIdx}
              onChange={(e) => setSpendIdx(Number(e.target.value))}
              className="mt-4 w-full accent-[var(--accent)]"
            />
          </div>

          <div className="border-t border-line pt-6">
            <p className="text-[0.9375rem] font-medium">How careful should we be?</p>
            <div className="mt-3 flex flex-col gap-1.5">
              {MODES.map((mo, i) => (
                <button
                  key={mo.key}
                  type="button"
                  onClick={() => setModeIdx(i)}
                  className={`rounded-lg border px-3.5 py-2.5 text-left transition-colors ${
                    i === modeIdx
                      ? "border-accent/45 bg-accent/[0.07]"
                      : "border-line hover:bg-surface"
                  }`}
                >
                  <span
                    className={`block text-[0.875rem] ${
                      i === modeIdx ? "font-medium text-ink" : "text-ink-muted"
                    }`}
                  >
                    {mo.label}
                  </span>
                  <span className="block text-[0.75rem] text-ink-faint">
                    {mo.hint}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Result */}
        <div className="flex flex-col gap-3">
          <div className="rounded-xl border border-line bg-elevated p-6 sm:p-8">
            <p className="text-[0.9375rem] text-ink-muted">You would save about</p>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-5xl font-semibold tracking-[-0.04em] text-accent tabular-nums sm:text-6xl">
                {usd(saved)}
              </span>
              <span className="text-lg text-ink-muted">a month</span>
            </div>
            <p className="mt-3 text-[0.9375rem] text-ink-muted">
              That is {Math.round(mode.rate * 100)}% off your bill — about{" "}
              <span className="text-ink">{usd(saved * 12)}</span> a year. Your new
              bill would be around{" "}
              <span className="text-ink">{usd(spend - saved)}</span> a month.
            </p>
          </div>

          <div className="rounded-xl border border-line bg-elevated p-6">
            <h3 className="text-[0.9375rem] font-medium">
              Where your questions would go
            </h3>

            <div className="mt-4 flex h-8 gap-0.5 overflow-hidden rounded-lg">
              {TIERS.map((t) => (
                <m.div
                  key={t.key}
                  className="h-full"
                  style={{ background: t.color }}
                  animate={{ width: `${mode.split[t.key] * 100}%` }}
                  transition={{ type: "spring", stiffness: 220, damping: 30 }}
                />
              ))}
            </div>

            <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
              {TIERS.map((t) => (
                <li key={t.key} className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="size-2 rounded-full"
                    style={{ background: t.color }}
                  />
                  <span className="text-[0.875rem] text-ink-muted">{t.label}</span>
                  <span className="text-[0.875rem] font-medium tabular-nums">
                    {Math.round(mode.split[t.key] * 100)}%
                  </span>
                </li>
              ))}
            </ul>

            <p className="mt-5 border-t border-line pt-4 text-[0.8125rem] text-ink-faint">
              An estimate, not a quote. We plan on the cautious side — the real
              number depends on the questions you actually ask, and you will see it
              on your dashboard within a day of switching.
            </p>
          </div>
        </div>
      </div>
    </Section>
  );
}
