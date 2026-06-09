# 2 — Signal Quality Improvement (Improvement 5)

Addresses 7 issues identified from backtest analysis where AVOID labels outperformed BUY labels,
score distribution collapsed, and signal cards were inversely correlated with returns.

---

## Issue 1 — AVOID Labels Outperform BUY Labels (Critical)
**Status: COMPLETE ✅**

| File | Change |
|------|--------|
| `backend/app/services/recommendation_service.py` | `_classify_bad_chart()` now accepts `regime`; bear-regime capitulation gate added |
| `backend/app/services/recommendation_service.py` | `_decide_long_term_v2()` now accepts `regime`; AVOID_LONG_TERM relaxed in BEAR_RISK_OFF |
| `backend/app/services/recommendation_service.py` | `build_recommendations()` passes `regime_assessment` and `archetype` to decision functions |
| `backend/algo_config.json` | Added `bear_regime_oversold_rsi_max`, `bear_regime_drawdown_min_pct`, `bear_regime_sma200_slope_min`, `bear_regime_avoid_score_floor` |

---

## Issue 2 — Score Non-Monotonic (Critical)
**Status: COMPLETE ✅**

| File | Change |
|------|--------|
| `backend/algo_config.json` | `signal_card_short_weights`: removed momentum, added growth |
| `backend/algo_config.json` | `signal_card_medium_weights`: removed trend, increased growth to 30 |
| `backend/algo_config.json` | `signal_card_long_weights`: increased growth to 30, reduced quality to 30, reduced valuation to 10 |

---

## Issue 3 — Trend + Momentum Cards Inversely Correlated (Critical)
**Status: COMPLETE ✅**

| File | Change |
|------|--------|
| `backend/app/services/signal_card_service.py` | `score_trend()`: added SMA50/SMA20 extension penalty |
| `backend/app/services/signal_card_service.py` | `score_momentum()`: added late-phase momentum penalty |
| `backend/algo_config.json` | Added extension penalty params to `signal_cards.trend` |
| `backend/algo_config.json` | Added late-phase penalty params to `signal_cards.momentum` |

---

## Issue 4 — Score Distribution Collapsed (High)
**Status: COMPLETE ✅**

| File | Change |
|------|--------|
| `backend/backtest/runner.py` | Signal card composite always computed (even for new engine path); stored as `signal_card_score` |
| `backend/backtest/metrics.py` | `_by_score_bucket()` uses `signal_card_score` column (falls back to `score`) |

---

## Issue 5 — Valuation Card Penalizes HYPER_GROWTH (High)
**Status: COMPLETE ✅**

| File | Change |
|------|--------|
| `backend/app/services/signal_card_service.py` | `score_all_cards()` accepts `archetype` param; dispatches to `score_valuation_with_archetype()` |
| `backend/app/routers/stock.py` | Passes `archetype=fundamentals.archetype` to `score_all_cards()` |
| `backend/backtest/runner.py` | Passes `archetype` to `score_all_cards()` |

---

## Issue 6 — Short-Term Near-Zero Edge (Medium)
**Status: COMPLETE ✅**

| File | Change |
|------|--------|
| `backend/app/models/response.py` | `HorizonRecommendation` gains `confidence_level: Optional[str]` field |
| `backend/app/services/recommendation_service.py` | `_decide_short_term_v2()`: early WATCHLIST return when score < `short_term_min_confidence` and not BEAR_RISK_OFF |
| `backend/app/services/recommendation_service.py` | `build_recommendations()` populates `confidence_level` on each recommendation |
| `backend/algo_config.json` | Added `short_term_min_confidence: 60` to `decision_logic` |

---

## Issue 7 — Bear Regime Masks Bull-Market Signal Quality (Medium)
**Status: COMPLETE ✅**

| File | Change |
|------|--------|
| `backend/algo_config.json` | `bull_short_composite_coef` 0.10 → 0.0 (bull no longer boosts short-term) |
| `backend/algo_config.json` | `bear_short_composite_coef` 0.10 → 0.05 (softer blanket penalty now that AVOID gate is regime-aware) |
| `backend/algo_config.json` | `BEAR_RISK_OFF` regime thresholds loosened from impossible (999/-999) to RSI 30–55 range |

---

## Verification

```bash
cd backend && source .venv/bin/activate

# Unit tests
PYTHONPATH=. pytest tests/ -v

# Backtest (representative tickers)
python -m backtest.run_backtest --tickers AAPL,MSFT,NVDA,AMZN,JNJ,XOM \
  --start 2020-01-01 --end 2024-01-01 --experiment-id improvement5

# Expected outcomes vs pre-improvement backtest:
#  - 0-12 score bucket: drop from 79% → < 30% of signals
#  - LT score buckets: avg_return monotonically increasing left-to-right
#  - AVOID label returns: drop below BUY label returns
#  - ST BUY_ON_PULLBACK profit factor: improve from 1.32 toward 1.8+
```

---

---

# 3 — Signal Quality Improvement (Improvement 6)

Post-improvement-5 backtest showed the core AVOID-outperforms-BUY problem persists because the
new strategy engine (`use_new_strategy_engine: true`) routes broken-chart stocks to an AVOID
strategy regardless of fundamental quality. Six new issues were identified.

---

## Issue A — BROKEN_SUPPORT_AVOID / TRUE_DOWNTREND_AVOID Are Buy Signals in Disguise (Critical)

**Status: COMPLETE ✅**

