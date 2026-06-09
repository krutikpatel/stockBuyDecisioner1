# 3 — Signal Quality Improvement Plan (Improvement 7)

Post-improvement-6 backtest confirms the core AVOID-outperforms-BUY problem is structurally
unresolved and five new/persistent issues are identified. The expert panel diagnosis points to a
single root cause: **all signal cards measure "current performance quality," but in a quality-stock
universe the alpha source is "temporary dislocation from fundamental fair value."**

Backtest date: 2026-06-03. Universe: AAPL, MSFT, NVDA, AMZN, JNJ, XOM + others.
Period: 2018–2024. 244,684 signals across three horizons.

---

## Evidence Summary

| Metric | Observed value | Target |
|--------|---------------|--------|
| LT: BROKEN_SUPPORT_AVOID avg return | **33.65%** | Should be lowest BUY label |
| LT: BUY_ON_PULLBACK avg return | **15.00%** | Should be highest BUY label |
| LT: WAIT_FOR_PULLBACK avg return | **12.83%** | Worst active label |
| ST score bucket 12–25 return | **2.46%** | Should be < 50–62 bucket |
| ST score bucket 50–62 return | **1.02%** | Should exceed 12–25 |
| volatility_risk card LT correlation | **–0.234** | Should be > 0 |
| trend card ST correlation | **–0.077** | Should be > 0 |
| RSI < 25 → LT forward return | **33.84%** | Best single predictor — unused as gate |
| BULL_RISK_ON: ORC MT return | **1.03%** | Engine still issues ORC in bull regimes |
| HYPER_GROWTH avg score | **12.9** | Best archetype, lowest score |

---

## Issue 1 — volatility_risk Card Is the Strongest Inverse Predictor (Critical)

**Evidence:** corr = –0.131 ST, –0.186 MT, –0.234 LT. The Q1 (low-score) quartile earns 29.82%
LT vs Q4 (high-score) 9.87%. Rewards quiet, low-drawdown stocks → those are priced to perfection.
Penalises high-ATR, high-drawdown stocks → those are the capitulation buys.

**Root cause:** The card rewards *current* low volatility. But in quality universe: low volatility
= stable = expensive = no upside surprise. High volatility at a moment of stress = panic selling
into a fundamentally sound company = opportunity.

**Fix — replace "reward low volatility" with "reward volatility spike relative to baseline":**

The new card measures *dislocation volatility*: is current volatility elevated vs. its own 90-day
average? If yes, the stock is experiencing a fear-driven sell-off which, in quality names, reverses.

| Sub-component | Old logic | New logic |
|---------------|-----------|-----------|
| ATR% | Low ATR → high score | ATR% spike vs 90d avg ATR% → high score |
| dd3m | Small drawdown → high score | Large drawdown in quality stock → high score |
| Weekly vol | Low vol → high score | Vol spike (current > 1.5× 90d avg) → high score |
| New: distance from 52W high | absent | Distance –20% to –40% → bonus |

**Files to change:**

| File | Change |
|------|--------|
| `backend/app/services/signal_card_service.py` | Rewrite `score_volatility_risk()` body; rename card purpose to "dislocation_opportunity" |
| `backend/algo_config.json` | Replace `signal_cards.volatility_risk` params with new dislocation params: `atr_spike_ratio_threshold` (1.5), `atr_spike_pts` (25), `dd3m_severe_opportunity_threshold` (–15), `dd3m_severe_pts` (20), `hi52w_dist_tiers` ([–20, –30, –40]), `hi52w_dist_pts` ([10, 20, 30]) |

---

## Issue 2 — trend and momentum Cards Reward Stocks Already Extended (Critical)

**Evidence:** trend corr = –0.077 ST, –0.084 MT, –0.065 LT. momentum corr = –0.060 ST, –0.071
MT. Q1 (lowest trend/momentum) earns 2.40% ST vs Q4 0.28%. The cards correctly reward
strong-trending, high-momentum stocks — but those stocks have already had their move.

**Root cause:** The trend card rewards "price above SMA200 + SMA50 rising" which identifies
confirmed uptrends. In those stocks, the expected forward return is already priced in.

**Fix — pivot trend card from "uptrend confirmation" to "early recovery detection":**

Replace the core SMA above/below binary with a two-component design:

1. **Recovery signal (new):** SMA20 crossed above SMA50 in last 10 bars → strong signal (stock
   is just beginning to recover). SMA50 slope turned positive after being negative → signal.
   Price reclaimed SMA200 from below in last 20 bars → signal.

