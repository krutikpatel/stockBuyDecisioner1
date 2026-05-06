# Stories: Finviz-Inspired Stock Decision Tool Expansion

> Source: `improvements2.md`
> Approach: TDD (failing tests first), HLD+LLD updated after each story, README updated in Story 11.

---

## Story 1: Enhanced Technical Indicators — EMA, Slopes, Performance, Range Distances

**Goal:** Extend `technical_analysis_service.py` with new price/MA/performance/range indicators.

### New Indicators to Compute

| Indicator | Field Name | Formula |
|-----------|-----------|---------|
| EMA 8 relative | `ema8_relative` | `(price - ema8) / ema8 * 100` |
| EMA 21 relative | `ema21_relative` | `(price - ema21) / ema21 * 100` |
| SMA 20 slope | `sma20_slope` | `(sma20[-1] - sma20[-6]) / sma20[-6] * 100` (5-bar slope %) |
| SMA 50 slope | `sma50_slope` | same formula, 5-bar |
| SMA 200 slope | `sma200_slope` | same formula, 5-bar |
| 1W performance | `perf_1w` | `(price / price[-5] - 1) * 100` |
| 1M performance | `perf_1m` | `(price / price[-21] - 1) * 100` |
| 3M performance | `perf_3m` | `(price / price[-63] - 1) * 100` |
| 6M performance | `perf_6m` | `(price / price[-126] - 1) * 100` |
| YTD performance | `perf_ytd` | `(price / price_jan1 - 1) * 100` |
| 1Y performance | `perf_1y` | `(price / price[-252] - 1) * 100` |
| 3Y performance | `perf_3y` | `(price / price[-756] - 1) * 100` (null if insufficient data) |
| 5Y performance | `perf_5y` | `(price / price[-1260] - 1) * 100` (null if insufficient data) |
| Gap % | `gap_percent` | `(open - prev_close) / prev_close * 100` |
| Change from open % | `change_from_open_percent` | `(price - open) / open * 100` |
| Distance from 20D high | `dist_from_20d_high` | `(price / rolling_20d_high - 1) * 100` |
| Distance from 20D low | `dist_from_20d_low` | `(price / rolling_20d_low - 1) * 100` |
| Distance from 50D high | `dist_from_50d_high` | same, 50D |
| Distance from 50D low | `dist_from_50d_low` | same, 50D |
| Distance from 52W high | `dist_from_52w_high` | `(price / rolling_252d_high - 1) * 100` |
| Distance from 52W low | `dist_from_52w_low` | `(price / rolling_252d_low - 1) * 100` |
| ATH distance | `dist_from_ath` | `(price / all_time_high - 1) * 100` |
| ATL distance | `dist_from_atl` | `(price / all_time_low - 1) * 100` |
| Weekly volatility | `volatility_weekly` | std dev of weekly returns × √52 (annualized) |
| Monthly volatility | `volatility_monthly` | std dev of monthly returns × √12 (annualized) |

### Files to Modify
- `backend/app/services/technical_analysis_service.py`
- `backend/app/models/market.py`

### TDD Test File
`backend/tests/test_technical_enhanced.py`

### Acceptance Criteria
- [ ] All new fields present in `TechnicalAnalysisResult`
- [ ] EMA8/21 computed correctly (vs pandas ewm)
- [ ] SMA slopes computed as 5-bar % change
- [ ] Performance periods return None when insufficient history
- [ ] Gap % uses previous close correctly
- [ ] Range distances are negative (price below high) or positive (price above low)
- [ ] Volatility computed as annualized std dev
- [ ] Full test suite passes (no regressions)

---

## Story 2: Volume & Accumulation Indicators

**Goal:** Add volume-based technical indicators to `technical_analysis_service.py`.

### New Indicators

| Indicator | Field Name | Formula |
|-----------|-----------|---------|
| OBV trend score | `obv_trend` | +1 rising, -1 falling, 0 flat (based on 10-bar OBV slope) |
| A/D Line trend | `ad_trend` | +1 rising, -1 falling, 0 flat |
| Chaikin Money Flow | `chaikin_money_flow` | 20-period CMF = sum(MFV) / sum(vol), MFV = ((close-low)-(high-close))/(high-low) × vol |
| VWAP deviation % | `vwap_deviation` | `(price - vwap_20d) / vwap_20d * 100`, VWAP = sum(typical×vol)/sum(vol) over 20 days |
| Anchored VWAP deviation | `anchored_vwap_deviation` | VWAP from last earnings date; null if no earnings date |
| Volume dry-up ratio | `volume_dryup_ratio` | avg(vol[-3:]) / avg(vol[-13:-3]) |
| Breakout volume multiple | `breakout_volume_multiple` | current_vol / avg_vol_20d |
| Up/down volume ratio | `updown_volume_ratio` | sum(vol on up days) / sum(vol on down days) over 20 bars |

