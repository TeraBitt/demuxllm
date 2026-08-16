"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Brain, Gauge, Route, ShieldAlert, Timer, Wallet, Wrench } from "lucide-react";
import { cx } from "@/components/ui/primitives";
import { TIER_VAR, usd } from "@/lib/dashboard/models";
import { type RunRecord, analyse, byDay, useHistory } from "@/lib/dashboard/history";
import { usePrefs } from "@/lib/dashboard/prefs";
import type { Scope } from "@/lib/dashboard/router";

/**
 * The metrics view, built only from runs that actually happened.
 *
 * The reference dashboards for this pattern open on six figures of traffic and
 * a five-figure saving. Inventing those would make every real number beside
 * them unreadable — nobody can tell which of the two is the demo. So this reads
 * the local run history and shows an empty state until there is something true
 * to plot.
 *
 * The chart is one dollar axis carrying two series, never two axes: spend and
 * the frontier-only baseline are the same unit, and their gap IS the product.
 */

const RANGES = [
  { days: 7, label: "7D" },
  { days: 30, label: "30D" },
  { days: 90, label: "90D" },
] as const;

function Tile({
  icon: Icon,
  label,
  value,
  spark,
}: {
  icon: typeof Route;
  label: string;
  value: string;
  spark: number[];
}) {
  const max = Math.max(1, ...spark);
  const pts = spark
    .map((v, i) => `${(i / Math.max(1, spark.length - 1)) * 100},${28 - (v / max) * 24}`)
    .join(" ");

  return (
    <div className="glass glass-line edge-lit rounded-2xl border p-4">
      <div className="flex items-start justify-between gap-3">
        <span className="flex size-8 items-center justify-center rounded-full bg-ink/[0.05] text-ink-muted dark:bg-white/[0.06]">
          <Icon size={15} strokeWidth={2} />
        </span>
        {spark.some((v) => v > 0) ? (
          <svg viewBox="0 0 100 30" className="h-7 w-20" preserveAspectRatio="none" aria-hidden>
            <polyline
              points={pts}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        ) : null}
      </div>
      <div className="mt-3.5 text-[0.75rem] text-ink-muted">{label}</div>
      <div className="mt-1 text-[1.625rem] leading-none font-semibold tracking-[-0.03em] tabular-nums">
        {value}
      </div>
    </div>
  );
}

