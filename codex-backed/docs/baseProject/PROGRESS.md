# Codex-Backed Implementation Progress

This tracker follows `IMPLEMENTATION_PLAN.md`.

## Current Status

Native historical backtest inputs are now implemented. The default backtest path computes technical/setup features from cached OHLCV bars instead of relying on the parent signal CSV.

## Milestone Progress

| Milestone | Story | Status | Notes |
|---|---|---|---|
| 0 | 0.1 Create Design Documentation | Complete | `README.md`, `DESIGN.md`, and `IMPLEMENTATION_PLAN.md` exist. |
| 1 | 1.1 Create Python Package Skeleton | Complete | Package directories and `pyproject.toml` created. |
| 1 | 1.2 Add CLI Entrypoint | Complete | CLI commands scaffolded with config validation gate. |
| 1 | 1.3 Add Result Directory Convention | Complete | Run path and manifest helper added. |
| 2 | 2.1 Add New JSON Config Files | Complete | Added new JSON defaults and adapted existing technical/universe/classification configs. |
| 2 | 2.2 Implement Config Loader | Complete | Loads required JSON files from `--config-dir` and fails fast on missing/invalid JSON. |
| 2 | 2.3 Implement Config Validation | Complete | Validates labels, horizons, operators, and core exit/risk bounds; tests pass. |
| 3 | 3.1 Port JSON Rule Engine | Complete | Rule engine ported with operator/composition/missing-field tests passing. |
| 3 | 3.2 Implement New FeatureSnapshot | Complete | Snapshot includes technical/fundamental/classification fields and signal-card scores. |
| 3 | 3.3 Implement FeatureBuilder Adapter | In Progress | Added flat mapping adapter with tests; richer service-model adapters still pending. |
| 5 | 5.1 Implement Entry Setup Detector | Complete | Detector supports copied `technical_setups` and future `entry_setups`; tests pass. |
| 5 | 5.2 Implement Entry Router | Complete | Priority-first entry router added and tested. |
| 5 | 5.3 Implement Entry Strategy Scoring | Complete | Score rules, thresholds, confidence, and reasons added and tested. |
| 5 | 5.4 Add Initial Entry Strategies | Complete | Initial strategies are configured in `entry_signal_config.json`. |
| 6 | 6.1 Implement Entry Execution Simulator | Complete | List-of-dict OHLCV simulator added and tested. |
| 6 | 6.2 Implement Stop and Target Calculator | Complete | ATR/support stop and R target helper added and tested. |
| 6 | 6.3 Implement Position Sizing Policy | Complete | Label sizing plus high-ATR and earnings caps added and tested. |
| 7 | 7.1 Implement Trade Simulation Loop | Complete | Bar-by-bar simulator added and tested. |
| 7 | 7.2 Implement Partial Profit Taking | Complete | Partial profit event support added and tested. |
| 7 | 7.3 Implement Stop Move to Breakeven | Complete | Breakeven stop event support added and tested. |
| 7 | 7.4 Implement ATR Trailing Stop | Complete | ATR trailing stop support added and tested. |
| 7 | 7.5 Implement Time Stop | Complete | Time stop support added and tested. |
| 7 | 7.6 Compute Trade Metrics | Complete | Per-trade realized return, MAE, MFE, MFE capture, and days held computed by simulator. |
| 9 | 9.1 Build Trade Metrics | Complete | Aggregate lifecycle metrics added and tested. |
| B1 | Backtest CLI Arguments | Complete | Added `--tickers`, `--start`, `--end`, `--workers`, `--force-refresh`, `--rebuild-feature-cache`, and `--no-report`. |
| B2 | Data Cache Loader | Complete | Loads `codex-backed/cache/prices.pkl`; parent signal CSV remains debug-only fallback. |
| B3 | Bar Normalization | Complete | Converts OHLCV DataFrames to normalized list-of-dict bars. |
| B8 | Worker Implementation | Complete | Per-ticker worker runs entry decisions and lifecycle trade simulation. |
| B9 | Parallel Runner | Complete | Supports serial debug and `ProcessPoolExecutor` ticker workers. |
| B10 | Artifact Writer | Complete | Writes entry decisions, trades, metrics, sliced metrics, and HTML report. |
| B11 | Wire CLI Backtest | Complete | `codex-backed backtest` now runs the lifecycle backtest. |
| B12 | HTML Report | Complete | Diagnostic report includes input quality, setup distribution, entry quality, horizon quality, and exit quality. |
| N1 | Native Historical Feature Builder | Complete | Computes setup-critical OHLCV features, SPY relative strength, and SPY-derived market regime. |
| N2 | Native Feature Cache | Complete | Persistent feature cache keyed by source, tickers, date range, horizons, signal frequency, and config hash. |
| N3 | Backtest Source Selection | Complete | Default source is `native`; `parent_csv` remains as explicit debug fallback. |
| N4 | Setup-Aware Entry Routing | Complete | Entry config now uses native technical setups/confirmations and no fabricated fundamentals. |
| N5 | Backtest Diagnostics | Complete | Metrics/report expose missing fields, setup distribution, actionable-by-setup, and horizon slices. |
| N6 | First Config Tuning Pass | Complete | `BUY_AGGRESSIVE` tightened/downgraded; partial targets lowered; early breakeven config added. |
| N7 | Post-my_run_02 Entry Filter Plan | Complete | `NEXT_IMPROVEMENTS_PLAN.md` captures the seven proposed improvements. |
| N8 | Post-my_run_02 Entry Filters | Complete | Quality recovery regime-gated, liquidity pullbacks blocked, pullbacks require confirmation, broad leadership downgraded, weak tickers excluded. |
| N9 | Five-Loop Config Optimization | Complete | `ITERATIVE_IMPROVEMENTS_LOG.md` records five full backtest loops and resulting config changes. |

