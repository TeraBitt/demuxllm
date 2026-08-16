"""RollingBench — the router engine and the experiments that test its claims.

Layout
------
`catalog`     the model pools: the Chutes pool the product serves, and the dated
              RouterBench pool the staleness study replays
`data/`       corpus adapters and the label matrix everything reads
`features`    φ(q) — the frozen static lane (§8.2)
`router`      the estimator: shared-γ baseline (§8) and decomposed (§4)
`coldstart`   IRT, low-rank completion, the derived prior (§8.6, §5)
`metrics`     normalised regret (§8.8) and the shrinkage fix (§6)
`experiments/` one module per claim, each returning plain dicts/arrays so a
              notebook can plot them without re-deriving anything

Nothing in this package touches the network at import time or at fit time. Data is
downloaded once by `scripts/fetch_data.py`; every experiment then replays graded
outcomes already on disk, which is what "zero inference spend" means in practice.
"""

from .catalog import CHUTES_CATALOG, ROUTERBENCH_POOL, Model
from .features import FeatureMap
from .metrics import UtilityWeights, per_cell_utility, score_batch, shrink_scores
from .router import (
    BestSingleRouter,
    DecomposedRouter,
    PoolState,
    RandomRouter,
    RidgeLinUCBRouter,
    RouterConfig,
)

__all__ = [
    "CHUTES_CATALOG",
    "ROUTERBENCH_POOL",
    "Model",
    "FeatureMap",
    "RidgeLinUCBRouter",
    "DecomposedRouter",
    "BestSingleRouter",
    "RandomRouter",
    "PoolState",
    "RouterConfig",
    "UtilityWeights",
    "per_cell_utility",
    "score_batch",
    "shrink_scores",
]

__version__ = "1.0.0"
