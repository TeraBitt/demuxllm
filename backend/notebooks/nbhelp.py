"""Shared helpers for the notebooks.

The notebooks read `artifacts/*.json` written by `scripts/run_all.py` rather than
recomputing. That keeps them fast to open and, more importantly, keeps the numbers in
the analysis identical to the numbers in the artifacts — a notebook that recomputes is
a notebook that can disagree with the report it is supposed to explain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
FIGURES = ARTIFACTS / "figures"


def load(name: str) -> dict:
    path = ARTIFACTS / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing — run `python scripts/run_all.py` from the backend directory first"
        )
    return json.loads(path.read_text())


def table(rows, cols: list[str] | None = None, **fmt) -> pd.DataFrame:
    """Rows of dicts to a DataFrame, in the column order given."""
    df = pd.DataFrame(rows)
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    return df.style.format(fmt) if fmt else df


def pct(x, places: int = 1) -> str:
    return "—" if x is None else f"{100 * x:.{places}f}%"


def show(name: str, caption: str = "") -> None:
    """Display a figure written by run_all.py, with its caption.

    The PNG bytes are embedded rather than linked, so an executed notebook renders on
    its own — emailed, viewed on GitHub, or opened from anywhere on disk — without the
    `artifacts/` tree sitting next to it.
    """
    from IPython.display import Image, Markdown, display

    path = FIGURES / f"{name}.png"
    if not path.exists():
        display(Markdown(f"*figure `{name}` not found — re-run `scripts/run_all.py`*"))
        return
    display(Image(filename=str(path), embed=True))
    if caption:
        display(Markdown(f"*{caption}*"))


def md(text: str) -> None:
    from IPython.display import Markdown, display

    display(Markdown(text))


def finding(verdict: str, text: str) -> None:
    """A labelled finding, so a reader skimming can see which way each result went.

    `verdict` is one of supported / not-supported / mixed / correction.
    """
    from IPython.display import Markdown, display

    mark = {
        "supported": "**SUPPORTED**",
        "not-supported": "**NOT SUPPORTED**",
        "mixed": "**MIXED**",
        "correction": "**CORRECTION**",
        "new": "**NEW FINDING**",
    }.get(verdict, f"**{verdict.upper()}**")
    display(Markdown(f"> {mark} — {text}"))


pd.set_option("display.max_columns", 40)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda v: f"{v:,.4f}")
