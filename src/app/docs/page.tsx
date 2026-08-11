import type { Metadata } from "next";
import { CopyButton, EndpointField } from "@/components/copy-field";
import { Quickstart } from "@/components/docs/quickstart";
import { Cta } from "@/components/shared/cta";
import { Reveal } from "@/components/ui/motion";
import { Card, PageHeader, Section, SectionHeading } from "@/components/ui/primitives";
import {
  AGENT_SNIPPETS,
  DOC_HEADERS,
  DOC_OPTIONS,
  DROP_IN_SNIPPETS,
  INSTALL,
  SDK_SNIPPETS,
  TOOL_SNIPPETS,
} from "@/lib/data";

export const metadata: Metadata = {
  title: "Docs",
  description:
    "Change one web address and you are done. Install the demuxllm package when you want to route an agent step by step.",
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

const RUN_NOTES = [
  {
    title: "A run is one user request",
    body: "Open it once at the top of your loop. Everything inside is routed on its own and totalled together, so the dashboard can show you the cost of a task rather than the cost of a call.",
  },
  {
    title: "A step says what kind of work it is",
    body: "plan, tool, read, decide, write, check. We route a tool call differently from a customer reply, and grade it differently too.",
  },
  {
    title: "Thinking is per step",
    body: "Leave it on auto and we buy reasoning only where it changes the answer. Set it to off on the steps you already know are trivial.",
  },
];

function InstallRow({ label, code }: { label: string; code: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-line bg-elevated py-2 pr-2 pl-3.5">
      <span className="w-20 shrink-0 text-[0.8125rem] text-ink-faint">{label}</span>
      <code className="min-w-0 flex-1 truncate font-mono text-[0.8125rem] text-ink">
        {code}
      </code>
      <CopyButton value={code} label={`Copy ${label} install command`} />
    </div>
  );
}

export default function DocsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Docs"
        title="Change one line. That is the whole setup."
        lede="We speak the same format as the OpenAI API, so whatever you already use keeps working — no new library, no rewrite. The package below is optional, and only earns its place once you are routing an agent."
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
            <Quickstart snippets={DROP_IN_SNIPPETS} />
          </Reveal>
        </div>
      </Section>

      <Section className="bg-surface">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)] lg:gap-12">
          <div className="lg:sticky lg:top-24 lg:self-start">
            <SectionHeading
              eyebrow="The package"
              title="demuxllm"
              lede="A thin client over the same API — the same chat.completions.create call, so nothing above needs unlearning. What it adds is named options instead of magic strings, the cost and the saving on every reply, and the run helper on the next page down."
            />
            <div className="mt-6 flex flex-col gap-2">
              {INSTALL.map((i) => (
                <InstallRow key={i.label} label={i.label} code={i.code} />
              ))}
            </div>
          </div>

          <Reveal className="min-w-0">
            <Quickstart snippets={SDK_SNIPPETS} />
          </Reveal>
        </div>
      </Section>

      <Section>
        <SectionHeading
          eyebrow="Agents"
          title="Route a loop, not just a call"
          lede="An agent makes dozens of calls to answer one question, and they are not the same kind of work. Wrap the loop in a run and every step is priced, routed and graded on its own."
        />

        <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,340px)] lg:gap-12">
          <Reveal className="min-w-0">
            <Quickstart snippets={AGENT_SNIPPETS} />
          </Reveal>

          <div className="flex flex-col gap-6">
            {RUN_NOTES.map((n) => (
              <div key={n.title}>
                <h3 className="text-[0.9375rem] font-medium">{n.title}</h3>
                <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-ink-muted">
                  {n.body}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-16 border-t border-line pt-12">
          <SectionHeading
            title="Tools work exactly as they do now"
            lede="Send the same tool schema you already send. We do not intercept the call or run anything for you — we only make sure the step goes to a model that can use them, and price the round trip afterwards."
          />

          <Reveal className="mt-8 min-w-0">
            <Quickstart snippets={TOOL_SNIPPETS} />
          </Reveal>
        </div>
      </Section>

      <Section className="bg-surface">
        <SectionHeading
          title="Optional settings"
          lede="Sensible defaults mean you can skip all of these. Add them when you want more control over a particular call."
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
          lede="Alongside the answer, every response tells you what we picked, how much it thought and what it cost — so the savings are yours to verify, not ours to claim."
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
