import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Reveal, RevealItem } from "@/components/ui/motion";
import { Card, Pill, Section, SectionHeading } from "@/components/ui/primitives";
import { ROUTE_AXES, STEPS } from "@/lib/data";

export function Steps() {
  return (
    <Section>
      <SectionHeading
        eyebrow="How it works"
        title="Three steps. You only do the first one."
      />

      <Reveal group className="mt-12 grid gap-8 sm:grid-cols-3 sm:gap-6">
        {STEPS.map((s) => (
          <RevealItem key={s.n} className="relative">
            <span className="text-[0.8125rem] font-medium text-accent tabular-nums">
              {s.n}
            </span>
            <h3 className="mt-3 text-lg font-medium tracking-[-0.02em]">
              {s.title}
            </h3>
            <p className="mt-2 text-[0.9375rem] leading-relaxed text-ink-muted">
              {s.body}
            </p>
          </RevealItem>
        ))}
      </Reveal>

      <div className="mt-16 border-t border-line pt-12">
        <SectionHeading
          title="What we decide, on every single call"
          lede="Most routers answer the first question and stop. The other two are where the money is now."
        />

        <Reveal group className="mt-8 grid gap-3 lg:grid-cols-3">
          {ROUTE_AXES.map((a) => (
            <RevealItem key={a.n}>
              <Card hover className="flex h-full flex-col p-6">
                <span className="text-[0.8125rem] font-medium text-accent tabular-nums">
                  {a.n}
                </span>
                <h3 className="mt-3 text-[1.0625rem] font-medium tracking-[-0.015em]">
                  {a.title}
                </h3>
                <p className="mt-2.5 text-[0.9375rem] leading-relaxed text-ink-muted">
                  {a.body}
                </p>
                <div className="mt-5 pt-4 border-t border-line">
                  <Pill>{a.detail}</Pill>
                </div>
              </Card>
            </RevealItem>
          ))}
        </Reveal>
      </div>

      <Reveal className="mt-12">
        <Link
          href="/docs"
          className="inline-flex items-center gap-2 text-[0.9375rem] font-medium text-accent transition-opacity hover:opacity-80"
        >
          See what the code looks like
          <ArrowRight size={15} strokeWidth={2.2} />
        </Link>
      </Reveal>
    </Section>
  );
}