### Files to Modify
- `backend/app/services/technical_analysis_service.py`
- `backend/app/models/market.py`

### TDD Test File
`backend/tests/test_volume_indicators.py`

### Acceptance Criteria
- [ ] OBV computed correctly (cumulative based on price direction)
- [ ] A/D Line uses Money Flow Multiplier correctly
- [ ] CMF in range [-1, 1]
- [ ] VWAP deviation computable from 20 days of OHLCV
- [ ] Anchored VWAP returns None when no earnings date provided
- [ ] Volume dry-up ratio: < 1 means drying up
- [ ] Up/down vol ratio > 1 means buying pressure
- [ ] Full test suite passes

---

## Story 3: RS vs QQQ, Return Percentile Ranks, Drawdown, Gap Fill

**Goal:** Add comparative and risk metrics to `technical_analysis_service.py`.

### New Metrics

| Metric | Field Name | Definition |
|--------|-----------|-----------|
| RS vs QQQ | `rs_vs_qqq` | `(stock_63d_return - qqq_63d_return)` |
| Return percentile 20D | `return_pct_rank_20d` | Percentile rank of 20D return vs own 252-period rolling distribution |
| Return percentile 63D | `return_pct_rank_63d` | Same for 63D return |
| Return percentile 126D | `return_pct_rank_126d` | Same for 126D |
| Return percentile 252D | `return_pct_rank_252d` | Same for 252D |
| Max drawdown 3M | `max_drawdown_3m` | Peak-to-trough % over last 63 trading days |
| Max drawdown 1Y | `max_drawdown_1y` | Peak-to-trough % over last 252 trading days |
| Gap fill status | `gap_filled` | True if price has returned to the pre-gap level since the most recent gap |
| Post-earnings drift | `post_earnings_drift` | % return from last earnings date to today; null if no date |

### Files to Modify
- `backend/app/providers/market_data_provider.py` (add QQQ fetch)
- `backend/app/services/technical_analysis_service.py`
- `backend/app/models/market.py`

### TDD Test File
`backend/tests/test_relative_strength.py`

### Acceptance Criteria
- [ ] QQQ data fetched alongside SPY and VIX
- [ ] RS vs QQQ is difference (not ratio) for interpretability
- [ ] Percentile ranks in [0, 100] range
- [ ] Max drawdown is negative (or 0)
- [ ] Gap fill logic handles no-gap case gracefully
- [ ] Full test suite passes

---

## Story 4: Enhanced Fundamental Data Provider

**Goal:** Expand `fundamental_provider.py` with multi-period growth rates, ownership, and new ratios.

### New Fields

| Field | Source | Fallback |
|-------|--------|---------|
| `eps_growth_this_year` | `ticker.info['earningsGrowth']` | None |
| `eps_growth_next_year` | `ticker.info['earningsQuarterlyGrowth']` | None |
| `eps_growth_ttm` | Compute from quarterly EPS | None |
| `eps_growth_3y` | `ticker.info['earningsCagr3Year']` or derived | None |
| `eps_growth_5y` | `ticker.info['earningsCagr5Year']` or derived | None |
| `eps_growth_next_5y` | `ticker.info['longTermPotentialGrowthRate']` | None |
| `sales_growth_qoq` | From quarterly revenue statements | None |
| `sales_growth_ttm` | TTM rev vs prior TTM rev | None |
| `sales_growth_3y` | Derived from annual revenue | None |
| `sales_growth_5y` | Derived from annual revenue | None |
| `roa` | `net_income / total_assets` | None |
| `quick_ratio` | `ticker.info.get('quickRatio')` | None |
| `long_term_debt_equity` | `ticker.info.get('longTermDebt')` / equity | None |
| `insider_ownership` | `ticker.info.get('heldPercentInsiders')` | None |
| `insider_transactions` | `ticker.info.get('insiderTransactions')` | None |
| `institutional_ownership` | `ticker.info.get('heldPercentInstitutions')` | None |
| `institutional_transactions` | `ticker.info.get('netSharePurchaseActivity')` | None |
| `short_float` | `ticker.info.get('shortPercentOfFloat')` | None |
| `short_ratio` | `ticker.info.get('shortRatio')` | None |
| `analyst_recommendation` | `ticker.info.get('recommendationMean')` | None |
| `analyst_target_price` | `ticker.info.get('targetMeanPrice')` | None |
| `target_price_distance` | `(target - price) / price * 100` | None |
| `shares_float` | `ticker.info.get('floatShares')` | None |
| `ipo_date` | `ticker.info.get('firstTradeDateEpochUtc')` | None |
| `dividend_growth_1y` | Compute from dividend history | None |
| `ev_sales` | `enterprise_value / revenue_ttm` | None |
| `price_to_cash` | `price / (cash / shares_outstanding)` | None |

