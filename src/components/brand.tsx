import { cx } from "@/components/ui/primitives";

/**
 * A solid "D" with a demultiplexer knocked out of it: one line enters the flat
 * edge, splits, and leaves as three.
 *
 * Solid rather than outlined on purpose. The outlined version had a 2.6-unit
 * stroke for the D *and* the fan inside it, so below ~32px the two merged into a
 * grey smudge. A filled silhouette keeps the D readable at 16px and lets the
 * interior detail simply fade out when it is too small to matter.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cx("shrink-0", className)}
      role="img"
      aria-label="DemuxLLM"
    >
      <path d="M4 4h9.5a12 12 0 0 1 0 24H4z" className="fill-ink" />
      <g
        className="stroke-canvas"
        strokeWidth={2.6}
        strokeLinecap="round"
        fill="none"
      >
        <path d="M4 16h6.5" />
        <path d="M10.5 16c4.5 0 3.5-6 8-6" />
        <path d="M10.5 16h9" />
        <path d="M10.5 16c4.5 0 3.5 6 8 6" />
      </g>
      <circle cx="10.5" cy="16" r="2.9" fill="var(--logo-accent)" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span
      className={cx(
        "text-[1.0625rem] leading-none font-semibold tracking-[-0.025em] whitespace-nowrap",
        className,
      )}
    >
      Demux<span className="text-ink-muted">LLM</span>
    </span>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cx("flex items-center gap-2.5", className)}>
      <LogoMark className="h-[26px] w-[26px]" />
      <Wordmark />
    </span>
  );
}
