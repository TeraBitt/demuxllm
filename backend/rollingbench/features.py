"""The feature map φ(q) — RollingBench §8.2.

x = [ PCA_52(hashed n-grams), log(1+input_tokens), surface flags, language one-hot,
      structure, 1 ]  →  d = 64

§8.2 specifies "roughly 64 dimensions" and does not say why. The capacity sweep in
`experiments/scaling.py` checks it, and it holds up: once the hash is wide enough, d = 64
and d = 108 are statistically tied on routing (regret 0.9530 ± 0.0045 against
0.9547 ± 0.0030 over four splits) and d = 64 costs a third of the artifact.

What was wrong was the *encoder*, not the dimension. Widening the hash from 512 to 4,096
buckets lifts the share of the attainable gap captured from +0.589 to +0.836 — collisions
were destroying signal before the projection ever saw it, and a wider hash costs nothing at
serving time. Past d ≈ 108 validation loss keeps falling while routing quality degrades,
which is the other half of notebook 08's finding.

Two decisions worth stating, because both are load-bearing for the claim that this
router is cheap:

The encoder is frozen and never trained. §3.1 reports that encoder scale barely
moves routing accuracy, so the default here is a hashed character/word n-gram
projection — deterministic, dependency-free, microseconds per query. A sentence
encoder can be dropped in via `embed_fn` without touching anything downstream; the
interface is a function from strings to a matrix, nothing more.

The PCA projection is fitted once by SVD on a training slice and then frozen. That
keeps it a closed-form operation (§8.1) and, more importantly, keeps the feature
space fixed while the router updates — a moving feature map would invalidate every
Gram matrix accumulated under the old one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

# Latin-script share is a cheap, honest language signal on a corpus that mixes
# English and Chinese. Full language ID is a dependency this does not need.
_CJK = re.compile(r"[一-鿿㐀-䶿]")
_CODE_FENCE = re.compile(r"```|\bdef \b|\bclass \b|;\s*$|\{\s*$", re.MULTILINE)
_TABLE = re.compile(r"\|.*\|")
_URL = re.compile(r"https?://")
_NUMBER = re.compile(r"\d")
_QUESTION = re.compile(r"\?")
_WORD = re.compile(r"[a-z0-9']+")


def _hash_bucket(token: str, n_buckets: int) -> int:
    # Python's str hash is salted per process; a stable hash keeps a fitted
    # projection reusable across runs, which a saved policy artifact requires.
    h = 2166136261
    for ch in token:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % n_buckets


def hashed_bow(texts: list[str], n_buckets: int = 512, ngram: int = 3) -> np.ndarray:
    """Hashed bag of words + character n-grams, L2-normalised.

    Stands in for the sentence encoder: same shape of signal (similar texts get
    similar vectors), no model to download, no GPU, and deterministic across runs.
    """
    out = np.zeros((len(texts), n_buckets), dtype=np.float64)
    for i, text in enumerate(texts):
        low = str(text).lower()
        for w in _WORD.findall(low)[:400]:
            out[i, _hash_bucket(w, n_buckets)] += 1.0
        # Character n-grams carry script and morphology, which word tokens miss
        # entirely on Chinese items.
        squeezed = re.sub(r"\s+", " ", low)[:600]
        for p in range(len(squeezed) - ngram + 1):
            out[i, _hash_bucket(squeezed[p : p + ngram], n_buckets)] += 0.5
        norm = np.linalg.norm(out[i])
        if norm > 0:
            out[i] /= norm
    return out


def surface_features(texts: list[str]) -> np.ndarray:
    """The non-semantic half of x: length, format flags, script, shape."""
    rows = []
    for text in texts:
        s = str(text)
        n_chars = len(s)
        tokens_in = max(1.0, np.ceil(n_chars / 4.0))
        cjk = len(_CJK.findall(s))
        rows.append([
            np.log1p(tokens_in),
            np.log1p(n_chars) / 10.0,
            1.0 if _CODE_FENCE.search(s) else 0.0,
            1.0 if _TABLE.search(s) else 0.0,
            1.0 if _URL.search(s) else 0.0,
            min(1.0, len(_NUMBER.findall(s)) / 20.0),
            1.0 if _QUESTION.search(s) else 0.0,
            min(1.0, cjk / 50.0),                       # language: CJK
            1.0 if cjk == 0 else 0.0,                   # language: latin-only
            min(1.0, s.count("\n") / 10.0),             # turn/structure proxy
            min(1.0, len(s.split()) / 400.0),
        ])
    return np.asarray(rows, dtype=np.float64)


N_SURFACE = 11


@dataclass
class FeatureMap:
    """Fit-once, frozen-forever φ.

    `fit` computes the PCA basis by SVD; `transform` is a matmul plus a few regex
    passes. Nothing here updates after fitting, which is what makes it the static
    lane in the four-lane split.
    """

    # Both defaults are measured rather than assumed — see experiments/scaling.py and
    # notebook 08. d = 64 matches §8.2 and is confirmed: past it, validation loss keeps
    # falling while routing quality does not. The hash width is the part §8.2 never mentions
    # and the part that was actually costing accuracy.
    n_components: int = 52          # d = 52 + 11 surface + 1 bias = 64
    n_buckets: int = 4096
    _mean: np.ndarray | None = field(default=None, repr=False)
    _basis: np.ndarray | None = field(default=None, repr=False)
    _scale: np.ndarray | None = field(default=None, repr=False)

    @property
    def dim(self) -> int:
        """d — semantic components + surface features + bias."""
        return self.n_components + N_SURFACE + 1

    def fit(self, texts: list[str], seed: int = 0) -> "FeatureMap":
        bow = hashed_bow(list(texts), self.n_buckets)
        self._mean = bow.mean(axis=0)
        centred = bow - self._mean
        # Randomised range finder: full SVD of 36k x 512 is affordable but this
        # keeps fitting sub-second on the largest corpus and is the same closed-form
        # operation, not an iterative fit.
        rng = np.random.default_rng(seed)
        omega = rng.standard_normal((centred.shape[1], self.n_components + 10))
        y = centred @ omega
        q, _ = np.linalg.qr(y)
        b = q.T @ centred
        _, _, vt = np.linalg.svd(b, full_matrices=False)
        self._basis = vt[: self.n_components].T          # (n_buckets, n_components)
        proj = centred @ self._basis
        # Unit-variance components keep the ridge penalty comparable across
        # directions; without it λ regularises the leading component into nothing
        # and the trailing ones not at all.
        self._scale = np.maximum(proj.std(axis=0), 1e-8)
        return self

    def transform(self, texts: list[str]) -> np.ndarray:
        if self._basis is None or self._mean is None or self._scale is None:
            raise RuntimeError("FeatureMap.fit must be called before transform")
        texts = list(texts)
        bow = hashed_bow(texts, self.n_buckets)
        semantic = ((bow - self._mean) @ self._basis) / self._scale
        surface = surface_features(texts)
        bias = np.ones((len(texts), 1))
        return np.hstack([semantic, surface, bias])

    def fit_transform(self, texts: list[str], seed: int = 0) -> np.ndarray:
        return self.fit(texts, seed=seed).transform(texts)

    # Saved with the policy artifact; §13.6's `feature_schema` field is this.
    def state(self) -> dict:
        return {
            "n_components": self.n_components,
            "n_buckets": self.n_buckets,
            "mean": self._mean,
            "basis": self._basis,
            "scale": self._scale,
        }

    @classmethod
    def from_state(cls, state: dict) -> "FeatureMap":
        fm = cls(n_components=int(state["n_components"]), n_buckets=int(state["n_buckets"]))
        fm._mean, fm._basis, fm._scale = state["mean"], state["basis"], state["scale"]
        return fm
