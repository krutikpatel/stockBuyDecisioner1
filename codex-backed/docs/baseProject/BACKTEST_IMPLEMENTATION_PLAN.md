# Backtest Implementation Plan

This plan implements the real `codex-backed backtest` command. It reuses the good architectural parts of `backend/backtest` while adapting them to the new entry/exit lifecycle engine.

## Current State

Already implemented in `codex-backed`:

- Config loader and validation.
- Rule engine.
- Feature snapshot model.
- Entry setup detector.
- Entry router and scorer.
- Entry execution simulator.
- Stop/target calculator.
- Position sizing.
- Trade simulator with partial profits, breakeven stop, ATR trailing stop, and time stop.
- Trade metrics aggregation.

Not implemented yet:

- Historical data loader.
- Historical feature generation.
- Parallel backtest runner.
- CSV/JSON output writing.
- Lifecycle HTML report.
- Optimization runner.

## Parent Backtest Features To Reuse

The existing `backend/backtest` has several good patterns that should be retained.

### 1. Per-Ticker Parallelism

`backend/backtest/runner.py` processes one ticker per worker using `ProcessPoolExecutor`.

Keep this pattern:

```text
main process:
  build test dates
  load caches
  precompute shared date state
  build one work item per ticker
  submit each ticker to ProcessPoolExecutor

worker process:
  process all dates for one ticker
  return entry decisions and trades for that ticker
```

Why this is good:

- Ticker-level work is naturally independent.
- It avoids tiny tasks per ticker/date, which would create too much process overhead.
- It keeps each worker's hot data local while iterating through dates.
- It makes progress reporting simple.

### 2. Worker Initializer

The parent runner uses an initializer to load shared read-only state into process globals once.

Keep this pattern:

```text
_worker_init(shared_date_state, configs, feature_cache_metadata)
```

Use worker globals for:

- Config bundle.
- Entry decision engine.
- Risk config.
- Exit policy config.
- Shared benchmark/date state.

Avoid repeatedly pickling this data with every ticker task.

### 3. Disk-Cached Price Data

The parent loader caches:

```text
prices.pkl
quarterly.pkl
```

For `codex-backed`, implement a new cache namespace:

```text
codex-backed/cache/
  prices.pkl
  fundamentals.pkl
  features.pkl
  metadata.json
```

The first version can use pickle for speed and simplicity. Later, migrate to parquet shards if needed.

### 4. Precomputed Indicator / Feature Cache

The parent has `indicator_cache.py` to avoid recomputing technicals for every run.

The new engine should use a broader feature cache:

```text
feature_cache[ticker][date_iso] -> FeatureSnapshot-compatible dict
```

This should include:

- Technical fields.
- Relative strength fields.
- Regime fields.
- Fundamental/valuation fields if available.
- Signal-card scores if available.

This is more useful than only caching indicators because the new entry engine consumes a flat snapshot.

### 5. Precomputed Date State

The parent runner precomputes SPY/QQQ slices, VIX proxy, and market regime once per test date.

Keep this:

```text
date_state[date_iso] = {
  "spy_bar_or_slice": ...,
  "qqq_bar_or_slice": ...,
  "vix_proxy": ...,
  "market_regime": ...,
  "regime_confidence": ...
}
```

This prevents recomputing regime per ticker.

### 6. Flat Records

The parent emits flat signal dicts consumed by outcome/metrics/report modules.

Keep flat output artifacts:

- `entry_decisions.csv`
- `trades.csv`
- `metrics.json`
- sliced CSV metrics

Flat files make analysis in Python, spreadsheets, or notebooks easy.

## Key Difference From Parent Backtest

The parent backtest answers:

```text
What was return exactly after 20D / 63D / 252D?
```

The new backtest answers:

```text
If this entry signal fired, how would the configured sell policy have managed the trade?
```

So fixed horizons become maximum simulation windows:

- `short_term`: simulate up to 30 trading days by default.
- `medium_term`: simulate up to 90 trading days by default.

Trades can exit earlier via:

- Stop loss.
- Partial profit.
- Breakeven stop.
- Trailing stop.
- Time stop.
- Max simulation window.

## Proposed Runtime Flow

```text
codex-backed backtest
  -> load and validate configs
  -> create run directory and manifest
  -> load historical data from cache or provider
  -> generate weekly test dates
  -> build/load feature cache
  -> precompute date state
  -> build per-ticker work items
  -> run ticker workers in ProcessPoolExecutor
  -> merge worker outputs
  -> write entry_decisions.csv
  -> write trades.csv
  -> build metrics
  -> write metrics.json and sliced CSVs
  -> generate report.html
```

## Proposed Modules

```text
codex-backed/src/codex_backed/data/
  loader.py              # load cached or downloaded historical data
  cache.py               # cache read/write/invalidation
  bars.py                # convert DataFrame rows to normalized bar dicts

codex-backed/src/codex_backed/features/
  historical_builder.py  # build FeatureSnapshot for ticker/date
  feature_cache.py       # build/load feature snapshot cache
  date_state.py          # benchmark/regime state per date

codex-backed/src/codex_backed/backtest/
  dates.py               # generate weekly test dates
  worker.py              # worker init and per-ticker worker
  runner.py              # orchestrates full backtest
  writer.py              # writes CSV/JSON artifacts
  report.py              # HTML report
```

## CLI Additions

Extend `codex-backed backtest`:

```text
--config-dir
--output-dir
--run-id
--tickers AAPL,MSFT,NVDA
--start YYYY-MM-DD
--end YYYY-MM-DD
--workers N
--force-refresh
--rebuild-feature-cache
--no-report
```

Defaults:

- `workers = min(os.cpu_count(), number_of_tickers)`.
- `start/end` come from `backtest_config.json`.
- `output_dir` defaults to `codex-backed/results`.

## Data Strategy

### Phase 1: Reuse Existing Backtest Cache

Fastest path:

- Read `codex-backed/cache/prices.pkl`.
- Keep all new cache artifacts under `codex-backed/cache`.
- Do not use parent `backend/backtest/cache` as the default cache location.

Benefit:

- Avoid immediate network/download work.
- Gets the new runner working quickly.

Risk:

- Parent cache format is implicit. Add validation before use.

### Phase 2: Native `codex-backed` Cache

Implement:

```text
codex-backed/cache/prices.pkl
codex-backed/cache/fundamentals.pkl
codex-backed/cache/features.pkl
codex-backed/cache/metadata.json
```

Cache metadata should include:

- Config hash.
- Ticker list.
- Date range.
- Source provider.
- Created timestamp.
- Parent cache source path if imported.

### Phase 3: Optional Parquet Shards

If pickle becomes too large or slow:

```text
codex-backed/cache/prices/{ticker}.parquet
codex-backed/cache/features/{ticker}.parquet
```

Do not start here unless needed.

## Feature Generation Strategy

Use the existing backend services initially because they already compute the hard technical/fundamental fields.

Option A, fastest:

- Import existing backend modules from `backend/app`.
- Build `FeatureSnapshot` using current service outputs.
- Reuse `compute_technicals`, `score_all_cards`, regime classification, archetype classification.

Option B, cleaner later:

- Move shared feature computation into a library module.
- Make both old backend and `codex-backed` depend on it.

Recommended version 1: Option A with adapter boundaries.

Adapter boundary:

```text
HistoricalFeatureBuilder.build(ticker, date, price_slice, benchmark_state, fundamentals)
  -> FeatureSnapshot
```

This keeps imports contained and makes later replacement easier.

## Parallel Runner Design

### Main Process Responsibilities

1. Load configs.
2. Load data.
3. Build test dates.
4. Build/load feature cache.
5. Precompute date state.
6. Create work items:

```python
{
  "ticker": ticker,
  "bars": ticker_bars,
  "feature_rows": feature_cache[ticker],
  "test_dates": test_dates,
}
```

7. Start process pool.
8. Merge worker outputs.
9. Write artifacts.

