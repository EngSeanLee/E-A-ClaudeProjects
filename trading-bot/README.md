# Trading Bot (Alpaca, paper-first)

A personal algorithmic trading bot for a **$500 account**, split into two sleeves:

- **Core (50%)** — momentum/trend screen over a curated large-cap universe, meant
  for steadier 3–6 month holds. "Sure thing" is aspirational, not a guarantee —
  see [Honest expectations](#honest-expectations) below.
- **Satellite (50%)** — scans a watchlist for stocks that are statistically cheap
  (low P/E, low P/B, non-shrinking revenue) *and* showing a technical breakout,
  then trades those more actively. This is the higher-risk, higher-reward half.

Every order — from either sleeve — passes through a risk manager that enforces:
- A **daily loss circuit breaker** (halts new orders if equity drops too far in
  one day — catches bugs, not just bad market days).
- The **PDT day-trade limit** (accounts under $25k get 3 day-trades per rolling
  5 trading days — enforced in software so paper mode behaves like live will).
- **Per-position size caps** and **per-sleeve stop losses**.

## Honest expectations

No bot can reliably find "sure things" or guarantee 10x returns — if it could,
whoever built it wouldn't be sharing it. What this bot actually does:

- The **core** sleeve picks the strongest-trending names out of a hand-picked
  list of large, liquid companies. That's a bet on momentum continuing, not a
  guarantee.
- The **satellite** sleeve looks for stocks that are numerically cheap on a few
  standard value metrics AND showing renewed buying interest (breakout +
  volume). Most "cheap" stocks are cheap for a reason. A 10x is possible but
  will be the rare outcome, not the expected one — size your expectations
  around losing part or all of the satellite sleeve sometimes.

This is a real piece of software placing real orders (in paper mode by
default) — treat it with the same skepticism you'd give any trading strategy,
not extra trust just because a bot is running it.

## Setup

1. **Get Alpaca paper API keys**: sign up at https://alpaca.markets/, go to
   your dashboard, switch to **Paper Trading**, and generate an API key/secret.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your paper keys:
   ```
   cp .env.example .env
   ```
   `.env` is git-ignored — never commit real keys.
4. Run one cycle manually to make sure everything connects:
   ```
   python main.py
   ```
   Check `logs/` for what it did (or didn't do, and why).
5. Once you're comfortable, run it continuously on weekdays:
   ```
   python main.py --loop
   ```
   (Or use Windows Task Scheduler / cron to run `python main.py` once daily
   instead of keeping a process running — either works. `--loop`'s `RUN_TIME`
   is in your system's local time, not exchange time — adjust it.)

## Going live (real money)

Don't, until you've watched it run in paper mode for a while and read every
line of `config.py`. When you're ready:

1. Generate **live** API keys from the Alpaca dashboard (different from paper keys).
2. Update `.env`: put the live keys in, and set `ALPACA_PAPER=false`.
3. That's it — the bot will log a loud warning on startup confirming live mode.

## Tuning it

Everything adjustable lives in `config.py`: universe/watchlist symbols,
allocation split, position size caps, stop losses, PDT/circuit-breaker
thresholds, screen thresholds. Nothing else in the codebase should need
editing to change behavior.

## Project layout

```
config.py             all tunable settings
broker.py              Alpaca API wrapper (orders, positions, market data)
risk_manager.py         circuit breaker, PDT tracking, position size caps
data_fundamentals.py    yfinance-based P/E, P/B, revenue growth lookups
core_strategy.py        core sleeve: trend + momentum ranking
satellite_strategy.py   satellite sleeve: value screen + breakout trigger
main.py                 orchestrator / entry point
state/                  local JSON state (day-trade log, daily equity) — git-ignored
logs/                   daily run logs — git-ignored
```

## Disclaimer

This is a personal project, not financial advice. Trading involves real risk
of loss, including total loss of the funds allocated to it. Past performance
of any strategy (including the simple factors used here) does not guarantee
future results.
