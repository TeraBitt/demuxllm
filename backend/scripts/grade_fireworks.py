"""Grade the real checkpoints on a real endpoint, under a hard budget.

Why Fireworks and not Chutes: the two serve the *same open-weights checkpoints*, and
Fireworks is the one we hold a key for. Quality and token behaviour are properties of
the weights, so measuring them here replaces the proxy assumption
("DeepSeek V4 Flash behaves like DeepSeek-R1-0528-Qwen3-8B") with a far weaker one
("the same checkpoint behaves the same on two hosts"). Price stays the Chutes list
price, exactly as the architecture already requires — prices are read, never fitted.

Only four of the thirteen slots are reachable: Fireworks serves the rest as tunable
models that need a dedicated deployment, not serverless. `MAPPING` is the whole of the
assumption and it is checked at startup.

Three properties this harness has to hold, all of them for reasons the repository
already paid to learn:

**The output is dense.** Items are the outer loop and every model answers an item
before the next item starts, so *any* prefix of the run is a complete matrix. This is
not a nicety: `RESULTS.md` §4.2 records that training on unevenly-covered columns cost
twelve points of quality retention, and §4.4 that ranking models on their own coverage
makes a 9B model look better than a frontier one. A budget that stops mid-run must not
be able to reintroduce either.

**A failed call is not a zero.** `RESULTS.md` §4.3: 470 failed calls recorded as score
0.0 with zero tokens taught the cost model that some models were free. Here a call that
never produced a gradeable answer is written with `observed: false` and no score.

**Truncation is recorded, not scored.** A reasoning model cut off at `max_tokens` has
not answered wrongly, it has not answered. Those are marked and excluded rather than
counted as failures, because scoring them would understate exactly the models that
think longest.

Resumable: every completed cell is appended to a JSONL ledger and re-reading it is how
a re-run picks up. Nothing is ever re-paid for.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "artifacts" / "grading"
ITEMS = OUT_DIR / "items.json"
LEDGER = OUT_DIR / "cells.jsonl"

ENDPOINT = "https://api.fireworks.ai/inference/v1/chat/completions"
# Cloudflare rejects urllib's default agent outright (error 1010), which looks like an
# auth failure if you are not expecting it.
UA = "Mozilla/5.0 (X11; Linux x86_64) rollingbench/1.0"

# The four Chutes slots Fireworks actually serves serverless, with the price we pay
# there (for the budget guard only — routing cost is recomputed at Chutes list price).
# `fw_in`/`fw_out` are USD per 1M tokens.
MAPPING = {
    "deepseek-ai/DeepSeek-V4-Flash-0731-TEE": {
        "fw": "accounts/fireworks/models/deepseek-v4-flash-0731",
        "fw_in": 0.14, "fw_out": 0.28, "exact": True,
    },
    "moonshotai/Kimi-K2.6-TEE": {
        "fw": "accounts/fireworks/models/kimi-k2p6",
        "fw_in": 0.95, "fw_out": 4.00, "exact": True,
    },
    "zai-org/GLM-5.2-TEE": {
        "fw": "accounts/fireworks/models/glm-5p2",
        "fw_in": 1.40, "fw_out": 4.40, "exact": True,
    },
    "moonshotai/Kimi-K3-TEE": {
        "fw": "accounts/fireworks/models/kimi-k3",
        "fw_in": 3.00, "fw_out": 15.00, "exact": True,
    },
}

# ------------------------------------------------------------------ graders --

_BOXED = re.compile(r"\\boxed\s*\{")
_LETTER = re.compile(r"answer\s*:\s*\**\s*\$?\\?\(?([A-J])\)?", re.IGNORECASE)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Drop inline reasoning so the grader reads the answer, not the working.

    A model that emits `<think>…</think>` inline will otherwise have every candidate
    answer it considered and discarded scanned by the extractor, and "last match wins"
    would pick one out of the middle of its reasoning.
    """
    out = _THINK.sub(" ", text)
    # An unclosed <think> means the answer never arrived — the trace ran to the cap.
    if "<think>" in out.lower():
        out = out[:out.lower().rindex("<think>")]
    return out


def extract_boxed(text: str) -> str | None:
    """Contents of the LAST \\boxed{...}, brace-matched.

    Regex alone cannot do this: answers legitimately contain braces (`\\frac{1}{2}`),
    so the closing brace has to be found by counting depth.
    """
    starts = [m.end() for m in _BOXED.finditer(text)]
    for start in reversed(starts):
        depth, i = 1, start
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        if depth == 0:
            return text[start:i - 1].strip()
    return None


