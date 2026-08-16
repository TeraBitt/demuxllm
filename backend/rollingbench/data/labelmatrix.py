"""The label matrix — the one data object everything else reads.

Rows are items, columns are models, each cell records what happened when that
model answered that item. RollingBench §2 defines it; this module is the in-memory
form of it, plus the two derived quantities every experiment needs (`oracle` and
`best_single`) so they are computed once and identically everywhere.

Held as dense arrays rather than a long dataframe on purpose: every experiment
below slices by item and by model thousands of times, and a 36k x 11 float array
is 3 MB. Sparsity is expressed as a mask, not as missing rows, because "this model
was never run on this item" and "this model failed on this item" are different
facts and a long table loses the distinction.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

import numpy as np


@dataclass
class LabelMatrix:
    """Graded outcomes for `n_items` items over `n_models` models.

    Attributes
    ----------
    quality : (n_items, n_models) float
        Graded outcome in [0, 1]. RouterBench ships accuracy per cell.
    cost : (n_items, n_models) float
        Realised USD for that call, as measured, not re-derived from a price list.
    observed : (n_items, n_models) bool
        Whether the cell was actually run. Everything that fits a model reads
        through this mask, so a sampled matrix and a dense one behave the same.
    tokens_out : (n_items, n_models) float
        Output-token estimate per cell. RouterBench does not publish token counts,
        so this is derived from response length where responses exist — flagged in
        `notes` wherever that is the case rather than passed off as measured.
    """

    item_ids: np.ndarray          # (n_items,) str
    model_ids: list[str]
    quality: np.ndarray           # (n_items, n_models) float
    cost: np.ndarray              # (n_items, n_models) float
    observed: np.ndarray          # (n_items, n_models) bool
    tokens_out: np.ndarray | None = None
    prompts: np.ndarray | None = None     # (n_items,) str
    task: np.ndarray | None = None        # (n_items,) str  e.g. "mmlu-anatomy"
    domain: np.ndarray | None = None      # (n_items,) str  coarse bucket
    released: dict[str, _dt.date] = field(default_factory=dict)
    source: str = ""
    notes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ shape --
    @property
    def n_items(self) -> int:
        return self.quality.shape[0]

    @property
    def n_models(self) -> int:
        return self.quality.shape[1]

    def col(self, model_id: str) -> int:
        return self.model_ids.index(model_id)

    def cols(self, model_ids: list[str]) -> list[int]:
        return [self.col(m) for m in model_ids]

    # ------------------------------------------------------------- selections --
    def subset_items(self, idx: np.ndarray) -> "LabelMatrix":
        """Keep a subset of rows. Used for train/test splits, which are by item.

        Splitting by item and not by row is NFR-7: the same prompt answered by
        eleven models is eleven rows and one item, and letting those straddle a
        split leaks the answer.
        """
        idx = np.asarray(idx)
        return LabelMatrix(
            item_ids=self.item_ids[idx],
            model_ids=list(self.model_ids),
            quality=self.quality[idx],
            cost=self.cost[idx],
            observed=self.observed[idx],
            tokens_out=None if self.tokens_out is None else self.tokens_out[idx],
            prompts=None if self.prompts is None else self.prompts[idx],
            task=None if self.task is None else self.task[idx],
            domain=None if self.domain is None else self.domain[idx],
            released=dict(self.released),
            source=self.source,
            notes=list(self.notes),
        )

    def subset_models(self, model_ids: list[str]) -> "LabelMatrix":
        """Keep a subset of columns — how a growing pool is replayed."""
        cols = self.cols(model_ids)
        return LabelMatrix(
            item_ids=self.item_ids,
            model_ids=list(model_ids),
            quality=self.quality[:, cols],
            cost=self.cost[:, cols],
            observed=self.observed[:, cols],
            tokens_out=None if self.tokens_out is None else self.tokens_out[:, cols],
            prompts=self.prompts,
            task=self.task,
            domain=self.domain,
            released={k: v for k, v in self.released.items() if k in model_ids},
            source=self.source,
            notes=list(self.notes),
        )

    # ------------------------------------------------------------ derivatives --
    def solve_rate(self) -> np.ndarray:
        """Per-item share of the pool that got it right.

        The calibration gate (FR-5) and the retirement rule (FR-25) are both
        thresholds on this, and item difficulty in the IRT sense is a monotone
        function of it.
        """
        obs = self.observed
        n = obs.sum(axis=1)
        tot = np.where(obs, self.quality, 0.0).sum(axis=1)
        return np.divide(tot, np.maximum(n, 1), out=np.zeros(self.n_items), where=n > 0)

    def model_accuracy(self) -> dict[str, float]:
        out = {}
        for j, m in enumerate(self.model_ids):
            obs = self.observed[:, j]
            out[m] = float(self.quality[obs, j].mean()) if obs.any() else float("nan")
        return out

    def summary(self) -> dict:
        return {
            "source": self.source,
            "items": self.n_items,
            "models": self.n_models,
            "cells": int(self.observed.sum()),
            "density": float(self.observed.mean()),
            "mean_quality": float(self.quality[self.observed].mean()),
            "total_cost_usd": float(self.cost[self.observed].sum()),
            "notes": self.notes,
        }


def tie_rate(lm: LabelMatrix, tol: float = 1e-9) -> dict[str, float]:
    """Share of model pairs that score identically on the same item.

    This is the measurement RollingBench §3.1 leans on ("ties 52.9% to 61.7%") and
    the reason §6/Contribution 3 expects uninformative batches to be common. It is
    computed here rather than quoted so the number in the report is ours.
    """
    q, obs = lm.quality, lm.observed
    ties = 0
    pairs = 0
    for a in range(lm.n_models):
        for b in range(a + 1, lm.n_models):
            both = obs[:, a] & obs[:, b]
            if not both.any():
                continue
            d = np.abs(q[both, a] - q[both, b])
            ties += int((d <= tol).sum())
            pairs += int(both.sum())
    # Per-item: does every model in the pool agree?
    row_min = np.where(obs, q, np.nan)
    with np.errstate(invalid="ignore"):
        spread = np.nanmax(row_min, axis=1) - np.nanmin(row_min, axis=1)
    return {
        "pairwise_tie_rate": ties / max(pairs, 1),
        "pairs_compared": pairs,
        "unanimous_item_rate": float(np.nanmean(spread <= tol)),
    }
