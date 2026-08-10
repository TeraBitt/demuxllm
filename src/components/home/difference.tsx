import Link from "next/link";
import { ArrowRight, Check, X } from "lucide-react";
import { Reveal } from "@/components/ui/motion";
import { Card, Section, SectionHeading } from "@/components/ui/primitives";

const THEM = [
  "Built once, then left alone",
  "Yesterday's prices, hard-coded",
  "New models take months to appear",
  "Trust us, it works",
];

const US = [
  "Re-tested against every model, every day",
  "Today's prices, read live",
  "New models added within 24 hours",
  "Every choice shown and checked against invoices",
];

export function Difference() {
  return (
    <Section className="bg-surface">
      <SectionHeading
        eyebrow="Why us"
        title="Other routers were right once. Ours is right today."
        lede="Anyone can compare models on a Tuesday and ship the results. The hard part is that the answer changes every week — new models, new prices, quiet updates nobody announces."
      />

      <Reveal className="mt-10 grid gap-3 sm:grid-cols-2">
        <Card className="p-6">
          <h3 className="text-[0.9375rem] font-medium text-ink-muted">
            A typical router
          </h3>
          <ul className="mt-4 flex flex-col gap-3">
            {THEM.map((t) => (
              <li key={t} className="flex items-start gap-2.5">
                <X
                  size={15}
                  strokeWidth={2.2}
                  className="mt-0.5 shrink-0 text-ink-faint"
                />
                <span className="text-[0.9375rem] text-ink-muted">{t}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="border-accent/30 bg-accent/[0.05] p-6">
          <h3 className="text-[0.9375rem] font-medium text-accent">DemuxLLM</h3>
          <ul className="mt-4 flex flex-col gap-3">
            {US.map((t) => (
              <li key={t} className="flex items-start gap-2.5">
                <Check
                  size={15}
                  strokeWidth={2.4}
                  className="mt-0.5 shrink-0 text-accent"
                />
                <span className="text-[0.9375rem] text-ink">{t}</span>
              </li>
            ))}
          </ul>
        </Card>
      </Reveal>

      <Reveal className="mt-8">
        <Link
          href="/benchmark"
          className="inline-flex items-center gap-2 text-[0.9375rem] font-medium text-accent transition-opacity hover:opacity-80"
        >
          See how we test
          <ArrowRight size={15} strokeWidth={2.2} />
        </Link>
      </Reveal>
    </Section>
  );
}
