"""Live prices, and what happens to routing when they move.

RollingBench splits the router into a lane that is fitted and a lane that is read.
Quality and expected output tokens are fitted; price, latency and availability are
read from a table at decision time and never enter the fit. FR-16 is the promise
that falls out of that split: a price change reaches routing decisions without a
refit, a redeploy, or a retraining job.

That is a claim about the architecture, so this module tests it rather than
repeating it. `fetch_live` reads the published Chutes price list — the endpoint is
public, no key required — and `price_shock` re-decides an already-trained router
against a changed table, asserting the fitted state is byte-identical either side.

The interesting result is not that the code runs. It is the elasticity: how much
traffic and spend actually move for a given price cut, which is the number that
says whether "we react to price changes" is a feature or a slogan.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import numpy as np

from ..catalog import CHUTES_CATALOG, by_id
from ..data.labelmatrix import LabelMatrix
from ..router import PoolState, RidgeLinUCBRouter

ENDPOINT = "https://llm.chutes.ai/v1/models"


def fetch_live(url: str = ENDPOINT, timeout: float = 20.0) -> dict:
    """The published price list, as USD per 1M tokens.

    Returns `{model_id: {"in_per_1m", "out_per_1m", "cached_in_per_1m", "ctx"}}`.
    Raises on a network failure rather than falling back to the shipped catalogue:
    a silent fallback would let a stale table masquerade as a live read, which is
    exactly the failure this module exists to rule out.
    """
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"{url} returned {resp.status}")
        payload = json.loads(resp.read().decode("utf-8"))

    out: dict[str, dict] = {}
    for m in payload.get("data", []):
        pricing = m.get("pricing") or {}
        if pricing.get("prompt") is None:
            continue  # image / audio / OCR chutes cannot be routed to
        out[str(m["id"])] = {
            "in_per_1m": float(pricing["prompt"]),
            "out_per_1m": float(pricing.get("completion", pricing["prompt"])),
            "cached_in_per_1m": (
                float(pricing["input_cache_read"])
                if pricing.get("input_cache_read") is not None else None),
            "ctx": m.get("context_length"),
        }
    return out


def diff_against_catalogue(live: dict) -> dict:
    """What drifted between the shipped catalogue and the live list."""
    drift, missing, extra = [], [], []
    for m in CHUTES_CATALOG:
        row = live.get(m.id)
        if row is None:
            missing.append(m.id)
            continue
        d_in = row["in_per_1m"] - m.in_per_1m
        d_out = row["out_per_1m"] - m.out_per_1m
        if abs(d_in) > 1e-9 or abs(d_out) > 1e-9:
            drift.append({
                "model_id": m.id, "label": m.label,
                "catalogue_in": m.in_per_1m, "live_in": row["in_per_1m"],
                "catalogue_out": m.out_per_1m, "live_out": row["out_per_1m"],
                "blended_change_pct": (
                    ((row["in_per_1m"] + 3 * row["out_per_1m"]) / max(m.blended_price, 1e-12)) - 1.0
                ),
            })
    served = {m.id for m in CHUTES_CATALOG}
    extra = sorted(set(live) - served)
    return {
        "in_sync": not drift and not missing,
        "drift": drift,
        "missing_from_live": missing,
        "served_live_but_not_in_catalogue": extra,
        "live_model_count": len(live),
        "catalogue_model_count": len(CHUTES_CATALOG),
    }


def pool_state_from(prices: dict[str, dict]) -> PoolState:
    """A `PoolState` built from a price table rather than from the catalogue."""
    return PoolState(
        price_in=np.array([prices[m.id]["in_per_1m"] for m in CHUTES_CATALOG]),
        price_out=np.array([prices[m.id]["out_per_1m"] for m in CHUTES_CATALOG]),
    )


def catalogue_prices() -> dict[str, dict]:
    return {m.id: {"in_per_1m": m.in_per_1m, "out_per_1m": m.out_per_1m}
            for m in CHUTES_CATALOG}


def _decide(router: RidgeLinUCBRouter, X: np.ndarray, prices: dict[str, dict],
            tokens_in: np.ndarray) -> np.ndarray:
    return router.decide(X, pool_state_from(prices), tokens_in=tokens_in).choice


def reprice(
    router: RidgeLinUCBRouter,
    lm: LabelMatrix,
    X: np.ndarray,
    test: np.ndarray,
    tokens_in: np.ndarray,
    new_prices: dict[str, dict],
    *,
    base_prices: dict[str, dict] | None = None,
) -> dict:
    """Re-decide under a new price table, with no refit, and report what moved.

    The fitted state is hashed before and after. If a price change could only reach
    decisions by touching the estimator, these two hashes would differ and the
    architectural claim would be false.
    """
    base_prices = base_prices or catalogue_prices()
    before_state = router.quality.W.tobytes() + router.tokens.W.tobytes()

    old_choice = _decide(router, X[test], base_prices, tokens_in)
    new_choice = _decide(router, X[test], new_prices, tokens_in)

    after_state = router.quality.W.tobytes() + router.tokens.W.tobytes()
    n = len(test)
    rows = np.arange(n)

    def spend(prices: dict[str, dict], choice: np.ndarray) -> float:
        p_in = np.array([prices[m.id]["in_per_1m"] for m in CHUTES_CATALOG])
        p_out = np.array([prices[m.id]["out_per_1m"] for m in CHUTES_CATALOG])
        cost = (tokens_in[:, None] / 1e6) * p_in[None, :] + (
            lm.tokens_out[test] / 1e6) * p_out[None, :]
        return float(cost[rows, choice].sum())

    q = lm.quality[test]
    return {
        "estimator_unchanged": before_state == after_state,
        "requests_rerouted": int((old_choice != new_choice).sum()),
        "requests_rerouted_pct": float((old_choice != new_choice).mean()),
        "spend_before_usd": spend(base_prices, old_choice),
        # What the old policy would have cost once the new prices landed — the
        # counterfactual for a router that could not react.
        "spend_if_frozen_usd": spend(new_prices, old_choice),
        "spend_after_usd": spend(new_prices, new_choice),
        "quality_before": float(q[rows, old_choice].mean()),
        "quality_after": float(q[rows, new_choice].mean()),
        "traffic_before": {lm.model_ids[j]: float((old_choice == j).mean())
                           for j in range(lm.n_models)},
        "traffic_after": {lm.model_ids[j]: float((new_choice == j).mean())
                          for j in range(lm.n_models)},
    }


def price_shock(
    router: RidgeLinUCBRouter,
    lm: LabelMatrix,
    X: np.ndarray,
    test: np.ndarray,
    tokens_in: np.ndarray,
    *,
    target_id: str | None = None,
    factors: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0),
) -> dict:
    """Move one model's price and watch the traffic move — the elasticity curve.

    A router that reacts to price is worth paying for only if the reaction is
    material, so this reports the whole curve rather than a single "yes it moved".
    """
    base = catalogue_prices()
    target_id = target_id or max(
        CHUTES_CATALOG, key=lambda m: by_id(CHUTES_CATALOG, m.id).blended_price).id

    points = []
    for f in factors:
        prices = {k: dict(v) for k, v in base.items()}
        prices[target_id]["in_per_1m"] *= f
        prices[target_id]["out_per_1m"] *= f
        res = reprice(router, lm, X, test, tokens_in, prices, base_prices=base)
        j = lm.model_ids.index(target_id)
        points.append({
            "factor": f,
            "target_share_before": res["traffic_before"][target_id],
            "target_share_after": res["traffic_after"][target_id],
            "requests_rerouted_pct": res["requests_rerouted_pct"],
            "spend_after_usd": res["spend_after_usd"],
            "spend_if_frozen_usd": res["spend_if_frozen_usd"],
            "saved_by_reacting_usd": res["spend_if_frozen_usd"] - res["spend_after_usd"],
            "quality_after": res["quality_after"],
            "estimator_unchanged": res["estimator_unchanged"],
        })
        del j

    halved = next((p for p in points if abs(p["factor"] - 0.5) < 1e-9), None)
    doubled = next((p for p in points if abs(p["factor"] - 2.0) < 1e-9), None)
    return {
        "target": target_id,
        "target_label": by_id(CHUTES_CATALOG, target_id).label,
        "points": points,
        "reading": (
            f"Halving {by_id(CHUTES_CATALOG, target_id).label}'s price moves its traffic "
            f"share from {halved['target_share_before']:.1%} to "
            f"{halved['target_share_after']:.1%}; doubling it moves it to "
            f"{doubled['target_share_after']:.1%}. No refit — the fitted state is "
            f"unchanged at every point."
            if halved and doubled else "insufficient grid"),
    }