2. **Extension penalty (already exists, needs strengthening):** Price > 15% above SMA50 → heavy
   penalty. Price > 8% above SMA20 → penalty. These are already coded but weights need doubling.

**Fix — pivot momentum card from "high RSI = good" to "RSI recovery from oversold":**

Replace RSI sweet spot (55–68) with an oversold-recovery band:
- RSI 20–35 AND RSI slope > 0 → highest score (recovering from capitulation)
- RSI 35–50 AND RSI slope > 0 → high score (early recovery)
- RSI 50–65 flat → neutral
- RSI 65–80 → penalty
- RSI > 80 → strong penalty

**Files to change:**

| File | Change |
|------|--------|
| `backend/app/services/signal_card_service.py` | `score_trend()`: add SMA cross-up detection, double extension penalty weights |
| `backend/app/services/signal_card_service.py` | `score_momentum()`: invert RSI scoring tiers; new oversold-recovery band as top tier |
| `backend/algo_config.json` | Add `signal_cards.trend.sma20_cross_sma50_lookback` (10), `sma20_cross_sma50_pts` (25), `sma50_slope_recovery_pts` (15), `sma200_reclaim_lookback` (20), `sma200_reclaim_pts` (20). Double `extension_penalty_sma50_pts` from –12 to –25, `extension_penalty_sma20_pts` from –5 to –12. |
| `backend/algo_config.json` | Add `signal_cards.momentum.oversold_recovery_rsi_max` (35), `oversold_recovery_slope_min` (0.5), `oversold_recovery_pts` (30), `early_recovery_rsi_min` (35), `early_recovery_rsi_max` (50), `early_recovery_pts` (22), `extended_rsi_min` (65), `extended_penalty_pts` (–10), `overbought_penalty_pts` (–20) |

---

## Issue 3 — entry_timing Card Rewards Near-High Entries (High)

**Evidence:** entry_timing corr = –0.034 ST, –0.059 MT, –0.044 LT. Q1 earns 1.75% ST vs Q4
0.79%. The card's highest score goes to stocks with RSI 45–65 (continuation zone) near VWAP and
within Bollinger mid-range — i.e., stocks that haven't pulled back.

**Root cause:** The card was designed for a breakout/continuation system. The backtest proves
these are the worst entries in a quality universe. The best entries are below VWAP, below
Bollinger mid, with RSI recovering from oversold.

**Fix — invert RSI scoring; reward below-VWAP and lower-Bollinger entries:**

| Sub-component | Old top score | New top score |
|---------------|--------------|--------------|
| RSI ideal zone | 45–65 | 25–40 (recovering from oversold) |
| RSI pullback | 40–45 | 40–50 (mild pullback) |
| RSI deep oversold | penalty | small bonus (extreme capitulation) |
| VWAP | 0 to +2% | –5% to 0% (below VWAP = discount) |
| Bollinger | 0.3–0.7 (mid) | 0.0–0.25 (lower third) |

**Files to change:**

| File | Change |
|------|--------|
| `backend/app/services/signal_card_service.py` | `score_entry_timing()`: swap RSI scoring tier values; invert VWAP preference (below VWAP → top score); invert Bollinger preference (lower band → top score) |
| `backend/algo_config.json` | Update `signal_cards.entry_timing` RSI params: `rsi_ideal_min` 45→25, `rsi_ideal_max` 65→40, `rsi_pullback_min` 40→40, `rsi_pullback_max` 45→50, `rsi_oversold_pts` increase from weak to moderate bonus. Update VWAP: `vwap_dev_good_max` 2→0 (reward below VWAP). Update BB: `bb_ideal_min` 0.3→0.0, `bb_ideal_max` 0.7→0.3. |

---

## Issue 4 — RSI < 30 Is the Strongest Alpha Signal but Not Used as a Hard Gate (Critical)

**Evidence:**

| RSI band | LT forward return | Count |
|----------|-----------------|-------|
| RSI < 25 | **33.84%** | 838 |
| RSI 25–35 | 19.20% | 4,847 |
| RSI 35–45 | 17.54% | 13,323 |
| RSI 65–80 | 15.98% | 11,248 |

RSI < 25 generates 33.84% LT return — the strongest single predictor in the dataset. Yet the
system routes stocks with RSI ~31 to `TRUE_DOWNTREND_AVOID` / `BROKEN_SUPPORT_AVOID` labels
(named as negatives). The `quality_broken_chart_recovery` setup captures some of these via
`OVERSOLD_REBOUND_CANDIDATE` but requires RSI turning up AND volume — too many conditions.

