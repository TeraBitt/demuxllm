"use client";

/**
 * Tools the model can actually call, executed in this browser.
 *
 * The constraint that shaped this list: the demo holds one Chutes key and no
 * server, so a tool may not need a credential of its own and may not need an
 * origin that refuses cross-origin reads. What is left is better than it sounds
 * — four of the five answer questions about DemuxLLM itself, from real data, so
 * the assistant can be asked what a request would cost or where the month's
 * money went and reply with arithmetic instead of a guess.
 *
 * Every tool returns a `summary` for the model and `data` for the panel that
 * renders the call. The model never sees the panel and the panel never re-runs
 * the tool, so the two cannot disagree.
 */

import {
  BASELINE_ID,
  CATALOG,
  type CatalogModel,
  type Tier,
  baselineCost,
  byId,
  costOf,
  formatCtx,
} from "./models";
import { readRuns } from "./history";
import { blendedPrice } from "./prefs";

export type ToolResult = {
  ok: boolean;
  /** What goes back to the model. Compact, factual, no markup. */
  summary: string;
  /** What the inline panel renders. Never sent to the model. */
  data?: unknown;
};

export type ToolSpec = {
  name: string;
  /** Shown in the call panel: "Searched the model pool". */
  label: string;
  /** Present-tense, shown while the call is in flight. */
  running: string;
  description: string;
  parameters: Record<string, unknown>;
  run: (args: Record<string, unknown>) => Promise<ToolResult>;
};

/* ------------------------------------------------------------------ utils -- */

const num = (v: unknown, fallback: number) =>
  typeof v === "number" && Number.isFinite(v) ? v : fallback;

const str = (v: unknown) => (typeof v === "string" ? v : "");

const list = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];

const money = (n: number) => `$${n < 0.01 ? n.toFixed(6) : n.toFixed(4)}`;

const describe = (m: CatalogModel) =>
  `${m.label} (${m.id}) — ${m.tier} tier, $${m.inPer1M}/$${m.outPer1M} per 1M in/out, ${formatCtx(
    m.ctx,
  )} context${m.vision ? ", vision" : ""}${m.video ? ", video" : ""}${
    m.structured ? ", tools+JSON" : ", no tools"
  }${m.thinks ? ", reasoning" : ""}. Good at: ${m.goodAt}.`;

/* ---------------------------------------------------------- search_models -- */

const searchModels: ToolSpec = {
  name: "search_models",
  label: "Searched the model pool",
  running: "Searching the model pool",
  description:
    "Search the DemuxLLM routing pool — the models this product can actually route to — by capability, tier, price or context window. Use this whenever the user asks which model to use, what a model costs, or what is available. Never answer from memory.",
  parameters: {
    type: "object",
    properties: {
      needs: {
        type: "array",
        items: { type: "string", enum: ["vision", "video", "tools", "thinking"] },
        description: "Capabilities the model must have.",
      },
      tier: {
        type: "string",
        enum: ["open", "mid", "frontier"],
        description: "Restrict to one price tier.",
      },
      maxPricePer1M: {
        type: "number",
        description: "Highest acceptable output price in USD per 1M tokens.",
      },
      minContext: { type: "number", description: "Smallest acceptable context window in tokens." },
      sort: {
        type: "string",
        enum: ["cheapest", "largest-context", "most-capable"],
        description: "Ordering. Defaults to cheapest.",
      },
      limit: { type: "number", description: "How many to return. Defaults to 6." },
    },
    required: [],
    additionalProperties: false,
  },
  async run(args) {
    const needs = list(args.needs);
    const tier = str(args.tier) as Tier | "";
    const maxPrice = num(args.maxPricePer1M, Infinity);
    const minCtx = num(args.minContext, 0);
    const limit = Math.max(1, Math.min(20, num(args.limit, 6)));

    let out = CATALOG.filter((m) => {
      if (tier && m.tier !== tier) return false;
      if (m.outPer1M > maxPrice) return false;
      if (minCtx && (m.ctx ?? 0) < minCtx) return false;
      if (needs.includes("vision") && !m.vision) return false;
      if (needs.includes("video") && !m.video) return false;
      if (needs.includes("tools") && !m.structured) return false;
      if (needs.includes("thinking") && !m.thinks) return false;
      return true;
    });

    // Tier is the only ordinal claim the catalog makes about capability, so
    // "most-capable" reads it rather than inferring capability from price.
    const TIER_RANK: Record<Tier, number> = { open: 0, mid: 1, frontier: 2 };
    const sort = str(args.sort) || "cheapest";
    if (sort === "largest-context") out = [...out].sort((a, b) => (b.ctx ?? 0) - (a.ctx ?? 0));
    else if (sort === "most-capable")
      out = [...out].sort(
        (a, b) => TIER_RANK[b.tier] - TIER_RANK[a.tier] || blendedPrice(b) - blendedPrice(a),
      );
    else out = [...out].sort((a, b) => blendedPrice(a) - blendedPrice(b));

    const hits = out.slice(0, limit);

    return {
      ok: true,
      summary: hits.length
        ? `${out.length} of ${CATALOG.length} models match. Closest ${hits.length}:\n${hits
            .map((m) => `- ${describe(m)}`)
            .join("\n")}`
        : `No model in the pool of ${CATALOG.length} matches those constraints. Say so plainly and suggest which constraint to relax.`,
      data: {
        matched: out.length,
        total: CATALOG.length,
        models: hits.map((m) => ({
          id: m.id,
          label: m.label,
          tier: m.tier,
          inPer1M: m.inPer1M,
          outPer1M: m.outPer1M,
          ctx: m.ctx,
          goodAt: m.goodAt,
        })),
      },
    };
  },
};

