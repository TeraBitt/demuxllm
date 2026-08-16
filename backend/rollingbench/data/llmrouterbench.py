"""LLMRouterBench adapter.

LLMRouterBench ships one JSON file per (task, model) run, each holding aggregate
figures and a `records` array with one entry per item: the prompt, the grade, the
realised cost, and — unlike RouterBench — *measured* prompt and completion token
counts. That last column is why this corpus is worth the parsing: the token target
the router fits is observed here rather than estimated from response length.

The archive is never extracted. It expands to well beyond the free space on a
normal machine (the `raw_output` and `prediction` fields dominate it and nothing
downstream reads them), so `build_cache` streams members straight out of the
compressed tarball, keeps the four numeric columns plus a truncated prompt, and
writes a compact `.npz`. One pass, a few hundred MB of peak RSS, ~60 MB on disk.

Items are keyed by a hash of (dataset, prompt text), not by the `index` field.
Indices restart per split and the same task appears under several split names
(`test_1000` and `test_3000` for mmlupro, `subset_500` and `test` for hle), so
index-alignment would silently glue different questions together. Content
alignment cannot: two rows meet only if the model was asked the same thing.
"""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
from pathlib import Path

import numpy as np

from .labelmatrix import LabelMatrix

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARBALL = ROOT / "data" / "raw" / "llmrouterbench-release.tar.gz"
DEFAULT_CACHE = ROOT / "data" / "cache" / "llmrouterbench.npz"

# The feature map reads the first 400 words / 600 characters, so storing more than
# this buys nothing and swe-bench prompts alone would otherwise run to hundreds of MB.
_PROMPT_CHARS = 4000

_WS = re.compile(r"\s+")

# Coarse buckets, the same role `domain` plays in the RouterBench adapter: the
# granularity a router can realistically specialise on.
_DOMAIN_OF: dict[str, str] = {
    "aime": "math",
    "livemathbench": "math",
    "math500": "math",
    "mathbench": "math",
    "arenahard_math": "math",
    "livecodebench": "code",
    "humaneval": "code",
    "mbpp": "code",
    "swe-bench": "code",
    "arenahard_coding": "code",
    "gpqa": "science",
    "mmlupro": "knowledge",
    "arcc": "knowledge",
    "hle": "knowledge",
    "simpleqa": "knowledge",
    "medqa": "medicine",
    "finqa": "business",
    "bbh": "reasoning",
    "kandk": "reasoning",
    "korbench": "reasoning",
    "arc-agi": "reasoning",
    "winogrande": "commonsense",
    "emorynlp": "dialogue",
    "meld": "dialogue",
    "tau2": "agentic",
    "arenahard": "openended",
    "arenahard_creative_writing": "openended",
}


def _item_key(dataset: str, prompt: str) -> str:
    """Stable content address for an item.

    Whitespace is normalised before hashing because the same question arrives with
    different wrapping depending on which harness wrote the file.
    """
    norm = _WS.sub(" ", str(prompt)).strip()
    h = hashlib.sha1(f"{dataset}\x00{norm}".encode("utf-8", "replace")).hexdigest()
    return h[:20]