Currently BROKEN_SUPPORT_AVOID (RSI ~31.4 avg, return 33.65%) outperforms
OVERSOLD_REBOUND_CANDIDATE (RSI ~37.1, return 20.74%) by 13pp because BSA captures more extreme
dislocations that the ORC gate misses.

**Fix — add a dedicated RSI-capitulation hard gate in the strategy router (priority 150):**

A new priority-150 router rule fires before the quality_broken_chart_recovery rule (P130) and
after the BULL_NARROW_LEADERSHIP suppress (P200):

**Conditions:**
- `rsi_14 < 35` (deeply oversold)
- `sc_growth >= 45` (fundamental growth still intact)
- `archetype in [HYPER_GROWTH, PROFITABLE_GROWTH, TURNAROUND]`
- `market_regime not in [BULL_RISK_ON]` (don't apply in pure bull market where ORC underperforms)

**Route to:** `quality_broken_chart_recovery` strategy → produces `OVERSOLD_REBOUND_CANDIDATE`

This captures the RSI < 35 alpha pool that currently leaks into BSA/TDA labels without requiring
the RSI slope or volume conditions that the existing ORC gate demands.

**Also add a legacy path gate in `recommendation_service.py`:**

In `_decide_short_term_v2()`, `_decide_medium_term_v2()`, `_decide_long_term_v2()`: when
`rsi < 30 AND sc_growth >= 45 AND archetype in [HYPER_GROWTH, PROFITABLE_GROWTH]`, override
any AVOID or WAIT decision to `OVERSOLD_REBOUND_CANDIDATE`.

**Files to change:**

| File | Change |
|------|--------|
| `backend/config/strategy_logic_config.json` | Add priority-150 router rule: `rsi_14 < 35 AND sc_growth >= 45 AND archetype in [HYPER_GROWTH, PROFITABLE_GROWTH, TURNAROUND] AND market_regime != BULL_RISK_ON` → `quality_broken_chart_recovery` |
| `backend/app/services/recommendation_service.py` | Add RSI capitulation override in all three horizon decision functions |
| `backend/algo_config.json` | Add `decision_logic.rsi_capitulation_threshold` (35), `rsi_capitulation_growth_min` (45) |

---

## Issue 5 — Regime-Strategy Mismatch Destroys 2,300+ MT Signals in BULL_RISK_ON (High)

**Evidence:**

| Decision | BULL_RISK_ON MT return | BEAR_RISK_OFF MT return |
|----------|----------------------|------------------------|
| BUY_STARTER_STRONG_BUT_EXTENDED | **13.83%** | best in BEAR too |
| OVERSOLD_REBOUND_CANDIDATE | **1.03%** | 13.96% |
| BROKEN_SUPPORT_AVOID | **0.50%** | 16.02% |

In `BULL_RISK_ON`, mean-reversion plays (ORC: 1.03%, BSA: 0.50%) are near worthless while
momentum continuation (BSE: 13.83%) is the dominant alpha. The router currently sends ORC/BSA
signals regardless of regime — 1,619 ORC and 720 BSA medium-term signals in BULL_RISK_ON.

In `SIDEWAYS_CHOPPY`, BSE is the worst label (–1.52% MT) while ORC works well (6.87%).

**Fix — add regime-conditional label suppression in `strategy_router.py` (the engine runner)
and/or in recommendation_service.py:**

The cleanest implementation is at the **strategy output layer**, not the router itself (so the
router still routes correctly, but the label-assignment function applies a regime modifier):

**BULL_RISK_ON:**
- `OVERSOLD_REBOUND_CANDIDATE` → downgrade to `WATCHLIST` (return < WATCHLIST baseline)
- `BROKEN_SUPPORT_AVOID` → downgrade to `WATCHLIST` (return 0.50% vs WATCHLIST 0.85%)
- `BUY_ON_PULLBACK` from mean-reversion strategies → downgrade to `WAIT_FOR_PULLBACK`

**SIDEWAYS_CHOPPY:**
- `BUY_STARTER_STRONG_BUT_EXTENDED` → downgrade to `WATCHLIST`
- `WAIT_FOR_PULLBACK` → downgrade to `WATCHLIST` (–1.27% ST in choppy)

**BEAR_RISK_OFF:**
- No suppression (all labels work well; mean-reversion wins)

**LIQUIDITY_RALLY:**
- No suppression (highest returns across the board; max aggression correct)

**Files to change:**

| File | Change |
|------|--------|
| `backend/app/engine/config_driven_strategy_engine.py` | After strategy assigns label, apply `_apply_regime_label_modifier(label, regime)` which downgrades per the matrix above |
| `backend/app/services/recommendation_service.py` | Same modifier applied in `build_recommendations()` after decision is assigned |
| `backend/algo_config.json` | Add `decision_logic.regime_label_suppression` dict with suppression matrix |

---

## Issue 6 — HYPER_GROWTH Archetype Misclassified and Underscored (High)

**Evidence:**

| Archetype | Avg score | LT return |
|-----------|-----------|-----------|
| HYPER_GROWTH | **12.9** | **30.92%** |
| PROFITABLE_GROWTH | 13.1 | 16.52% |
| TURNAROUND | 15.0 | 16.11% |

HYPER_GROWTH has the lowest average score of all archetypes (12.9) yet the best long-term
return (30.92%). The system routes 65% of HYPER_GROWTH signals to `WATCHLIST`. Within
HYPER_GROWTH, even `BROKEN_SUPPORT_AVOID` generates 40.8% LT and `WATCHLIST` generates 31.16%
LT — every single decision label works well, meaning HYPER_GROWTH stocks have persistent alpha
regardless of signal quality.

**Root cause:** The signal cards penalise HYPER_GROWTH for:
1. High valuation (valuation card: no P/E, no current earnings → low score)
2. High volatility (volatility_risk card: high ATR → low score — also fixed in Issue 1)
3. Below SMA in growth drawdowns (trend card: below SMA200 → big penalty)

**Fix — add archetype-specific score floor and card weight overrides for HYPER_GROWTH:**

1. **Score floor:** In `scoring_service.py` or `signal_card_service.py`, when
   `archetype == HYPER_GROWTH`, apply a minimum composite score of 40 (prevents score of 12.9
   from triggering WATCHLIST gates).

2. **Archetype card weight profile in `algo_config.json`:** Add
   `signal_card_hyper_growth_weights` profile: remove `valuation` weight entirely (or set to 0),
   set `growth` weight to 50, set `volatility_risk` weight to 0 (until Issue 1 fix is deployed).

3. **RSI gate tightening:** For HYPER_GROWTH, the RSI capitulation threshold from Issue 4
   should be `rsi < 40` (not 35) since HYPER_GROWTH regularly has RSI 35–45 in normal pullbacks.

4. **WATCHLIST suppression:** When archetype == HYPER_GROWTH AND sc_growth >= 50 AND RSI < 55,
   the engine should not issue WATCHLIST — upgrade to at minimum `WAIT_FOR_PULLBACK`.

**Files to change:**

| File | Change |
|------|--------|
| `backend/app/services/scoring_service.py` | Add HYPER_GROWTH score floor: `if archetype == HYPER_GROWTH: composite = max(composite, 40)` |
| `backend/algo_config.json` | Add `signal_card_hyper_growth_weights` with growth=50, valuation=0, volatility_risk=0, momentum=10, trend=10, entry_timing=10, quality=20 |
| `backend/app/services/signal_card_service.py` | `score_all_cards()`: select weight profile by archetype (HYPER_GROWTH uses hyper_growth_weights) |
| `backend/app/services/recommendation_service.py` | Add HYPER_GROWTH WATCHLIST upgrade gate in `build_recommendations()` |
| `backend/algo_config.json` | Add `decision_logic.hyper_growth_watchlist_upgrade_rsi_max` (55), `hyper_growth_watchlist_upgrade_growth_min` (50) |

---

## Issue 7 — BUY_ON_PULLBACK Issued Too Broadly; Underperforms WATCHLIST (Medium)

**Evidence:**

- ST: BUY_ON_PULLBACK = 0.83% avg, WATCHLIST = 1.03%. The labelled BUY underperforms WATCHLIST.
- 4,242 ST signals labelled BUY_ON_PULLBACK — 5.2% of all signals.
- Within BUY_ON_PULLBACK (LT), score buckets 50–65, 65–80, 80–100 produce 15.28%, 14.81%,
  15.57% — the score has zero predictive power within this label. Gating is too coarse.
- Avg RSI of BUY_ON_PULLBACK = 52.7 — not a pullback; these are stocks at mid-RSI with limited
  downside cushion and already partially recovered.

**Fix — tighten BUY_ON_PULLBACK issuance conditions:**

Add three new gates to `_decide_short_term_v2()` and `_decide_medium_term_v2()` before issuing
`BUY_ON_PULLBACK`:
1. RSI ≤ 52 (actual pullback occurred; RSI 55+ is not a pullback)
2. Price ≥ 5% below 20-day high (stock has actually pulled back, not just trading sideways)
3. `market_regime != BULL_RISK_ON` for MT/LT (in bull market, WATCHLIST is better unless RSI < 45)

Stocks that fail these gates and would have been BUY_ON_PULLBACK → downgrade to
`WAIT_FOR_PULLBACK` (wait for the actual pullback to materialise).

**Files to change:**

| File | Change |
|------|--------|
| `backend/app/services/recommendation_service.py` | `_decide_short_term_v2()`, `_decide_medium_term_v2()`: add RSI ≤ 52 gate and price-below-high gate before issuing BUY_ON_PULLBACK |
| `backend/algo_config.json` | Add `decision_logic.bop_rsi_max` (52), `bop_price_below_high_min_pct` (5.0) |

---

## Implementation Order

Issues are ordered by expected alpha impact based on signal count × magnitude of misclassification:

```
Phase 1 — Invert the Signal Cards (Issues 1, 2, 3)
  Fixes the root measurement problem. All downstream decisions benefit.
  Estimated backtest impact: score monotonicity improves, card correlations flip positive.

Phase 2 — RSI Capitulation Gate + Regime Suppression (Issues 4, 5)
  Directly captures the RSI <35 alpha pool; eliminates BULL_RISK_ON mean-reversion waste.
  Estimated: ORC signal quality improves, BSA count drops as quality recoveries are rerouted.

Phase 3 — HYPER_GROWTH and BUY_ON_PULLBACK (Issues 6, 7)
  Precision improvements to specific segments.
  Estimated: HYPER_GROWTH WATCHLIST count drops 50%+; BUY_ON_PULLBACK count drops 30%
             but profit_factor improves from 1.32 toward 1.8+.
```

---

## Files Modified Summary

| File | Issues |
|------|--------|
| `backend/app/services/signal_card_service.py` | 1, 2, 3, 6 |
| `backend/app/services/recommendation_service.py` | 4, 5, 6, 7 |
| `backend/app/services/scoring_service.py` | 6 |
| `backend/app/engine/config_driven_strategy_engine.py` | 5 |
| `backend/config/strategy_logic_config.json` | 4 |
| `backend/algo_config.json` | 1, 2, 3, 4, 5, 6, 7 |

---

## Verification

```bash
cd backend && source .venv/bin/activate

# Unit tests (all should pass after each phase)
PYTHONPATH=. pytest tests/ -v

# Phase 1 verification: card correlation sign check
python -m backtest.run_backtest --tickers AAPL,MSFT,NVDA,AMZN,JNJ,XOM \
  --start 2020-01-01 --end 2024-01-01 --experiment-id improvement7_phase1

# Expected after Phase 1:
#   volatility_risk ST corr: flip from –0.131 → positive (> 0)
#   trend ST corr: improve from –0.077 toward 0 or positive
#   entry_timing ST corr: improve from –0.034

# Phase 2 verification: label P&L ordering
python -m backtest.run_backtest --tickers AAPL,MSFT,NVDA,AMZN,JNJ,XOM \
  --start 2020-01-01 --end 2024-01-01 --experiment-id improvement7_phase2

# Expected after Phase 2:
#   LT: OVERSOLD_REBOUND_CANDIDATE > BUY_ON_PULLBACK > WAIT_FOR_PULLBACK (label ordering correct)
#   BULL_RISK_ON MT: ORC count drops by >1000; those signals become WATCHLIST
#   RSI <35 signals: routed to ORC label (not BSA/TDA)

# Full verification target (all 3 phases):
#   BUY_ON_PULLBACK ST return > WATCHLIST ST return (0.83% → 2%+)
#   BROKEN_SUPPORT_AVOID LT return < OVERSOLD_REBOUND_CANDIDATE LT return
#   ST score bucket monotonicity: 25–37 < 37–50 < 50–62 < 62–75
#   HYPER_GROWTH avg score > 30 (currently 12.9)
```

---

## What This Plan Does NOT Address

- **Data quality / survivorship bias**: The universe is pre-selected quality stocks. The AVOID
  logic was designed for low-quality breakdown candidates that don't exist in this universe.
  True improvement requires adding low-quality stocks (penny stocks, high-debt companies) to
  the backtest universe so AVOID signals have genuine negative ground truth.

- **WATCHLIST volume (73% of signals)**: The majority of signals remain WATCHLIST. This is partly
  by design (conservative engine) and partly a consequence of the current issue being fixed.
  Further reducing WATCHLIST penetration requires adding more setup definitions to
  `technical_setup_config.json`.

- **Sector-level regime awareness**: JNJ (healthcare) and XOM (energy) behave differently from
  AAPL/MSFT in bear regimes. Sector-specific regime logic is future work.
