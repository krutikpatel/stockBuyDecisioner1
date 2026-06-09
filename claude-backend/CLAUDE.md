# CLAUDE.md — claude-backend

This file gives Claude Code the context needed to work in this directory without re-reading every source file.

## Commands

```bash
cd claude-backend
source .venv/bin/activate

# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run a single test file
PYTHONPATH=. pytest tests/test_stage3_quality_gate.py -v

# Run a single test by name
PYTHONPATH=. pytest tests/test_stage4_buy_side.py::test_buy_score_above_threshold -v

# CLI — live analysis
python -m two_path_engine.cli NVDA
python -m two_path_engine.cli INTC --verbose
python -m two_path_engine.cli AAPL,MSFT,NVDA,INTC

# Backtest
python -m backtest.run_backtest --two-path --tickers NVDA,AAPL,MSFT --start 2022-01-01 --end 2024-01-01
python -m backtest.run_backtest --two-path --tickers loser --start 2022-01-01 --end 2024-01-01
python -m backtest.run_backtest --two-path --tickers NVDA,INTC --freq 5  # weekly samples
```

## Architecture

The engine splits every stock into exactly one of two paths before scoring:

```
FeatureSnapshot (~90 fields)
        │
   QualityGate (AND-logic, 5 checks from algo_config.json)
        │
 ┌──────┴──────┐
 │             │
PASSES       FAILS
 │             │
BuySide     AvoidSide
Scorer      Scorer
 │             │
BUY/WAIT  AVOID/WATCHLIST
```

