"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { m } from "@/components/ui/motion";
import { cx } from "@/components/ui/primitives";

export function FaqList({
  items,
  className,
}: {
  items: readonly { q: string; a: string }[];
  className?: string;
}) {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <ul className={cx("border-t border-line", className)}>
      {items.map((f, i) => {
        const isOpen = open === i;
        return (
          <li key={f.q} className="border-b border-line">
            <button
              type="button"
              onClick={() => setOpen(isOpen ? null : i)}
              aria-expanded={isOpen}
              className="flex w-full items-start gap-4 py-5 text-left"
            >
              <span
                className={cx(
                  "text-[0.9375rem] font-medium transition-colors sm:text-base",
                  isOpen ? "text-ink" : "text-ink-muted",
                )}
              >
                {f.q}
              </span>
              <Plus
                size={16}
                strokeWidth={2}
                className={cx(
                  "mt-0.5 ml-auto shrink-0 transition-transform duration-300",
                  isOpen ? "rotate-45 text-accent" : "text-ink-faint",
                )}
              />
            </button>

            <AnimatePresence initial={false}>
              {isOpen ? (
                <m.div
                  key="body"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                  className="overflow-hidden"
                >
                  <p className="max-w-2xl pr-8 pb-6 text-[0.9375rem] leading-relaxed text-ink-muted">
                    {f.a}
                  </p>
                </m.div>
              ) : null}
            </AnimatePresence>
          </li>
        );
      })}
    </ul>
  );
}
