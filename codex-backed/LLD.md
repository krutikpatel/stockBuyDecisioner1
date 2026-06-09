# Low-Level Design

## 1. Package Layout

```text
codex-backed/
  configs/
  src/codex_backed/
    cli.py
    results.py
    config/
      loader.py
    rules/
      rule_engine.py
    features/
      snapshot.py
      builder.py
    entry/
      labels.py
      setup_detector.py
      engine.py
    risk/
      sizing.py
      stops.py
    simulation/
      entry_simulator.py
      trade.py
      trade_simulator.py
    data/
      bars.py
      loader.py
    backtest/
      metrics.py
      runner.py
      worker.py
      writer.py
  tests/
```

## 2. CLI Layer

File: `src/codex_backed/cli.py`

Responsibilities:

- Parse CLI commands.
- Load and validate config bundle.
- Create run directories.
- Dispatch to backtest runner.
- Keep scaffold commands for future optimization/report/compare commands.

Implemented commands:

```text
validate-config
backtest
```

Scaffolded commands:

```text
optimize-entry
optimize-exit
report
compare
```

Backtest options:

```text
--config-dir
--output-dir
--run-id
--tickers
--start
--end
--workers
--force-refresh
--rebuild-feature-cache
--no-report
```

## 3. Config Layer

File: `src/codex_backed/config/loader.py`

Key types:

- `ConfigBundle`
- `ConfigError`

Required config files:

```text
entry_signal_config.json
exit_policy_config.json
risk_config.json
backtest_config.json
optimization_config.json
technical_setup_config.json
market_and_universe_config.json
stock_classification_config.json
```

Validation checks:

- Required files exist.
- Files contain JSON objects.
- Rule operators are valid.
- Entry labels are valid.
- Horizons are `short_term` and `medium_term`.
- Exit percentages are between 0 and 100.
- Stop, target, ATR, and risk numbers have valid bounds.
- Backtest data source paths are configured.

## 4. Rule Engine

File: `src/codex_backed/rules/rule_engine.py`

Class:

- `RuleEngine`

Supported composition:

- `all`
- `any`
- `not`

Supported operators:

```text
>=
<=
>
<
==
!=
in
not_in
between
exists
missing
contains
```

Output:

- `RuleEvaluationResult`
  - `matched`
  - `reasons`
  - `missing_fields`
  - `confidence_penalty`

## 5. Feature Layer

File: `src/codex_backed/features/snapshot.py`

Class:

- `FeatureSnapshot`

Important field groups:

- identity fields
- price and volume fields
- technical fields
- fundamental fields
- valuation fields
- market regime
- archetype/category fields
- signal-card fields
- entry-score working fields

Signal-card fields are first-class:

```text
sc_momentum
sc_trend
sc_entry_timing
sc_volume_accumulation
sc_volatility_risk
sc_relative_strength
sc_growth
sc_valuation
sc_quality
sc_ownership
sc_catalyst
```

File: `src/codex_backed/features/builder.py`

Function:

- `build_feature_snapshot_from_mapping`

Current behavior:

- Builds `FeatureSnapshot` from a flat mapping.
- Ignores unknown keys.
- Requires `ticker`, `date`, and `price`.

## 6. Entry Layer

### Labels

File: `src/codex_backed/entry/labels.py`

Entry labels:

```text
NO_TRADE
WATCHLIST
BUY_STARTER
BUY_FULL
BUY_AGGRESSIVE
```

Actionable labels:

```text
BUY_STARTER
BUY_FULL
BUY_AGGRESSIVE
```

### Setup Detector

File: `src/codex_backed/entry/setup_detector.py`

Class:

- `EntrySetupDetector`

Input:

- `technical_setup_config.json`
- feature snapshot dict

Supports config keys:

- `entry_setups`
- `technical_setups`

Detection logic:

1. Evaluate all named signal definitions.
2. Sort setups by priority.
3. Require all required signals.
4. Reject if any blocking signal matches.
5. Require minimum optional signals.
6. Return first matching setup.

Output:

- `SetupDetectionResult`
  - `selected_setup`
  - `matched_signals`
  - `blocked_signals`
  - `optional_signals`
  - `missing_fields`

### Entry Decision Engine

File: `src/codex_backed/entry/engine.py`

Class:

- `EntryDecisionEngine`

Flow:

```text
FeatureSnapshot
  -> setup detector
  -> enrich snapshot with selected_setup
  -> entry router
  -> selected entry strategy
  -> score rules
  -> penalty rules
  -> decision thresholds
  -> EntryDecision
```

Output:

- `EntryDecision`
  - `ticker`
  - `date`
  - `horizon`
  - `entry_label`
  - `entry_score`
  - `confidence`
  - `selected_setup`
  - `entry_strategy`
  - `reasons`
  - `missing_data`
  - `matched_signals`
  - `optional_signals`

