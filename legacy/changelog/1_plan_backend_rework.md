# Plan: Adopt Config-Driven Strategy Router Architecture

## Context

The current backend uses a monolithic decision pipeline: all stocks pass through the same hardcoded Python if/else logic in `recommendation_service.py`, regardless of archetype. Fine-tuning thresholds requires Python code changes, not config changes. There is also a structural gap: `signal_card_service.py` and `compute_scores_from_signal_cards()` are fully implemented but **not wired into the live API** (`routers/stock.py` calls the legacy `compute_scores()` path and never passes `signal_cards` to `build_recommendations()`).

The proposed architecture in `changelog/1_backendRework.md` addresses this by:
- Moving all strategy intelligence into JSON (rule engine, scoring rules, decision thresholds)
- Adding a technical signal → setup → strategy routing layer between indicator computation and decision output
- Creating 4 strategy engines (growth_leader_pullback, downtrend_rebound, true_broken_chart_avoid, quality_growth_expensive_but_working) each with its own per-setup scoring in JSON
- Splitting the single `algo_config.json` into 5 focused config files

**The plan never breaks the live API.** Existing paths are preserved; new paths are feature-flagged.

---

## Current vs. Proposed — Key Delta

| Area | Current | Proposed |
|------|---------|----------|
| Decision logic | Hardcoded Python if/else in `recommendation_service.py` | JSON rules evaluated by `RuleEngine` |
| Strategy routing | None — same path for all archetypes | Archetype + setup + regime → named strategy engine |
| Technical signals | Evaluated inline in recommendation code | Explicit `TechnicalSignalDetector` layer (named signals) |
| Config | 1 × `algo_config.json` (12 sections) | 5 focused JSON files + `algo_config.json` kept intact |
| Signal cards in live API | **Not wired** — only used in backtest | Wired in Phase 3 |
| Backtest metrics | Fixed horizon, no benchmark-relative, no entry/exit sim | Walk-forward, entry/exit simulation, experiment manifests |
| Data layer | yfinance called directly from provider functions | Abstract `MarketDataProvider` interface + pluggable |

---

## Phase 1 — Foundation (Pure Additions, Zero Risk)

**Goal:** Add all new engine primitives. No existing file is modified.

### New files to create

**`backend/app/features/`**
- `__init__.py`
- `feature_snapshot.py` — Pydantic model with ~50 flat fields (rsi14, sma50_relative, volume_dryup_ratio, sales_growth_yoy, primary_category, secondary_tags, market_regime, selected_setup, strategy_score). Exposes `.to_dict()` for rule engine evaluation.
- `feature_builder.py` — `build_feature_snapshot(ticker, price, technicals: TechnicalIndicators, fundamentals: FundamentalData, valuation: ValuationData, earnings: EarningsData, regime_assessment) -> FeatureSnapshot`. Pure adapter — maps existing model fields to snapshot fields with no logic duplication. Key mapping: `technicals.rsi_14 → rsi14`, `fundamentals.revenue_growth_yoy → sales_growth_yoy`, archetype enum → `_ARCHETYPE_TO_CATEGORY` translation dict.

**`backend/app/engine/`**
- `__init__.py`
- `rule_engine.py` — `RuleEngine.evaluate(rule: dict, snapshot: dict) -> RuleEvaluationResult`. Supports nested `all`/`any`/`not`. Leaf operators: `>=`, `<=`, `>`, `<`, `==`, `!=`, `in`, `not_in`, `between`, `exists`, `missing`, `contains`. `None` fields → non-match + `missing_fields` list + `confidence_penalty`. `RuleEvaluationResult(matched, reasons, missing_fields, confidence_penalty)`.
- `technical_signal_detector.py` — `TechnicalSignalDetector(signal_definitions: dict, rule_engine: RuleEngine).detect(snapshot) -> dict[str, bool]`. Signal definitions read from config JSON. Returns `SignalDetectionResult(active_signals: set[str], signal_reasons, missing_fields, confidence_penalty)`.
- `setup_detector.py` — `SetupDetector(setup_definitions: dict).detect(active_signals: set[str]) -> SetupDetectionResult`. Each setup has `required_signals`, `optional_signals`, `blocking_signals`, `min_required_optional_signals`. First match in priority order wins. Returns `SetupDetectionResult(selected_setup, all_matching_setups, blocked_by, confidence)`.
- `universe_filter.py` — `UniverseFilter(config: dict).check(snapshot) -> UniverseFilterResult(tradable, reason, warnings)`. Checks min_price, min_market_cap, min_avg_volume, earnings_proximity.

