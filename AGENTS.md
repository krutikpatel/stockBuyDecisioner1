# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.
Our base working directory is: "codex_backed" all changes shall remain inside this directory

## Commands

### Backend

```bash
cd backend
source .venv/bin/activate

# Run the API server
uvicorn app.main:app --reload --port 8000

# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run a single test file
PYTHONPATH=. pytest tests/test_signal_card_service.py -v

# Run a single test by name
PYTHONPATH=. pytest tests/test_signal_card_service.py::test_momentum_card_high -v

# Run backtest (from backend/ directory)
python -m backtest.run_backtest
python -m backtest.run_backtest --tickers AAPL,MSFT --start 2022-01-01 --end 2023-01-01 --phase 1
python -m backtest.run_backtest --algo-config /path/to/custom.json

# Run backtest with experiment tracking
python -m backtest.run_backtest --experiment-id my_run_01 --tickers AAPL,MSFT,NVDA

# Run walk-forward validation (replaces standard backtest when --walk-forward is passed)
python -m backtest.run_backtest --walk-forward --tickers AAPL,MSFT --start 2019-01-01 --end 2024-01-01
python -m backtest.run_walk_forward --tickers AAPL,MSFT --train-weeks 104 --test-weeks 26
```

### Frontend

```bash
cd frontend
npm run dev        # dev server on http://localhost:5173
npm test           # run Vitest tests (36 tests)
npm run build      # TypeScript check + Vite build
npm run lint       # ESLint
```

### Codex-Backed CLI

`codex-backed/` is a separate CLI-only strategy/backtest engine. It is intentionally independent from the frontend and from the production `backend/app` request path.

```bash
# Validate codex-backed JSON configs
PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli validate-config --config-dir codex-backed/configs

# Run codex-backed tests
backend/.venv/bin/python -m pytest codex-backed/tests -q

# Run a full native-feature backtest
PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id my_run_id \
  --rebuild-feature-cache \
  --workers 1

# Short smoke-style run examples are documented in codex-backed/BACKTEST_README.md
```

Use `--workers 1` by default in Codex sessions. Prior multiprocessing runs had sandbox/process-management friction, and the single-worker path is the known reliable path.

If `--tickers` is omitted, codex-backed backtests use `codex-backed/configs/backtest_ticker_universe_config.json`. Use `--tickers` only for temporary overrides or smoke tests.

## Architecture

### Request Flow

`POST /api/stocks/analyze` → `routers/stock.py` orchestrates:

1. **Data fetching** — five providers in `app/providers/` (yfinance wrappers): `market_data_provider`, `fundamental_provider`, `earnings_provider`, `news_provider`, `options_provider`
2. **Analysis** — services in `app/services/`:
   - `technical_analysis_service.py` — 55+ indicators (EMAs, RSI, MACD, ATR, OBV, CMF, VWAP, etc.)
   - `fundamental_analysis_service.py` — margins, FCF, ROE, ROIC, growth
   - `valuation_analysis_service.py` — P/E, PEG, EV/EBITDA, archetype-adjusted scoring
   - `news_sentiment_service.py` — OpenAI gpt-4o-mini (keyword fallback if no API key)
   - `stock_archetype_service.py` — classifies stock into 8 archetypes (e.g. High-Growth, Value, GARP)
   - `market_regime_service.py` — classifies SPY/VIX into 6 market regimes
3. **Signal Cards** — `signal_card_service.py` scores 11 cards (0–100 each): Momentum, Trend, Entry Timing, Volume/Accumulation, Volatility/Risk, Relative Strength, Growth, Valuation, Quality, Ownership, Catalyst
4. **Scoring** — `scoring_service.py` applies horizon-specific signal card weights → composite score per horizon
5. **Recommendation** — `recommendation_service.py` applies decision gates → per-horizon decision label + entry/exit/risk plan
6. **Report** — `markdown_report_service.py` generates a full markdown report

### AlgoConfig System

All tunable algorithm parameters live in `backend/algo_config.json` (12 sections). Services access them via a singleton:

```python
from app.algo_config import get_algo_config
cfg = get_algo_config()
period = cfg.technical_indicators["rsi_period"]
```

For tests and experiments, inject a custom config rather than relying on the singleton:

```python
from app.algo_config import AlgoConfig
cfg = AlgoConfig.from_dict({...})
result = compute_technicals(df, spy_df, algo_config=cfg)
```

Tests that mutate global state must call `reset_algo_config()` in teardown. The `ALGO_CONFIG_PATH` environment variable overrides the default JSON path.

