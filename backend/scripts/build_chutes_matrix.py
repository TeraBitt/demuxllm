#!/usr/bin/env python
"""Parse LLMRouterBench into the compact cache the Chutes pool reads.

    python scripts/build_chutes_matrix.py

Runs once. The release tarball is ~1.2 GB compressed and expands to far more than
that — the per-record `raw_output` and `prediction` fields dominate it and nothing
downstream reads either — so this never extracts it. It streams members straight
out of the archive, keeps the four numeric columns and a truncated prompt, and
writes ~8 MB of npz.

Extracting it instead will fill a normal disk and take the machine down with it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rollingbench.catalog import check_proxy_table, proxy_ids  # noqa: E402
from rollingbench.data import llmrouterbench  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tarball", default=str(llmrouterbench.DEFAULT_TARBALL))
    ap.add_argument("--out", default=str(llmrouterbench.DEFAULT_CACHE))
    args = ap.parse_args()

    check_proxy_table()
    llmrouterbench.build_cache(args.tarball, args.out)

    # Fail here rather than three stages later if a binding names a model the
    # corpus does not actually contain.
    lm = llmrouterbench.load(args.out, models=proxy_ids(), dense_only=True)
    print(f"[check] all {lm.n_models} bound proxies present; "
          f"dense core {lm.n_items:,} items over {len(set(lm.task.tolist()))} tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
