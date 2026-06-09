# Codex-Backed Trade Lifecycle Engine

`codex-backed` is a CLI-only stock trade lifecycle engine. It replaces the old single composite buy/avoid score with separate entry, exit, risk, and backtest components.

The engine is designed for short-term and medium-term trade decisions. It does not assume that a trade must be sold exactly on day 20 or day 63. Instead, it simulates a realistic lifecycle: enter, set a stop, take partial profit, move the stop, trail the remainder, and exit when the configured sell policy fires.

## Documents

- [HLD.md](HLD.md) - high-level system architecture and operating model.
- [LLD.md](LLD.md) - low-level module, class, config, and data-flow design.
- [BACKTEST_README.md](BACKTEST_README.md) - how to run and interpret lifecycle backtests.
- [DESIGN.md](DESIGN.md) - original architecture/design notes.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - story-based implementation plan.
- [BACKTEST_IMPLEMENTATION_PLAN.md](BACKTEST_IMPLEMENTATION_PLAN.md) - detailed backtest implementation plan.
- [PROGRESS.md](PROGRESS.md) - current implementation tracker.

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
codex-backed/.venv/bin/codex-backed backtest
codex-backed/.venv/bin/codex-backed optimize-entry
codex-backed/.venv/bin/codex-backed optimize-exit
codex-backed/.venv/bin/codex-backed report
codex-backed/.venv/bin/codex-backed compare
```

Only `validate-config` and `backtest` are fully wired today. Optimization/report/compare commands are scaffolded.

## Daily Usage Workflow

Use this as a decision-support tool, not an automatic trading bot. The daily workflow should separate new entries from trade management.

1. Refresh or generate the upstream price cache used by `codex-backed`.
2. Run `validate-config` after any config change.
3. Run a focused backtest or current-date analysis on the watchlist you care about.
4. Review `entry_decisions.csv` first.
5. Focus on actionable labels:
   - `BUY_STARTER`: valid setup, but use smaller size.
   - `BUY_FULL`: stronger setup with acceptable risk.
   - `BUY_AGGRESSIVE`: rare high-conviction setup; still respect stops.
6. Treat `WATCHLIST` as no immediate entry unless the setup improves or price reaches a planned trigger.
7. Treat `NO_TRADE` as no action.
8. Review `trades.csv` and `metrics.json` to understand how similar historical signals behaved under the configured sell policy.
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