/* ---------------------------------------------------------- estimate_cost -- */

const estimateCost: ToolSpec = {
  name: "estimate_cost",
  label: "Priced the work",
  running: "Pricing the work",
  description:
    "Price a workload against the DemuxLLM pool. Given token counts (and optionally a request volume), returns what it costs on a named model, on the cheapest model, and on the frontier model — plus what routing saves. Use for any 'what would this cost' question.",
  parameters: {
    type: "object",
    properties: {
      inputTokens: { type: "number", description: "Input tokens per request." },
      outputTokens: { type: "number", description: "Output tokens per request." },
      requests: { type: "number", description: "How many requests. Defaults to 1." },
      modelId: {
        type: "string",
        description: "Exact model id to price. Omit to compare cheapest against frontier.",
      },
    },
    required: ["inputTokens", "outputTokens"],
    additionalProperties: false,
  },
  async run(args) {
    const inTok = Math.max(0, num(args.inputTokens, 0));
    const outTok = Math.max(0, num(args.outputTokens, 0));
    const requests = Math.max(1, Math.round(num(args.requests, 1)));

    const cheapest = [...CATALOG].sort((a, b) => blendedPrice(a) - blendedPrice(b))[0];
    const named = byId(str(args.modelId)) ?? null;
    const frontier = byId(BASELINE_ID)!;

    const per = (m: CatalogModel) => costOf(m, inTok, outTok);
    const rows = [
      named ? { model: named, label: named.label, usd: per(named) } : null,
      { model: cheapest, label: `${cheapest.label} (cheapest)`, usd: per(cheapest) },
      { model: frontier, label: `${frontier.label} (frontier)`, usd: baselineCost(inTok, outTok) },
    ].filter((r): r is { model: CatalogModel; label: string; usd: number } => r !== null);

    const reference = named ?? cheapest;
    const saved = baselineCost(inTok, outTok) - per(reference);
    const savedPct = baselineCost(inTok, outTok) > 0
      ? Math.round((saved / baselineCost(inTok, outTok)) * 100)
      : 0;

    return {
      ok: true,
      summary: [
        `${inTok} in / ${outTok} out tokens × ${requests} request${requests === 1 ? "" : "s"}:`,
        ...rows.map(
          (r) => `- ${r.label}: ${money(r.usd)} each, ${money(r.usd * requests)} total`,
        ),
        `Routing to ${reference.label} instead of ${frontier.label} saves ${money(
          saved * requests,
        )} (${savedPct}%).`,
      ].join("\n"),
      data: {
        inTok,
        outTok,
        requests,
        savedPct,
        rows: rows.map((r) => ({
          label: r.label,
          tier: r.model.tier,
          each: r.usd,
          total: r.usd * requests,
        })),
      },
    };
  },
};

/* ------------------------------------------------------------ usage_stats -- */

