"""Feature cache.

φ is fit-once-frozen, so recomputing it for every experiment burns a minute to
arrive at a byte-identical array. Cached under a key that covers everything which
could change the array — corpus, dimension, bucket count, and which items were used
to fit the projection — so a stale cache cannot be picked up by accident.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from ..features import FeatureMap
from .labelmatrix import LabelMatrix

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"


def _key(lm: LabelMatrix, n_components: int, n_buckets: int, fit_idx: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(lm.source.encode())
    h.update(str((lm.n_items, lm.n_models, n_components, n_buckets)).encode())
    h.update(np.asarray(fit_idx, dtype=np.int64).tobytes())
    return h.hexdigest()[:16]


def features_for(
    lm: LabelMatrix,
    n_components: int = 52,
    n_buckets: int = 4096,
    fit_idx: np.ndarray | None = None,
    cache: bool = True,
    verbose: bool = True,
) -> tuple[np.ndarray, FeatureMap]:
    """Features for every item in `lm`, with the projection fitted on `fit_idx`.

    Fitting the projection on a subset and transforming everything is the honest
    order of operations: the PCA basis is part of the model, so letting it see the
    test items would leak. `fit_idx` defaults to all items, which is correct only
    for unsupervised description (EDA) — every experiment passes its training split.
    """
    if fit_idx is None:
        fit_idx = np.arange(lm.n_items)
    if lm.prompts is None:
        raise ValueError("label matrix has no prompts; load with with_prompts=True")

    key = _key(lm, n_components, n_buckets, fit_idx)
    xpath = CACHE_DIR / f"X_{key}.npy"
    spath = CACHE_DIR / f"fm_{key}.npz"

    if cache and xpath.exists() and spath.exists():
        state = dict(np.load(spath, allow_pickle=False))
        state["n_components"] = int(state["n_components"])
        state["n_buckets"] = int(state["n_buckets"])
        if verbose:
            print(f"[cache] features from {xpath.name}")
        return np.load(xpath), FeatureMap.from_state(state)

    if verbose:
        print(f"[build] features for {lm.n_items:,} items "
              f"(d={n_components + 12}, {n_buckets} hash buckets) …")
    fm = FeatureMap(n_components=n_components, n_buckets=n_buckets)
    fm.fit(list(lm.prompts[fit_idx]))
    X = fm.transform(list(lm.prompts))

    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(xpath, X)
        st = fm.state()
        np.savez(spath, n_components=st["n_components"], n_buckets=st["n_buckets"],
                 mean=st["mean"], basis=st["basis"], scale=st["scale"])
    return X, fm
