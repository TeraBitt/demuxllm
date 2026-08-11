"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

/**
 * The dashboard is an application, not a page: it owns the full viewport, has
 * its own sidebar, and a marketing footer under a chat composer would read as a
 * mistake. Rather than splitting the tree into route groups with two root
 * layouts, the site chrome is gated here — one client component, no file moves,
 * and the marketing pages are untouched.
 */
export function AppChrome({
  nav,
  footer,
  children,
}: {
  nav: ReactNode;
  footer: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const bare = pathname?.startsWith("/dashboard") ?? false;

  if (bare) return <main id="main">{children}</main>;

  return (
    <>
      {nav}
      <main id="main">{children}</main>
      {footer}
    </>
  );
}
