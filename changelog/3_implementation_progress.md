# Improvement 7 — Implementation Progress

Plan: `3_signal_quality_improvement_plan.md`
Started: 2026-06-03
Completed: 2026-06-04

---

## Phase 1 — Invert the Signal Cards (Issues 1, 2, 3)

### Issue 1 — volatility_risk card redesign
- [x] Rewrite `score_volatility_risk()` in `signal_card_service.py`
- [x] Update `signal_cards.volatility_risk` params in `algo_config.json`

### Issue 2 — trend + momentum card redesign
- [x] Update `score_trend()` — add SMA cross-up detection, double extension penalties
- [x] Update `score_momentum()` — invert RSI tiers, oversold-recovery as top tier
- [x] Update `signal_cards.trend` params in `algo_config.json`
- [x] Update `signal_cards.momentum` params in `algo_config.json`

### Issue 3 — entry_timing card redesign
- [x] Update `score_entry_timing()` — invert RSI/VWAP/Bollinger preferences
- [x] Update `signal_cards.entry_timing` params in `algo_config.json`

---

## Phase 2 — Route Alpha Correctly (Issues 4, 5)

### Issue 4 — RSI capitulation hard gate
- [x] Add priority-150 rule to `strategy_logic_config.json`
- [x] Add RSI capitulation override in `recommendation_service.py` (all 3 horizon functions)
  - ST: returns `OVERSOLD_REBOUND_CANDIDATE`
  - MT: returns `BUY_STARTER`
  - LT: returns `ACCUMULATE_ON_WEAKNESS`
- [x] Add `rsi_capitulation_threshold`, `rsi_capitulation_growth_min` to `algo_config.json`

### Issue 5 — Regime-conditional label suppression
- [x] Add `_apply_regime_label_modifier()` in `recommendation_service.py`
- [x] Apply modifier in `build_recommendations()` after all decision logic
- [x] Add `decision_logic.regime_label_suppression` matrix to `algo_config.json`

---

## Phase 3 — Precision Fixes (Issues 6, 7)

### Issue 6 — HYPER_GROWTH archetype fixes
- [x] Add HYPER_GROWTH score floor in `scoring_service.py` `compute_scores_from_signal_cards()`
- [x] Add `signal_card_hyper_growth_weights` to `algo_config.json`
- [x] Update `compute_scores_from_signal_cards()` to select weight profile by archetype
- [x] Add HYPER_GROWTH WATCHLIST upgrade gate in `build_recommendations()`
- [x] Pass `archetype` from router to `compute_scores_from_signal_cards()`
- [x] Add hyper_growth gate params to `algo_config.json`

### Issue 7 — BUY_ON_PULLBACK gate tightening
- [x] Add RSI ≤ 52 + price-below-high gates to ST decision function
- [x] Add `bop_rsi_max`, `bop_price_below_high_min_pct` to `algo_config.json`

---

## Status

| Phase | Issue | Status |
|-------|-------|--------|
| 1 | 1 — volatility_risk redesign | ✅ done |
| 1 | 2 — trend + momentum redesign | ✅ done |
| 1 | 3 — entry_timing redesign | ✅ done |
| 2 | 4 — RSI capitulation gate | ✅ done |
| 2 | 5 — regime label suppression | ✅ done |
| 3 | 6 — HYPER_GROWTH fixes | ✅ done |
| 3 | 7 — BUY_ON_PULLBACK tightening | ✅ done |

## Verification

- [x] All 1043 tests pass (`PYTHONPATH=. pytest tests/ -v`)
- [ ] Run backtest and compare card correlations, decision P&L ordering
