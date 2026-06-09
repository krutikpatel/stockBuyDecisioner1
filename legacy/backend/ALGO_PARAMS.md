# Algo Parameter Interface — Stock Decision Engine

> **Purpose**: Formal, exhaustive catalog of every tunable parameter in the algorithm.
> Use this file to document experiments, track changes, and reason about sensitivity.
>
> **Structure**: Parameters are grouped by processing layer, top to bottom.
> Each parameter shows: current value, type, effect, and which file owns it.

---

## Table of Contents

1. [Technical Indicator Computation](#1-technical-indicator-computation)
2. [Technical Score (score_technicals)](#2-technical-score-score_technicals)
3. [Extension Detection](#3-extension-detection)
4. [Support / Resistance Detection](#4-support--resistance-detection)
5. [Volume Trend Classification](#5-volume-trend-classification)
6. [Stock Archetype Classification](#6-stock-archetype-classification)
7. [Market Regime Classification](#7-market-regime-classification)
8. [Regime Score (for composite)](#8-regime-score-for-composite)
9. [Regime Weight Adjustments (score multipliers)](#9-regime-weight-adjustments-score-multipliers)
10. [Scoring Layer — Legacy Path (compute_scores)](#10-scoring-layer--legacy-path-compute_scores)
11. [Scoring Layer — Signal Card Path (compute_scores_from_signal_cards)](#11-scoring-layer--signal-card-path-compute_scores_from_signal_cards)
12. [Signal Card Internal Thresholds](#12-signal-card-internal-thresholds)
13. [Decision Logic Thresholds](#13-decision-logic-thresholds)
14. [Data Completeness & Confidence](#14-data-completeness--confidence)
15. [Risk Management (Entry / Exit / Sizing)](#15-risk-management-entry--exit--sizing)
16. [Valuation Score — Archetype-Adjusted](#16-valuation-score--archetype-adjusted)
17. [Experiment Log Template](#17-experiment-log-template)

---

## 1. Technical Indicator Computation

**File**: `app/services/technical_analysis_service.py`

### 1.1 Moving Averages

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `sma_periods` | `[10, 20, 50, 100, 200]` | `list[int]` | SMA windows computed on Close. All feed into trend classification, score, and extension detection. |
| `ema_periods` | `[8, 21]` | `list[int]` | EMA windows; deviations feed into Momentum and Entry Timing signal cards. |
| `sma_slope_bars` | `5` | `int` | Number of bars over which SMA slope is computed. Smaller = more responsive; larger = smoother. |

### 1.2 Momentum Indicators

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `rsi_period` | `14` | `int` | RSI lookback in bars. Shorter period = faster signal, noisier. |
| `rsi_slope_bars` | `5` | `int` | Bars over which RSI slope is measured. |
| `macd_fast` | `12` | `int` | MACD fast EMA period. |
| `macd_slow` | `26` | `int` | MACD slow EMA period. |
| `macd_signal` | `9` | `int` | MACD signal line EMA period. |
| `adx_period` | `14` | `int` | ADX (Average Directional Index) period using Wilder's smoothing. Score card uses ADX >= 30 as "strong trend". |
| `stochrsi_period` | `14` | `int` | StochRSI RSI length and outer period. |
| `stochrsi_smooth_k` | `3` | `int` | %K smoothing period. |
| `stochrsi_smooth_d` | `3` | `int` | %D smoothing period. |

### 1.3 Volatility

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `atr_period` | `14` | `int` | ATR lookback in bars. Feeds into stop-loss placement and position sizing. |
| `bb_period` | `20` | `int` | Bollinger Band SMA period. |
| `bb_std_dev` | `2.0` | `float` | Bollinger Band standard deviation width. |
| `weekly_vol_min_bars` | `10` | `int` | Minimum bars required to compute weekly volatility. |
| `monthly_vol_min_bars` | `24` | `int` | Minimum bars required to compute monthly volatility. |

### 1.4 Volume / Accumulation

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `obv_slope_bars` | `10` | `int` | OBV slope window. |
| `ad_slope_bars` | `10` | `int` | A/D line slope window. |
| `cmf_period` | `20` | `int` | Chaikin Money Flow period. |
| `vwap_period` | `20` | `int` | Rolling VWAP lookback (bars). |
| `volume_dryup_recent_bars` | `3` | `int` | Recent bars for volume dry-up numerator. |
| `volume_dryup_ref_bars` | `10` | `int` | Prior reference bars for volume dry-up denominator. |
| `breakout_vol_ref_period` | `20` | `int` | Reference window for relative volume (breakout_volume_multiple). |
| `updown_vol_period` | `20` | `int` | Period over which up/down volume ratio is computed. |

### 1.5 Relative Strength

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `rs_spy_period` | `63` | `int` | Bars for legacy RS vs SPY (rs_vs_spy). |
| `rs_benchmark_20d` | `20` | `int` | Short-window RS vs SPY and sector (rs_vs_spy_20d, rs_vs_sector_20d). |
| `rs_benchmark_63d` | `63` | `int` | Medium-window RS vs SPY, QQQ, and sector. |

### 1.6 Return Percentile Ranks

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `rank_lookback` | `252` | `int` | Historical distribution window for percentile ranking. |
| `rank_return_bars` | `[20, 63, 126, 252]` | `list[int]` | Return periods ranked: 20D, 63D (3M), 126D (6M), 252D (1Y). |

### 1.7 Drawdown & Gap

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `drawdown_3m_bars` | `63` | `int` | Max drawdown lookback for 3M metric. |
| `drawdown_1y_bars` | `252` | `int` | Max drawdown lookback for 1Y metric. |
| `gap_fill_min_gap_pct` | `2.0` | `float` | Minimum gap % to be considered a "significant gap". |
| `gap_fill_scan_bars` | `30` | `int` | Bars to scan backward for a significant gap. |

### 1.8 Performance Periods

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `perf_bars` | `{1W: 5, 1M: 21, 3M: 63, 6M: 126, 1Y: 252, 3Y: 756, 5Y: 1260}` | `dict` | Positional bar counts for each performance period. |

---

## 2. Technical Score (`score_technicals`)

**File**: `app/services/technical_analysis_service.py` → `score_technicals()`

Base score: `50.0`

| Component | Parameter | Default | Range | Effect |
|-----------|-----------|---------|-------|--------|
| Trend | `strong_uptrend_pts` | `+20` | `int` | Added when trend = `strong_uptrend`. |
| Trend | `weak_uptrend_pts` | `+5` | `int` | Added when trend = `weak_uptrend`. |
| Trend | `sideways_pts` | `-5` | `int` | Added when trend = `sideways`. |
| Trend | `downtrend_pts` | `-20` | `int` | Added when trend = `downtrend`. |
| RSI | `rsi_healthy_min` | `50` | `float` | Lower bound of healthy RSI zone. |
| RSI | `rsi_healthy_max` | `70` | `float` | Upper bound of healthy RSI zone. |
| RSI | `rsi_healthy_pts` | `+15` | `int` | Points if RSI in [50, 70]. |
| RSI | `rsi_mid_min` | `40` | `float` | Lower bound of mid zone. |
| RSI | `rsi_mid_pts` | `+5` | `int` | Points if RSI in [40, 50). |
| RSI | `rsi_overbought_threshold` | `75` | `float` | RSI above this → overbought. |
| RSI | `rsi_overbought_pts` | `-5` | `int` | Applied if RSI > 75. |
| RSI | `rsi_oversold_threshold` | `30` | `float` | RSI below this → oversold. |
| RSI | `rsi_oversold_pts` | `-15` | `int` | Applied if RSI < 30. |
| MACD | `macd_positive_pts` | `+10` | `int` | Added if MACD histogram > 0. |
| MACD | `macd_negative_pts` | `-10` | `int` | Added if MACD histogram <= 0. |
| Extension | `extension_penalty_pts` | `-10` | `int` | Applied when `is_extended = True`. |
| Volume | `vol_above_avg_pts` | `+5` | `int` | Applied when `volume_trend = above_average`. |
| Volume | `vol_below_avg_pts` | `-5` | `int` | Applied when `volume_trend = below_average`. |
| RS vs SPY | `rs_strong_threshold` | `1.2` | `float` | rs_vs_spy > this → strong. |
| RS vs SPY | `rs_strong_pts` | `+10` | `int` | Applied when rs_vs_spy > 1.2. |
| RS vs SPY | `rs_above_threshold` | `1.0` | `float` | rs_vs_spy in (1.0, 1.2] → moderate. |
| RS vs SPY | `rs_above_pts` | `+5` | `int` | Applied when rs_vs_spy in (1.0, 1.2]. |
| RS vs SPY | `rs_weak_threshold` | `0.8` | `float` | rs_vs_spy < this → weak. |
| RS vs SPY | `rs_weak_pts` | `-10` | `int` | Applied when rs_vs_spy < 0.8. |
| RS vs SPY | `rs_below_pts` | `-5` | `int` | Applied when rs_vs_spy in [0.8, 1.0). |
| Support | `support_cushion_good_pct` | `5.0` | `float` | Support within 5% of price → good cushion. |
| Support | `support_cushion_good_pts` | `+5` | `int` | Applied when cushion <= 5%. |
| Support | `support_cushion_bad_pct` | `15.0` | `float` | Support > 15% away → no cushion. |
| Support | `support_cushion_bad_pts` | `-5` | `int` | Applied when cushion > 15%. |

---

## 3. Extension Detection

**File**: `app/services/technical_analysis_service.py` → `detect_extension()`

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `ext_above_20ma_threshold` | `8.0` | `float %` | Price > SMA20 by this % → `is_extended = True`. |
| `ext_above_50ma_threshold` | `15.0` | `float %` | Price > SMA50 by this % → `is_extended = True`. |
| `ext_rsi_overbought` | `75.0` | `float` | RSI above this → `is_extended = True`. |

`is_extended` suppresses BUY_NOW in all horizons and modifies decision labels.

---

## 4. Support / Resistance Detection

**File**: `app/services/technical_analysis_service.py` → `find_support_resistance()`

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `sr_window` | `10` | `int` | Local swing high/low detection window (not currently used directly; kept for API). |
| `sr_n_levels` | `3` | `int` | Max support and resistance levels to return. |
| `sr_lookback_bars` | `60` | `int` | Number of bars to scan for swing highs/lows. |
| `sr_cluster_tolerance` | `0.01` | `float (1%)` | Levels within this % of each other are merged into one cluster. |

---

## 5. Volume Trend Classification

**File**: `app/services/technical_analysis_service.py` → `compute_volume_trend()`

| Parameter | Default | Type | Effect |
|-----------|---------|------|--------|
| `vol_trend_ref_bars` | `30` | `int` | Rolling average reference window (bars). |
| `vol_above_avg_ratio` | `1.3` | `float` | Current/avg >= 1.3 → `above_average`. |
| `vol_below_avg_ratio` | `0.7` | `float` | Current/avg <= 0.7 → `below_average`. |

---

## 6. Stock Archetype Classification

**File**: `app/services/stock_archetype_service.py` → `classify_archetype()`

Priority order is top-to-bottom. First matching rule wins.

| Archetype | Key Criteria | Confidence |
|-----------|-------------|-----------|
| `SPECULATIVE_STORY` | P/S > 20 AND unprofitable AND rev_yoy > 20% | 80 |
| `SPECULATIVE_STORY` | P/S > 40 (regardless) | 70 |
| `HYPER_GROWTH` | rev_yoy > 30% | 70 + (rev_yoy - 0.30) × 100, capped 95 |
| `HYPER_GROWTH` | rev_yoy > 20% AND fpe > 40 | 72 |
| `DEFENSIVE` | sector ∈ defensive AND beta < 0.8 | 80 |
| `DEFENSIVE` | sector ∈ defensive (any beta) | 65 |
| `COMMODITY_CYCLICAL` | sector ∈ commodity | 78 |
| `CYCLICAL_GROWTH` | beta > 1.3 AND sector ∈ cyclical | 72 |
| `PROFITABLE_GROWTH` | rev_yoy > 15% AND (op_margin > 0 OR fcf > 0) | 65 + (rev_yoy - 0.15) × 100, capped 85 |
| `TURNAROUND` | slow annual growth + eps_growth_yoy > 10% OR rev_qoq > 5%, eps > 0 | 60 |
| `MATURE_VALUE` | rev_yoy < 10% AND (fcf > 0 OR eps > 0) | 68 |
| `PROFITABLE_GROWTH` | fallback | 40 |

**Sector sets:**

```python
DEFENSIVE_SECTORS  = {"Healthcare", "Consumer Defensive", "Utilities"}
COMMODITY_SECTORS  = {"Energy", "Basic Materials"}
CYCLICAL_SECTORS   = {"Energy", "Basic Materials", "Industrials", "Consumer Cyclical"}
```

**Tunable thresholds:**

| Parameter | Default | Effect |
|-----------|---------|--------|
| `speculative_ps_min` | `20` | P/S above this + unprofitable → SPECULATIVE |
| `speculative_ps_hard` | `40` | P/S above this alone → SPECULATIVE |
| `hyper_growth_rev_yoy_min` | `0.30` | Revenue YoY above this → HYPER_GROWTH |
| `hyper_growth_rev_alt` | `0.20` | Alt hyper growth threshold (requires fpe > 40) |
| `hyper_growth_fpe_min` | `40` | fpe threshold for alt hyper growth |
| `defensive_beta_max` | `0.8` | Beta below this in defensive sector → high confidence |
| `cyclical_beta_min` | `1.3` | Beta above this in cyclical sector → CYCLICAL_GROWTH |
| `profitable_growth_rev_min` | `0.15` | Revenue YoY above this + positive ops → PROFITABLE_GROWTH |
| `turnaround_eps_growth_min` | `0.10` | Minimum EPS growth YoY for TURNAROUND |
| `turnaround_rev_qoq_min` | `0.05` | Minimum QoQ revenue for TURNAROUND |
| `mature_value_rev_max` | `0.10` | Revenue YoY below this → MATURE_VALUE candidate |

---

## 7. Market Regime Classification

**File**: `app/services/market_regime_service.py` → `classify_regime()` / `_determine_regime()`

Inputs: SPY daily OHLCV, QQQ daily OHLCV, optional VIX reading.

| Regime | Trigger Conditions | Confidence |
|--------|--------------------|-----------|
| `BEAR_RISK_OFF` | SPY below 200DMA, VIX > 25 | 82 |
| `BEAR_RISK_OFF` | SPY below 200DMA, QQQ below 200DMA, VIX > 20 | 70 |
| `SIDEWAYS_CHOPPY` | SPY below 200DMA, QQQ above 200DMA | 55 |
| `BULL_RISK_ON` | SPY above 50DMA + 200DMA, QQQ above 200DMA, VIX < 20 | 85 |
| `BULL_NARROW_LEADERSHIP` | SPY above both MAs, VIX < 20, QQQ below 200DMA | 68 |
| `LIQUIDITY_RALLY` | SPY above both MAs, VIX 20–25 | 62 |
| `BULL_RISK_ON` | SPY above both MAs, no VIX, QQQ above 200DMA | 70 |
| `BULL_NARROW_LEADERSHIP` | SPY above both MAs, no VIX, QQQ below 200DMA | 58 |
| `SIDEWAYS_CHOPPY` | SPY above 200DMA, below 50DMA | 60 |
| `LIQUIDITY_RALLY` | VIX 20–30, SPY above 200DMA | 55 |
| `SIDEWAYS_CHOPPY` | Fallback / insufficient data | 40–45 |

**VIX thresholds:**

| Parameter | Default | Effect |
|-----------|---------|--------|
| `vix_bear_threshold` | `25.0` | VIX above this → high-confidence BEAR regime |
| `vix_moderate_threshold` | `20.0` | VIX above this → some fear, below → low fear |
| `vix_liquidity_max` | `30.0` | VIX below this + SPY above 200DMA → LIQUIDITY_RALLY |
| `spy_min_bars` | `50` | Minimum bars needed to classify; otherwise defaults to SIDEWAYS_CHOPPY/20 |

---

## 8. Regime Score (for composite)

**File**: `app/services/scoring_service.py` → `_regime_score()`

Converts the regime + confidence into a 0–100 score that enters the `market_regime` slot of the short-term composite.

| Regime | Formula | Range |
|--------|---------|-------|
| `BULL_RISK_ON` | `50 + confidence × 0.35` | 50–85 |
| `BEAR_RISK_OFF` | `50 - confidence × 0.35` | 15–50 |
| `BULL_NARROW_LEADERSHIP` | `50 + confidence × 0.15` | 50–65 |
| `LIQUIDITY_RALLY` | `50 + confidence × 0.15` | 50–65 |
| `SIDEWAYS_CHOPPY` | `50.0` | fixed |
| Other / None | `50.0` | fixed |

**Tunable parameters:**

| Parameter | Default | Effect |
|-----------|---------|--------|
| `regime_score_bull_coef` | `0.35` | Multiplier on confidence for bull regimes. |
| `regime_score_bear_coef` | `0.35` | Multiplier on confidence for bear regimes. |
| `regime_score_narrow_coef` | `0.15` | Multiplier for narrow-leadership / liquidity-rally. |
| `regime_score_base` | `50.0` | Neutral baseline score. |

---

## 9. Regime Weight Adjustments (score multipliers)

**File**: `app/services/market_regime_service.py` → `REGIME_WEIGHT_ADJUSTMENTS`

Applied in `_apply_regime_multipliers()`. Each factor's intermediate score is multiplied and clamped to [0, 100].

| Regime | Factor | Multiplier |
|--------|--------|-----------|
| `BULL_RISK_ON` | `technical_momentum` | `1.20` |
| `BULL_RISK_ON` | `relative_strength` | `1.15` |
| `BULL_RISK_ON` | `growth_acceleration` | `1.15` |
| `BULL_RISK_ON` | `valuation_relative_growth` | `0.70` |
| `BULL_RISK_ON` | `fcf_quality` | `0.90` |
| `BEAR_RISK_OFF` | `valuation_relative_growth` | `1.30` |
| `BEAR_RISK_OFF` | `balance_sheet_strength` | `1.25` |
| `BEAR_RISK_OFF` | `fcf_quality` | `1.20` |
| `BEAR_RISK_OFF` | `technical_momentum` | `0.90` |
| `BEAR_RISK_OFF` | `catalyst_news` | `0.90` |
| `SIDEWAYS_CHOPPY` | `risk_reward` | `1.25` |
| `SIDEWAYS_CHOPPY` | `relative_strength` | `1.10` |
| `SIDEWAYS_CHOPPY` | `technical_momentum` | `0.85` |
| `BULL_NARROW_LEADERSHIP` | `technical_momentum` | `1.15` |
| `BULL_NARROW_LEADERSHIP` | `relative_strength` | `1.20` |
| `BULL_NARROW_LEADERSHIP` | `sector_strength` | `1.15` |
| `LIQUIDITY_RALLY` | `technical_momentum` | `1.10` |
| `LIQUIDITY_RALLY` | `catalyst_news` | `1.10` |
| `LIQUIDITY_RALLY` | `valuation_relative_growth` | `0.80` |
| `SECTOR_ROTATION` | `sector_strength` | `1.30` |
| `SECTOR_ROTATION` | `relative_strength` | `1.15` |

---

## 10. Scoring Layer — Legacy Path (`compute_scores`)

**File**: `app/services/scoring_service.py`

Used when `signal_cards` is **not** provided to `build_recommendations()`.

### 10.1 Short-Term Weights

Must sum to 100.

| Factor | Default Weight | Input Source |
|--------|---------------|-------------|
| `technical_momentum` | `30` | `technicals.technical_score` |
| `relative_strength` | `20` | `technicals.technical_score` (placeholder; refined in signal cards) |
| `catalyst_news` | `20` | `(catalyst_score + news.news_score) / 2` |
| `options_flow` | `10` | `catalyst_score` |
| `market_regime` | `10` | `_regime_score(regime_assessment)` |
| `risk_reward` | `10` | `risk_reward_score` (caller-provided) |

### 10.2 Medium-Term Weights

| Factor | Default Weight | Input Source |
|--------|---------------|-------------|
| `earnings_revision` | `25` | `earnings.earnings_score` |
| `growth_acceleration` | `20` | `fundamentals.fundamental_score` |
| `technical_trend` | `20` | `technicals.technical_score` |
| `sector_strength` | `15` | `sector_macro_score` (caller-provided) |
| `valuation_relative_growth` | `10` | `valuation.archetype_adjusted_score` or `valuation.valuation_score` |
| `catalyst_news` | `10` | `(catalyst_score + news.news_score) / 2` |

### 10.3 Long-Term Weights

| Factor | Default Weight | Input Source |
|--------|---------------|-------------|
| `business_quality` | `25` | `fundamentals.fundamental_score` |
| `growth_durability` | `20` | `fundamentals.fundamental_score` |
| `fcf_quality` | `15` | `fundamentals.fundamental_score` |
| `balance_sheet_strength` | `15` | `fundamentals.fundamental_score` |
| `valuation_relative_growth` | `15` | `valuation.archetype_adjusted_score` |
| `competitive_moat` | `10` | `fundamentals.fundamental_score` |

> **Note**: Multiple long-term factors all map to `fundamental_score`. This is intentional — the single score aggregates all quality signals — but also means improving the sub-scoring of each factor requires enhancing `fundamental_score` granularity.

---

## 11. Scoring Layer — Signal Card Path (`compute_scores_from_signal_cards`)

**File**: `app/services/scoring_service.py`

Used when `signal_cards` **is** provided to `build_recommendations()`. This is the current primary path.

### 11.1 Short-Term Signal Card Weights

| Card | Default Weight |
|------|---------------|
| `momentum` | `25` |
| `volume_accumulation` | `20` |
| `entry_timing` | `20` |
| `relative_strength` | `15` |
| `volatility_risk` | `10` |
| `catalyst` | `10` |

### 11.2 Medium-Term Signal Card Weights

| Card | Default Weight |
|------|---------------|
| `trend` | `20` |
| `growth` | `20` |
| `relative_strength` | `15` |
| `volume_accumulation` | `15` |
| `valuation` | `10` |
| `quality` | `10` |
| `catalyst` | `10` |

### 11.3 Long-Term Signal Card Weights

| Card | Default Weight |
|------|---------------|
| `quality` | `35` |
| `growth` | `20` |
| `valuation` | `15` |
| `trend` | `10` |
| `catalyst` | `10` |
| `ownership` | `5` |
| `volatility_risk` | `5` |

### 11.4 Regime Composite Adjustments (Signal Card Path)

Applied after card-weighted composite, before decision logic.

| Regime | Short-Term | Medium-Term |
|--------|-----------|------------|
| `BULL_RISK_ON` | `× (1 + conf/100 × 0.10)` | `× (1 + conf/100 × 0.05)` |
| `BEAR_RISK_OFF` | `× (1 - conf/100 × 0.10)` | `× (1 - conf/100 × 0.05)` |
| Other | no adjustment | no adjustment |

---

## 12. Signal Card Internal Thresholds

**File**: `app/services/signal_card_service.py`

Each card computes `raw / total_possible × 100` then clamps to [0, 100].

### 12.1 Momentum Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `perf_1w` | 10 | Positive: `min(10, 10 × (1 + perf/20))`; Negative: 0 |
| `perf_1m` | 15 | Same scaling rule |
| `perf_3m` | 20 | Same scaling rule |
| `macd_histogram` | 15 | Positive: `min(15, 7.5 + hist × 5)`; Negative: 0 |
| `rsi_14` | 15 | 45–65: 15pts; 65–75: 9pts; >75: 4pts; 35–45: 6pts; <35: 0 |
| `rsi_slope` | 10 | ≥5: 10; ≥1: 7; ≥-1: 5; ≥-5: 2; else: 0 |
| `ema8_relative` | 10 | >0: 10; ≤0: 0 |
| `ema21_relative` | 10 | >0: 10; ≤0: 0 |

### 12.2 Trend Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `sma20_relative` | 15 | >0: full pts; ≤0: 0 |
| `sma50_relative` | 15 | >0: full pts; ≤0: 0 |
| `sma200_relative` | 20 | >0: full pts; ≤0: 0 |
| `sma20_slope` | 10 | >0: full pts; ≤0: 0 |
| `sma50_slope` | 15 | >0: full pts; ≤0: 0 |
| `adx` | 15 | ≥30: 15; ≥20: 10; else: 5 |
| `perf_6m` | 5 | >0: 5; ≤0: 0 |
| `perf_1y` | 5 | >0: 5; ≤0: 0 |

### 12.3 Entry Timing Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `rsi_14` | 25 | 55–68: 25; 40–55: 20; 25–42: 15; 68–76: 15; >76: 5; <25: 3 |
| `stochastic_rsi` | 15 | 0.2–0.6: 15; >0.8: 5; <0.2: 8; else: 10 |
| `vwap_deviation` | 15 | 0–3%: 15; >3%: 8; <0: 5 |
| `bollinger_band_position` | 10 | 0.3–0.7: 10; >0.85: 3; <0.15: 5; else: 7 |
| `ema8_relative` | 10 | 0–3%: 10; >3%: 5; <0: 3 |
| `rsi_slope` | 10 | ≥3: 10; ≥0: 7; ≥-3: 3; else: 1 |
| `gap_percent` | 5 | -1 to +1%: 5; >3%: 1; else: 3 |

### 12.4 Volume / Accumulation Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `obv_trend` | 20 | +1: 20; -1: 0; 0: 10 |
| `ad_trend` | 15 | +1: 15; -1: 0; 0: 7 |
| `chaikin_money_flow` | 20 | >0.1: 20; >0: 12; <-0.1: 0; else: 5 |
| `breakout_volume_multiple` | 20 | ≥1.5: 20; ≥1.0: 12; else: 5 |
| `updown_volume_ratio` | 15 | ≥1.3: 15; ≥1.0: 10; else: 0 |
| `volume_dryup_ratio` | 10 | <0.7: 10; >1.2: 3; else: 6 |

### 12.5 Volatility / Risk Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `max_drawdown_3m` | 25 | ≥-5%: 25; ≥-10%: 18; ≥-20%: 10; else: 3 |
| `max_drawdown_1y` | 15 | ≥-10%: 15; ≥-25%: 8; else: 2 |
| `atr_percent` | 20 | ≤1.5%: 20; ≤3.0%: 13; ≤5.0%: 7; else: 2 |
| `volatility_weekly` | 15 | ≤20%: 15; ≤40%: 8; else: 2 |
| `beta` (from fundamentals) | 15 | 0.5–1.3: 15; ≤1.8: 8; else: 3 |
| `dist_from_52w_high` | 10 | ≥-5%: 10; ≥-15%: 6; else: 2 |

### 12.6 Relative Strength Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `rs_vs_qqq` | 30 | ≥+5%: 30; ≥0: 18; ≥-5%: 10; else: 0 |
| `return_pct_rank_20d` | 15 | ≥75th: 15; ≥50th: 9.75; ≥25th: 5.25; else: 0 |
| `return_pct_rank_63d` | 20 | ≥75th: 20; ≥50th: 13; ≥25th: 7; else: 0 |
| `return_pct_rank_126d` | 15 | ≥75th: 15; ≥50th: 9.75; ≥25th: 5.25; else: 0 |
| `return_pct_rank_252d` | 20 | ≥75th: 20; ≥50th: 13; ≥25th: 7; else: 0 |

### 12.7 Growth Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `revenue_growth_yoy` | 20 | ≥20%: 20; ≥10%: 14; ≥0: 8; else: 0 |
| `revenue_growth_qoq` | 10 | ≥5%: 10; ≥0: 7; else: 0 |
| `eps_growth_yoy` | 20 | ≥20%: 20; ≥10%: 13; ≥0: 8; else: 0 |
| `eps_growth_next_year` | 10 | ≥15%: 10; ≥0: 6; else: 0 |
| `sales_growth_ttm` | 10 | ≥15%: 10; ≥0: 6; else: 0 |
| `eps_growth_3y` | 10 | ≥15%: 10; ≥5%: 6; ≥0: 3; else: 0 |
| `sales_growth_3y` | 8 | ≥10%: 8; ≥5%: 5; ≥0: 2; else: 0 |
| `eps_growth_next_5y` | 7 | ≥15%: 7; ≥8%: 4; else: 1 |
| `beat_rate` | 20 | ≥75%: 20; ≥50%: 12; else: 0 |
| `avg_eps_surprise_pct` | 10 | ≥5%: 10; ≥2%: 7; ≥0: 4; else: 0 |

### 12.8 Valuation Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `forward_pe` | 20 | ≤15: 20; ≤25: 13; ≤40: 7; else: 2 |
| `peg_ratio` | 20 | ≤1.0: 20; ≤1.5: 14; ≤2.5: 8; else: 2 |
| `price_to_sales` | 15 | ≤3: 15; ≤8: 9; ≤15: 5; else: 1 |
| `ev_to_ebitda` | 15 | ≤12: 15; ≤20: 9; ≤35: 4; else: 1 |
| `fcf_yield` | 15 | ≥5%: 15; ≥2%: 9; ≥0: 4; else: 0 |
| `ev_sales` | 15 | ≤3: 15; ≤8: 9; ≤15: 4; else: 1 |

### 12.9 Quality Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `gross_margin` | 15 | ≥50%: 15; ≥30%: 9; else: 3 |
| `operating_margin` | 15 | ≥20%: 15; ≥10%: 9; ≥0: 4; else: 0 |
| `roe` | 15 | ≥20%: 15; ≥10%: 9; ≥0: 4; else: 0 |
| `roic` | 15 | ≥15%: 15; ≥8%: 9; ≥0: 4; else: 0 |
| `roa` | 10 | ≥10%: 10; ≥5%: 6; ≥0: 3; else: 0 |
| `current_ratio` | 10 | ≥2.0: 10; ≥1.2: 7; else: 2 |
| `quick_ratio` | 10 | ≥1.5: 10; ≥1.0: 7; else: 2 |
| `debt_to_equity` | 7 | ≤50%: 7; ≤100%: 4; ≤200%: 2; else: 0 |
| `long_term_debt_equity` | 8 | ≤30%: 8; ≤80%: 5; ≤150%: 2; else: 0 |

### 12.10 Ownership Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `insider_ownership` | 15 | ≥10%: 15; ≥3%: 10; else: 5 |
| `insider_transactions` | 20 | >0: 20; =0: 10; <0: 0 |
| `institutional_ownership` | 15 | 50–90%: 15; <30%: 5; else: 9 |
| `institutional_transactions` | 20 | >0: 20; =0: 10; <0: 0 |
| `short_float` | 20 | ≤5%: 20; ≤10%: 12; ≤20%: 6; >20%: 8 (squeeze dual signal) |
| `short_ratio` | 10 | ≤3 days: 10; ≤7 days: 6; else: 2 |

### 12.11 Catalyst Card

| Component | Weight | Scoring Rules |
|-----------|--------|--------------|
| `analyst_recommendation` | 25 | ≤1.5: 25; ≤2.5: 18; ≤3.5: 10; ≤4.0: 4; else: 0 |
| `target_price_distance` | 20 | ≥20%: 20; ≥10%: 14; ≥0: 8; else: 0 |
| `news_score` | 25 | ≥70: 25; ≥55: 18; ≥45: 12; ≥30: 5; else: 0 |
| `beat_rate` | 15 | ≥75%: 15; ≥50%: 9; else: 0 |
| `within_30_days` | 15 | True: 10 pts; False: 12 pts |

---

## 13. Decision Logic Thresholds

**File**: `app/services/recommendation_service.py`

### 13.1 Shared Override Gates (all horizons)

| Gate | Trigger | Decision Forced |
|------|---------|----------------|
| **Chart is weak** | `trend = downtrend` AND `rs_vs_spy < 0.8` | `AVOID_BAD_CHART` |
| **Business deteriorating** | `rev_yoy < 0` AND (`op_margin < -5%` OR `beat_rate < 40%`) | `AVOID_BAD_BUSINESS` |

### 13.2 Short-Term v2 (Primary Path: `_decide_short_term_v2`)

#### Per-Regime Entry Thresholds (`RegimeThresholds`)

| Regime | `rsi_min` | `rsi_max` | `sma20_max %` | `rel_vol_min` |
|--------|----------|----------|--------------|--------------|
| `LIQUIDITY_RALLY` | 55.0 | 74.0 | 8.0 | 1.2 |
| `BULL_RISK_ON` | 55.0 | 68.0 | 5.0 | 1.3 |
| `SIDEWAYS_CHOPPY` | 40.0 | 58.0 | 3.0 | 1.3 |
| `BEAR_RISK_OFF` | 999.0 | -999.0 | 0.0 | 999.0 |
| `BULL_NARROW_LEADERSHIP` | 55.0 | 68.0 | 5.0 | 1.3 |
| Default | 55.0 | 68.0 | 5.0 | 1.3 |

#### Decision Priority Order

| Priority | Label | Gate Conditions |
|----------|-------|----------------|
| 1 | `_classify_bad_chart()` | `chart_is_weak AND score < 50` OR `score < 40` |
| 2 | `OVERSOLD_REBOUND_CANDIDATE` | RSI ∈ [25, 42] AND rsi_slope > 0 AND (perf_1w ≥ 0 OR change_from_open > 0) AND rel_vol ≥ 1.2 |
| 3 | `WAIT_FOR_PULLBACK` | `perf_1w > 10%` OR `perf_1m > 25%` OR `sma20_relative > 10%` |
| 4 | `BUY_ON_PULLBACK` | In `SIDEWAYS_CHOPPY` AND score ≥ 55 AND `_is_pullback_to_sma50()` |
| 5 | `BUY_NOW_CONTINUATION` | score ≥ 70, not extended, all gates below pass |
| 6 | `BUY_STARTER_STRONG_BUT_EXTENDED` | score ≥ 70 AND (extended OR sma20 5–10% OR rsi > rsi_max) |
| 7 | `BUY_ON_PULLBACK` | score ≥ 70 AND `_is_pullback_to_sma50()` |
| 8 | `WAIT_FOR_PULLBACK` | score ≥ 70 (fallback from above) |
| 9 | `WAIT_FOR_PULLBACK` | score ≥ 55 AND rsi > 72 |
| 10 | `BUY_ON_PULLBACK` | score ≥ 55 AND `_is_pullback_to_sma50()` |
| 11 | `WAIT_FOR_PULLBACK` | score ≥ 55 |
| 12 | `WATCHLIST` | fallback |

#### `BUY_NOW_CONTINUATION` Gate Parameters

| Gate | Default | Effect |
|------|---------|--------|
| `score_min` | `70` | Minimum composite score |
| `not_extended` | required | `is_extended` must be False |
| `rsi` | `[rsi_min, rsi_max]` (regime-specific) | RSI in regime window |
| `sma20_relative` | `[0%, sma20_max%]` | Price mildly above SMA20 |
| `sma50_relative_max` | `12.0%` | Price not too far above SMA50 |
| `sma20_slope_min` | `0` | SMA20 slope non-negative |
| `sma50_slope_min` | `0` | SMA50 slope non-negative |
| `rsi_slope_min` | `0` | RSI slope non-negative |
| `rel_vol_min` | `1.3` (regime-specific) | Relative volume confirming |
| `rs_continuation_ok` | positive across all available RS fields | RS leader in narrow regime |
| `perf_1w` | `[0%, 6%]` | Not chasing, but not weak |
| `perf_1m` | `[3%, 15%]` | Healthy medium-term momentum |

#### `_is_pullback_to_sma50()` Gate Parameters

| Gate | Standard | HYPER_GROWTH override |
|------|----------|----------------------|
| `sma50_relative` | `[-3%, +5%]` | `[-5%, +8%]` |
| `sma20_relative_max` | `8.0%` | `8.0%` |
| `rsi` | `[40, 58]` | `[38, 62]` |
| `rsi_slope_min` | `-2.0` | `-2.0` |
| `perf_1m_min` | `-12.0%` | `-12.0%` |
| `perf_3m_min` | `> 0%` | `> 0%` |
| `volume_dryup_max` | `< 0.85` | `< 0.85` |
| `rs_vs_sector_20d_min` | `-3.0%` | `-3.0%` |
| `sma50_slope_min` | `>= 0` | `>= 0` |

#### Bad Chart Sub-Classification

| Label | Conditions |
|-------|-----------|
| `OVERSOLD_REBOUND_CANDIDATE` | RSI [25, 42] AND rsi_slope > 0 AND (perf_1w ≥ 0 OR green close) AND rel_vol ≥ 1.2 AND sma200_slope ≥ -0.5 |
| `BROKEN_SUPPORT_AVOID` | volume_dryup_ratio > 1.5 AND change_from_open < -1% AND RSI < 40 AND rsi_slope ≤ 0 |
| `TRUE_DOWNTREND_AVOID` | default |

#### RS Classification Gates

| Classification | Conditions |
|---------------|-----------|
| **RS Leader** | `rs_spy_20d ≥ 3%` AND `rs_spy_63d ≥ 5%` AND `rs_sector_20d ≥ 2%` |
| **RS Avoid** | `rs_spy_20d < -5%` OR `rs_spy_63d < -10%` OR `rs_sector_20d < -5%` |

#### 52-Week Position Buckets

| Bucket | Distance from 52W High |
|--------|----------------------|
| `near_52w_high` | `[0%, -3%)` |
| `healthy_pullback` | `[-3%, -10%)` |
| `extended_pullback` | `[-10%, -15%)` |
| `rebound_territory` | `[-15%, -35%)` |
| `avoid_zone` | `< -35%` |

### 13.3 Medium-Term v2 (`_decide_medium_term_v2`)

| Score | `is_extended` | Decision |
|-------|--------------|---------|
| ≥ 72 | False | `BUY_NOW` |
| ≥ 72 | True | `BUY_STARTER` |
| ≥ 60 | True | `BUY_ON_PULLBACK` |
| ≥ 60 | False | `BUY_STARTER` |
| ≥ 45 | — | `WATCHLIST_NEEDS_CONFIRMATION` |
| < 45 | — | `AVOID_BAD_BUSINESS` |

Override: business deteriorating AND score < 60 → `AVOID_BAD_BUSINESS`.

### 13.4 Long-Term v2 (`_decide_long_term_v2`)

| Condition | Decision |
|-----------|---------|
| Business deteriorating AND score < 60 | `AVOID_LONG_TERM` |
| `valuation_score < 35` AND score < 65 | `WATCHLIST_VALUATION_TOO_RICH` |
| score ≥ 72 | `BUY_NOW_LONG_TERM` |
| score ≥ 55 | `ACCUMULATE_ON_WEAKNESS` |
| score ≥ 40 | `WATCHLIST_VALUATION_TOO_RICH` |
| score < 40 | `AVOID_LONG_TERM` |

### 13.5 Confidence Thresholds

| Label | Score Range |
|-------|------------|
| `high` | ≥ 80 |
| `medium_high` | 65–79 |
| `medium` | 50–64 |
| `low` | < 50 |

---

## 14. Data Completeness & Confidence

**File**: `app/services/data_completeness_service.py`

| Data Gap | Score Deduction |
|---------|----------------|
| No recent news | `−15` |
| No next earnings date | `−10` |
| No peer comparison | `−5` |
| No options data | `−15` |
| Insufficient price history | `−5` |

| Parameter | Default | Effect |
|-----------|---------|--------|
| `AVOID_LOW_CONFIDENCE_THRESHOLD` | `55.0` | Completeness below this → force `AVOID_LOW_CONFIDENCE` decision |
| `_CONFIDENCE_CAP_THRESHOLD` | `60.0` | Completeness below this → cap confidence_score at 60 |
| `_CONFIDENCE_CAP_VALUE` | `60.0` | Capped confidence value |

Minimum achievable completeness: **50** (all 5 deductions hit). `AVOID_LOW_CONFIDENCE` fires when 3+ major categories are missing.

---

## 15. Risk Management (Entry / Exit / Sizing)

**File**: `app/services/risk_management_service.py`

### 15.1 ATR Stop-Loss Multipliers

| Horizon | ATR Multiplier | Formula |
|---------|---------------|---------|
| `short_term` | `1.5` | `stop = entry − 1.5 × ATR` |
| `medium_term` | `2.0` | `stop = entry − 2.0 × ATR` |
| `long_term` | `2.5` | `stop = entry − 2.5 × ATR` |

Invalidation level: `stop − 0.5 × ATR`

Fallback (no ATR):
- If support exists: `stop = nearest_support × 0.99`, `invalidation = nearest_support × 0.98`
- Else: `stop = price × 0.92`, `invalidation = price × 0.90`

### 15.2 ATR Position Size Adjustments

| ATR% | Size Multiplier |
|------|----------------|
| < 4.0% | 1.00 (full size) |
| 4.0–7.0% | 0.55 (starter only) |
| > 7.0% | 0.30 (speculative/small) |

### 15.3 Position Sizing by Risk Profile

| Profile | `starter_pct` | `max_allocation` |
|---------|--------------|-----------------|
| `conservative` | 15% | 3.0% of portfolio |
| `moderate` | 25% | 5.0% of portfolio |
| `aggressive` | 40% | 8.0% of portfolio |

### 15.4 Pre-Earnings Reduction

Applied when `within_30_days_earnings = True`:

| Parameter | Adjustment |
|-----------|-----------|
| `starter_pct` | `× 0.50` |
| `max_allocation` | `× 0.70` |

### 15.5 Entry Plans by Decision

| Decision | `preferred_entry` | `starter_entry` | `avoid_above` |
|----------|-------------------|-----------------|--------------|
| `BUY_NOW` | `price` | `price × 1.005` | `price × 1.08` |
| `BUY_STARTER` | `price` | `price × 1.01` | `price × 1.06` |
| `WAIT_FOR_PULLBACK` | `nearest_support` or `price × 0.95` | `price × 0.98` | `price × 1.05` |
| `BUY_ON_BREAKOUT` | `nearest_resistance` or `price × 1.03` | `price × 1.01` | `breakout × 1.03` |
| `WATCHLIST` / `AVOID` | `nearest_support` or `price × 0.90` | `None` | `None` |

### 15.6 Target Prices

| Target | Rule |
|--------|------|
| `first_target` | First resistance level, else `price × 1.10` |
| `second_target` | Second resistance level, else `price × 1.20` |

---

## 16. Valuation Score — Archetype-Adjusted

**File**: `app/services/valuation_analysis_service.py` → `score_valuation_with_archetype()`

Base: `50.0` for all archetypes.

### 16.1 HYPER_GROWTH / SPECULATIVE_STORY

| Component | Rules |
|-----------|-------|
| Rule of 40 (rev_growth% + op_margin%) | ≥60: +15; ≥40: +8; ≥20: 0; else: -10 |
| PEG (primary signal) | ≤1.0: +15; ≤1.5: +8; ≤2.5: 0; ≤4.0: -8; else: -15 |
| Forward P/E (only if no PEG) | ≤30: +10; ≤50: 0; ≤80: -5; else: -10 |
| P/S | ≤10: +5; ≤20: 0; ≤40 (high-GM): 0; ≤40: -5; else: -10 |
| FCF yield | ≥3%: +10; ≥1%: +5; <0: -5 |

### 16.2 MATURE_VALUE

| Component | Rules |
|-----------|-------|
| Forward P/E | ≤12: +20; ≤18: +12; ≤25: 0; ≤35: -12; else: -20 |
| FCF yield | ≥6%: +15; ≥3%: +8; ≥1%: +3; <0: -15 |
| PEG | ≤1.0: +10; ≤1.5: +5; >2.5: -10 |
| P/S | ≤2: +8; ≤5: +3; >10: -8 |
| EV/EBITDA | ≤10: +10; ≤15: +5; >25: -10 |

### 16.3 CYCLICAL_GROWTH

| Component | Rules |
|-----------|-------|
| EV/EBITDA | ≤8: +5 (careful, may be peak); ≤15: +10; ≤25: 0; ≤40: -8; else: -15 |
| FCF yield | ≥5%: +10; ≥2%: +5; <0: -10 |
| Forward P/E | ≤10: +3 (soft reward); ≤20: +8; ≤30: 0; ≤40: -8; else: -15 |

### 16.4 DEFENSIVE / COMMODITY_CYCLICAL

| Component | Rules |
|-----------|-------|
| Forward P/E | ≤15: +15; ≤20: +8; ≤30: 0; ≤40: -10; else: -18 |
| FCF yield | ≥5%: +12; ≥2%: +6; <0: -12 |
| P/S | ≤2: +8; ≤5: +3; >10: -5 |

### 16.5 PROFITABLE_GROWTH / TURNAROUND

Uses `score_valuation()` (standard, archetype-neutral):

| Component | Rules |
|-----------|-------|
| Forward P/E | ≤15: +20; ≤20: +10; ≤30: 0; ≤40: -10; else: -20 |
| PEG | ≤1.0: +15; ≤1.5: +8; ≤2.0: 0; ≤3.0: -10; else: -15 |
| P/S | ≤2: +10; ≤5: +5; ≤10: 0; ≤20: -5; else: -10 |
| EV/EBITDA | ≤10: +10; ≤15: +5; ≤25: 0; ≤40: -5; else: -10 |
| FCF yield | ≥5%: +10; ≥2%: +5; <0: -10 |
| Trailing P/E | ≤20: +5; >60: -5 |

---

## 17. Experiment Log Template

Use this block for each parameter experiment. Store completed experiments as separate files or append below.

```markdown
### Experiment: [EXP-001] [Short name]

**Date**: YYYY-MM-DD
**Branch / commit**:
**Hypothesis**: What do you expect to improve and why?

**Parameters Changed**:
| File | Parameter | Old Value | New Value |
|------|-----------|-----------|-----------|
| `scoring_service.py` | `SIGNAL_CARD_SHORT_WEIGHTS["momentum"]` | 25 | 30 |
| `scoring_service.py` | `SIGNAL_CARD_SHORT_WEIGHTS["volume_accumulation"]` | 20 | 15 |

**Backtest Config**:
- Tickers:
- Date range:
- Horizons:

**Results**:
| Metric | Baseline | Experiment | Delta |
|--------|---------|------------|-------|
| Win rate | | | |
| Avg return (winners) | | | |
| Avg return (losers) | | | |
| Max drawdown | | | |
| Sharpe (if computed) | | | |

**Outcome**: ✅ Keep / ❌ Revert / 🔄 Iterate

**Notes**: What did you learn? What to try next?
```

---

## Quick-Reference: Key Thresholds

| Concept | Parameter | Value | File |
|---------|-----------|-------|------|
| Extension above SMA20 | `ext_above_20ma_threshold` | 8% | `technical_analysis_service.py` |
| Extension above SMA50 | `ext_above_50ma_threshold` | 15% | `technical_analysis_service.py` |
| RSI overbought (extension) | `ext_rsi_overbought` | 75 | `technical_analysis_service.py` |
| RSI continuation zone (bull) | `rsi_min/rsi_max` | 55–68 | `recommendation_service.py` |
| SMA20 max for continuation | `sma20_max` | 5% | `recommendation_service.py` |
| Relative volume min | `rel_vol_min` | 1.3 | `recommendation_service.py` |
| Chasing perf_1w | hardcoded | > 10% | `recommendation_service.py` |
| Chasing perf_1m | hardcoded | > 25% | `recommendation_service.py` |
| SMA50 pullback zone | `sma50_relative` | −3% to +5% | `recommendation_service.py` |
| Data completeness floor | `AVOID_LOW_CONFIDENCE_THRESHOLD` | 55 | `data_completeness_service.py` |
| Bear VIX threshold | `vix_bear_threshold` | 25 | `market_regime_service.py` |
| ATR stop short-term | `atr_multiplier_short` | 1.5× | `risk_management_service.py` |
| Moderate position size | `max_allocation` | 5% | `risk_management_service.py` |
| Pre-earnings size cut | `earnings_starter_cut` | 50% | `risk_management_service.py` |
| High ATR (starter-only) | `atr_high_threshold` | 4% | `risk_management_service.py` |
