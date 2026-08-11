"use client";

import { LazyMotion, MotionConfig, domAnimation, m } from "motion/react";
import type { ReactNode } from "react";

/**
 * `LazyMotion` + the `m` component ship ~5 kB of the animation runtime instead of
 * the ~34 kB full `motion` bundle. Every animated element in the app uses `m.*`,
 * so nothing pulls the eager bundle back in.
 *
 * `reducedMotion="user"` matters more than it looks: these animations are
 * JS-driven inline styles, so the CSS `prefers-reduced-motion` block does not
 * reach them. Without this, a reduced-motion visitor would still get every
 * animation. With it, elements jump straight to their final state.
 *
 * What remains animated is only what carries meaning: the FAQ accordion, the
 * benchmark chart drawing itself in, the rotating router demo. The decorative
 * scroll-reveal fade that used to wrap most of the page is gone — see `Reveal`.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </LazyMotion>
  );
}

type RevealProps = {
  children: ReactNode;
  className?: string;
  /** Retained so call sites need no edit; no longer does anything. */
  delay?: number;
  group?: boolean;
  as?: "div" | "section" | "li" | "tr";
};

/**
 * Content appears immediately. This was a fade-up-on-scroll wrapper, which read
 * as filler and made every page feel slow on the way down — content the reader
 * has already scrolled to should not still be arriving.
 *
 * It stays as a plain element rather than being deleted from ~20 call sites, so
 * the layout grouping it provides is preserved and reinstating an animation
 * later is a one-file change.
 */
export function Reveal({ children, className, as = "div" }: RevealProps) {
  const Tag = as;
  return <Tag className={className}>{children}</Tag>;
}

export function RevealItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={className}>{children}</div>;
}

export { m };