const usageStats: ToolSpec = {
  name: "usage_stats",
  label: "Read the run history",
  running: "Reading the run history",
  description:
    "Read this workspace's real routing history on this device: spend, savings, latency, and the split by model, category or work-scope. Use for any question about what has been spent, which models get picked, or what the workspace has been asking about.",
  parameters: {
    type: "object",
    properties: {
      days: { type: "number", description: "Look back this many days. Defaults to 30." },
      groupBy: {
        type: "string",
        enum: ["model", "category", "scope", "tier"],
        description: "How to break the spend down. Defaults to model.",
      },
    },
    required: [],
    additionalProperties: false,
  },
  async run(args) {
    const days = Math.max(1, Math.min(365, num(args.days, 30)));
    const since = Date.now() - days * 86_400_000;
    const runs = readRuns().filter((r) => r.at >= since);

    if (!runs.length) {
      return {
        ok: true,
        summary: `No routed requests in the last ${days} days on this device. Say so rather than inventing figures.`,
        data: { runs: 0, days },
      };
    }

    const cost = runs.reduce((n, r) => n + r.costUsd, 0);
    const baseline = runs.reduce((n, r) => n + r.baselineUsd, 0);
    const avgMs = runs.reduce((n, r) => n + r.ms, 0) / runs.length;

    const key = str(args.groupBy) || "model";
    const pick = (r: (typeof runs)[number]) =>
      key === "category" ? r.category : key === "scope" ? r.scope : key === "tier" ? r.tier : r.modelLabel;

    const groups = new Map<string, { runs: number; cost: number }>();
    for (const r of runs) {
      const k = pick(r);
      const cur = groups.get(k) ?? { runs: 0, cost: 0 };
      groups.set(k, { runs: cur.runs + 1, cost: cur.cost + r.costUsd });
    }
    const rows = [...groups.entries()]
      .map(([label, v]) => ({ label, ...v }))
      .sort((a, b) => b.cost - a.cost);

    return {
      ok: true,
      summary: [
        `${runs.length} routed requests in the last ${days} days.`,
        `Spent ${money(cost)}; the same traffic on the frontier model alone would have cost ${money(
          baseline,
        )} — saved ${money(baseline - cost)} (${Math.round(
          baseline > 0 ? ((baseline - cost) / baseline) * 100 : 0,
        )}%).`,
        `Median-ish latency ${(avgMs / 1000).toFixed(1)}s.`,
        `By ${key}:`,
        ...rows.map((r) => `- ${r.label}: ${r.runs} requests, ${money(r.cost)}`),
      ].join("\n"),
      data: {
        runs: runs.length,
        days,
        cost,
        baseline,
        saved: baseline - cost,
        groupBy: key,
        rows: rows.slice(0, 8),
      },
    };
  },
};

/* --------------------------------------------------------- run_javascript -- */

/**
 * A worker, a three-second fuse, and no handle on the page.
 *
 * The worker is built from a blob so it inherits no scope from here, and it is
 * terminated on timeout rather than asked to stop — a `while (true)` cannot be
 * asked. `postMessage` is the only way anything gets back out, so a script that
 * hangs costs three seconds and nothing else.
 */
const WORKER_SRC = `
const fmt = (v) => {
  if (typeof v === "string") return v;
  if (v === undefined) return "undefined";
  try { return JSON.stringify(v, null, 2) ?? String(v); } catch { return String(v); }
};
self.onmessage = (e) => {
  const logs = [];
  const cap = (...a) => { if (logs.length < 200) logs.push(a.map(fmt).join(" ")); };
  const sandboxConsole = { log: cap, info: cap, warn: cap, error: cap, debug: cap };
  try {
    const fn = new Function("console", '"use strict";' + e.data);
    const value = fn(sandboxConsole);
    self.postMessage({ ok: true, logs, value: value === undefined ? null : fmt(value) });
  } catch (err) {
    self.postMessage({ ok: false, logs, error: String(err && err.message ? err.message : err) });
  }
};
`;

const TIMEOUT_MS = 3000;

