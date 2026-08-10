"use client";

import { Moon, Sun } from "lucide-react";

/** Runs before paint in <head> to stamp `.dark` and avoid a flash. */
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("dx-theme");var d=t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d);}catch(e){document.documentElement.classList.add("dark");}})()`;

/**
 * The current theme lives in one place — the `dark` class on <html>. Both icons
 * render and CSS picks the visible one, so there is no React state to hydrate,
 * no effect, and no mismatch between server and client markup.
 */
export function ThemeToggle({ className = "" }: { className?: string }) {
  function toggle() {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("dx-theme", next ? "dark" : "light");
    } catch {
      /* storage blocked — the toggle still works for this session */
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle colour theme"
      className={`grid size-8 place-items-center rounded-lg text-ink-muted transition-colors hover:bg-surface hover:text-ink ${className}`}
    >
      <Sun size={15} strokeWidth={1.8} className="hidden dark:block" />
      <Moon size={15} strokeWidth={1.8} className="block dark:hidden" />
    </button>
  );
}
