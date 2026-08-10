"use client";

import { useState } from "react";
import { CopyButton } from "@/components/copy-field";
import { CodeBlock } from "@/components/ui/code";
import { cx } from "@/components/ui/primitives";
import { DOC_SNIPPETS } from "@/lib/data";

type Lang = keyof typeof DOC_SNIPPETS;
const LANGS = Object.keys(DOC_SNIPPETS) as Lang[];

export function Quickstart() {
  const [lang, setLang] = useState<Lang>("python");
  const snippet = DOC_SNIPPETS[lang];

  return (
    <div className="min-w-0 overflow-hidden rounded-xl border border-line bg-elevated">
      <div className="flex items-center gap-1 border-b border-line bg-surface px-2 py-1.5">
        {LANGS.map((l) => (
          <button
            key={l}
            type="button"
            onClick={() => setLang(l)}
            className={cx(
              "rounded-md px-3 py-1.5 text-[0.8125rem] transition-colors",
              lang === l ? "bg-elevated text-ink" : "text-ink-faint hover:text-ink-muted",
            )}
          >
            {DOC_SNIPPETS[l].label}
          </button>
        ))}
        <div className="ml-auto">
          <CopyButton value={snippet.code} label="Copy code" />
        </div>
      </div>
      <CodeBlock code={snippet.code} className="rounded-none border-0" />
    </div>
  );
}
