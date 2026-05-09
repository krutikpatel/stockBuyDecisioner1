# Config Migration Progress

All algo parameters are being moved from hardcoded service constants into `algo_config.json`.
Each step adds `algo_config: Optional[AlgoConfig] = None` to service functions and reads
parameters from config. Default values always match original hardcoded values, so all
existing tests remain green after every step.

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Complete

---

## Steps

### Step 1: AlgoConfig Loader Infrastructure
- Status: [x] Complete
- Files created:
  - `algo_config.json` — 12 top-level sections with all default param values
  - `app/algo_config.py` — `AlgoConfig` class, `get_algo_config()` singleton, `reset_algo_config()`
  - `tests/test_algo_config.py` — 22 tests
  - `CONFIG_MIGRATION_PROGRESS.md` — this file
- Tests added: 22 (loads, sections, defaults, from_dict, env override, sum validations)
- Baseline: 241 tests green before this step

### Step 2: Migrate `data_completeness_service.py`
- Status: [x] Complete
- Files to modify: `app/services/data_completeness_service.py`
- Files to create: `tests/test_algo_config_data_completeness.py`
- Key changes:
  - `compute_completeness()` gains `algo_config=None` param
  - `_DEDUCTIONS`, `_CONFIDENCE_CAP_THRESHOLD`, `_CONFIDENCE_CAP_VALUE`,
    `AVOID_LOW_CONFIDENCE_THRESHOLD` read from config
  - `AVOID_LOW_CONFIDENCE_THRESHOLD` kept as module-level alias for backward compat

### Step 3: Migrate `risk_management_service.py`
- Status: [x] Complete
- Files to modify: `app/services/risk_management_service.py`
- Files to create: `tests/test_algo_config_risk_management.py`
- Key changes:
  - `compute_risk_management()` gains `algo_config=None`
  - Position sizing, ATR multipliers, entry/target factors from config
  - `_POSITION_SIZING` kept as module-level alias

### Step 4: Migrate `market_regime_service.py`
- Status: [x] Complete
- Files to modify: `app/services/market_regime_service.py`
- Files to create: `tests/test_algo_config_market_regime.py`
- Key changes:
  - `classify_regime()` gains `algo_config=None`
  - VIX thresholds, regime confidences, weight adjustments from config
  - `REGIME_WEIGHT_ADJUSTMENTS` kept as module-level alias (imported by scoring_service)

### Step 5: Migrate `scoring_service.py`
- Status: [x] Complete
- Files to modify: `app/services/scoring_service.py`
- Files to create: `tests/test_algo_config_scoring.py`
- Key changes:
  - `compute_scores()` and `compute_scores_from_signal_cards()` gain `algo_config=None`
  - Weight dicts read from config; module-level aliases kept for backward compat
  - Regime composite coefficients from config

### Step 6: Migrate `technical_analysis_service.py`
- Status: [x] Complete
- Files to modify: `app/services/technical_analysis_service.py`
- Files to create: `tests/test_algo_config_technical.py`
- Key changes:
  - `compute_technicals()` gains `algo_config=None`
  - RSI/MACD/ATR periods, extension thresholds, S/R params, scoring points from config

### Step 7: Migrate `stock_archetype_service.py`
- Status: [x] Complete
- Files to modify: `app/services/stock_archetype_service.py`
- Files to create: `tests/test_algo_config_stock_archetype.py`
- Key changes:
  - `classify_archetype()` gains `algo_config=None`
  - Sector sets, revenue/beta thresholds, confidence values from config

### Step 8: Migrate `signal_card_service.py`
- Status: [x] Complete
- Files to modify: `app/services/signal_card_service.py`
- Files to create: `tests/test_algo_config_signal_cards.py`
- Key changes:
  - All 11 card scorers + `score_all_cards()` gain `algo_config=None`
  - Point tables and tier arrays driven by config; `_tier_pts()` helper added

### Step 9: Migrate `recommendation_service.py` + `valuation_analysis_service.py`
- Status: [x] Complete
- Files to modify:
  - `app/services/recommendation_service.py`
  - `app/services/valuation_analysis_service.py`
- Files to create:
  - `tests/test_algo_config_recommendation.py`
  - `tests/test_algo_config_valuation.py`
- Key changes:
  - `build_recommendations()` gains `algo_config=None`; all gate thresholds from config
  - `score_valuation()` and `score_valuation_with_archetype()` gain `algo_config=None`

### Step 10: Backtest Integration
- Status: [x] Complete
- Files to modify:
  - `backtest/runner.py`
  - `backtest/run_backtest.py`
- Key changes:
  - `run_backtest()` gains `algo_config=None`; threaded through all service calls
  - `--algo-config /path/to/experiment.json` CLI flag added

---

## Test Count History

| After Step | New Tests | Total |
|------------|-----------|-------|
| Baseline   | —         | 241   |
| Step 1     | +22       | 263   |
| Step 2     | +10       | 273   |
| Step 3     | +20       | 293   |
| Step 4     | +10       | 303   |
| Step 5     | +13       | 316   |
| Step 6     | +19       | 335   |
| Step 7     | +11       | 346   |
| Step 8     | +13       | 359   |
| Step 9     | +16       | 375   |
| Step 10    | +0        | 754 (incl. all pre-existing) |

---

## Usage After Migration

**Using default config** (no code changes needed):
```python
# Services auto-load algo_config.json via singleton
result = compute_technicals(df)
```

**Injecting a custom config for experiments**:
```python
import copy, json
from app.algo_config import AlgoConfig

base = json.load(open("algo_config.json"))
experiment = copy.deepcopy(base)
experiment["technical_indicators"]["rsi_period"] = 9
experiment["scoring"]["signal_card_short_weights"]["momentum"] = 30
experiment["scoring"]["signal_card_short_weights"]["catalyst"] = 5

cfg = AlgoConfig.from_dict(experiment)
result = compute_technicals(df, algo_config=cfg)
```

**Running backtest with custom config** (after Step 10):
```bash
python -m backtest.run_backtest --tickers AAPL,MSFT --algo-config experiments/rsi9.json
```