## 7. Risk Layer

### Position Sizing

File: `src/codex_backed/risk/sizing.py`

Function:

- `compute_position_size`

Inputs:

- entry label
- ATR percent
- earnings days away
- `risk_config.json`

Output:

- `PositionSize`
  - base multiplier
  - final multiplier
  - applied caps

Caps:

- high ATR cap
- earnings avoid
- earnings starter-only

### Stops and Targets

File: `src/codex_backed/risk/stops.py`

Functions:

- `compute_atr`
- `compute_stop_target`

Supported initial stop methods:

- `atr`
- `support`
- `atr_or_support`

Output:

- `StopTarget`
  - `initial_stop`
  - `target_1`
  - `risk_per_share`
  - `initial_risk_pct`

## 8. Simulation Layer

### Entry Execution

File: `src/codex_backed/simulation/entry_simulator.py`

Class:

- `EntryExecutionSimulator`

Methods:

```text
NEXT_OPEN
NEXT_CLOSE
PULLBACK_TO_SMA20
PULLBACK_TO_SMA50
BREAKOUT_CONFIRMATION
```

Output:

- `EntryExecution`
  - `entry_price`
  - `entry_index`
  - `entry_date`
  - `method_used`
  - `wait_days`
  - `triggered`

### Trade Data Classes

File: `src/codex_backed/simulation/trade.py`

Classes:

- `ExitEvent`
- `SimulatedTrade`

### Trade Simulator

File: `src/codex_backed/simulation/trade_simulator.py`

Class:

- `TradeSimulator`

Bar-by-bar lifecycle:

1. Compute initial stop and target 1.
2. Track MAE and MFE.
3. Stop out if active stop is hit.
4. Take partial profit if target 1 is hit.
5. Move stop to breakeven if configured.
6. Activate/update trailing stop.
7. Exit on time stop if no progress.
8. Exit at max simulation window if no earlier exit fires.

## 9. Data Layer

### Bar Normalization

File: `src/codex_backed/data/bars.py`

Functions:

- `normalize_price_frame`
- `build_date_index`
- `find_index_on_or_before`

Bar shape:

```text
date
open
high
low
close
volume
```

### Loader

File: `src/codex_backed/data/loader.py`

Functions:

- `load_price_bars`
- `load_feature_rows`
- `group_feature_rows_by_ticker`

Current feature source:

- Parent `signals_with_outcomes.csv`

Temporary field proxies:

- growth score -> `sales_growth_yoy`
- quality score -> `operating_margin`
- volatility/dislocation card -> `dist_from_52w_high`
- relative strength card -> `rs_vs_spy_20d` and `rs_vs_sector_20d`
- trend card -> `sma50_slope`

These proxies are explicitly temporary until native historical feature generation is added.

## 10. Backtest Layer

### Runner

File: `src/codex_backed/backtest/runner.py`

Class:

- `BacktestOptions`

Function:

- `run_lifecycle_backtest`

Responsibilities:

- Read backtest config.
- Load feature rows.
- Load price bars.
- Group work by ticker.
- Run serial or parallel workers.
- Write outputs.

### Worker

File: `src/codex_backed/backtest/worker.py`

Functions:

- `worker_init`
- `process_ticker`

Worker flow:

```text
for each feature row:
  build FeatureSnapshot
  run EntryDecisionEngine
  write entry decision record
  if actionable:
    find signal bar index
    simulate entry execution
    compute position size
    simulate trade lifecycle
    write trade record
```

### Writer

File: `src/codex_backed/backtest/writer.py`

Functions:

- `write_csv`
- `write_json`
- `build_record_metrics`
- `build_sliced_metrics`
- `write_lifecycle_report`

Artifacts:

- `entry_decisions.csv`
- `trades.csv`
- `metrics.json`
- sliced metric CSVs
- `report.html`

### Metrics

File: `src/codex_backed/backtest/metrics.py`

Functions:

- `build_trade_metrics`
- `group_trade_metrics`

Metrics:

- count
- average return
- median return
- win rate
- profit factor
- average MAE
- average MFE
- average MFE capture
- average days held
- partial-profit hit rate
- exit reason counts

## 11. Test Coverage

Current tests cover:

- config loading and validation
- rule engine operators
- feature snapshot mapping
- entry setup and entry engine behavior
- entry execution
- stop/target math
- trade simulator lifecycle
- sizing
- aggregate metrics
- backtest runner artifact generation

Run:

```bash
codex-backed/.venv/bin/python -m pytest codex-backed/tests -q
```

## 12. Known Technical Debt

- Native historical feature builder is not implemented.
- Native feature cache is not implemented.
- HTML report is basic.
- Optimizer commands are not implemented.
- Backtest currently depends on parent feature CSV shape.
