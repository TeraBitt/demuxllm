"use client";

import { useState } from "react";
import { Check, Eye, EyeOff, ShieldCheck, Trash2 } from "lucide-react";
import { cx } from "@/components/ui/primitives";
import { useKeys } from "@/lib/dashboard/keys";
import { CATALOG, TIER_LABEL, TIER_VAR, usd } from "@/lib/dashboard/models";

export function PanelHeading({
  title,
  lede,
}: {
  title: string;
  lede?: string;
}) {
  return (
    <div>
      <h2 className="text-[0.9375rem] font-medium">{title}</h2>
      {lede ? (
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-ink-muted">
          {lede}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ BYOK -- */

function KeyField({
  label,
  hint,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  const [shown, setShown] = useState(false);

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label className="text-[0.8125rem] font-medium">{label}</label>
        {value ? (
          <span className="flex items-center gap-1 text-[0.75rem] text-accent">
            <Check size={12} strokeWidth={2.8} />
            stored
          </span>
        ) : null}
      </div>
      <div className="glass glass-line edge-sunk mt-2 flex items-center gap-1.5 rounded-xl border py-1.5 pr-1.5 pl-3 transition-colors focus-within:border-accent/40">
        <input
          type={shown ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent font-mono text-[0.8125rem] text-ink outline-none placeholder:text-ink-faint"
        />
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          aria-label={shown ? "Hide key" : "Show key"}
          className="rounded-md p-1.5 text-ink-faint transition-colors hover:text-ink"
        >
          {shown ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
      <p className="mt-1.5 text-[0.75rem] leading-relaxed text-ink-faint">{hint}</p>
    </div>
  );
}

export function ByokPanel() {
  const { keys, setKey, clear, hasGemini } = useKeys();

  return (
    <div className="flex flex-col gap-5">
      <PanelHeading
        title="Bring your own key"
        lede="Keys are held in this browser's localStorage and used to call the provider directly from your machine. Nothing is sent to a DemuxLLM server — there isn't one in this demo's path."
      />

      <KeyField
        label="Gemini"
        placeholder="AIza…"
        hint="Drives real routing, search grounding and answers. Without it the dashboard runs a deterministic simulation."
        value={keys.gemini}
        onChange={(v) => setKey("gemini", v)}
      />

      <KeyField
        label="Chutes"
        placeholder="cpk_…"
        hint="Unlocks the open-weights tier in the router — DeepSeek, Qwen and Llama. Routing decisions are shown either way; only the call is simulated."
        value={keys.chutes}
        onChange={(v) => setKey("chutes", v)}
      />

      <div
        className={cx(
          "rounded-lg border p-3 text-[0.75rem] leading-relaxed",
          hasGemini
            ? "border-accent/30 bg-accent/[0.06] text-ink-muted"
            : "border-line bg-surface text-ink-faint",
        )}
      >
        {hasGemini
          ? "Live. Classification, search and answers are real Gemini calls made from this browser."
          : "Simulated. Every step below is scripted and deterministic — the same question always produces the same route."}
      </div>

      {keys.gemini || keys.chutes ? (
        <button
          type="button"
          onClick={clear}
          className="inline-flex items-center gap-1.5 self-start text-[0.8125rem] text-ink-faint transition-colors hover:text-ink"
        >
          <Trash2 size={13} />
          Forget both keys
        </button>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------- TEE -- */

/**
 * Static on purpose. A measurement that changed on every render would be
 * theatre; a fixed one reads as what it is — the shape of an attestation
 * document, so the panel can show where a real one would be checked.
 */
const ATTESTATION = {
  enclave: "gcp-confidential-h100",
  measurement: "7f3a91c04e2b8d5f6a1c93e7b204df85c6a09e13",
  signer: "demuxllm-inference-v4",
  issued: "2026-08-11T09:14:22Z",
};

export function TeePanel() {
  return (
    <div className="flex flex-col gap-5">
      <PanelHeading
        title="Confidential inference"
        lede="Routes marked private run inside a hardware enclave: the weights and your prompt are decrypted only inside it, and the host — including us — cannot read either."
      />

      <div className="glass glass-line edge-lit rounded-2xl border">
        <div className="glass-line flex items-center gap-2 border-b px-3.5 py-2.5">
          <ShieldCheck size={14} className="text-accent" strokeWidth={2.4} />
          <span className="text-[0.8125rem] font-medium">Attestation verified</span>
          <span className="ml-auto text-[0.75rem] text-ink-faint">demo document</span>
        </div>
        <dl className="glass-line divide-y">
          {Object.entries(ATTESTATION).map(([k, v]) => (
            <div key={k} className="flex items-baseline gap-4 px-3.5 py-2.5">
              <dt className="w-24 shrink-0 text-[0.75rem] text-ink-faint capitalize">
                {k}
              </dt>
              <dd className="min-w-0 flex-1 truncate font-mono text-[0.75rem] text-ink-muted">
                {v}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      <p className="text-[0.75rem] leading-relaxed text-ink-faint">
        Simulated. A real integration verifies the measurement against the
        provider&rsquo;s published value before any prompt is sent, and refuses the
        route if it does not match.
      </p>
    </div>
  );
}

/* ----------------------------------------------------------------- tools -- */

const TOOLS = [
  {
    name: "web_search",
    args: "{ query: string }",
    body: "Gemini search grounding. Called only when classification says the answer depends on information newer than training.",
    live: true,
  },
  {
    name: "model_pricing",
    args: "{ provider?: string }",
    body: "Reads the routing catalog — list price, context window, whether the model can think or call tools.",
    live: true,
  },
  {
    name: "run_cost",
    args: "{ runId: string }",
    body: "Totals one run: per-step cost against the frontier baseline, and the reasoning budget bought at each step.",
    live: true,
  },
] as const;

export function ToolsPanel() {
  return (
    <div className="flex flex-col gap-5">
      <PanelHeading
        title="Tools"
        lede="Defined as LangChain tools and bound to the graph. A step carrying tools is only ever routed to a model that can call them."
      />

      <div className="flex flex-col gap-2">
        {TOOLS.map((t) => (
          <div key={t.name} className="glass glass-hover glass-line rounded-2xl border p-3.5">
            <div className="flex items-center gap-2">
              <code className="font-mono text-[0.8125rem] text-accent">{t.name}</code>
              <code className="truncate font-mono text-[0.75rem] text-ink-faint">
                {t.args}
              </code>
            </div>
            <p className="mt-1.5 text-[0.75rem] leading-relaxed text-ink-muted">
              {t.body}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- usage -- */

export function UsagePanel({
  runs,
  cost,
  baseline,
}: {
  runs: number;
  cost: number;
  baseline: number;
}) {
  const saved = baseline > 0 ? 1 - cost / baseline : 0;

  return (
    <div className="flex flex-col gap-5">
      <PanelHeading
        title="This session"
        lede="Totalled per run rather than per call, because a run is what a user actually asked for."
      />

      <dl className="grid grid-cols-3 gap-3">
        {[
          { label: "Runs", value: String(runs), tone: "ink" },
          { label: "Spent", value: usd(cost, 4), tone: "accent" },
          { label: "Frontier-only", value: usd(baseline, 4), tone: "muted" },
        ].map((s) => (
          <div key={s.label} className="glass glass-line edge-lit rounded-2xl border p-3">
            <dt className="text-[0.6875rem] text-ink-faint">{s.label}</dt>
            <dd
              className={cx(
                "mt-1 text-[1.0625rem] font-semibold tabular-nums",
                s.tone === "accent" && "text-accent",
                s.tone === "muted" && "text-ink-muted",
              )}
            >
              {s.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="glass glass-line edge-lit rounded-2xl border p-3.5">
        <div className="flex items-baseline justify-between">
          <span className="text-[0.8125rem] font-medium">Cheaper by</span>
          <span className="text-[0.9375rem] font-semibold text-accent tabular-nums">
            {Math.round(saved * 100)}%
          </span>
        </div>
        <div aria-hidden className="mt-2.5 h-1 overflow-hidden rounded-full bg-line">
          <span
            className="block h-full rounded-full bg-accent transition-[width] duration-500"
            style={{ width: `${Math.max(0, Math.min(1, saved)) * 100}%` }}
          />
        </div>
      </div>

      <div>
        <h3 className="text-[0.8125rem] font-medium">Routing pool</h3>
        <ul className="mt-2.5 flex flex-col gap-1.5">
          {CATALOG.map((m) => (
            <li key={m.id} className="flex items-center gap-2.5">
              <span
                aria-hidden
                className="size-2 shrink-0 rounded-full"
                style={{ background: TIER_VAR[m.tier] }}
              />
              <span className="min-w-0 flex-1 truncate text-[0.8125rem] text-ink-muted">
                {m.label}
              </span>
              <span className="shrink-0 text-[0.6875rem] text-ink-faint">
                {TIER_LABEL[m.tier]}
              </span>
              <span className="w-20 shrink-0 text-right text-[0.6875rem] text-ink-faint tabular-nums">
                ${m.inPer1M}/${m.outPer1M}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[0.6875rem] leading-relaxed text-ink-faint">
          List prices per 1M tokens, recorded by hand and certain to drift. They
          make the arithmetic the right shape, not invoiceable.
        </p>
      </div>
    </div>
  );
}