**`backend/config/`** (new directory)
- `technical_setup_config.json` — Define 10 named signals and 4 setup definitions:
  - Signals: `STRONG_UPTREND`, `SMA50_PULLBACK`, `RSI_PULLBACK_ZONE`, `VOLUME_DRY_UP`, `BREAKOUT_CONFIRMED`, `RS_LEADER_VS_SECTOR`, `TRUE_BROKEN_CHART`, `BROKEN_SUPPORT`, `OVERSOLD_REVERSAL`, `EXTENDED_ABOVE_SMA20`
  - Setups: `GROWTH_LEADER_PULLBACK` (requires STRONG_UPTREND + SMA50_PULLBACK + RSI_PULLBACK_ZONE, blocks on TRUE_BROKEN_CHART), `DOWNTREND_REBOUND_CANDIDATE`, `TRUE_BROKEN_CHART_AVOID`, `BREAKOUT_MOMENTUM`
- `parameter_governance_config.json` — Frozen params (RSI period, MACD periods, ATR period), active tuning params (RSI zone thresholds in setup rules, SMA distance bounds), tuning budget limits.

**New test files:**
- `backend/tests/test_rule_engine.py`
- `backend/tests/test_technical_signal_detector.py`
- `backend/tests/test_setup_detector.py`
- `backend/tests/test_feature_builder.py`

---

## Phase 2 — Config Split + Strategy Router + 4 MVP Strategy Engines

**Goal:** Create 5 new config files. Build strategy router and 4 strategy engines driven by JSON. Still no changes to live request pipeline.

### New config files under `backend/config/`

