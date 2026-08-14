"""
All the knobs live here. Nothing in strategy/risk/broker code should hardcode
a number that a human might reasonably want to change — it should read it
from here instead.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Broker credentials / mode
# ---------------------------------------------------------------------------
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
# Paper trading unless this is explicitly the string "false" in .env.
# Defaulting to paper on any missing/misconfigured value is intentional.
ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").strip().lower() != "false"

# ---------------------------------------------------------------------------
# Account / allocation
# ---------------------------------------------------------------------------
# This is a *target* total used for position sizing math. The bot also reads
# your real account equity from Alpaca and will scale down automatically if
# actual equity is lower than this.
ACCOUNT_TARGET_TOTAL = 500.00

CORE_ALLOCATION_PCT = 0.50       # "sure thing" sleeve, 3-6mo holds
SATELLITE_ALLOCATION_PCT = 0.50  # aggressive / undervalued / swing sleeve

# ---------------------------------------------------------------------------
# Risk manager — these apply no matter how aggressive the strategy is.
# They exist to catch BUGS, not to second-guess your risk appetite.
# ---------------------------------------------------------------------------

# Halt ALL new orders for the rest of the day if account equity drops this
# much from the start-of-day value. This is a bug/crash circuit breaker.
DAILY_LOSS_HALT_PCT = 0.08  # 8%

# Pattern Day Trader rule: accounts under $25k are limited to 3 day trades
# (open+close same symbol same day) per rolling 5 trading-day window on a
# margin account. We track and enforce this ourselves so paper trading
# behaves the same as it will once real money / real PDT enforcement kicks in.
PDT_EQUITY_THRESHOLD = 25_000.00
PDT_MAX_DAY_TRADES_PER_5_DAYS = 3

# Per-position sizing caps, as a fraction of EACH sleeve's own capital
# (not the whole account).
CORE_MAX_POSITION_PCT = 0.25       # e.g. up to 25% of core sleeve in one name
SATELLITE_MAX_POSITION_PCT = 0.20  # up to 20% of satellite sleeve in one name

# Stop losses (fraction below entry price). Core sleeve is meant to be
# "steadier" so it gets a wider stop; satellite is meant to be volatile
# so it gets a tighter one to avoid one bad name eating the whole sleeve.
CORE_STOP_LOSS_PCT = 0.15
SATELLITE_STOP_LOSS_PCT = 0.10

# ---------------------------------------------------------------------------
# Core sleeve — momentum/trend screen over a curated large-cap universe.
# Edit this list to whatever you consider "sure thing" candidates.
# ---------------------------------------------------------------------------
CORE_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AVGO",
    "V", "MA", "COST", "JNJ", "PG", "HD", "LLY", "UNH",
]
CORE_TOP_N = 5           # hold at most this many core names at once
CORE_REBALANCE_DAYS = 7  # only re-check core ranking this often

# ---------------------------------------------------------------------------
# Satellite sleeve — fundamentals-cheap + technical-breakout watchlist.
# This is a candidate universe, NOT a guarantee any of these are actually
# undervalued at any given time — the screen below filters it live.
# ---------------------------------------------------------------------------
SATELLITE_WATCHLIST = [
    "SOFI", "PLUG", "RIOT", "MARA", "PLTR", "RIVN", "LCID",
    "CHPT", "IONQ", "SIRI", "OPEN", "SNAP",
]

# Fundamental screen thresholds (a candidate must pass ALL to be "undervalued")
SATELLITE_MAX_PE = 25          # trailing P/E below this (ignored if PE is negative/N/A)
SATELLITE_MAX_PB = 3.0         # price/book below this
SATELLITE_MIN_REVENUE_GROWTH = 0.0  # YoY revenue growth must be >= this (0 = not shrinking)

# Technical trigger: breakout above N-day high with volume confirmation
SATELLITE_BREAKOUT_LOOKBACK_DAYS = 20
SATELLITE_VOLUME_SPIKE_MULT = 1.5  # today's volume >= 1.5x the 20-day avg volume

SATELLITE_TOP_N = 3  # hold at most this many satellite names at once

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
STATE_DIR = "state"
LOG_DIR = "logs"
