# Design: CLI Trade Lifecycle Engine

## 1. Purpose

Build a fresh CLI-only stock decision engine that separates entry decisions from exit decisions.

The current engine uses one composite score to route a stock into buy, wait, or avoid labels. That is structurally weak because the same feature can mean different things depending on trade state:

- Low RSI can be bullish for a new dislocation entry.
- High RSI can be bullish for holding a winner, but bearish if it rolls over.
- Strong trend can be too extended for a new buy, but still correct to hold.
- Broken support can be bad for momentum entry, but useful for quality-dislocation rebound setups.

The new engine should answer two separate questions:

1. Entry: should a new trade be opened today?
2. Exit: after a historical entry, how should the trade be sold?

For now, the system will not track live open positions. It will generate hypothetical exit analysis for every historical buy signal during backtests.

## 2. Goals

- Implement a new CLI tool under `codex-backed/`.
- Keep config files as pure JSON.
- Reuse as many existing config parameters and rule concepts as practical.
- Optimize entry and exit rules separately.
- Optimize primarily for absolute return.
- Replace fixed day-N sell assumptions with smarter trade simulation.
- Support partial profit-taking and trailing stops.
- Keep the design clean enough to replace the old engine later.
- Avoid frontend work.

## 3. Non-Goals

- No frontend.
- No live brokerage integration.
- No live position tracking for now.
- No compatibility requirement with old labels.
- No forced sell exactly on day 20 or day 63.
- No separate sell rules by setup type in the first version.

## 4. High-Level Architecture

```text
CLI command
  -> ConfigLoader
  -> DataLoader
  -> FeatureBuilder
  -> UniverseFilter
  -> EntrySetupDetector
  -> EntryEngine
  -> TradeSimulator
  -> ExitEngine
  -> MetricsBuilder
  -> Optimizer / ReportWriter
```

The engine is designed around complete trade lifecycle simulation:

```text
historical date
  -> generate entry decision
  -> if entry is actionable, simulate entry price
  -> initialize stop and target
  -> walk forward bar by bar
  -> take partial profit if target is reached
  -> move stop according to policy
  -> trail remaining position
  -> exit on stop, trailing stop, time stop, failed setup, or max simulation window
  -> record realized trade return
```

## 5. Proposed Directory Layout

```text
codex-backed/
  README.md
  DESIGN.md
  IMPLEMENTATION_PLAN.md
  pyproject.toml
  configs/
    entry_signal_config.json
    exit_policy_config.json
    risk_config.json
    backtest_config.json
    optimization_config.json
    market_and_universe_config.json
    stock_classification_config.json
    technical_setup_config.json
  src/
    codex_backed/
      __init__.py
      cli.py
      config/
        loader.py
        schema.py
      data/
        loader.py
        cache.py
      features/
        snapshot.py
        builder.py
      rules/
        rule_engine.py
      entry/
        setup_detector.py
        engine.py
        labels.py
      exit/
        policy.py
        engine.py
        labels.py
      risk/
        sizing.py
        stops.py
      simulation/
        entry_simulator.py
        trade_simulator.py
        trade.py
      backtest/
        runner.py
        metrics.py
        report.py
      optimization/
        entry_optimizer.py
        exit_optimizer.py
        walk_forward.py
  tests/
```

The docs are being created now. The code directories above are the intended implementation structure.

## 6. Reuse From Existing System

The new engine should reuse concepts, not blindly copy behavior.

### Reuse Strongly

- `backend/app/engine/rule_engine.py`
  - JSON rule syntax: `all`, `any`, `not`.
  - Operators: `>=`, `<=`, `>`, `<`, `==`, `!=`, `in`, `not_in`, `between`, `exists`, `missing`, `contains`.

- `backend/app/features/feature_snapshot.py`
  - Flat feature snapshot pattern.
  - Optional fields with missing-data handling.

- `backend/app/features/feature_builder.py`
  - Mapping from existing service outputs to flat features.

