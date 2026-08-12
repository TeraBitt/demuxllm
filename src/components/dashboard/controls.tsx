"use client";

import { type ReactNode, useEffect, useState } from "react";
import { Check, Eye, EyeOff, Trash2, X } from "lucide-react";
import { cx } from "@/components/ui/primitives";
import { useKeys } from "@/lib/dashboard/keys";
import { CATALOG, FAMILY_LABEL, type Family } from "@/lib/dashboard/models";
import { COST_CAPS, PRESETS, blendedPrice, usePrefs } from "@/lib/dashboard/prefs";

/**
 * Two overlays, both of which change behaviour.
 *
 * The reference designs for this pattern carry seven settings sections, most of
 * them inert. Everything here is wired: a provider toggle removes models from
 * the pool, a cost cap removes them by price, the floor raises the bar the
 * scorer set. A control that could not change the next answer was left out
 * rather than drawn — an inert switch is worse than a missing one, because a
 * missing one does not lie about what the product does.
 */

/* ------------------------------------------------------------------ shell -- */

function Overlay({
  title,
  onClose,
  children,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
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
      <div
        role="dialog"
        aria-modal
        aria-label={title}
        className={cx(
          "glass-strong glass-line edge-lit relative flex max-h-[85vh] w-full flex-col overflow-hidden rounded-3xl border shadow-2xl shadow-black/20 dark:shadow-black/60",
          wide ? "max-w-3xl" : "max-w-2xl",
        )}
      >
        <div className="glass-line flex shrink-0 items-center border-b px-5 py-4">
          <h2 className="text-[1.0625rem] font-semibold tracking-[-0.02em]">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="glass-line ml-auto flex size-8 items-center justify-center rounded-full border transition-colors hover:bg-ink/[0.04] dark:hover:bg-white/[0.06]"
          >
            <X size={15} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-[0.6875rem] tracking-[0.08em] text-ink-faint uppercase">
        {label}
      </div>
      <div className="mt-2.5">{children}</div>
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

/* --------------------------------------------------------- routing control -- */

/** Derived from the pool, so a model added to the catalog needs no edit here. */
const FAMILIES: Family[] = [...new Set(CATALOG.map((m) => m.family))];

export function RoutingControl({ onClose }: { onClose: () => void }) {
  const { prefs, set, toggleFamily, reset, pool } = usePrefs();

  return (
    <Overlay title="Routing control" onClose={onClose} wide>
      <div className="grid gap-6 sm:grid-cols-2">
        <Field label="Strategy">
          <Segmented
            options={PRESETS.map((p) => ({ value: p.value, label: p.label.split(" ")[0] }))}
            value={prefs.preset}
            onChange={(v) => set("preset", v)}
          />
          <p className="mt-2 text-[0.75rem] leading-relaxed text-ink-faint">
            {PRESETS.find((p) => p.value === prefs.preset)?.hint}
          </p>
        </Field>

        <Field label="Max price per 1M tokens">
          <Segmented
            options={COST_CAPS.map((c) => ({ value: c.value, label: c.label }))}
            value={prefs.maxCostPer1M}
            onChange={(v) => set("maxCostPer1M", v)}
          />
          <p className="mt-2 text-[0.75rem] leading-relaxed text-ink-faint">
            Blended, output-weighted. Anything dearer leaves the pool.
          </p>
        </Field>

        <Field label="Quality floor">
          <div className="flex items-center gap-3.5">
            <input
              type="range"
              min={0}
              max={0.95}
              step={0.05}
              value={prefs.qualityFloor}
              onChange={(e) => set("qualityFloor", Number(e.target.value))}
              aria-label="Quality floor"
              className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-ink/[0.12] accent-[var(--accent)] dark:bg-white/[0.14]"
            />
            <span className="w-10 shrink-0 text-right font-mono text-[0.8125rem] tabular-nums">
              {prefs.qualityFloor.toFixed(2)}
            </span>
          </div>
          <p className="mt-2 text-[0.75rem] leading-relaxed text-ink-faint">
            Raises the bar the router sets. It never lowers it.
          </p>
        </Field>

        <Field label="Model families">
          <div className="flex max-h-52 flex-col gap-1.5 overflow-y-auto">
            {FAMILIES.map((f) => {
              const on = !prefs.disallowed.includes(f);
              const count = CATALOG.filter((m) => m.family === f).length;
              return (
                <button
                  key={f}
                  type="button"
                  onClick={() => toggleFamily(f)}
                  aria-pressed={on}
                  className="glass glass-line flex items-center gap-3 rounded-xl border px-3 py-2 text-left transition-colors hover:bg-ink/[0.03] dark:hover:bg-white/[0.04]"
                >
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
                  <span className="text-[0.8125rem]">{FAMILY_LABEL[f]}</span>
                  <span className="ml-auto text-[0.75rem] text-ink-faint tabular-nums">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </Field>
      </div>

      {/* The consequence of the four controls above, in one line. */}
      <div className="glass glass-line edge-lit mt-6 rounded-2xl border p-4">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-[0.8125rem] font-medium">
            {pool.length} of {CATALOG.length} models eligible
          </span>
          <button
            type="button"
            onClick={reset}
            className="text-[0.75rem] text-ink-faint transition-colors hover:text-ink"
          >
            Reset
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {[...CATALOG]
            .sort((a, b) => blendedPrice(a) - blendedPrice(b))
            .map((m) => {
              const inPool = pool.some((p) => p.id === m.id);
              return (
                <span
                  key={m.id}
                  className={cx(
                    "glass-line rounded-full border px-2.5 py-1 text-[0.75rem]",
                    inPool ? "text-ink-muted" : "text-ink-faint line-through opacity-50",
                  )}
                >
                  {m.label}
                </span>
              );
            })}
        </div>
      </div>
    </Overlay>
  );
}

/* ---------------------------------------------------------------- settings -- */

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
            connected ? "bg-accent/15 text-accent" : "bg-ink/[0.06] text-ink-faint dark:bg-white/[0.07]",
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

export function Settings({ onClose }: { onClose: () => void }) {
  const { keys, setKey } = useKeys();
  const { prefs, set } = usePrefs();

  return (
    <Overlay title="Settings" onClose={onClose}>
      <div className="flex flex-col gap-5">
        <div>
          <h3 className="text-[0.9375rem] font-medium">Provider</h3>
          <p className="mt-1 text-[0.8125rem] leading-relaxed text-ink-muted">
            Every model in the pool is served by Chutes, so one key reaches all
            {" "}
            {CATALOG.length} of them. It is held in this browser and used to call
            Chutes directly from your machine.
          </p>
        </div>

        <KeyRow
          label="Chutes"
          meta="routing · answers"
          placeholder="cpk_…"
          value={keys.chutes}
          onChange={(v) => setKey("chutes", v)}
        />

        <div>
          <h3 className="text-[0.9375rem] font-medium">Workspace</h3>
          <p className="mt-1 text-[0.8125rem] leading-relaxed text-ink-muted">
            Prompt analytics reports how much of the spend is company work. It
            has nothing but this description to judge against — leave it empty
            and every request is filed as unclear, which is the honest answer.
          </p>
        </div>

        <div className="flex flex-col gap-2.5">
          <input
            value={prefs.orgName}
            onChange={(e) => set("orgName", e.target.value)}
            placeholder="Organisation name"
            className="glass glass-line edge-sunk rounded-xl border px-3 py-2 text-[0.8125rem] outline-none placeholder:text-ink-faint focus-within:border-accent/40"
          />
          <textarea
            value={prefs.orgContext}
            onChange={(e) => set("orgContext", e.target.value)}
            rows={4}
            placeholder="What does this team work on? e.g. “We build and run a payments API for Nepali merchants — backend in Go, dashboard in Next.js, plus support and finance ops.”"
            className="glass glass-line edge-sunk resize-y rounded-xl border px-3 py-2 text-[0.8125rem] leading-relaxed outline-none placeholder:text-ink-faint focus-within:border-accent/40"
          />
        </div>

        <div className="glass glass-line rounded-xl border p-3.5 text-[0.75rem] leading-relaxed text-ink-faint">
          The classification is stored; the request is not. A request flagged as
          carrying credentials or customer data is recorded as a paraphrase, so
          an analytics view never becomes a place to read other people&rsquo;s
          prompts.
        </div>
      </div>
    </Overlay>
  );
}
