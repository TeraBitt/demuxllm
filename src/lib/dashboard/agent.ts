"use client";

/**
 * The answer loop: stream, call tools, stream again, until the model stops
 * asking for tools or runs out of rounds.
 *
 * Three things arrive on one stream and have to be told apart. Ordinary tokens
 * are the answer. Reasoning arrives either as its own `reasoning_content` delta
 * (the OpenAI-shaped field vLLM emits) or inline inside `<think>` tags (what a
 * Qwen chat template produces when nothing strips them) — both are handled,
 * because which one you get depends on the model and not on anything we send.
 * Tool calls arrive as fragments indexed by position, with the name in one frame
 * and the arguments spread across a dozen more.
 */

import type { CatalogModel } from "./models";
import { type Prefs, thinkingFor, toolsFor } from "./prefs";
import {
  type Usage,
  EMPTY_USAGE,
  addUsage,
  chutes,
  readUsage,
  sseFrames,
} from "./chutes";
import { type ToolResult, executeTool, toolSchemas } from "./tools";

export type ChatMessage = {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: { id: string; type: "function"; function: { name: string; arguments: string } }[];
  tool_call_id?: string;
};

export type AgentEvent =
  | { kind: "reasoning"; text: string }
  | { kind: "text"; text: string }
  | { kind: "tool_start"; id: string; name: string; args: string }
  | { kind: "tool_end"; id: string; result: ToolResult; ms: number }
  | { kind: "round"; n: number };

/* --------------------------------------------------------- think splitter -- */

const OPEN = "<think>";
const CLOSE = "</think>";
/** Longest tag minus one: enough to never split a tag across two emissions. */
const HOLD = CLOSE.length - 1;

/**
 * Routes a token stream into two channels on `<think>` boundaries. The tail of
 * every push is held back by seven characters so a tag straddling two deltas is
 * still recognised as a tag rather than leaked into the answer as text.
 */
function thinkSplitter(onReason: (t: string) => void, onText: (t: string) => void) {
  let buf = "";
  let inside = false;

  const drain = (final: boolean) => {
    for (;;) {
      const tag = inside ? CLOSE : OPEN;
      const at = buf.indexOf(tag);
      if (at !== -1) {
        const before = buf.slice(0, at);
        if (before) (inside ? onReason : onText)(before);
        buf = buf.slice(at + tag.length);
        inside = !inside;
        continue;
      }
      const keep = final ? 0 : Math.min(HOLD, buf.length);
      const out = buf.slice(0, buf.length - keep);
      if (out) (inside ? onReason : onText)(out);
      buf = buf.slice(buf.length - keep);
      return;
    }
  };

  return {
    push(chunk: string) {
      buf += chunk;
      drain(false);
    },
    end() {
      drain(true);
    },
  };
}

/* ------------------------------------------------------------ system text -- */

const STYLE_RULES: Record<Prefs["style"], string> = {
  concise:
    "Answer in as few words as the question allows. Lead with the answer. No preamble, no restating the question, no summary at the end.",
  balanced:
    "Lead with the answer, then give only the reasoning a reader would actually want. No preamble, no restating the question.",
  thorough:
    "Give the answer, then the reasoning behind it, the alternatives you rejected and the edge cases that would change it. Still no preamble.",
};

export function systemPrompt(prefs: Prefs, model: CatalogModel, tools: string[]) {
  const parts = [
    "You are DemuxLLM's assistant. A router picked you for this specific request out of a pool of models, on price against a quality bar.",
    STYLE_RULES[prefs.style],
    "Write in markdown. Use fenced code blocks for code, with the language tagged.",
  ];

  if (tools.length) {
    parts.push(
      "You have tools. Call them rather than guessing: they are the only way you can reach real figures, this workspace's own usage, or a computed result. Never state a price, a total or a date you did not get from a tool. After a tool returns, answer the question — do not narrate the call.",
    );
  }

  if (prefs.orgContext.trim()) {
    parts.push(
      `The user works at ${prefs.orgName.trim() || "an organisation"} described as: "${prefs.orgContext.trim()}". Use that for context only; do not mention it unless it is relevant.`,
    );
  }

  if (prefs.systemPrompt.trim()) {
    parts.push(`Standing instructions from the user, which take priority:\n${prefs.systemPrompt.trim()}`);
  }

  parts.push(`You are running as ${model.label}.`);

  return parts.join("\n\n");
}

/* ------------------------------------------------------------------- loop -- */

type Accumulated = {
  text: string;
  reasoning: string;
  calls: { id: string; name: string; args: string }[];
  usage: Usage;
  finish: string | null;
};

