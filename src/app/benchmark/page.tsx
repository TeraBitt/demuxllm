import type { Metadata } from "next";
import { DecayChart } from "@/components/benchmark/decay-chart";
import { FrontierDial } from "@/components/benchmark/frontier-dial";
import { MeasuredResults } from "@/components/benchmark/measured-results";
import { Cta } from "@/components/shared/cta";
import { Reveal, RevealItem } from "@/components/ui/motion";
import { Card, PageHeader, Section, SectionHeading } from "@/components/ui/primitives";
import { GRADING, HOW_WE_TEST, STALE_REASONS } from "@/lib/data";

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
          eyebrow="Results"
          title="What routing this pool is actually worth"
          lede="Measured on held-out questions, against the two baselines that matter — including the one that is hard to beat."
        />
        <Reveal className="mt-8">
          <MeasuredResults />
        </Reveal>
        <Reveal className="mt-3">
          <FrontierDial />
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

      <Section className="bg-surface">
        <SectionHeading
          eyebrow="What we grade"
          title="A leaderboard score does not tell you how to route an agent"
          lede="Public benchmarks measure finished prose. An agent spends most of its calls on something else entirely — so we grade four things, and three of them are not on any leaderboard."
        />

        <Reveal group className="mt-8 grid gap-3 sm:grid-cols-2">
          {GRADING.map((g) => (
            <RevealItem key={g.title}>
              <Card hover className="h-full p-5">
                <h3 className="text-[0.9375rem] font-medium">{g.title}</h3>
                <p className="mt-2 text-[0.9375rem] leading-relaxed text-ink-muted">
                  {g.body}
                </p>
              </Card>
            </RevealItem>
          ))}
        </Reveal>

        <Reveal className="mt-3 rounded-xl border border-accent/30 bg-accent/[0.05] p-5">
          <p className="text-[0.9375rem] leading-relaxed text-ink-muted">
            <span className="font-medium text-ink">
              This is the part that compounds.
            </span>{" "}
            Every day of testing, and every request you route, adds another
            observation about which model is worth its price for which kind of work.
            A competitor can copy the idea in a week and still be a year of evidence
            behind.
          </p>
        </Reveal>
      </Section>

      <Cta
        title="Let someone else keep score."
        body="We do the testing, the pricing and the picking. You send questions and get answers."
      />
    </>
  );
}
