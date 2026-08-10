import { ArrowRight } from "lucide-react";
import { EndpointField } from "@/components/copy-field";
import { RouterVisual } from "@/components/router-visual";
import { Reveal, RevealItem } from "@/components/ui/motion";
import { Button } from "@/components/ui/primitives";
import { HERO_STATS, PROVIDERS } from "@/lib/data";

export function Hero() {
  return (
    <div className="relative overflow-hidden">
      <div
        aria-hidden
        className="bg-grid mask-fade-b pointer-events-none absolute inset-0"
      />

      <div className="relative mx-auto max-w-6xl px-5 pt-14 pb-12 sm:px-8 sm:pt-20 sm:pb-16">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,480px)] lg:gap-14">
          <Reveal group className="flex flex-col items-start gap-6">
            <RevealItem>
              <span className="inline-flex items-center gap-2 rounded-full border border-line bg-elevated px-3 py-1 text-[0.8125rem] text-ink-muted">
                <span className="size-1.5 rounded-full bg-accent animate-[pulse-dot_2.4s_ease-in-out_infinite]" />
                Re-tested against every model, every day
              </span>
            </RevealItem>

            <RevealItem>
              <h1 className="max-w-[13ch] text-[2.75rem] leading-[1.02] font-semibold tracking-[-0.045em] text-balance sm:text-6xl">
                One key for
                <span className="text-gradient"> every AI model</span>
              </h1>
            </RevealItem>

            <RevealItem>
              <p className="max-w-lg text-[1.0625rem] leading-relaxed text-ink-muted">
                Most questions do not need the most expensive model. We send each
                one to the cheapest model that still gets it right — and show you
                exactly what that saved.
              </p>
            </RevealItem>

            <RevealItem className="flex flex-wrap items-center gap-2.5">
              <Button href="/docs" className="h-11 px-5 text-[0.9375rem]">
                Start free
                <ArrowRight size={16} strokeWidth={2.2} />
              </Button>
              <Button
                href="/models"
                variant="secondary"
                className="h-11 px-5 text-[0.9375rem]"
              >
                Browse models
              </Button>
            </RevealItem>

            <RevealItem>
              <EndpointField value="https://api.demuxllm.com/v1" />
            </RevealItem>
          </Reveal>

          <Reveal delay={0.12}>
            <RouterVisual />
          </Reveal>
        </div>

        <Reveal
          group
          className="mt-14 grid grid-cols-2 gap-x-6 gap-y-8 sm:mt-20 lg:grid-cols-4"
        >
          {HERO_STATS.map((s) => (
            <RevealItem key={s.label}>
              <div className="text-3xl font-semibold tracking-[-0.03em] tabular-nums sm:text-4xl">
                {s.value}
              </div>
              <div className="mt-1.5 text-sm text-ink-muted">{s.label}</div>
            </RevealItem>
          ))}
        </Reveal>
      </div>

      <div className="border-t border-line py-7">
        <p className="mb-5 text-center text-[0.8125rem] text-ink-faint">
          Every major provider, one bill
        </p>
        <div className="mask-fade-x relative flex overflow-hidden">
          <div className="animate-marquee flex shrink-0 items-center gap-12 pr-12">
            {[...PROVIDERS, ...PROVIDERS].map((p, i) => (
              <span
                key={`${p}-${i}`}
                className="text-base font-medium whitespace-nowrap text-ink-faint"
              >
                {p}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
