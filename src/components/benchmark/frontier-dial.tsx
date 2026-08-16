"use client";

import { useState } from "react";
import { cx } from "@/components/ui/primitives";
import { CHUTES_POOL, FRONTIER_CURVE, SAVINGS } from "@/lib/measured";
import { CATALOG } from "@/lib/dashboard/models";

/*
 * The trade-off itself, drawn as a shape.
 *
 * Savings on x against quality kept on y — not either one against the dial —
 * because the reader's question is "what does going cheaper cost me?", and the
 * answer is in the curve's form: flat, then a knee. Plotting both measures
 * against lambda would have been legal (they share a unit) and would have hidden
 * the one thing worth seeing.
 *
 * Emphasis, not a two-series chart. The curve is context in muted ink; the
 * setting we actually ship is the only accent on the plot, which is what the
 * accent means everywhere else in this product — the option that was chosen.
 * Identity never rests on that colour: the point is ringed, enlarged and
 * directly labelled.
 *
 * The y-axis is truncated, and deliberately in the direction that flatters us
 * least. Quality spans 94-100%, so a 0-100% axis would draw a straight line and
 * imply the trade-off does not exist. Zooming in exaggerates the drop instead,
 * which is the error worth making.
 */

const POINTS = FRONTIER_CURVE;
const SHIPPED = POINTS.reduce((best, p) =>
  Math.abs(p.lamCost - CHUTES_POOL.lamCost) < Math.abs(best.lamCost - CHUTES_POOL.lamCost)
    ? p
    : best,
);

const W = 760;
const H = 340;
const PAD = { t: 30, r: 44, b: 58, l: 56 };
const PLOT_W = W - PAD.l - PAD.r;
const PLOT_H = H - PAD.t - PAD.b;

// Sized from the data rather than pinned, so a future run that dials further
// cannot quietly run off the edge and read as a plateau.
const xs = POINTS.map((p) => p.savings);
const ys = POINTS.map((p) => p.qualityRetained);
const X_MIN = Math.floor(Math.min(...xs) * 20) / 20;
const X_MAX = Math.ceil(Math.max(...xs) * 20) / 20;
const Y_MIN = Math.floor(Math.min(...ys) * 100) / 100 - 0.01;
const Y_MAX = Math.ceil(Math.max(...ys) * 50) / 50;

const x = (v: number) => PAD.l + ((v - X_MIN) / (X_MAX - X_MIN)) * PLOT_W;
const y = (v: number) => PAD.t + ((Y_MAX - v) / (Y_MAX - Y_MIN)) * PLOT_H;

const PATH = POINTS.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.savings)} ${y(p.qualityRetained)}`).join(
  " ",
);

const X_TICKS: number[] = [];
for (let t = Math.ceil(X_MIN * 10) / 10; t <= X_MAX + 1e-9; t += 0.1) {
  X_TICKS.push(Math.round(t * 100) / 100);
}
// Snapped to the 2% grid rather than stepped off Y_MIN, so tightening the
// domain cannot turn the axis into 95 / 97 / 99.
const Y_TICKS: number[] = [];
for (let t = Math.ceil(Y_MIN / 0.02) * 0.02; t <= Y_MAX + 1e-9; t += 0.02) {
  Y_TICKS.push(Math.round(t * 100) / 100);
}

const pct = (v: number) => `${Math.round(v * 100)}%`;
const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`;

const frontierLabel =
  CATALOG.find((mm) => mm.id === SAVINGS.vsFrontierModel.model)?.label ??
  SAVINGS.vsFrontierModel.model;