- **`market_and_universe_config.json`** — Extract from `algo_config.json`: market_regime rules and regime weight adjustments. Add: `universe_filters` (min_price: 5, min_market_cap: 1e9, min_avg_volume: 500000), `sector_benchmarks` mapping (currently in `providers/market_data_provider.py`'s `_SECTOR_ETF_MAP`), `data_sources.active_provider: "yfinance"`.
- **`stock_classification_config.json`** — Extract `stock_archetype` section from `algo_config.json`. Rename 8 archetypes to new primary category names via `_ARCHETYPE_TO_CATEGORY` mapping. Add `secondary_tag_rules` section with JSON rules for: `HIGH_MOMENTUM`, `EXPENSIVE_VALUATION`, `HIGH_ATR`, `SECTOR_LEADER`, `EARNINGS_NEAR`, `HIGH_QUALITY`, `HIGH_SHORT_INTEREST`.
- **`strategy_logic_config.json`** — The most important new file. Contains: (1) strategy router rules (priority-ordered, each with JSON logic + `strategy` name), (2) 4 strategy engine configs with `score_rules`, `decision_thresholds`, and `risk_overrides`.
- **`parameter_governance_config.json`** — Extend skeleton from Phase 1.
- `technical_setup_config.json` — Extend from Phase 1.

### New Python files

**`backend/app/config/config_loader.py`** — `MultiSourceConfig` class. Loads 5 config files from `backend/config/` dir. Exposes properties: `universe_filters`, `market_regime_rules`, `archetype_rules`, `secondary_tag_rules`, `signal_definitions`, `setup_definitions`, `strategy_router_rules`, `strategy_engines`. Module-level singleton via `get_multi_config()`. Keeps `AlgoConfig` singleton untouched.

**`backend/app/engine/strategy_router.py`** — `StrategyRouter(config: MultiSourceConfig, rule_engine: RuleEngine).route(snapshot: FeatureSnapshot) -> StrategyRoutingResult`. Evaluates `strategy_logic_config.strategy_router.rules` in priority order; first match wins. Fallback: `watchlist_low_confidence`. Returns `StrategyRoutingResult(selected_strategy, matched_rule_id, confidence, debug_info)`.

**`backend/app/engine/config_driven_strategy_engine.py`** — `ConfigDrivenStrategyEngine(engine_name, engine_config, rule_engine).score(snapshot) -> StrategyEngineResult`. Sums `score_rules` points, evaluates `decision_thresholds` in order, applies `risk_overrides` based on secondary tags. Returns `StrategyEngineResult(strategy_name, strategy_score, recommendation, reasons, missing_data, confidence, risk_inputs)`.

### 4 MVP strategy engines in `strategy_logic_config.json`

1. **`growth_leader_pullback`** — Triggers on PROFITABLE_GROWTH_LEADER or HYPER_GROWTH_STORY + GROWTH_LEADER_PULLBACK setup. Score rules: sma50_pullback_zone (+20), rsi_pullback_zone (+20), volume_dry_up (+15), sector_relative_strength (+15), growth_quality (+15), sma50_slope_rising (+10), regime_supportive (+5). Decisions: BUY_ON_PULLBACK (≥65), WATCHLIST (≥40).
2. **`downtrend_rebound`** — Any archetype + OVERSOLD_REVERSAL signal. Score rules: rsi_oversold_recovery (+25), rsi_slope_positive (+20), volume_expanding (+20), perf_recovering (+20), sma_not_crashed (+15). Decisions: OVERSOLD_REBOUND_CANDIDATE (≥60), WATCHLIST.
3. **`true_broken_chart_avoid`** — Priority 100 router rule; always outputs TRUE_DOWNTREND_AVOID or BROKEN_SUPPORT_AVOID based on severity.
4. **`quality_growth_expensive_but_working`** — Triggers on EXPENSIVE_VALUATION tag + strong RS. Score rules: rs_leader (+30), growth_rate (+25), quality_metrics (+25), valuation_penalty (subtract if extreme), low_atr_bonus (+20). Decisions: BUY_STARTER_STRONG_BUT_EXTENDED, WAIT_FOR_PULLBACK.

### New test files
- `backend/tests/test_strategy_router.py`
- `backend/tests/test_config_driven_strategy_engine.py`
- `backend/tests/test_secondary_tags.py`
- `backend/tests/test_multi_source_config.py`

---

## Phase 3 — Wire Into API (Feature-Flagged)

**Goal:** Replace `recommendation_service.py`'s decision logic with the new engine. API contract unchanged.

### Changes to existing files

**`backend/algo_config.json`** — Add one new section:
```json
"feature_flags": {
  "use_new_strategy_engine": false
}
```

**`backend/app/routers/stock.py`** — Two targeted additions:
1. Always call `score_all_cards()` from `signal_card_service.py` and `compute_scores_from_signal_cards()` — **this fixes the existing gap where signal cards are never computed in the live API regardless of which engine is used**.
2. Feature-flag dispatch:
```python
if use_new_engine:
    engine = get_decision_engine()
    recommendations = engine.decide(ticker, price, technicals, ...)
else:
    recommendations = build_recommendations(..., signal_cards=signal_cards)
```

### New file

**`backend/app/engine/stock_decision_engine.py`** — `StockDecisionEngine` class. The single orchestrating entry point replacing `build_recommendations()`'s if/else chains.

`decide(ticker, price, technicals, fundamentals, valuation, earnings, news, signal_cards, horizons, risk_profile, regime_assessment, has_options_data) -> list[HorizonRecommendation]`

Pipeline inside `decide()`:
1. `build_feature_snapshot(...)` from Phase 1
2. `_detect_secondary_tags(snapshot)` via RuleEngine + `secondary_tag_rules` → updates `snapshot.secondary_tags`
3. `signal_detector.detect(snapshot)` → `active_signals`
4. `setup_detector.detect(active_signals)` → updates `snapshot.selected_setup`
5. `strategy_router.route(snapshot)` → `selected_strategy`
6. For each horizon: `strategy_engines[selected_strategy].score(snapshot_for_horizon)` → `StrategyEngineResult`
7. Map to `HorizonRecommendation` — reuse `compute_risk_management()` from `risk_management_service.py` for entry/exit/sizing
8. Reuse `compute_completeness()` from `data_completeness_service.py` for `confidence_score`

The output must populate all existing `HorizonRecommendation` fields (horizon, decision, score, confidence, confidence_score, summary, bullish_factors, bearish_factors, entry_plan, exit_plan, risk_reward, position_sizing, data_warnings, signal_cards_weights). This preserves the API contract exactly.

**Feature flag gate:** Start at `false`. After manual parity testing on NVDA, AAPL, SPY (diverse archetype + regime combos), flip to `true`.

### New test files
- `backend/tests/test_stock_decision_engine.py` — end-to-end with fixture data for each archetype/regime
- `backend/tests/test_engine_output_parity.py` — parametric tests confirming all `HorizonRecommendation` fields are present and correctly typed in both old and new paths

---

## Phase 4 — Backtest Enhancement

**Goal:** Add walk-forward validation, entry/exit simulation, benchmark-relative metrics, experiment tracking.

### New backtest files

- **`backend/backtest/walk_forward.py`** — `WalkForwardValidator(wf_config, algo_config).run(data, tickers)`. Generates folds (train_window_weeks=104, test_window_weeks=26, step_weeks=13). Calls existing `run_backtest()` for each fold. Returns `WalkForwardResult` with per-fold IS vs OOS metrics + `oos_vs_is_consistency` overfitting indicator.
- **`backend/backtest/entry_simulator.py`** — `EntrySimulator.simulate_entry(signal, price_df, method, max_wait_days=10)`. Methods: `NEXT_CLOSE`, `NEXT_OPEN`, `PULLBACK_TO_SMA20`, `PULLBACK_TO_SMA50`, `BREAKOUT_CONFIRMATION`.
- **`backend/backtest/exit_simulator.py`** — `ExitSimulator.simulate_exit(signal, price_df, entry_price, entry_date, method, horizon)`. Methods: `FIXED_HORIZON`, `ATR_STOP_TARGET`, `TRAILING_STOP`.
- **`backend/backtest/experiment_tracker.py`** — `ExperimentTracker(experiments_dir)`. Saves `ExperimentManifest` (experiment_id, changed_params, code_version, config_hash, primary_metric). Methods: `start_experiment()`, `save_results()`, `compare_to_baseline()`, `list_experiments()`.
- **`backend/backtest/run_walk_forward.py`** — CLI entry point.

### Existing backtest files modified

- **`backend/backtest/outcome.py`** — Add optional `entry_method` / `exit_method` params to `attach_outcomes()`. Default = current fixed-horizon behavior (backward compatible).
- **`backend/backtest/run_backtest.py`** — Add `--experiment-id` and `--walk-forward` CLI flags.
- **`backend/backtest/metrics.py`** — Add Sharpe, Sortino, Calmar, MAE, MFE columns. Add `by_setup` and `by_strategy` aggregation sections alongside existing `by_decision`, `by_archetype`, `by_regime`.

---

## Phase 5 — Data Layer Abstraction

**Goal:** Wrap yfinance behind a `MarketDataProvider` interface. Add parquet cache for backtesting.

### New files

- **`backend/app/data/providers/base.py`** — Abstract `MarketDataProvider` with methods: `get_price_history`, `get_fundamentals`, `get_company_profile`, `get_earnings_calendar`, `get_news`, `get_benchmark_history`. Property: `supports_point_in_time_fundamentals = False`.
- **`backend/app/data/providers/yfinance_provider.py`** — `YFinanceProvider(MarketDataProvider)`. Wraps existing provider functions from `app/providers/` — calls them internally, no logic duplication.
- **`backend/app/data/providers/provider_factory.py`** — `ProviderFactory.create(provider_name, config) -> MarketDataProvider`. Reads `active_provider` from `market_and_universe_config.json`.
- **`backend/app/data/cache/parquet_store.py`** — `ParquetCacheStore(cache_dir)`. Methods: `has_coverage()`, `read()`, `write()`, `get_missing_ranges()`. Layout: `data/cache/raw/{provider}/{data_type}/{ticker}_{interval}_{start}_{end}.parquet`. Parallel to existing pickle cache — writes both formats during transition.
- **`backend/app/data/cache/cache_metadata.py`** — Saves provenance JSON alongside each parquet file (ticker, provider, fetched_at, schema_version, adjusted_prices).

**No existing files modified in Phase 5.**

---

## Files Changed Summary

| Phase | New Files | Modified Files |
|-------|-----------|----------------|
| 1 | 10 files (feature_snapshot, rule_engine, signal_detector, setup_detector, universe_filter, feature_builder, 2 config JSONs, 4 test files) | 0 |
| 2 | 12 files (3 config JSONs + 2 Python engine files + config_loader + 4 test files) | 1 (technical_setup_config.json extended) |
| 3 | 3 files (stock_decision_engine, 2 test files) | 2 (routers/stock.py + algo_config.json) |
| 4 | 5 files (walk_forward, entry_simulator, exit_simulator, experiment_tracker, run_walk_forward) | 3 (outcome.py, run_backtest.py, metrics.py) |
| 5 | 7 files (base, yfinance_provider, provider_factory, parquet_store, cache_metadata + 2 __init__.py) | 0 |

**Key reused functions (do not rewrite):**
- `compute_risk_management()` in `risk_management_service.py` — reused in Phase 3 for entry/exit/sizing
- `compute_completeness()` in `data_completeness_service.py` — reused in Phase 3 for confidence
- Existing 55+ indicator calculations in `technical_analysis_service.py` — unchanged, feed into FeatureBuilder
- `run_backtest()` in `backtest/runner.py` — reused as-is by WalkForwardValidator

---

## Verification Plan

### Phase 1
```bash
cd backend && source .venv/bin/activate
PYTHONPATH=. pytest tests/test_rule_engine.py tests/test_feature_builder.py tests/test_technical_signal_detector.py tests/test_setup_detector.py -v
# All existing tests must still pass:
PYTHONPATH=. pytest tests/ -v
```

### Phase 2
```bash
PYTHONPATH=. pytest tests/test_strategy_router.py tests/test_config_driven_strategy_engine.py tests/test_secondary_tags.py -v
# Test each of the 4 strategy engines with synthetic FeatureSnapshot:
# - growth leader with all required signals present → BUY_ON_PULLBACK
# - broken chart → TRUE_DOWNTREND_AVOID regardless of archetype
```

### Phase 3
1. Start API: `uvicorn app.main:app --reload --port 8000`
2. Call with `use_new_strategy_engine = false` (default) — verify response shape unchanged
3. Set flag to `true` in `algo_config.json`
4. Call with NVDA (growth leader), JNJ (defensive), a broken-chart stock
5. Confirm `decision`, `entry_plan`, `exit_plan` fields all present and non-null
6. Run parity tests: `PYTHONPATH=. pytest tests/test_engine_output_parity.py -v`

### Phase 4
```bash
python -m backtest.run_backtest --tickers AAPL,MSFT,NVDA --start 2022-01-01 --end 2024-01-01
python -m backtest.run_walk_forward --tickers AAPL,MSFT --start 2019-01-01 --end 2024-01-01
# Check results/report.html has by_setup and by_strategy sections
```

### Phase 5
```bash
# Verify provider abstraction doesn't change data output:
PYTHONPATH=. python -c "
from app.data.providers.provider_factory import ProviderFactory
p = ProviderFactory.create('yfinance')
df = p.get_price_history('AAPL', '2023-01-01', '2023-06-01')
print(df.shape, df.columns.tolist())
"
```
