"use client";

import { useCallback, useId, useRef, useState } from "react";
import { m } from "@/components/ui/motion";
import { cx } from "@/components/ui/primitives";
import { DECAY_SERIES, DECAY_WEEKS } from "@/lib/data";
import { DECAY, ROUTERBENCH } from "@/lib/measured";

/*
 * Plotted as "share of the possible saving you actually capture", so up is good
 * and the reference line at 0% means "you would have done just as well sending
 * everything to one model". The underlying figures are regret values; captured
 * is simply 1 − regret, converted once here rather than stored twice.
 */
const captured = (vals: readonly number[]) => vals.map((v) => 1 - v);

const FROZEN = captured(DECAY_SERIES.frozen);
const ROLLING = captured(DECAY_SERIES.rolling);

const W = 760;
const H = 320;
const PAD = { t: 28, r: 142, b: 44, l: 52 };
const Y_MAX = 1;
// The measured frozen curve reaches −1.37 by week 26. The axis is sized from the
// data rather than pinned, so a worse decay in a future run cannot silently run
// off the bottom of the plot and read as a plateau.
const Y_MIN = Math.min(-0.2, Math.floor(Math.min(...FROZEN, ...ROLLING) * 10) / 10);
const PLOT_W = W - PAD.l - PAD.r;
const PLOT_H = H - PAD.t - PAD.b;
const LAST = DECAY_WEEKS.length - 1;

const x = (i: number) => PAD.l + (i / LAST) * PLOT_W;
const y = (v: number) => PAD.t + ((Y_MAX - v) / (Y_MAX - Y_MIN)) * PLOT_H;

const line = (vals: readonly number[]) =>
  vals.map((v, i) => `${i === 0 ? "M" : "L"}${x(i)} ${y(v)}`).join(" ");

/** Closed polygon between the curves — the saving that quietly leaks away. */
const GAP_PATH = `${line(ROLLING)} ${FROZEN.map((_, k) => {
  const i = LAST - k;
  return `L${x(i)} ${y(FROZEN[i])}`;
}).join(" ")} Z`;

const SERIES = [
  {
    key: "rolling" as const,
    label: "DemuxLLM",
    values: ROLLING,
    color: "var(--series-1)",
    note: "re-tested every day",
  },
  {
    key: "frozen" as const,
    label: "Built once",
    values: FROZEN,
    color: "var(--series-2)",
    note: "never re-tested",
  },
];

/**
 * Ticks every 25% down to whatever the data reaches. Generated rather than listed
 * because the interesting half of this chart is below zero — a frozen router ends
 * up worse than not routing — and a fixed 0…100% scale would leave that half of
 * the plot unlabelled, which reads as an empty margin rather than as the point.
 */
const Y_TICKS = Array.from(
  { length: Math.round((Y_MAX - Math.ceil(Y_MIN * 4) / 4) / 0.25) + 1 },
  (_, i) => Y_MAX - i * 0.25,
);
const pct = (v: number) => `${Math.round(v * 100)}%`;

