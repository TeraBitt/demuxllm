import { cx } from "@/components/ui/primitives";

/**
 * Server-rendered syntax accent. Deliberately not a highlighter: comments and
 * strings carry almost all the readability, and skipping a tokenizer keeps this
 * at zero client JS.
 */
const COMMENT = /^(\s*)((?:#|\/\/).*)$/;
const STRING = /("[^"]*"|'[^']*')/g;

function renderLine(line: string, key: number) {
  // An empty <span class="block"> collapses to zero height, which silently ate
  // every blank line in a snippet. A hard space keeps the gap.
  if (!line.trim()) {
    return (
      <span key={key} className="block">
        {" "}
      </span>
    );
  }

  const comment = COMMENT.exec(line);
  if (comment) {
    return (
      <span key={key} className="block">
        {comment[1]}
        <span className="text-ink-faint">{comment[2]}</span>
      </span>
    );
  }

  const [code, trailing] = splitTrailingComment(line);
  return (
    <span key={key} className="block">
      {code.split(STRING).map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className="text-accent">
            {part}
          </span>
        ) : (
          part
        ),
      )}
      {trailing ? <span className="text-ink-faint">{trailing}</span> : null}
    </span>
  );
}

/**
 * Both comment styles need a leading space, which is also what keeps the `//`
 * in a URL out of it — those are preceded by a colon, never a space.
 */
function splitTrailingComment(line: string): [string, string] {
  const marks = [line.indexOf(" #"), line.indexOf(" //")].filter((i) => i !== -1);
  if (marks.length === 0) return [line, ""];
  const at = Math.min(...marks);
  return [line.slice(0, at), line.slice(at)];
}

export function CodeBlock({
  code,
  filename,
  className,
  actions,
}: {
  code: string;
  filename?: string;
  className?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div
      className={cx(
        "overflow-hidden rounded-xl border border-line bg-elevated",
        className,
      )}
    >
      {filename || actions ? (
        <div className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2">
          {filename ? (
            <span className="font-mono text-[0.6875rem] text-ink-faint">
              {filename}
            </span>
          ) : null}
          <div className="ml-auto flex items-center gap-1">{actions}</div>
        </div>
      ) : null}
      <pre className="overflow-x-auto p-4 font-mono text-[0.75rem] leading-[1.7] text-ink-muted sm:text-[0.8125rem]">
        <code>{code.split("\n").map(renderLine)}</code>
      </pre>
    </div>
  );
}