### Worker Initializer

```python
def _worker_init(config_bundle_data, date_state):
    global _CONFIG, _ENTRY_ENGINE, _RISK_CONFIG, _EXIT_POLICY, _DATE_STATE
```

Initialize once:

- `EntryDecisionEngine`.
- Rule engine.
- Risk config.
- Exit policies.

### Per-Ticker Worker

```text
for each test_date:
  feature = feature_cache[ticker][date]
  for horizon in enabled horizons:
    decision = entry_engine.decide(feature, horizon)
    append entry decision record
    if actionable:
      entry = entry_execution_simulator.simulate(...)
      if entry triggered:
        trade = trade_simulator.simulate(...)
        append trade record
return worker_result
```

Worker output:

```python
{
  "ticker": ticker,
  "entry_decisions": list[dict],
  "trades": list[dict],
  "errors": list[dict],
}
```

## Speed Optimizations

### 1. Avoid Rebuilding Features Every Run

Feature computation is expensive. Cache it by:

- ticker
- date
- relevant config hash
- price cache mtime

### 2. Use One Task Per Ticker

Avoid one task per ticker/date/horizon. That creates too many futures.

### 3. Use Worker Globals

Do not pickle config/engines/date-state with every task.

### 4. Preconvert Price Data

Before workers:

- Normalize columns to lowercase: `open`, `high`, `low`, `close`, `volume`.
- Convert each ticker DataFrame to list-of-dict bars or compact column arrays.
- Build a date-index map:

```python
date_to_index[ticker][date_iso] = int
```

This avoids repeated DataFrame search operations in workers.

### 5. Precompute Benchmark/Regime Once Per Date

Regime does not depend on ticker. Compute once.

### 6. Batch Writes

Workers return in memory. Main process writes CSV once per artifact.

Avoid per-worker file writes in version 1.

### 7. Configurable Worker Count

Add `--workers`. Default:

```python
min(os.cpu_count() or 4, len(work_items))
```

Allow `--workers 1` for debugging.

### 8. Minimal Worker Logging

Workers should not print progress. Main process prints completion by ticker.

## Output Artifacts

Each run writes:

```text
codex-backed/results/<run_id>/
  manifest.json
  entry_decisions.csv
  trades.csv
  metrics.json
  by_entry_label.csv
  by_entry_strategy.csv
  by_entry_setup.csv
  by_market_regime.csv
  by_exit_reason.csv
  by_ticker.csv
  report.html
```

### `entry_decisions.csv`

Columns:

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
reasons
missing_data
matched_signals
optional_signals
market_regime
archetype
price
```

### `trades.csv`

Columns:

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
entry_wait_days
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
event_count
market_regime
archetype
```

## Metrics

Primary objective:

```text
average realized_return_pct
```

Core metrics:

- Count.
- Average realized return.
- Median realized return.
- Win rate.
- Profit factor.
- Average MAE.
- Average MFE.
- Average MFE capture.
- Average days held.
- Partial-profit hit rate.
- Exit reason distribution.

Slices:

- Entry label.
- Entry strategy.
- Entry setup.
- Market regime.
- Archetype.
- Ticker.
- Exit reason.
- Score bucket.

## Implementation Stories

### Story B1: Backtest CLI Arguments

Add CLI options:

- `--tickers`
- `--start`
- `--end`
- `--workers`
- `--force-refresh`
- `--rebuild-feature-cache`
- `--no-report`

Acceptance criteria:

- `codex-backed backtest --help` shows all options.
- `--workers 1` is accepted.
- Explicit CLI values override JSON config.

### Story B2: Data Cache Loader

Implement `codex_backed.data.loader`.

Acceptance criteria:

- Loads `codex-backed/cache/prices.pkl` when present.
- Validates required OHLCV columns.
- Normalizes ticker keys and date indices.
- Falls back with clear error if no cache exists.

### Story B3: Bar Normalization

Implement `codex_backed.data.bars`.

Acceptance criteria:

