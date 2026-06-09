# Algorithm Parameter Values — Current Exact Defaults

> All values extracted directly from source code. Organized by file.
> For parameter meaning and effect, see `ALGO_PARAMS.md`.

---

## `technical_analysis_service.py`

### Moving Averages & EMA

| Parameter | Value |
|-----------|-------|
| SMA periods computed | 10, 20, 50, 100, 200 |
| EMA periods computed | 8, 21 |
| SMA slope window (`slope_bars`) | 5 bars |

### Momentum Indicators

| Parameter | Value |
|-----------|-------|
| RSI period | 14 |
| RSI slope window | 5 bars |
| MACD fast EMA | 12 |
| MACD slow EMA | 26 |
| MACD signal EMA | 9 |
| ADX period | 14 |
| StochRSI period | 14 |
| StochRSI smooth_k | 3 |
| StochRSI smooth_d | 3 |

### Volatility

| Parameter | Value |
|-----------|-------|
| ATR period | 14 |
| Bollinger Band SMA period | 20 |
| Bollinger Band std deviation | 2.0 |
| Weekly vol min bars required | 10 |
| Monthly vol min bars required | 24 |

### Volume / Accumulation

| Parameter | Value |
|-----------|-------|
| OBV slope bars | 10 |
| A/D line slope bars | 10 |
| Chaikin Money Flow period | 20 |
| VWAP rolling period | 20 |
| Volume dry-up recent bars | 3 |
| Volume dry-up reference bars | 10 |
| Breakout volume reference period | 20 |
| Up/down volume ratio period | 20 |

### Relative Strength

| Parameter | Value |
|-----------|-------|
| RS vs SPY legacy period | 63 bars |
| RS short window (20d) | 20 bars |
| RS medium window (63d) | 63 bars |

### Percentile Ranks & Drawdown

| Parameter | Value |
|-----------|-------|
| Percentile rank lookback | 252 bars |
| Return bars ranked | 20, 63, 126, 252 |
| Drawdown 3M bars | 63 |
| Drawdown 1Y bars | 252 |

### Gap Fill

| Parameter | Value |
|-----------|-------|
| Minimum gap % to qualify | 2.0% |
| Backward scan bars | 30 |

### Performance Period Bar Counts

| Period | Bars |
|--------|------|
| 1W | 5 |
| 1M | 21 |
| 3M | 63 |
| 6M | 126 |
| 1Y | 252 |
| 3Y | 756 |
| 5Y | 1260 |

### Support / Resistance

| Parameter | Value |
|-----------|-------|
| Lookback bars for swing highs/lows | 60 |
| Number of levels returned (`n_levels`) | 3 |
| Cluster merge tolerance | 1% (0.01) |

### Volume Trend Classification

| Parameter | Value |
|-----------|-------|
| Reference bars | 30 |
| above_average threshold | ≥ 1.3× avg |
| below_average threshold | ≤ 0.7× avg |

### `score_technicals` — Base & Contributions

| Component | Condition | Points |
|-----------|-----------|--------|
| Base | always | 50.0 |
| Trend | `strong_uptrend` | +20 |
| Trend | `weak_uptrend` | +5 |
| Trend | `sideways` | −5 |
| Trend | `downtrend` | −20 |
| Trend | `unknown` | 0 |
| RSI | 50 ≤ RSI ≤ 70 | +15 |
| RSI | 40 ≤ RSI < 50 | +5 |
| RSI | RSI > 75 | −5 |
| RSI | RSI < 30 | −15 |
| MACD histogram | > 0 | +10 |
| MACD histogram | ≤ 0 | −10 |
| Extension | `is_extended = True` | −10 |
| Volume | `above_average` | +5 |
| Volume | `below_average` | −5 |
| RS vs SPY | > 1.2 | +10 |
| RS vs SPY | 1.0 < rs ≤ 1.2 | +5 |
| RS vs SPY | < 0.8 | −10 |
| RS vs SPY | 0.8 ≤ rs < 1.0 | −5 |
| Support cushion | ≤ 5% from price | +5 |
| Support cushion | > 15% from price | −5 |

### `detect_extension` Thresholds

| Parameter | Value |
|-----------|-------|
| Extension above SMA20 | > 8.0% |
| Extension above SMA50 | > 15.0% |
| RSI overbought (extension) | > 75.0 |

---

## `stock_archetype_service.py`

### Archetype Priority Rules & Confidence

| Priority | Archetype | Trigger | Confidence |
|----------|-----------|---------|-----------|
| 1 | `SPECULATIVE_STORY` | P/S > 20 AND eps < 0 AND rev_yoy > 0.20 | 80.0 |
| 1 | `SPECULATIVE_STORY` | P/S > 40 (alone) | 70.0 |
| 2 | `HYPER_GROWTH` | rev_yoy > 0.30 | 70 + (rev_yoy − 0.30) × 100, cap 95 |
| 2 | `HYPER_GROWTH` | rev_yoy > 0.20 AND fpe > 40 | 72.0 |
| 3 | `DEFENSIVE` | sector ∈ defensive AND beta < 0.8 | 80.0 |
| 3 | `DEFENSIVE` | sector ∈ defensive (any beta) | 65.0 |
| 4 | `COMMODITY_CYCLICAL` | sector ∈ commodity | 78.0 |
| 5 | `CYCLICAL_GROWTH` | beta > 1.3 AND sector ∈ cyclical | 72.0 |
| 6 | `PROFITABLE_GROWTH` | rev_yoy > 0.15 AND (op_margin > 0 OR fcf > 0) | 65 + (rev_yoy − 0.15) × 100, cap 85 |
| 7 | `TURNAROUND` | slow growth AND (eps_growth_yoy > 0.10 OR rev_qoq > 0.05) AND eps > 0 | 60.0 |
| 8 | `MATURE_VALUE` | rev_yoy < 0.10 AND (fcf > 0 OR eps > 0) | 68.0 |
| fallback | `PROFITABLE_GROWTH` | none matched | 40.0 |

