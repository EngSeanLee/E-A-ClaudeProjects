"""
Core sleeve — "sure thing" is in quotes for a reason (see README): nothing is
guaranteed, but this sleeve aims for steadier, longer-hold (3-6mo) exposure
by picking the strongest trending names out of a curated large-cap universe,
rather than chasing volatility.

Signal: simple trend + momentum.
  - Trend filter: price must be above its 200-day SMA (long-term uptrend).
  - Momentum score: price vs its 100-day SMA — bigger gap = stronger recent
    momentum, ranked highest first.

This is intentionally simple (classic, well-understood factors) rather than
clever — clever curve-fit strategies tend to be the ones that break in live
markets. Tune CORE_UNIVERSE / CORE_TOP_N in config.py.
"""

from __future__ import annotations

import logging
import pandas as pd

import config

log = logging.getLogger("core_strategy")


def _score_symbol(broker, symbol: str) -> dict | None:
    bars = broker.get_daily_bars(symbol, lookback_days=220)
    if bars.empty or len(bars) < 200:
        log.info("%s: not enough history, skipping", symbol)
        return None

    close = bars["close"]
    price = float(close.iloc[-1])
    sma100 = float(close.rolling(100).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1])

    if price <= sma200:
        return None  # not in a long-term uptrend, fails trend filter

    momentum = (price / sma100) - 1.0
    return {"symbol": symbol, "price": price, "sma100": sma100,
            "sma200": sma200, "momentum": momentum}


def rank_candidates(broker) -> list[dict]:
    """Returns qualifying core-universe symbols sorted best-momentum first."""
    scored = []
    for symbol in config.CORE_UNIVERSE:
        try:
            s = _score_symbol(broker, symbol)
        except Exception as e:
            log.warning("%s: scoring failed: %s", symbol, e)
            s = None
        if s:
            scored.append(s)

    scored.sort(key=lambda s: s["momentum"], reverse=True)
    return scored


def desired_holdings(broker) -> list[str]:
    """Top-N symbols that should be held in the core sleeve right now."""
    ranked = rank_candidates(broker)
    return [s["symbol"] for s in ranked[: config.CORE_TOP_N]]
