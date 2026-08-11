import { Reveal, RevealItem } from "@/components/ui/motion";
import { Card, Pill, Section, SectionHeading } from "@/components/ui/primitives";
import {
  AGENT_RUN,
  AGENT_TASK,
  THINKING_MODES,
  agentTotals,
  type AgentStep,
  type PoolModel,
} from "@/lib/data";

const TIER_COLOR: Record<PoolModel["tier"], string> = {
  frontier: "var(--tier-3)",
  mid: "var(--tier-2)",
  open: "var(--tier-1)",
};

const THINKING_LABEL: Record<AgentStep["thinking"], string> = {
  off: "none",
  short: "short",
  deep: "deep",
};

const usd = (n: number, places = 4) => `$${n.toFixed(places)}`;

/** Widest bar in the table, so every row is comparable to every other row. */
const WIDEST = Math.max(...AGENT_RUN.map((s) => s.baseline));

function Row({ step }: { step: AgentStep }) {
  return (
    <li className="relative overflow-hidden border-b border-line last:border-b-0">
      {/* What one frontier model would have charged for this step… */}
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 bg-ink/[0.035] dark:bg-white/[0.03]"
        style={{ width: `${(step.baseline / WIDEST) * 100}%` }}
      />
      {/* …and what it actually cost. */}
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 bg-accent/[0.09]"
        style={{ width: `${(step.cost / WIDEST) * 100}%` }}
      />

      <div className="relative grid gap-2.5 px-4 py-3.5 sm:grid-cols-[1.75rem_minmax(0,1fr)_8.5rem_4.5rem_6.5rem] sm:items-center sm:gap-4 sm:px-5">
        <span className="text-[0.8125rem] font-medium text-accent tabular-nums">
          {step.n}
        </span>

        <div className="min-w-0">
          <p className="text-[0.9375rem] font-medium">{step.label}</p>
          <p className="mt-0.5 text-[0.8125rem] text-ink-faint">{step.detail}</p>
        </div>

        <span className="flex items-center gap-2">
          <span
            aria-hidden
            className="size-2 shrink-0 rounded-full"
            style={{ background: TIER_COLOR[step.tier] }}
          />
          <span className="text-[0.875rem] text-ink-muted">{step.model}</span>
        </span>

        <span
          className={
            step.thinking === "off"
              ? "text-[0.8125rem] text-ink-faint"
              : "text-[0.8125rem] text-ink-muted"
          }
        >
          <span className="text-ink-faint sm:hidden">Thinking: </span>
          {THINKING_LABEL[step.thinking]}
        </span>

        <span className="flex items-baseline gap-2 tabular-nums sm:flex-col sm:items-end sm:gap-0">
          <span className="text-[0.875rem] font-medium">{usd(step.cost)}</span>
          <span className="text-[0.75rem] text-ink-faint">
            {step.cost === step.baseline ? "worth it" : `was ${usd(step.baseline)}`}
          </span>
        </span>
      </div>
    </li>
  );
}

export function Agentic() {
  const { cost, baseline, saved, ratio } = agentTotals();

  return (
    <Section>
      <SectionHeading
        eyebrow="Agents"
        title="One request is no longer one call."
        lede="An agent turns a single question into a loop — plan, call a tool, read something, decide, write, check. Sending all of that to one expensive model is the most common way to overspend today, and the easiest to fix."
      />

      <Reveal className="mt-10 overflow-hidden rounded-2xl border border-line bg-elevated">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-surface px-4 py-3.5 sm:px-5">
          <span className="text-[0.8125rem] text-ink-faint">Someone asks</span>
          <span className="text-[0.9375rem] font-medium">{AGENT_TASK}</span>
          <Pill tone="accent" className="ml-auto">
            {AGENT_RUN.length} calls
          </Pill>
        </div>

        <div className="hidden grid-cols-[1.75rem_minmax(0,1fr)_8.5rem_4.5rem_6.5rem] gap-4 border-b border-line px-5 py-2.5 text-[0.75rem] tracking-[0.06em] text-ink-faint uppercase sm:grid">
          <span>#</span>
          <span>Step</span>
          <span>Routed to</span>
          <span>Thinking</span>
          <span className="text-right">Cost</span>
        </div>

        <ul>
          {AGENT_RUN.map((s) => (
            <Row key={s.n} step={s} />
          ))}
        </ul>

        <div className="flex flex-col gap-5 border-t border-line bg-surface px-4 py-5 sm:flex-row sm:items-center sm:gap-8 sm:px-5">
          <p className="text-[0.9375rem] leading-relaxed text-ink-muted sm:max-w-xs">
            Six calls.{" "}
            <span className="text-ink">One of them needed the expensive model.</span>{" "}
            The other five were work a small model does identically.
          </p>

          <dl className="ml-auto grid grid-cols-3 gap-6 sm:gap-8">
            <div>
              <dt className="text-[0.75rem] text-ink-faint">This run</dt>
              <dd className="mt-1 text-xl font-semibold text-accent tabular-nums">
                {usd(cost, 3)}
              </dd>
            </div>
            <div>
              <dt className="text-[0.75rem] text-ink-faint">One frontier model</dt>
              <dd className="mt-1 text-xl font-semibold text-ink-muted tabular-nums">
                {usd(baseline, 3)}
              </dd>
            </div>
            <div>
              <dt className="text-[0.75rem] text-ink-faint">Cheaper by</dt>
              <dd className="mt-1 text-xl font-semibold tabular-nums">
                {ratio.toFixed(1)}×
              </dd>
            </div>
          </dl>
        </div>
      </Reveal>

      <Reveal className="mt-3 rounded-xl border border-line bg-elevated p-5 text-[0.8125rem] leading-relaxed text-ink-faint">
        The bar behind each row is what that step cost, against what one frontier
        model would have charged for it. An illustration with real list prices, not a
        measured result — your own runs are totalled on the dashboard from the first
        day. {Math.round(saved * 100)}% is what this shape of task tends to give
        back; a chat-only workload gives back less.
      </Reveal>

      <div className="mt-16">
        <SectionHeading
          title="Thinking is the other half of the bill."
          lede="Reasoning models spend tokens working things out before they answer, billed at output rates and invisible to you. We buy that budget per call, the same way we pick the model."
        />

        <Reveal group className="mt-8 grid gap-3 sm:grid-cols-3">
          {THINKING_MODES.map((t) => (
            <RevealItem key={t.key}>
              <Card className="flex h-full flex-col p-5">
                <div className="flex items-baseline justify-between">
                  <h3 className="text-[0.9375rem] font-medium">{t.label}</h3>
                  <span className="text-[0.875rem] font-medium text-accent tabular-nums">
                    {Math.round(t.share * 100)}%
                  </span>
                </div>
                <div
                  aria-hidden
                  className="mt-3 h-1 overflow-hidden rounded-full bg-line"
                >
                  <span
                    className="block h-full rounded-full bg-accent"
                    style={{ width: `${t.share * 100}%` }}
                  />
                </div>
                <p className="mt-3.5 text-[0.9375rem] leading-relaxed text-ink-muted">
                  {t.body}
                </p>
              </Card>
            </RevealItem>
          ))}
        </Reveal>

        <Reveal className="mt-3 text-[0.8125rem] text-ink-faint">
          Share of calls in a typical agent workload. You can cap the budget
          yourself, or turn thinking off entirely for a route.
        </Reveal>
      </div>
    </Section>
  );
}