### Sector Sets

| Set | Members |
|-----|---------|
| `DEFENSIVE_SECTORS` | Healthcare, Consumer Defensive, Utilities |
| `COMMODITY_SECTORS` | Energy, Basic Materials |
| `CYCLICAL_SECTORS` | Energy, Basic Materials, Industrials, Consumer Cyclical |

---

## `market_regime_service.py`

### `classify_regime` — Minimum Data

| Parameter | Value |
|-----------|-------|
| SPY min bars to classify | 50 |
| Default when insufficient | `SIDEWAYS_CHOPPY`, confidence 20 |

### `_determine_regime` — Decision Table

| Condition | Regime | Confidence |
|-----------|--------|-----------|
| SPY below 200DMA, VIX > 25 | `BEAR_RISK_OFF` | 82.0 |
| SPY below 200DMA, QQQ below 200DMA, VIX > 20 | `BEAR_RISK_OFF` | 70.0 |
| SPY below 200DMA, QQQ above 200DMA | `SIDEWAYS_CHOPPY` | 55.0 |
| SPY above 50DMA + 200DMA, QQQ above 200DMA, VIX < 20 | `BULL_RISK_ON` | 85.0 |
| SPY above 50DMA + 200DMA, QQQ below 200DMA, VIX < 20 | `BULL_NARROW_LEADERSHIP` | 68.0 |
| SPY above 50DMA + 200DMA, VIX 20–25 | `LIQUIDITY_RALLY` | 62.0 |
| SPY above 50DMA + 200DMA, QQQ above 200DMA, no VIX | `BULL_RISK_ON` | 70.0 |
| SPY above 50DMA + 200DMA, QQQ below 200DMA, no VIX | `BULL_NARROW_LEADERSHIP` | 58.0 |
| SPY above 200DMA, below 50DMA | `SIDEWAYS_CHOPPY` | 60.0 |
| SPY above 200DMA, no VIX info | `SIDEWAYS_CHOPPY` | 40.0 |
| VIX 20–30, SPY above 200DMA | `LIQUIDITY_RALLY` | 55.0 |
| Fallback | `SIDEWAYS_CHOPPY` | 45.0 |

### `REGIME_WEIGHT_ADJUSTMENTS` — Score Multipliers

| Regime | Factor | Multiplier |
|--------|--------|-----------|
| `BULL_RISK_ON` | `technical_momentum` | 1.20 |
| `BULL_RISK_ON` | `relative_strength` | 1.15 |
| `BULL_RISK_ON` | `growth_acceleration` | 1.15 |
| `BULL_RISK_ON` | `valuation_relative_growth` | 0.70 |
| `BULL_RISK_ON` | `fcf_quality` | 0.90 |
| `BEAR_RISK_OFF` | `valuation_relative_growth` | 1.30 |
| `BEAR_RISK_OFF` | `balance_sheet_strength` | 1.25 |
| `BEAR_RISK_OFF` | `fcf_quality` | 1.20 |
| `BEAR_RISK_OFF` | `technical_momentum` | 0.90 |
| `BEAR_RISK_OFF` | `catalyst_news` | 0.90 |
| `SIDEWAYS_CHOPPY` | `risk_reward` | 1.25 |
| `SIDEWAYS_CHOPPY` | `relative_strength` | 1.10 |
| `SIDEWAYS_CHOPPY` | `technical_momentum` | 0.85 |
| `BULL_NARROW_LEADERSHIP` | `technical_momentum` | 1.15 |
| `BULL_NARROW_LEADERSHIP` | `relative_strength` | 1.20 |
| `BULL_NARROW_LEADERSHIP` | `sector_strength` | 1.15 |
| `LIQUIDITY_RALLY` | `technical_momentum` | 1.10 |
| `LIQUIDITY_RALLY` | `catalyst_news` | 1.10 |
| `LIQUIDITY_RALLY` | `valuation_relative_growth` | 0.80 |
| `SECTOR_ROTATION` | `sector_strength` | 1.30 |
| `SECTOR_ROTATION` | `relative_strength` | 1.15 |

---

## `scoring_service.py`

### Legacy Horizon Weights (`SHORT_TERM_WEIGHTS`)

| Factor | Weight |
|--------|--------|
| `technical_momentum` | 30 |
| `relative_strength` | 20 |
| `catalyst_news` | 20 |
| `options_flow` | 10 |
| `market_regime` | 10 |
| `risk_reward` | 10 |

### Legacy Horizon Weights (`MEDIUM_TERM_WEIGHTS`)

| Factor | Weight |
|--------|--------|
| `earnings_revision` | 25 |
| `growth_acceleration` | 20 |
| `technical_trend` | 20 |
| `sector_strength` | 15 |
| `valuation_relative_growth` | 10 |
| `catalyst_news` | 10 |

### Legacy Horizon Weights (`LONG_TERM_WEIGHTS`)

| Factor | Weight |
|--------|--------|
| `business_quality` | 25 |
| `growth_durability` | 20 |
| `fcf_quality` | 15 |
| `balance_sheet_strength` | 15 |
| `valuation_relative_growth` | 15 |
| `competitive_moat` | 10 |

### Signal Card Weights — Short-Term (`SIGNAL_CARD_SHORT_WEIGHTS`)

