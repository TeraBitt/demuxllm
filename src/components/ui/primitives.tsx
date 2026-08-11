import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/* ---------------------------------------------------------------- layout -- */

export function Section({
  id,
  children,
  className,
  bordered = true,
  /** Use for the first section under a PageHeader, which already has padding. */
  tight = false,
}: {
  id?: string;
  children: ReactNode;
  className?: string;
  bordered?: boolean;
  tight?: boolean;
}) {
  return (
    <section
      id={id}
      className={cx("scroll-mt-20", bordered && "border-t border-line", className)}
    >
      <div
        className={cx(
          "mx-auto max-w-6xl px-5 sm:px-8",
          tight ? "py-10 sm:py-12" : "py-16 sm:py-24",
        )}
      >
        {children}
      </div>
    </section>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="size-1.5 rounded-full bg-accent" />
      <span className="text-[0.8125rem] font-medium text-accent">{children}</span>
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  lede,
  align = "left",
  className,
}: {
  eyebrow?: string;
  title: ReactNode;
  lede?: ReactNode;
  align?: "left" | "center";
  className?: string;
}) {
  return (
    <div
      className={cx(
        "flex flex-col gap-3.5",
        align === "center" && "items-center text-center",
        className,
      )}
    >
      {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
      <h2 className="max-w-2xl text-[1.75rem] leading-[1.15] font-semibold tracking-[-0.03em] text-balance sm:text-4xl">
        {title}
      </h2>
      {lede ? (
        <p className="max-w-xl text-[0.9375rem] leading-relaxed text-ink-muted sm:text-base">
          {lede}
        </p>
      ) : null}
    </div>
  );
}

/** Top-of-page banner for every route except the home page. */
export function PageHeader({
  eyebrow,
  title,
  lede,
  children,
}: {
  eyebrow: string;
  title: string;
  lede: string;
  children?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden border-b border-line">
      <div className="relative mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-20">
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1 className="mt-4 max-w-3xl text-[2rem] leading-[1.1] font-semibold tracking-[-0.035em] text-balance sm:text-[2.75rem]">
          {title}
        </h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-ink-muted">
          {lede}
        </p>
        {children ? <div className="mt-7">{children}</div> : null}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- button -- */

type ButtonProps = Omit<ComponentProps<"a">, "href"> & {
  href: string;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
};

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas";

const BUTTON_VARIANTS = {
  primary: "bg-ink text-canvas hover:opacity-90 active:scale-[0.985]",
  secondary:
    "border border-line-strong bg-elevated text-ink hover:border-ink-faint hover:bg-surface active:scale-[0.985]",
  ghost: "text-ink-muted hover:bg-surface hover:text-ink",
} as const;

const BUTTON_SIZES = {
  sm: "h-8 px-3 text-[0.8125rem]",
  md: "h-10 px-4 text-sm",
} as const;

export function Button({
  variant = "primary",
  size = "md",
  className,
  href,
  ...props
}: ButtonProps) {
  const classes = cx(
    BUTTON_BASE,
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    className,
  );
  // Internal routes go through <Link> for client-side navigation.
  return href.startsWith("/") ? (
    <Link href={href} className={classes} {...props} />
  ) : (
    <a href={href} className={classes} {...props} />
  );
}

/* ------------------------------------------------------------------ card -- */

export function Card({
  children,
  className,
  hover = false,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <div
      className={cx(
        "rounded-xl border border-line bg-elevated",
        hover &&
          "transition-colors duration-200 hover:border-line-strong hover:bg-surface",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Pill({
  children,
  className,
  tone = "neutral",
}: {
  children: ReactNode;
  className?: string;
  tone?: "neutral" | "accent";
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[0.75rem] whitespace-nowrap",
        tone === "accent"
          ? "border-accent/35 bg-accent/10 text-accent"
          : "border-line bg-surface text-ink-muted",
        className,
      )}
    >
      {children}
    </span>
  );
}
