"use client";

import { useCallback, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import { cx } from "@/components/ui/primitives";

export function CopyButton({
  value,
  className,
  label = "Copy",
}: {
  value: string;
  className?: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const copy = useCallback(() => {
    navigator.clipboard?.writeText(value).then(
      () => {
        setCopied(true);
        clearTimeout(timer.current);
        timer.current = setTimeout(() => setCopied(false), 1600);
      },
      () => {
        /* clipboard denied — leave the button idle rather than lying */
      },
    );
  }, [value]);

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? "Copied" : label}
      className={cx(
        "grid size-7 shrink-0 place-items-center rounded-md text-ink-faint transition-colors hover:bg-surface hover:text-ink",
        className,
      )}
    >
      {copied ? (
        <Check size={13} strokeWidth={2.4} className="text-accent" />
      ) : (
        <Copy size={13} strokeWidth={2} />
      )}
    </button>
  );
}

/** The whole integration, in one line you can copy. */
export function EndpointField({ value }: { value: string }) {
  return (
    <div className="inline-flex max-w-full items-center gap-2 rounded-lg border border-line bg-elevated py-2 pr-2 pl-3.5">
      <span className="truncate font-mono text-[0.8125rem] text-ink">
        {value}
      </span>
      <CopyButton value={value} label="Copy address" />
    </div>
  );
}