| Card | Weight |
|------|--------|
| `momentum` | 25 |
| `volume_accumulation` | 20 |
| `entry_timing` | 20 |
| `relative_strength` | 15 |
| `volatility_risk` | 10 |
| `catalyst` | 10 |

### Signal Card Weights — Medium-Term (`SIGNAL_CARD_MEDIUM_WEIGHTS`)

| Card | Weight |
|------|--------|
| `trend` | 20 |
| `growth` | 20 |
| `relative_strength` | 15 |
| `volume_accumulation` | 15 |
| `valuation` | 10 |
| `quality` | 10 |
| `catalyst` | 10 |

### Signal Card Weights — Long-Term (`SIGNAL_CARD_LONG_WEIGHTS`)

| Card | Weight |
|------|--------|
| `quality` | 35 |
| `growth` | 20 |
| `valuation` | 15 |
| `trend` | 10 |
| `catalyst` | 10 |
| `ownership` | 5 |
| `volatility_risk` | 5 |

### Regime Composite Adjustments (Signal Card Path)

| Regime | Short-Term Multiplier | Medium-Term Multiplier |
|--------|----------------------|----------------------|
| `BULL_RISK_ON` | `× (1 + conf/100 × 0.10)` | `× (1 + conf/100 × 0.05)` |
| `BEAR_RISK_OFF` | `× (1 − conf/100 × 0.10)` | `× (1 − conf/100 × 0.05)` |
| All others | no change | no change |

### `_regime_score` — Regime → Score Mapping

| Regime | Formula | Effective Range |
|--------|---------|----------------|
| `BULL_RISK_ON` | `50 + confidence × 0.35` | 50.0 – 85.0 |
| `BEAR_RISK_OFF` | `50 − confidence × 0.35` | 15.0 – 50.0 |
| `BULL_NARROW_LEADERSHIP` | `50 + confidence × 0.15` | 50.0 – 65.0 |
| `LIQUIDITY_RALLY` | `50 + confidence × 0.15` | 50.0 – 65.0 |
| `SIDEWAYS_CHOPPY` | `50.0` | 50.0 |
| `None` / other | `50.0` | 50.0 |

---

## `recommendation_service.py`

### Per-Regime Entry Thresholds (`RegimeThresholds`)

| Regime | `rsi_min` | `rsi_max` | `sma20_max %` | `rel_vol_min` |
|--------|----------|----------|--------------|--------------|
| `LIQUIDITY_RALLY` | 55.0 | 74.0 | 8.0 | 1.2 |
| `BULL_RISK_ON` | 55.0 | 68.0 | 5.0 | 1.3 |
| `SIDEWAYS_CHOPPY` | 40.0 | 58.0 | 3.0 | 1.3 |
| `BEAR_RISK_OFF` | 999.0 | −999.0 | 0.0 | 999.0 |
| `BULL_NARROW_LEADERSHIP` | 55.0 | 68.0 | 5.0 | 1.3 |
| Default | 55.0 | 68.0 | 5.0 | 1.3 |

### `BUY_NOW_CONTINUATION` Gate Values

| Gate | Value |
|------|-------|
| Minimum composite score | 70 |
| `is_extended` | must be False |
| RSI range | `[rsi_min, rsi_max]` (regime-specific) |
| SMA20 relative range | `[0.0%, sma20_max%]` (regime-specific) |
| SMA50 relative max | 12.0% |
| SMA20 slope min | 0 (non-negative) |
| SMA50 slope min | 0 (non-negative) |
| RSI slope min | 0 (non-negative) |
| Relative volume min | `rel_vol_min` (regime-specific) |
| `perf_1w` range | 0.0% to 6.0% |
| `perf_1m` range | 3.0% to 15.0% |
| BULL_NARROW: RS requirement | `_rs_leader()` (spy20 ≥ 3, spy63 ≥ 5, sector20 ≥ 2) |
| Others: RS requirement | all available RS fields > 0 |

### `_is_pullback_to_sma50` Gate Values

| Gate | Standard | HYPER_GROWTH Override |
|------|----------|-----------------------|
| `sma50_relative` min | −3.0% | −5.0% |
| `sma50_relative` max | 5.0% | 8.0% |
| `sma20_relative` max | 8.0% | 8.0% |
| RSI min | 40.0 | 38.0 |
| RSI max | 58.0 | 62.0 |
| RSI slope min | −2.0 | −2.0 |
| `perf_1m` min | −12.0% | −12.0% |
| `perf_3m` min | > 0% | > 0% |
| `volume_dryup_ratio` max | < 0.85 | < 0.85 |
| `rs_vs_sector_20d` min | −3.0% | −3.0% |
| SMA50 slope min | ≥ 0 | ≥ 0 |

### `_classify_bad_chart` Sub-Label Thresholds

| Label | Conditions (all must be met) |
|-------|------------------------------|
| `OVERSOLD_REBOUND_CANDIDATE` | RSI ∈ [25.0, 42.0] AND rsi_slope > 0 AND (perf_1w ≥ 0 OR change_from_open > 0) AND breakout_vol_multiple ≥ 1.2 AND sma200_slope ≥ −0.5 |
| `BROKEN_SUPPORT_AVOID` | volume_dryup_ratio > 1.5 AND change_from_open < −1.0% AND RSI < 40.0 AND (rsi_slope ≤ 0 OR rsi_slope is None) |
| `TRUE_DOWNTREND_AVOID` | default (none of above) |

### Shared Override Gates

| Gate | Trigger |
|------|---------|
| `_chart_is_weak` | `trend = downtrend` AND `rs_vs_spy < 0.8` |
| `_business_deteriorating` | `rev_growth_yoy < 0` AND (`op_margin < −0.05` OR `beat_rate < 0.40`) |