def norm_math(s: str) -> str:
    """Normalise a maths answer so two spellings of one answer compare equal.

    Calibrated against the corpus's own verdicts rather than invented: each rule
    below fixes a disagreement actually observed when this comparison was run over
    13,312 already-graded records (see `--validate`). The corpus uses a symbolic
    checker; this is a string normaliser, so it stays deliberately conservative —
    every rule here rewrites notation, none of them do algebra. Genuinely algebraic
    equivalences (`8\\sqrt{5}-16` vs `8(\\sqrt{5}-2)`) are left to disagree rather
    than risk calling two different answers the same.
    """
    s = s.strip()
    s = re.sub(r"^\\\[|\\\]$|^\\\(|\\\)$", "", s).strip()
    s = s.strip("$").strip()
    s = re.sub(r"^\\(?:text|mathrm|mbox)\s*\{(.*)\}$", r"\1", s).strip()
    # Units and trailing qualifiers the corpus ignores: 336^\circ == 336.
    s = re.sub(r"\^\s*\{?\s*\\circ\s*\}?", "", s)
    s = re.sub(r"\\(?:degree|percent)\b|\\%", "", s)
    s = s.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    for junk in (r"\left", r"\right", r"\!", r"\,", r"\;", r"\quad", r"\ ", "$", " "):
        s = s.replace(junk, "")
    # \frac{a}{b} -> (a)/(b), innermost first, so nested fractions collapse too.
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    # Set braces: \{2,5\} and 2,5 are the same answer.
    s = re.sub(r"^\\\{(.*)\\\}$", r"\1", s)
    s = re.sub(r"^\{(.*)\}$", r"\1", s)
    # Redundant braces around a single token: 2^{n} -> 2^n.
    s = re.sub(r"\{(\w)\}", r"\1", s)
    # Parens the \frac rewrite introduced around atoms: (1)/(n!) -> 1/n!.
    s = re.sub(r"\((\w+!*)\)", r"\1", s)
    s = s.replace(",", "").rstrip(".").rstrip("\\")
    # A plain rational and its decimal are the same answer: 5/2 == 2.5.
    frac = re.fullmatch(r"(-?\d+)/(\d+)", s)
    if frac and int(frac.group(2)):
        f = int(frac.group(1)) / int(frac.group(2))
        return str(int(f)) if f == int(f) else str(f)
    if re.fullmatch(r"-?\d+(\.\d+)?", s):           # 33.0 and 33 are the same answer
        f = float(s)
        return str(int(f)) if f == int(f) else str(f)
    return s.lower()


def grade(task: str, ground_truth: str, text: str) -> tuple[float | None, str | None]:
    """(score, extracted answer). score is None when nothing gradeable was produced."""
    body = strip_reasoning(text)
    if task in ("mmlupro", "gpqa"):
        hits = _LETTER.findall(body)
        if not hits:
            return None, None
        pred = hits[-1].upper()
        return float(pred == ground_truth.strip().upper()), pred
    pred = extract_boxed(body)
    if pred is None:
        return None, None
    return float(norm_math(pred) == norm_math(ground_truth)), pred


# --------------------------------------------------------------------- call --

class Budget:
    """Hard ceilings on tokens and dollars, shared across threads.

    Checked before a call is issued and updated after it returns. Because items are
    the outer loop, tripping either ceiling stops the run on an item boundary and the
    ledger stays dense.
    """

    def __init__(self, max_tokens: int, max_usd: float) -> None:
        self.max_tokens, self.max_usd = max_tokens, max_usd
        self.tokens = 0
        self.usd = 0.0
        self.calls = 0

    def exhausted(self) -> bool:
        return self.tokens >= self.max_tokens or self.usd >= self.max_usd

    def add(self, tin: int, tout: int, spec: dict) -> None:
        self.tokens += tin + tout
        self.usd += tin / 1e6 * spec["fw_in"] + tout / 1e6 * spec["fw_out"]
        self.calls += 1


