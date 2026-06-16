# Backtest README

This document explains how to run and interpret `codex-backed` lifecycle backtests.

## What Makes This Backtest Different

The old backtest measured fixed returns at exact horizons such as 20 trading days and 63 trading days.

`codex-backed` instead simulates a trade lifecycle:

```text
entry signal
  -> simulated entry (NEXT_OPEN)
  -> initial stop (ATR-based)
  -> target 1 (R multiple)
  -> partial profit (optional)
  -> breakeven stop
  -> trailing stop
  -> time stop or max simulation window
```

Short-term and medium-term horizons are **maximum windows**, not forced sell dates. The exit policy closes the trade as soon as stop, profit, or time logic fires.

## Active Data Source

The default mode is `fmp_primary_yfinance_fallback`:

| Data | Source |
|------|--------|
| Historical prices (backtest) | FMP `/stable/historical-price-eod/full` → `prices.pkl` fallback |
| Live prices (analyze) | FMP `/stable/historical-price-eod/full` → yfinance fallback |
| Fundamentals | FMP `/stable/key-metrics`, `/stable/ratios`, `/stable/financial-growth`, `/stable/profile`, `/stable/earnings` → yfinance fallback |
| Market regime | SPY SMA50/SMA200 (from price provider above) |

FMP data is disk-cached at `codex-backed/cache/fmp/`. A cold run fetches ~600 API calls across 200 tickers; all subsequent runs are served from the cache instantly.

FMP history confirmed available back to **2000-01-03**. Current backtest starts 2018 — extending to 2010 is a one-line config change and would cover the 2008 crash.

### Without FMP key

Force the legacy pickle-only mode for an offline run:

```bash
--data-mode legacy_yfinance
```

Prices come from `prices.pkl`, fundamentals are not populated.

## Running a Backtest

All commands run from the repo root. Export your FMP key before every command:

```bash
set -a; source .env; set +a
```

### Full backtest (all tickers, full date range)

```bash
set -a; source .env; set +a
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id my_run_01 \
  --rebuild-feature-cache \
  --workers 1
```

### Smoke test (2 tickers, fast)

```bash
set -a; source .env; set +a
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id smoke_01 \
  --tickers AAPL,MSFT \
  --rebuild-feature-cache \
  --workers 1
```

Note: AAPL and MSFT rarely trigger the `quality_dislocation` entry. Use a broader set like `AIG,CCL,MU,XOM` if you want to see trades in a smoke test.

### Custom date range

```bash
set -a; source .env; set +a
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id bear_2020 \
  --start 2020-01-01 \
  --end 2020-12-31 \
  --rebuild-feature-cache \
  --workers 1
```

## CLI Reference

```text
--config-dir              JSON config directory
--output-dir              result output directory
--run-id                  explicit result run id
--tickers                 comma-separated tickers (omit for full universe)
--start                   start date, YYYY-MM-DD (default: from backtest_config.json)
--end                     end date, YYYY-MM-DD (default: from backtest_config.json)
--workers                 process count (default: 1)
--feature-source          native (default) or parent_csv (debug fallback)
--force-refresh           alias for --rebuild-feature-cache
--rebuild-feature-cache   force feature rebuild even if cache is valid
--no-report               skip HTML report generation
--data-mode               override active_mode from data_provider_config.json
```

Use `--workers 1` for deterministic debugging. Increase only if the environment supports multiprocessing without sandbox restrictions.

## Daily Analysis (Live Signals)

Run each morning before market open:

```bash
set -a; source .env; set +a
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli analyze \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id today_watchlist
```

This fetches fresh FMP prices and fundamentals for tickers in `watchlist_config.json`, runs the full entry engine, and writes results to `codex-backed/results/today_watchlist/`.

### Reading the output

Open `entry_decisions.csv` and filter `is_actionable = true`:

| Column | What to check |
|--------|---------------|
| `ticker` | Which stock |
| `entry_label` | `BUY_STARTER` / `BUY_FULL` / `BUY_AGGRESSIVE` — conviction level |
| `entry_score` | Higher = stronger signal |
| `selected_setup` | Technical pattern that fired |
| `entry_strategy` | Strategy family (e.g. `quality_dislocation`, `bull_leadership`) |
| `reasons` | Scoring rules that fired — sanity-check the signal here |
| `horizon` | `short_term` (≤60 days) or `medium_term` (≤90 days) |

Priority order: `BUY_AGGRESSIVE` > `BUY_FULL` > `BUY_STARTER`. `WATCHLIST` = monitor, no entry yet.

### Exit discipline (current best config)

- **Short-term:** initial stop → 2.375R target → move stop to breakeven → 2.5 ATR trailing → 60-day max
- **Medium-term:** initial stop → 2.0R target (take 40% off) → 1.25R breakeven → 3.0 ATR trailing → 90-day max

## Output Files

```text
manifest.json                     run metadata, config snapshot, git commit
entry_decisions.csv               every decision for every ticker/date/horizon
trades.csv                        simulated trades with full lifecycle detail
metrics.json                      overall + sliced performance metrics
by_entry_label.csv
by_entry_strategy.csv
by_entry_setup.csv
by_horizon.csv
by_market_regime.csv
by_exit_reason.csv
by_ticker.csv
report.html                       summary HTML report
run_metrics_data_layer.json       provider-level stats (cache hits, errors, latency)
errors.csv                        row-level errors if any occurred
```

## Understanding `entry_decisions.csv`

Every decision is recorded before trade simulation.