### `WAIT_FOR_PULLBACK` Short-Circuit Conditions

| Condition | Value |
|-----------|-------|
| Chasing: `perf_1w` | > 10.0% |
| Chasing: `perf_1m` | > 25.0% |
| SMA20 extended: `sma20_relative` | > 10.0% |
| RSI too hot (used in score 55–70 zone) | > 72.0 |

### RS Threshold Gates

| Gate | Threshold |
|------|----------|
| RS leader: `rs_vs_spy_20d` | ≥ 3.0% |
| RS leader: `rs_vs_spy_63d` | ≥ 5.0% |
| RS leader: `rs_vs_sector_20d` | ≥ 2.0% |
| RS avoid: `rs_vs_spy_20d` | < −5.0% |
| RS avoid: `rs_vs_spy_63d` | < −10.0% |
| RS avoid: `rs_vs_sector_20d` | < −5.0% |

### 52-Week High Distance Buckets

| Bucket | `dist_from_52w_high` Range |
|--------|--------------------------|
| `near_52w_high` | ≥ −3.0% |
| `healthy_pullback` | −3.0% to −10.0% |
| `extended_pullback` | −10.0% to −15.0% |
| `rebound_territory` | −15.0% to −35.0% |
| `avoid_zone` | < −35.0% |

### Medium-Term v2 Decision Table (`_decide_medium_term_v2`)

| Score | `is_extended` | Decision |
|-------|--------------|---------|
| ≥ 72 | False | `BUY_NOW` |
| ≥ 72 | True | `BUY_STARTER` |
| ≥ 60 | True | `BUY_ON_PULLBACK` |
| ≥ 60 | False | `BUY_STARTER` |
| ≥ 45 | — | `WATCHLIST_NEEDS_CONFIRMATION` |
| < 45 | — | `AVOID_BAD_BUSINESS` |
| Business deteriorating AND score < 60 | — | `AVOID_BAD_BUSINESS` (override) |

### Long-Term v2 Decision Table (`_decide_long_term_v2`)

| Condition | Decision |
|-----------|---------|
| Business deteriorating AND score < 60 | `AVOID_LONG_TERM` |
| `valuation_score < 35` AND `score < 65` | `WATCHLIST_VALUATION_TOO_RICH` |
| score ≥ 72 | `BUY_NOW_LONG_TERM` |
| score ≥ 55 | `ACCUMULATE_ON_WEAKNESS` |
| score ≥ 40 | `WATCHLIST_VALUATION_TOO_RICH` |
| score < 40 | `AVOID_LONG_TERM` |

### Confidence Label Thresholds

| Label | Score |
|-------|-------|
| `high` | ≥ 80 |
| `medium_high` | ≥ 65 |
| `medium` | ≥ 50 |
| `low` | < 50 |

---

## `data_completeness_service.py`

### Data Gap Deductions

| Missing Data Category | Deduction |
|----------------------|----------|
| No news | −15 |
| No next earnings date | −10 |
| No peer comparison | −5 |
| No options data | −15 |
| Insufficient price history | −5 |
| **Minimum achievable score** | **50** |

### Completeness Thresholds

| Parameter | Value |
|-----------|-------|
| `AVOID_LOW_CONFIDENCE_THRESHOLD` | 55.0 |
| `_CONFIDENCE_CAP_THRESHOLD` | 60.0 |
| `_CONFIDENCE_CAP_VALUE` | 60.0 |

---

## `risk_management_service.py`

### Position Sizing by Risk Profile

| Profile | `starter_pct` | `max_allocation` |
|---------|--------------|-----------------|
| `conservative` | 15% | 3.0% |
| `moderate` | 25% | 5.0% |
| `aggressive` | 40% | 8.0% |

### Pre-Earnings Size Reduction

| Parameter | Multiplier |
|-----------|-----------|
| `starter_pct` | × 0.50 |
| `max_allocation` | × 0.70 |

### ATR Position Size Multiplier (`_atr_size_multiplier`)

| ATR% Range | Size Multiplier |
|-----------|----------------|
| < 4.0% | 1.00 |
| 4.0% – 7.0% | 0.55 |
| > 7.0% | 0.30 |

### ATR Stop-Loss Multipliers (`_compute_stop_atr`)

| Horizon | ATR Multiplier | Stop Formula |
|---------|---------------|-------------|
| `short_term` | 1.5 | `entry − 1.5 × ATR` |
| `medium_term` | 2.0 | `entry − 2.0 × ATR` |
| `long_term` | 2.5 | `entry − 2.5 × ATR` |
| `invalidation` (all) | +0.5 | `stop − 0.5 × ATR` |

### Fallback Stop / Invalidation (No ATR)

| Condition | Stop | Invalidation |
|-----------|------|-------------|
| Support available | `nearest_support × 0.99` | `nearest_support × 0.98` |
| No support | `price × 0.92` | `price × 0.90` |

### Entry Plan Price Levels

| Decision | `preferred_entry` | `starter_entry` | `avoid_above` |
|----------|------------------|-----------------|--------------|
| `BUY_NOW` | `price` | `price × 1.005` | `price × 1.08` |
| `BUY_STARTER` | `price` | `price × 1.01` | `price × 1.06` |
| `WAIT_FOR_PULLBACK` | `nearest_support` or `price × 0.95` | `price × 0.98` | `price × 1.05` |
| `BUY_ON_BREAKOUT` | `nearest_resistance` or `price × 1.03` | `price × 1.01` | `breakout × 1.03` |
| `WATCHLIST` / `AVOID` | `nearest_support` or `price × 0.90` | `None` | `None` |

