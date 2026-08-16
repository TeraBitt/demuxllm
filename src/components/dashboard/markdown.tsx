"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cx } from "@/components/ui/primitives";

/**
 * Just enough markdown for model output, rendered as React nodes rather than
 * HTML — nothing a model emits is ever parsed as markup, so a prompt cannot
 * inject an element into the page.
 *
 * It is line-driven rather than block-driven on purpose. Models freely mix a
 * heading, a sentence and a list inside one paragraph with single newlines
 * between them; matching whole blocks drops the markers and the reader sees a
 * literal "###".
 */

/* --------------------------------------------------------------- inline -- */

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|~~[^~]+~~|\*[^*\n]+\*|_[^_\n]+_|\[[^\]]+\]\([^)\s]+\))/g;
const LINK = /^\[([^\]]+)\]\(([^)\s]+)\)$/;

export function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(INLINE).map((part, i) => {
        if (!part) return null;

        if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
          return (
            <strong key={i} className="font-semibold text-ink">
              <Inline text={part.slice(2, -2)} />
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
          return (
            <code
              key={i}
              className="glass-line rounded-[0.3rem] border bg-ink/[0.04] px-1 py-0.5 font-mono text-[0.8125em] text-accent dark:bg-white/[0.05]"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        if (part.startsWith("~~") && part.endsWith("~~") && part.length > 4) {
          return (
            <span key={i} className="line-through opacity-60">
              {part.slice(2, -2)}
            </span>
          );
        }

        const link = LINK.exec(part);
        if (link) {
          const external = /^https?:\/\//.test(link[2]);
          return (
            <a
              key={i}
              href={link[2]}
              target={external ? "_blank" : undefined}
              rel={external ? "noopener noreferrer" : undefined}
              className="text-accent underline decoration-accent/35 underline-offset-2 transition-colors hover:decoration-accent"
            >
              {link[1]}
            </a>
          );
        }

        if (
          (part.startsWith("*") && part.endsWith("*") && part.length > 2) ||
          (part.startsWith("_") && part.endsWith("_") && part.length > 2)
        ) {
          return (
            <em key={i} className="italic">
              {part.slice(1, -1)}
            </em>
          );
        }

        return part;
      })}
    </>
  );
}

/* ----------------------------------------------------------------- code -- */

