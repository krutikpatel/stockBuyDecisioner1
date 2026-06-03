# Backend — What It Does (Plain English)

## The Big Picture

You provide two inputs: a **stock ticker** (e.g. `NVDA`) and a **risk profile** (`conservative / moderate / aggressive`). All algorithm tuning parameters come from `algo_config.json`. The backend then runs a full multi-layer analysis pipeline and returns a structured recommendation for three investment horizons: **short-term, medium-term, and long-term**.

---

## Step 1 — Fetch Raw Data

The backend pulls everything from Yahoo Finance (yfinance):

| What | Source | Used For |
|------|--------|----------|
| 1-year daily OHLCV price history | yfinance | All technical calculations |
| SPY + QQQ 1-year history | yfinance | Market regime, relative strength benchmark |
| Sector ETF 6-month history | yfinance | Sector macro score |
| VIX 1-month history | yfinance | Market regime classification |
| Company snapshot (`ticker.info`) | yfinance | Fundamentals, sector, beta, analyst data |
| Quarterly income / balance / cashflow statements | yfinance | Revenue, margins, debt, ROE, ROIC |
| Earnings history + next earnings date | yfinance | Beat rate, surprise %, earnings proximity |
| Recent news headlines | yfinance | Sentiment scoring |
| Options chain (nearest expiry) | yfinance | Put/call ratio for catalyst signal |

Price data is cached 15 minutes; fundamental data is cached 24 hours.

---

## Step 2 — Technical Analysis

Runs entirely on price/volume history. Computes ~50+ indicators:

**Moving Averages & Trend**
- SMA 10/20/50/100/200 and EMA 8/21
- SMA slopes (20/50/200 — rising or falling?)
- Where price sits relative to each MA (% above/below)
- Trend classification: STRONG_UPTREND / UPTREND / SIDEWAYS / DOWNTREND / STRONG_DOWNTREND
- Extension detection: price > 8% above SMA20 or > 15% above SMA50, or RSI > 75 → `is_extended = True`

**Momentum & Oscillators**
- RSI(14) — overbought/oversold
- MACD (fast=12, slow=26, signal=9 lines + histogram)
- ADX(14) — trend strength
- Stochastic RSI(14) — short-term momentum

**Volatility**
- ATR(14) — absolute and % form
- Bollinger Bands(20, 2σ) — position and width
- Weekly/monthly volatility
- Max drawdown over 3M (63 bars) and 1Y (252 bars)

**Performance Periods**
- Returns for: 1W / 1M / 3M / 6M / 1Y / 3Y / 5Y
- Return percentile ranks vs the stock's own 252-day window (20/63/126/252 bar ranks)

**Volume & Accumulation**
- OBV (On-Balance Volume) trend (slope over 10 bars)
- Accumulation/Distribution trend (slope over 10 bars)
- CMF (Chaikin Money Flow, 20-period)
- VWAP deviation (20-period)
- Volume dry-up: recent 3-bar avg vs 10-bar ref (< 0.85x = drying up)
- Breakout volume multiplier vs 20-bar average
- Up-volume vs down-volume ratio (20-period)

**Relative Strength**
- RS vs SPY (63-day), RS vs QQQ, RS vs sector ETF (20/63-day windows)
- Distance from 52-week high/low and all-time high/low
- Support and resistance levels (60-bar lookback, up to 3 levels, 1% cluster tolerance)

---

## Step 3 — Stock Archetype Classification

The backend classifies the stock into one of 8 archetypes based on revenue growth, margins, FCF, and debt. This matters because a 40x P/E is fine for a hyper-growth company but terrible for a mature business.

