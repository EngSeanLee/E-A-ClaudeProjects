"""
Every order in this bot must be approved by RiskManager before it's sent to
the broker. This module doesn't know or care about strategy logic — it only
answers "is this safe to do right now?"

Two independent safety nets live here:
  1. Daily loss circuit breaker — halts all new orders for the day if
     account equity drops too far from where it started today. This exists
     to catch BUGS (a runaway loop, a bad price read, a strategy gone
     haywire), not to second-guess intentional risk-taking.
  2. PDT day-trade counter — tracks round-trips (buy+sell same symbol same
     day) so we never exceed the legal limit for a sub-$25k account.

State is persisted to small JSON files in state/ so counts survive restarts.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, date, timedelta

import config

log = logging.getLogger("risk")

DAILY_EQUITY_FILE = os.path.join(config.STATE_DIR, "daily_equity.json")
DAY_TRADES_FILE = os.path.join(config.STATE_DIR, "day_trades.json")
FILLS_FILE = os.path.join(config.STATE_DIR, "fills_today.json")


def _load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


class RiskManager:
    def __init__(self, broker):
        self.broker = broker
        self.today = date.today().isoformat()
        self._halted = False
        self._halt_reason = None
        self._ensure_start_of_day_equity()

    # -- daily loss circuit breaker ------------------------------------------

    def _ensure_start_of_day_equity(self):
        record = _load(DAILY_EQUITY_FILE, {})
        if record.get("date") != self.today:
            equity = self.broker.get_equity()
            record = {"date": self.today, "start_equity": equity}
            _save(DAILY_EQUITY_FILE, record)
            log.info("New trading day. Start-of-day equity: $%.2f", equity)
        self.start_equity = record["start_equity"]

    def check_circuit_breaker(self) -> bool:
        """Returns True if trading is currently allowed, False if halted."""
        if self._halted:
            return False
        equity = self.broker.get_equity()
        if self.start_equity <= 0:
            return True
        drawdown = (self.start_equity - equity) / self.start_equity
        if drawdown >= config.DAILY_LOSS_HALT_PCT:
            self._halted = True
            self._halt_reason = (
                f"Daily loss circuit breaker tripped: equity down "
                f"{drawdown:.1%} from start-of-day ${self.start_equity:.2f} "
                f"to ${equity:.2f} (limit {config.DAILY_LOSS_HALT_PCT:.0%})."
            )
            log.error(self._halt_reason)
            return False
        return True

    @property
    def halt_reason(self):
        return self._halt_reason

    # -- PDT day-trade counter -----------------------------------------------

    def _load_day_trades(self):
        data = _load(DAY_TRADES_FILE, {"trades": []})
        cutoff = date.today() - timedelta(days=7)  # keep a little buffer
        data["trades"] = [t for t in data["trades"] if date.fromisoformat(t) >= cutoff]
        return data

    def _rolling_5_day_count(self, data) -> int:
        # Rolling 5 *trading* days approximated as the last 5 calendar days
        # that had a recorded day-trade; good enough for a v1 self-imposed
        # limit (deliberately conservative vs. exact trading-calendar math).
        cutoff = date.today() - timedelta(days=5)
        return sum(1 for t in data["trades"] if date.fromisoformat(t) >= cutoff)

    def day_trades_remaining(self) -> int:
        equity = self.broker.get_equity()
        if equity >= config.PDT_EQUITY_THRESHOLD:
            return 999  # not subject to PDT limits
        data = self._load_day_trades()
        used = self._rolling_5_day_count(data)
        return max(0, config.PDT_MAX_DAY_TRADES_PER_5_DAYS - used)

    def record_day_trade(self):
        data = self._load_day_trades()
        data["trades"].append(date.today().isoformat())
        _save(DAY_TRADES_FILE, data)
        log.info("Recorded a day trade. Remaining today's window: %d",
                  self.day_trades_remaining())

    def opened_position_today(self, symbol: str) -> bool:
        """Track symbols bought today so we know if a same-day sell would count as a day trade."""
        fills = _load(FILLS_FILE, {"date": self.today, "bought": []})
        if fills.get("date") != self.today:
            fills = {"date": self.today, "bought": []}
        return symbol in fills["bought"]

    def record_buy(self, symbol: str):
        fills = _load(FILLS_FILE, {"date": self.today, "bought": []})
        if fills.get("date") != self.today:
            fills = {"date": self.today, "bought": []}
        if symbol not in fills["bought"]:
            fills["bought"].append(symbol)
        _save(FILLS_FILE, fills)

    # -- position sizing guardrails -------------------------------------------

    def max_position_dollars(self, sleeve: str, sleeve_capital: float) -> float:
        pct = (config.CORE_MAX_POSITION_PCT if sleeve == "core"
               else config.SATELLITE_MAX_POSITION_PCT)
        return round(sleeve_capital * pct, 2)

    def stop_loss_pct(self, sleeve: str) -> float:
        return config.CORE_STOP_LOSS_PCT if sleeve == "core" else config.SATELLITE_STOP_LOSS_PCT

    # -- master gate ------------------------------------------------------------

    def approve_buy(self, sleeve: str, symbol: str, dollar_amount: float) -> tuple[bool, str]:
        if not self.check_circuit_breaker():
            return False, self.halt_reason
        cap = self.max_position_dollars(
            sleeve,
            self.broker.get_equity() * (config.CORE_ALLOCATION_PCT if sleeve == "core"
                                         else config.SATELLITE_ALLOCATION_PCT),
        )
        if dollar_amount > cap:
            return False, f"Order ${dollar_amount:.2f} exceeds per-position cap ${cap:.2f} for {sleeve} sleeve"
        return True, "ok"

    def approve_same_day_sell(self, symbol: str) -> tuple[bool, str]:
        """Only relevant if we bought this symbol earlier today (that's what makes it a day trade)."""
        if not self.opened_position_today(symbol):
            return True, "ok"  # not a day trade, no PDT concern
        if self.day_trades_remaining() <= 0:
            return False, (
                f"PDT limit reached ({config.PDT_MAX_DAY_TRADES_PER_5_DAYS} per 5 days) — "
                f"cannot close {symbol} same-day. Will hold overnight instead."
            )
        return True, "ok"
