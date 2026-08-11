"use client";

import { useState } from "react";
import { CopyButton } from "@/components/copy-field";
import { CodeBlock } from "@/components/ui/code";
import { cx } from "@/components/ui/primitives";

type Snippet = { readonly label: string; readonly code: string };

/** A tabbed code panel. The tab set is whatever the caller hands it. */
export function Quickstart({
  snippets,
}: {
  snippets: Readonly<Record<string, Snippet>>;
}) {
  const langs = Object.keys(snippets);
  const [lang, setLang] = useState(langs[0]);
  const snippet = snippets[lang] ?? snippets[langs[0]];

  return (
    <div className="min-w-0 overflow-hidden rounded-xl border border-line bg-elevated">
      <div className="flex items-center gap-1 border-b border-line bg-surface px-2 py-1.5">
        {langs.map((l) => (
          <button
            key={l}
            type="button"
            onClick={() => setLang(l)}
            className={cx(
              "rounded-md px-3 py-1.5 text-[0.8125rem] transition-colors",
              lang === l ? "bg-elevated text-ink" : "text-ink-faint hover:text-ink-muted",
            )}
          >
            {snippets[l].label}
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
