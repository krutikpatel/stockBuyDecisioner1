# Implementation Plan: CLI Trade Lifecycle Engine

This plan implements the new engine in `codex-backed/` as a CLI-only tool. It is intentionally separate from the existing backend and frontend.

The stories are ordered so each milestone produces something testable.

## Milestone 0: Documentation and Scope Lock

### Story 0.1: Create Design Documentation

Status: complete in this documentation pass.

Acceptance criteria:

- `codex-backed/README.md` exists.
- `codex-backed/DESIGN.md` exists.
- `codex-backed/IMPLEMENTATION_PLAN.md` exists.
- Design states that the new engine is CLI-only.
- Design states that entry and exit optimization are separate.
- Design states that fixed 20D/63D selling is replaced by smarter exit simulation.

## Milestone 1: Project Skeleton

### Story 1.1: Create Python Package Skeleton

Create:

```text
codex-backed/pyproject.toml
codex-backed/src/codex_backed/
codex-backed/tests/
```

Acceptance criteria:

- Package imports as `codex_backed`.
- `python -m codex_backed.cli --help` works.
- Tests can run from `codex-backed/`.
- No frontend dependencies are introduced.

### Story 1.2: Add CLI Entrypoint

Implement CLI commands:

```text
validate-config
backtest
optimize-entry
optimize-exit
report
compare
```

Acceptance criteria:

- Each command has `--help`.
- Each command accepts `--config-dir`.
- Commands fail with clear errors when config is invalid or missing.

### Story 1.3: Add Result Directory Convention

Create a run output layout:

```text
codex-backed/results/
  <run_id>/
    manifest.json
    trades.csv
    entry_decisions.csv
    metrics.json
    report.html
```

Acceptance criteria:

- Every run creates a unique `run_id`.
- Manifest records CLI args, config paths, git commit if available, and run timestamp.

## Milestone 2: Config System

### Story 2.1: Add New JSON Config Files

Create:

```text
codex-backed/configs/entry_signal_config.json
codex-backed/configs/exit_policy_config.json
codex-backed/configs/risk_config.json
codex-backed/configs/backtest_config.json
codex-backed/configs/optimization_config.json
```

Also copy or adapt:

```text
backend/config/technical_setup_config.json
backend/config/market_and_universe_config.json
backend/config/stock_classification_config.json
```

Acceptance criteria:

- Configs are pure JSON.
- Config files contain defaults for short-term and medium-term only.
- Defaults match the design doc first-version defaults.

### Story 2.2: Implement Config Loader

Implement `codex_backed.config.loader`.

Acceptance criteria:

- Loads all required JSON files from `--config-dir`.
- Fails fast on missing files.
- Exposes typed config access or validated dict access.
- Preserves unknown fields only if explicitly allowed.

### Story 2.3: Implement Config Validation

Implement schema validation for:

- Required top-level keys.
- Valid labels.
- Valid rule operators.
- Valid horizon names.
- Numeric bounds for stop/target/trailing parameters.

Acceptance criteria:

- `codex-backed validate-config --config-dir codex-backed/configs` passes.
- Invalid operator names fail with clear messages.
- Negative sell percentages or percentages over 100 fail.

## Milestone 3: Rule Engine and Feature Snapshot

### Story 3.1: Port JSON Rule Engine

Use the existing `backend/app/engine/rule_engine.py` as inspiration.

Acceptance criteria:

- Supports `all`, `any`, `not`.
- Supports `>=`, `<=`, `>`, `<`, `==`, `!=`, `in`, `not_in`, `between`, `exists`, `missing`, `contains`.
- Records missing fields.
- Unit tests cover each operator.

### Story 3.2: Implement New FeatureSnapshot

Create `codex_backed.features.snapshot`.

Acceptance criteria:

- Contains technical, fundamental, valuation, classification, market regime, and optional signal-card fields.
- Includes `sc_momentum`, `sc_trend`, `sc_entry_timing`, `sc_volume_accumulation`, `sc_volatility_risk`, `sc_relative_strength`, `sc_growth`, `sc_valuation`, `sc_quality`, and `sc_catalyst`.
- Exposes `to_dict()` for rule evaluation.

### Story 3.3: Implement FeatureBuilder Adapter

Create an adapter that can build the new snapshot from existing backend service models or backtest snapshot data.

Acceptance criteria:

- Can create a snapshot for one ticker/date.
- Maps all fields needed by initial entry configs.
- Missing data remains `None`, not fake defaults.

## Milestone 4: Data Loading

### Story 4.1: Reuse Existing Historical Data Loader

Use `backend/backtest/data_loader.py` and existing yfinance cache patterns as inspiration.

Acceptance criteria:

- Loads OHLCV data for configured tickers.
- Ensures `SPY` and `QQQ` are available for diagnostics.
- Supports start/end dates from config or CLI.
- Does not require the FastAPI app to run.

### Story 4.2: Add Data Quality Checks

Acceptance criteria:

- Rejects tickers with insufficient price history.
- Warns on missing OHLC columns.
- Records skipped tickers in manifest.

## Milestone 5: Entry Engine

### Story 5.1: Implement Entry Setup Detector

Use `technical_setup_config.json` to detect entry setups.

Acceptance criteria:

- Supports `signal_definitions`.
- Supports `entry_setups`.
- Selects highest-priority matched setup.
- Records matched and missing signals.

### Story 5.2: Implement Entry Router

Use `entry_signal_config.json`.

Acceptance criteria:

- Priority-first routing.
- Fallback route returns `watchlist`.
- Router can branch by setup, regime, archetype, secondary tags, and raw features.

### Story 5.3: Implement Entry Strategy Scoring

Implement `entry_engines` with score rules, penalty rules, and thresholds.

Acceptance criteria:

- Produces `EntryDecision`.
- Labels are limited to `NO_TRADE`, `WATCHLIST`, `BUY_STARTER`, `BUY_FULL`, `BUY_AGGRESSIVE`.
- Reasons include fired score rules.
- Missing fields reduce confidence but do not crash.

### Story 5.4: Add Initial Entry Strategies

Implement config strategies:

- `quality_dislocation`
- `oversold_rebound`
- `bull_leadership`
- `pullback_entry`
- `breakout_entry`
- `no_trade`

Acceptance criteria:

- Each strategy exists in JSON.
- Each strategy has score rules and thresholds.
- Pullback entry requires at least one confirmation signal.
- Bull leadership is favored in `BULL_RISK_ON`.
- Quality dislocation can trigger in weaker/choppy regimes.

## Milestone 6: Risk and Entry Execution

### Story 6.1: Implement Entry Execution Simulator

Use existing `backend/backtest/entry_simulator.py` as inspiration.

Supported methods:

```text
NEXT_OPEN
NEXT_CLOSE
PULLBACK_TO_SMA20
PULLBACK_TO_SMA50
BREAKOUT_CONFIRMATION
```

Acceptance criteria:

- Entry is never same-bar lookahead unless explicitly configured.
- Entry can fail if pullback/breakout is not triggered.
- Failed entries are recorded separately from losing trades.

### Story 6.2: Implement Stop and Target Calculator

Acceptance criteria:

- Supports ATR stop.
- Supports technical support buffer if support is available.
- Computes initial `R`.
- Computes target 1 using configured R multiple.
- Handles missing ATR with fallback config.

### Story 6.3: Implement Position Sizing Policy

Acceptance criteria:

- Maps entry label to nominal size.
- Applies high-ATR cap.
- Applies earnings proximity cap.
- Records final size multiplier for each simulated trade.

## Milestone 7: Exit Engine and Trade Simulator

### Story 7.1: Implement Trade Simulation Loop

Simulate bar-by-bar exits after a buy signal.

Acceptance criteria:

- Uses max simulation days per horizon.
- Checks stop hit.
- Checks target 1 hit.
- Checks trailing stop.
- Checks time stop.
- Exits at max simulation window only if no earlier exit condition fires.

### Story 7.2: Implement Partial Profit Taking

Acceptance criteria:

- When target 1 is hit, sells configured percentage.
- Records `PARTIAL_PROFIT_TAKEN` event.
- Remaining position continues to be simulated.
- Realized return handles multiple exit legs.

### Story 7.3: Implement Stop Move to Breakeven

Acceptance criteria:

- If configured, stop moves to entry after target 1.
- Records `STOP_MOVED_TO_BREAKEVEN`.
- New stop applies only after target 1 event.

### Story 7.4: Implement ATR Trailing Stop

Acceptance criteria:

- Trailing stop activates after target 1 if configured.
- Stop only moves upward for long trades.
- Exit reason is `TRAILING_STOP_EXIT`.
- Records stop movement events if report verbosity is enabled.

### Story 7.5: Implement Time Stop

Acceptance criteria:

- Exits if trade fails to make configured progress by configured day count.
- Uses open return or MFE threshold from config.
- Exit reason is `TIME_STOP_EXIT`.

### Story 7.6: Compute Trade Metrics

Acceptance criteria:

- Computes realized return.
- Computes MAE.
- Computes MFE.
- Computes MFE capture.
- Computes days held.
- Computes partial-profit hit flag.
- Computes stop-out flag.

## Milestone 8: Backtest Runner

### Story 8.1: Generate Historical Entry Decisions

Acceptance criteria:

- Iterates tickers and test dates.
- Builds features.
- Runs entry engine.
- Writes `entry_decisions.csv`.

### Story 8.2: Simulate Trades for Buy Labels

Only simulate trades for:

```text
BUY_STARTER
BUY_FULL
BUY_AGGRESSIVE
```

Acceptance criteria:

- Writes `trades.csv`.
- Includes entry decision fields and exit simulation fields.
- Records entry signals that did not trigger separately.

### Story 8.3: Preserve Fixed-Horizon Diagnostics Only as Secondary Fields

