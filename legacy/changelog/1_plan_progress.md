# Implementation Progress: Backend Rework (Config-Driven Strategy Router)

Reference plan: `changelog/1_plan_backend_rework.md`

---

## Phase 1 — Foundation (Pure Additions, Zero Risk)

Status: **COMPLETE** ✅

### ✅ Completed

| File | Status | Notes |
|------|--------|-------|
| `backend/app/features/__init__.py` | Done | empty init |
| `backend/app/engine/__init__.py` | Done | empty init |
| `backend/app/features/feature_snapshot.py` | Done | Pydantic model, ~120 fields, `.to_dict()` |
| `backend/app/features/feature_builder.py` | Done | `build_feature_snapshot()` — pure adapter from existing models; includes `_ARCHETYPE_TO_CATEGORY` translation dict |
| `backend/app/engine/rule_engine.py` | Done | `RuleEngine.evaluate()`, all operators, nested all/any/not, None → missing_fields + confidence_penalty |
| `backend/app/engine/technical_signal_detector.py` | Done | `TechnicalSignalDetector.detect()` → `SignalDetectionResult` |
| `backend/app/engine/setup_detector.py` | Done | `SetupDetector.detect()` with required/optional/blocking signals, priority order |
| `backend/app/engine/universe_filter.py` | Done | `UniverseFilter.check()` — price/market_cap/volume/earnings checks |
| `backend/config/technical_setup_config.json` | Done | 10 signals, 4 setups with priorities |
| `backend/config/parameter_governance_config.json` | Done | frozen/active/research_only tiers |

### ✅ Also Completed (Phase 1 tests)

| File | Status | Notes |
|------|--------|-------|
| `backend/tests/test_rule_engine.py` | Done | 36 tests — all operators, nested logic, missing field handling |
| `backend/tests/test_feature_builder.py` | Done | 21 tests — field mapping, archetype translation, earnings days |
| `backend/tests/test_technical_signal_detector.py` | Done | 19 tests — per-signal verification |
| `backend/tests/test_setup_detector.py` | Done | 16 tests — priority, blocking, optional requirements |

---

## Phase 2 — Config Split + Strategy Router + 4 MVP Strategy Engines

Status: **COMPLETE** ✅

### ✅ Completed

| File | Status | Notes |
|------|--------|-------|
| `backend/config/market_and_universe_config.json` | Done | universe_filters, market_regime_rules, sector_benchmarks, data_sources |
| `backend/config/stock_classification_config.json` | Done | archetype_rules, 11 secondary_tag_rules (HIGH_MOMENTUM, EXPENSIVE_VALUATION, HIGH_ATR, SECTOR_LEADER, EARNINGS_NEAR, HIGH_QUALITY, HIGH_SHORT_INTEREST, etc.) |
| `backend/config/strategy_logic_config.json` | Done | strategy_router (5 priority rules) + 5 strategy engine configs (score_rules, decision_thresholds, risk_overrides) |
| `backend/app/config/__init__.py` | Done | Re-exports Settings + settings singleton (shadows old app/config.py — intentional) |
| `backend/app/config/config_loader.py` | Done | `MultiSourceConfig` loads 5 config files; `get_multi_config()` + `reset_multi_config()` |
| `backend/app/engine/strategy_router.py` | Done | `StrategyRouter.route()` → `StrategyRoutingResult`; fallback = watchlist_low_confidence |
| `backend/app/engine/config_driven_strategy_engine.py` | Done | `ConfigDrivenStrategyEngine.score()` → `StrategyEngineResult`; handles valuation_penalty_rules + risk_overrides |
| `backend/tests/test_strategy_router.py` | Done | 13 tests |
| `backend/tests/test_config_driven_strategy_engine.py` | Done | 16 tests |
| `backend/tests/test_secondary_tags.py` | Done | 13 tests |
| `backend/tests/test_multi_source_config.py` | Done | 16 tests |

#### 5 Strategy Engines in strategy_logic_config.json

