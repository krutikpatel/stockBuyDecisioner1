# Two-Path Engine — Progress Tracker

## Stages

| Stage | Description | Tests | Status |
|-------|-------------|-------|--------|
| 1 | Project scaffold + data layer | `tests/test_stage1_data_layer.py` | ✅ Done (11/11) |
| 2 | Feature snapshot | `tests/test_stage2_feature_snapshot.py` | ✅ Done (14/14) |
| 3 | Quality gate | `tests/test_stage3_quality_gate.py` | ✅ Done (20/20) |
| 4 | Buy-side engine | `tests/test_stage4_buy_side.py` | ✅ Done (14/14) |
| 5 | Avoid-side engine | `tests/test_stage5_avoid_side.py` | ✅ Done (13/13) |
| 6 | Two-path orchestrator | `tests/test_stage6_engine.py` | ✅ Done (17/17) |
| 7 | CLI | manual | ✅ Done |
| 8 | Backtest integration | `backtest/run_backtest.py` | ✅ Done |

**Total: 89/89 tests pass (all stages)**

---

## Stage 1: Project Scaffold + Data Layer
**Goal:** Verify that the copied providers and analysis services can fetch and compute data.

**What was done:**
- Copied providers: market_data, fundamental, earnings, news, options
- Copied services: technical_analysis, fundamental_analysis, valuation_analysis, market_regime, stock_archetype, news_sentiment, risk_management
- Copied features: feature_snapshot, feature_builder
- Copied engine: rule_engine
- Copied models: market, fundamentals, earnings, news, request
- Updated algo_config.py: removed old sections (signal_cards, scoring, decision_logic, data_completeness, feature_flags), added quality_gate
- Updated algo_config.json: same removals + quality_gate section added
- Created venv + installed dependencies

**Tests:** `tests/test_stage1_data_layer.py`
**Status:** ✅ Done — 11/11 tests pass

---

## Stage 2: Feature Snapshot
**Goal:** feature_builder.py correctly flattens all service outputs into FeatureSnapshot.

**What was done:**
- Verified `build_feature_snapshot` maps all service outputs into flat FeatureSnapshot
- Tests cover: identity, fundamental, valuation, earnings, market data, technical fields
- Tests cover: to_dict() flat output, missing data graceful handling, earnings proximity

**Tests:** `tests/test_stage2_feature_snapshot.py`
**Status:** ✅ Done — 14/14 tests pass

---

## Stage 3: Quality Gate
**Goal:** Multi-factor AND-logic gate correctly splits quality vs deteriorating stocks.

**What was done:**
- Created `two_path_engine/quality_gate.py` with `QualityGate` class
- AND-logic: gross_margin, op_margin, (roe OR fcf > 0), debt_equity, current_ratio
- Reads thresholds from `algo_config.json quality_gate` section
- Missing required fields fail the gate; missing optional checks pass gracefully
- Custom config injection supported for tests

**Tests:** `tests/test_stage3_quality_gate.py`
**Status:** ✅ Done — 20/20 tests pass

---

## Stage 4: Buy-Side Engine
**Goal:** Dislocation-timing scorer correctly produces BUY/WAIT decisions for quality stocks.

**What was done:**
- Created `config/buy_side_timing_config.json` with 13 rules (10 positive, 3 penalty)
- Created `two_path_engine/buy_side.py` with `BuySideScorer` class
- Point-accumulation: each fired rule adds/subtracts points, clamped [0, 100]
- Decision: BUY if score >= 60, else WAIT

**Key rules:**
- RSI 20-40: +25 (deep dislocation zone)
- RSI slope > 0: +10 (momentum recovering)
- 52W high dist <= -20%: +15 (meaningful pullback)
- Volume spike >= 1.3x: +10 (accumulation)
- ATR >= 2%: +8 (volatility entry)
- Penalty RSI > 70: -20, Penalty SMA20 extended > 8%: -15

**Tests:** `tests/test_stage4_buy_side.py`
**Status:** ✅ Done — 14/14 tests pass

---

## Stage 5: Avoid-Side Engine
**Goal:** Deterioration scorer correctly produces AVOID/WATCHLIST decisions.

**What was done:**
- Created `config/avoid_side_deterioration_config.json` with 12 rules
- Created `two_path_engine/avoid_side.py` with `AvoidSideScorer` class
- Point-accumulation: higher score = more confirmed deterioration, clamped [0, 100]
- Decision: AVOID if score >= 60, else WATCHLIST

**Key rules:**
- Revenue YoY <= 0%: +20 (top-line contraction)
- Revenue QoQ < 0: +10 (sequential deceleration)
- Op margin < -5%: +20 (burning cash operationally)
- Beat rate < 40%: +15 (management missing estimates)
- Debt/equity > 2.0: +15 (elevated leverage)
- FCF negative: +10 (cash burn)

**Tests:** `tests/test_stage5_avoid_side.py`
**Status:** ✅ Done — 13/13 tests pass

---

## Stage 6: Two-Path Orchestrator
**Goal:** TwoPathEngine correctly routes to buy-side or avoid-side based on quality gate.

**What was done:**
- Created `two_path_engine/engine.py` with `TwoPathEngine` and `TwoPathDecision`
- `analyze_snapshot()`: routes pre-built FeatureSnapshot (used in tests + backtest)
- `analyze(ticker)`: full live pipeline (fetch → compute → build snapshot → route)
- `TwoPathDecision` dataclass: ticker, path_taken, decision, score, reasons, gate_reasons, missing_fields, risk_plan, snapshot
- Inline risk plan computed from price + ATR

**Tests:** `tests/test_stage6_engine.py`
**Status:** ✅ Done — 17/17 tests pass

---

## Stage 7: CLI
**Goal:** `python -m two_path_engine.cli TICKER` produces human-readable output.

**What was done:**
- Created `two_path_engine/cli.py`
- Supports single ticker, batch (comma-separated), `--verbose` flag
- Prints path, decision, score, gate reasons, signals, risk plan (verbose)

**Tests:** manual
- `python -m two_path_engine.cli NVDA` → live fetch + decision
- `python -m two_path_engine.cli INTC --verbose` → verbose output

**Status:** ✅ Done

---

## Stage 8: Backtest Integration
**Goal:** Backtest runs with `--two-path` flag across quality and loser universes.

**What was done:**
- Created `backtest/loser_universe.json` (13 known deteriorating tickers)
- Created `backtest/run_backtest.py` with `--two-path` flag
- Samples dates between `--start` and `--end` at `--freq` day intervals
- Runs TwoPathEngine.analyze() per ticker per date
- Computes 20d and 60d forward returns
- Saves CSV to `backtest/results/` with summary printed

**Usage:**
```bash
python -m backtest.run_backtest --two-path --tickers NVDA,AAPL,MSFT --start 2022-01-01 --end 2024-01-01
python -m backtest.run_backtest --two-path --tickers loser --start 2022-01-01 --end 2024-01-01
```

**Status:** ✅ Done

---

## Test Suite History

| Stage | Tests Added | Cumulative | Pass Rate |
|-------|-------------|-----------|-----------|
| Stage 1 | 11 | 11 | 100% |
| Stage 2 | 14 | 25 | 100% |
| Stage 3 | 20 | 45 | 100% |
| Stage 4 | 14 | 59 | 100% |
| Stage 5 | 13 | 72 | 100% |
| Stage 6 | 17 | 89 | 100% |
