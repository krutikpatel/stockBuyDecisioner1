# CLAUDE.md

This file gives Claude Code the context needed to work in this repository.

**Working directory:** All code reads and writes are scoped to `codex-backed/`. Do not touch `backend/`, `claude-backend/`, `legacy/`, or `frontend/` unless the user explicitly asks.

## Commands

All commands run from the repository root. Use the `codex-backed` virtualenv:

```bash
# Validate configs (always run after a config change)
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli validate-config \
  --config-dir codex-backed/configs

# Run tests
codex-backed/.venv/bin/python -m pytest codex-backed/tests -q

# Run a full backtest (default ticker universe, FMP primary data)
set -a; source .env; set +a
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id <run_id> \
  --rebuild-feature-cache \
  --workers 1

# Smoke test on a few tickers
set -a; source .env; set +a
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id smoke_aapl_msft \
  --tickers AAPL,MSFT \
  --rebuild-feature-cache \
  --workers 1

# Daily watchlist analysis (FMP prices + fundamentals, today's date)
set -a; source .env; set +a
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli analyze \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id today_watchlist
```

Use `--workers 1` by default — multiprocessing has sandbox friction; single-worker is the known reliable path.

`set -a; source .env; set +a` exports `FMP_API_KEY` into the process environment. Plain `source .env` only sets a shell variable and Python will not see it.

### Legacy mode (no FMP key needed)

Force legacy yfinance-only mode with `--data-mode legacy_yfinance`. Useful for offline tests or when the FMP key is unavailable:

```bash
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id legacy_smoke \
  --tickers AAPL,MSFT \
  --data-mode legacy_yfinance \
  --rebuild-feature-cache \
  --workers 1
```

### FMP gate and smoke tests

```bash
# Provider smoke test (real HTTP, AAPL + MSFT only — fast)
set -a; source .env; set +a
codex-backed/.venv/bin/python -m pytest codex-backed/tests/test_fmp_free_key_smoke.py -v

# Full S4.3 activation gate suite (real backtest + live analyze — slow, ~15 min)
set -a; source .env; set +a
codex-backed/.venv/bin/python -m pytest \
  codex-backed/tests/test_activation_gates.py \
  codex-backed/tests/test_fmp_baseline_capture.py -v

# Access audit — probe FMP plan coverage across the ticker universe
set -a; source .env; set +a
python codex-backed/scripts/fmp_access_audit.py --max 20
```

If `--tickers` is omitted, backtests use `codex-backed/configs/backtest_ticker_universe_config.json`. Pass `--tickers` only for smoke tests or temporary overrides.

## Architecture

### Backtest Data Flow

```
FMP REST API (/stable/ endpoints)       prices.pkl (pickle fallback)
  -> FMPPriceProvider                     -> PickleProvider
       \                                 /
        CompositePriceProvider (primary = FMP, fallback = pickle)
             |
             v
  native historical feature builder
             |
             v
  FMP fundamentals + yfinance fallback
  -> CompositeFundamentalsProvider
             |
             v
  setup detection  (technical_setup_config.json)
  entry routing    (entry_signal_config.json)
  risk sizing      (risk_config.json)
  bar-by-bar exit  (exit_policy_config.json)
             |
             v
  metrics + CSV/HTML outputs (codex-backed/results/)
```

### Key Directories

| Path | Purpose |
|------|---------|
| `codex-backed/src/codex_backed/` | CLI, feature builder, entry engine, trade simulator, risk, metrics, writers |
| `codex-backed/configs/` | All strategy/backtest/risk/exit JSON configs |
| `codex-backed/cache/prices.pkl` | OHLCV bar cache (pickle fallback for FMP) |
| `codex-backed/cache/fmp/` | FMP disk cache — JSON files, 24h TTL, populated on first run |
| `codex-backed/cache/features.pkl` | Native feature cache (invalidated by config hash) |
| `codex-backed/results/` | Backtest run artifacts |
| `codex-backed/scripts/` | Utility scripts (e.g. `fmp_access_audit.py`) |

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
| `backtest_ticker_universe_config.json` | Default broad ticker universe (200 tickers) |
| `watchlist_config.json` | Default daily analysis tickers |
| `data_provider_config.json` | Active data mode (`fmp_primary_yfinance_fallback`), provider settings |

### Data Provider Modes

`data_provider_config.json` controls how price and fundamentals data are sourced. The active mode is `fmp_primary_yfinance_fallback`.

| Mode | Prices | Fundamentals | When to use |
|------|--------|-------------|-------------|
| `fmp_primary_yfinance_fallback` | FMP → pickle | FMP → yfinance | Default — requires `FMP_API_KEY` |
| `legacy_yfinance` | pickle only | none | Offline / no-key fallback |

Pass `--data-mode <mode>` to override for a single run without touching the config.

### Feature Source

The default backtest feature source is `native` — computes features from OHLCV bars and caches to `features.pkl`.

`parent_csv` exists only as a debug/compatibility fallback. Never use it for real optimization.

## Current Baseline

**FMP production baseline (`fmp_baseline_02`)** — 200 tickers, 2018-01-02 → 2025-12-31, `fmp_primary_yfinance_fallback`:
- trades: 104 | avg return: 15.67% | median: 2.98% | win rate: 98.1% | profit factor: 160.6

All 104 trades use the `quality_dislocation` strategy in `BEAR_RISK_OFF` regime. 75% are from the 2020 COVID crash.

**Exit config (from 50-iteration loop, still current):**
- Short-term: target `2.375R`, partial sell `0%`, breakeven after target, trailing `2.5 ATR`, max `60` days
- Medium-term: target `2.0R`, partial sell `40%`, breakeven at `1.25R`, trailing `3.0 ATR`, max `90` days

## Key Conventions

- Always run `validate-config` after any config change before a backtest.
- For optimization: change config → run named backtest → inspect metrics → log the decision.
- When adding/removing backtest tickers, edit `backtest_ticker_universe_config.json` then validate.
- When adding/removing watchlist tickers, edit `watchlist_config.json` then validate.
- `analyze` always fetches fresh data; it does not read `prices.pkl` or `features.pkl`.
- The FMP disk cache (`cache/fmp/`) is populated on the first cold run. Subsequent runs are served from cache at no API cost — do not delete it between runs.
- SPY and QQQ are always fetched alongside the ticker universe for market regime detection. They are not in the trading universe config but the runner appends them automatically.

## Reference Docs

- `codex-backed/HLD.md` — architecture overview and operating model
- `codex-backed/LLD.md` — module, class, config, and data-flow design
- `codex-backed/BACKTEST_README.md` — backtest commands and output interpretation
- `codex-backed/docs/pre-refactoring-iterative-fine-tuning-logs/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` — completed 50-run exit optimization audit trail (legacy, pre-FMP)

### Iterative improvement loop (FMP era)

All files for the active optimization loop live in `codex-backed/iterative_improvements_using_backtests/`:

| File | Purpose |
|------|---------|
| `optimization_state.json` | Current best run, accepted metrics, tried array, next queue — read this first when resuming |
| `history.jsonl` | Append-only per-iteration record (full metrics + delta + decision) — never re-read by Claude unless asked |
| `optimization_memory.json` | Parameter values known to be rejected — consult before proposing a change |
| `FMP_BASELINE.md` | Canonical baseline metrics and extended-range experiment notes |
| `ITERATIVE_IMPROVEMENTS_PLAN.md` | Planned next improvements |