- `backend/config/technical_setup_config.json`
  - Signal definitions for RSI, trend, support break, pullback, breakout, volume, and extension.

- `backend/config/market_and_universe_config.json`
  - Universe filters and market regimes.

- `backend/config/stock_classification_config.json`
  - Archetypes and secondary tags.

- `backend/backtest/entry_simulator.py`
  - Entry methods like `NEXT_OPEN`, `NEXT_CLOSE`, pullback entries, and breakout confirmation.

- `backend/backtest/exit_simulator.py`
  - ATR target/stop and trailing stop concepts.

- `backend/backtest/outcome.py`
  - MAE/MFE calculations.

### Replace or Redesign

- Replace one composite score with separate entry and exit engines.
- Replace fixed-horizon `forward_return` as the primary objective.
- Replace old buy/avoid labels with clean entry and exit labels.
- Replace fixed report interpretation with trade lifecycle metrics.

## 7. Core Data Contracts

### 7.1 FeatureSnapshot

A flat, date-specific stock snapshot used by JSON rules.

Required identity fields:

```text
ticker
date
price
market_regime
archetype
sector
```

Feature groups:

```text
technical:
  rsi14
  rsi_slope
  sma20_relative
  sma50_relative
  sma200_relative
  sma20_slope
  sma50_slope
  sma200_slope
  atr_percent
  vwap_deviation
  dist_from_20d_high
  dist_from_52w_high
  max_drawdown_3m
  perf_1w
  perf_1m
  perf_3m
  breakout_volume_multiple
  volume_dryup_ratio
  updown_volume_ratio

fundamental:
  sales_growth_yoy
  eps_growth_yoy
  operating_margin
  gross_margin
  roic
  roe
  free_cash_flow
  debt_to_equity

valuation:
  forward_pe
  peg_ratio
  price_to_sales
  ev_to_ebitda
  fcf_yield

classification:
  primary_category
  secondary_tags

optional signal card values:
  sc_momentum
  sc_trend
  sc_entry_timing
  sc_volume_accumulation
  sc_volatility_risk
  sc_relative_strength
  sc_growth
  sc_valuation
  sc_quality
  sc_catalyst
```

The new engine should include signal card values as first-class optional fields so config can express card-based rules.

### 7.2 EntryDecision

The output of the entry engine for one ticker/date/horizon.

```text
ticker
date
horizon
entry_label
entry_score
confidence
entry_setup
entry_strategy
reasons
missing_data
risk_profile
initial_stop_method
target_method
max_simulation_days
```

Clean entry labels:

```text
NO_TRADE
WATCHLIST
BUY_STARTER
BUY_FULL
BUY_AGGRESSIVE
```

Suggested first-version interpretation:

- `NO_TRADE`: setup is absent or negative.
- `WATCHLIST`: setup is improving but not actionable.
- `BUY_STARTER`: valid setup with elevated uncertainty or volatility.
- `BUY_FULL`: valid setup with strong expected value and manageable risk.
- `BUY_AGGRESSIVE`: rare, high-conviction setup in supportive regime.

### 7.3 SimulatedTrade

The output of historical trade simulation.

```text
ticker
signal_date
entry_date
entry_price
entry_label
entry_setup
entry_strategy
initial_stop
initial_risk_pct
target_1
target_1_hit
partial_exit_date
partial_exit_price
partial_exit_pct
trailing_stop_enabled
exit_date
exit_price
exit_reason
days_held
realized_return_pct
mae_pct
mfe_pct
mfe_capture_pct
max_open_profit_pct
max_open_loss_pct
```

### 7.4 ExitEvent

Each simulated trade can have one or more exit events.

```text
event_date
event_type
event_price
position_pct_before
position_pct_after
realized_return_pct
reason
```

Exit event types:

```text
PARTIAL_PROFIT_TAKEN
STOP_MOVED_TO_BREAKEVEN
TRAILING_STOP_RAISED
TRAILING_STOP_EXIT
STOP_LOSS_EXIT
TIME_STOP_EXIT
FAILED_SETUP_EXIT
MAX_SIM_WINDOW_EXIT
```

## 8. Config Model

Config remains pure JSON.

### 8.1 `configs/technical_setup_config.json`

Purpose: reusable technical signals and setup definitions.

This can start as a copy of the existing `backend/config/technical_setup_config.json`, then evolve.

Recommended shape:

```json
{
  "signal_definitions": {},
  "entry_setups": {},
  "exit_setups": {}
}
```

First version can leave `exit_setups` minimal because sell rules are not separate by setup yet.

### 8.2 `configs/entry_signal_config.json`

Purpose: entry routing, entry scoring, and entry labels.

Recommended shape:

```json
{
  "entry_router": {
    "method": "priority_first_match",
    "rules": []
  },
  "entry_engines": {
    "quality_dislocation": {
      "score_rules": [],
      "penalty_rules": [],
      "decision_thresholds": [],
      "fallback_label": "WATCHLIST"
    }
  }
}
```

Initial entry strategy families:

- `quality_dislocation`
- `oversold_rebound`
- `bull_leadership`
- `pullback_entry`
- `breakout_entry`
- `no_trade`

### 8.3 `configs/exit_policy_config.json`

Purpose: sell logic used by trade simulation.

First version uses one default policy per horizon, not per setup type.

Example:

```json
{
  "default_exit_policy": {
    "short_term": {
      "max_simulation_days": 30,
      "initial_stop": {
        "method": "atr_or_support",
        "atr_multiplier": 2.0,
        "support_buffer_pct": 1.0
      },
      "partial_profit": {
        "enabled": true,
        "target_r_multiple": 2.0,
        "sell_pct": 50,
        "move_stop_to_breakeven": true
      },
      "trailing_stop": {
        "enabled": true,
        "method": "atr",
        "atr_multiplier": 2.5,
        "activate_after_target_1": true
      },
      "time_stop": {
        "enabled": true,
        "days_without_progress": 10,
        "min_open_return_pct": 1.0
      }
    },
    "medium_term": {
      "max_simulation_days": 90,
      "initial_stop": {
        "method": "atr_or_support",
        "atr_multiplier": 2.5,
        "support_buffer_pct": 1.5
      },
      "partial_profit": {
        "enabled": true,
        "target_r_multiple": 2.5,
        "sell_pct": 40,
        "move_stop_to_breakeven": true
      },
      "trailing_stop": {
        "enabled": true,
        "method": "atr",
        "atr_multiplier": 3.0,
        "activate_after_target_1": true
      },
      "time_stop": {
        "enabled": true,
        "days_without_progress": 20,
        "min_open_return_pct": 2.0
      }
    }
  }
}
```

### 8.4 `configs/risk_config.json`

Purpose: position sizing, risk caps, volatility gates, and earnings risk controls.

Example:

```json
{
  "position_sizing": {
    "BUY_STARTER": 0.5,
    "BUY_FULL": 1.0,
    "BUY_AGGRESSIVE": 1.25
  },
  "risk_caps": {
    "max_risk_per_trade_pct": 1.0,
    "max_position_size_pct": 10.0,
    "high_atr_position_cap_pct": 50
  },
  "earnings_risk": {
    "avoid_new_entries_within_days": 3,
    "starter_only_within_days": 10
  }
}
```

### 8.5 `configs/backtest_config.json`

Purpose: universe, date range, entry method, horizons, output paths.

Example:

```json
{
  "date_range": {
    "start": "2018-01-01",
    "end": "2025-12-31"
  },
  "horizons": {
    "short_term": {
      "enabled": true,
      "max_simulation_days": 30
    },
    "medium_term": {
      "enabled": true,
      "max_simulation_days": 90
    }
  },
  "entry_execution": {
    "default_method": "NEXT_OPEN",
    "max_wait_days": 10
  },
  "outputs": {
    "directory": "codex-backed/results"
  }
}
```

