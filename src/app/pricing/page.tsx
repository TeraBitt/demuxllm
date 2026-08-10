import type { Metadata } from "next";
import { Check } from "lucide-react";
import { FaqList } from "@/components/shared/faq-list";
import { Reveal, RevealItem } from "@/components/ui/motion";
import {
  Button,
  Card,
  PageHeader,
  Pill,
  Section,
  SectionHeading,
  cx,
} from "@/components/ui/primitives";
import { PLANS, PRICING_FAQS } from "@/lib/data";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "You pay a share of what we save you. If we save you nothing, you pay nothing.",
};

const EXAMPLE = [
  { label: "What you spend today", value: "$10,000", muted: true },
  { label: "What you spend with us", value: "$6,000" },
  { label: "So we saved you", value: "$4,000", accent: true },
  { label: "Our 20% share", value: "$800", muted: true },
  { label: "You keep", value: "$3,200", accent: true },
];

export default function PricingPage() {
  return (
    <>
      <PageHeader
        eyebrow="Pricing"
        title="If we don't save you money, you don't pay us"
        lede="No seats, no subscription, no minimum. We take a fifth of what we save you, and you can check our arithmetic against your provider invoices."
      />

      <Section bordered={false} tight>
        <Reveal group className="grid gap-4 lg:grid-cols-3">
          {PLANS.map((p) => (
            <RevealItem key={p.name}>
              <Card
                className={cx(
                  "flex h-full flex-col p-6",
                  p.featured && "border-accent/40 bg-accent/[0.04]",
                )}
              >
                <div className="flex items-center gap-2">
                  <h2 className="text-[0.9375rem] font-medium">{p.name}</h2>
                  {p.featured ? <Pill tone="accent">Most popular</Pill> : null}
                </div>

                <div className="mt-5 flex items-baseline gap-2">
                  <span
                    className={cx(
                      "text-4xl font-semibold tracking-[-0.04em]",
                      p.featured && "text-accent",
                    )}
                  >
                    {p.price}
                  </span>
                  <span className="text-[0.875rem] text-ink-muted">
                    {p.cadence}
                  </span>
                </div>

                <p className="mt-3 text-[0.9375rem] leading-relaxed text-ink-muted">
                  {p.tagline}
                </p>

                <ul className="mt-6 flex flex-1 flex-col gap-2.5 border-t border-line pt-6">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5">
                      <Check
                        size={15}
                        strokeWidth={2.4}
                        className="mt-0.5 shrink-0 text-accent"
                      />
                      <span className="text-[0.875rem] text-ink-muted">{f}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  href="/docs"
                  variant={p.featured ? "primary" : "secondary"}
                  className="mt-7 h-11 w-full text-[0.9375rem]"
                >
                  {p.cta}
                </Button>
              </Card>
            </RevealItem>
          ))}
        </Reveal>
      </Section>

      <Section className="bg-surface">
        <div className="grid items-start gap-10 lg:grid-cols-2 lg:gap-16">
          <SectionHeading
            title="What a bill actually looks like"
            lede="Say you spend ten thousand dollars a month on one strong model today, and the router cuts that by 40%."
          />

          <Reveal>
            <Card className="overflow-hidden">
              <ul>
                {EXAMPLE.map((row, i) => (
                  <li
                    key={row.label}
                    className={cx(
                      "flex items-center justify-between px-5 py-3.5",
                      i < EXAMPLE.length - 1 && "border-b border-line",
                      row.muted && "bg-surface",
                    )}
                  >
                    <span className="text-[0.9375rem] text-ink-muted">
                      {row.label}
                    </span>
                    <span
                      className={cx(
                        "text-[1.0625rem] font-medium tabular-nums",
                        row.accent && "text-accent",
                      )}
                    >
                      {row.value}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
            <p className="mt-4 text-[0.875rem] text-ink-faint">
              You still pay the model providers directly, at their list price. We
              never mark that up.
            </p>
          </Reveal>
        </div>
      </Section>

      <Section>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)] lg:gap-16">
          <SectionHeading
            eyebrow="Pricing questions"
            title="The fine print, in plain words."
            className="lg:sticky lg:top-24 lg:self-start"
          />
          <FaqList items={PRICING_FAQS} />
        </div>
      </Section>
    </>
  );
}