### Files to Modify
- `backend/app/providers/fundamental_provider.py`
- `backend/app/providers/earnings_provider.py` (expose revenue surprise)
- `backend/app/models/fundamentals.py`

### TDD Test File
`backend/tests/test_fundamental_enhanced.py`

### Acceptance Criteria
- [ ] All new fields present in `FundamentalsResult` (Optional[float] with None default)
- [ ] yfinance mock used in tests — no real network calls
- [ ] Missing fields return None (not raise exception)
- [ ] EV/Sales computed correctly when both ev and revenue available
- [ ] Full test suite passes

---

## Story 5: New SignalCard Models & TypeScript Types

**Goal:** Define Pydantic models for 11 signal cards and update response contract.

### New Models

```python
class SignalCardLabel(str, Enum):
    VERY_BEARISH = "VERY_BEARISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    BULLISH = "BULLISH"
    VERY_BULLISH = "VERY_BULLISH"

class SignalCard(BaseModel):
    name: str
    score: float  # 0-100
    label: SignalCardLabel
    explanation: str
    top_positives: list[str]
    top_negatives: list[str]
    missing_data_warnings: list[str]

class SignalCards(BaseModel):
    momentum: SignalCard
    trend: SignalCard
    entry_timing: SignalCard
    volume_accumulation: SignalCard
    volatility_risk: SignalCard
    relative_strength: SignalCard
    growth: SignalCard
    valuation: SignalCard
    quality: SignalCard
    ownership: SignalCard
    catalyst: SignalCard
```

`StockAnalysisResult` gets `signal_cards: SignalCards` field.
`HorizonScore` updated to include `signal_cards_weights: dict[str, float]`.

### Label Thresholds
- 0–20: VERY_BEARISH
- 21–40: BEARISH
- 41–60: NEUTRAL
- 61–80: BULLISH
- 81–100: VERY_BULLISH

### TDD Test File
`backend/tests/test_signal_card_models.py`

### Acceptance Criteria
- [ ] SignalCard serializes/deserializes via Pydantic
- [ ] Score→label threshold mapping correct
- [ ] SignalCards contains all 11 cards
- [ ] StockAnalysisResult accepts signal_cards field
- [ ] TypeScript types in `stock.ts` mirror Pydantic models

---

## Story 6: 11 Signal Card Scoring Engine

**Goal:** Create `backend/app/services/signal_card_service.py`.

### Signal Card Scoring Logic

Each card starts at 50 and adjusts up/down. Max adjustments sum to ±50.

#### 1. Momentum Card
Inputs: `perf_1w`, `perf_1m`, `perf_3m`, `macd_histogram`, `rsi` (slope implied by current vs prior RSI), `sma20_relative`, `sma50_relative`
- perf_1w > 0: +5; > 3%: +5
- perf_1m > 0: +5; > 5%: +5
- perf_3m > 0: +5; > 10%: +5
- MACD histogram > 0: +5; crossing from negative: +5
- RSI 50-70: +5; RSI rising: +5
- price > sma20: +5; price > sma50: +5

#### 2. Trend Card
Inputs: `sma20_relative`, `sma50_relative`, `sma200_relative`, `sma20_slope`, `sma50_slope`, `sma200_slope`, `adx`
- price > sma20: +10; > sma50: +10; > sma200: +10
- sma20 > sma50 (golden cross): +5
- sma50 > sma200: +5
- All slopes positive: +5; sma200_slope > 0: +5
- ADX > 25: +5 (trending); ADX > 40: +5