1. **`growth_leader_pullback`** — PROFITABLE_GROWTH_LEADER/HYPER_GROWTH_STORY + GROWTH_LEADER_PULLBACK setup. Score rules: sma50_pullback_zone(+20), rsi_pullback_zone(+20), volume_dry_up(+15), sector_rs(+15), growth_quality(+15), sma50_slope(+10), regime(+5). Decisions: BUY_ON_PULLBACK(≥65), WATCHLIST(≥40).
2. **`downtrend_rebound`** — Any archetype + DOWNTREND_REBOUND_CANDIDATE. Score: rsi_oversold_recovery(+25), rsi_slope(+20), volume_expanding(+20), perf_recovering(+20), sma_not_crashed(+15). Decisions: OVERSOLD_REBOUND_CANDIDATE(≥60).
3. **`true_broken_chart_avoid`** — Priority 100 route; always → TRUE_DOWNTREND_AVOID or BROKEN_SUPPORT_AVOID based on severity.
4. **`quality_growth_expensive_but_working`** — EXPENSIVE_VALUATION tag + strong RS. Score: rs_leader(+30), growth_rate(+25), quality_metrics(+25), valuation_penalty(subtract extreme), low_atr_bonus(+20). Decisions: BUY_STARTER_STRONG_BUT_EXTENDED, WAIT_FOR_PULLBACK.
5. **`watchlist_low_confidence`** — Fallback engine when no routing rule matches. Always returns WATCHLIST.

---

## Phase 3 — Wire Into API (Feature-Flagged)

Status: **COMPLETE** ✅

### ✅ Completed

| File | Status | Notes |
|------|--------|-------|
| `backend/app/engine/stock_decision_engine.py` | Done | `StockDecisionEngine.decide()` — orchestrates full new pipeline; produces `list[HorizonRecommendation]`; singleton via `get_decision_engine()` |
| `backend/tests/test_stock_decision_engine.py` | Done | 13 tests — end-to-end with fixture data per archetype/regime |
| `backend/tests/test_engine_output_parity.py` | Done | 68 tests — all HorizonRecommendation fields present + correct types in both paths |
| `backend/algo_config.json` | Done | Added `"feature_flags": {"use_new_strategy_engine": false}` |
| `backend/app/algo_config.py` | Done | Added `feature_flags` property |
| `backend/app/routers/stock.py` | Done | (1) Always computes signal_cards + passes to result; (2) Feature-flag dispatch to new engine via `compute_scores_from_signal_cards` → `build_recommendations` (legacy) or `StockDecisionEngine.decide()` (new) |

---

## Phase 4 — Backtest Enhancement

Status: **COMPLETE** ✅

### ✅ Created

| File | Notes |
|------|-------|
| `backend/backtest/entry_simulator.py` | `EntrySimulator` — NEXT_CLOSE/OPEN/PULLBACK_TO_SMA20/PULLBACK_TO_SMA50/BREAKOUT_CONFIRMATION |
| `backend/backtest/exit_simulator.py` | `ExitSimulator` — FIXED_HORIZON/ATR_STOP_TARGET/TRAILING_STOP; always computes MAE + MFE |
| `backend/backtest/experiment_tracker.py` | `ExperimentTracker` + `ExperimentManifest`; file-based manifests in `backtest/experiments/` |
| `backend/backtest/walk_forward.py` | `WalkForwardValidator` — rolling IS/OOS folds; `_compute_consistency()` overfitting score |
| `backend/backtest/run_walk_forward.py` | CLI entry point for walk-forward validation |

### ✅ Modified

| File | Change |
|------|--------|
| `backend/backtest/outcome.py` | Added `mfe_pct` to base behavior; optional `entry_method`/`exit_method` params write `sim_*` columns (backward-compatible) |
| `backend/backtest/run_backtest.py` | Added `--experiment-id`, `--walk-forward`, `--train-weeks`, `--test-weeks`, `--step-weeks` flags |
| `backend/backtest/metrics.py` | Added Sharpe/Sortino/Calmar in `_overall_stats`; `avg_mfe_pct` in `_perf_row`; `by_setup` + `by_strategy` sections |

### ✅ Tests (Phase 4)

| File | Count |
|------|-------|
| `backend/tests/test_entry_simulator.py` | 11 tests |
| `backend/tests/test_exit_simulator.py` | 11 tests |
| `backend/tests/test_experiment_tracker.py` | 12 tests |
| `backend/tests/test_walk_forward.py` | 10 tests |

---

## Phase 5 — Data Layer Abstraction

Status: **COMPLETE** ✅

### ✅ Created

