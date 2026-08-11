"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
import { Card, Pill, cx } from "@/components/ui/primitives";
import { POOL, TIER_LABEL, costPerAnswer, type PoolModel } from "@/lib/data";

const PAGE_SIZE = 5;

const FILTERS = [
  { key: "all", label: "All models" },
  { key: "open", label: "Budget" },
  { key: "mid", label: "Mid-range" },
  { key: "frontier", label: "Premium" },
] as const;

const SORTS = [
  { key: "cost", label: "Cheapest first" },
  { key: "quality", label: "Best first" },
  { key: "speed", label: "Fastest first" },
] as const;

type FilterKey = (typeof FILTERS)[number]["key"];
type SortKey = (typeof SORTS)[number]["key"];

function Sparkline({ points }: { points: readonly number[] }) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = max - min || 1;
  const d = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * 52;
      const y = 16 - ((p - min) / span) * 13;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 52 18" className="h-[18px] w-13 overflow-visible" aria-hidden>
      <path
        d={d}
        fill="none"
        stroke="var(--series-1)"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={52}
        cy={16 - ((points[points.length - 1] - min) / span) * 13}
        r={2}
        fill="var(--series-1)"
      />
    </svg>
  );
}

export function ModelsExplorer() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [sort, setSort] = useState<SortKey>("cost");
  const [page, setPage] = useState(0);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = POOL.filter((m) => {
      const matchesTier = filter === "all" || m.tier === filter;
      const matchesQuery =
        !q ||
        m.name.toLowerCase().includes(q) ||
        m.vendor.toLowerCase().includes(q) ||
        m.bestAt.toLowerCase().includes(q) ||
        (m.thinks && "reasoning thinking".includes(q));
      return matchesTier && matchesQuery;
    });

    const sorted = [...list];
    if (sort === "cost") sorted.sort((a, b) => costPerAnswer(a) - costPerAnswer(b));
    if (sort === "quality") sorted.sort((a, b) => b.quality - a.quality);
    if (sort === "speed") sorted.sort((a, b) => a.p95 - b.p95);
    return sorted;
  }, [query, filter, sort]);

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  // Clamp rather than store a page that no longer exists after filtering.
  const current = Math.min(page, pageCount - 1);
  const visible = rows.slice(current * PAGE_SIZE, current * PAGE_SIZE + PAGE_SIZE);

  function reset(fn: () => void) {
    fn();
    setPage(0);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search
            size={15}
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-faint"
          />
          <input
            type="search"
            value={query}
            onChange={(e) => reset(() => setQuery(e.target.value))}
            placeholder="Search by name, provider or what it's good at"
            aria-label="Search models"
            className="h-10 w-full rounded-lg border border-line bg-elevated pr-3 pl-9 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-line-strong"
          />
        </div>

        <label className="relative">
          <span className="sr-only">Sort models</span>
          <SlidersHorizontal
            size={14}
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-faint"
          />
          <select
            value={sort}
            onChange={(e) => reset(() => setSort(e.target.value as SortKey))}
            className="h-10 w-full appearance-none rounded-lg border border-line bg-elevated pr-8 pl-9 text-sm text-ink outline-none focus:border-line-strong sm:w-auto"
          >
            {SORTS.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => reset(() => setFilter(f.key))}
            className={cx(
              "rounded-full border px-3 py-1 text-[0.8125rem] transition-colors",
              filter === f.key
                ? "border-accent/45 bg-accent/10 text-accent"
                : "border-line text-ink-muted hover:bg-surface hover:text-ink",
            )}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-[0.8125rem] text-ink-faint">
          {rows.length} {rows.length === 1 ? "model" : "models"}
        </span>
      </div>

      {/* Rows */}
      {visible.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-[0.9375rem] text-ink-muted">
            Nothing matches “{query}”.
          </p>
          <button
            type="button"
            onClick={() => reset(() => setQuery(""))}
            className="mt-2 text-[0.875rem] text-accent hover:opacity-80"
          >
            Clear search
          </button>
        </Card>
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map((m) => (
            <ModelRow key={m.id} model={m} />
          ))}
        </ul>
      )}

      {/* Pagination */}
      {pageCount > 1 ? (
        <nav
          className="flex items-center justify-center gap-1.5 pt-2"
          aria-label="Pagination"
        >
          <button
            type="button"
            onClick={() => setPage(Math.max(0, current - 1))}
            disabled={current === 0}
            aria-label="Previous page"
            className="grid size-9 place-items-center rounded-lg border border-line text-ink-muted transition-colors hover:bg-surface hover:text-ink disabled:pointer-events-none disabled:opacity-40"
          >
            <ChevronLeft size={16} />
          </button>

          {Array.from({ length: pageCount }, (_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setPage(i)}
              aria-current={i === current ? "page" : undefined}
              className={cx(
                "size-9 rounded-lg border text-[0.875rem] tabular-nums transition-colors",
                i === current
                  ? "border-line-strong bg-elevated text-ink"
                  : "border-transparent text-ink-muted hover:bg-surface hover:text-ink",
              )}
            >
              {i + 1}
            </button>
          ))}

          <button
            type="button"
            onClick={() => setPage(Math.min(pageCount - 1, current + 1))}
            disabled={current === pageCount - 1}
            aria-label="Next page"
            className="grid size-9 place-items-center rounded-lg border border-line text-ink-muted transition-colors hover:bg-surface hover:text-ink disabled:pointer-events-none disabled:opacity-40"
          >
            <ChevronRight size={16} />
          </button>
        </nav>
      ) : null}
    </div>
  );
}

function ModelRow({ model: m }: { model: PoolModel }) {
  const cost = costPerAnswer(m);
  return (
    <li>
      <Card
        hover
        className="flex flex-col gap-3.5 p-4 sm:grid sm:grid-cols-[minmax(0,1.7fr)_repeat(3,minmax(0,1fr))] sm:items-center sm:gap-4 sm:p-5"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[0.9375rem] font-medium">{m.name}</h3>
            <Pill tone={m.tier === "open" ? "accent" : "neutral"}>
              {TIER_LABEL[m.tier]}
            </Pill>
            {m.thinks ? <Pill>Can think first</Pill> : null}
          </div>
          <p className="mt-1 text-[0.8125rem] text-ink-muted">
            {m.vendor} · {m.bestAt}
          </p>
        </div>

        {/* One compact row on phones; `sm:contents` promotes them back to
            columns of the card's own grid on wider screens. */}
        <div className="grid grid-cols-3 gap-3 border-t border-line pt-3.5 sm:contents sm:border-0 sm:pt-0">
          <Stat label="Cost per answer" value={`$${cost.toFixed(4)}`} />
          <Stat label="Typical wait" value={`${(m.p95 / 1000).toFixed(1)}s`} />
          <div className="flex items-center gap-3 sm:justify-end">
            <div>
              <div className="text-[0.75rem] text-ink-faint">Traffic</div>
              <div className="mt-0.5 text-[0.9375rem] font-medium tabular-nums">
                {m.share > 0 ? `${Math.round(m.share * 100)}%` : "New"}
              </div>
            </div>
            <span className="hidden sm:block">
              <Sparkline points={m.trend} />
            </span>
          </div>
        </div>
      </Card>
    </li>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[0.75rem] text-ink-faint">{label}</div>
      <div className="mt-0.5 text-[0.9375rem] font-medium tabular-nums">{value}</div>
    </div>
  );
}