| Archetype | What It Means |
|-----------|--------------|
| `HYPER_GROWTH` | Revenue YoY ≥ 30% (or ≥ 20% with fwd P/E ≥ 40) |
| `PROFITABLE_GROWTH` | Revenue YoY ≥ 15% — default for growing, profitable companies |
| `CYCLICAL_GROWTH` | Beta ≥ 1.3 in cyclical sectors (Energy, Materials, Industrials, Consumer Cyclical) |
| `MATURE_VALUE` | Revenue growth ≤ 10%, slow/stable |
| `TURNAROUND` | EPS growth ≥ 10% or revenue QoQ ≥ 5%, but still slow overall |
| `SPECULATIVE_STORY` | P/S ≥ 20 with high growth, or P/S ≥ 40 |
| `DEFENSIVE` | Beta ≤ 0.8 in defensive sectors (Healthcare, Consumer Defensive, Utilities) |
| `COMMODITY_CYCLICAL` | In commodity sectors (Energy, Basic Materials) |

Default fallback when data is ambiguous: `PROFITABLE_GROWTH` (confidence 40%).

---

## Step 4 — Fundamental Analysis

Scores the company's financial health 0–100:

- Revenue growth: YoY, QoQ, 3-year, 5-year
- EPS growth: TTM, 3-year, 5-year, forward estimate
- Margins: Gross / Operating / Net margin
- Cash flow: Free cash flow, FCF margin
- Balance sheet: Net debt, Debt-to-equity, Long-term D/E, Quick ratio
- Returns: ROE, ROIC, ROA
- Ownership: Insider %, institutional %, short float %, analyst recommendation, target price distance

---

## Step 5 — Valuation Analysis (Archetype-Adjusted)

Two scoring modes:

1. **Generic valuation** — scores raw multiples: trailing P/E, forward P/E, PEG, P/Sales, EV/EBITDA, P/FCF, FCF yield, EV/Sales, P/Book, P/Cash
2. **Archetype-adjusted valuation** — applies different thresholds per archetype. `HYPER_GROWTH` uses Rule-of-40 and looser P/E tiers; `MATURE_VALUE` uses tighter forward P/E tiers. This prevents NVDA/PLTR from being penalized by a simple P/E check.

Output: `valuation_score` (generic) and `archetype_adjusted_score` (used for decisions). If `archetype_adjusted_score > 0`, it takes priority over the generic score.

---

## Step 6 — Market Regime Classification

Looks at SPY, QQQ, and VIX to classify the current macro environment into one of 6 regimes:

| Regime | What It Means |
|--------|--------------|
| `BULL_RISK_ON` | SPY above 50DMA and 200DMA, QQQ above 200DMA, VIX < 20 |
| `BULL_NARROW_LEADERSHIP` | Market up but only a few sectors/stocks leading |
| `SIDEWAYS_CHOPPY` | SPY above 200DMA but below 50DMA, mixed signals |
| `BEAR_RISK_OFF` | SPY below key MAs, VIX > 25 |
| `SECTOR_ROTATION` | Mixed MA signals across SPY/QQQ |
| `LIQUIDITY_RALLY` | VIX elevated but recovering from bear |

The regime affects scoring via multipliers on individual sub-scores:
- `BULL_RISK_ON`: technical_momentum ×1.20, relative_strength ×1.15, growth ×1.15, valuation ×0.70
- `BEAR_RISK_OFF`: valuation ×1.30, balance_sheet ×1.25, technical_momentum ×0.90
- `SIDEWAYS_CHOPPY`: risk_reward ×1.25, technical_momentum ×0.85

For the signal-card composite path, a simpler approach is used: `BULL_RISK_ON` adds up to +10% to short-term composite, `BEAR_RISK_OFF` subtracts up to -10% (scaled by regime confidence).

---

## Step 7 — Earnings & Sentiment & Catalyst

**Earnings Analysis**
- Beat rate over last 8 quarters
- Average EPS surprise %
- Is the next earnings date within 30 days? (adds risk)
- Produces an `earnings_score` 0–100

**Sentiment Analysis**
- Each news headline is classified as positive / neutral / negative
- Uses GPT-4o-mini if OpenAI API key is set; falls back to keyword matching
- Produces a `news_score` 0–100