See `backend/ALGO_PARAMS.md` for the full parameter catalog with descriptions.

### Config-Driven Strategy Engine

A second decision path sits behind a feature flag (`use_new_strategy_engine` in `algo_config.json`, default `false`). The new engine lives entirely in `backend/app/engine/` and `backend/app/features/`:

```
FeatureSnapshot (app/features/feature_snapshot.py)
  ↓  built by feature_builder.py from existing service models
TechnicalSignalDetector (engine/technical_signal_detector.py)
  ↓  signals defined in config/technical_setup_config.json
SetupDetector (engine/setup_detector.py)
  ↓  setups defined in same config
StrategyRouter (engine/strategy_router.py)
  ↓  routes defined in config/strategy_logic_config.json
ConfigDrivenStrategyEngine (engine/config_driven_strategy_engine.py)
  ↓  score rules + decision thresholds in JSON
StockDecisionEngine (engine/stock_decision_engine.py)
  orchestrates the above, returns list[HorizonRecommendation]
```

All strategy intelligence lives in 5 JSON files under `backend/config/`:
- `market_and_universe_config.json` — universe filters, regime rules, sector benchmarks
- `stock_classification_config.json` — archetype rules, 11 secondary tag rules
- `technical_setup_config.json` — 10 named signals, 4 setup definitions
- `strategy_logic_config.json` — strategy router (5 priority rules) + 5 strategy engines
- `parameter_governance_config.json` — frozen/active/research-only parameter tiers

To flip to the new engine: set `"use_new_strategy_engine": true` in `algo_config.json`. Recommended to test on NVDA, AAPL, and SPY first for parity check.

### Multi-Source Config

`backend/app/config/config_loader.py` provides `MultiSourceConfig` — loads all 5 JSON files above. Access via singleton:

```python
from app.config.config_loader import get_multi_config
cfg = get_multi_config()
filters = cfg.universe_filters
engines = cfg.strategy_engines
```

`reset_multi_config()` clears the singleton (required in tests that mutate it).

**Config package note:** `backend/app/config/` (package) shadows the old `backend/app/config.py` (module). The package `__init__.py` re-exports `Settings` and `settings` to maintain backward compatibility — do not revert this.

### Data Layer Abstraction

`backend/app/data/` provides a pluggable provider interface:

```python
from app.data.providers.provider_factory import ProviderFactory
p = ProviderFactory.create("yfinance")   # or omit name to read from config
df = p.get_price_history("AAPL", "2023-01-01", "2023-06-01")
```

- `app/data/providers/base.py` — abstract `MarketDataProvider` with 6 methods
- `app/data/providers/yfinance_provider.py` — delegates to existing `app/providers/` functions
- `app/data/providers/provider_factory.py` — reads `active_provider` from `market_and_universe_config.json`
- `app/data/cache/parquet_store.py` — persistent parquet cache for backtests (`has_coverage`, `read`, `write`)
- `app/data/cache/cache_metadata.py` — provenance JSON alongside each parquet shard

### Backtest System

`backend/backtest/` replays the full signal pipeline across historical dates using downloaded price snapshots. Key files:

- `run_backtest.py` — CLI entry point (supports `--experiment-id`, `--walk-forward`)
- `runner.py` — iterates tickers × dates × horizons, calls production services
- `data_loader.py` + `indicator_cache.py` — downloads and caches yfinance data
- `outcome.py` — computes forward returns, MAE (`max_drawdown_period`), MFE (`mfe_pct`); optional `entry_method`/`exit_method` params write `sim_*` columns
- `metrics.py` — aggregates by decision, regime, archetype, score bucket, setup, strategy; includes Sharpe/Sortino/Calmar in `overall_stats`
- `report.py` — generates `results/report.html`
- `entry_simulator.py` — 5 entry methods: NEXT_CLOSE, NEXT_OPEN, PULLBACK_TO_SMA20/50, BREAKOUT_CONFIRMATION
- `exit_simulator.py` — 3 exit methods: FIXED_HORIZON, ATR_STOP_TARGET, TRAILING_STOP
- `walk_forward.py` — rolling IS/OOS folds; `WalkForwardValidator.run()` returns consistency score
- `experiment_tracker.py` — `ExperimentTracker` saves manifests to `backtest/experiments/`; compare runs with `compare_to_baseline()`
- `run_walk_forward.py` — dedicated CLI for walk-forward validation

Results land in `backend/backtest/results/` as CSVs + HTML.

