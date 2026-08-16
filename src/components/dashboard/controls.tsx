"use client";

import { type ReactNode, useEffect, useState } from "react";
import {
  Brain,
  Check,
  Eye,
  EyeOff,
  KeyRound,
  MessageSquare,
  Route,
  Trash2,
  Wrench,
  X,
} from "lucide-react";
import { cx } from "@/components/ui/primitives";
import { useKeys } from "@/lib/dashboard/keys";
import { CATALOG, FAMILY_LABEL, type Family, formatCtx } from "@/lib/dashboard/models";
import {
  COST_CAPS,
  PRESETS,
  STYLES,
  THINKING_MODES,
  blendedPrice,
  usePrefs,
} from "@/lib/dashboard/prefs";
import { TOOLS } from "@/lib/dashboard/tools";

/**
 * One dialog, five tabs, and nothing inert.
 *
 * The reference designs for this pattern carry seven settings sections, most of
 * them decoration. Everything here is wired: a provider toggle removes models
 * from the pool, a cost cap removes them by price, the floor raises the bar the
 * scorer set, the thinking mode decides whether a reasoning trace gets bought at
 * all, and a tool switched off is never declared to the model. A control that
 * could not change the next answer was left out rather than drawn — an inert
 * switch is worse than a missing one, because a missing one does not lie about
 * what the product does.
 */

export type Tab = "provider" | "routing" | "reasoning" | "tools" | "workspace";

const TABS: { id: Tab; label: string; icon: typeof Route }[] = [
  { id: "provider", label: "Provider", icon: KeyRound },
  { id: "routing", label: "Routing", icon: Route },
  { id: "reasoning", label: "Answers", icon: Brain },
  { id: "tools", label: "Tools", icon: Wrench },
  { id: "workspace", label: "Workspace", icon: MessageSquare },
];

/* ------------------------------------------------------------------ shell -- */

function Overlay({
  onClose,
  children,
  tab,
  onTab,
}: {
  onClose: () => void;
  children: ReactNode;
  tab: Tab;
  onTab: (t: Tab) => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-ink/25 backdrop-blur-sm dark:bg-black/60"
      />
      {/*
       * Near-opaque rather than glass. A modal's legibility cannot depend on
       * `backdrop-filter` landing: where it is unsupported, disabled, or simply
       * slow to composite, `glass-strong` is a 7% white wash and the page shows
       * straight through the settings. 96% of the elevated surface keeps the
       * material language and reads as solid everywhere.
       */}
      <div
        role="dialog"
        aria-modal
        aria-label="Settings"
        style={{ background: "color-mix(in oklab, var(--elevated) 96%, transparent)" }}
        className="glass-line edge-lit relative flex max-h-[86vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl border shadow-2xl shadow-black/20 backdrop-blur-xl dark:shadow-black/60"
      >
        <div className="glass-line flex shrink-0 items-center gap-3 border-b px-5 py-3.5">
          <h2 className="text-[1.0625rem] font-semibold tracking-[-0.02em]">Settings</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="glass-line ml-auto flex size-8 items-center justify-center rounded-full border transition-colors hover:bg-ink/[0.04] dark:hover:bg-white/[0.06]"
          >
            <X size={15} />
          </button>
        </div>

        <div className="glass-line flex shrink-0 gap-1 overflow-x-auto border-b px-3 py-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onTab(t.id)}
              className={cx(
                "flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-[0.8125rem] font-medium transition-all",
                tab === t.id
                  ? "glass-strong edge-lit text-ink"
                  : "text-ink-faint hover:text-ink-muted",
              )}
            >
              <t.icon size={13} strokeWidth={2.2} />
              {t.label}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="text-[0.6875rem] tracking-[0.08em] text-ink-faint uppercase">{label}</div>
      <div className="mt-2.5">{children}</div>
      {hint ? <p className="mt-2 text-[0.75rem] leading-relaxed text-ink-faint">{hint}</p> : null}
    </div>
  );
}

