#!/usr/bin/env python
"""Download the public label-matrix corpora. Run once; everything else is offline.

    python scripts/fetch_data.py                       # primary corpus only
    python scripts/fetch_data.py --corpus all          # + secondary corpora
    python scripts/fetch_data.py --list                # what is available, what is here

Only RouterBench is required. The rest are replication and cross-check corpora and
each one is large, so they are opt-in rather than pulled by default.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

CORPORA = {
    "routerbench": {
        "url": "https://huggingface.co/datasets/withmartian/routerbench/resolve/main/routerbench_0shot.pkl",
        "path": "routerbench_0shot.pkl",
        "size_mb": 95,
        "required": True,
        "what": "405K outcomes, 11 models, 36,497 prompts, realised per-call cost",
    },
    "llmrouterbench": {
        "url": "https://huggingface.co/datasets/NPULH/LLMRouterBench/resolve/main/bench-release.tar.gz",
        "path": "llmrouterbench-release.tar.gz",
        "size_mb": 1224,
        "required": False,
        "what": "larger pool for replication; per-benchmark model answers",
    },
    "mixinstruct": {
        "url": "https://huggingface.co/datasets/llm-blender/mix-instruct/resolve/main/test_data_prepared.jsonl",
        "path": "mixinstruct_test.jsonl",
        "size_mb": 82,
        "required": False,
        "what": "11 models, pairwise preferences — quality-label cross-check",
    },
}


def _human(n: int) -> str:
    return f"{n / 1e6:.1f} MB"


def fetch(name: str, force: bool = False) -> Path:
    spec = CORPORA[name]
    dest = RAW / spec["path"]
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        print(f"[skip] {name}: already at {dest} ({_human(dest.stat().st_size)})")
        return dest

    print(f"[get ] {name}: ~{spec['size_mb']} MB from {spec['url']}")
    tmp = dest.with_suffix(dest.suffix + ".part")

    def hook(block: int, block_size: int, total: int) -> None:
        if total <= 0:
            return
        done = min(block * block_size, total)
        pct = 100 * done / total
        sys.stdout.write(f"\r       {pct:5.1f}%  {_human(done)} / {_human(total)}")
        sys.stdout.flush()

    urllib.request.urlretrieve(spec["url"], tmp, reporthook=hook)
    sys.stdout.write("\n")
    tmp.rename(dest)

    digest = hashlib.sha256(dest.read_bytes()).hexdigest()[:16]
    print(f"[ok  ] {name}: {dest} ({_human(dest.stat().st_size)}) sha256:{digest}…")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="routerbench",
                    choices=[*CORPORA, "all", "required"])
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    ap.add_argument("--list", action="store_true", help="show status and exit")
    args = ap.parse_args()

    if args.list:
        print(f"{'corpus':<16} {'status':<10} {'size':>9}  what")
        for name, spec in CORPORA.items():
            p = RAW / spec["path"]
            status = "present" if p.exists() else "missing"
            size = _human(p.stat().st_size) if p.exists() else f"~{spec['size_mb']} MB"
            print(f"{name:<16} {status:<10} {size:>9}  {spec['what']}")
        return 0

    if args.corpus == "all":
        names = list(CORPORA)
    elif args.corpus == "required":
        names = [n for n, s in CORPORA.items() if s["required"]]
    else:
        names = [args.corpus]

    for name in names:
        try:
            fetch(name, force=args.force)
        except Exception as exc:                      # noqa: BLE001 — report, continue
            print(f"[fail] {name}: {exc}")
            if CORPORA[name]["required"]:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