### Target Prices

| Target | Rule |
|--------|------|
| `first_target` | `resistances[0]` or `price × 1.10` |
| `second_target` | `resistances[1]` or `price × 1.20` |

---

## `valuation_analysis_service.py`

### Standard Score (`score_valuation`) — Base 50.0

| Metric | Threshold | Points |
|--------|-----------|--------|
| `forward_pe` | ≤ 15 | +20 |
| `forward_pe` | ≤ 20 | +10 |
| `forward_pe` | ≤ 30 | 0 |
| `forward_pe` | ≤ 40 | −10 |
| `forward_pe` | > 40 | −20 |
| `peg_ratio` | ≤ 1.0 | +15 |
| `peg_ratio` | ≤ 1.5 | +8 |
| `peg_ratio` | ≤ 2.0 | 0 |
| `peg_ratio` | ≤ 3.0 | −10 |
| `peg_ratio` | > 3.0 | −15 |
| `price_to_sales` | ≤ 2 | +10 |
| `price_to_sales` | ≤ 5 | +5 |
| `price_to_sales` | ≤ 10 | 0 |
| `price_to_sales` | ≤ 20 | −5 |
| `price_to_sales` | > 20 | −10 |
| `ev_to_ebitda` | ≤ 10 | +10 |
| `ev_to_ebitda` | ≤ 15 | +5 |
| `ev_to_ebitda` | ≤ 25 | 0 |
| `ev_to_ebitda` | ≤ 40 | −5 |
| `ev_to_ebitda` | > 40 | −10 |
| `fcf_yield` | ≥ 5% | +10 |
| `fcf_yield` | ≥ 2% | +5 |
| `fcf_yield` | < 0% | −10 |
| `trailing_pe` | ≤ 20 | +5 |
| `trailing_pe` | > 60 | −5 |

### Archetype-Adjusted: `HYPER_GROWTH` / `SPECULATIVE_STORY` — Base 50.0

| Metric | Threshold | Points |
|--------|-----------|--------|
| Rule of 40 (rev% + op_margin%) | ≥ 60 | +15 |
| Rule of 40 | ≥ 40 | +8 |
| Rule of 40 | ≥ 20 | 0 |
| Rule of 40 | < 20 | −10 |
| `peg_ratio` | ≤ 1.0 | +15 |
| `peg_ratio` | ≤ 1.5 | +8 |
| `peg_ratio` | ≤ 2.5 | 0 |
| `peg_ratio` | ≤ 4.0 | −8 |
| `peg_ratio` | > 4.0 | −15 |
| `forward_pe` (only if no PEG) | ≤ 30 | +10 |
| `forward_pe` (only if no PEG) | ≤ 50 | 0 |
| `forward_pe` (only if no PEG) | ≤ 80 | −5 |
| `forward_pe` (only if no PEG) | > 80 | −10 |
| `price_to_sales` | ≤ 10 | +5 |
| `price_to_sales` | ≤ 20 | 0 |
| `price_to_sales` | ≤ 40 AND gross_margin > 0.60 | 0 |
| `price_to_sales` | ≤ 40 (low margin) | −5 |
| `price_to_sales` | > 40 | −10 |
| `fcf_yield` | ≥ 3% | +10 |
| `fcf_yield` | ≥ 1% | +5 |
| `fcf_yield` | < 0% | −5 |

### Archetype-Adjusted: `MATURE_VALUE` — Base 50.0

| Metric | Threshold | Points |
|--------|-----------|--------|
| `forward_pe` | ≤ 12 | +20 |
| `forward_pe` | ≤ 18 | +12 |
| `forward_pe` | ≤ 25 | 0 |
| `forward_pe` | ≤ 35 | −12 |
| `forward_pe` | > 35 | −20 |
| `fcf_yield` | ≥ 6% | +15 |
| `fcf_yield` | ≥ 3% | +8 |
| `fcf_yield` | ≥ 1% | +3 |
| `fcf_yield` | < 0% | −15 |
| `peg_ratio` | ≤ 1.0 | +10 |
| `peg_ratio` | ≤ 1.5 | +5 |
| `peg_ratio` | > 2.5 | −10 |
| `price_to_sales` | ≤ 2 | +8 |
| `price_to_sales` | ≤ 5 | +3 |
| `price_to_sales` | > 10 | −8 |
| `ev_to_ebitda` | ≤ 10 | +10 |
| `ev_to_ebitda` | ≤ 15 | +5 |
| `ev_to_ebitda` | > 25 | −10 |

### Archetype-Adjusted: `CYCLICAL_GROWTH` — Base 50.0

| Metric | Threshold | Points |
|--------|-----------|--------|
| `ev_to_ebitda` | ≤ 8 | +5 |
| `ev_to_ebitda` | ≤ 15 | +10 |
| `ev_to_ebitda` | ≤ 25 | 0 |
| `ev_to_ebitda` | ≤ 40 | −8 |
| `ev_to_ebitda` | > 40 | −15 |
| `fcf_yield` | ≥ 5% | +10 |
| `fcf_yield` | ≥ 2% | +5 |
| `fcf_yield` | < 0% | −10 |
| `forward_pe` | ≤ 10 | +3 |
| `forward_pe` | ≤ 20 | +8 |
| `forward_pe` | ≤ 30 | 0 |
| `forward_pe` | ≤ 40 | −8 |
| `forward_pe` | > 40 | −15 |

### Archetype-Adjusted: `DEFENSIVE` / `COMMODITY_CYCLICAL` — Base 50.0

