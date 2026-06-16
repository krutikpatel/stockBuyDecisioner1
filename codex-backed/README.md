# Codex-Backed Trade Lifecycle Engine

`codex-backed` is a CLI-only stock trade lifecycle engine. It replaces the old single composite buy/avoid score with separate entry, exit, risk, and backtest components.

The engine is designed for short-term and medium-term trade decisions. It does not assume that a trade must be sold exactly on day 20 or day 63. Instead, it simulates a realistic lifecycle: enter, set a stop, take partial profit, move the stop, trail the remainder, and exit when the configured sell policy fires.

## Documents

- [HLD.md](HLD.md) - high-level system architecture and operating model.
- [LLD.md](LLD.md) - low-level module, class, config, and data-flow design.
- [BACKTEST_README.md](BACKTEST_README.md) - how to run and interpret lifecycle backtests.
- [DESIGN.md](docs/baseProject/DESIGN.md) - original architecture/design notes.
- [IMPLEMENTATION_PLAN.md](docs/baseProject/IMPLEMENTATION_PLAN.md) - story-based implementation plan.
- [BACKTEST_IMPLEMENTATION_PLAN.md](docs/baseProject/BACKTEST_IMPLEMENTATION_PLAN.md) - detailed backtest implementation plan.
- [PROGRESS.md](docs/baseProject/PROGRESS.md) - original implementation tracker (archived).

## Current Capabilities

- Pure JSON config loading and validation.
- Config-driven entry setup detection.
- Config-driven entry routing and scoring.
- Clean entry labels:
  - `NO_TRADE`
  - `WATCHLIST`
  - `BUY_STARTER`
  - `BUY_FULL`
  - `BUY_AGGRESSIVE`
- Entry execution simulation:
  - `NEXT_OPEN`
  - `NEXT_CLOSE`
  - `PULLBACK_TO_SMA20`
  - `PULLBACK_TO_SMA50`
  - `BREAKOUT_CONFIRMATION`
- Risk controls:
  - label-based sizing
  - high-ATR cap
  - earnings proximity cap
- Exit lifecycle simulation:
  - initial ATR/support stop
  - partial profit-taking
  - stop move to breakeven
  - ATR trailing stop
  - time stop
  - max simulation window
- Parallel ticker-level backtest runner.
- Native OHLCV historical feature generation for backtests.
- Live watchlist analysis using fresh yfinance OHLCV data.
- Feature caching with config-hash invalidation.
- CSV, JSON, and diagnostic HTML report output.

## Setup

Run commands from the repository root:

```bash
cd /Users/krutik/technical/claudeCodeExperiments/stockButDecisionMaker/usingGptStrategy
```

Create and use the dedicated `codex-backed` virtual environment:

```bash
python3 -m venv codex-backed/.venv
codex-backed/.venv/bin/python -m pip install -e 'codex-backed[dev]'
codex-backed/.venv/bin/codex-backed --help
```

Validate config:

```bash
codex-backed/.venv/bin/codex-backed validate-config \
  --config-dir codex-backed/configs
```

Run tests:

```bash
codex-backed/.venv/bin/python -m pytest codex-backed/tests -q
```

## CLI Commands

```bash
codex-backed/.venv/bin/codex-backed validate-config
codex-backed/.venv/bin/codex-backed analyze
codex-backed/.venv/bin/codex-backed backtest
codex-backed/.venv/bin/codex-backed optimize-entry
codex-backed/.venv/bin/codex-backed optimize-exit
codex-backed/.venv/bin/codex-backed report
codex-backed/.venv/bin/codex-backed compare
```

`validate-config`, `analyze`, and `backtest` are fully wired today. Optimization/report/compare commands are scaffolded.

## Daily Watchlist Analysis

`analyze` is the current-date watchlist command. It does not accept or require a date. Each run uses today's local date as the analysis date, pulls fresh daily OHLCV data from yfinance, builds latest native feature snapshots, scores both configured horizons, and writes a small watchlist artifact set.