Key columns:
```text
ticker, date, horizon, entry_label, entry_score, confidence
selected_setup    — technical pattern (e.g. BROKEN_CHART_QUALITY_RECOVERY)
entry_strategy    — which scoring engine was used
is_actionable     — true if BUY_*
market_regime     — BULL_RISK_ON / BEAR_RISK_OFF / SIDEWAYS_CHOPPY / LIQUIDITY_RALLY
reasons           — pipe-separated scoring rules that fired
missing_data      — fields the config wanted but the feature row lacked
```

`reasons` is your primary debugging tool. If a stock is WATCHLIST and you expected BUY_FULL, compare its `reasons` against the score thresholds in `entry_signal_config.json`.

## Understanding `trades.csv`

Only actionable entries that triggered a valid entry execution appear here.

Key columns:
```text
ticker, signal_date, horizon, entry_label, entry_strategy, selected_setup
entry_date, entry_price, entry_method
initial_stop, target_1, target_1_hit, partial_exit_pct
exit_date, exit_price, exit_reason, days_held
realized_return_pct   — primary result
mae_pct               — worst adverse excursion
mfe_pct               — best favorable excursion
mfe_capture_pct       — how much available upside the exit policy captured
market_regime, archetype
```

## Understanding `metrics.json`

Top-level sections:
```text
overall
by_entry_label
by_entry_strategy
by_entry_setup
by_horizon
by_market_regime
by_exit_reason
by_ticker
entry_decisions
input_quality
```

Primary metric: `avg_return_pct`. Also check `median_return_pct`, `win_rate_pct`, `profit_factor`, `count`.

## Sliced CSVs

| File | Question it answers |
|------|---------------------|
| `by_entry_label.csv` | Do higher-conviction labels outperform? |
| `by_entry_strategy.csv` | Which strategy family drives results? |
| `by_entry_setup.csv` | Which detected technical pattern works? |
| `by_horizon.csv` | Short-term vs medium-term behavior |
| `by_market_regime.csv` | Which regimes produce trades? |
| `by_exit_reason.csv` | What exits dominate? (trailing stop is better than stop loss) |
| `by_ticker.csv` | Which tickers drive performance? Are results concentrated? |

## Current Baseline

**`fmp_baseline_02`** — 200 tickers, 2018-01-02 → 2025-12-31, `fmp_primary_yfinance_fallback`:

| Metric | Value |
|--------|-------|
| Trades | 104 |
| Avg return | 15.67% |
| Median return | 2.98% |
| Win rate | 98.1% |
| Profit factor | 160.6 |

Key characteristics:
- All 104 trades use `quality_dislocation` strategy in `BEAR_RISK_OFF` regime
- 78 of 104 trades (75%) from the 2020 COVID crash
- Short-term profit factor 226, medium-term 111
- 46% trailing stop exits, 41% stop loss exits, 13% max-window exits
- 38 of 200 tickers produced at least one trade

Bull market strategies (`bull_leadership`, `oversold_rebound`, `breakout_entry`) detect setups but never reach the BUY threshold. BULL_RISK_ON accounts for 50% of decision rows but 0% of trades — the primary tuning opportunity.

## Input Quality Checks

Before interpreting performance, verify `metrics.json → input_quality` or the HTML report:

- `feature_source` should be `native`.
- `feature_cache_status` should be `rebuilt` on first run and `hit` on repeated runs with the same config.
- `missing_field_counts` should not show setup-critical fields missing globally.
- `decision_setup_distribution` should include real setup names (not all blank).
- `actionable_by_setup` shows which setups produce BUY decisions.

In the `run_metrics_data_layer.json`, check `fmp.api_errors_by_status` — a high count of `429` errors means the rate limit was hit repeatedly and some tickers may have missing fundamentals. The FMP cache prevents this on subsequent runs.

## Good and Bad Signs

Good signs:
- Positive avg and median realized return
- Profit factor above 2.0
- `BUY_FULL` outperforms `BUY_STARTER`
- Trailing stop exits dominate over stop losses
- Results spread across multiple tickers and years
- `mfe_capture_pct` above 50% (exit policy captures meaningful upside)

Bad signs:
- High actionable count but poor realized return
- Stop losses dominate (41% in current baseline — entry timing opportunity)
- `selected_setup` is always blank (technical setups not detecting)
- Setup-critical fields in `missing_field_counts`
- MFE is high but realized return is low (exit policy leaving money on the table)
- All gains from one market regime or one crash year

## Recommended Backtest Workflow

1. Validate config: `validate-config --config-dir codex-backed/configs`
2. Run a smoke test on 3–5 tickers that historically produce trades (e.g. `AIG,CCL,MU,XOM,GE`)
3. Inspect `entry_decisions.csv` — check regime, setup, strategy, and reasons
4. Inspect `trades.csv` — check exit reasons and MFE capture
5. Review `metrics.json` and sliced CSVs
6. Run the full 200-ticker universe
7. Compare run directories (use different `--run-id` for each experiment)
8. Log every decision in the relevant audit log before starting the next iteration

## Managing the Ticker Universe

Edit `backtest_ticker_universe_config.json` to add or remove tickers. Always validate after changes.

For new tickers: FMP will fetch their price history on the next cold run. No other prep needed.

SPY and QQQ do not need to be in this file — the runner fetches them automatically for regime detection.

## FMP Cache Management

The FMP disk cache is at `codex-backed/cache/fmp/`. Do not delete it between runs — it saves all API calls on subsequent runs.

The cache TTL is 24 hours. To force a fresh fetch from FMP for fundamentals data:
```bash
rm codex-backed/cache/fmp/fundamentals_*.json
```

To force a fresh price fetch:
```bash
rm codex-backed/cache/fmp/history_*.json
```
