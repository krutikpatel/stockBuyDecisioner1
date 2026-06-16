# CLAUDE.md

This file gives Claude Code the context needed to work in this repository.

**Working directory:** All code reads and writes are scoped to `codex-backed/`. Do not touch `backend/`, `claude-backend/`, `legacy/`, or `frontend/` unless the user explicitly asks.

## Commands

All commands run from the repository root. Use the `codex-backed` virtualenv:

```bash
# Validate configs (always run after a config change)
PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli validate-config \
  --config-dir codex-backed/configs

# Run tests
backend/.venv/bin/python -m pytest codex-backed/tests -q

# Run a full backtest (default ticker universe)
PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id <run_id> \
  --rebuild-feature-cache \
  --workers 1

# Smoke test on a few tickers
PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id smoke_aapl_msft \
  --tickers AAPL,MSFT \
  --rebuild-feature-cache \
  --workers 1

# Daily watchlist analysis (live yfinance data, today's date)
PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli analyze \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id today_watchlist
```

Use `--workers 1` by default — multiprocessing has sandbox friction; single-worker is the known reliable path.

### FMP mode commands (requires API key)

Put your key in `.env` at the repo root (`FMP_API_KEY=sk-...`). Source it before any FMP command:

```bash
# Full backtest using FMP data (prices + fundamentals)
source .env && PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id fmp_run_<id> \
  --data-mode fmp_primary_yfinance_fallback \
  --rebuild-feature-cache \
  --workers 1

# Smoke test with FMP data (two tickers)
source .env && PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id fmp_smoke_aapl_msft \
  --tickers AAPL,MSFT \
  --data-mode fmp_primary_yfinance_fallback \
  --rebuild-feature-cache \
  --workers 1

# Daily watchlist analysis with FMP fundamentals
source .env && PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli analyze \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id today_watchlist_fmp \
  --data-mode fmp_primary_yfinance_fallback

# Run FMP baseline capture tests (S4.2)
source .env && backend/.venv/bin/python -m pytest codex-backed/tests/test_fmp_baseline_capture.py -v

# Run S4.3 activation gate tests (all 6 gates — required before flipping active_mode)
source .env && backend/.venv/bin/python -m pytest codex-backed/tests/test_activation_gates.py -v
```

If `--tickers` is omitted, backtests use `codex-backed/configs/backtest_ticker_universe_config.json`. Pass `--tickers` only for smoke tests or temporary overrides.

## Architecture

### Backtest Data Flow

```
cached OHLCV bars (codex-backed/cache/prices.pkl)
  -> native historical feature builder
  -> setup detection  (technical_setup_config.json)
  -> entry routing    (entry_signal_config.json)
  -> risk sizing      (risk_config.json)
  -> bar-by-bar exit  (exit_policy_config.json)
  -> metrics + CSV/HTML outputs (codex-backed/results/)
```

### Key Directories

| Path | Purpose |
|------|---------|
| `codex-backed/src/codex_backed/` | CLI, feature builder, entry engine, trade simulator, risk, metrics, writers |
| `codex-backed/configs/` | All strategy/backtest/risk/exit JSON configs |
| `codex-backed/cache/prices.pkl` | OHLCV bar cache |
| `codex-backed/cache/features.pkl` | Native feature cache (invalidated by config hash) |
| `codex-backed/results/` | Backtest run artifacts |

### Entry Labels

- `NO_TRADE` — no setup
- `WATCHLIST` — setup present, no immediate entry
- `BUY_STARTER` — valid setup, smaller size
- `BUY_FULL` — stronger setup, acceptable risk
- `BUY_AGGRESSIVE` — rare high-conviction setup

### Config Files

All strategy intelligence lives in `codex-backed/configs/`. Keep them pure JSON (no YAML/TOML).

| Config file | What it controls |
|-------------|-----------------|
| `technical_setup_config.json` | Named signals and setup definitions |
| `entry_signal_config.json` | Entry routing and scoring rules |
| `risk_config.json` | Position sizing, ATR cap, earnings cap |
| `exit_policy_config.json` | Stop, partial profit, breakeven, trailing stop, time stop |
| `backtest_ticker_universe_config.json` | Default broad ticker universe |
| `watchlist_config.json` | Default daily analysis tickers |
| `data_provider_config.json` | Active data mode, provider tier caps, FMP/yfinance settings |

### Feature Source

The default backtest feature source is `native` — reads `prices.pkl`, computes features locally, caches to `features.pkl`.

`parent_csv` exists only as a debug/compatibility fallback. Never use it for real optimization — old parent signal CSV fields hide missing historical setup data.

## Current Baseline

The 50-iteration optimization loop completed and selected `loop50_49` as the best run. Do not restart it. For further tuning, start a new named run series and append a new audit log (do not overwrite `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`).

**Best short-term exit config:**
- target 1 / breakeven trigger: `2.375R`, partial sell at target 1: `0%`
- move stop to breakeven after target: `true`, trailing stop: `2.5 ATR`, max sim days: `60`

**Medium-term exit config:**
- target 1: `2.0R`, partial sell: `40%`, breakeven trigger: `1.25R`, trailing stop: `3.0 ATR`, max sim days: `90`

**Best run metrics (`codex-backed/results/loop50_49`):**
- decisions: 161,842 | trades: 1,082 | avg return: 9.1276% | median: 7.6729% | win rate: 58.3179% | profit factor: 5.0810

## Key Conventions

- Always run `validate-config` after any config change before a backtest.
- For optimization: change config → run named backtest → inspect metrics → log the decision.
- When adding/removing backtest tickers, edit `backtest_ticker_universe_config.json` then validate.
- When adding/removing watchlist tickers, edit `watchlist_config.json` then validate.
- A ticker also needs price bars in `prices.pkl`; otherwise it produces no feature rows or trades until the cache is expanded.
- `analyze` always fetches fresh yfinance data; it does not read `prices.pkl` or `features.pkl`.

## Reference Docs

- `codex-backed/HLD.md` — architecture overview and operating model
- `codex-backed/LLD.md` — module, class, config, and data-flow design
- `codex-backed/BACKTEST_README.md` — backtest commands and output interpretation
- `codex-backed/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` — completed 50-run optimization audit trail
- `codex-backed/NEXT_IMPROVEMENTS_PLAN.md` — planned next improvements