#### 3. Entry Timing Card
Inputs: `rsi`, `stochastic_rsi`, `ema8_relative`, `ema21_relative`, `gap_percent`, `vwap_deviation`, `dist_from_20d_high`
- RSI 45-65: +15 (ideal); RSI 65-75: +5 (ok); RSI > 75 or < 40: penalty
- Stoch RSI: 20-60: +10 (good entry zone)
- price near VWAP (deviation < 1%): +10
- dist_from_20d_high > -5% (not extended): +10
- No large gap today (gap_percent < 2%): +5

#### 4. Volume/Accumulation Card
Inputs: `breakout_volume_multiple`, `obv_trend`, `ad_trend`, `chaikin_money_flow`, `updown_volume_ratio`, `volume_dryup_ratio`
- breakout vol > 1.5: +10; > 2.0: +10
- OBV rising (+1): +10
- A/D rising (+1): +10
- CMF > 0: +5; > 0.1: +5
- up/down vol ratio > 1.2: +5; > 1.5: +5

#### 5. Volatility/Risk Card (inverted — lower risk = higher score)
Inputs: `atr_percent`, `volatility_weekly`, `beta`, `max_drawdown_3m`, `max_drawdown_1y`
- atr_percent < 2%: +15; < 3%: +10; > 5%: -10
- beta 0.8-1.5: +10; > 2.5: -10
- max_drawdown_3m > -10%: +15; > -20%: +5; < -30%: -10
- max_drawdown_1y > -20%: +10

#### 6. Relative Strength Card
Inputs: `rs_vs_spy`, `rs_vs_qqq`, `rs_vs_sector`, `return_pct_rank_20d`, `return_pct_rank_63d`
- rs_vs_spy > 0: +10; > 5%: +10
- rs_vs_qqq > 0: +10
- rs_vs_sector > 0: +10
- return_pct_rank_63d > 60: +5; > 80: +5

#### 7. Growth Card
Inputs: `eps_growth_ttm`, `eps_growth_this_year`, `sales_growth_ttm`, `sales_growth_qoq`, `avg_eps_surprise`, `avg_rev_surprise` (from earnings)
- EPS growth > 0%: +5; > 10%: +5; > 25%: +5
- Sales growth > 0%: +5; > 10%: +5; > 20%: +5
- EPS surprise > 0%: +5; > 5%: +5
- Revenue surprise > 0%: +5; > 2%: +5

#### 8. Valuation Card
Inputs: `forward_pe`, `peg_ratio`, `price_to_sales`, `ev_ebitda`, `price_to_fcf`, `ev_sales`
- fwd P/E < 15: +15; < 25: +10; > 40: -10; > 60: -15
- PEG < 1.0: +15; < 1.5: +10; > 3.0: -10
- P/S < 3: +10; < 6: +5; > 15: -10
- P/FCF < 20: +10; < 30: +5; > 60: -10

#### 9. Quality Card
Inputs: `gross_margin`, `operating_margin`, `net_margin`, `roe`, `roic`, `roa`, `current_ratio`, `quick_ratio`, `debt_to_equity`
- gross_margin > 50%: +10; > 30%: +5
- operating_margin > 20%: +10; > 10%: +5; < 0: -10
- ROIC > 15%: +15; > 8%: +5
- ROE > 15%: +10
- current_ratio > 1.5: +5; < 1.0: -5
- debt_to_equity < 0.5: +5; > 2.0: -5

#### 10. Ownership Card
Inputs: `insider_ownership`, `insider_transactions`, `institutional_ownership`, `institutional_transactions`, `short_float`
- insider_ownership > 5%: +5; > 15%: +5
- insider_transactions > 0 (net buying): +15; < 0 (net selling): -10
- institutional_ownership > 60%: +5
- institutional_transactions > 0: +10; < 0: -5
- short_float > 20%: squeeze risk → +5 (contrarian) or flag

#### 11. Catalyst Card
Inputs: `news_score`, `analyst_recommendation`, `target_price_distance`, `earnings_within_30d`, `beat_rate`, `avg_eps_surprise`
- news_score > 60: +10; > 75: +10
- analyst_rec < 2.5 (buy consensus): +10; < 2.0: +5
- target_distance > 10%: +10; > 20%: +5
- earnings NOT within 30d: +5 (no event risk)
- beat_rate > 75%: +10; avg_eps_surprise > 5%: +5

