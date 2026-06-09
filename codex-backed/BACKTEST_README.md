# Backtest README

This document explains how to run and interpret `codex-backed` lifecycle backtests.

## What Makes This Backtest Different

The old backtest measured fixed returns at exact horizons such as 20 trading days and 63 trading days.

`codex-backed` instead simulates a trade lifecycle:

```text
entry signal
  -> simulated entry
  -> initial stop
  -> target 1
  -> partial profit
  -> breakeven stop
  -> trailing stop
  -> time stop or max simulation window
```

Short-term and medium-term horizons are maximum windows, not forced sell dates.

## Current Data Sources

Default mode uses:

- Price bars: `codex-backed/cache/prices.pkl`
- Native generated features: `codex-backed/cache/features.pkl`

Configured in:

```text
codex-backed/configs/backtest_config.json
codex-backed/configs/backtest_ticker_universe_config.json
```

Native mode computes setup-critical fields directly from OHLCV history: SMA relatives/slopes, RSI and RSI slope, ATR%, weekly/monthly performance, distance from highs/lows, volume dry-up, breakout volume multiple, up/down volume ratio, trend label, SPY-relative strength, and SPY-derived market regime.

The old parent signal CSV remains available as an explicit debug fallback with `--feature-source parent_csv`. It no longer fabricates raw fields from signal-card scores.

## Default Ticker Universe

If `--tickers` is omitted, backtests use the default universe in:

```text
codex-backed/configs/backtest_ticker_universe_config.json
```

Use `--tickers AAPL,MSFT` only for a temporary override or smoke test. Edit `backtest_ticker_universe_config.json` when the default broad backtest universe should change.

## Basic Command

Run from repository root:

```bash
codex-backed/.venv/bin/codex-backed backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id my_run \
  --start 2022-01-01 \
  --end 2024-12-31 \
  --workers 1
```

Use `--workers 1` for deterministic debugging. Use more workers for faster runs when the environment allows multiprocessing.

## CLI Options

```text
--config-dir              JSON config directory
--output-dir              result output directory
--run-id                  explicit result run id
--tickers                 comma-separated tickers
--start                   start date, YYYY-MM-DD
--end                     end date, YYYY-MM-DD
--workers                 process count
--feature-source          native or parent_csv
--force-refresh           rebuild native feature cache
--rebuild-feature-cache   rebuild native feature cache
--no-report               skip HTML report
```

## Example Smoke Test

```bash
codex-backed/.venv/bin/codex-backed backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id smoke_real_report \
  --tickers AAPL,MSFT \
  --start 2022-01-01 \
  --end 2022-03-31 \
  --workers 1
```

Expected output shape:

```text
status: ok
entry_decisions: non-zero
trades: zero or more, depending on actionability
errors: ideally zero
run_dir: codex-backed/results/<run_id>
```

## Output Files

Each run writes:

```text
manifest.json
entry_decisions.csv
trades.csv
metrics.json
by_entry_label.csv
by_entry_strategy.csv
by_entry_setup.csv
by_horizon.csv
by_market_regime.csv
by_exit_reason.csv
by_ticker.csv
report.html
```

If row-level errors occur:

```text
errors.csv
```

## `entry_decisions.csv`

This file records every entry decision before trade simulation.

Important columns:

```text
ticker
date
horizon
entry_label
entry_score
confidence
selected_setup
entry_strategy
is_actionable
market_regime
archetype
reasons
missing_data
source_decision
source_setup
source_strategy
```

How to read it:

- `BUY_STARTER`, `BUY_FULL`, and `BUY_AGGRESSIVE` are actionable.
- `WATCHLIST` and `NO_TRADE` are not simulated as trades.
- `reasons` explains which score rules fired.
- `missing_data` shows what the config wanted but the current feature row did not provide.
- In native mode, `source_*` columns are blank. In `parent_csv` mode, they show the parent backtest label/setup/strategy that produced the feature row.

## `trades.csv`

This file records only actionable entries that successfully triggered an entry execution and passed sizing rules.

Important columns:

```text
ticker
signal_date
horizon
entry_label
entry_strategy
selected_setup
entry_date
entry_price
entry_method
position_size_multiplier
initial_stop
target_1
target_1_hit
partial_exit_pct
exit_date
exit_price
exit_reason
days_held
realized_return_pct
mae_pct
mfe_pct
mfe_capture_pct
market_regime
archetype
```

