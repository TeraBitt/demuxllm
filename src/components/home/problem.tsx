import { Reveal, RevealItem } from "@/components/ui/motion";
import { Card, Section, SectionHeading } from "@/components/ui/primitives";
import { PROBLEM, WHY_NOW } from "@/lib/data";

export function Problem() {
  return (
    <Section className="bg-surface">
      <SectionHeading
        eyebrow="The problem"
        title="Nobody meant to overspend on this."
        lede="Every team building on AI made the same three reasonable decisions, in the same order, and ended up with a bill that has very little to do with the value being produced."
      />

      <Reveal group className="mt-10 grid gap-3 sm:grid-cols-2">
        {PROBLEM.map((p) => (
          <RevealItem key={p.title}>
            <Card hover className="h-full p-6">
              <h3 className="text-[1.0625rem] font-medium tracking-[-0.015em]">
                {p.title}
              </h3>
              <p className="mt-2.5 text-[0.9375rem] leading-relaxed text-ink-muted">
                {p.body}
              </p>
            </Card>
          </RevealItem>
        ))}
      </Reveal>

      <Reveal group className="mt-12 border-t border-line pt-10">
        <RevealItem>
          <h3 className="text-[0.8125rem] font-medium tracking-[0.08em] text-ink-faint uppercase">
            And it only got true recently
          </h3>
        </RevealItem>
        <div className="mt-6 grid gap-8 sm:grid-cols-3 sm:gap-6">
          {WHY_NOW.map((w) => (
            <RevealItem key={w.title}>
              <div className="text-3xl font-semibold tracking-[-0.03em] text-accent tabular-nums">
                {w.stat}
              </div>
              <h4 className="mt-2 text-[0.9375rem] font-medium">{w.title}</h4>
              <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-ink-muted">
                {w.body}
              </p>
            </RevealItem>
          ))}
        </div>
      </Reveal>
    </Section>
  );
}