export function DecayChart() {
  const [view, setView] = useState<"chart" | "table">("chart");
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const gradientId = useId();

  const onMove = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    // Map client px → viewBox units, then invert the x scale to an index.
    const vx = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((vx - PAD.l) / PLOT_W) * LAST);
    setHover(i >= 0 && i <= LAST ? i : null);
  }, []);

  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-elevated">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3.5 sm:px-5">
        <div>
          <h3 className="text-[0.9375rem] font-medium">
            What happens to a router nobody updates
          </h3>
          <p className="mt-0.5 text-[0.8125rem] text-ink-faint">
            How much of the available saving it still finds, as the months pass
          </p>
        </div>
        <div className="ml-auto flex rounded-lg border border-line p-0.5">
          {(["chart", "table"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={cx(
                "rounded-md px-2.5 py-1 text-[0.8125rem] capitalize transition-colors",
                view === v ? "bg-surface text-ink" : "text-ink-faint hover:text-ink-muted",
              )}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {view === "table" ? (
        <div className="max-h-[330px] overflow-auto">
          <table className="w-full border-collapse text-left">
            <thead className="sticky top-0 bg-surface">
              <tr className="border-b border-line">
                {["Month", "DemuxLLM", "Built once"].map((h) => (
                  <th
                    key={h}
                    scope="col"
                    className="px-5 py-2.5 text-[0.8125rem] font-medium text-ink-muted"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DECAY_WEEKS.map((w, i) => (
                <tr key={w} className="border-b border-line last:border-0">
                  <th
                    scope="row"
                    className="px-5 py-2 text-left text-[0.875rem] font-normal text-ink-muted tabular-nums"
                  >
                    {(w / 4).toFixed(1).replace(".0", "")}
                  </th>
                  <td className="px-5 py-2 text-[0.875rem] tabular-nums">
                    {pct(ROLLING[i])}
                  </td>
                  <td className="px-5 py-2 text-[0.875rem] tabular-nums">
                    {pct(FROZEN[i])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-2 pt-3 sm:px-4">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            className="h-auto w-full touch-none"
            role="img"
            aria-label="Over six months, a router that is re-tested daily holds steady at about 84% of the available saving. A router built once slides from 79% to below 0%, meaning it ends up worse than sending every question to a single model."
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--series-2)" stopOpacity={0.14} />
                <stop offset="100%" stopColor="var(--series-2)" stopOpacity={0.01} />
              </linearGradient>
            </defs>

            {Y_TICKS.map((t) => (
              <g key={t}>
                <line
                  x1={PAD.l}
                  x2={W - PAD.r}
                  y1={y(t)}
                  y2={y(t)}
                  stroke="var(--line)"
                  strokeWidth={1}
                />
                <text
                  x={PAD.l - 10}
                  y={y(t) + 4}
                  textAnchor="end"
                  className="fill-[var(--ink-faint)] text-[11px] tabular-nums"
                >
                  {pct(t)}
                </text>
              </g>
            ))}

            {DECAY_WEEKS.map((w, i) =>
              i % 4 === 0 ? (
                <text
                  key={w}
                  x={x(i)}
                  y={H - PAD.b + 22}
                  textAnchor="middle"
                  className="fill-[var(--ink-faint)] text-[11px]"
                >
                  {w === 0 ? "day one" : `month ${w / 4}`}
                </text>
              ) : null,
            )}

            <path d={GAP_PATH} fill={`url(#${gradientId})`} />

            {/* Zero line: below this you would be better off not routing */}
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={y(0)}
              y2={y(0)}
              stroke="var(--ink-faint)"
              strokeWidth={1.5}
            />
            <text
              x={PAD.l + 6}
              y={y(0) + 18}
              className="fill-[var(--ink-muted)] text-[11px]"
            >
              no better than doing nothing
            </text>

            {SERIES.map((s, si) => (
              <m.path
                key={s.key}
                d={line(s.values)}
                fill="none"
                stroke={s.color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                whileInView={{ pathLength: 1 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{
                  duration: 1.1,
                  delay: si * 0.12,
                  ease: [0.16, 1, 0.3, 1],
                }}
              />
            ))}

            {/* Direct labels, so identity never rests on colour alone */}
            {SERIES.map((s) => {
              const v = s.values[LAST];
              return (
                <g key={`lab-${s.key}`}>
                  <circle
                    cx={x(LAST)}
                    cy={y(v)}
                    r={4}
                    fill={s.color}
                    stroke="var(--elevated)"
                    strokeWidth={2}
                  />
                  <text
                    x={x(LAST) + 12}
                    y={y(v) + 4}
                    className="fill-[var(--ink)] text-[12px]"
                  >
                    {s.label} {pct(v)}
                  </text>
                </g>
              );
            })}

            {hover !== null ? (
              <g pointerEvents="none">
                <line
                  x1={x(hover)}
                  x2={x(hover)}
                  y1={PAD.t}
                  y2={H - PAD.b}
                  stroke="var(--line-strong)"
                  strokeWidth={1}
                />
                {SERIES.map((s) => (
                  <circle
                    key={`h-${s.key}`}
                    cx={x(hover)}
                    cy={y(s.values[hover])}
                    r={4.5}
                    fill={s.color}
                    stroke="var(--elevated)"
                    strokeWidth={2}
                  />
                ))}
              </g>
            ) : null}
          </svg>
        </div>
      )}

      {/* Legend doubles as the tooltip readout */}
      <div className="flex min-h-[2.75rem] flex-wrap items-center gap-x-5 gap-y-1 border-t border-line px-4 py-3 sm:px-5">
        {hover !== null ? (
          <span className="text-[0.8125rem] text-ink-muted tabular-nums">
            {DECAY_WEEKS[hover] === 0
              ? "day one"
              : `week ${DECAY_WEEKS[hover]}`}
          </span>
        ) : null}
        {SERIES.map((s) => (
          <span key={s.key} className="flex items-center gap-2">
            <span
              aria-hidden
              className="size-2 rounded-full"
              style={{ background: s.color }}
            />
            <span className="text-[0.875rem] text-ink">{s.label}</span>
            {hover !== null ? (
              <span className="text-[0.875rem] font-medium tabular-nums">
                {pct(s.values[hover])}
              </span>
            ) : (
              <span className="text-[0.8125rem] text-ink-faint">{s.note}</span>
            )}
          </span>
        ))}
      </div>

      <figcaption className="border-t border-line px-4 py-3 text-[0.8125rem] text-ink-faint sm:px-5">
        Measured, not illustrative. A 26-week replay on RouterBench —{" "}
        {ROUTERBENCH.items.toLocaleString()} real prompts across{" "}
        {ROUTERBENCH.models} real commercial models,{" "}
        {ROUTERBENCH.gradedCells.toLocaleString()} graded answers. Both routers start
        identical; only one keeps testing.{" "}
        {Math.round(DECAY.shareFromNewModels * 100)}% of the gap comes from being able
        to pick models that did not exist when the frozen router was built — not from
        fresher data on the models it already had.
      </figcaption>
    </figure>
  );
}