### 8.6 `configs/optimization_config.json`

Purpose: define optimization objective, train/test split, parameter search spaces, and constraints.

Since the user wants primary optimization for absolute return:

```json
{
  "primary_objective": "realized_return_pct",
  "secondary_metrics": [
    "profit_factor",
    "win_rate_pct",
    "mfe_capture_pct",
    "max_drawdown_pct"
  ],
  "constraints": {
    "min_trades": 200,
    "max_avg_mae_pct": 12.0,
    "min_profit_factor": 1.2
  },
  "walk_forward": {
    "enabled": true,
    "train_weeks": 104,
    "test_weeks": 26,
    "step_weeks": 13
  }
}
```

## 9. Entry Engine Design

The entry engine evaluates whether a new trade should be opened.

### 9.1 Entry Router

The router selects one entry strategy using priority-first rules.

Example priority:

1. Universe or data quality fail -> `no_trade`
2. Earnings too close and not already in trade -> `watchlist_or_no_trade`
3. Quality dislocation -> `quality_dislocation`
4. Bull leadership -> `bull_leadership`
5. Oversold rebound -> `oversold_rebound`
6. Pullback entry -> `pullback_entry`
7. Breakout entry -> `breakout_entry`
8. Fallback -> `watchlist`

### 9.2 Entry Strategy Families

#### Quality Dislocation

Idea: fundamentally sound growth/quality stocks under price stress.

Candidate fields:

- `sales_growth_yoy >= 0.05`
- `operating_margin >= 0`
- `rsi14 < 45`
- `dist_from_52w_high <= -15`
- `sc_volatility_risk >= 65` if signal cards are available
- `market_regime in ["BEAR_RISK_OFF", "SIDEWAYS_CHOPPY", "LIQUIDITY_RALLY"]`

#### Bull Leadership

Idea: risk-on market leader that is working now.

Candidate fields:

- `market_regime == "BULL_RISK_ON"`
- `rs_vs_spy_20d >= 3`
- `rs_vs_sector_20d >= 2`
- `sales_growth_yoy >= 0.10`
- `sma50_slope >= 0`
- `sma20_relative` not too extended

#### Oversold Rebound

Idea: tactical rebound after selling pressure starts to ease.

Candidate fields:

- `rsi14 between 25 and 42`
- `rsi_slope > 0`
- `perf_1w >= 0` or positive reversal day
- `volume_dryup_ratio <= 0.8` or `updown_volume_ratio > 1`

#### Pullback Entry

Idea: clean pullback into SMA20/SMA50 with trend intact.

Candidate fields:

- `sma50_relative between -5 and 5`
- `sma50_slope >= 0`
- `rsi14 between 38 and 58`
- require at least one confirmation: volume dry-up or relative strength.

#### Breakout Entry

Idea: confirmed breakout with volume and market support.

Candidate fields:

- `dist_from_20d_high >= -1`
- `breakout_volume_multiple >= 1.5`
- `rs_vs_spy_20d >= 0`
- avoid `BEAR_RISK_OFF` unless explicitly tested.

## 10. Exit Engine Design

The exit engine is used during historical trade simulation.

First version uses one policy per horizon, not per setup type.

### 10.1 Exit Lifecycle

For each buy signal:

1. Simulate entry price using configured entry method.
2. Compute initial stop.
3. Compute initial risk `R`.
4. Compute first target, usually `entry + target_r_multiple * R`.
5. Walk forward one bar at a time.
6. If stop is hit before target, exit full position.
7. If target is hit, sell configured partial percentage.
8. If configured, move stop to breakeven.
9. Trail remaining position.
10. Exit remainder on trailing stop, time stop, failed setup, or max simulation window.

### 10.2 No Fixed Day-N Sell

Short-term and medium-term windows are maximum windows:

- Short-term max simulation window: 30 trading days by default.
- Medium-term max simulation window: 90 trading days by default.