- Converts DataFrame to list of normalized bar dicts.
- Columns are lowercase.
- Includes date string per bar.
- Builds `date_to_index` map.

### Story B4: Test Date Generation

Implement `codex_backed.backtest.dates`.

Acceptance criteria:

- Generates weekly Monday test dates.
- Applies start/end overrides.
- Skips dates not in data index through date map lookup.

### Story B5: Date State Builder

Implement `codex_backed.features.date_state`.

Acceptance criteria:

- Computes one market regime record per test date.
- Uses SPY/QQQ when available.
- Caches date state for reuse by all workers.

### Story B6: Feature Cache

Implement `codex_backed.features.feature_cache`.

Acceptance criteria:

- Builds `feature_cache[ticker][date_iso]`.
- Saves/loads cache from disk.
- Invalidates cache when config hash or price cache mtime changes.
- Supports `--rebuild-feature-cache`.

### Story B7: Historical Feature Builder

Implement `codex_backed.features.historical_builder`.

Acceptance criteria:

- Builds `FeatureSnapshot` for one ticker/date.
- Uses existing backend feature services via adapter boundary.
- Includes signal-card fields.
- Keeps missing data as `None`.

### Story B8: Worker Implementation

Implement `codex_backed.backtest.worker`.

Acceptance criteria:

- Has worker initializer for configs and engines.
- Processes one ticker across all dates/horizons.
- Returns entry decision records and trade records.
- Catches per-date errors without killing the whole run.

### Story B9: Parallel Runner

Implement `codex_backed.backtest.runner`.

Acceptance criteria:

- Builds per-ticker work items.
- Runs with `ProcessPoolExecutor`.
- Supports `--workers 1`.
- Prints ticker-level progress.
- Merges worker outputs.

### Story B10: Artifact Writer

Implement `codex_backed.backtest.writer`.

Acceptance criteria:

- Writes `entry_decisions.csv`.
- Writes `trades.csv`.
- Writes `metrics.json`.
- Writes sliced metric CSVs.

### Story B11: Wire CLI Backtest

Replace scaffold behavior in `cli.py`.

Acceptance criteria:

- `codex-backed backtest` performs a real run.
- Manifest is still written.
- Exit code is non-zero on fatal config/data errors.

### Story B12: HTML Report

Implement `codex_backed.backtest.report`.

Acceptance criteria:

- Report focuses on lifecycle metrics.
- Shows entry quality and exit quality separately.
- Shows exit reason distribution.
- Shows MFE vs realized return summary.
- Does not treat 20D/63D fixed return as primary.

## Testing Plan

### Unit Tests

- Date generation.
- Bar normalization.
- Feature cache metadata invalidation.
- Worker result serialization.
- Artifact writer.
- Metrics slices.

### Integration Tests

Use a tiny synthetic data fixture:

```text
2 tickers
40 trading days
short_term only
known feature rows
known price paths
```

Acceptance criteria:

- Runner writes all expected artifacts.
- At least one actionable trade is simulated.
- Metrics match expected synthetic result.
- `--workers 1` and `--workers 2` produce identical outputs after sorting.

### Smoke Test With Existing Cache

Use:

```bash
codex-backed/.venv/bin/codex-backed backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --tickers AAPL,MSFT \
  --start 2022-01-01 \
  --end 2022-06-30 \
  --workers 2
```

Acceptance criteria:

- Completes without network if `codex-backed/cache/prices.pkl` exists.
- Writes non-empty `entry_decisions.csv`.
- Writes `trades.csv`, even if zero actionable trades.
- Writes `metrics.json`.

## Recommended Build Order

1. CLI argument expansion.
2. Data cache loader and bar normalization.
3. Synthetic-data runner path without backend feature services.
4. Artifact writer and metric slices.
5. Parallel worker path.
6. Parent-cache integration.
7. Historical feature builder adapter to existing backend services.
8. Real `codex-backed backtest` CLI wiring.
9. HTML report.
10. Smoke test on AAPL/MSFT.

This order gets deterministic runner tests working before adding expensive historical feature generation.
