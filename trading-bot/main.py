"""
Orchestrator. One call to run_cycle() = one full pass:
  1. Check circuit breaker.
  2. Core sleeve: rank universe, buy anything newly in the top-N, sell
     anything that dropped out or hit its stop loss.
  3. Satellite sleeve: scan watchlist for value+breakout hits, buy up to
     TOP_N new positions, sell anything that hit its stop loss.
  4. Every sell respects the PDT day-trade budget — if closing a position
     bought today would blow the budget, it holds overnight instead.

Usage:
  python main.py            # run one cycle right now, then exit
  python main.py --loop     # run once at market-open-ish every weekday
                             # (edit RUN_TIME below for your timezone —
                             # 'schedule' uses local system time)

Nothing here trades unless config.ALPACA_PAPER is respected by your .env —
default is paper. See README.md before ever flipping that to live.
"""

import argparse
import logging
import os
import sys
import time
from datetime import date

import config
from broker import Broker
from risk_manager import RiskManager
import core_strategy
import satellite_strategy

RUN_TIME = "09:35"  # local system time; adjust to match market open in your TZ


def setup_logging():
    os.makedirs(config.LOG_DIR, exist_ok=True)
    log_file = os.path.join(config.LOG_DIR, f"{date.today().isoformat()}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )


log = logging.getLogger("main")


def sleeve_capital(broker, sleeve: str) -> float:
    equity = broker.get_target_equity()
    pct = config.CORE_ALLOCATION_PCT if sleeve == "core" else config.SATELLITE_ALLOCATION_PCT
    return equity * pct


def guess_sleeve(symbol: str) -> str:
    if symbol in config.CORE_UNIVERSE:
        return "core"
    if symbol in config.SATELLITE_WATCHLIST:
        return "satellite"
    return "unknown"


def check_stop_losses(broker, risk):
    positions = broker.get_positions()
    for symbol, pos in positions.items():
        sleeve = guess_sleeve(symbol)
        if sleeve == "unknown":
            continue
        stop_pct = risk.stop_loss_pct(sleeve)
        unrealized_pct = float(pos.unrealized_plpc)  # e.g. -0.12 == -12%
        if unrealized_pct <= -stop_pct:
            log.warning("%s (%s sleeve) down %.1f%%, exceeds stop loss %.1f%% — selling",
                        symbol, sleeve, unrealized_pct * 100, stop_pct * 100)
            ok, reason = risk.approve_same_day_sell(symbol)
            if not ok:
                log.warning("%s: stop-loss sell deferred — %s", symbol, reason)
                continue
            try:
                broker.close_position(symbol)
                if risk.opened_position_today(symbol):
                    risk.record_day_trade()
            except Exception as e:
                log.error("%s: stop-loss sell failed: %s", symbol, e)


def run_core_sleeve(broker, risk):
    log.info("--- Core sleeve ---")
    if not risk.check_circuit_breaker():
        log.error("Circuit breaker active (%s) — skipping core sleeve", risk.halt_reason)
        return

    desired = set(core_strategy.desired_holdings(broker))
    positions = broker.get_positions()
    held_core = {s for s in positions if guess_sleeve(s) == "core"}

    # Sell anything that dropped out of the top-N ranking
    for symbol in held_core - desired:
        log.info("%s dropped out of core top-N — selling", symbol)
        ok, reason = risk.approve_same_day_sell(symbol)
        if not ok:
            log.warning("%s: rebalance sell deferred — %s", symbol, reason)
            continue
        try:
            broker.close_position(symbol)
            if risk.opened_position_today(symbol):
                risk.record_day_trade()
        except Exception as e:
            log.error("%s: rebalance sell failed: %s", symbol, e)

    # Buy anything newly desired that we don't already hold
    capital = sleeve_capital(broker, "core")
    per_position = capital / max(config.CORE_TOP_N, 1)
    for symbol in desired - held_core:
        ok, reason = risk.approve_buy("core", symbol, per_position)
        if not ok:
            log.warning("%s: buy blocked — %s", symbol, reason)
            continue
        try:
            broker.submit_notional_buy(symbol, per_position)
            risk.record_buy(symbol)
        except Exception as e:
            log.error("%s: buy failed: %s", symbol, e)


def run_satellite_sleeve(broker, risk):
    log.info("--- Satellite sleeve ---")
    if not risk.check_circuit_breaker():
        log.error("Circuit breaker active (%s) — skipping satellite sleeve", risk.halt_reason)
        return

    positions = broker.get_positions()
    held_satellite = {s for s in positions if guess_sleeve(s) == "satellite"}
    slots_open = config.SATELLITE_TOP_N - len(held_satellite)
    if slots_open <= 0:
        log.info("Satellite sleeve full (%d/%d positions) — scanning skipped",
                  len(held_satellite), config.SATELLITE_TOP_N)
        return

    candidates = satellite_strategy.find_candidates(broker)
    capital = sleeve_capital(broker, "satellite")
    per_position = capital / max(config.SATELLITE_TOP_N, 1)

    for hit in candidates:
        if slots_open <= 0:
            break
        symbol = hit["symbol"]
        if symbol in held_satellite:
            continue
        ok, reason = risk.approve_buy("satellite", symbol, per_position)
        if not ok:
            log.warning("%s: buy blocked — %s", symbol, reason)
            continue
        try:
            broker.submit_notional_buy(symbol, per_position)
            risk.record_buy(symbol)
            slots_open -= 1
            log.info("%s: breakout above %.2f on %.1fx volume — bought $%.2f",
                      symbol, hit["prior_high"], hit["volume"] / max(hit["avg_volume"], 1), per_position)
        except Exception as e:
            log.error("%s: buy failed: %s", symbol, e)


def run_cycle():
    log.info("=" * 60)
    log.info("Cycle start — %s", date.today().isoformat())
    broker = Broker()
    risk = RiskManager(broker)

    if not risk.check_circuit_breaker():
        log.error("Circuit breaker already tripped for today: %s", risk.halt_reason)
        return

    check_stop_losses(broker, risk)
    run_core_sleeve(broker, risk)
    run_satellite_sleeve(broker, risk)

    equity = broker.get_equity()
    log.info("Cycle complete. Account equity: $%.2f", equity)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true",
                         help="Run continuously, once per weekday at RUN_TIME (local system time)")
    args = parser.parse_args()

    setup_logging()

    if not args.loop:
        run_cycle()
        return

    import schedule

    def job():
        if date.today().weekday() >= 5:  # skip weekends
            return
        run_cycle()

    schedule.every().day.at(RUN_TIME).do(job)
    log.info("Looping — will run every weekday at %s (local system time). Ctrl+C to stop.", RUN_TIME)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
