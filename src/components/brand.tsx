import { cx } from "@/components/ui/primitives";

/**
 * The mark is a demultiplexer drawn as the switch it actually is: one signal
 * arrives on the left, reaches a switch body holding a dial, and leaves on
 * exactly one of three outputs. The needle points at the output it chose, and
 * that path — needle, trace, terminal — is the only thing wearing the accent.
 * Everything else is ink.
 *
 * Three rules hold the drawing together. Keep them if it is ever redrawn:
 *
 *   1. The needle and the lit trace are ONE straight 45° line leaving the hub,
 *      passing exactly through the octagon's cut corner. That is the whole
 *      reason the corner is cut at 45°. The chosen path is visibly continuous
 *      from dial to terminal, which is the thing the mark is trying to say.
 *   2. The silhouette is symmetric — three terminals, always, evenly spaced.
 *      Only the COLOUR is asymmetric. So the mark stays optically balanced
 *      beside the wordmark while still reading as "a choice was made".
 *   3. Every diagonal in the drawing is 45°. There are no other angles.
 *
 * Two cuts, because one drawing cannot do both jobs:
 *
 * `LogoMark` is the full cut, with the dial ring and hollow ring terminals. It
 * needs ~40px. Below that the 1.4-unit ring strokes fall under a pixel and the
 * interior turns to grey haze. Used at display sizes: the CTA and the 404.
 *
 * `LogoMarkCompact` is the small cut, and a real simplification rather than the
 * same paths made heavier: the dial ring is dropped so hub and needle carry the
 * dial alone, ring terminals become solid dots, and strokes go up ~50%. It is
 * the same skeleton and the same 45° geometry, so the two cuts read as one
 * mark. Used by the nav, the footer and `app/icon.svg`.
 *
 * Both stroke in `--ink` with `--accent` on the chosen path, so they invert
 * with the theme and sit correctly on canvas, surface or elevated. See
 * BRAND.md for the colour rules — in particular why the accent is never
 * orange, and what the mark may not be used for.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cx("shrink-0", className)}
      role="img"
      aria-label="DemuxLLM"
    >
      <g transform="translate(0.45 0)">
        <g
          fill="none"
          className="stroke-ink"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {/* Switch body */}
          <path
            d="M13.5 10H18.5L21.5 13V19L18.5 22H13.5L10.5 19V13Z"
            strokeWidth={1.9}
          />
          {/* Input lead */}
          <path d="M6.6 16h3.9" strokeWidth={1.7} />
          {/* Dial face */}
          <circle cx="16" cy="16" r="2.6" strokeWidth={1.5} />
          {/* The two routes not taken */}
          <path d="M21.5 16h2.95" strokeWidth={1.7} />
          <path d="M20.25 20.25 25.2 25.2" strokeWidth={1.7} />
          <circle cx="27" cy="16" r="1.85" strokeWidth={1.4} />
          <circle cx="27" cy="24.7" r="1.85" strokeWidth={1.4} />
        </g>

        {/* Input terminal */}
        <circle cx="4.2" cy="16" r="2" className="fill-ink" />

        {/* The chosen path: needle and trace are one unbroken 45° line. */}
        <g
          fill="none"
          stroke="var(--accent)"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M16 16 25.2 6.8" strokeWidth={1.7} />
          <circle cx="27" cy="7.3" r="1.85" strokeWidth={1.4} />
        </g>
        <circle cx="16" cy="16" r="1.15" fill="var(--accent)" />
      </g>
    </svg>
  );
}

export function LogoMarkCompact({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cx("shrink-0", className)}
      role="img"
      aria-label="DemuxLLM"
    >
      <g transform="translate(0.45 0)">
        <g
          fill="none"
          className="stroke-ink"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path
            d="M13.5 10H18.5L21.5 13V19L18.5 22H13.5L10.5 19V13Z"
            strokeWidth={2.6}
          />
          <path d="M6.6 16h3.9" strokeWidth={2.4} />
          <path d="M21.5 16h3.2" strokeWidth={2.4} />
          <path d="M20.25 20.25 24.7 24.7" strokeWidth={2.4} />
        </g>

        <g className="fill-ink">
          <circle cx="4.2" cy="16" r="2.4" />
          <circle cx="27" cy="16" r="2.3" />
          <circle cx="27" cy="24.7" r="2.3" />
        </g>

        <path
          d="M16 16 24.7 7.3"
          fill="none"
          stroke="var(--accent)"
          strokeWidth={2.6}
          strokeLinecap="round"
        />
        <circle cx="16" cy="16" r="1.9" fill="var(--accent)" />
        <circle cx="27" cy="7.3" r="2.3" fill="var(--accent)" />
      </g>
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
    <span className={cx("flex items-center gap-2", className)}>
      <LogoMarkCompact className="h-[27px] w-[27px]" />
      <Wordmark />
    </span>
  );
}