| Metric | Threshold | Points |
|--------|-----------|--------|
| `forward_pe` | ≤ 15 | +15 |
| `forward_pe` | ≤ 20 | +8 |
| `forward_pe` | ≤ 30 | 0 |
| `forward_pe` | ≤ 40 | −10 |
| `forward_pe` | > 40 | −18 |
| `fcf_yield` | ≥ 5% | +12 |
| `fcf_yield` | ≥ 2% | +6 |
| `fcf_yield` | < 0% | −12 |
| `price_to_sales` | ≤ 2 | +8 |
| `price_to_sales` | ≤ 5 | +3 |
| `price_to_sales` | > 10 | −5 |

---

## `signal_card_service.py`

### Momentum Card — Point Table

| Metric | Condition | Points (of weight) |
|--------|-----------|-------------------|
| `perf_1w` (weight 10) | > 0% | `min(10, 10 × (1 + val/20))` |
| `perf_1w` | ≤ 0% | 0 |
| `perf_1m` (weight 15) | > 0% | `min(15, 15 × (1 + val/20))` |
| `perf_1m` | ≤ 0% | 0 |
| `perf_3m` (weight 20) | > 0% | `min(20, 20 × (1 + val/20))` |
| `perf_3m` | ≤ 0% | 0 |
| `macd_histogram` (weight 15) | > 0 | `min(15, 7.5 + hist × 5)` |
| `macd_histogram` | ≤ 0 | 0 |
| `rsi_14` (weight 15) | 45–65 | 15 |
| `rsi_14` | 65–75 | 9 |
| `rsi_14` | > 75 | 4 |
| `rsi_14` | 35–45 | 6 |
| `rsi_14` | < 35 | 0 |
| `rsi_slope` (weight 10) | ≥ 5 | 10 |
| `rsi_slope` | ≥ 1 | 7 |
| `rsi_slope` | ≥ −1 | 5 |
| `rsi_slope` | ≥ −5 | 2 |
| `rsi_slope` | < −5 | 0 |
| `ema8_relative` (weight 10) | > 0 | 10 |
| `ema8_relative` | ≤ 0 | 0 |
| `ema21_relative` (weight 10) | > 0 | 10 |
| `ema21_relative` | ≤ 0 | 0 |

### Trend Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `sma20_relative` (weight 15) | > 0 | 15 |
| `sma20_relative` | ≤ 0 | 0 |
| `sma50_relative` (weight 15) | > 0 | 15 |
| `sma50_relative` | ≤ 0 | 0 |
| `sma200_relative` (weight 20) | > 0 | 20 |
| `sma200_relative` | ≤ 0 | 0 |
| `sma20_slope` (weight 10) | > 0 | 10 |
| `sma20_slope` | ≤ 0 | 0 |
| `sma50_slope` (weight 15) | > 0 | 15 |
| `sma50_slope` | ≤ 0 | 0 |
| `adx` (weight 15) | ≥ 30 | 15 |
| `adx` | ≥ 20 | 10 |
| `adx` | < 20 | 5 |
| `perf_6m` (weight 5) | > 0 | 5 |
| `perf_6m` | ≤ 0 | 0 |
| `perf_1y` (weight 5) | > 0 | 5 |
| `perf_1y` | ≤ 0 | 0 |

### Entry Timing Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `rsi_14` (weight 25) | 55.0–68.0 | 25 |
| `rsi_14` | 40.0–55.0 | 20 |
| `rsi_14` | 25.0–42.0 | 15 |
| `rsi_14` | 68.0–76.0 | 15 |
| `rsi_14` | > 76.0 | 5 |
| `rsi_14` | < 25.0 | 3 |
| `stochastic_rsi` (weight 15) | 0.2–0.6 | 15 |
| `stochastic_rsi` | > 0.8 | 5 |
| `stochastic_rsi` | < 0.2 | 8 |
| `stochastic_rsi` | 0.6–0.8 | 10 |
| `vwap_deviation` (weight 15) | 0–3% | 15 |
| `vwap_deviation` | > 3% | 8 |
| `vwap_deviation` | < 0 | 5 |
| `bollinger_band_position` (weight 10) | 0.3–0.7 | 10 |
| `bollinger_band_position` | > 0.85 | 3 |
| `bollinger_band_position` | < 0.15 | 5 |
| `bollinger_band_position` | other | 7 |
| `ema8_relative` (weight 10) | 0–3% | 10 |
| `ema8_relative` | > 3% | 5 |
| `ema8_relative` | < 0 | 3 |
| `rsi_slope` (weight 10) | ≥ 3 | 10 |
| `rsi_slope` | ≥ 0 | 7 |
| `rsi_slope` | ≥ −3 | 3 |
| `rsi_slope` | < −3 | 1 |
| `gap_percent` (weight 5) | −1% to +1% | 5 |
| `gap_percent` | > 3% | 1 |
| `gap_percent` | other | 3 |

### Volume / Accumulation Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `obv_trend` (weight 20) | +1 (rising) | 20 |
| `obv_trend` | 0 (flat) | 10 |
| `obv_trend` | −1 (falling) | 0 |
| `ad_trend` (weight 15) | +1 | 15 |
| `ad_trend` | 0 | 7 |
| `ad_trend` | −1 | 0 |
| `chaikin_money_flow` (weight 20) | > 0.1 | 20 |
| `chaikin_money_flow` | > 0 | 12 |
| `chaikin_money_flow` | 0 to −0.1 | 5 |
| `chaikin_money_flow` | < −0.1 | 0 |
| `breakout_volume_multiple` (weight 20) | ≥ 1.5 | 20 |
| `breakout_volume_multiple` | ≥ 1.0 | 12 |
| `breakout_volume_multiple` | < 1.0 | 5 |
| `updown_volume_ratio` (weight 15) | ≥ 1.3 | 15 |
| `updown_volume_ratio` | ≥ 1.0 | 10 |
| `updown_volume_ratio` | < 1.0 | 0 |
| `volume_dryup_ratio` (weight 10) | < 0.7 | 10 |
| `volume_dryup_ratio` | 0.7–1.2 | 6 |
| `volume_dryup_ratio` | > 1.2 | 3 |