### TDD Test File
`backend/tests/test_signal_card_service.py` (33+ tests)

### Acceptance Criteria
- [ ] All 11 cards return SignalCard with correct types
- [ ] Scores stay in [0, 100] range
- [ ] Missing inputs excluded from score, added to missing_data_warnings
- [ ] High-score scenario test passes for each card
- [ ] Low-score scenario test passes for each card
- [ ] Null-input scenario test passes for each card

---

## Story 7: Revised Horizon Scoring & Recommendation Engine

**Goal:** Replace composite scoring with signal-card weighted scoring per horizon.

### New Signal Card → Horizon Weights

**Short-term:**
| Signal Card | Weight |
|-------------|--------|
| momentum | 25% |
| volume_accumulation | 20% |
| entry_timing | 20% |
| relative_strength | 15% |
| volatility_risk | 10% |
| catalyst | 10% |

**Medium-term:**
| Signal Card | Weight |
|-------------|--------|
| trend | 20% |
| growth | 20% |
| relative_strength | 15% |
| volume_accumulation | 15% |
| valuation | 10% |
| quality | 10% |
| catalyst | 10% |

**Long-term:**
| Signal Card | Weight |
|-------------|--------|
| growth | 20% |
| quality | 20% |
| valuation | 15% |
| trend | 10% |
| momentum | 5% (sector tailwind proxy) |
| ownership | 5% |
| volatility_risk | 5% |

### New Decision Labels

**Short-term** (based on momentum, entry_timing, trend cards):
- `BUY_NOW_MOMENTUM`: momentum > 65, entry_timing > 55, not overbought
- `BUY_STARTER_STRONG_BUT_EXTENDED`: momentum > 65, entry_timing < 45 (extended)
- `WAIT_FOR_PULLBACK`: trend > 60, momentum > 50, entry_timing < 40
- `AVOID_BAD_CHART`: trend < 40 or (momentum < 40 and relative_strength < 40)

**Medium-term** (based on growth, trend, valuation cards):
- `BUY_NOW`: trend > 60, growth > 55, valuation > 40
- `BUY_STARTER`: trend > 55, growth > 50, valuation < 40 (extended)
- `BUY_ON_PULLBACK`: trend > 60, growth > 50, entry_timing < 40
- `WATCHLIST_NEEDS_CONFIRMATION`: growth > 50, trend < 50
- `AVOID_BAD_BUSINESS`: growth < 40 or quality < 35

**Long-term** (based on quality, growth, valuation cards):
- `BUY_NOW_LONG_TERM`: quality > 65, growth > 55, valuation > 45
- `ACCUMULATE_ON_WEAKNESS`: quality > 65, growth > 55, valuation < 40
- `WATCHLIST_VALUATION_TOO_RICH`: quality > 60, growth > 55, valuation < 30
- `AVOID_LONG_TERM`: quality < 40 or growth < 35

### Files to Modify
- `backend/app/services/scoring_service.py`
- `backend/app/services/recommendation_service.py`

### TDD Test File
`backend/tests/test_revised_scoring.py`

### Acceptance Criteria
- [ ] Horizon score = weighted sum of signal card scores
- [ ] Regime multipliers still applied after weighted sum
- [ ] Decision labels use new names
- [ ] Correct label returned for boundary conditions
- [ ] Full test suite passes

---

## Story 8: Risk Management, Signal Profile & Markdown Report Updates

**Goal:** Update downstream services to use new fields and include signal cards in output.

### Changes

**risk_management_service.py:**
- Use `atr_percent` (from Story 1) for stop-loss calculation
- Use `dist_from_20d_low` as downside reference
- Include `risk_reward_ratio` in RiskManagement output

**signal_profile_service.py:**
- Map signal card scores → 6 profile dimensions:
  - momentum_label ← momentum card label
  - growth_label ← growth card label
  - valuation_label ← valuation card label (mapped: BULLISH→ATTRACTIVE, etc.)
  - entry_timing_label ← entry_timing card score → IDEAL/ACCEPTABLE/EXTENDED/VERY_EXTENDED
  - sentiment_label ← catalyst card label
  - risk_reward_label ← volatility_risk card score → EXCELLENT/GOOD/ACCEPTABLE/POOR

