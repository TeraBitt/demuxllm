"""Select the items to grade on the real endpoint, and pull their full prompts.

Three things have to line up for a graded run to be worth paying for, and this
script is where all three are established.

**Same items as the proxy baseline.** The selection is drawn from the *dense core* —
the items every one of the 13 stand-in columns answered — so a real measurement can
be laid directly beside the proxy's prediction for the same question. A run on fresh
items would tell us how the models score; a run on these items tells us how wrong the
proxy was, which is the number the whole repository is blocked on.

**Only tasks a grader can settle without a judge.** mmlupro and gpqa end in
`Answer: $LETTER`; aime and livemathbench end in `\\boxed{}`. Both are exact-match
against a `ground_truth` the corpus ships. The arenahard family is excluded on
purpose: its `ground_truth` is literally `None` and its scores come from a pairwise
LLM judge, so regrading it means reproducing a judge protocol and any drift there
lands in the numbers as if it were a model difference. livecodebench is excluded
because grading it means executing untrusted code.

**Full prompts, not the cache.** `data/cache` truncates prompts to 4,000 characters
because nothing downstream reads more than the feature map needs. Re-serving a
truncated prompt would ask a different question than the corpus asked, so prompts are
read back out of the extracted release.

Writes `artifacts/grading/items.json`.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rollingbench.catalog import proxy_ids  # noqa: E402

RAW = ROOT / "data" / "raw" / "llmrouterbench"
CACHE = ROOT / "data" / "cache" / "llmrouterbench.npz"
OUT = ROOT / "artifacts" / "grading" / "items.json"

# The four tasks whose grader is a string comparison. See the module docstring for
# why the other five in the dense core are not here.
EXACT_MATCH_TASKS = ("mmlupro", "gpqa", "aime", "livemathbench")

_WS = re.compile(r"\s+")


def item_key(dataset: str, prompt: str) -> str:
    """Identical to `rollingbench.data.llmrouterbench._item_key`.

    Duplicated rather than imported because the two must agree byte for byte, and a
    copy that is checked against the cache (see `--verify`) is safer than an import
    that silently follows a refactor.
    """
    norm = _WS.sub(" ", str(prompt)).strip()
    return hashlib.sha1(f"{dataset}\x00{norm}".encode("utf-8", "replace")).hexdigest()[:20]


def dense_core_keys() -> set[str]:
    """Item keys every one of the 13 proxy columns answered."""
    z = np.load(CACHE, allow_pickle=True)
    models = [str(m) for m in z["model_ids"]]
    cols = [models.index(p) for p in proxy_ids()]
    dense = z["observed"][:, cols].all(axis=1)
    return {str(k) for k in z["item_keys"][dense]}


def harvest(tasks: tuple[str, ...]) -> dict[str, dict]:
    """Full prompt and ground truth for every item of `tasks` in the release.

    Two details have to match `build_cache` exactly or the keys address nothing:
    the corpus keys on **`origin_query`** (the bare question), falling back to
    `prompt`, and it keys on **`dataset_name`** from the document rather than the
    directory the file sits in. What we re-serve is the other field — `prompt`, the
    formatted question carrying the answer-format instruction the grader depends on.

    The same question appears once per model that answered it; the first sighting
    wins, which is also what the cache does.
    """
    found: dict[str, dict] = {}
    for ds in tasks:
        d = RAW / ds
        if not d.is_dir():
            raise SystemExit(f"missing extracted task dir: {d}")
        for path in sorted(d.rglob("*.json")):
            try:
                doc = json.loads(path.read_text())
            except Exception:
                continue
            dataset = str(doc.get("dataset_name") or "unknown")
            for rec in doc.get("records") or []:
                prompt, gt = rec.get("prompt"), rec.get("ground_truth")
                if not prompt or gt is None or str(gt) == "None":
                    continue
                keyed_on = rec.get("origin_query")
                if keyed_on is None:
                    keyed_on = prompt
                k = item_key(dataset, keyed_on)
                if k not in found:
                    found[k] = {
                        "key": k, "task": dataset, "prompt": str(prompt),
                        "ground_truth": str(gt),
                    }
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", default=list(EXACT_MATCH_TASKS))
    ap.add_argument("--verify", action="store_true",
                    help="check the harvested keys really are cache keys")
    args = ap.parse_args()

    core = dense_core_keys()
    print(f"dense core (all 13 proxy columns answered): {len(core):,} items")

    harvested = harvest(tuple(args.tasks))
    print(f"harvested with a usable ground truth:       {len(harvested):,} items")

    sel = {k: v for k, v in harvested.items() if k in core}
    print(f"intersection — gradeable AND in dense core: {len(sel):,} items\n")

    by_task = collections.Counter(v["task"] for v in sel.values())
    for t, n in by_task.most_common():
        print(f"  {t:16s} {n:5d}")

    if args.verify:
        z = np.load(CACHE, allow_pickle=True)
        cache_keys = {str(k) for k in z["item_keys"]}
        missing = set(sel) - cache_keys
        assert not missing, f"{len(missing)} harvested keys are not cache keys"
        print("\nverify: every selected key resolves in the cache ✓")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Sorted by key so the ordering is deterministic across machines; the sampler
    # downstream seeds off this order.
    items = [sel[k] for k in sorted(sel)]
    OUT.write_text(json.dumps({
        "n_items": len(items),
        "tasks": dict(by_task),
        "source": "LLMRouterBench release, dense core, exact-match tasks only",
        "items": items,
    }, indent=1))
    print(f"\nwrote {OUT.relative_to(ROOT)}  ({len(items):,} items)")


if __name__ == "__main__":
    main()
