"""RouterBench adapter.

RouterBench (withmartian/routerbench, 0-shot split) ships one row per prompt with
one score column and one realised-cost column per model. That is exactly a label
matrix in wide form, so the adapter is mostly bookkeeping: name the columns, coerce
the scores, attach the release dates the pool carries, and derive an output-token
estimate from the responses because the corpus does not publish token counts.

Downloading is separate (`scripts/fetch_data.py`) so that loading never touches the
network — an experiment that silently re-downloads is an experiment that cannot be
replayed on a train.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..catalog import ROUTERBENCH_POOL, pool_ids
from .labelmatrix import LabelMatrix

# eval_name is fine-grained (57 mmlu subjects). Domain is the bucket a router can
# realistically specialise on, which is what §16.2's per-region scoring needs.
_DOMAIN_RULES: tuple[tuple[str, str], ...] = (
    ("mbpp", "code"),
    ("code", "code"),
    ("grade-school-math", "math"),
    ("mmlu-elementary-mathematics", "math"),
    ("mmlu-high-school-mathematics", "math"),
    ("mmlu-college-mathematics", "math"),
    ("mmlu-abstract-algebra", "math"),
    ("mmlu-high-school-statistics", "math"),
    ("mmlu-econometrics", "math"),
    ("chinese", "chinese"),
    ("mmlu-professional-law", "law"),
    ("mmlu-international-law", "law"),
    ("mmlu-jurisprudence", "law"),
    ("mmlu-professional-medicine", "medicine"),
    ("mmlu-clinical-knowledge", "medicine"),
    ("mmlu-college-medicine", "medicine"),
    ("mmlu-medical-genetics", "medicine"),
    ("mmlu-anatomy", "medicine"),
    ("mmlu-virology", "medicine"),
    ("mmlu-nutrition", "medicine"),
    ("hellaswag", "commonsense"),
    ("winogrande", "commonsense"),
    ("arc-challenge", "commonsense"),
    ("mtbench", "openended"),
    ("consensus_summary", "openended"),
    ("abstract2title", "openended"),
    ("bias_detection", "openended"),
    ("accounting_audit", "business"),
    ("mmlu-professional-accounting", "business"),
    ("mmlu-management", "business"),
    ("mmlu-marketing", "business"),
    ("mmlu-business-ethics", "business"),
    ("mmlu-public-relations", "business"),
    ("mmlu-moral", "humanities"),
    ("mmlu-philosophy", "humanities"),
    ("mmlu-world-religions", "humanities"),
    ("mmlu-logical-fallacies", "humanities"),
    ("mmlu-formal-logic", "humanities"),
    ("mmlu-prehistory", "humanities"),
    ("history", "humanities"),
    ("mmlu-sociology", "humanities"),
    ("mmlu-psychology", "humanities"),
    ("mmlu-machine-learning", "cs"),
    ("mmlu-computer-science", "cs"),
    ("mmlu-computer-security", "cs"),
    ("mmlu-security-studies", "cs"),
    ("mmlu-electrical-engineering", "engineering"),
    ("mmlu-conceptual-physics", "science"),
    ("physics", "science"),
    ("chemistry", "science"),
    ("biology", "science"),
    ("mmlu-astronomy", "science"),
)


def _domain_of(eval_name: str) -> str:
    key = str(eval_name).lower()
    for needle, bucket in _DOMAIN_RULES:
        if needle in key:
            return bucket
    if key.startswith("mmlu"):
        return "knowledge"
    return "other"


def _prompt_text(raw) -> str:
    """RouterBench stores prompts as a stringified list of turns.

    The literal string is what a feature map would see if it were handed the raw
    field, so unwrap it here once — a router fed `['...', '...']` is featurising
    Python syntax as much as the question.
    """
    s = str(raw)
    if s.startswith("[") and s.endswith("]"):
        try:
            import ast

            parts = ast.literal_eval(s)
            if isinstance(parts, (list, tuple)):
                return "\n\n".join(str(p) for p in parts)
        except (ValueError, SyntaxError):
            pass
    return s


def load(
    path: str | Path = "data/raw/routerbench_0shot.pkl",
    *,
    with_prompts: bool = True,
    estimate_tokens: bool = True,
) -> LabelMatrix:
    """Read the RouterBench pickle into a `LabelMatrix`."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run: python scripts/fetch_data.py --corpus routerbench"
        )

    df = pd.read_pickle(path)
    models = pool_ids(ROUTERBENCH_POOL)
    missing = [m for m in models if m not in df.columns]
    if missing:
        raise ValueError(f"RouterBench is missing expected model columns: {missing}")

    n, k = len(df), len(models)
    quality = np.zeros((n, k), dtype=np.float64)
    cost = np.zeros((n, k), dtype=np.float64)
    tokens_out = np.zeros((n, k), dtype=np.float64) if estimate_tokens else None

    for j, m in enumerate(models):
        quality[:, j] = pd.to_numeric(df[m], errors="coerce").to_numpy()
        cost[:, j] = pd.to_numeric(df[f"{m}|total_cost"], errors="coerce").to_numpy()
        if estimate_tokens:
            resp_col = f"{m}|model_response"
            if resp_col in df.columns:
                lens = df[resp_col].astype(str).str.len().to_numpy()
                # ~4 chars per token is the same estimator the frontend uses to
                # price a demo (`estimateTokens`); keeping them identical means the
                # backend's token predictions and the product's cost display agree.
                tokens_out[:, j] = np.maximum(1.0, np.ceil(lens / 4.0))

    # A NaN score means the cell was not graded, not that the model scored zero.
    observed = np.isfinite(quality) & np.isfinite(cost)
    quality = np.nan_to_num(quality, nan=0.0)
    cost = np.nan_to_num(cost, nan=0.0)

    tasks = df["eval_name"].astype(str).to_numpy()
    domains = np.array([_domain_of(t) for t in tasks])

    notes = [
        "quality = RouterBench per-cell accuracy in [0,1] (as published)",
        "cost = RouterBench realised per-call USD (as published, not re-derived)",
    ]
    if estimate_tokens:
        notes.append(
            "tokens_out = ceil(len(response)/4) — DERIVED, not measured; RouterBench "
            "publishes no token counts. Used only for the token-prediction target."
        )

    return LabelMatrix(
        item_ids=df["sample_id"].astype(str).to_numpy(),
        model_ids=models,
        quality=quality,
        cost=cost,
        observed=observed,
        tokens_out=tokens_out,
        prompts=(
            np.array([_prompt_text(p) for p in df["prompt"]]) if with_prompts else None
        ),
        task=tasks,
        domain=domains,
        released={m.id: m.released for m in ROUTERBENCH_POOL if m.released},
        source="RouterBench 0-shot (withmartian/routerbench)",
        notes=notes,
    )