function evalInWorker(code: string) {
  return new Promise<{ ok: boolean; logs: string[]; value?: string | null; error?: string }>(
    (resolve) => {
      let url: string;
      let worker: Worker;
      try {
        url = URL.createObjectURL(new Blob([WORKER_SRC], { type: "text/javascript" }));
        worker = new Worker(url);
      } catch {
        resolve({ ok: false, logs: [], error: "This browser blocked the sandbox worker." });
        return;
      }

      const done = (r: { ok: boolean; logs: string[]; value?: string | null; error?: string }) => {
        clearTimeout(fuse);
        worker.terminate();
        URL.revokeObjectURL(url);
        resolve(r);
      };

      const fuse = setTimeout(
        () => done({ ok: false, logs: [], error: `Timed out after ${TIMEOUT_MS}ms.` }),
        TIMEOUT_MS,
      );

      worker.onmessage = (e) => done(e.data);
      worker.onerror = (e) => done({ ok: false, logs: [], error: e.message || "Worker error." });
      worker.postMessage(code);
    },
  );
}

const runJavascript: ToolSpec = {
  name: "run_javascript",
  label: "Ran JavaScript",
  running: "Running JavaScript",
  description:
    "Execute JavaScript in a sandboxed worker and get the result. Use it for arithmetic, dates, string and data manipulation, sorting, parsing, simulation — anything where a computed answer beats a guessed one. The code is a function body: `return` the value you want, or console.log it. No network, no DOM, 3 second limit.",
  parameters: {
    type: "object",
    properties: {
      code: {
        type: "string",
        description: "JavaScript function body. End with a `return` statement.",
      },
    },
    required: ["code"],
    additionalProperties: false,
  },
  async run(args) {
    const code = str(args.code).trim();
    if (!code) return { ok: false, summary: "No code was supplied.", data: { code: "" } };

    const r = await evalInWorker(code);
    const parts: string[] = [];
    if (r.logs.length) parts.push(`Output:\n${r.logs.join("\n")}`);
    if (r.ok && r.value != null) parts.push(`Returned:\n${r.value}`);
    if (!r.ok) parts.push(`Error: ${r.error}`);
    if (r.ok && !parts.length) parts.push("Ran without error and returned nothing.");

    return {
      ok: r.ok,
      summary: parts.join("\n\n").slice(0, 4000),
      data: { code, logs: r.logs, value: r.value ?? null, error: r.error ?? null },
    };
  },
};

/* ----------------------------------------------------------- current_time -- */

const currentTime: ToolSpec = {
  name: "current_time",
  label: "Checked the clock",
  running: "Checking the clock",
  description:
    "The current date and time. Call this before any answer that depends on today's date, an elapsed duration, or a deadline.",
  parameters: {
    type: "object",
    properties: {
      timeZone: {
        type: "string",
        description: "IANA zone, e.g. Asia/Kathmandu. Defaults to the user's own.",
      },
    },
    required: [],
    additionalProperties: false,
  },
  async run(args) {
    const now = new Date();
    const zone = str(args.timeZone) || Intl.DateTimeFormat().resolvedOptions().timeZone;
    let formatted: string;
    try {
      formatted = now.toLocaleString("en-GB", { timeZone: zone, dateStyle: "full", timeStyle: "short" });
    } catch {
      formatted = now.toISOString();
    }
    return {
      ok: true,
      summary: `${formatted} (${zone}). ISO: ${now.toISOString()}.`,
      data: { formatted, zone, iso: now.toISOString() },
    };
  },
};

/* --------------------------------------------------------------- registry -- */

export const TOOLS: ToolSpec[] = [
  searchModels,
  estimateCost,
  usageStats,
  runJavascript,
  currentTime,
];

export const TOOL_BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));

/** The OpenAI-shaped declarations sent with the request. */
export function toolSchemas(enabled: string[]) {
  return TOOLS.filter((t) => enabled.includes(t.name)).map((t) => ({
    type: "function" as const,
    function: { name: t.name, description: t.description, parameters: t.parameters },
  }));
}

export async function executeTool(name: string, rawArgs: string): Promise<ToolResult> {
  const spec = TOOL_BY_NAME.get(name);
  if (!spec) {
    return { ok: false, summary: `There is no tool called "${name}". Do not call it again.` };
  }

  let args: Record<string, unknown> = {};
  if (rawArgs.trim()) {
    try {
      const parsed = JSON.parse(rawArgs);
      if (parsed && typeof parsed === "object") args = parsed as Record<string, unknown>;
    } catch {
      return {
        ok: false,
        summary: "The arguments were not valid JSON. Call the tool again with valid JSON.",
        data: { rawArgs },
      };
    }
  }

  try {
    return await spec.run(args);
  } catch (err) {
    return {
      ok: false,
      summary: `The tool failed: ${err instanceof Error ? err.message : String(err)}`,
    };
  }
}