Acceptance criteria:

- Optional fixed 20D/63D return can be computed for comparison.
- Report and optimizer use realized trade return as primary.
- Documentation warns that fixed horizon is diagnostic only.

## Milestone 9: Metrics and Reporting

### Story 9.1: Build Trade Metrics

Acceptance criteria:

- Overall average realized return.
- Win rate.
- Profit factor.
- Average MAE.
- Average MFE.
- Average MFE capture.
- Average days held.
- Partial-profit hit rate.
- Exit reason distribution.

### Story 9.2: Slice Metrics

Metrics by:

- Entry label.
- Entry setup.
- Entry strategy.
- Market regime.
- Archetype.
- Ticker.
- Exit reason.
- Score bucket.

Acceptance criteria:

- Each slice is written as CSV.
- Slices include count, average realized return, median return, win rate, MAE, MFE, and days held.

### Story 9.3: Generate HTML Report

Acceptance criteria:

- Report highlights trade lifecycle performance.
- Report shows fixed-horizon return only as diagnostic.
- Report has sections for entry quality and exit quality.
- Report shows MFE vs realized return.
- Report shows partial-profit and trailing-stop effectiveness.

## Milestone 10: Entry Optimization

### Story 10.1: Define Entry Parameter Search Space

Acceptance criteria:

- Search space is defined in `optimization_config.json`.
- Parameters include RSI thresholds, dislocation thresholds, growth minimums, RS thresholds, pullback confirmation requirements, and score thresholds.
- Search is reproducible with a seed.

### Story 10.2: Implement Entry Optimizer

Entry optimizer uses fixed baseline exit policy.

Acceptance criteria:

- Primary objective is average realized return.
- Enforces minimum trade count.
- Enforces configured risk constraints.
- Writes best config candidate to results.

### Story 10.3: Add Walk-Forward Entry Optimization

Acceptance criteria:

- Uses train/test windows from config.
- Optimizes on train period.
- Evaluates on test period.
- Reports out-of-sample average realized return and consistency.

## Milestone 11: Exit Optimization

### Story 11.1: Define Exit Parameter Search Space

Parameters:

- Initial ATR stop multiplier.
- Target 1 R multiple.
- Partial sell percentage.
- Trailing ATR multiplier.
- Time stop days.
- Time stop minimum return.

Acceptance criteria:

- Search space lives in pure JSON.
- Bounds are validated.

### Story 11.2: Implement Exit Optimizer

Exit optimizer uses fixed entry signals.

Acceptance criteria:

- Primary objective is average realized return.
- Reports MFE capture and profit factor as diagnostics.
- Writes best exit policy candidate.

### Story 11.3: Add Walk-Forward Exit Optimization

Acceptance criteria:

- Same train/test framework as entry optimizer.
- Reports out-of-sample performance.
- Compares optimized exit policy against baseline partial-profit/trailing-stop policy.

## Milestone 12: Comparison and Migration

### Story 12.1: Compare Against Existing Backtest

Acceptance criteria:

- Compare old fixed-horizon results against new simulated trade results.
- Show where old buy labels were bad entries vs bad exits.
- Show where avoid labels were actually profitable entry candidates.

### Story 12.2: Migration Decision Report

Acceptance criteria:

- Summarizes whether new engine improves short-term and medium-term realized returns.
- Identifies configs to promote.
- Identifies old logic to discard.

## Testing Strategy

### Unit Tests

- Rule engine operators.
- Config validation.
- Feature snapshot mapping.
- Entry setup detection.
- Entry scoring thresholds.
- Stop/target calculation.
- Partial profit accounting.
- Trailing stop behavior.
- Time stop behavior.
- MFE/MAE calculations.

### Integration Tests

- One ticker, one year, short-term only.
- Two tickers, multiple regimes.
- Entry decision generation.
- Trade simulation output.
- Metrics/report generation.

### Regression Tests

- Known synthetic price path where target 1 hits before stop.
- Known synthetic price path where stop hits before target.
- Known synthetic price path where trailing stop captures profit.
- Known synthetic price path where time stop exits.

## First Build Sequence

Recommended practical order:

1. Project skeleton and CLI.
2. Config loader and validation.
3. Rule engine and feature snapshot.
4. Entry engine using a small static config.
5. Trade simulator with partial profits and trailing stops.
6. Backtest runner writing `trades.csv`.
7. Metrics and report.
8. Entry optimizer.
9. Exit optimizer.
10. Walk-forward validation.

## Definition of Done for Version 1

Version 1 is done when:

- `codex-backed backtest` runs without frontend or FastAPI.
- Configs are pure JSON.
- Short-term and medium-term trades are simulated with partial profit and trailing stop exits.
- Backtest does not force sell exactly on day 20 or day 63.
- Entry and exit metrics are reported separately.
- Entry optimizer and exit optimizer can run independently.
- Primary optimization target is absolute realized return.
- Results can explain whether a historical signal failed because entry was bad or exit policy was bad.

