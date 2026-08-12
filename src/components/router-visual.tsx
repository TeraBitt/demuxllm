"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence } from "motion/react";
import { Check } from "lucide-react";
import { m } from "@/components/ui/motion";
import { cx } from "@/components/ui/primitives";

type Candidate = { name: string; fit: number; cost: string };

type Scene = {
  prompt: string;
  verdict: string;
  candidates: Candidate[];
};

/**
 * Four questions, four different winners. Same pool every time, and every model
 * in it is one Chutes serves — costs are that model's published price for a
 * request of roughly this shape, so the gap on screen is the real gap.
 */
const SCENES: Scene[] = [
  {
    prompt: "Summarise this email thread in three bullets.",
    verdict: "75× cheaper",
    candidates: [
      { name: "Mistral Nemo", fit: 0.92, cost: "$0.0001" },
      { name: "Qwen3 32B", fit: 0.87, cost: "$0.0002" },
      { name: "Qwen3.6 27B", fit: 0.74, cost: "$0.0009" },
      { name: "Kimi K3", fit: 0.41, cost: "$0.0075" },
    ],
  },
  {
    prompt: "Prove this series converges, then bound the error.",
    verdict: "12× cheaper",
    candidates: [
      { name: "Qwen3 235B Thinking", fit: 0.93, cost: "$0.0019" },
      { name: "Kimi K3", fit: 0.91, cost: "$0.0234" },
      { name: "GLM 5.2", fit: 0.84, cost: "$0.0063" },
      { name: "Mistral Nemo", fit: 0.19, cost: "$0.0002" },
    ],
  },
  {
    prompt: "Write a Python function that parses this CSV.",
    verdict: "9× cheaper",
    candidates: [
      { name: "DeepSeek V3.2", fit: 0.9, cost: "$0.0009" },
      { name: "Qwen3.5 397B", fit: 0.88, cost: "$0.0017" },
      { name: "GLM 5.2", fit: 0.83, cost: "$0.0025" },
      { name: "Qwen3 32B", fit: 0.61, cost: "$0.0002" },
    ],
  },
  {
    prompt: "Traduis ce contrat et signale les clauses inhabituelles.",
    verdict: "2.6× cheaper",
    candidates: [
      { name: "GLM 5.2", fit: 0.9, cost: "$0.0178" },
      { name: "Kimi K2.6", fit: 0.86, cost: "$0.0093" },
      { name: "DeepSeek V4 Flash", fit: 0.79, cost: "$0.0019" },
      { name: "Qwen3 32B", fit: 0.52, cost: "$0.0015" },
    ],
  },
];

export function RouterVisual() {
  const [i, setI] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setI((v) => (v + 1) % SCENES.length), 4200);
    return () => clearInterval(id);
  }, []);

  const scene = SCENES[i];
  const winner = useMemo(
    () => scene.candidates.reduce((a, b) => (b.fit > a.fit ? b : a)),
    [scene],
  );

  return (
    <div className="relative">
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-12 -z-10 opacity-70 blur-3xl"
        style={{
          background:
            "radial-gradient(38% 44% at 50% 42%, var(--glow), transparent 70%)",
        }}
      />

      <div className="overflow-hidden rounded-2xl border border-line bg-elevated shadow-2xl shadow-black/5 dark:shadow-black/40">
        <div className="flex items-center gap-2 border-b border-line bg-surface px-4 py-3">
          <span className="text-[0.8125rem] font-medium">Someone asks…</span>
          <span className="ml-auto text-[0.75rem] text-ink-faint">example</span>
        </div>

        <div className="p-4 sm:p-5">
          <AnimatePresence mode="wait">
            <m.p
              key={`q-${i}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="rounded-lg border border-line bg-surface p-3.5 text-[0.9375rem] leading-snug"
            >
              {scene.prompt}
            </m.p>
          </AnimatePresence>

          <p className="mt-4 mb-2.5 text-[0.75rem] text-ink-faint">
            How well each model would do, and what it would charge
          </p>

          <ul className="flex flex-col gap-1.5">
            {scene.candidates.map((c, idx) => {
              const isWinner = c.name === winner.name;
              return (
                <li
                  key={c.name}
                  className={cx(
                    "relative overflow-hidden rounded-lg border px-3 py-2.5 transition-colors duration-300",
                    isWinner
                      ? "border-accent/45 bg-accent/[0.07]"
                      : "border-line bg-surface",
                  )}
                >
                  <m.span
                    aria-hidden
                    className={cx(
                      "absolute inset-y-0 left-0",
                      isWinner
                        ? "bg-accent/12"
                        : "bg-ink/[0.035] dark:bg-white/[0.03]",
                    )}
                    initial={{ width: 0 }}
                    animate={{ width: `${c.fit * 100}%` }}
                    transition={{
                      duration: 0.65,
                      delay: idx * 0.05,
                      ease: [0.16, 1, 0.3, 1],
                    }}
                  />
                  <div className="relative flex items-center gap-2.5">
                    <span
                      className={cx(
                        "size-1.5 shrink-0 rounded-full",
                        isWinner ? "bg-accent" : "bg-line-strong",
                      )}
                    />
                    <span
                      className={cx(
                        "text-[0.875rem]",
                        isWinner ? "font-medium text-ink" : "text-ink-muted",
                      )}
                    >
                      {c.name}
                    </span>
                    <span className="ml-auto text-[0.8125rem] text-ink-faint tabular-nums">
                      {c.cost}
                    </span>
                    <span className="w-4 shrink-0">
                      {isWinner ? (
                        <Check size={14} className="text-accent" strokeWidth={2.6} />
                      ) : null}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="mt-4 flex items-center gap-2 border-t border-line pt-4">
            <span className="text-[0.8125rem] text-ink-muted">We picked</span>
            <AnimatePresence mode="wait">
              <m.span
                key={`w-${i}`}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 6 }}
                transition={{ duration: 0.28 }}
                className="text-[0.875rem] font-medium text-ink"
              >
                {winner.name}
              </m.span>
            </AnimatePresence>
            <span className="ml-auto rounded-full border border-accent/35 bg-accent/10 px-2.5 py-0.5 text-[0.75rem] text-accent">
              {scene.verdict}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-center gap-1.5">
        {SCENES.map((s, idx) => (
          <button
            key={s.prompt}
            type="button"
            onClick={() => setI(idx)}
            aria-label={`Show example ${idx + 1}`}
            className={cx(
              "h-1 rounded-full transition-all duration-300",
              idx === i ? "w-6 bg-accent" : "w-1.5 bg-line-strong hover:bg-ink-faint",
            )}
          />
        ))}
      </div>
    </div>
  );
}