**markdown_report_service.py:**
- Add "Signal Cards" section with table: Card | Score | Label | Key Factors
- Add performance table: 1W | 1M | 3M | 6M | YTD | 1Y | 3Y | 5Y
- Update horizon section to show new decision labels

### TDD Test File
`backend/tests/test_risk_report_updates.py`

### Acceptance Criteria
- [ ] Risk plan uses atr_percent correctly
- [ ] Signal profile maps all 6 dimensions from cards
- [ ] Markdown report contains "## Signal Cards" heading
- [ ] Markdown report contains performance table
- [ ] Full test suite passes

---

## Story 9: Frontend — SignalCard & SignalCardsGrid Components

**Goal:** Build signal card UI components and integrate into Dashboard.

### Components

**SignalCard.tsx:**
- Score gauge (arc or progress bar, 0–100)
- Label badge with color: VERY_BEARISH=red-700, BEARISH=red-400, NEUTRAL=gray, BULLISH=green-400, VERY_BULLISH=green-700
- Card name + score number
- Expandable section: top_positives (green bullets), top_negatives (red bullets)
- Missing data warnings (amber, collapsible)

**SignalCardsGrid.tsx:**
- Responsive grid: 2 cols mobile, 3 cols tablet, 4 cols desktop, overflow to 3-col last row for 11
- Order: Momentum, Trend, Entry Timing, Volume/Acc, Volatility/Risk, Relative Strength, Growth, Valuation, Quality, Ownership, Catalyst

**Dashboard.tsx:**
- Add `<SignalCardsGrid cards={result.signal_cards} />` after the main header
- De-emphasize or remove old composite score cards (keep horizon recommendations)

### TDD Test File
`frontend/src/components/__tests__/SignalCard.test.tsx`

### Acceptance Criteria
- [ ] Score renders correctly for all values (0, 50, 100)
- [ ] Label badge color matches label value
- [ ] Positives/negatives expand/collapse
- [ ] Missing warnings shown in amber
- [ ] Grid renders all 11 cards without crash
- [ ] Null/empty arrays handled gracefully

---

## Story 10: Frontend — Enhanced Data Panels

**Goal:** Display new indicators from Stories 1–4 in existing panels.

### Panel Updates

**Technical Panel** (add rows):
- EMA8 deviation %, EMA21 deviation %
- SMA20 slope, SMA50 slope, SMA200 slope
- VWAP deviation %
- Stochastic RSI
- ADX

**Performance Table** (new section):
| 1W | 1M | 3M | 6M | YTD | 1Y | 3Y | 5Y |
with color coding (green positive, red negative)

**Fundamental Panel** (add rows):
- ROA, ROIC (if not already shown)
- Quick ratio
- Long-term D/E

**Ownership Panel** (new section):
- Insider ownership %, Insider transactions (buying/selling)
- Institutional ownership %, Institutional transactions
- Short float %

**Valuation Panel** (add rows):
- EV/Sales
- Price/FCF
- Analyst target distance %

**Volume Panel** (add rows):
- OBV trend (arrow up/flat/down)
- A/D trend
- CMF value
- Up/Down vol ratio
- Volume dry-up ratio

### TDD Test File
`frontend/src/components/__tests__/DataPanelUpdates.test.tsx`

### Acceptance Criteria
- [ ] New fields render when data is present
- [ ] Null fields display "N/A"
- [ ] Performance table colors green/red correctly
- [ ] No crash when signal_cards or new fields are missing

---

## Story 11: Final HLD/LLD & README Update

**Goal:** Bring all documentation fully up to date.

### HLD.md Changes
- Architecture diagram: add `signal_card_service` as 12th service
- Analysis pipeline: replace old 11-stage list with new 12-stage list including signal cards
- Scoring System section: new 3-tier with signal card weights per horizon
- Decision Logic section: new labels per horizon
- Data Model section: add SignalCard, SignalCards models
- Frontend Component Tree: add SignalCard, SignalCardsGrid, new panel sections
- Known Limitations: update for new yfinance limitations

### LLD.md Changes
- Project Layout: add all new files
- Module specs: update technical_analysis_service, fundamental_provider, scoring_service, recommendation_service; add signal_card_service

### README.md Changes
- "What It Does": 55+ indicators
- New "Signal Cards" section
- Updated scoring weight tables per horizon
- Updated decision label list
- Updated test count
- Updated known limitations