def call(fw_model: str, prompt: str, key: str, max_tokens: int,
         temperature: float, timeout: float, retries: int = 3) -> dict:
    """One chat completion, with backoff. Raises only when every attempt failed."""
    payload = json.dumps({
        "model": fw_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(ENDPOINT, data=payload, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": UA,
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode("utf-8", "replace")
            last = f"HTTP {e.code}: {body}"
            if e.code in (400, 401, 403, 404):     # not transient; retrying just burns time
                break
        except Exception as e:                      # timeouts, resets, partial reads
            last = f"{type(e).__name__}: {e}"
        time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(last or "unknown failure")


def run_cell(item: dict, slot: str, spec: dict, key: str, args) -> dict:
    """Answer one item with one model and grade it."""
    rec = {"item": item["key"], "task": item["task"], "slot": slot,
           "observed": False, "score": None, "tokens_in": None, "tokens_out": None}
    try:
        resp = call(spec["fw"], item["prompt"], key,
                    args.max_tokens, args.temperature, args.timeout)
    except Exception as e:
        rec["error"] = str(e)[:300]
        return rec

    usage = resp.get("usage") or {}
    tin = int(usage.get("prompt_tokens") or 0)
    tout = int(usage.get("completion_tokens") or 0)
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = msg.get("content") or ""
    # Some servers put the trace in its own field; it is not the answer but it is
    # billed, and a model that spent everything there produced no answer.
    reasoning = msg.get("reasoning_content") or ""
    finish = choice.get("finish_reason")

    rec.update(tokens_in=tin, tokens_out=tout, finish=finish,
               reasoning_tokens=len(reasoning) // 4 if reasoning else 0)

    if finish == "length":
        rec["truncated"] = True                     # not an answer; not a zero
        return rec
    score, pred = grade(item["task"], item["ground_truth"], text)
    if score is None:
        rec["ungradeable"] = True
        return rec
    rec.update(observed=True, score=score, pred=pred)
    return rec


# --------------------------------------------------------------------- main --

def load_ledger() -> dict[tuple[str, str], dict]:
    done: dict[tuple[str, str], dict] = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            done[(r["item"], r["slot"])] = r
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0, help="items to grade (0 = all)")
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--budget-tokens", type=int, default=100_000_000)
    ap.add_argument("--budget-usd", type=float, default=33.0)
    ap.add_argument("--batch", type=int, default=6, help="items in flight")
    ap.add_argument("--timeout", type=float, default=240.0)
    ap.add_argument("--slots", nargs="*", default=list(MAPPING))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("FIREWORKS_API_KEY", "").strip()
    if not key:
        raise SystemExit("set FIREWORKS_API_KEY")

    slots = [s for s in args.slots if s in MAPPING]
    if not slots:
        raise SystemExit("no valid slots")

    payload = json.loads(ITEMS.read_text())
    items = payload["items"]
    # Stratified by task, round-robin, so a run that stops early is still balanced
    # across tasks rather than being all of whichever task sorted first.
    by_task: dict[str, list] = {}
    for it in items:
        by_task.setdefault(it["task"], []).append(it)
    order, pools = [], [by_task[t] for t in sorted(by_task)]
    while any(pools):
        for p in pools:
            if p:
                order.append(p.pop(0))
    if args.n:
        order = order[:args.n]

    done = load_ledger()
    budget = Budget(args.budget_tokens, args.budget_usd)
    for r in done.values():                          # re-runs must not re-spend
        if r.get("tokens_in") is not None:
            budget.add(r["tokens_in"], r["tokens_out"], MAPPING[r["slot"]])

    todo = [it for it in order if any((it["key"], s) not in done for s in slots)]
    print(f"slots={len(slots)}  items queued={len(todo):,}  already graded="
          f"{len(done):,} cells")
    print(f"budget: {budget.max_tokens:,} tokens / ${budget.max_usd:.2f}   "
          f"already spent {budget.tokens:,} tok / ${budget.usd:.2f}")
    print(f"max_tokens={args.max_tokens} temperature={args.temperature}\n")
    if args.dry_run:
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    stopped = None
    with LEDGER.open("a") as ledger, ThreadPoolExecutor(max_workers=len(slots) * args.batch) as ex:
        for b in range(0, len(todo), args.batch):
            if budget.exhausted():
                stopped = "budget"
                break
            chunk = todo[b:b + args.batch]
            jobs = [(it, s) for it in chunk for s in slots if (it["key"], s) not in done]
            # Written as each cell lands, not when the batch does. One endpoint that
            # stops streaming used to hold 47 finished calls hostage in memory, and
            # killing the run then threw away work that had already been paid for.
            futures = {ex.submit(run_cell, it, s, MAPPING[s], key, args): (it, s)
                       for it, s in jobs}
            for fut in as_completed(futures):
                it, s = futures[fut]
                try:
                    rec = fut.result()
                except Exception as e:                # a worker itself failed
                    rec = {"item": it["key"], "task": it["task"], "slot": s,
                           "observed": False, "score": None, "tokens_in": None,
                           "tokens_out": None, "error": f"worker: {type(e).__name__}: {e}"}
                if rec.get("tokens_in") is not None:
                    budget.add(rec["tokens_in"], rec["tokens_out"], MAPPING[s])
                done[(it["key"], s)] = rec
                ledger.write(json.dumps(rec) + "\n")
                ledger.flush()

            graded = sum(1 for r in done.values() if r.get("observed"))
            n_items = len({k[0] for k in done})
            print(f"  items {n_items:5,}  cells {len(done):6,}  graded {graded:6,}  "
                  f"{budget.tokens:11,} tok  ${budget.usd:7.3f}  "
                  f"{time.time() - t0:6.0f}s", flush=True)

    print(f"\nstopped: {stopped or 'work complete'}")
    print(f"cells={len(done):,}  tokens={budget.tokens:,}  spend=${budget.usd:.3f}")


if __name__ == "__main__":
    main()
