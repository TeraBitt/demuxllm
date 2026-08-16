/**
 * The transport. One place that knows how to talk to Chutes, so the router and
 * the answer loop cannot drift apart on headers, errors or usage parsing.
 */

export const BASE = "https://llm.chutes.ai/v1";

export type Usage = { inTok: number; outTok: number };

export const EMPTY_USAGE: Usage = { inTok: 0, outTok: 0 };

export function addUsage(a: Usage, b: Usage): Usage {
  return { inTok: a.inTok + b.inTok, outTok: a.outTok + b.outTok };
}

export function readUsage(usage: unknown, fallback: Usage): Usage {
  const u = usage as { prompt_tokens?: number; completion_tokens?: number } | null;
  return {
    inTok: u?.prompt_tokens ?? fallback.inTok,
    outTok: u?.completion_tokens ?? fallback.outTok,
  };
}

/**
 * `thinking` rides a header rather than the body. Chutes names X-Enable-Thinking
 * in the CORS allowlist it serves, which makes it the supported switch; the
 * vLLM-style `chat_template_kwargs` is a body field a strict proxy may reject.
 */
export async function chutes(
  apiKey: string,
  body: Record<string, unknown>,
  opts: { thinking?: boolean; signal?: AbortSignal } = {},
) {
  let res: Response;
  try {
    res = await fetch(`${BASE}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
        ...(opts.thinking === undefined
          ? {}
          : { "X-Enable-Thinking": String(opts.thinking) }),
      },
      body: JSON.stringify(body),
      signal: opts.signal,
    });
  } catch (err) {
    // An aborted run is a user action, not a failure — let it through untouched
    // so the caller can tell the two apart.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new Error(
      "Could not reach Chutes. Check the network, or whether the key still has credit.",
    );
  }

  if (!res.ok) {
    // Chutes puts the useful half of a failure in the body, not the status.
    const detail = await res.text().catch(() => "");
    const trimmed = detail.slice(0, 200);
    throw new Error(
      res.status === 401
        ? "Chutes rejected the key. Check it under Settings."
        : res.status === 429
          ? "Chutes is rate-limiting this key. Wait a moment and send again."
          : `Chutes returned ${res.status}${trimmed ? ` — ${trimmed}` : ""}`,
    );
  }

  return res;
}

/**
 * Server-sent events from a chat completion, as parsed JSON frames.
 *
 * A frame can straddle two network chunks, so the tail of every read is held
 * back until a newline completes it. `[DONE]` ends the stream; a frame that
 * will not parse is dropped rather than thrown, because the next read is
 * usually the other half of it.
 */
export async function* sseFrames(res: Response): AsyncGenerator<Record<string, unknown>> {
  if (!res.body) throw new Error("Chutes returned no stream.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload || payload === "[DONE]") continue;
        try {
          yield JSON.parse(payload);
        } catch {
          /* partial JSON across chunk boundaries — the next read completes it */
        }
      }
    }
  } finally {
    reader.cancel().catch(() => {});
  }
}

/** Qwen thinks out loud unless told not to; take the JSON object regardless. */
export function parseJson(raw: string) {
  const cleaned = raw.replace(/<think>[\s\S]*?<\/think>/g, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start === -1 || end <= start) throw new Error("The orchestrator did not return JSON.");
  return JSON.parse(cleaned.slice(start, end + 1));
}