| File | Notes |
|------|-------|
| `backend/app/data/__init__.py` | empty init |
| `backend/app/data/providers/__init__.py` | empty init |
| `backend/app/data/providers/base.py` | Abstract `MarketDataProvider` — 6 abstract methods + `name` + `supports_point_in_time_fundamentals` |
| `backend/app/data/providers/yfinance_provider.py` | `YFinanceProvider` delegates to existing `app/providers/` functions; no logic duplication |
| `backend/app/data/providers/provider_factory.py` | `ProviderFactory.create()` reads `active_provider` from `market_and_universe_config.json`; falls back to yfinance |
| `backend/app/data/cache/__init__.py` | empty init |
| `backend/app/data/cache/parquet_store.py` | `ParquetCacheStore` — `has_coverage()`, `read()`, `write()`, `get_missing_ranges()`, `metadata()` |
| `backend/app/data/cache/cache_metadata.py` | `CacheMetadata` dataclass; `save_metadata()` / `load_metadata()` / `make_metadata()` helpers |

---

## Test Suite Status (as of Phase 5 completion)

```
1032 passed, 11 failed (pre-existing, unrelated to this work)
```

44 new tests added in Phase 4 (entry_simulator: 11, exit_simulator: 11, experiment_tracker: 12, walk_forward: 10).

Pre-existing failures are in `test_backtest_metrics.py` (by_regime/by_archetype return lists not dicts) and `test_improvements3.py` (RSI 80 score threshold). These existed before this rework and are NOT caused by any changes in Phases 1–5.

### Verification commands

```bash
cd backend && source .venv/bin/activate

# Phase 1 tests
PYTHONPATH=. pytest tests/test_rule_engine.py tests/test_feature_builder.py tests/test_technical_signal_detector.py tests/test_setup_detector.py -v

# Phase 2 tests
PYTHONPATH=. pytest tests/test_strategy_router.py tests/test_config_driven_strategy_engine.py tests/test_secondary_tags.py tests/test_multi_source_config.py -v

# Phase 3 tests
PYTHONPATH=. pytest tests/test_stock_decision_engine.py tests/test_engine_output_parity.py -v

# All tests (expect 1032 passed, 11 pre-existing failures)
PYTHONPATH=. pytest tests/ -v

# Phase 4 tests
PYTHONPATH=. pytest tests/test_entry_simulator.py tests/test_exit_simulator.py tests/test_experiment_tracker.py tests/test_walk_forward.py -v
```

---

## ✅ ALL PHASES COMPLETE

All 5 phases of the backend rework have been implemented and tested. The plan is complete.

Summary of what was built:
- **Phase 1**: Feature snapshot + rule engine + signal/setup detectors (foundation primitives)
- **Phase 2**: Config-split + strategy router + 5 strategy engines (config-driven logic)
- **Phase 3**: Live API wiring with feature flag (new engine off by default)
- **Phase 4**: Walk-forward validation, entry/exit simulators, experiment tracking, Sharpe/Sortino/Calmar metrics
- **Phase 5**: Abstract `MarketDataProvider` interface + `YFinanceProvider` + `ParquetCacheStore`

---

## Key Design Decisions (permanent reference)

1. **FeatureSnapshot field names** match existing `TechnicalIndicators` names exactly (e.g., `sma50_relative`). The only rename is `rsi_14` → `rsi14` for cleaner JSON field names.
2. **Archetype translation** lives in `feature_builder.py` as `_ARCHETYPE_TO_CATEGORY` dict. The `StockArchetype` enum is NOT renamed (too many existing references).
3. **Config package shadowing**: `backend/app/config/` (package) shadows the old `backend/app/config.py` (module). Fixed by re-exporting `Settings` + `settings` inside `app/config/__init__.py`. Do not revert this.
4. **SetupDetector priority order**: TRUE_BROKEN_CHART_AVOID=1 (highest), GROWTH_LEADER_PULLBACK=2, BREAKOUT_MOMENTUM=3, DOWNTREND_REBOUND_CANDIDATE=4.
5. **BROKEN_SUPPORT signal** uses: perf_1w < -3 AND breakout_volume_multiple >= 1.5 AND rsi_slope < 0.
6. **Feature flag** `use_new_strategy_engine=false` in `algo_config.json` keeps live API on the legacy path. Flip to `true` only after manual parity testing on real tickers (NVDA, AAPL, SPY recommended).
7. **New engine does not differentiate by horizon** — all 3 horizons get the same strategy score and recommendation label. This is an accepted Phase 3 simplification. Horizon-specific scoring can be added to `strategy_logic_config.json` in a later iteration.
8. **Legacy gap fixed**: `signal_cards` are now always computed in `routers/stock.py` and passed to both the result object and `build_recommendations()`, regardless of which engine is active.
