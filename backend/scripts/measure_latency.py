#!/usr/bin/env python
"""Latency in seconds — the harness for the one §6 row that only needs a timed run.

    python scripts/measure_latency.py plan                   # what it would do, free
    FIREWORKS_API_KEY=... python scripts/measure_latency.py run
    python scripts/measure_latency.py analyse                # ledger -> seconds

`RESULTS.md` §4c says per-request latency is not measurable from the corpus, and it is
right: `time_taken` is published per *run* of a few hundred items, the runs were
executed concurrently, and fitting `time = counts·overhead + tokens/throughput` gives
26 of 38 models a decode rate above 500 tok/s. That check lives in
`latency.throughput_is_credible` and it fails, which is why the whole section is
quoted in output tokens rather than seconds.

Tokens are the right *routing* signal — within a model, length is what decides how
long a request takes — but they are not an answer to "what is your p99". Converting
one to the other needs two numbers per slot that no corpus contains: time to first
token, and single-stream decode rate. This measures both.

What it does differently from the corpus, on purpose:

**Concurrency 1 by default.** Measuring under parallelism is precisely the mistake
that makes the corpus's wall-clock unusable. The default run issues one request at a
time and the number it produces is a per-request latency.

**Load is a separate, labelled arm.** Queueing and admission delay are most of a real
p99, so `--load 1,2,4,8` reruns the same probe at rising concurrency and reports each
level separately. That is a different quantity from the single-stream one and is
never averaged into it.

**Prefill and decode are separated.** Each slot is probed across prompt-length
buckets, so time-to-first-token can be regressed on input tokens rather than folded
into a single tok/s that silently depends on the prompt mix.

**A dry run cannot be mistaken for a measurement.** `--dry-run` synthesises a ledger
so the whole path — including `analyse` — is exercisable with no key and no spend, but
every synthetic record carries `synthetic: true`, and `analyse` refuses to write the
artifact from synthetic records unless it is told to, and stamps the result when it
does.

Cost. The probe is deliberately small: `--items 12 --repeats 3` over four slots is 144
calls, and at the graded run's measured ~$0.14 per item across four slots that is
roughly $5 — the cheapest remaining row on the §6 list.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.grade_fireworks import ENDPOINT, MAPPING, UA  # noqa: E402

OUT = ROOT / "artifacts" / "latency"
LEDGER = OUT / "timings.jsonl"
ITEMS = ROOT / "artifacts" / "grading" / "items.json"

#: Prompt-length buckets, in characters. Time to first token is dominated by prefill,
#: which is linear in input length, so probing one bucket would report a TTFT that is
#: really a statement about the prompt mix that happened to be sampled.
BUCKETS = ((0, 1500), (1500, 4000), (4000, 10**9))


# --------------------------------------------------------------- the probe --
def stream_once(fw_model: str, prompt: str, key: str, *, max_tokens: int,
                temperature: float, timeout: float) -> dict:
    """One streamed completion, timed. Returns the timings, never raises for content.

    Streaming is not an optimisation here, it is the measurement: a non-streamed call
    returns one blob and cannot separate the time spent waiting for the first token
    from the time spent producing the rest. Those two have different causes — prefill
    and queueing versus decode — and mixing them is how you get a p99 that moves for
    reasons you cannot attribute.
    """
    payload = json.dumps({
        "model": fw_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=payload, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "Accept": "text/event-stream", "User-Agent": UA,
    })

    t0 = time.perf_counter()
    ttft = None
    chunks = 0
    usage = {}
    finish = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                try:
                    ev = json.loads(body)
                except json.JSONDecodeError:
                    continue
                if ev.get("usage"):
                    usage = ev["usage"]
                ch = (ev.get("choices") or [{}])[0]
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
                delta = ch.get("delta") or {}
                if delta.get("content") or delta.get("reasoning_content"):
                    chunks += 1
                    if ttft is None:
                        ttft = time.perf_counter() - t0
    except Exception as e:                                    # transport, not content
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}",
                "wall_s": time.perf_counter() - t0}

    wall = time.perf_counter() - t0
    tout = int(usage.get("completion_tokens") or 0)
    # Decode rate over the *decode phase* only. Including prefill would make a long
    # prompt look like a slow model.
    decode_s = max(wall - (ttft or wall), 1e-9)
    return {
        "ok": True,
        "wall_s": wall,
        "ttft_s": ttft,
        "decode_s": decode_s,
        "tokens_in": int(usage.get("prompt_tokens") or 0),
        "tokens_out": tout,
        "chunks": chunks,
        "decode_tok_s": (tout - 1) / decode_s if tout > 1 else None,
        "finish": finish,
    }


def synth_once(fw_model: str, prompt: str, _key, *, max_tokens: int, **_kw) -> dict:
    """A stand-in for `stream_once` with no network, for exercising the pipeline.

    The numbers are invented from a declared model — TTFT linear in prompt length,
    decode at a fixed per-slot rate, both with a little jitter — so that `analyse` has
    something shaped like a ledger to read. They are not measurements of anything and
    every record they produce is stamped `synthetic`.
    """
    import random

    rate = 40.0 + (hash(fw_model) % 60)                      # 40–100 tok/s, per slot
    tin = max(len(prompt) // 4, 1)
    ttft = 0.25 + tin / 9000.0 + random.random() * 0.15
    tout = min(max_tokens, int(200 + random.random() * 2400))
    decode_s = tout / rate * (0.9 + 0.2 * random.random())
    return {
        "ok": True, "synthetic": True,
        "wall_s": ttft + decode_s, "ttft_s": ttft, "decode_s": decode_s,
        "tokens_in": tin, "tokens_out": tout, "chunks": tout,
        "decode_tok_s": (tout - 1) / decode_s, "finish": "stop",
    }


# ---------------------------------------------------------------- the plan --
def pick_probes(n_items: int, seed: int = 0) -> list[dict]:
    """Items spread across the prompt-length buckets, from the graded set."""
    import random

    if not ITEMS.exists():
        raise FileNotFoundError(
            f"{ITEMS} not found. Run: python scripts/build_grading_set.py --verify")
    items = json.loads(ITEMS.read_text())["items"]
    rng = random.Random(seed)
    per = max(1, n_items // len(BUCKETS))
    out = []
    for lo, hi in BUCKETS:
        pool = [it for it in items if lo <= len(it["prompt"]) < hi]
        if not pool:
            continue
        out.extend(rng.sample(pool, min(per, len(pool))))
    return out


def ledger_key(rec: dict) -> tuple:
    return (rec["slot"], rec["item"], rec["repeat"], rec["concurrency"])


def load_ledger() -> set:
    done = set()
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if line.strip():
                done.add(ledger_key(json.loads(line)))
    return done


def cmd_plan(args) -> int:
    probes = pick_probes(args.items, args.seed)
    levels = [int(x) for x in args.load.split(",")] if args.load else [args.concurrency]
    calls = len(probes) * args.repeats * len(args.slots) * len(levels)
    est = sum(
        (len(p["prompt"]) / 4 / 1e6) * MAPPING[s]["fw_in"]
        + (args.max_tokens * 0.35 / 1e6) * MAPPING[s]["fw_out"]
        for p in probes for s in args.slots) * args.repeats * len(levels)
    print(f"probe items      {len(probes)} across {len(BUCKETS)} length buckets")
    print(f"slots            {len(args.slots)}")
    print(f"repeats          {args.repeats}")
    print(f"concurrency      {levels}")
    print(f"calls            {calls}")
    print(f"rough cost       ${est:.2f} (assumes 35% of max_tokens is produced)")
    print(f"already in ledger {len(load_ledger())}")
    for lo, hi in BUCKETS:
        k = sum(1 for p in probes if lo <= len(p["prompt"]) < hi)
        print(f"  bucket {lo:>5}-{hi if hi < 10**8 else 'inf':>5} chars: {k} items")
    return 0


def cmd_run(args) -> int:
    key = os.environ.get("FIREWORKS_API_KEY", "").strip()
    if not key and not args.dry_run:
        print("FIREWORKS_API_KEY is not set. Use --dry-run to exercise the pipeline "
              "with synthetic timings, or `plan` to see what a real run would cost.",
              file=sys.stderr)
        return 2
    shoot = synth_once if args.dry_run else stream_once

    probes = pick_probes(args.items, args.seed)
    levels = [int(x) for x in args.load.split(",")] if args.load else [args.concurrency]
    done = load_ledger()
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0

    with LEDGER.open("a") as fh:
        for conc in levels:
            for slot in args.slots:
                spec = MAPPING[slot]
                # One slot at a time even inside a load level: mixing models under
                # concurrency measures the endpoint's scheduler, not the model.
                jobs = [(p, rep) for p in probes for rep in range(args.repeats)
                        if (slot, p["key"], rep, conc) not in done]
                if not jobs:
                    continue
                print(f"[c={conc}] {slot}: {len(jobs)} calls")

                def one(job):
                    p, rep = job
                    r = shoot(spec["fw"], p["prompt"], key,
                              max_tokens=args.max_tokens,
                              temperature=args.temperature, timeout=args.timeout)
                    return {"slot": slot, "item": p["key"], "task": p["task"],
                            "repeat": rep, "concurrency": conc,
                            "prompt_chars": len(p["prompt"]),
                            "synthetic": bool(args.dry_run), **r}

                if conc == 1:
                    results = [one(j) for j in jobs]
                else:
                    with ThreadPoolExecutor(max_workers=conc) as ex:
                        results = list(ex.map(one, jobs))
                for rec in results:
                    fh.write(json.dumps(rec) + "\n")
                    written += 1
                fh.flush()

    print(f"wrote {written} records to {LEDGER.relative_to(ROOT)}")
    return 0


# --------------------------------------------------------------- analysis --
def _pct(v: list[float], p: float) -> float:
    if not v:
        return float("nan")
    s = sorted(v)
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def fit_slot(records: list[dict]) -> dict:
    """Per slot: TTFT against prompt length, and single-stream decode rate.

    TTFT is fitted rather than averaged because prefill is linear in input tokens, so
    a mean TTFT is only valid for the prompt mix it was measured on and the router
    needs to predict latency for prompts it has not seen.
    """
    ok = [r for r in records if r.get("ok") and r.get("ttft_s") and r.get("tokens_out")]
    if len(ok) < 2:
        return {"n": len(ok), "fitted": False}

    x = [r["tokens_in"] for r in ok]
    y = [r["ttft_s"] for r in ok]
    n = len(ok)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    slope = sxy / sxx if sxx > 0 else 0.0
    intercept = my - slope * mx
    ss_tot = sum((b - my) ** 2 for b in y)
    ss_res = sum((b - (intercept + slope * a)) ** 2 for a, b in zip(x, y))

    rates = [r["decode_tok_s"] for r in ok if r.get("decode_tok_s")]
    return {
        "n": n,
        "fitted": True,
        "ttft_intercept_s": intercept,
        "ttft_per_input_token_s": slope,
        "ttft_r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0,
        "ttft_p50_s": _pct(y, 50), "ttft_p95_s": _pct(y, 95),
        "decode_tok_s_p50": statistics.median(rates) if rates else None,
        "decode_tok_s_p05": _pct(rates, 5), "decode_tok_s_p95": _pct(rates, 95),
        "wall_p50_s": _pct([r["wall_s"] for r in ok], 50),
        "wall_p95_s": _pct([r["wall_s"] for r in ok], 95),
        "wall_p99_s": _pct([r["wall_s"] for r in ok], 99),
    }


def credible(fits: dict) -> dict:
    """The same gate `latency.throughput_is_credible` applies to the corpus.

    Applied to our own numbers too, and for the same reason: a measurement that
    reports a small model decoding at 1,200 tok/s single-stream has measured
    something other than what it thinks. Failing our own gate is the outcome that
    would tell us the probe was itself run under hidden parallelism.
    """
    from rollingbench.experiments.latency import PLAUSIBLE_TOK_S

    rates = [f["decode_tok_s_p50"] for f in fits.values()
             if f.get("fitted") and f.get("decode_tok_s_p50")]
    bad = [r for r in rates if r > PLAUSIBLE_TOK_S]
    return {
        "threshold_tok_s": PLAUSIBLE_TOK_S,
        "slots_fitted": len(rates),
        "implausible": len(bad),
        "credible": len(rates) > 0 and not bad,
        "reading": (
            f"{len(rates)} slots timed; {len(bad)} decode above {PLAUSIBLE_TOK_S} tok/s. "
            + ("These are per-request rates."
               if not bad else
               "At least one rate is not physically a single-stream rate — the probe "
               "was not isolated and these numbers must not be quoted as latency.")),
    }


def cmd_analyse(args) -> int:
    if not LEDGER.exists():
        print(f"no ledger at {LEDGER}. Run `measure_latency.py run` first "
              f"(or `run --dry-run` to exercise this path).", file=sys.stderr)
        return 2
    recs = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    synthetic = [r for r in recs if r.get("synthetic")]
    if synthetic and not args.allow_synthetic:
        print(f"{len(synthetic)} of {len(recs)} ledger records are synthetic "
              f"(--dry-run). Refusing to write a latency artifact from invented "
              f"numbers. Pass --allow-synthetic to write it anyway; the artifact "
              f"will be stamped so it cannot be quoted by accident.", file=sys.stderr)
        return 3

    single = [r for r in recs if r.get("concurrency") == 1]
    by_slot: dict[str, list[dict]] = {}
    for r in single:
        by_slot.setdefault(r["slot"], []).append(r)
    fits = {s: fit_slot(v) for s, v in by_slot.items()}

    load: dict[str, dict] = {}
    for r in recs:
        c = str(r.get("concurrency"))
        if c == "1" or not r.get("ok"):
            continue
        load.setdefault(c, {"walls": [], "ttfts": []})
        load[c]["walls"].append(r["wall_s"])
        if r.get("ttft_s"):
            load[c]["ttfts"].append(r["ttft_s"])
    load_rows = [{
        "concurrency": int(c),
        "n": len(v["walls"]),
        "wall_p50_s": _pct(v["walls"], 50),
        "wall_p95_s": _pct(v["walls"], 95),
        "wall_p99_s": _pct(v["walls"], 99),
        "ttft_p95_s": _pct(v["ttfts"], 95),
    } for c, v in sorted(load.items(), key=lambda kv: int(kv[0]))]

    payload = {
        "synthetic": bool(synthetic),
        "n_records": len(recs),
        "n_single_stream": len(single),
        "per_slot": fits,
        "credibility": credible(fits),
        "under_load": load_rows,
        "what_this_replaces": (
            "RESULTS.md §4c quotes routed latency in output tokens because the "
            "corpus's wall-clock is concurrent. With a per-slot TTFT and decode rate "
            "measured at concurrency 1, the same token distribution converts to "
            "seconds: latency = ttft(prompt tokens) + output_tokens / decode_rate."),
    }
    if synthetic:
        payload["WARNING"] = (
            "SYNTHETIC. Produced from --dry-run records, which are invented by "
            "`synth_once` to exercise this code path. Not a measurement of anything.")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ("measured_SYNTHETIC.json" if synthetic else "measured.json")
    path.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["credibility"], indent=2))
    for s, f in fits.items():
        if f.get("fitted"):
            print(f"{s:45s} ttft p50 {f['ttft_p50_s']:.2f}s  decode "
                  f"{f['decode_tok_s_p50']:.0f} tok/s  wall p95 {f['wall_p95_s']:.1f}s")
    print(f"→ {path.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--items", type=int, default=12)
        p.add_argument("--repeats", type=int, default=3)
        p.add_argument("--slots", nargs="*", default=list(MAPPING))
        p.add_argument("--concurrency", type=int, default=1)
        p.add_argument("--load", default="", help="e.g. 1,2,4,8 — a labelled load arm")
        p.add_argument("--max-tokens", type=int, default=4096)
        p.add_argument("--temperature", type=float, default=0.6)
        p.add_argument("--timeout", type=float, default=240.0)
        p.add_argument("--seed", type=int, default=0)
        if name == "run":
            p.add_argument("--dry-run", action="store_true")
    pa = sub.add_parser("analyse")
    pa.add_argument("--allow-synthetic", action="store_true")
    args = ap.parse_args()
    return {"plan": cmd_plan, "run": cmd_run, "analyse": cmd_analyse}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