**Quality gate checks** (all must pass; thresholds in `algo_config.json → quality_gate`):
1. gross_margin ≥ 0.30 — required field; None → FAIL
2. operating_margin ≥ −0.05 — required field; None → FAIL
3. ROE ≥ 5.0 OR FCF > 0 — either condition satisfies; both absent → FAIL
4. debt_to_equity ≤ 2.0 — optional; None → skip (don't fail)
5. current_ratio ≥ 1.0 — optional; None → skip (don't fail)

**Scoring**: point accumulation (not weighted average). Each rule in the JSON config has `logic` (evaluated by RuleEngine), `points` (added if matched), and `reason` (shown in output). Score clamped to [0, 100]. BUY/AVOID threshold: 60.

## Key Files

| What you want to change | File |
|-------------------------|------|
| Quality gate thresholds | `algo_config.json → quality_gate` |
| Buy-side scoring rules | `config/buy_side_timing_config.json` |
| Avoid-side scoring rules | `config/avoid_side_deterioration_config.json` |
| BUY/AVOID score threshold | `decision_thresholds.buy_min_score` / `avoid_min_score` in the respective config JSON |
| Technical indicator periods | `algo_config.json → technical_indicators` |
| Loser universe for backtest | `backtest/loser_universe.json` |
| Gate AND-logic implementation | `two_path_engine/quality_gate.py` |
| Buy-side scorer | `two_path_engine/buy_side.py` |
| Avoid-side scorer | `two_path_engine/avoid_side.py` |
| Main orchestrator | `two_path_engine/engine.py` |
| CLI entry point | `two_path_engine/cli.py` |
| Backtest runner | `backtest/run_backtest.py` |
| FeatureSnapshot model | `app/features/feature_snapshot.py` |
| Feature builder (adapter) | `app/features/feature_builder.py` |
| Rule evaluator | `app/engine/rule_engine.py` |

## Adding a Scoring Rule

Only touch the JSON config — no Python changes needed.

**Buy-side** (`config/buy_side_timing_config.json`):
```json
{
  "id": "unique_snake_case_id",
  "logic": {"field": "rsi14", "operator": "<=", "value": 30},
  "points": 12,
  "reason": "Human-readable explanation shown in CLI output"
}
```

**Avoid-side** (`config/avoid_side_deterioration_config.json`): same structure, no negative points (avoid-side rules only add to deterioration score).

**Available operators**: `>=`, `<=`, `>`, `<`, `==`, `!=`, `in`, `not_in`, `between` (two-element list), `exists`, `missing`, `contains`.

**Available fields**: every field on `FeatureSnapshot` — see `app/features/feature_snapshot.py` for the full list. Common ones: `rsi14`, `rsi_slope`, `dist_from_52w_high`, `sma20_relative`, `sma200_relative`, `atr_percent`, `obv_trend`, `vwap_deviation`, `breakout_volume_multiple`, `chaikin_money_flow`, `max_drawdown_3m`, `stochastic_rsi`, `sales_growth_yoy`, `operating_margin`, `gross_margin`, `free_cash_flow`, `beat_rate`, `debt_to_equity`, `roe`, `eps_growth_yoy`.

## Testing Conventions

All tests use synthetic `FeatureSnapshot` objects — no network calls, no yfinance.

**Standard pattern:**
```python
from app.features.feature_snapshot import FeatureSnapshot
from two_path_engine.quality_gate import QualityGate

snap = FeatureSnapshot(
    ticker="TEST",
    price=100.0,
    gross_margin=0.55,
    operating_margin=0.20,
    roe=20.0,
    free_cash_flow=1e9,
    # all other fields default to None
)
result = QualityGate().evaluate(snap)
assert result.passes is True
```

**Custom config injection (don't touch the singleton):**
```python
from app.algo_config import AlgoConfig
from two_path_engine.quality_gate import QualityGate

cfg = AlgoConfig.from_dict({
    "quality_gate": {
        "gross_margin_min": 0.50,   # stricter
        "op_margin_min": -0.05,
        "roe_min": 5.0,
        "fcf_substitutes_roe": True,
        "debt_equity_max": 2.0,
        "current_ratio_min": 1.0,
    }
})
gate = QualityGate(algo_config=cfg)
```

**Testing the full engine (snapshot path — no I/O):**
```python
from two_path_engine.engine import TwoPathEngine

engine = TwoPathEngine()
decision = engine.analyze_snapshot(snap)   # use this in tests
# decision = engine.analyze("NVDA")        # this fetches live data — not for tests
```

If a test modifies the global `AlgoConfig` singleton, call `reset_algo_config()` in teardown.

## Backtest Design Notes

- **Pre-fetch once**: price history, SPY, QQQ, and fundamental data are fetched once per ticker before the date loop.
- **Slice per date**: `df.loc[:actual_date]` before calling `compute_technicals()` — this is what prevents lookahead.
- **Forward returns use the full df**: `_forward_return(df_full, actual_date, bars=20)` — future prices are intentionally visible here.
- **Fundamental lookahead is a known limitation**: yfinance returns current fundamentals only. Quality gate and avoid-side signals carry some lookahead in historical backtests. Buy-side timing signals (all price-derived) are clean.
- **`analyze_snapshot()` not `analyze()`**: the backtest calls `engine.analyze_snapshot(snapshot)` after manually building the snapshot from sliced data. `analyze()` would fetch live data and destroy the no-lookahead guarantee.

## Current Test Count

89 tests, 100% pass rate. Run `PYTHONPATH=. pytest tests/ -v` to confirm before and after any change.

| Stage | File | Tests |
|-------|------|-------|
| 1 — data layer | `test_stage1_data_layer.py` | 11 |
| 2 — feature snapshot | `test_stage2_feature_snapshot.py` | 14 |
| 3 — quality gate | `test_stage3_quality_gate.py` | 20 |
| 4 — buy-side | `test_stage4_buy_side.py` | 14 |
| 5 — avoid-side | `test_stage5_avoid_side.py` | 13 |
| 6 — engine routing | `test_stage6_engine.py` | 17 |

## Things Not to Break

- `app/config.py` must exist — `cache_manager.py` imports `settings` from it at module load time. Removing or renaming it breaks all provider imports.
- `app/features/feature_builder.py` is a pure adapter — it must not contain scoring logic. Scoring belongs in `buy_side.py`, `avoid_side.py`, or their JSON configs.
- `two_path_engine/engine.py:analyze_snapshot()` must remain I/O-free. It is called by the backtest for every sampled date — any network call inside it would make the backtest unusably slow.
- `algo_config.json` must retain all sections that existing services read. Removing `technical_indicators`, `market_regime`, `stock_archetype`, `valuation`, or `risk_management` breaks the corresponding services.
- The `quality_gate` section in `algo_config.json` is read by `QualityGate.__init__` via `get_algo_config()`. Removing it makes every stock pass the gate (falls back to hardcoded defaults in the `qg.get(key, default)` calls).

## Reference

- `HLD.md` — architecture overview, decision logic, design rationale
- `LLD.md` — class APIs, rule tables, data flow step-by-step, all method signatures
- `README.md` — daily CLI usage, output interpretation, daily workflow
- `BACKTEST_README.md` — backtest commands, output interpretation, CSV analysis