### Codex-Backed Strategy Engine

`codex-backed/` is the newer buy/sell-separated engine built during this project. It uses native historical OHLCV feature generation and a JSON-only configuration model.

Important files:
- `codex-backed/src/codex_backed/` — CLI, feature builder, entry engine, trade simulator, risk, metrics, writers
- `codex-backed/configs/` — all strategy/backtest/risk/exit JSON configs
- `codex-backed/configs/backtest_ticker_universe_config.json` — default broad ticker universe for backtests
- `codex-backed/results/` — backtest run artifacts
- `codex-backed/cache/features.pkl` — native feature cache
- `codex-backed/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` — audit trail for the 50-run optimization loop
- `codex-backed/HLD.md`, `codex-backed/LLD.md`, `codex-backed/README.md`, `codex-backed/BACKTEST_README.md` — design and usage docs

Backtest data flow:

```
cached OHLCV bars
  -> native historical feature builder
  -> setup detection from technical_setup_config.json
  -> entry routing from entry_signal_config.json
  -> risk sizing from risk_config.json
  -> bar-by-bar exit simulation from exit_policy_config.json
  -> metrics/report CSV/HTML outputs
```

The default feature source should remain `native`. `parent_csv` exists only as a debug/compatibility fallback and must not be used for real optimization because old parent signal CSV fields can hide missing historical setup data.

#### Current Codex-Backed Baseline

The completed 50-iteration optimization loop selected `loop50_49` as the best average-return run.

Best tested short-term exit config:
- target 1 / breakeven trigger: `2.375R`
- partial sell at target 1: `0%`
- move stop to breakeven after target: `true`
- trailing stop: `2.5 ATR`
- max simulation days: `60`

Medium-term exit config remains:
- target 1: `2.0R`
- partial sell: `40%`
- breakeven trigger: `1.25R`
- trailing stop: `3.0 ATR`
- max simulation days: `90`

Best run metrics from `codex-backed/results/loop50_49`:
- decisions: `161,842`
- trades: `1,082`
- avg return: `9.1276%`
- median return: `7.6729%`
- win rate: `58.3179%`
- profit factor: `5.0810`

Main tradeoff: this final config optimized absolute return, not smoothness. Compared with the smoother `loop50_38` baseline, avg return improved from `9.0335%` to `9.1276%`, but median return fell from `8.8654%` to `7.6729%` and win rate fell from `58.5952%` to `58.3179%`.

Do not restart the 50-loop automation; it was completed and the heartbeat automation was deleted. If more tuning is requested, start a new named run series and append a new audit log instead of overwriting `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`.

### Frontend

React 18 + TypeScript + Vite + Tailwind CSS v4. The Vite dev server proxies `/api` to `http://localhost:8000`. Main entry point is `src/pages/Dashboard.tsx`. Types are defined in `src/types/stock.ts`; API calls in `src/api/stockApi.ts`.

### Caching

TTLCache (cachetools) inside `app/cache/`: 15-minute TTL for price data, 24-hour TTL for fundamentals. yfinance 429 rate limits are handled with tenacity exponential backoff.

## Key Conventions

- All service functions accept an optional `algo_config: Optional[AlgoConfig] = None` parameter — pass `None` in production (uses singleton), pass a custom instance in tests.
- Data providers return typed Pydantic models; the analysis pipeline is fully decoupled from the data source.
- Missing data is handled gracefully everywhere — optional fields stay `None` and are excluded from scoring with a note in `missing_data_warnings`.
- Decision labels are horizon-specific sets: short-term has 4 labels, medium-term has 5, long-term has 4.
- The new config-driven engine does **not** differentiate by horizon — all 3 horizons receive the same strategy score and label. Horizon-specific scoring can be added to `strategy_logic_config.json` later.
- `signal_cards` are always computed in `routers/stock.py` regardless of which engine is active — this fixed a pre-existing gap where the legacy path never populated them.
- Tests that use `MultiSourceConfig` must call `reset_multi_config()` in teardown, same as `reset_algo_config()`.
- When adding a new `MarketDataProvider` implementation, register it in `provider_factory.py`'s `_load_registry()`. The factory reads `active_provider` from `market_and_universe_config.json` at runtime.
- Keep `codex-backed` configs pure JSON. Avoid YAML/TOML unless the user explicitly changes that constraint.
- For codex-backed optimization, change config first, run a named backtest, inspect metrics, then log the decision. Do not tune from stale or parent CSV-derived features.