**Catalyst Signal (from Options)**
- Looks at put/call ratio from the nearest options expiry
- PCR < 0.7 → bullish → `catalyst_score = 65`
- PCR > 1.3 → bearish → `catalyst_score = 35`
- Otherwise → neutral → `catalyst_score = 50`

**Sector Macro Score**
- Computes 63-day relative strength of the stock's sector ETF vs SPY
- RS > 1.05 → score 65; RS < 0.95 → score 35; else → score 50

---

## Step 8 — 11 Signal Cards (Designed, In Codebase)

> **Important:** The 11 signal card scorers are fully implemented in `signal_card_service.py`, but the **production API router (`stock.py`) does not currently call `score_all_cards`**. The router uses the legacy `compute_scores()` path instead. Signal cards are not yet wired into the live API pipeline.

Each card scores one aspect 0–100 with a label (VERY_BULLISH → VERY_BEARISH), top positives/negatives, and missing-data warnings.

| Signal Card | What It Scores |
|-------------|----------------|
| **Momentum** | 1W/1M/3M performance, MACD, RSI, EMA8/21 |
| **Trend** | Price vs SMA20/50/200, SMA slopes, ADX, 6M/1Y return |
| **Entry Timing** | RSI zone (ideal 55–68), StochRSI, VWAP deviation, BB position, EMA8 deviation |
| **Volume/Accumulation** | OBV trend, A/D trend, CMF, breakout vol multiple, up/down vol ratio, dry-up |
| **Volatility/Risk** | Max drawdown (3M/1Y), ATR%, weekly vol, beta, distance from 52W high |
| **Relative Strength** | RS vs QQQ (primary), return percentile ranks (20/63/126/252 day) |
| **Growth** | EPS/revenue growth multi-period, EPS beat rate, EPS surprise % |
| **Valuation** | fwd P/E, PEG, P/Sales, EV/EBITDA, FCF yield, EV/Sales |
| **Quality** | Gross/op margins, ROE, ROIC, ROA, current/quick ratio, D/E ratios |
| **Ownership** | Insider/institutional ownership + transaction direction, short float/ratio |
| **Catalyst** | Analyst rec, target price distance, news score, beat rate, earnings proximity |

---

## Step 9 — Composite Scoring per Horizon

### Active Path: Legacy Scoring (what the production router uses)

`compute_scores()` maps sub-scores to legacy weight buckets:

| Bucket | Short-Term (weight) | Medium-Term (weight) | Long-Term (weight) |
|--------|--------------------|--------------------|------------------|
| Technical momentum / trend / quality | 30% | 20% | 25% + 20% + 15% (business/growth/fcf) |
| Relative strength | 20% | — | — |
| Catalyst + news | 20% | 10% | — |
| Options flow | 10% | — | — |
| Market regime | 10% | — | — |
| Risk/reward | 10% | — | — |
| Earnings revision | — | 25% | — |
| Growth acceleration | — | 20% | — |
| Sector strength | — | 15% | — |
| Valuation (growth-adj) | — | 10% | 15% |
| Balance sheet | — | — | 15% |
| Competitive moat | — | — | 10% |

Note: many long-term buckets (business_quality, growth_durability, fcf_quality, competitive_moat) all map to `fundamentals.fundamental_score` — so the long-term composite is heavily weighted toward fundamental quality.

### Designed Path: Signal Card Weights (when signal cards are passed)

When `signal_cards` is provided to `build_recommendations`, the following weights are used instead:

| Signal Card | Short-Term | Medium-Term | Long-Term |
|-------------|-----------|------------|----------|
| Momentum | 25% | — | — |
| Volume/Accum | 20% | 15% | — |
| Entry Timing | 20% | — | — |
| Relative Strength | 15% | 15% | — |
| Volatility/Risk | 10% | — | 5% |
| Catalyst | 10% | 10% | 10% |
| Trend | — | 20% | 10% |
| Growth | — | 20% | 20% |
| Valuation | — | 10% | 15% |
| Quality | — | 10% | **35%** |
| Ownership | — | — | 5% |

---