export function FrontierDial() {
  const [view, setView] = useState<"chart" | "table">("chart");
  const [hover, setHover] = useState<number | null>(null);

  const active = hover !== null ? POINTS[hover] : SHIPPED;

  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-elevated">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3.5 sm:px-5">
        <div>
          <h3 className="text-[0.9375rem] font-medium">The dial, and where we set it</h3>
          <p className="mt-0.5 text-[0.8125rem] text-ink-faint">
            What each setting saves, and what it costs in quality
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
                {["Setting", "Cheaper by", "Quality kept", "Models used"].map((h) => (
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
              {POINTS.map((p) => (
                <tr
                  key={p.lamCost}
                  className={cx(
                    "border-b border-line last:border-0",
                    p === SHIPPED && "bg-accent/[0.06]",
                  )}
                >
                  <th
                    scope="row"
                    className="px-5 py-2 text-left text-[0.875rem] font-normal text-ink-muted tabular-nums"
                  >
                    {p.lamCost}
                    {p === SHIPPED ? (
                      <span className="ml-2 text-[0.75rem] font-medium text-accent">
                        shipped
                      </span>
                    ) : null}
                  </th>
                  <td className="px-5 py-2 text-[0.875rem] tabular-nums">{pct1(p.savings)}</td>
                  <td className="px-5 py-2 text-[0.875rem] tabular-nums">
                    {pct1(p.qualityRetained)}
                  </td>
                  <td className="px-5 py-2 text-[0.875rem] text-ink-muted tabular-nums">
                    {p.modelsUsed}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-2 pt-3 sm:px-4">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="h-auto w-full touch-none"
            role="img"
            aria-label={`Quality holds close to the strongest single model while savings rise to about ${pct(
              SHIPPED.savings,
            )}, then falls away. At the setting we ship, routing is ${pct(
              SHIPPED.savings,
            )} cheaper while keeping ${pct1(SHIPPED.qualityRetained)} of that model's quality.`}
          >
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

            {X_TICKS.map((t) => (
              <text
                key={t}
                x={x(t)}
                y={H - PAD.b + 22}
                textAnchor="middle"
                className="fill-[var(--ink-faint)] text-[11px] tabular-nums"
              >
                {pct(t)}
              </text>
            ))}

            <text
              x={PAD.l + PLOT_W / 2}
              y={H - 10}
              textAnchor="middle"
              className="fill-[var(--ink-faint)] text-[11px]"
            >
              cheaper than sending everything to {frontierLabel} →
            </text>

            {/* Parity: above this line the router is not losing anything at all. */}
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={y(1)}
              y2={y(1)}
              stroke="var(--ink-faint)"
              strokeWidth={1.5}
            />
            {/* Parked top-right: the curve never enters that corner, and the
                left end of this line is where it starts. */}
            <text
              x={W - PAD.r - 6}
              y={y(1) - 12}
              textAnchor="end"
              className="fill-[var(--ink-muted)] text-[11px]"
            >
              same quality as {frontierLabel}
            </text>

            {/* Drawn statically, not animated in. A `pathLength` reveal makes the
                curve invisible until an intersection observer happens to fire —
                which is a coin toss on first paint, and the curve IS the chart. */}
            <path
              d={PATH}
              fill="none"
              stroke="var(--ink-muted)"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {POINTS.map((p, i) =>
              p === SHIPPED ? null : (
                <circle
                  key={p.lamCost}
                  cx={x(p.savings)}
                  cy={y(p.qualityRetained)}
                  r={hover === i ? 5 : 3.5}
                  fill="var(--ink-muted)"
                  stroke="var(--elevated)"
                  strokeWidth={2}
                />
              ),
            )}

            {/* The chosen setting: the only accent on the plot. */}
            <circle
              cx={x(SHIPPED.savings)}
              cy={y(SHIPPED.qualityRetained)}
              r={7}
              fill="var(--accent)"
              stroke="var(--elevated)"
              strokeWidth={2.5}
            />
            {/* Below the point, not above it: the parity rule runs six pixels
                over the marker, and a label there would sit on the line. */}
            <text
              x={x(SHIPPED.savings) - 6}
              y={y(SHIPPED.qualityRetained) + 26}
              textAnchor="end"
              className="fill-[var(--ink)] text-[12px] font-medium"
            >
              we ship here
            </text>
            <text
              x={x(SHIPPED.savings) - 6}
              y={y(SHIPPED.qualityRetained) + 42}
              textAnchor="end"
              className="fill-[var(--ink-muted)] text-[11px] tabular-nums"
            >
              {pct(SHIPPED.savings)} cheaper · {pct1(SHIPPED.qualityRetained)} of its quality
            </text>

            {/* Hit targets, sized for a finger rather than for the mark. */}
            {POINTS.map((p, i) => (
              <circle
                key={`hit-${p.lamCost}`}
                cx={x(p.savings)}
                cy={y(p.qualityRetained)}
                r={16}
                fill="transparent"
                onPointerEnter={() => setHover(i)}
                onPointerLeave={() => setHover(null)}
              />
            ))}
          </svg>
        </div>
      )}

      <div className="flex min-h-[2.75rem] flex-wrap items-center gap-x-5 gap-y-1 border-t border-line px-4 py-3 sm:px-5">
        <span className="flex items-center gap-2">
          <span aria-hidden className="size-2 rounded-full bg-accent" />
          <span className="text-[0.875rem] text-ink">
            {hover !== null && active !== SHIPPED ? `Setting ${active.lamCost}` : "Shipped setting"}
          </span>
        </span>
        <span className="text-[0.875rem] text-ink-muted tabular-nums">
          {pct1(active.savings)} cheaper
        </span>
        <span className="text-[0.875rem] text-ink-muted tabular-nums">
          {pct1(active.qualityRetained)} quality kept
        </span>
        <span className="text-[0.8125rem] text-ink-faint tabular-nums">
          {active.modelsUsed} of {CATALOG.length} models used
        </span>
      </div>

      <figcaption className="border-t border-line px-4 py-3 text-[0.8125rem] leading-relaxed text-ink-faint sm:px-5">
        Measured on {CHUTES_POOL.testItems.toLocaleString()} held-out questions. The y-axis
        starts at {pct(Y_MIN)}, not zero — quality moves within six points across the whole
        dial, so a full axis would draw a flat line and imply there is no trade-off at all.
        Zooming in overstates the cost rather than hiding it. Proxy-backed: each Chutes model
        is stood in for by one that has been graded publicly, so read this as what this pool
        does if each model performs like its stand-in. The assistant exposes the same dial as{" "}
        <span className="text-ink-muted">Strategy</span> and{" "}
        <span className="text-ink-muted">Max price</span> under Settings.
      </figcaption>
    </figure>
  );
}