### Volatility / Risk Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `max_drawdown_3m` (weight 25) | ≥ −5% | 25 |
| `max_drawdown_3m` | ≥ −10% | 18 |
| `max_drawdown_3m` | ≥ −20% | 10 |
| `max_drawdown_3m` | < −20% | 3 |
| `max_drawdown_1y` (weight 15) | ≥ −10% | 15 |
| `max_drawdown_1y` | ≥ −25% | 8 |
| `max_drawdown_1y` | < −25% | 2 |
| `atr_percent` (weight 20) | ≤ 1.5% | 20 |
| `atr_percent` | ≤ 3.0% | 13 |
| `atr_percent` | ≤ 5.0% | 7 |
| `atr_percent` | > 5.0% | 2 |
| `volatility_weekly` (weight 15) | ≤ 20% ann. | 15 |
| `volatility_weekly` | ≤ 40% ann. | 8 |
| `volatility_weekly` | > 40% ann. | 2 |
| `beta` (weight 15) | 0.5–1.3 | 15 |
| `beta` | ≤ 1.8 | 8 |
| `beta` | > 1.8 | 3 |
| `dist_from_52w_high` (weight 10) | ≥ −5% | 10 |
| `dist_from_52w_high` | ≥ −15% | 6 |
| `dist_from_52w_high` | < −15% | 2 |

### Relative Strength Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `rs_vs_qqq` (weight 30) | ≥ +5% | 30 |
| `rs_vs_qqq` | ≥ 0% | 18 |
| `rs_vs_qqq` | ≥ −5% | 10 |
| `rs_vs_qqq` | < −5% | 0 |
| `return_pct_rank_20d` (weight 15) | ≥ 75th pct | 15 |
| `return_pct_rank_20d` | ≥ 50th pct | 9.75 |
| `return_pct_rank_20d` | ≥ 25th pct | 5.25 |
| `return_pct_rank_20d` | < 25th pct | 0 |
| `return_pct_rank_63d` (weight 20) | ≥ 75th pct | 20 |
| `return_pct_rank_63d` | ≥ 50th pct | 13.0 |
| `return_pct_rank_63d` | ≥ 25th pct | 7.0 |
| `return_pct_rank_63d` | < 25th pct | 0 |
| `return_pct_rank_126d` (weight 15) | ≥ 75th pct | 15 |
| `return_pct_rank_126d` | ≥ 50th pct | 9.75 |
| `return_pct_rank_126d` | ≥ 25th pct | 5.25 |
| `return_pct_rank_126d` | < 25th pct | 0 |
| `return_pct_rank_252d` (weight 20) | ≥ 75th pct | 20 |
| `return_pct_rank_252d` | ≥ 50th pct | 13.0 |
| `return_pct_rank_252d` | ≥ 25th pct | 7.0 |
| `return_pct_rank_252d` | < 25th pct | 0 |

### Growth Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `revenue_growth_yoy` (weight 20) | ≥ 20% | 20 |
| `revenue_growth_yoy` | ≥ 10% | 14 |
| `revenue_growth_yoy` | ≥ 0% | 8 |
| `revenue_growth_yoy` | < 0% | 0 |
| `revenue_growth_qoq` (weight 10) | ≥ 5% | 10 |
| `revenue_growth_qoq` | ≥ 0% | 7 |
| `revenue_growth_qoq` | < 0% | 0 |
| `eps_growth_yoy` (weight 20) | ≥ 20% | 20 |
| `eps_growth_yoy` | ≥ 10% | 13 |
| `eps_growth_yoy` | ≥ 0% | 8 |
| `eps_growth_yoy` | < 0% | 0 |
| `eps_growth_next_year` (weight 10) | ≥ 15% | 10 |
| `eps_growth_next_year` | ≥ 0% | 6 |
| `eps_growth_next_year` | < 0% | 0 |
| `sales_growth_ttm` (weight 10) | ≥ 15% | 10 |
| `sales_growth_ttm` | ≥ 0% | 6 |
| `sales_growth_ttm` | < 0% | 0 |
| `eps_growth_3y` (weight 10) | ≥ 15% | 10 |
| `eps_growth_3y` | ≥ 5% | 6 |
| `eps_growth_3y` | ≥ 0% | 3 |
| `eps_growth_3y` | < 0% | 0 |
| `sales_growth_3y` (weight 8) | ≥ 10% | 8 |
| `sales_growth_3y` | ≥ 5% | 5 |
| `sales_growth_3y` | ≥ 0% | 2 |
| `sales_growth_3y` | < 0% | 0 |
| `eps_growth_next_5y` (weight 7) | ≥ 15% | 7 |
| `eps_growth_next_5y` | ≥ 8% | 4 |
| `eps_growth_next_5y` | < 8% | 1 |
| `beat_rate` (weight 20) | ≥ 75% | 20 |
| `beat_rate` | ≥ 50% | 12 |
| `beat_rate` | < 50% | 0 |
| `avg_eps_surprise_pct` (weight 10) | ≥ 5% | 10 |
| `avg_eps_surprise_pct` | ≥ 2% | 7 |
| `avg_eps_surprise_pct` | ≥ 0% | 4 |
| `avg_eps_surprise_pct` | < 0% | 0 |

