"use client";

import { LazyMotion, MotionConfig, domAnimation, m, type Variants } from "motion/react";
import type { ReactNode } from "react";

/**
 * `LazyMotion` + the `m` component ship ~5 kB of the animation runtime instead of
 * the ~34 kB full `motion` bundle. Every animated element in the app uses `m.*`,
 * so nothing pulls the eager bundle back in.
 *
 * `reducedMotion="user"` matters more than it looks: these animations are
 * JS-driven inline styles, so the CSS `prefers-reduced-motion` block does not
 * reach them. Without this, a reduced-motion visitor would still get every
 * scroll reveal. With it, elements jump straight to their final state.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </LazyMotion>
  );
}

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] },
  },
};

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.04 } },
};

type RevealProps = {
  children: ReactNode;
  className?: string;
  delay?: number;
  /** Stagger direct children that use the `fadeUp` variant. */
  group?: boolean;
  as?: "div" | "section" | "li" | "tr";
};

export function Reveal({
  children,
  className,
  delay = 0,
  group = false,
  as = "div",
}: RevealProps) {
  const Tag = m[as];
  return (
    <Tag
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
      variants={group ? stagger : fadeUp}
      transition={delay ? { delay } : undefined}
    >
      {children}
    </Tag>
  );
}

export function RevealItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <m.div className={className} variants={fadeUp}>
      {children}
    </m.div>
  );
}

export { m };