## Step 10 — Decision Labels

Each horizon gets one decision label. The label set depends on whether signal cards are available.

### Active Path: Legacy Decision Functions (production router, no signal_cards)

**Short-Term** (`_decide_short_term`):

| Label | Condition |
|-------|-----------|
| `AVOID_BAD_CHART` | Chart in downtrend + RS vs SPY < 0.8 + score < 55 (or bear regime + weak chart) |
| `AVOID_BAD_BUSINESS` | Revenue declining + op margin < -5% or beat rate < 40% + score < 55 |
| `BUY_AFTER_EARNINGS` | Score 55–69 + earnings within 30 days |
| `BUY_NOW` | Score ≥ 80 + not extended + nearest support exists |
| `BUY_STARTER` | Score ≥ 80 + not extended (no support), or score 70–79 |
| `BUY_STARTER_EXTENDED` | Score ≥ 65 + is_extended + bull regime |
| `BUY_ON_PULLBACK` | Score ≥ 65 + is_extended + not bull, or score ≥ 65 generally |
| `AVOID` | Score < 50 |
| `WATCHLIST` | Score 50–64 (fallback) |

**Medium-Term** (`_decide_medium_term`):

| Label | Condition |
|-------|-----------|
| `AVOID_BAD_BUSINESS` | Business deteriorating + score < 65 |
| `AVOID_BAD_CHART` | Chart weak + score < 55 |
| `BUY_NOW` | Score ≥ 82 + not extended |
| `BUY_STARTER` | Score 72–81, or score ≥ 82 + extended |
| `BUY_STARTER_EXTENDED` | Score ≥ 68 + extended + bull regime |
| `BUY_ON_PULLBACK` | Score ≥ 68 + extended (not bull), or score ≥ 68 generally |
| `WATCHLIST` | Score 55–67 |
| `AVOID` | Score < 55 |

**Long-Term** (`_decide_long_term`):

| Label | Condition |
|-------|-----------|
| `AVOID_BAD_BUSINESS` | Business deteriorating + score < 65 |
| `AVOID_BAD_CHART` | Chart weak + score < 60 |
| `BUY_NOW` | Score ≥ 85 + not extended |
| `BUY_STARTER` | Score 75–84 |
| `BUY_ON_BREAKOUT` | Score ≥ 75 + is_extended |
| `WATCHLIST` | Score 60–74 |
| `AVOID` | Score < 60 |

### Designed Path: v2 Decision Functions (when signal_cards are passed)

These precise labels are used when `signal_cards` is provided. The thresholds come from `algo_config.json → decision_logic`:

**Short-Term** (`_decide_short_term_v2`), score_min = **70**:

| Label | Condition |
|-------|-----------|
| `TRUE_DOWNTREND_AVOID` / `BROKEN_SUPPORT_AVOID` | Chart weak + score < 50 (or score < 40 unconditionally) |
| `OVERSOLD_REBOUND_CANDIDATE` | RSI 25–42 + turning up + improving price + vol ≥ 1.2 |
| `WAIT_FOR_PULLBACK` | 1W > 10% or 1M > 25% (chasing) OR SMA20 > 10% above |
| `BUY_NOW_CONTINUATION` | Score ≥ 70 + RSI in regime-range + SMA20 0–5% + SMA50 ≤ 12% + RS all positive + vol ≥ 1.3 |
| `BUY_STARTER_STRONG_BUT_EXTENDED` | Score ≥ 70 + is_extended or SMA20 5–10% or RSI > regime max |
| `BUY_ON_PULLBACK` | Score ≥ 55 + price near SMA50 (−3% to +5%) + RSI 40–58 + vol drying up |
| `WATCHLIST` | Score ≥ 55 (fallback) |

Regime thresholds for BUY_NOW_CONTINUATION:

| Regime | RSI range | SMA20 max | Rel-vol min |
|--------|-----------|-----------|-------------|
| BULL_RISK_ON | 55–68 | 5% | 1.3 |
| LIQUIDITY_RALLY | 55–74 | 8% | 1.2 |
| SIDEWAYS_CHOPPY | 40–58 | 3% | 1.3 |
| BEAR_RISK_OFF | blocks all (impossible thresholds) | — | — |

**Medium-Term** (`_decide_medium_term_v2`): BUY_NOW (≥**72**) → BUY_STARTER (≥**60**) → BUY_ON_PULLBACK (≥60 + extended) → WATCHLIST_NEEDS_CONFIRMATION (≥**45**) → AVOID_BAD_BUSINESS

**Long-Term** (`_decide_long_term_v2`): BUY_NOW_LONG_TERM (≥**72**) → ACCUMULATE_ON_WEAKNESS (≥**55**) → WATCHLIST_VALUATION_TOO_RICH (≥**40**) → AVOID_LONG_TERM

---

## Step 11 — Data Completeness & Confidence

Before finalizing the recommendation, the backend checks for missing data:

| Missing Data | Score Deduction |
|-------------|----------------|
| No news items | -15 |
| No options data | -15 |
| No next earnings date | -10 |
| No peer comparison data | -5 |
| Insufficient price history | -5 |

- `completeness < 60` → `confidence_score` capped at **60**
- `completeness < 55` → decision forced to `AVOID_LOW_CONFIDENCE` regardless of score
- Full data → completeness = 100, no caps applied

---

## Step 12 — Risk Management Output

For each horizon, the backend computes concrete trading parameters:

**Entry Plan**
- Preferred entry price
- Starter position entry (more conservative)
- Breakout entry (if waiting for confirmation)
- Avoid-above price (chase avoidance)

**Exit Plan**
- Stop-loss — ATR-based when ATR is available: 1.5× ATR (short), 2.0× ATR (medium), 2.5× ATR (long)
- Falls back to support-level buffer (0.99× nearest support) or fixed 8% below price when no support
- Invalidation level = stop_loss − 0.5× ATR (slightly below stop)
- First target: nearest resistance or +10% if none
- Second target: next resistance or +20% if none

**Risk/Reward**
- Downside % from preferred entry to stop
- Upside % from preferred entry to first target
- R/R ratio computed (no hard enforced minimum — just reported)

**Position Sizing** (scales with risk profile and ATR volatility):

| Risk Profile | Starter % of full | Max Portfolio % |
|-------------|------------------|----------------|
| Conservative | 15% | 3.0% |
| Moderate | 25% | 5.0% |
| Aggressive | 40% | 8.0% |

Additional adjustments:
- If earnings within 30 days → **starter_pct × 0.50** (halved), **max_alloc × 0.70** (reduced by 30%)
- ATR% < 4% → full size (×1.0); 4–7% → ×0.55; > 7% → ×0.30

---

## Step 13 — Signal Profile (6 Human-Readable Dimensions)

Derived from sub-scores, six summary labels for quick human review. The production router calls `build_signal_profile()` (legacy path):

| Dimension | Possible Labels | Derived From (legacy path) |
|-----------|----------------|--------------------------|
| Momentum | VERY_BULLISH → VERY_BEARISH | `technical_score` (≥80 + not extended = VERY_BULLISH) |
| Growth | VERY_BULLISH → VERY_BEARISH | `fundamental_score` |
| Valuation | ATTRACTIVE / FAIR / ELEVATED / RISKY | `archetype_adjusted_score` (≥70 / ≥55 / ≥40 / <40) |
| Entry Timing | IDEAL / ACCEPTABLE / EXTENDED / VERY_EXTENDED | `is_extended` + `extension_pct_above_20ma` (≥15% = VERY_EXTENDED) + trend label |
| Sentiment | VERY_BULLISH → VERY_BEARISH | `news_score` |
| Risk/Reward | EXCELLENT / GOOD / ACCEPTABLE / POOR | `(earnings_score + technical_score) / 2` |

> When signal cards are wired in, `build_signal_profile_from_cards()` is used instead: Momentum from momentum card, Growth from growth card, Sentiment from catalyst card, Risk/Reward from volatility_risk card.

