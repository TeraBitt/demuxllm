#!/usr/bin/env node
/**
 * Compares src/lib/dashboard/models.ts against the live Chutes catalog.
 *
 * It reports rather than rewrites. Prices and context windows are mechanical
 * and can be trusted from the API; `tier`, `goodAt` and the orchestrator choice
 * are judgements, and a script that regenerated the file would quietly throw
 * them away. So this prints what drifted and leaves the edit to a person.
 *
 *   node scripts/sync-catalog.mjs          # report drift, exit 1 if any
 *   node scripts/sync-catalog.mjs --json   # the live catalog, for piping
 */

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ENDPOINT = "https://llm.chutes.ai/v1/models";
const SOURCE = join(dirname(fileURLToPath(import.meta.url)), "../src/lib/dashboard/models.ts");

const live = await fetch(ENDPOINT)
  .then((r) => {
    if (!r.ok) throw new Error(`${ENDPOINT} returned ${r.status}`);
    return r.json();
  })
  .catch((err) => {
    console.error(`Could not read the Chutes catalog: ${err.message}`);
    process.exit(2);
  });

/** Chutes serves images, audio and OCR too. Only chat models can be routed to. */
const chat = live.data.filter((m) => m.pricing?.prompt !== undefined);

if (process.argv.includes("--json")) {
  console.log(JSON.stringify(chat, null, 2));
  process.exit(0);
}

const source = await readFile(SOURCE, "utf8");

/** Reads the shipped catalog without importing TypeScript into node. */
function shipped() {
  const out = new Map();
  for (const block of source.split(/\n  \{\n/).slice(1)) {
    const get = (key, pattern) => block.match(new RegExp(`${key}: (${pattern})`))?.[1];
    const id = get("id", `"[^"]+"`)?.slice(1, -1);
    if (!id) continue;
    out.set(id, {
      inPer1M: Number(get("inPer1M", "[\\d._]+")),
      outPer1M: Number(get("outPer1M", "[\\d._]+")),
      ctx: get("ctx", "null|[\\d_]+") === "null" ? null : Number(get("ctx", "[\\d_]+").replaceAll("_", "")),
    });
  }
  return out;
}

const ours = shipped();
const problems = [];

for (const m of chat) {
  const mine = ours.get(m.id);
  if (!mine) {
    problems.push(`NEW      ${m.id} — $${m.pricing.prompt}/$${m.pricing.completion}, ${m.context_length ?? "?"} ctx`);
    continue;
  }
  const round = (n) => Math.round(n * 1e4) / 1e4;
  if (round(mine.inPer1M) !== round(m.pricing.prompt) || round(mine.outPer1M) !== round(m.pricing.completion)) {
    problems.push(
      `PRICE    ${m.id} — catalog $${mine.inPer1M}/$${mine.outPer1M}, live $${m.pricing.prompt}/$${m.pricing.completion}`,
    );
  }
  const liveCtx = m.context_length ?? null;
  if (mine.ctx !== liveCtx) {
    problems.push(`CONTEXT  ${m.id} — catalog ${mine.ctx}, live ${liveCtx}`);
  }
}

for (const id of ours.keys()) {
  if (!chat.some((m) => m.id === id)) problems.push(`GONE     ${id} — no longer served`);
}

if (!problems.length) {
  console.log(`In sync: ${chat.length} chat models, prices and context windows match.`);
  process.exit(0);
}

console.log(`${problems.length} difference${problems.length === 1 ? "" : "s"} against ${ENDPOINT}:\n`);
for (const p of problems) console.log(`  ${p}`);
console.log(`\nEdit ${SOURCE.replace(process.cwd() + "/", "")} by hand — tier and goodAt are judgements.`);
process.exit(1);