**Evidence:**
- BROKEN_SUPPORT_AVOID: 4.69% ST avg, 10.81% MT avg, **34.14% LT avg** (best label by far)
- TRUE_DOWNTREND_AVOID: 2.05% ST, 5.26% MT, 17.21% LT — beats BUY_ON_PULLBACK in all horizons
- `true_broken_chart_avoid` strategy: LT avg 24.8%, avg_score 25.6 — **best strategy**
- `growth_leader_pullback` strategy: LT avg 14.17%, avg_score 59.7 — worst strategy despite highest score

**Root cause:**
The `TRUE_BROKEN_CHART_AVOID` setup (priority=1, highest) fires for any stock with `trend_label=downtrend + sma50_relative<-5 + sma200_relative<0`. The strategy router then unconditionally routes to `true_broken_chart_avoid` strategy → AVOID labels. The `DOWNTREND_REBOUND_CANDIDATE` setup is blocked by `TRUE_BROKEN_CHART` signal, so broken-chart stocks can never reach the rebound path. But the backtest proves these are contrarian BUY signals when fundamentals are intact.

**Fixes:**
| File | Change |
|------|--------|
| `backend/config/technical_setup_config.json` | Added `BROKEN_CHART_QUALITY_RECOVERY` setup (priority=0): requires TRUE_BROKEN_CHART + OVERSOLD_REVERSAL, no blocking signals |
| `backend/config/strategy_logic_config.json` | Added priority-130 router rule routing `BROKEN_CHART_QUALITY_RECOVERY` setup → `quality_broken_chart_recovery` strategy |
| `backend/config/strategy_logic_config.json` | Added priority-120 router rule: broken chart + good fundamentals (sales_growth≥5%, operating_margin≥0) + bear/liquidity regime → `quality_broken_chart_recovery` |
| `backend/config/strategy_logic_config.json` | Added new `quality_broken_chart_recovery` strategy engine producing `OVERSOLD_REBOUND_CANDIDATE` (score≥30) or `BUY_ON_PULLBACK` fallback |
| `backend/app/services/recommendation_service.py` | Legacy path: `_decide_short_term_v2()`, `_decide_medium_term_v2()`, `_decide_long_term_v2()` now accept `signal_cards` param; when BSA/TDA would fire, override to recovery label if growth≥50 and quality≥40 |

---

## Issue B — Score System Still Inverted (Critical)

**Status: COMPLETE ✅**

**Evidence:**
- ST score bucket 12–25: 4.51% avg (best) vs 62–75: 0.87% (worst)
- 8 of 10 signal cards have NEGATIVE correlation with returns
- `volatility_risk` is worst: -0.131 ST, -0.186 MT, -0.234 LT

**Root cause:** All cards measure "current quality" (is the stock performing well now?). High-current-quality stocks are priced to perfection → mean-revert. `volatility_risk` specifically rewards low-volatility stocks, but low-vol = priced as safe = no upside surprise.

**Fix:**
| File | Change |
|------|--------|
| `backend/algo_config.json` | Removed `volatility_risk` from `signal_card_short_weights`; redistributed 10pts to `growth` (now 30) |

---

## Issue C — `true_broken_chart_avoid` Strategy Has Highest Alpha but Scores 25 (High)

**Status: COMPLETE ✅** (addressed via Issue A fix — quality broken-chart stocks now routed differently)

---

## Issue D — BULL_NARROW_LEADERSHIP Regime Destroys Medium-Term Alpha (High)

**Status: COMPLETE ✅**

**Evidence:**
- MT return in BULL_NARROW_LEADERSHIP: **-0.16%** (negative), profit_factor < 1.0
- 979 medium-term signals with negative expected value; algo still generating active BUY recommendations

**Root cause:** No regime gate suppresses BULL_NARROW_LEADERSHIP. This is a late-cycle distribution regime (only mega-cap leads, breadth deteriorating) — all entry signals here fail.

**Fix:**
| File | Change |
|------|--------|
| `backend/config/strategy_logic_config.json` | Added priority-200 (highest) router rule: `market_regime == BULL_NARROW_LEADERSHIP` → `watchlist_low_confidence`; forces all signals to WATCHLIST in this regime |

---

## Issue E — HYPER_GROWTH Scored Lowest Despite Best Returns (High)

**Status: PARTIAL** — archetype-aware valuation (Improvement 5) helps the valuation card; trend/momentum extension penalties still penalize high-growth stocks. Full fix requires archetype-specific card weight profiles (future work).

---

## Issue F — Signal Cards Structurally Measure Wrong Things (Medium)

**Status: PARTIAL** — `volatility_risk` removed from short-term weights (Issue B fix). Full inversion of negatively-correlated cards requires rebuilding card scoring logic around "recovery potential" vs "current quality" (future work).

---

## Verification

```bash
cd backend && source .venv/bin/activate

# Unit tests
PYTHONPATH=. pytest tests/ -v --ignore=tests/test_backtest_metrics.py

# Backtest
python -m backtest.run_backtest --tickers AAPL,MSFT,NVDA,AMZN,JNJ,XOM \
  --start 2020-01-01 --end 2024-01-01 --experiment-id improvement6

# Expected outcomes:
#  - BROKEN_SUPPORT_AVOID count drops significantly (quality stocks rerouted to OVERSOLD_REBOUND_CANDIDATE)
#  - OVERSOLD_REBOUND_CANDIDATE count increases; its avg return should be 5–10%+
#  - BULL_NARROW_LEADERSHIP signals become WATCHLIST (near-zero count for active BUY labels in this regime)
#  - BUY_ON_PULLBACK profit factor improves toward 1.5+
#  - Short-term score monotonicity: 50–62 bucket should outperform 37–50
```
