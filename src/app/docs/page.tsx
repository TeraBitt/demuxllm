import type { Metadata } from "next";
import { EndpointField } from "@/components/copy-field";
import { Quickstart } from "@/components/docs/quickstart";
import { Cta } from "@/components/shared/cta";
import { Reveal } from "@/components/ui/motion";
import { Card, PageHeader, Section, SectionHeading } from "@/components/ui/primitives";
import { DOC_HEADERS, DOC_OPTIONS } from "@/lib/data";

export const metadata: Metadata = {
  title: "Docs",
  description:
    "Change one web address and you are done. Everything else is optional.",
};

const SETUP = [
  {
    n: "01",
    title: "Get a key",
    body: "Sign up and copy your key. Free until you route $500 a month.",
  },
  {
    n: "02",
    title: "Change the address",
    body: "Point your existing client at our endpoint instead of your provider's.",
  },
  {
    n: "03",
    title: "Ask for “auto”",
    body: "Use auto as the model name and we choose. Name a specific model and we send it straight there.",
  },
];

export default function DocsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Docs"
        title="Change one line. That is the whole setup."
        lede="We speak the same format as the OpenAI API, so whatever you already use keeps working — no new library, no rewrite."
      >
        <EndpointField value="https://api.demuxllm.com/v1" />
      </PageHeader>

      <Section bordered={false} tight>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)] lg:gap-12">
          <div className="flex flex-col gap-7">
            {SETUP.map((s) => (
              <div key={s.n}>
                <span className="text-[0.8125rem] font-medium text-accent tabular-nums">
                  {s.n}
                </span>
                <h2 className="mt-2 text-[0.9375rem] font-medium">{s.title}</h2>
                <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-ink-muted">
                  {s.body}
                </p>
              </div>
            ))}
          </div>

          <Reveal className="min-w-0">
            <Quickstart />
          </Reveal>
        </div>
      </Section>

      <Section className="bg-surface">
        <SectionHeading
          title="Optional settings"
          lede="Sensible defaults mean you can skip all of these. Add them when you want more control over a particular request."
        />

        <Reveal className="mt-8 grid gap-3 sm:grid-cols-2">
          {DOC_OPTIONS.map((o) => (
            <Card key={o.name} className="p-5">
              <div className="flex flex-wrap items-center gap-2">
                <code className="rounded-md border border-line bg-surface px-2 py-0.5 font-mono text-[0.8125rem] text-ink">
                  {o.name}
                </code>
                <span className="text-[0.75rem] text-ink-faint">{o.type}</span>
              </div>
              <p className="mt-3 text-[0.9375rem] leading-relaxed text-ink-muted">
                {o.body}
              </p>
              <p className="mt-3 font-mono text-[0.8125rem] text-accent">
                {o.name}: {o.example}
              </p>
            </Card>
          ))}
        </Reveal>
      </Section>

      <Section>
        <SectionHeading
          title="What comes back"
          lede="Alongside the answer, every response tells you what we picked and what it cost — so the savings are yours to verify, not ours to claim."
        />

        <Reveal className="mt-8 overflow-hidden rounded-xl border border-line">
          <ul>
            {DOC_HEADERS.map((h, i) => (
              <li
                key={h.name}
                className={`flex flex-col gap-1 bg-elevated px-5 py-4 sm:flex-row sm:items-center sm:gap-6 ${
                  i < DOC_HEADERS.length - 1 ? "border-b border-line" : ""
                }`}
              >
                <code className="font-mono text-[0.8125rem] text-ink sm:w-56 sm:shrink-0">
                  {h.name}
                </code>
                <span className="text-[0.9375rem] text-ink-muted">{h.body}</span>
              </li>
            ))}
          </ul>
        </Reveal>
      </Section>

      <Cta
        title="Try it on one endpoint."
        body="Point a single non-critical route at us, compare the bill for a week, then decide. Nothing to uninstall if you change your mind."
      />
    </>
  );
}