By default, `analyze` reads:

```text
codex-backed/configs/watchlist_config.json
```

Default command:

```bash
codex-backed/.venv/bin/codex-backed analyze \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id today_watchlist
```

Temporary ticker override:

```bash
codex-backed/.venv/bin/codex-backed analyze \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id today_aapl_msft \
  --tickers AAPL,MSFT
```

Outputs land in `codex-backed/results/<run-id>/`:

```text
manifest.json
entry_decisions.csv
actionable_watchlist.csv
metrics.json
```

Important behavior:

- `analyze` always fetches fresh yfinance data.
- `analyze` does not read `codex-backed/cache/prices.pkl`.
- `analyze` does not read or write `codex-backed/cache/features.pkl`.
- `actionable_watchlist.csv` contains only `BUY_STARTER`, `BUY_FULL`, and `BUY_AGGRESSIVE` rows.
- If yfinance's latest returned bar is from the previous trading day, the run still records today's requested analysis date and the latest signal date actually used.

## Daily Usage Workflow

Use this as a decision-support tool, not an automatic trading bot. The daily workflow should separate new entries from trade management.

1. Run `analyze` for the default watchlist or a temporary ticker override.
2. Run `validate-config` after any config change.
3. Review the current-date `entry_decisions.csv` and `actionable_watchlist.csv`.
4. Review `entry_decisions.csv` first.
5. Focus on actionable labels:
   - `BUY_STARTER`: valid setup, but use smaller size.
   - `BUY_FULL`: stronger setup with acceptable risk.
   - `BUY_AGGRESSIVE`: rare high-conviction setup; still respect stops.
6. Treat `WATCHLIST` as no immediate entry unless the setup improves or price reaches a planned trigger.
7. Treat `NO_TRADE` as no action.
8. Review `metrics.json` and recent backtests to understand how similar historical signals behaved under the configured sell policy.
9. For any candidate, check the stop, target, expected position size, exit policy, and current market regime before acting.
10. Keep a trade log with entry label, entry strategy, regime, entry price, stop, target, exit reason, and realized result.

The intended daily output is a small set of candidates, not a large ranked list. Good daily candidates are stocks where the entry label, market regime, risk size, and sell policy all make sense together.

## Common Backtest Command

By default, `backtest` uses the broad ticker universe in:

```text
codex-backed/configs/backtest_ticker_universe_config.json
```

```bash
codex-backed/.venv/bin/codex-backed backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id daily_watchlist_check \
  --start 2022-01-01 \
  --end 2024-12-31 \
  --rebuild-feature-cache \
  --workers 1
```

Use `--tickers` only for a temporary smoke test or focused run:

```bash
codex-backed/.venv/bin/codex-backed backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id smoke_aapl_msft \
  --tickers AAPL,MSFT \
  --rebuild-feature-cache \
  --workers 1
```

Use `--workers 1` for debugging. Use higher worker counts for faster runs when the environment allows process spawning.

When adding or removing default backtest tickers, edit `codex-backed/configs/backtest_ticker_universe_config.json` and then run `validate-config`. A ticker also needs price bars in `codex-backed/cache/prices.pkl`; otherwise it will not produce feature rows or trades until the price cache is expanded.

When adding or removing default daily analysis tickers, edit `codex-backed/configs/watchlist_config.json` and then run `validate-config`.

## Backtest Feature Sources

The default backtest feature source is now native:

```text
feature_generation.source = native
```

Native mode reads OHLCV bars from `codex-backed/cache/prices.pkl`, computes technical/setup features locally, and caches generated feature rows in `codex-backed/cache/features.pkl`.

The old parent signal CSV can still be used only as an explicit debug fallback:

```bash
codex-backed/.venv/bin/codex-backed backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id parent_csv_debug \
  --feature-source parent_csv
```

The fallback no longer fabricates raw fundamentals or technical fields from signal-card scores.