## Decisions Locked

- New work lives under `codex-backed/`.
- CLI-only; no frontend.
- Config remains pure JSON.
- Entry and exit engines are optimized separately.
- Historical backtests simulate exits for every buy signal.
- Fixed 20D/63D returns are diagnostics only, not primary sell assumptions.
- Primary optimization objective is absolute realized return.

## Next Steps

1. Run `my_run_03` and compare against `my_run_02`.
2. Review whether entry filters improved average return, profit factor, and stop-loss rate.
3. Tune exit configs separately for short-term and medium-term windows only after `my_run_03` entry quality is reviewed.
4. Add optimizer commands for entry and exit parameter sweeps.
5. Add native fundamentals/signal-card adapters if production parity becomes necessary.

## Current Limitations

- Native feature generation is technical/OHLCV-first. Point-in-time fundamentals and historical signal-card parity are not implemented yet.
- `parent_csv` mode is available only as a debug fallback and does not fabricate missing raw fields.
- Optimization commands are still scaffolded; parameter sweeps are not implemented yet.

## Verification Log

- `backend/.venv/bin/python -m pytest codex-backed/tests -q` -> 7 passed.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli --help` -> passed.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli validate-config --config-dir codex-backed/configs` -> passed.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest --config-dir codex-backed/configs --output-dir codex-backed/results --run-id smoke_run` -> created scaffold manifest.
- `backend/.venv/bin/python -m pytest codex-backed/tests/test_entry_engine.py -q` -> 4 passed.
- `backend/.venv/bin/python -m pytest codex-backed/tests -q` -> 18 passed.
- `backend/.venv/bin/python -m pytest codex-backed/tests -q` -> 19 passed.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest --config-dir codex-backed/configs --output-dir codex-backed/results --run-id smoke_real_report --tickers AAPL,MSFT --start 2022-01-01 --end 2022-03-31 --workers 1` -> 52 entry decisions, 10 trades, full artifact set.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest --config-dir codex-backed/configs --output-dir codex-backed/results --run-id smoke_real_2w_b --tickers AAPL,MSFT --start 2022-01-01 --end 2022-03-31 --workers 2 --no-report` -> 52 entry decisions, 10 trades, verified multiprocessing path with escalation.
- `backend/.venv/bin/python -m pytest codex-backed/tests -q` -> 23 passed.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli validate-config --config-dir codex-backed/configs` -> passed.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest --config-dir codex-backed/configs --output-dir codex-backed/results --run-id native_smoke_aapl_msft_v2 --tickers AAPL,MSFT --start 2022-01-01 --end 2022-03-31 --workers 1` -> native source rebuilt feature cache, 52 decisions, 12 trades, 0 errors.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest --config-dir codex-backed/configs --output-dir codex-backed/results --run-id native_smoke_aapl_msft_v2_cache --tickers AAPL,MSFT --start 2022-01-01 --end 2022-03-31 --workers 1 --no-report` -> native source cache hit, same 52 decisions and 12 trades.
- `backend/.venv/bin/python -m pytest codex-backed/tests -q` -> 25 passed after post-`my_run_02` entry-filter changes.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli validate-config --config-dir codex-backed/configs` -> passed after post-`my_run_02` entry-filter changes.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli backtest --config-dir codex-backed/configs --output-dir codex-backed/results --run-id my_run_03_workers1 --rebuild-feature-cache --workers 1` -> 161842 decisions, 41522 trades, 0 errors. Overall avg return improved from `my_run_02` 0.7717% to 0.9325%; profit factor improved from 1.3511 to 1.4201.
- Five-loop serial optimization runs `iter_01` through `iter_05` completed with 0 errors each. Measured avg return improved from 0.9325% to 2.1711%; profit factor improved from 1.4201 to 1.8721; stop-loss rate improved from 60.0429% to 55.2228%.
- `backend/.venv/bin/python -m pytest codex-backed/tests -q` -> 25 passed after final five-loop config changes.
- `PYTHONPATH=codex-backed/src backend/.venv/bin/python -m codex_backed.cli validate-config --config-dir codex-backed/configs` -> passed after final five-loop config changes.