function CodeFence({ raw }: { raw: string }) {
  const [copied, setCopied] = useState(false);
  const lang = /^```([a-zA-Z0-9+#._-]*)/.exec(raw)?.[1] ?? "";
  const body = raw
    .replace(/^```[a-zA-Z0-9+#._-]*\n?/, "")
    .replace(/```\s*$/, "")
    .replace(/\n$/, "");

  function copy() {
    navigator.clipboard?.writeText(body).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      },
      () => {},
    );
  }

  return (
    <div className="glass glass-line group/code relative overflow-hidden rounded-xl border">
      <div className="glass-line flex items-center border-b px-3 py-1.5">
        <span className="font-mono text-[0.6875rem] tracking-[0.06em] text-ink-faint uppercase">
          {lang || "text"}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label="Copy code"
          className="ml-auto flex items-center gap-1.5 rounded-md px-1.5 py-1 text-[0.6875rem] text-ink-faint opacity-0 transition-all group-hover/code:opacity-100 hover:text-ink focus-visible:opacity-100"
        >
          {copied ? <Check size={12} strokeWidth={3} /> : <Copy size={12} />}
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3.5 font-mono text-[0.8125rem] leading-relaxed text-ink">
        <code>{body}</code>
      </pre>
    </div>
  );
}

/* ---------------------------------------------------------------- table -- */

const splitRow = (line: string) =>
  line
    .replace(/^\s*\|/, "")
    .replace(/\|\s*$/, "")
    .split("|")
    .map((c) => c.trim());

function Table({ rows }: { rows: string[] }) {
  const head = splitRow(rows[0]);
  const body = rows.slice(2).map(splitRow);

  return (
    <div className="glass-line overflow-x-auto rounded-xl border">
      <table className="w-full border-collapse text-[0.8125rem]">
        <thead>
          <tr className="glass-line border-b">
            {head.map((c, i) => (
              <th key={i} className="px-3 py-2 text-left font-medium text-ink whitespace-nowrap">
                <Inline text={c} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="glass-line divide-y">
          {body.map((row, i) => (
            <tr key={i}>
              {row.map((c, j) => (
                <td key={j} className="px-3 py-2 align-top text-ink-muted">
                  <Inline text={c} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------------------------------------------------------- block -- */

const HEADING = /^(#{1,4})\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;
const QUOTE = /^\s*>\s?(.*)$/;
const RULE = /^\s*([-*_])(?:\s*\1){2,}\s*$/;
const TABLE_DIVIDER = /^\s*\|?[\s:|-]+\|[\s:|-]*$/;

function Block({ block }: { block: string }) {
  const out: React.ReactNode[] = [];
  let para: string[] = [];
  let bullets: string[] = [];
  let numbers: string[] = [];
  let quote: string[] = [];

  const flushPara = () => {
    if (!para.length) return;
    out.push(
      <p key={`p${out.length}`} className="leading-[1.7]">
        <Inline text={para.join(" ")} />
      </p>,
    );
    para = [];
  };

  const flushBullets = () => {
    if (!bullets.length) return;
    out.push(
      <ul key={`u${out.length}`} className="flex flex-col gap-1.5">
        {bullets.map((item, i) => (
          <li key={i} className="flex gap-2.5 leading-[1.7]">
            <span aria-hidden className="mt-[0.6em] size-1 shrink-0 rounded-full bg-ink-faint" />
            <span className="min-w-0">
              <Inline text={item} />
            </span>
          </li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  const flushNumbers = () => {
    if (!numbers.length) return;
    out.push(
      <ol key={`o${out.length}`} className="flex flex-col gap-1.5">
        {numbers.map((item, i) => (
          <li key={i} className="flex gap-2.5 leading-[1.7]">
            <span className="shrink-0 font-mono text-[0.8125em] text-ink-faint tabular-nums">
              {i + 1}.
            </span>
            <span className="min-w-0">
              <Inline text={item} />
            </span>
          </li>
        ))}
      </ol>,
    );
    numbers = [];
  };

  const flushQuote = () => {
    if (!quote.length) return;
    out.push(
      <blockquote
        key={`q${out.length}`}
        className="border-l-2 border-accent/40 pl-3.5 text-ink-muted italic"
      >
        <Inline text={quote.join(" ")} />
      </blockquote>,
    );
    quote = [];
  };

  const flushAll = () => {
    flushPara();
    flushBullets();
    flushNumbers();
    flushQuote();
  };

  const lines = block.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // A table needs its divider row to be a table at all, so look one ahead.
    if (line.includes("|") && lines[i + 1] && TABLE_DIVIDER.test(lines[i + 1])) {
      flushAll();
      const rows: string[] = [line, lines[i + 1]];
      let j = i + 2;
      while (j < lines.length && lines[j].includes("|")) rows.push(lines[j++]);
      out.push(<Table key={`t${out.length}`} rows={rows} />);
      i = j - 1;
      continue;
    }

    if (RULE.test(line)) {
      flushAll();
      out.push(<hr key={`r${out.length}`} className="glass-line border-t" />);
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      flushAll();
      const level = heading[1].length;
      out.push(
        <h3
          key={`h${out.length}`}
          className={cx(
            "font-semibold text-ink",
            level <= 2 ? "text-[1.0625rem] tracking-[-0.02em]" : "text-[0.9375rem]",
          )}
        >
          <Inline text={heading[2]} />
        </h3>,
      );
      continue;
    }

    const q = QUOTE.exec(line);
    if (q) {
      flushPara();
      flushBullets();
      flushNumbers();
      quote.push(q[1]);
      continue;
    }

    const numbered = NUMBERED.exec(line);
    if (numbered) {
      flushPara();
      flushBullets();
      flushQuote();
      numbers.push(numbered[2]);
      continue;
    }

    const bullet = BULLET.exec(line);
    if (bullet) {
      flushPara();
      flushNumbers();
      flushQuote();
      bullets.push(bullet[1]);
      continue;
    }

    if (!line.trim()) {
      flushAll();
      continue;
    }

    flushBullets();
    flushNumbers();
    flushQuote();
    para.push(line);
  }

  flushAll();
  return <>{out}</>;
}

const FENCE = /(```[\s\S]*?(?:```|$))/g;

export function Markdown({ text, className }: { text: string; className?: string }) {
  return (
    <div className={cx("flex flex-col gap-3.5", className)}>
      {text.split(FENCE).map((section, i) => {
        if (section.startsWith("```")) return <CodeFence key={i} raw={section} />;
        if (!section.trim()) return null;
        return <Block key={i} block={section.replace(/^\n+|\n+$/g, "")} />;
      })}
    </div>
  );
}