How to read it:

- `realized_return_pct` is the primary result.
- `mae_pct` is worst adverse move during the trade.
- `mfe_pct` is best favorable move during the trade.
- `mfe_capture_pct` tells how much of available upside the exit policy captured.
- `exit_reason` explains what ended the trade.

## Exit Reasons

Common exit reasons:

```text
STOP_LOSS_EXIT
PARTIAL_PROFIT_TAKEN
TRAILING_STOP_EXIT
TIME_STOP_EXIT
MAX_SIM_WINDOW_EXIT
```

Note: `PARTIAL_PROFIT_TAKEN` is an event, not necessarily the final exit reason. The final trade row shows the final exit reason.

## `metrics.json`

Top-level sections:

```text
overall
entry_decisions
by_entry_label
by_entry_strategy
by_entry_setup
by_horizon
by_market_regime
by_exit_reason
by_ticker
input_quality
```

Primary metric:

```text
avg_return_pct
```

Other useful metrics:

```text
median_return_pct
win_rate_pct
profit_factor
count
```

## Sliced CSVs

Use sliced CSVs to answer targeted questions:

- `by_entry_label.csv`: which entry labels work?
- `by_entry_strategy.csv`: which strategy family works?
- `by_entry_setup.csv`: which detected technical setup works?
- `by_horizon.csv`: short-term vs medium-term behavior.
- `by_market_regime.csv`: which regimes support entries?
- `by_exit_reason.csv`: what exits dominate results?
- `by_ticker.csv`: which tickers drive performance?

## Input Quality Checks

Before interpreting performance, check `metrics.json -> input_quality` or the HTML report:

- `feature_source` should be `native` for normal runs.
- `feature_cache_status` should be `rebuilt` on first run and `hit` on repeated identical runs.
- `missing_field_counts` should not show globally missing setup-critical fields.
- `decision_setup_distribution` should include real setup names when the market produces matching setups.
- `actionable_by_setup` shows whether entries are coming from real setups or broad technical routes.

## Current Entry-Filter Experiment

The config now applies the first post-`my_run_02` filter pass:

- `BROKEN_CHART_QUALITY_RECOVERY` is promoted only in `BEAR_RISK_OFF` and `SIDEWAYS_CHOPPY`.
- `GROWTH_LEADER_PULLBACK` requires at least one confirmation signal.
- `GROWTH_LEADER_PULLBACK` is blocked in `LIQUIDITY_RALLY`.
- Broad `bull_leadership` can produce only `BUY_STARTER` or `WATCHLIST`.
- `extended_starter` remains starter-only.
- Weak tickers from `my_run_02` are routed to `NO_TRADE`.

Do not tune exits again until this filtered entry run is reviewed against `my_run_02`.

## Parallel Runs

Use:

```bash
--workers 4
```

Current implementation uses one worker task per ticker, matching the good pattern from `backend/backtest`.

If process spawning is blocked by the environment, use:

```bash
--workers 1
```

## Interpreting Results

Do not evaluate the engine by fixed 20D or 63D return. The lifecycle result is the trade result.

Good signs:

- Positive average realized return.
- Positive median return.
- Profit factor above 1.
- Reasonable MAE.
- `BUY_FULL` outperforms `BUY_STARTER`.
- Exit reasons include profitable trailing exits, not only stop losses.
- Results are not driven by one ticker only.

Bad signs:

- High actionable count but poor realized return.
- `BUY_AGGRESSIVE` underperforms.
- Stop losses dominate.
- `selected_setup` is always `None`.
- Setup-critical fields appear in `missing_field_counts`.
- MFE is high but realized return is low, meaning exits are poor.
- One market regime drives all gains.

## Current Known Limitations

- Uses parent feature CSV rather than native feature generation.
- Some raw features are proxied from signal cards.
- HTML report is basic.
- Optimizers are not wired yet.

## Recommended Backtest Workflow

1. Start small with `--tickers AAPL,MSFT --workers 1`.
2. Inspect `entry_decisions.csv` for label quality and missing data.
3. Inspect `trades.csv` for exit behavior.
4. Review `metrics.json` and sliced CSVs.
5. Expand ticker universe.
6. Increase worker count if available.
7. Tune JSON configs.
8. Re-run and compare run directories.
