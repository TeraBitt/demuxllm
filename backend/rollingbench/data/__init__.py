"""Corpus adapters. Each returns the same `LabelMatrix`, so an experiment written
against one corpus runs against another without edits."""

from .labelmatrix import LabelMatrix, tie_rate

__all__ = ["LabelMatrix", "tie_rate"]