async function streamOnce(opts: {
  apiKey: string;
  model: CatalogModel;
  messages: ChatMessage[];
  prefs: Prefs;
  tools: string[];
  thinking: boolean;
  signal?: AbortSignal;
  onEvent: (e: AgentEvent) => void;
}): Promise<Accumulated> {
  const { apiKey, model, messages, prefs, tools, thinking, signal, onEvent } = opts;

  const res = await chutes(
    apiKey,
    {
      model: model.id,
      messages,
      stream: true,
      stream_options: { include_usage: true },
      temperature: prefs.temperature,
      ...(tools.length ? { tools: toolSchemas(tools), tool_choice: "auto" } : {}),
    },
    { thinking, signal },
  );

  let text = "";
  let reasoning = "";
  let usage: Usage | null = null;
  let finish: string | null = null;
  const parts = new Map<number, { id: string; name: string; args: string }>();

  const split = thinkSplitter(
    (t) => {
      reasoning += t;
      onEvent({ kind: "reasoning", text: t });
    },
    (t) => {
      text += t;
      onEvent({ kind: "text", text: t });
    },
  );

  for await (const frame of sseFrames(res)) {
    const f = frame as {
      usage?: unknown;
      choices?: {
        finish_reason?: string | null;
        delta?: {
          content?: string | null;
          reasoning_content?: string | null;
          reasoning?: string | null;
          tool_calls?: {
            index?: number;
            id?: string;
            function?: { name?: string; arguments?: string };
          }[];
        };
      }[];
    };

    // The usage frame is the last one and carries no choices.
    if (f.usage) usage = readUsage(f.usage, EMPTY_USAGE);

    const choice = f.choices?.[0];
    if (!choice) continue;
    if (choice.finish_reason) finish = choice.finish_reason;

    const delta = choice.delta;
    if (!delta) continue;

    // Reasoning on its own field never passes through the tag splitter — it is
    // already separated, and running it through would strip nothing and risk
    // holding the last seven characters back forever.
    const thought = delta.reasoning_content ?? delta.reasoning;
    if (thought) {
      reasoning += thought;
      onEvent({ kind: "reasoning", text: thought });
    }

    if (delta.content) split.push(delta.content);

    for (const tc of delta.tool_calls ?? []) {
      const idx = tc.index ?? 0;
      const cur = parts.get(idx) ?? { id: "", name: "", args: "" };
      if (tc.id) cur.id = tc.id;
      if (tc.function?.name) cur.name += tc.function.name;
      if (tc.function?.arguments) cur.args += tc.function.arguments;
      parts.set(idx, cur);
    }
  }

  split.end();

  const calls = [...parts.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([i, c]) => ({ ...c, id: c.id || `call-${i}` }))
    .filter((c) => c.name);

  return {
    text,
    reasoning,
    calls,
    finish,
    usage:
      usage ?? {
        inTok: Math.ceil(JSON.stringify(messages).length / 4),
        outTok: Math.ceil((text.length + reasoning.length) / 4),
      },
  };
}

export type AgentRun = {
  text: string;
  reasoning: string;
  usage: Usage;
  /** How many times tools were called and answered. */
  toolRounds: number;
  /** True when the round budget ran out with the model still asking for tools. */
  truncated: boolean;
};

export async function runAgent(opts: {
  apiKey: string;
  model: CatalogModel;
  /** Prior conversation, oldest first. The current question is the last entry. */
  messages: ChatMessage[];
  prefs: Prefs;
  bar: number;
  signal?: AbortSignal;
  onEvent: (e: AgentEvent) => void;
}): Promise<AgentRun> {
  const { apiKey, model, prefs, bar, signal } = opts;

  // Counted so a retry can tell a request that was refused outright from one
  // that died halfway through — replaying the second would print the first
  // half of the answer twice.
  let emitted = 0;
  const onEvent = (e: AgentEvent) => {
    emitted += 1;
    opts.onEvent(e);
  };

  const tools = toolsFor(prefs, model);
  const thinking = thinkingFor(prefs, model, bar);
  const messages: ChatMessage[] = [
    { role: "system", content: systemPrompt(prefs, model, tools) },
    ...opts.messages,
  ];

  let usage = EMPTY_USAGE;
  let text = "";
  let reasoning = "";
  let toolRounds = 0;

  let live = tools;
  const maxRounds = tools.length ? Math.max(0, Math.min(8, prefs.maxToolRounds)) : 0;

  for (let round = 0; ; round++) {
    if (round > 0) onEvent({ kind: "round", n: round });

    let step: Accumulated;
    try {
      step = await streamOnce({
        apiKey,
        model,
        messages,
        prefs,
        tools: live,
        thinking,
        signal,
        onEvent,
      });
    } catch (err) {
      // The catalog says which models can hold a tool schema, but the endpoint
      // has the last word. Rather than fail the turn on a model that turns out
      // not to accept them, drop the tools and answer once without.
      if (
        round === 0 &&
        emitted === 0 &&
        live.length &&
        !(err instanceof DOMException && err.name === "AbortError")
      ) {
        live = [];
        step = await streamOnce({
          apiKey,
          model,
          messages,
          prefs,
          tools: live,
          thinking,
          signal,
          onEvent,
        });
      } else {
        throw err;
      }
    }

    usage = addUsage(usage, step.usage);
    // Only the final pass is the answer. Text a model emits alongside a tool
    // call is a plan, not a reply, and keeping it would prepend "Let me check…"
    // to every answer that used a tool.
    if (step.calls.length === 0) {
      text += step.text;
      reasoning += step.reasoning;
      return { text, reasoning, usage, toolRounds, truncated: false };
    }
    reasoning += step.reasoning;

    if (round >= maxRounds) {
      return { text: text || step.text, reasoning, usage, toolRounds, truncated: true };
    }

    messages.push({
      role: "assistant",
      content: step.text || null,
      tool_calls: step.calls.map((c) => ({
        id: c.id,
        type: "function" as const,
        function: { name: c.name, arguments: c.args || "{}" },
      })),
    });

    for (const call of step.calls) {
      if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

      onEvent({ kind: "tool_start", id: call.id, name: call.name, args: call.args });
      const startedAt = performance.now();
      const result = await executeTool(call.name, call.args);
      onEvent({
        kind: "tool_end",
        id: call.id,
        result,
        ms: Math.round(performance.now() - startedAt),
      });

      messages.push({
        role: "tool",
        tool_call_id: call.id,
        content: result.summary.slice(0, 6000),
      });
    }

    toolRounds += 1;
  }
}