def build_cache(
    tarball: str | Path = DEFAULT_TARBALL,
    out: str | Path = DEFAULT_CACHE,
    *,
    verbose: bool = True,
) -> Path:
    """Stream the archive once and write the compact cache.

    Returns the cache path. Safe to re-run; it overwrites.
    """
    tarball, out = Path(tarball), Path(out)
    if not tarball.exists():
        raise FileNotFoundError(
            f"{tarball} not found. Run: python scripts/fetch_data.py --corpus llmrouterbench"
        )

    # (item_key) -> row index, and parallel metadata lists.
    row_of: dict[str, int] = {}
    prompts: list[str] = []
    tasks: list[str] = []

    col_of: dict[str, int] = {}
    model_names: list[str] = []

    # Coordinate lists; densified at the end. A dict-of-dicts would be 3x the RSS.
    ri: list[int] = []
    ci: list[int] = []
    v_score: list[float] = []
    v_cost: list[float] = []
    v_tin: list[float] = []
    v_tout: list[float] = []

    # Wall-clock is published per run, never per record, so it is kept at that
    # granularity rather than divided out here. `experiments/latency.py` fits a
    # per-model (overhead, throughput) from these and derives per-item latency from
    # the *measured* token counts; doing the division at read time would throw away
    # the fact that a run's total is one observation of two parameters, not n.
    timings: list[dict] = []

    n_files = 0
    n_dupe = 0
    with tarfile.open(tarball, "r:gz") as tf:
        for member in tf:
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            try:
                doc = json.loads(fh.read().decode("utf-8", "replace"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            n_files += 1

            dataset = str(doc.get("dataset_name") or "unknown")
            model = str(doc.get("model_name") or "unknown")
            if model not in col_of:
                col_of[model] = len(model_names)
                model_names.append(model)
            j = col_of[model]

            t_taken = doc.get("time_taken")
            if isinstance(t_taken, (int, float)) and t_taken > 0:
                timings.append({
                    "model": model, "dataset": dataset,
                    "time_taken_s": float(t_taken),
                    "counts": int(doc.get("counts") or 0),
                    "completion_tokens": int(doc.get("completion_tokens") or 0),
                    "prompt_tokens": int(doc.get("prompt_tokens") or 0),
                })

            seen_here: set[int] = set()
            for rec in doc.get("records") or []:
                score = rec.get("score")
                if not isinstance(score, (int, float)):
                    continue
                text = rec.get("origin_query")
                if text is None:
                    text = rec.get("prompt")
                if text is None:
                    continue
                key = _item_key(dataset, text)
                i = row_of.get(key)
                if i is None:
                    i = len(prompts)
                    row_of[key] = i
                    prompts.append(str(text)[:_PROMPT_CHARS])
                    tasks.append(dataset)
                if i in seen_here:
                    # Same model, same question, twice in one file (or across the
                    # two splits of one task). Keep the first; count it.
                    n_dupe += 1
                    continue
                seen_here.add(i)

                ri.append(i)
                ci.append(j)
                v_score.append(float(score))
                c = rec.get("cost")
                v_cost.append(float(c) if isinstance(c, (int, float)) else np.nan)
                ti = rec.get("prompt_tokens")
                v_tin.append(float(ti) if isinstance(ti, (int, float)) else np.nan)
                to = rec.get("completion_tokens")
                v_tout.append(float(to) if isinstance(to, (int, float)) else np.nan)

            del doc

    n, k = len(prompts), len(model_names)
    if verbose:
        print(f"[llmrouterbench] {n_files} files → {n:,} items x {k} models, "
              f"{len(ri):,} graded cells ({n_dupe:,} duplicate cells dropped)")

    ri_a = np.asarray(ri, dtype=np.int32)
    ci_a = np.asarray(ci, dtype=np.int16)

    quality = np.zeros((n, k), dtype=np.float32)
    cost = np.zeros((n, k), dtype=np.float32)
    tokens_in = np.zeros((n, k), dtype=np.float32)
    tokens_out = np.zeros((n, k), dtype=np.float32)
    observed = np.zeros((n, k), dtype=bool)

    quality[ri_a, ci_a] = np.asarray(v_score, dtype=np.float32)
    cost[ri_a, ci_a] = np.nan_to_num(np.asarray(v_cost, dtype=np.float32))
    tokens_in[ri_a, ci_a] = np.nan_to_num(np.asarray(v_tin, dtype=np.float32))
    tokens_out[ri_a, ci_a] = np.nan_to_num(np.asarray(v_tout, dtype=np.float32))
    observed[ri_a, ci_a] = True

    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        model_ids=np.array(model_names, dtype=object),
        item_keys=np.array(list(row_of.keys()), dtype=object),
        prompts=np.array(prompts, dtype=object),
        task=np.array(tasks, dtype=object),
        quality=quality,
        cost=cost,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        observed=observed,
        timings=np.array(json.dumps(timings), dtype=object),
        allow_pickle=True,
    )
    if verbose:
        print(f"[llmrouterbench] wrote {out} ({out.stat().st_size / 1e6:.1f} MB); "
              f"{len(timings)} run timings kept")
    return out


def timings(cache: str | Path = DEFAULT_CACHE) -> list[dict]:
    """Per-run wall-clock, as published: one row per (model, task) run.

    Not per item — the corpus never records that. See `experiments/latency.py` for
    what can honestly be derived from it and what cannot.
    """
    z = np.load(Path(cache), allow_pickle=True)
    if "timings" not in z:
        raise KeyError("cache predates timing capture — rerun build_chutes_matrix.py")
    return json.loads(str(z["timings"]))


def load(
    cache: str | Path = DEFAULT_CACHE,
    *,
    models: list[str] | None = None,
    tasks: list[str] | None = None,
    dense_only: bool = False,
) -> LabelMatrix:
    """Read the cache into a `LabelMatrix`.

    Parameters
    ----------
    models : keep only these columns, in this order.
    tasks : keep only items from these datasets.
    dense_only : keep only items every retained model actually answered. This is
        what the headline pool uses — a cost/quality frontier is only interpretable
        when every policy had the same menu on every item.
    """
    cache = Path(cache)
    if not cache.exists():
        raise FileNotFoundError(
            f"{cache} not found. Run: python scripts/build_chutes_matrix.py"
        )
    z = np.load(cache, allow_pickle=True)

    all_models = [str(m) for m in z["model_ids"]]
    quality = z["quality"].astype(np.float64)
    cost = z["cost"].astype(np.float64)
    tokens_in = z["tokens_in"].astype(np.float64)
    tokens_out = z["tokens_out"].astype(np.float64)
    observed = z["observed"]
    task = np.array([str(t) for t in z["task"]])
    prompts = np.array([str(p) for p in z["prompts"]])
    item_keys = np.array([str(k) for k in z["item_keys"]])

    if models is not None:
        missing = [m for m in models if m not in all_models]
        if missing:
            raise ValueError(f"cache has no such models: {missing}")
        cols = [all_models.index(m) for m in models]
        quality, cost = quality[:, cols], cost[:, cols]
        tokens_in, tokens_out = tokens_in[:, cols], tokens_out[:, cols]
        observed = observed[:, cols]
        all_models = list(models)

    keep = np.ones(len(prompts), dtype=bool)
    if tasks is not None:
        keep &= np.isin(task, list(tasks))
    if dense_only:
        keep &= observed.all(axis=1)
    idx = np.flatnonzero(keep)

    notes = [
        "quality = LLMRouterBench per-item score as published (task-specific grader)",
        "cost = LLMRouterBench realised per-call USD for the *measured* model",
        "tokens_in / tokens_out = MEASURED token counts, not derived from text length",
        f"items keyed by sha1(dataset, normalised prompt); {len(idx):,} kept",
    ]
    if dense_only:
        notes.append("dense_only=True — every retained model answered every retained item")

    return LabelMatrix(
        item_ids=item_keys[idx],
        model_ids=list(all_models),
        quality=quality[idx],
        cost=cost[idx],
        observed=observed[idx],
        tokens_out=tokens_out[idx],
        prompts=prompts[idx],
        task=task[idx],
        domain=np.array([_DOMAIN_OF.get(t, "other") for t in task[idx]]),
        source="LLMRouterBench (bench-release)",
        notes=notes,
    )


def tokens_in_for(cache: str | Path = DEFAULT_CACHE,
                  models: list[str] | None = None) -> np.ndarray:
    """Measured prompt-token counts, which `LabelMatrix` has no field for.

    Pricing a Chutes model needs both halves of the bill, and the input half is a
    property of the item rather than the model, so it is fetched separately rather
    than bolted onto the matrix.
    """
    z = np.load(Path(cache), allow_pickle=True)
    all_models = [str(m) for m in z["model_ids"]]
    tin = z["tokens_in"].astype(np.float64)
    if models is not None:
        tin = tin[:, [all_models.index(m) for m in models]]
    return tin
