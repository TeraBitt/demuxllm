import type { Metadata } from "next";
import { DecayChart } from "@/components/benchmark/decay-chart";
import { Cta } from "@/components/shared/cta";
import { Reveal, RevealItem } from "@/components/ui/motion";
import { Card, PageHeader, Section, SectionHeading } from "@/components/ui/primitives";
import { HOW_WE_TEST, STALE_REASONS } from "@/lib/data";

export const metadata: Metadata = {
  title: "Why us",
  description:
    "Picking the right model only works if you know what each model is good at today. Here is how we keep that up to date.",
};

export default function BenchmarkPage() {
  return (
    <>
      <PageHeader
        eyebrow="Why us"
        title="Knowing which model is best is a job, not a fact"
        lede="Anyone can compare models once and ship the results. The catch is that the answer changes every few weeks — so we re-run the comparison every day."
      />

      <Section bordered={false} tight>
        <SectionHeading
          title="Why a router goes out of date"
          lede="Four things move underneath it, all on their own schedule."
        />

        <Reveal group className="mt-8 grid gap-3 sm:grid-cols-2">
          {STALE_REASONS.map((r) => (
            <RevealItem key={r.title}>
              <Card hover className="h-full p-5">
                <h3 className="text-[0.9375rem] font-medium">{r.title}</h3>
                <p className="mt-2 text-[0.9375rem] leading-relaxed text-ink-muted">
                  {r.body}
                </p>
              </Card>
            </RevealItem>
          ))}
        </Reveal>
      </Section>

      <Section className="bg-surface">
        <SectionHeading
          title="What that costs you"
          lede="A router that was accurate in January is guessing by summer. Left long enough, it can end up doing worse than if you had never routed at all."
        />
        <Reveal className="mt-8">
          <DecayChart />
        </Reveal>
      </Section>

      <Section>
        <SectionHeading
          eyebrow="How we test"
          title="Every model, every day, on questions it has never seen"
        />

        <Reveal group className="mt-10 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {HOW_WE_TEST.map((s) => (
            <RevealItem key={s.n} className="flex flex-col bg-elevated p-5">
              <span className="text-[0.8125rem] font-medium text-accent tabular-nums">
                {s.n}
              </span>
              <h3 className="mt-3 text-[0.9375rem] font-medium">{s.title}</h3>
              <p className="mt-2 text-[0.875rem] leading-relaxed text-ink-muted">
                {s.body}
              </p>
            </RevealItem>
          ))}
        </Reveal>

        <Reveal className="mt-3 grid gap-3 sm:grid-cols-2">
          <Card className="border-accent/30 bg-accent/[0.05] p-5">
            <h3 className="text-[0.9375rem] font-medium text-accent">
              We pay for the testing, not you
            </h3>
            <p className="mt-2 text-[0.9375rem] leading-relaxed text-ink-muted">
              Asking every model thousands of questions a day costs real money.
              That bill is ours. You get the conclusions.
            </p>
          </Card>
          <Card className="p-5">
            <h3 className="text-[0.9375rem] font-medium">
              And we publish the results
            </h3>
            <p className="mt-2 text-[0.9375rem] leading-relaxed text-ink-muted">
              The scores are open. If we ever claim a model is better than it is,
              anyone can check — including the company that made it.
            </p>
          </Card>
        </Reveal>
      </Section>

      <Cta
        title="Let someone else keep score."
        body="We do the testing, the pricing and the picking. You send questions and get answers."
      />
    </>
  );
}