function Chart({ days }: { days: { at: number; cost: number; baseline: number }[] }) {
  const max = Math.max(...days.map((d) => d.baseline), 0.0001);
  const W = 100;
  const H = 40;
  const x = (i: number) => (i / Math.max(1, days.length - 1)) * W;
  const y = (v: number) => H - (v / max) * H;

  const line = (pick: (d: (typeof days)[number]) => number) =>
    days.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(pick(d))}`).join(" ");
  const area = (pick: (d: (typeof days)[number]) => number) =>
    `${line(pick)} L${W},${H} L0,${H} Z`;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-56 w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="baseFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--series-2)" stopOpacity={0.16} />
            <stop offset="100%" stopColor="var(--series-2)" stopOpacity={0.01} />
          </linearGradient>
          <linearGradient id="costFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.22} />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75].map((g) => (
          <line
            key={g}
            x1={0}
            x2={W}
            y1={H * g}
            y2={H * g}
            stroke="var(--line)"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
        ))}

        <path d={area((d) => d.baseline)} fill="url(#baseFill)" />
        <path
          d={line((d) => d.baseline)}
          fill="none"
          stroke="var(--series-2)"
          strokeWidth={2}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        <path d={area((d) => d.cost)} fill="url(#costFill)" />
        <path
          d={line((d) => d.cost)}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={2}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>

      <div className="mt-2 flex justify-between text-[0.6875rem] text-ink-faint">
        <span>{new Date(days[0].at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
        <span>latest</span>
      </div>
    </div>
  );
}

function RecentRoutes({ runs }: { runs: RunRecord[] }) {
  return (
    <div className="glass glass-line edge-lit rounded-2xl border">
      <div className="glass-line border-b px-4 py-3.5">
        <h2 className="text-[0.9375rem] font-medium">Recent routes</h2>
      </div>
      <ul className="glass-line divide-y">
        {runs.map((r, i) => (
          <li key={i} className="flex items-center gap-3 px-4 py-3">
            <span
              aria-hidden
              className="size-1.5 shrink-0 rounded-full"
              style={{ background: TIER_VAR[r.tier] }}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[0.8125rem]">{r.topic}</p>
              <p className="mt-0.5 flex items-center gap-1.5 text-[0.6875rem] text-ink-faint">
                <span className="truncate">
                  {r.modelLabel} · scored {r.quality}, needed {r.bar}
                </span>
                {r.thought ? <Brain size={10} className="shrink-0" /> : null}
                {r.toolCalls ? (
                  <span className="flex shrink-0 items-center gap-0.5">
                    <Wrench size={10} />
                    {r.toolCalls}
                  </span>
                ) : null}
              </p>
            </div>
            <span className="w-16 shrink-0 text-right font-mono text-[0.75rem] text-ink-muted tabular-nums">
              {usd(r.costUsd, 4)}
            </span>
            <span className="hidden w-12 shrink-0 text-right font-mono text-[0.75rem] text-ink-faint tabular-nums sm:block">
              {(r.ms / 1000).toFixed(1)}s
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------- prompt analytics -- */

const SCOPE_META: Record<Scope, { label: string; color: string }> = {
  work: { label: "Company work", color: "var(--accent)" },
  outside: { label: "Outside it", color: "var(--series-2)" },
  unclear: { label: "Unclear", color: "color-mix(in oklab, var(--ink) 35%, transparent)" },
};

/**
 * Where the money went, split by whether the request was company work.
 *
 * Spend is the unit, not request counts: a hundred greetings and one migration
 * are not the same question. The unclear share is drawn as loudly as the other
 * two, because a router that quietly filed every ambiguous request as "work"
 * would produce a cleaner chart and a false one.
 */
function PromptAnalytics({ runs }: { runs: RunRecord[] }) {
  const { prefs } = usePrefs();
  const a = analyse(runs);
  const configured = Boolean(prefs.orgContext.trim());
  const pct = (n: number) => (a.total > 0 ? (n / a.total) * 100 : 0);

  return (
    <div className="glass glass-line edge-lit rounded-2xl border p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-[0.9375rem] font-medium">
          Prompt analytics{prefs.orgName.trim() ? ` · ${prefs.orgName.trim()}` : ""}
        </h2>
        <span className="text-[0.75rem] text-ink-faint">
          {usd(a.total, 4)} across {runs.length} {runs.length === 1 ? "request" : "requests"}
        </span>
      </div>

      {configured ? null : (
        <p className="mt-2 text-[0.75rem] leading-relaxed text-ink-faint">
          No workspace description set, so every request is filed as unclear.
          Describe what this team works on under Settings to split the spend.
        </p>
      )}

      <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-ink/[0.06] dark:bg-white/[0.08]">
        {a.byScope.map((s) =>
          s.cost > 0 ? (
            <span
              key={s.scope}
              className="h-full"
              style={{ width: `${pct(s.cost)}%`, background: SCOPE_META[s.scope].color }}
            />
          ) : null,
        )}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-3">
        {a.byScope.map((s) => (
          <div key={s.scope}>
            <div className="flex items-center gap-1.5 text-[0.75rem] text-ink-muted">
              <span
                aria-hidden
                className="size-1.5 shrink-0 rounded-full"
                style={{ background: SCOPE_META[s.scope].color }}
              />
              {SCOPE_META[s.scope].label}
            </div>
            <div className="mt-1 text-[1.125rem] leading-none font-semibold tabular-nums">
              {Math.round(pct(s.cost))}%
            </div>
            <div className="mt-1 text-[0.6875rem] text-ink-faint tabular-nums">
              {s.runs} · {usd(s.cost, 4)}
            </div>
          </div>
        ))}
      </div>

      {a.byCategory.length ? (
        <ul className="mt-5 flex flex-col gap-2">
          {a.byCategory.slice(0, 5).map((c) => (
            <li key={c.category} className="flex items-center gap-3">
              <span className="w-28 shrink-0 truncate text-[0.75rem] text-ink-muted">
                {c.category}
              </span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink/[0.06] dark:bg-white/[0.08]">
                <span
                  className="block h-full rounded-full bg-accent/70"
                  style={{ width: `${Math.max(2, pct(c.cost))}%` }}
                />
              </span>
              <span className="w-16 shrink-0 text-right font-mono text-[0.6875rem] text-ink-faint tabular-nums">
                {usd(c.cost, 4)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="glass-line mt-5 flex flex-wrap gap-x-5 gap-y-1.5 border-t pt-3.5 text-[0.75rem] text-ink-faint">
        {/* What the extra capability was spent on, not what was offered. */}
        <span className="flex items-center gap-1.5">
          <Brain size={13} />
          {a.reasoned} of {runs.length} bought reasoning
        </span>
        <span className="flex items-center gap-1.5">
          <Wrench size={13} />
          {a.toolCalls} tool {a.toolCalls === 1 ? "call" : "calls"}
        </span>
        {a.sensitive ? (
          <span className="flex items-center gap-1.5">
            <ShieldAlert size={13} />
            {a.sensitive} carried sensitive data
          </span>
        ) : null}
        {a.lowConfidence ? (
          <span>{a.lowConfidence} classified with low confidence</span>
        ) : null}
      </div>
    </div>
  );
}

export function Overview() {
  const { runs, clear } = useHistory();
  const [range, setRange] = useState<(typeof RANGES)[number]["days"]>(7);
  // Anchor the buckets to the newest run rather than the wall clock: reading a
  // clock during render is impure and differs between server and client, and
  // with no runs there is nothing to plot anyway.
  const latest = runs.length ? Math.max(...runs.map((r) => r.at)) : null;

  const cost = runs.reduce((n, r) => n + r.costUsd, 0);
  const baseline = runs.reduce((n, r) => n + r.baselineUsd, 0);
  const saved = baseline - cost;
  const avgMs = runs.length ? runs.reduce((n, r) => n + r.ms, 0) / runs.length : 0;
  const cleared = runs.filter((r) => r.quality >= r.bar).length;

  const days = latest ? byDay(runs, range, latest) : null;
  const spark = days?.map((d) => d.runs) ?? [];

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-8 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.03em]">Dashboard</h1>
          <p className="mt-1.5 text-[0.875rem] text-ink-muted">
            {runs.length
              ? `${runs.length} ${runs.length === 1 ? "route" : "routes"} on this device`
              : "No routes yet — every number here comes from real runs"}
          </p>
        </div>
        <Link
          href="/dashboard/chat"
          className="glass-strong glass-line edge-lit inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-[0.875rem] font-medium transition-transform hover:-translate-y-px"
        >
          Open assistant
          <ArrowRight size={15} strokeWidth={2.2} />
        </Link>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile icon={Route} label="Requests routed" value={runs.length.toLocaleString("en-US")} spark={spark} />
        <Tile icon={Wallet} label="Saved" value={usd(saved, 4)} spark={days?.map((d) => d.baseline - d.cost) ?? []} />
        <Tile
          icon={Timer}
          label="Average latency"
          value={runs.length ? `${(avgMs / 1000).toFixed(1)}s` : "—"}
          spark={[]}
        />
        <Tile
          icon={Gauge}
          label="Cleared the bar"
          value={runs.length ? `${Math.round((cleared / runs.length) * 100)}%` : "—"}
          spark={[]}
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="glass glass-line edge-lit rounded-2xl border p-5">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
            <h2 className="text-[0.9375rem] font-medium">Spend against frontier-only</h2>
            <div className="flex items-center gap-3 text-[0.75rem]">
              <span className="flex items-center gap-1.5 text-ink-muted">
                <span aria-hidden className="h-0.5 w-3 rounded-full bg-accent" />
                Paid
              </span>
              <span className="flex items-center gap-1.5 text-ink-faint">
                <span
                  aria-hidden
                  className="h-0.5 w-3 rounded-full"
                  style={{ background: "var(--series-2)" }}
                />
                Top model only
              </span>
            </div>
            <div className="edge-sunk ml-auto flex gap-0.5 rounded-xl bg-ink/[0.04] p-1 dark:bg-black/25">
              {RANGES.map((r) => (
                <button
                  key={r.days}
                  type="button"
                  onClick={() => setRange(r.days)}
                  className={cx(
                    "rounded-lg px-2.5 py-1 text-[0.75rem] font-medium transition-all",
                    range === r.days
                      ? "glass-strong text-ink shadow-[inset_0_1px_0_0_var(--glass-highlight),0_1px_3px_0_rgb(0_0_0/0.12)]"
                      : "text-ink-faint hover:text-ink-muted",
                  )}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5">
            {days && runs.length ? (
              <Chart days={days} />
            ) : (
              <div className="flex h-56 items-center justify-center text-center">
                <p className="max-w-xs text-[0.8125rem] leading-relaxed text-ink-faint">
                  Ask the assistant something. Each answered request lands here
                  with what it cost and what the top model would have charged.
                </p>
              </div>
            )}
          </div>
        </div>

        {runs.length ? (
          <RecentRoutes runs={[...runs].reverse().slice(0, 6)} />
        ) : (
          <div className="glass glass-line edge-lit flex items-center justify-center rounded-2xl border p-5">
            <p className="max-w-[15rem] text-center text-[0.8125rem] leading-relaxed text-ink-faint">
              Routes appear here as they happen, newest first.
            </p>
          </div>
        )}
      </div>

      {runs.length ? <PromptAnalytics runs={runs} /> : null}

      {runs.length ? (
        <button
          type="button"
          onClick={clear}
          className="self-start text-[0.75rem] text-ink-faint transition-colors hover:text-ink"
        >
          Clear history on this device
        </button>
      ) : null}
    </div>
  );
}
