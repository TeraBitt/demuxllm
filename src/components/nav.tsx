"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { Logo } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button, cx } from "@/components/ui/primitives";
import { ROUTES } from "@/lib/data";

/** Scroll position read straight from the DOM — no state, no effect, SSR-safe. */
function subscribeToScroll(onChange: () => void) {
  window.addEventListener("scroll", onChange, { passive: true });
  return () => window.removeEventListener("scroll", onChange);
}

export function Nav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  const scrolled = useSyncExternalStore(
    subscribeToScroll,
    () => window.scrollY > 8,
    () => false,
  );

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header
      className={cx(
        "sticky top-0 z-50 transition-colors duration-300",
        scrolled || open
          ? "border-b border-line bg-canvas/85 backdrop-blur-xl"
          : "border-b border-transparent",
      )}
    >
      <nav className="mx-auto flex h-16 max-w-6xl items-center gap-2 px-5 sm:px-8">
        <Link href="/" aria-label="DemuxLLM home">
          <Logo />
        </Link>

        <ul className="ml-6 hidden items-center gap-1 md:flex">
          {ROUTES.map((r) => {
            const active = pathname === r.href;
            return (
              <li key={r.href}>
                <Link
                  href={r.href}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "rounded-lg px-3 py-1.5 text-sm transition-colors",
                    active
                      ? "bg-surface text-ink"
                      : "text-ink-muted hover:bg-surface hover:text-ink",
                  )}
                >
                  {r.label}
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="ml-auto flex items-center gap-1.5">
          <ThemeToggle />
          <Link
            href="/docs"
            className="hidden rounded-lg px-3 py-1.5 text-sm text-ink-muted transition-colors hover:bg-surface hover:text-ink sm:block"
          >
            Sign in
          </Link>
          <Button href="/docs" size="sm" className="hidden h-9 px-3.5 sm:inline-flex">
            Get started
            <ArrowUpRight size={14} strokeWidth={2.2} />
          </Button>

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="grid size-9 place-items-center rounded-lg text-ink-muted hover:bg-surface hover:text-ink md:hidden"
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </nav>

      {open ? (
        <div className="border-t border-line px-5 pt-2 pb-6 md:hidden">
          <ul className="flex flex-col">
            {ROUTES.map((r) => (
              <li key={r.href}>
                <Link
                  href={r.href}
                  onClick={() => setOpen(false)}
                  className="flex items-center justify-between border-b border-line py-3.5 text-[0.9375rem] text-ink"
                >
                  {r.label}
                  <ArrowUpRight size={15} className="text-ink-faint" />
                </Link>
              </li>
            ))}
          </ul>
          <Button href="/docs" className="mt-5 h-11 w-full">
            Get started
          </Button>
        </div>
      ) : null}
    </header>
  );
}
