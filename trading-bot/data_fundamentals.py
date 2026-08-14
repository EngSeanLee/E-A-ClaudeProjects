"""
Fundamentals lookups via yfinance (unofficial Yahoo Finance data — free, no
API key, but can be rate-limited or occasionally flaky/incomplete). Used only
by the satellite sleeve's "is this actually cheap" screen. Alpaca gives us
price/volume; it doesn't give us P/E, P/B, or revenue growth, so this fills
that gap.
"""

from __future__ import annotations

import logging
import yfinance as yf

log = logging.getLogger("fundamentals")


def get_fundamentals(symbol: str) -> dict | None:
    """
    Returns {"pe": float|None, "pb": float|None, "revenue_growth": float|None}
    or None if the lookup failed entirely.
    """
    try:
        info = yf.Ticker(symbol).info
    except Exception as e:
        log.warning("Fundamentals lookup failed for %s: %s", symbol, e)
        return None

    if not info:
        return None

    return {
        "pe": info.get("trailingPE"),
        "pb": info.get("priceToBook"),
        "revenue_growth": info.get("revenueGrowth"),  # YoY, as a fraction e.g. 0.12 = 12%
    }


def passes_value_screen(symbol: str, max_pe: float, max_pb: float, min_revenue_growth: float) -> bool:
    f = get_fundamentals(symbol)
    if f is None:
        log.info("%s: no fundamentals data, skipping", symbol)
        return False

    pe, pb, growth = f["pe"], f["pb"], f["revenue_growth"]

    if pe is not None and pe > 0 and pe > max_pe:
        return False
    if pb is not None and pb > 0 and pb > max_pb:
        return False
    if growth is not None and growth < min_revenue_growth:
        return False

    # If ALL fields are missing we have nothing to screen on — treat as fail
    # rather than silently letting it through.
    if pe is None and pb is None and growth is None:
        log.info("%s: fundamentals fields all missing, treating as fail", symbol)
        return False

    return True
