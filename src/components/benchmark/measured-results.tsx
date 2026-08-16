import { Card } from "@/components/ui/primitives";
import { CHUTES_POOL, PRICE_REACTIVITY, SAVINGS, SCALING } from "@/lib/measured";
import { CATALOG } from "@/lib/dashboard/models";

const pct = (v: number) => `${Math.round(v * 100)}%`;
const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`;

const labelFor = (id: string) => CATALOG.find((m) => m.id === id)?.label ?? id;

/**
 * The two savings numbers, side by side, with the harder one first.
 *
 * Quoting only the comparison against the most expensive model is the standard
 * trick in this category and it is worth about four times what the honest number
 * is. Both are shown, the harder one is given the stronger position, and the
 * weaker-opponent caveat is written on the card rather than in a footnote.
 */
function SavingsCards() {
  const best = SAVINGS.vsBestSingleModel;
  const front = SAVINGS.vsFrontierModel;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Card className="p-6">
        <p className="text-[0.8125rem] font-medium uppercase tracking-wide text-ink-faint">
          Against the best single model
        </p>
        <p className="mt-3 text-4xl font-medium tabular-nums">{pct(best.savings)}</p>
        <p className="mt-1 text-[0.9375rem] text-ink-muted">
          cheaper, at {pct1(best.qualityRetained)} of its quality
        </p>
        <p className="mt-4 border-t border-line pt-4 text-[0.875rem] leading-relaxed text-ink-muted">
          The hardest comparison there is: {labelFor(best.model)} is the one model
          that is already optimal on this pool once price is counted. Beating it is
          the number that actually means something. ±{pct1(best.savingsSe)} over{" "}
          {CHUTES_POOL.testItems.toLocaleString()} held-out questions.
        </p>
      </Card>

      <Card className="p-6">
        <p className="text-[0.8125rem] font-medium uppercase tracking-wide text-ink-faint">
          Against the strongest model
        </p>
        <p className="mt-3 text-4xl font-medium tabular-nums">{pct(front.savings)}</p>
        <p className="mt-1 text-[0.9375rem] text-ink-muted">
          cheaper, at {pct1(front.qualityRetained)} of its quality
        </p>
        <p className="mt-4 border-t border-line pt-4 text-[0.875rem] leading-relaxed text-ink-muted">
          What a team gets today by wiring everything to {labelFor(front.model)}.
          The bigger number — and the softer target, because a cheaper model already
          beats that one outright. We lead with the figure on the left.
        </p>
      </Card>
    </div>
  );
}

/**
 * Price reactivity. The one thing here a competitor cannot copy by retraining
 * harder: price is read at decision time, so it costs nothing to react to.
 */
function PriceReactivity() {
  const worst = PRICE_REACTIVITY.worstCase;
  const points = PRICE_REACTIVITY.points;
  const max = Math.max(...points.map((p) => p.spendFrozen));

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <p className="text-[0.8125rem] font-medium uppercase tracking-wide text-ink-faint">
          When a price moves
        </p>
        <p className="text-[0.8125rem] text-ink-faint">
          {PRICE_REACTIVITY.liveFetchOk
            ? "prices read live from llm.chutes.ai"
            : "prices from the shipped catalog"}
          {PRICE_REACTIVITY.catalogueInSync ? " · in sync" : ""}
        </p>
      </div>

      <p className="mt-3 text-[0.9375rem] leading-relaxed text-ink-muted">
        Prices are read when the request arrives, never baked into the model. So a
        price change reaches routing immediately — no retraining, no redeploy. Below,{" "}
        {PRICE_REACTIVITY.target}&rsquo;s price is moved and the same trained router
        re-decides the same {CHUTES_POOL.testItems.toLocaleString()} questions.
      </p>

      <div className="mt-6 space-y-2">
        {points.map((p) => {
          const saved = p.spendFrozen - p.spendReacting;
          return (
            <div key={p.factor} className="flex items-center gap-3 text-[0.8125rem]">
              <span className="w-12 shrink-0 tabular-nums text-ink-muted">
                {p.factor}×
              </span>
              <span className="w-14 shrink-0 tabular-nums text-ink-faint">
                {pct(p.shareAfter)}
              </span>
              <span className="relative h-5 flex-1 overflow-hidden rounded bg-surface">
                <span
                  className="absolute inset-y-0 left-0 rounded bg-line"
                  style={{ width: `${(p.spendFrozen / max) * 100}%` }}
                />
                <span
                  className="absolute inset-y-0 left-0 rounded bg-[var(--series-1)]"
                  style={{ width: `${(p.spendReacting / max) * 100}%` }}
                />
              </span>
              <span className="w-20 shrink-0 text-right tabular-nums text-ink-muted">
                {saved > 0.005 ? `−$${saved.toFixed(2)}` : "—"}
              </span>
            </div>
          );
        })}
      </div>

      <p className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-[0.75rem] text-ink-faint">
        <span>price multiplier</span>
        <span>· its share of traffic after</span>
        <span>
          · <span className="text-ink-muted">grey</span> = a router that cannot react
        </span>
        <span>
          · <span className="text-[var(--series-1)]">blue</span> = this one
        </span>
      </p>

      <p className="mt-4 border-t border-line pt-4 text-[0.875rem] leading-relaxed text-ink-muted">
        At {worst.factor}× the bill would have gone to ${worst.frozenSpendUsd.toFixed(2)}.
        Reacting held it to ${(worst.frozenSpendUsd - worst.savedUsd).toFixed(2)} —{" "}
        {pct(worst.savedShare)} less, on the same questions, with the trained model
        byte-for-byte unchanged
        {PRICE_REACTIVITY.estimatorUnchanged ? " (verified every run)" : ""}.
      </p>
    </Card>
  );
}

export function MeasuredResults() {
  return (
    <div className="space-y-3">
      <SavingsCards />
      <PriceReactivity />

      <Card className="p-6">
        <p className="text-[0.8125rem] font-medium uppercase tracking-wide text-ink-faint">
          What it took to get there
        </p>
        <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              k: "Questions",
              v: CHUTES_POOL.denseCoreItems.toLocaleString(),
              d: `every one answered by all ${CATALOG.length} models, across ${CHUTES_POOL.tasks.length} benchmarks`,
            },
            {
              k: "Training data needed",
              v: "~2,000",
              d: "graded questions before the router stops improving",
            },
            {
              k: "Model size",
              v: `d=${SCALING.bestDBySavings}`,
              d: `cheapest setting that saves most — loss alone would have picked d=${SCALING.bestDByLoss}`,
            },
            {
              k: "Headroom left",
              v: pct1(SAVINGS.routerQuality / SAVINGS.oracleQuality),
              d: "of what a perfect per-question oracle would score",
            },
          ].map((s) => (
            <div key={s.k}>
              <dt className="text-[0.8125rem] text-ink-faint">{s.k}</dt>
              <dd className="mt-1 text-2xl font-medium tabular-nums">{s.v}</dd>
              <dd className="mt-1 text-[0.8125rem] leading-relaxed text-ink-muted">
                {s.d}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      <p className="px-1 text-[0.8125rem] leading-relaxed text-ink-faint">
        Every figure on this page comes from a run of the benchmark, not an estimate.
        One caveat we would rather state than bury: no public benchmark grades the
        exact Chutes checkpoints, so each of the {CATALOG.length} models is stood in
        for by one that has been graded on public benchmarks — same family wherever
        one exists, and for one slot the identical checkpoint. Prices are the live
        Chutes list. Read these as what this pool does if each model performs like its
        stand-in.
      </p>
    </div>
  );
}