### Valuation Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `forward_pe` (weight 20) | ≤ 15 | 20 |
| `forward_pe` | ≤ 25 | 13 |
| `forward_pe` | ≤ 40 | 7 |
| `forward_pe` | > 40 | 2 |
| `peg_ratio` (weight 20) | ≤ 1.0 | 20 |
| `peg_ratio` | ≤ 1.5 | 14 |
| `peg_ratio` | ≤ 2.5 | 8 |
| `peg_ratio` | > 2.5 | 2 |
| `price_to_sales` (weight 15) | ≤ 3 | 15 |
| `price_to_sales` | ≤ 8 | 9 |
| `price_to_sales` | ≤ 15 | 5 |
| `price_to_sales` | > 15 | 1 |
| `ev_to_ebitda` (weight 15) | ≤ 12 | 15 |
| `ev_to_ebitda` | ≤ 20 | 9 |
| `ev_to_ebitda` | ≤ 35 | 4 |
| `ev_to_ebitda` | > 35 | 1 |
| `fcf_yield` (weight 15) | ≥ 5% | 15 |
| `fcf_yield` | ≥ 2% | 9 |
| `fcf_yield` | ≥ 0% | 4 |
| `fcf_yield` | < 0% | 0 |
| `ev_sales` (weight 15) | ≤ 3 | 15 |
| `ev_sales` | ≤ 8 | 9 |
| `ev_sales` | ≤ 15 | 4 |
| `ev_sales` | > 15 | 1 |

### Quality Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `gross_margin` (weight 15) | ≥ 50% | 15 |
| `gross_margin` | ≥ 30% | 9 |
| `gross_margin` | < 30% | 3 |
| `operating_margin` (weight 15) | ≥ 20% | 15 |
| `operating_margin` | ≥ 10% | 9 |
| `operating_margin` | ≥ 0% | 4 |
| `operating_margin` | < 0% | 0 |
| `roe` (weight 15) | ≥ 20% | 15 |
| `roe` | ≥ 10% | 9 |
| `roe` | ≥ 0% | 4 |
| `roe` | < 0% | 0 |
| `roic` (weight 15) | ≥ 15% | 15 |
| `roic` | ≥ 8% | 9 |
| `roic` | ≥ 0% | 4 |
| `roic` | < 0% | 0 |
| `roa` (weight 10) | ≥ 10% | 10 |
| `roa` | ≥ 5% | 6 |
| `roa` | ≥ 0% | 3 |
| `roa` | < 0% | 0 |
| `current_ratio` (weight 10) | ≥ 2.0 | 10 |
| `current_ratio` | ≥ 1.2 | 7 |
| `current_ratio` | < 1.2 | 2 |
| `quick_ratio` (weight 10) | ≥ 1.5 | 10 |
| `quick_ratio` | ≥ 1.0 | 7 |
| `quick_ratio` | < 1.0 | 2 |
| `debt_to_equity` (weight 7) | ≤ 50% | 7 |
| `debt_to_equity` | ≤ 100% | 4 |
| `debt_to_equity` | ≤ 200% | 2 |
| `debt_to_equity` | > 200% | 0 |
| `long_term_debt_equity` (weight 8) | ≤ 30% | 8 |
| `long_term_debt_equity` | ≤ 80% | 5 |
| `long_term_debt_equity` | ≤ 150% | 2 |
| `long_term_debt_equity` | > 150% | 0 |

### Ownership Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `insider_ownership` (weight 15) | ≥ 10% | 15 |
| `insider_ownership` | ≥ 3% | 10 |
| `insider_ownership` | < 3% | 5 |
| `insider_transactions` (weight 20) | > 0 (net buying) | 20 |
| `insider_transactions` | = 0 | 10 |
| `insider_transactions` | < 0 | 0 |
| `institutional_ownership` (weight 15) | 50%–90% | 15 |
| `institutional_ownership` | < 30% | 5 |
| `institutional_ownership` | other | 9 |
| `institutional_transactions` (weight 20) | > 0 | 20 |
| `institutional_transactions` | = 0 | 10 |
| `institutional_transactions` | < 0 | 0 |
| `short_float` (weight 20) | ≤ 5% | 20 |
| `short_float` | ≤ 10% | 12 |
| `short_float` | ≤ 20% | 6 |
| `short_float` | > 20% | 8 (squeeze dual signal) |
| `short_ratio` (weight 10) | ≤ 3 days | 10 |
| `short_ratio` | ≤ 7 days | 6 |
| `short_ratio` | > 7 days | 2 |

### Catalyst Card — Point Table

| Metric | Condition | Points |
|--------|-----------|--------|
| `analyst_recommendation` (weight 25) | ≤ 1.5 | 25 |
| `analyst_recommendation` | ≤ 2.5 | 18 |
| `analyst_recommendation` | ≤ 3.5 | 10 |
| `analyst_recommendation` | ≤ 4.0 | 4 |
| `analyst_recommendation` | > 4.0 | 0 |
| `target_price_distance` (weight 20) | ≥ 20% | 20 |
| `target_price_distance` | ≥ 10% | 14 |
| `target_price_distance` | ≥ 0% | 8 |
| `target_price_distance` | < 0% | 0 |
| `news_score` (weight 25) | ≥ 70 | 25 |
| `news_score` | ≥ 55 | 18 |
| `news_score` | ≥ 45 | 12 |
| `news_score` | ≥ 30 | 5 |
| `news_score` | < 30 | 0 |
| `beat_rate` (weight 15) | ≥ 75% | 15 |
| `beat_rate` | ≥ 50% | 9 |
| `beat_rate` | < 50% | 0 |
| `within_30_days` (weight 15) | True | 10 |
| `within_30_days` | False | 12 |
