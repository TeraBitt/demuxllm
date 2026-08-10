import { Difference } from "@/components/home/difference";
import { Hero } from "@/components/home/hero";
import { Savings } from "@/components/home/savings";
import { Steps } from "@/components/home/steps";
import { Cta } from "@/components/shared/cta";
import { FaqList } from "@/components/shared/faq-list";
import { Section, SectionHeading } from "@/components/ui/primitives";
import { HOME_FAQS } from "@/lib/data";

export default function HomePage() {
  return (
    <>
      <Hero />
      <Steps />
      <Difference />
      <Savings />

      <Section className="bg-surface">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)] lg:gap-16">
          <SectionHeading
            eyebrow="Questions"
            title="The things people ask first."
            className="lg:sticky lg:top-24 lg:self-start"
          />
          <FaqList items={HOME_FAQS} />
        </div>
      </Section>

      <Cta />
    </>
  );
}