/** Segmented control. One row, one choice, current state always visible. */
function Segmented<T extends string | number>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="edge-sunk flex gap-0.5 rounded-xl bg-ink/[0.04] p-1 dark:bg-black/25">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          onClick={() => onChange(o.value)}
          className={cx(
            "flex-1 rounded-lg px-3 py-1.5 text-[0.8125rem] font-medium transition-all",
            value === o.value
              ? "glass-strong text-ink shadow-[inset_0_1px_0_0_var(--glass-highlight),0_1px_3px_0_rgb(0_0_0/0.12)]"
              : "text-ink-faint hover:text-ink-muted",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Switch({ on }: { on: boolean }) {
  return (
    <span
      aria-hidden
      className={cx(
        "flex h-4 w-7 shrink-0 items-center rounded-full p-0.5 transition-colors",
        on ? "bg-accent" : "bg-ink/[0.15] dark:bg-white/[0.18]",
      )}
    >
      <span
        className={cx(
          "size-3 rounded-full bg-canvas transition-transform",
          on && "translate-x-3",
        )}
      />
    </span>
  );
}

function Toggle({
  on,
  onClick,
  title,
  meta,
  detail,
}: {
  on: boolean;
  onClick: () => void;
  title: string;
  meta?: string;
  detail?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className="glass glass-line flex w-full items-start gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors hover:bg-ink/[0.03] dark:hover:bg-white/[0.04]"
    >
      <span className="mt-0.5">
        <Switch on={on} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className="text-[0.8125rem] font-medium">{title}</span>
          {meta ? <span className="text-[0.6875rem] text-ink-faint">{meta}</span> : null}
        </span>
        {detail ? (
          <span className="mt-0.5 block text-[0.75rem] leading-relaxed text-ink-faint">
            {detail}
          </span>
        ) : null}
      </span>
    </button>
  );
}

function Slider({
  value,
  min,
  max,
  step,
  onChange,
  format,
  label,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format: (v: number) => string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3.5">
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label}
        className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-ink/[0.12] accent-[var(--accent)] dark:bg-white/[0.14]"
      />
      <span className="w-14 shrink-0 text-right font-mono text-[0.8125rem] tabular-nums">
        {format(value)}
      </span>
    </div>
  );
}

const INPUT =
  "glass glass-line edge-sunk w-full rounded-xl border px-3 py-2 text-[0.8125rem] outline-none placeholder:text-ink-faint focus:border-accent/40";

/* --------------------------------------------------------------- provider -- */

function KeyRow({
  label,
  meta,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  meta: string;
  value: string;
  placeholder: string;
  onChange: (v: string) => void;
}) {
  const [shown, setShown] = useState(false);
  const connected = Boolean(value);

  return (
    <div className="glass glass-line rounded-2xl border p-3.5">
      <div className="flex items-center gap-3">
        <span
          className={cx(
            "flex size-8 shrink-0 items-center justify-center rounded-full text-[0.8125rem] font-semibold",
            connected
              ? "bg-accent/15 text-accent"
              : "bg-ink/[0.06] text-ink-faint dark:bg-white/[0.07]",
          )}
        >
          {label[0]}
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[0.875rem] font-medium">{label}</span>
            <span className="text-[0.6875rem] tracking-[0.06em] text-ink-faint uppercase">
              {meta}
            </span>
          </div>
          <p className="mt-0.5 font-mono text-[0.6875rem] text-ink-faint">
            {connected ? `${value.slice(0, 6)}••••••${value.slice(-4)}` : "not connected"}
          </p>
        </div>
        {connected ? (
          <span className="ml-auto flex shrink-0 items-center gap-1 text-[0.75rem] text-accent">
            <Check size={12} strokeWidth={3} />
            live
          </span>
        ) : null}
      </div>

      <div className="glass glass-line edge-sunk mt-3 flex items-center gap-1.5 rounded-xl border py-1.5 pr-1.5 pl-3 focus-within:border-accent/40">
        <input
          type={shown ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent font-mono text-[0.8125rem] outline-none placeholder:text-ink-faint"
        />
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          aria-label={shown ? "Hide key" : "Show key"}
          className="rounded-md p-1.5 text-ink-faint transition-colors hover:text-ink"
        >
          {shown ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
        {connected ? (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label={`Remove ${label} key`}
            className="rounded-md p-1.5 text-ink-faint transition-colors hover:text-ink"
          >
            <Trash2 size={14} />
          </button>
        ) : null}
      </div>
    </div>
  );
}

function ProviderTab() {
  const { keys, setKey } = useKeys();
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[0.8125rem] leading-relaxed text-ink-muted">
        Every model in the pool is served by Chutes, so one key reaches all{" "}
        {CATALOG.length} of them. It is held in this browser and used to call Chutes
        directly from your machine — it is never sent anywhere else.
      </p>
      <KeyRow
        label="Chutes"
        meta="routing · answers"
        placeholder="cpk_…"
        value={keys.chutes}
        onChange={(v) => setKey("chutes", v)}
      />
      <p className="text-[0.75rem] text-ink-faint">
        No key yet?{" "}
        <a
          href="https://chutes.ai"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline decoration-accent/35 underline-offset-2"
        >
          chutes.ai
        </a>{" "}
        issues one in a minute.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- routing -- */

const FAMILIES: Family[] = [...new Set(CATALOG.map((m) => m.family))];

function RoutingTab() {
  const { prefs, set, toggleFamily, reset, pool } = usePrefs();
  const pinned = prefs.pinnedModel;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 sm:grid-cols-2">
        <Field
          label="Strategy"
          hint={PRESETS.find((p) => p.value === prefs.preset)?.hint}
        >
          <Segmented
            options={PRESETS.map((p) => ({ value: p.value, label: p.label.split(" ")[0] }))}
            value={prefs.preset}
            onChange={(v) => set("preset", v)}
          />
        </Field>

        <Field
          label="Max price per 1M tokens"
          hint="Blended, output-weighted. Anything dearer leaves the pool."
        >
          <Segmented
            options={COST_CAPS.map((c) => ({ value: c.value, label: c.label }))}
            value={prefs.maxCostPer1M}
            onChange={(v) => set("maxCostPer1M", v)}
          />
        </Field>

        <Field
          label="Quality floor"
          hint="Raises the bar the router sets. It never lowers it."
        >
          <Slider
            label="Quality floor"
            value={prefs.qualityFloor}
            min={0}
            max={0.95}
            step={0.05}
            onChange={(v) => set("qualityFloor", v)}
            format={(v) => v.toFixed(2)}
          />
        </Field>

        <Field label="Model families">
          <div className="flex max-h-44 flex-col gap-1.5 overflow-y-auto pr-1">
            {FAMILIES.map((f) => (
              <Toggle
                key={f}
                on={!prefs.disallowed.includes(f)}
                onClick={() => toggleFamily(f)}
                title={FAMILY_LABEL[f]}
                meta={(() => {
                  const n = CATALOG.filter((m) => m.family === f).length;
                  return `${n} model${n === 1 ? "" : "s"}`;
                })()}
              />
            ))}
          </div>
        </Field>
      </div>

      <Field
        label="Pin a model"
        hint={
          pinned
            ? "Routing still scores and classifies every request — it just does not get to choose. Unpin to let it."
            : "Leave on Auto to let the router pick. Pinning is for a side-by-side comparison."
        }
      >
        <select
          value={pinned}
          onChange={(e) => set("pinnedModel", e.target.value)}
          className={cx(INPUT, "cursor-pointer appearance-none")}
        >
          <option value="">Auto — let the router pick</option>
          {[...CATALOG]
            .sort((a, b) => blendedPrice(a) - blendedPrice(b))
            .map((m) => (
              <option key={m.id} value={m.id}>
                {m.label} — ${m.inPer1M}/${m.outPer1M} per 1M · {formatCtx(m.ctx)}
              </option>
            ))}
        </select>
      </Field>

      {/* The consequence of everything above, in one panel. */}
      <div className="glass glass-line edge-lit rounded-2xl border p-4">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-[0.8125rem] font-medium">
            {pinned ? "Routing bypassed" : `${pool.length} of ${CATALOG.length} models eligible`}
          </span>
          <button
            type="button"
            onClick={reset}
            className="text-[0.75rem] text-ink-faint transition-colors hover:text-ink"
          >
            Reset all
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {[...CATALOG]
            .sort((a, b) => blendedPrice(a) - blendedPrice(b))
            .map((m) => {
              const inPool = !pinned && pool.some((p) => p.id === m.id);
              const isPinned = pinned === m.id;
              return (
                <span
                  key={m.id}
                  className={cx(
                    "glass-line rounded-full border px-2.5 py-1 text-[0.75rem]",
                    isPinned
                      ? "border-accent/40 bg-accent/10 text-accent"
                      : inPool
                        ? "text-ink-muted"
                        : "text-ink-faint line-through opacity-50",
                  )}
                >
                  {m.label}
                </span>
              );
            })}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- reasoning -- */

function ReasoningTab() {
  const { prefs, set } = usePrefs();
  const mode = THINKING_MODES.find((m) => m.value === prefs.thinking);

  return (
    <div className="flex flex-col gap-6">
      <Field label="Reasoning" hint={mode?.hint}>
        <Segmented
          options={THINKING_MODES.map((m) => ({ value: m.value, label: m.label }))}
          value={prefs.thinking}
          onChange={(v) => set("thinking", v)}
        />
      </Field>

      {prefs.thinking === "auto" ? (
        <Field
          label="Think above this bar"
          hint={`A request the router grades at ${prefs.thinkingThreshold} or above buys a reasoning trace; anything easier does not. The bar is the same number shown under every answer.`}
        >
          <Slider
            label="Thinking threshold"
            value={prefs.thinkingThreshold}
            min={40}
            max={95}
            step={5}
            onChange={(v) => set("thinkingThreshold", v)}
            format={(v) => `${v}/100`}
          />
        </Field>
      ) : null}

      <Field
        label="Answer style"
        hint={STYLES.find((s) => s.value === prefs.style)?.hint}
      >
        <Segmented
          options={STYLES.map((s) => ({ value: s.value, label: s.label }))}
          value={prefs.style}
          onChange={(v) => set("style", v)}
        />
      </Field>

      <div className="grid gap-6 sm:grid-cols-2">
        <Field
          label="Temperature"
          hint="Lower is steadier and more repeatable; higher wanders more."
        >
          <Slider
            label="Temperature"
            value={prefs.temperature}
            min={0}
            max={1.2}
            step={0.1}
            onChange={(v) => set("temperature", v)}
            format={(v) => v.toFixed(1)}
          />
        </Field>

        <Field
          label="Conversation memory"
          hint={
            prefs.historyTurns === 0
              ? "Every message is judged and answered on its own, with no memory of the last."
              : `The last ${prefs.historyTurns} exchanges are re-sent as context. More memory costs more input tokens.`
          }
        >
          <Slider
            label="Conversation memory"
            value={prefs.historyTurns}
            min={0}
            max={20}
            step={1}
            onChange={(v) => set("historyTurns", v)}
            format={(v) => (v === 0 ? "off" : `${v}`)}
          />
        </Field>
      </div>

      <Field
        label="Custom instructions"
        hint="Added to the system prompt on every request, whichever model answers."
      >
        <textarea
          value={prefs.systemPrompt}
          onChange={(e) => set("systemPrompt", e.target.value)}
          rows={4}
          placeholder="e.g. “Always give me TypeScript, never Python. Assume I know the basics. If you are unsure, say so rather than guessing.”"
          className={cx(INPUT, "resize-y leading-relaxed")}
        />
      </Field>
    </div>
  );
}

/* ------------------------------------------------------------------ tools -- */

function ToolsTab() {
  const { prefs, set, toggleTool } = usePrefs();
  const active = prefs.toolsEnabled ? prefs.enabledTools.length : 0;

  return (
    <div className="flex flex-col gap-6">
      <Field
        label="Tool calling"
        hint="Tools run in this browser — nothing is sent to a third party. Only models that can hold a schema are offered them; the rest answer from what they know."
      >
        <Toggle
          on={prefs.toolsEnabled}
          onClick={() => set("toolsEnabled", !prefs.toolsEnabled)}
          title={prefs.toolsEnabled ? `On — ${active} available` : "Off"}
          detail="When on, the model can call any tool you leave enabled below."
        />
      </Field>

      <div className={cx("flex flex-col gap-1.5", !prefs.toolsEnabled && "pointer-events-none opacity-40")}>
        {TOOLS.map((t) => (
          <Toggle
            key={t.name}
            on={prefs.enabledTools.includes(t.name)}
            onClick={() => toggleTool(t.name)}
            title={t.name}
            detail={t.description.split(".")[0]}
          />
        ))}
      </div>

      <Field
        label="Tool rounds per answer"
        hint="How many times the model may call tools before it has to answer with what it has. A ceiling, not a target."
      >
        <Slider
          label="Tool rounds"
          value={prefs.maxToolRounds}
          min={1}
          max={8}
          step={1}
          onChange={(v) => set("maxToolRounds", v)}
          format={(v) => `${v}`}
        />
      </Field>
    </div>
  );
}

/* -------------------------------------------------------------- workspace -- */

function WorkspaceTab() {
  const { prefs, set } = usePrefs();

  return (
    <div className="flex flex-col gap-5">
      <p className="text-[0.8125rem] leading-relaxed text-ink-muted">
        Prompt analytics reports how much of the spend is company work. It has nothing
        but this description to judge against — leave it empty and every request is
        filed as unclear, which is the honest answer.
      </p>

      <div className="flex flex-col gap-2.5">
        <input
          value={prefs.orgName}
          onChange={(e) => set("orgName", e.target.value)}
          placeholder="Organisation name"
          className={INPUT}
        />
        <textarea
          value={prefs.orgContext}
          onChange={(e) => set("orgContext", e.target.value)}
          rows={5}
          placeholder="What does this team work on? e.g. “We build and run a payments API for Nepali merchants — backend in Go, dashboard in Next.js, plus support and finance ops.”"
          className={cx(INPUT, "resize-y leading-relaxed")}
        />
      </div>

      <div className="glass glass-line rounded-xl border p-3.5 text-[0.75rem] leading-relaxed text-ink-faint">
        The classification is stored; the request is not. A request flagged as carrying
        credentials or customer data is recorded as a paraphrase, so an analytics view
        never becomes a place to read other people&rsquo;s prompts.
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- export -- */

export function Settings({ onClose, initialTab = "provider" }: { onClose: () => void; initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);

  return (
    <Overlay onClose={onClose} tab={tab} onTab={setTab}>
      {tab === "provider" ? <ProviderTab /> : null}
      {tab === "routing" ? <RoutingTab /> : null}
      {tab === "reasoning" ? <ReasoningTab /> : null}
      {tab === "tools" ? <ToolsTab /> : null}
      {tab === "workspace" ? <WorkspaceTab /> : null}
    </Overlay>
  );
}
