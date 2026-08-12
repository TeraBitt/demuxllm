import type { Metadata } from "next";
import { ModelsExplorer } from "@/components/models/explorer";
import { Cta } from "@/components/shared/cta";
import { Reveal } from "@/components/ui/motion";
import { Card, PageHeader, Section } from "@/components/ui/primitives";
import { POOL, TYPICAL_IN_TOKENS, TYPICAL_OUT_TOKENS } from "@/lib/data";

export const metadata: Metadata = {
  title: "Models",
  description:
    "Every model we can route to, what each one is good at, and what a typical answer costs.",
};

const NOTES = [
  {
    title: "You do not have to choose",
    body: "This list is what we pick from on your behalf. You can restrict it if you want, but most people never touch it.",
  },
  {
    title: "Prices are Chutes's",
    body: "We pass through whatever Chutes charges, with no markup. When a price is cut, your next request is cheaper.",
  },
  {
    title: "New models appear on their own",
    body: "We test every new release the day it lands. If it earns a place, it shows up here — nothing for you to do.",
  },
  {
    title: "Some of them can think first",
    body: "Marked “can think first”. Reasoning is billed like output, so we only buy it where we have measured that it changes the answer.",
  },
];

export default function ModelsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Models"
        title="Every model, one bill"
        lede={`${POOL.length} models from ${new Set(POOL.map((m) => m.vendor)).size} labs, every one served by Chutes on confidential hardware. Cost shown is for a typical question — roughly ${TYPICAL_IN_TOKENS} words in, ${TYPICAL_OUT_TOKENS} out.`}
      />

      <Section bordered={false} tight>
        <ModelsExplorer />
      </Section>

      <Section className="bg-surface">
        <Reveal className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {NOTES.map((n) => (
            <Card key={n.title} className="p-5">
              <h2 className="text-[0.9375rem] font-medium">{n.title}</h2>
              <p className="mt-2 text-[0.875rem] leading-relaxed text-ink-muted">
                {n.body}
              </p>
            </Card>
          ))}
        </Reveal>
      </Section>

      <Cta
        title="Let us pick for you."
        body="One key, every model on this page, and a dashboard that shows which one answered and what it saved."
      />
    </>
  );
}
