#!/usr/bin/env python
"""Execute the notebooks in place so their outputs are baked into the files.

A notebook committed without outputs is a promise that it works; a notebook committed
with them is evidence. This runs each one against the artifacts on disk and fails loudly
if any cell raises, so a broken analysis cannot be checked in looking fine.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "notebooks"


def main() -> int:
    import nbformat
    from nbclient import NotebookClient

    if not (ROOT / "artifacts" / "manifest.json").exists():
        print("artifacts/ is empty — run `python scripts/run_all.py` first")
        return 1

    failures = []
    for path in sorted(NB.glob("*.ipynb")):
        print(f"executing {path.name} …", end=" ", flush=True)
        nb = nbformat.read(path, as_version=4)
        client = NotebookClient(nb, timeout=900, kernel_name="python3",
                               resources={"metadata": {"path": str(NB)}})
        try:
            client.execute()
            nbformat.write(nb, path)
            print("ok")
        except Exception as exc:                       # noqa: BLE001 — report all, fail at end
            print(f"FAILED\n  {type(exc).__name__}: {str(exc)[:400]}")
            failures.append(path.name)
            nbformat.write(nb, path)

    if failures:
        print(f"\n{len(failures)} notebook(s) failed: {', '.join(failures)}")
        return 1
    print(f"\nall {len(list(NB.glob('*.ipynb')))} notebooks executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