The trade can exit on any day inside that window.

### 10.3 Realized Return Calculation

For partial exits:

```text
realized_return_pct =
  sum(exit_leg_position_pct * leg_return_pct)
```

Example:

- Buy at 100.
- Sell 50 percent at 110: +10 percent on half position.
- Sell remaining 50 percent at 106: +6 percent on half position.
- Realized return = 0.5 * 10 + 0.5 * 6 = 8 percent.

### 10.4 MFE Capture

MFE capture measures how much of the best available move the exit policy captured.

```text
mfe_capture_pct = realized_return_pct / mfe_pct * 100
```

This is diagnostic only. The primary optimization target remains absolute realized return.

## 11. Backtest Philosophy

The backtest should judge trade lifecycle quality, not fixed-horizon price changes.

Primary output:

- Realized return after applying entry and exit policies.

Important diagnostics:

- MFE within max simulation window.
- MAE before exit.
- MFE capture ratio.
- Days held.
- Stop-out rate.
- Partial-profit hit rate.
- Trailing-stop exit rate.
- Time-stop exit rate.
- Profit factor.
- Win rate.
- Average return by entry setup, regime, archetype, and label.

## 12. Separate Optimization

### 12.1 Entry Optimization

Optimize entry rules using realized trade results after applying a fixed baseline exit policy.

Primary objective:

```text
average realized_return_pct
```

Constraints:

- Minimum number of trades.
- Maximum average MAE.
- Minimum profit factor.
- Avoid rules that only work in one small ticker sample.

### 12.2 Exit Optimization

Optimize exit policy using a fixed set of entry signals.

Primary objective:

```text
average realized_return_pct
```

Secondary diagnostics:

- MFE capture.
- Stop-out rate.
- Days held.
- Profit factor.
- Drawdown.

### 12.3 Walk-Forward Validation

Every optimization should use walk-forward validation:

```text
train period -> choose params
test period -> evaluate params out of sample
repeat
```

This prevents tuning an exit policy to one market period.

## 13. CLI Commands

Proposed CLI command group:

```text
codex-backed analyze
codex-backed backtest
codex-backed optimize-entry
codex-backed optimize-exit
codex-backed compare
codex-backed report
codex-backed validate-config
```

Examples:

```bash
codex-backed backtest --config codex-backed/configs/backtest_config.json
codex-backed optimize-entry --horizon short_term
codex-backed optimize-exit --horizon medium_term
codex-backed report --run-id run_2026_06_05
```

## 14. Reporting

Reports should focus on trade lifecycle results:

- Entry label performance.
- Entry setup performance.
- Exit reason performance.
- Realized return by regime.
- Realized return by archetype.
- MFE vs realized return.
- MAE vs realized return.
- Days held distribution.
- Partial profit hit rate.
- Trailing stop effectiveness.
- Time stop effectiveness.

The old fixed-horizon return can remain as a diagnostic, but not as the primary score.

## 15. First-Version Defaults

Recommended initial defaults:

```text
entry execution:
  default: NEXT_OPEN
  max wait: 10 trading days

short-term exit:
  max simulation days: 30
  initial stop: 2.0 ATR or nearby support
  target 1: 2.0R
  partial sell: 50 percent
  trailing stop: 2.5 ATR after target 1
  time stop: exit if less than 1 percent progress after 10 trading days

medium-term exit:
  max simulation days: 90
  initial stop: 2.5 ATR or nearby support
  target 1: 2.5R
  partial sell: 40 percent
  trailing stop: 3.0 ATR after target 1
  time stop: exit if less than 2 percent progress after 20 trading days
```

## 16. Open Design Decisions

These do not block version 1:

- Whether long-term should be included in the new engine now or later.
- Whether exits should later become setup-specific.
- Whether live position tracking should be added later.
- Whether absolute return should eventually be blended with risk-adjusted return.
- Whether old backend service functions should be imported directly or copied behind adapters.

