"use client";

import { useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronRight,
  Clock,
  Coins,
  Layers,
  Loader2,
  Terminal,
} from "lucide-react";
import { cx } from "@/components/ui/primitives";
import { TIER_VAR, usd } from "@/lib/dashboard/models";
import { TOOL_BY_NAME, type ToolResult } from "@/lib/dashboard/tools";

/**
 * One tool call, rendered as what it did rather than as JSON.
 *
 * The collapsed row is the claim — "searched the model pool, 4 matched, 12ms" —
 * and opening it shows the arguments and the result behind that claim. A demo
 * that only ever showed the spinner would be asking to be taken on trust, which
 * is the opposite of the argument this product makes.
 */

const ICONS: Record<string, typeof Layers> = {
  search_models: Layers,
  estimate_cost: Coins,
  usage_stats: Coins,
  run_javascript: Terminal,
  current_time: Clock,
};

function prettyArgs(raw: string) {
  if (!raw.trim()) return "";
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

/* ---------------------------------------------------------- result views -- */

type ModelRow = {
  id: string;
  label: string;
  tier: "open" | "mid" | "frontier";
  inPer1M: number;
  outPer1M: number;
  goodAt: string;
};

function ModelsResult({ data }: { data: { matched: number; total: number; models: ModelRow[] } }) {
  return (
    <ul className="flex flex-col gap-1.5">
      {data.models.map((m) => (
        <li key={m.id} className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="size-1.5 shrink-0 rounded-full"
            style={{ background: TIER_VAR[m.tier] }}
          />
          <span className="text-[0.8125rem] font-medium">{m.label}</span>
          <span className="truncate text-[0.75rem] text-ink-faint">{m.goodAt}</span>
          <span className="ml-auto shrink-0 font-mono text-[0.75rem] text-ink-muted tabular-nums">
            ${m.inPer1M}/${m.outPer1M}
          </span>
        </li>
      ))}
    </ul>
  );
}

function CostResult({
  data,
}: {
  data: { rows: { label: string; tier: string; each: number; total: number }[]; savedPct: number };
}) {
  const max = Math.max(...data.rows.map((r) => r.total), 1e-12);
  return (
    <ul className="flex flex-col gap-2">
      {data.rows.map((r) => (
        <li key={r.label} className="flex items-center gap-3">
          <span className="w-40 shrink-0 truncate text-[0.75rem] text-ink-muted">{r.label}</span>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink/[0.06] dark:bg-white/[0.08]">
            <span
              className="block h-full rounded-full bg-accent/70"
              style={{ width: `${Math.max(2, (r.total / max) * 100)}%` }}
            />
          </span>
          <span className="w-20 shrink-0 text-right font-mono text-[0.75rem] tabular-nums">
            {usd(r.total, 5)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function UsageResult({
  data,
}: {
  data: {
    runs: number;
    cost: number;
    saved: number;
    groupBy: string;
    rows: { label: string; runs: number; cost: number }[];
  };
}) {
  if (!data.runs) {
    return <p className="text-[0.8125rem] text-ink-faint">No runs recorded on this device yet.</p>;
  }
  const max = Math.max(...data.rows.map((r) => r.cost), 1e-12);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-5 text-[0.75rem]">
        <span>
          <span className="text-ink-faint">spent </span>
          <span className="font-mono tabular-nums">{usd(data.cost, 4)}</span>
        </span>
        <span>
          <span className="text-ink-faint">saved </span>
          <span className="font-mono text-accent tabular-nums">{usd(data.saved, 4)}</span>
        </span>
        <span className="text-ink-faint tabular-nums">{data.runs} runs</span>
      </div>
      <ul className="flex flex-col gap-1.5">
        {data.rows.map((r) => (
          <li key={r.label} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate text-[0.75rem] text-ink-muted">{r.label}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink/[0.06] dark:bg-white/[0.08]">
              <span
                className="block h-full rounded-full bg-accent/70"
                style={{ width: `${Math.max(2, (r.cost / max) * 100)}%` }}
              />
            </span>
            <span className="w-16 shrink-0 text-right font-mono text-[0.75rem] tabular-nums">
              {usd(r.cost, 4)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function JsResult({
  data,
}: {
  data: { code: string; logs: string[]; value: string | null; error: string | null };
}) {
  return (
    <div className="flex flex-col gap-2.5">
      <pre className="glass-line max-h-40 overflow-auto rounded-lg border p-2.5 font-mono text-[0.75rem] leading-relaxed text-ink-muted">
        <code>{data.code}</code>
      </pre>
      {data.logs.length ? (
        <pre className="max-h-32 overflow-auto font-mono text-[0.75rem] leading-relaxed text-ink-muted">
          <code>{data.logs.join("\n")}</code>
        </pre>
      ) : null}
      {data.value != null ? (
        <pre className="max-h-32 overflow-auto font-mono text-[0.75rem] leading-relaxed text-accent">
          <code>{data.value}</code>
        </pre>
      ) : null}
      {data.error ? (
        <p className="font-mono text-[0.75rem] text-[var(--series-2)]">{data.error}</p>
      ) : null}
    </div>
  );
}

function ResultBody({ name, result }: { name: string; result: ToolResult }) {
  const data = result.data as never;
  if (result.data) {
    if (name === "search_models") return <ModelsResult data={data} />;
    if (name === "estimate_cost") return <CostResult data={data} />;
    if (name === "usage_stats") return <UsageResult data={data} />;
    if (name === "run_javascript") return <JsResult data={data} />;
  }
  return (
    <p className="text-[0.8125rem] leading-relaxed whitespace-pre-wrap text-ink-muted">
      {result.summary}
    </p>
  );
}

/* ------------------------------------------------------------------ card -- */

export function ToolCall({
  name,
  args,
  result,
  ms,
}: {
  name: string;
  args: string;
  result?: ToolResult;
  ms?: number;
}) {
  const [open, setOpen] = useState(false);
  const spec = TOOL_BY_NAME.get(name);
  const Icon = ICONS[name] ?? Terminal;
  const running = !result;
  const failed = result && !result.ok;

  const headline = running
    ? (spec?.running ?? "Running a tool")
    : (spec?.label ?? name);

  return (
    <div className="glass glass-line edge-lit overflow-hidden rounded-2xl border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left transition-colors hover:bg-ink/[0.02] dark:hover:bg-white/[0.03]"
      >
        <span
          className={cx(
            "flex size-5 shrink-0 items-center justify-center rounded-md",
            failed ? "text-[var(--series-2)]" : "text-accent",
          )}
        >
          {running ? (
            <Loader2 size={13} className="animate-spin" strokeWidth={2.4} />
          ) : failed ? (
            <AlertCircle size={13} strokeWidth={2.4} />
          ) : (
            <Icon size={13} strokeWidth={2.2} />
          )}
        </span>

        <span className="text-[0.8125rem] font-medium">{headline}</span>

        {!running && ms != null ? (
          <span className="text-[0.75rem] text-ink-faint tabular-nums">{ms}ms</span>
        ) : null}

        {!running ? (
          <span
            className={cx(
              "flex items-center gap-1 text-[0.6875rem]",
              failed ? "text-[var(--series-2)]" : "text-ink-faint",
            )}
          >
            {failed ? "failed" : <Check size={11} strokeWidth={3} />}
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
        <div className="glass-line flex flex-col gap-3 border-t px-3.5 py-3">
          {args.trim() && args.trim() !== "{}" ? (
            <div>
              <div className="text-[0.6875rem] tracking-[0.06em] text-ink-faint uppercase">
                Called with
              </div>
              <pre className="mt-1.5 max-h-32 overflow-auto font-mono text-[0.75rem] leading-relaxed text-ink-muted">
                <code>{prettyArgs(args)}</code>
              </pre>
            </div>
          ) : null}

          {result ? (
            <div>
              <div className="text-[0.6875rem] tracking-[0.06em] text-ink-faint uppercase">
                Returned
              </div>
              <div className="mt-1.5">
                <ResultBody name={name} result={result} />
              </div>
            </div>
          ) : (
            <p className="text-[0.8125rem] text-ink-faint">Still running…</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
