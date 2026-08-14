"""
Thin wrapper around Alpaca's trading + market data clients. Nothing in here
decides WHAT to trade — it only knows HOW to talk to Alpaca. Strategy and
risk logic call into this, never the raw alpaca-py SDK directly, so we have
one place to log/guard every real order.
"""

import logging
from datetime import datetime, timedelta

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame

import config

log = logging.getLogger("broker")


class Broker:
    def __init__(self):
        if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
            raise RuntimeError(
                "Missing ALPACA_API_KEY / ALPACA_SECRET_KEY. Copy .env.example to "
                ".env and fill in your keys before running the bot."
            )

        self.trading = TradingClient(
            api_key=config.ALPACA_API_KEY,
            secret_key=config.ALPACA_SECRET_KEY,
            paper=config.ALPACA_PAPER,
        )
        self.data = StockHistoricalDataClient(
            api_key=config.ALPACA_API_KEY,
            secret_key=config.ALPACA_SECRET_KEY,
        )

        mode = "PAPER" if config.ALPACA_PAPER else "LIVE"
        log.info("Broker connected in %s mode", mode)
        if not config.ALPACA_PAPER:
            log.warning(
                "!!! LIVE TRADING MODE — real money, real orders. "
                "Make sure that's really what you want. !!!"
            )

    # -- account / positions -------------------------------------------------

    def get_account(self):
        return self.trading.get_account()

    def get_equity(self) -> float:
        return float(self.get_account().equity)

    def get_positions(self) -> dict:
        """symbol -> position object"""
        return {p.symbol: p for p in self.trading.get_all_positions()}

    def get_open_orders(self):
        return self.trading.get_orders()

    # -- market data -----------------------------------------------------------

    def get_daily_bars(self, symbol: str, lookback_days: int = 220):
        """Returns a pandas DataFrame of daily OHLCV bars, oldest first."""
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=datetime.utcnow() - timedelta(days=int(lookback_days * 1.6)),  # pad for weekends/holidays
        )
        bars = self.data.get_stock_bars(req).df
        if bars.empty:
            return bars
        # multi-index (symbol, timestamp) when one symbol requested too
        if isinstance(bars.index, type(bars.index)) and "symbol" in bars.index.names:
            bars = bars.xs(symbol, level="symbol")
        return bars.tail(lookback_days)

    def get_latest_price(self, symbol: str) -> float:
        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        trade = self.data.get_stock_latest_trade(req)[symbol]
        return float(trade.price)

    # -- orders ----------------------------------------------------------------

    def submit_notional_buy(self, symbol: str, dollar_amount: float):
        """Buy a fractional/whole quantity worth this many dollars."""
        dollar_amount = round(dollar_amount, 2)
        log.info("SUBMIT BUY  %s  $%.2f (notional)", symbol, dollar_amount)
        order = MarketOrderRequest(
            symbol=symbol,
            notional=dollar_amount,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        return self.trading.submit_order(order)

    def submit_market_sell(self, symbol: str, qty: float):
        """Sell a specific quantity (use to close/trim a position)."""
        log.info("SUBMIT SELL %s  qty=%s", symbol, qty)
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        return self.trading.submit_order(order)

    def close_position(self, symbol: str):
        log.info("CLOSE POSITION %s", symbol)
        return self.trading.close_position(symbol)