---

## Step 14 — Markdown Report

The backend generates a full human-readable markdown report summarizing all findings: archetype, regime, signal card scores (when available), horizon recommendations, and risk plans.

---

## What `algo_config.json` Controls

The `algo_config.json` file controls every tunable number in the system — nothing is hardcoded in service modules. It has 12 sections:

| Section | Controls |
|---------|---------|
| `technical_indicators` | RSI period (14), MACD 12/26/9, ATR period (14), SMA/EMA periods, OBV/CMF windows, RS periods |
| `technical_scoring` | Points awarded per RSI zone, trend label, MACD direction, extension, RS strength |
| `extension_detection` | SMA20 > 8%, SMA50 > 15%, RSI > 75 → is_extended |
| `stock_archetype` | Revenue growth cutoffs, beta thresholds, P/S thresholds, sector lists per archetype |
| `market_regime` | VIX thresholds (20/25/30), per-regime confidence values |
| `regime_scoring` | Score multipliers and composite adjustments per regime |
| `scoring` | Both legacy weights and signal card weights per horizon (must each sum to 100) |
| `signal_cards` | Per-card scoring thresholds (RSI zones, volume ratios, ADX levels, growth cutoffs) |
| `decision_logic` | Gate values for every BUY/AVOID label, regime threshold overrides, RS leader/avoid gates |
| `data_completeness` | Deduction amounts, confidence_cap_threshold (60), avoid_low_confidence_threshold (55) |
| `risk_management` | ATR stop multipliers, position sizing per profile, pre-earnings cuts, ATR size thresholds |
| `valuation` | Per-archetype score tiers (hyper_growth, mature_value, cyclical_growth, defensive, standard) |

To experiment: edit `algo_config.json` (or set `ALGO_CONFIG_PATH` env var to a different file) — no code changes needed.

---

## Summary Flow (End to End — Production)

```
Ticker + Risk Profile
        |
        v
[Fetch Data] yfinance — price, fundamentals, sector, VIX, earnings, news, options
        |
        v
[Classify Archetype] — 8 categories based on growth/margins/FCF/beta/sector
        |
        v
[Classify Market Regime] — 6 regimes from SPY/QQQ MAs + VIX level
        |
        v
[Compute Technicals]    — 50+ indicators from price/volume history
[Compute Fundamentals]  — revenue/margins/quality metrics → fundamental_score
[Compute Valuation]     — archetype-adjusted multiples → archetype_adjusted_score
[Compute Earnings]      — beat rate, surprise %, proximity → earnings_score
[Compute Sentiment]     — GPT-4o-mini or keyword news → news_score
[Compute Catalyst]      — options PCR → catalyst_score (35/50/65)
[Compute Sector RS]     — sector ETF vs SPY 63-day RS → sector_macro_score (35/50/65)
        |
        v
[Legacy Composite Score] — compute_scores() with legacy weight buckets per horizon
                           + regime multipliers on individual sub-scores
        |
        v
[Decision Logic] — _decide_short_term / _decide_medium_term / _decide_long_term
                   (score thresholds + override gates for bad chart / bad business)
        |
        v
[Data Completeness Check] — deduct for missing data, cap/force if below thresholds
        |
        v
[Risk Management] — entry, ATR-based stop-loss, targets, position sizing
        |
        v
[Signal Profile] — build_signal_profile() → 6 human-readable labels from sub-scores
        |
        v
[Markdown Report] — full written summary
        |
        v
StockAnalysisResult JSON → Frontend

--- Signal Cards (in codebase, not yet active in production router) ---
score_all_cards() → 11 SignalCard objects (each 0-100)
compute_scores_from_signal_cards() → horizon composites via signal card weights
_decide_*_v2() → precise v2 labels (BUY_NOW_CONTINUATION, ACCUMULATE_ON_WEAKNESS, etc.)
build_signal_profile_from_cards() → profile from card scores
```
