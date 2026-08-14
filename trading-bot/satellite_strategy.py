"""
Satellite sleeve — the "hunt for undervalued, let it run" half. Two-stage
filter:
  1. Fundamentals screen (data_fundamentals.py): is this name cheap on
     P/E, P/B, and not shrinking on revenue? This is a value proxy, NOT a
     prediction — plenty of "cheap" stocks are cheap for good reasons.
  2. Technical trigger: only actually buy on a breakout above its recent
     N-day high with a volume spike, i.e. wait for the market to show some
     confirmation instead of buying a falling knife just because it's cheap.

Read config.py's comment on SATELLITE_WATCHLIST — this is a candidate list
you curate, not an auto-discovered universe. Expand it as you find more
candidates worth watching.
"""

from __future__ import annotations

import logging

import config
from data_fundamentals import passes_value_screen

log = logging.getLogger("satellite_strategy")


def _check_breakout(broker, symbol: str) -> dict | None:
    bars = broker.get_daily_bars(symbol, lookback_days=config.SATELLITE_BREAKOUT_LOOKBACK_DAYS + 5)
    if bars.empty or len(bars) < config.SATELLITE_BREAKOUT_LOOKBACK_DAYS + 1:
        log.info("%s: not enough history for breakout check, skipping", symbol)
        return None

    lookback = bars.iloc[-(config.SATELLITE_BREAKOUT_LOOKBACK_DAYS + 1):-1]
    today = bars.iloc[-1]

    prior_high = float(lookback["high"].max())
    avg_volume = float(lookback["volume"].mean())

    breakout = float(today["close"]) > prior_high
    volume_spike = float(today["volume"]) >= avg_volume * config.SATELLITE_VOLUME_SPIKE_MULT

    if breakout and volume_spike:
        return {
            "symbol": symbol,
            "price": float(today["close"]),
            "prior_high": prior_high,
            "volume": float(today["volume"]),
            "avg_volume": avg_volume,
        }
    return None


def find_candidates(broker) -> list[dict]:
    """
    Scans the satellite watchlist and returns symbols that pass BOTH the
    value screen and the breakout trigger today, i.e. actual buy candidates.
    """
    hits = []
    for symbol in config.SATELLITE_WATCHLIST:
        try:
            if not passes_value_screen(
                symbol,
                max_pe=config.SATELLITE_MAX_PE,
                max_pb=config.SATELLITE_MAX_PB,
                min_revenue_growth=config.SATELLITE_MIN_REVENUE_GROWTH,
            ):
                continue
            breakout = _check_breakout(broker, symbol)
            if breakout:
                hits.append(breakout)
        except Exception as e:
            log.warning("%s: satellite scan failed: %s", symbol, e)

    # Rank by how strong the volume spike is — bigger confirmation first
    hits.sort(key=lambda h: h["volume"] / max(h["avg_volume"], 1), reverse=True)
    return hits[: config.SATELLITE_TOP_N]
