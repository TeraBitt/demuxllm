import { ArrowRight } from "lucide-react";
import { LogoMark } from "@/components/brand";
import { Reveal } from "@/components/ui/motion";
import { Button } from "@/components/ui/primitives";

export function Cta({
  title = "Start saving this week.",
  body = "Free up to $500 of spend a month. After that you only pay a share of what we save you — so if we save you nothing, you owe nothing.",
}: {
  title?: string;
  body?: string;
}) {
  return (
    <section className="relative overflow-hidden border-t border-line">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -bottom-40 h-80 blur-3xl"
        style={{
          background:
            "radial-gradient(50% 60% at 50% 100%, var(--glow), transparent 70%)",
        }}
      />

      <Reveal className="relative mx-auto flex max-w-2xl flex-col items-center px-5 py-20 text-center sm:py-28">
        <LogoMark className="h-20 w-20" />
        <h2 className="mt-6 text-3xl font-semibold tracking-[-0.035em] text-balance sm:text-4xl">
          {title}
        </h2>
        <p className="mt-4 text-[1.0625rem] leading-relaxed text-ink-muted">
          {body}
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-2.5">
          <Button href="/docs" className="h-11 px-5 text-[0.9375rem]">
            Start free
            <ArrowRight size={16} strokeWidth={2.2} />
          </Button>
          <Button
            href="/pricing"
            variant="secondary"
            className="h-11 px-5 text-[0.9375rem]"
          >
            See pricing
          </Button>
        </div>
      </Reveal>
    </section>
  );
}
