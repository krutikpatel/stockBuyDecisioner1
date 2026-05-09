# Stock Decision Tool

A full-stack stock decision-support tool that evaluates any US-listed stock or ETF across three investment horizons and returns a structured **Buy / Wait / Avoid** recommendation — with scoring, entry/exit plans, risk management, and a full markdown report.

> **Disclaimer:** This is a decision-support tool, not financial advice. Always verify important information before investing.

---

## What It Does

Enter a ticker symbol and choose a risk profile. The tool:

1. Fetches live market, fundamental, valuation, earnings, news, and options data via [yfinance](https://github.com/ranaroussi/yfinance)
2. Computes **55+ technical indicators** — EMAs, SMAs, RSI, MACD, ADX, Stochastic RSI, Bollinger Bands, ATR, VWAP, OBV, A/D Line, CMF, performance periods (1W–5Y), range distances, drawdown metrics, and more
3. Fetches **expanded fundamental data** — multi-period EPS/sales growth (TTM/3Y/5Y), ownership (insider, institutional, short float), ROA/ROIC/ROE, analyst targets, and valuation ratios (EV/Sales, P/Book, P/Cash)
4. Scores **11 signal cards** (Momentum, Trend, Entry Timing, Volume/Accumulation, Volatility/Risk, Relative Strength, Growth, Valuation, Quality, Ownership, Catalyst), each 0–100
5. Applies **horizon-specific signal card weights** to produce a composite score per time frame
6. Outputs a **per-horizon decision label** from horizon-specific label sets (short/medium/long each have their own 4–5 labels)
7. Generates an entry plan, exit plan, stop-loss level, risk/reward ratio, and position sizing suggestion
8. Classifies news sentiment using **OpenAI gpt-4o-mini** (falls back to keyword-based classifier if no API key)
9. Generates a full Markdown report including signal cards section

### Three Horizons

| Horizon | Time Frame | Key Drivers |
|---------|-----------|-------------|
| Short-term | Days to 4 weeks | Technical setup, momentum, volume, catalyst |
| Medium-term | 1–6 months | Earnings, guidance, fundamental trend |
| Long-term | 1–5+ years | Business quality, FCF, valuation, balance sheet |

### 11 Signal Cards

Each card scores 0–100 and carries a label (VERY_BEARISH → VERY_BULLISH):

| Card | What It Measures |
|------|-----------------|
| Momentum | Short-term price momentum: weekly/monthly returns, MACD, RSI slope |
| Trend | Medium-term trend strength: SMA position, slopes, ADX |
| Entry Timing | Optimal entry setup: RSI zone, VWAP support, not extended |
| Volume/Accumulation | Buying/selling pressure: OBV, A/D Line, CMF, volume ratios |
| Volatility/Risk | Risk profile: ATR%, drawdown, beta, weekly/monthly volatility |
| Relative Strength | Outperformance vs SPY, QQQ, sector; return percentile ranks |
| Growth | Revenue/EPS growth acceleration across TTM/3Y/5Y timeframes |
| Valuation | Price vs fair value across P/E, PEG, P/S, EV/EBITDA, EV/Sales |
| Quality | Profitability quality: margins, ROE, ROIC, ROA, balance sheet |
| Ownership | Insider/institutional activity, short float, analyst sentiment |
| Catalyst | Near-term catalysts: news score, analyst target, earnings proximity |

### Decision Outputs

**Short-term:** `BUY_NOW_MOMENTUM` | `BUY_STARTER_STRONG_BUT_EXTENDED` | `WAIT_FOR_PULLBACK` | `AVOID_BAD_CHART`

**Medium-term:** `BUY_NOW` | `BUY_STARTER` | `BUY_ON_PULLBACK` | `WATCHLIST_NEEDS_CONFIRMATION` | `AVOID_BAD_BUSINESS`

**Long-term:** `BUY_NOW_LONG_TERM` | `ACCUMULATE_ON_WEAKNESS` | `WATCHLIST_VALUATION_TOO_RICH` | `AVOID_LONG_TERM`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, uvicorn |
| Data | yfinance (price, fundamentals, earnings, options, news) |
| Technical Indicators | pandas-ta (RSI, MACD, ATR, SMAs) |
| News Sentiment | OpenAI gpt-4o-mini (keyword fallback) |
| Caching | cachetools TTLCache (15 min price, 24 h fundamentals) |
| Retry Logic | tenacity (exponential backoff on yfinance 429s) |
| Frontend | React 18 + TypeScript, Vite |
| Styling | Tailwind CSS v4 |
| Charts | recharts |
| Markdown Rendering | react-markdown |

---

## Project Structure

```
.
├── backend/
│   ├── algo_config.json            # Centralized algorithm parameters (all tunable values)
│   ├── ALGO_PARAMS.md              # Parameter catalog with descriptions and effects
│   ├── ALGO_PARAMS_VALUES.md       # Parameter values reference
│   ├── app/
│   │   ├── algo_config.py          # AlgoConfig loader — singleton + injection pattern
│   │   ├── providers/          # Data fetching (yfinance wrappers)
│   │   │   ├── market_data_provider.py
│   │   │   ├── fundamental_provider.py
│   │   │   ├── earnings_provider.py
│   │   │   ├── news_provider.py
│   │   │   └── options_provider.py
│   │   ├── services/           # Analysis and scoring logic
│   │   │   ├── technical_analysis_service.py
│   │   │   ├── fundamental_analysis_service.py
│   │   │   ├── valuation_analysis_service.py
│   │   │   ├── news_sentiment_service.py
│   │   │   ├── scoring_service.py
│   │   │   ├── recommendation_service.py
│   │   │   ├── risk_management_service.py
│   │   │   └── markdown_report_service.py
│   │   ├── models/             # Pydantic models
│   │   ├── cache/              # TTLCache manager
│   │   ├── routers/            # FastAPI route handlers
│   │   │   └── stock.py        # POST /api/stocks/analyze
│   │   ├── config.py
│   │   └── main.py
│   ├── tests/                  # 768 unit tests
│   │   ├── test_technical_analysis.py          # 38 tests
│   │   ├── test_fundamental_analysis.py        # 32 tests
│   │   ├── test_earnings_analysis.py           # 29 tests
│   │   ├── test_scoring_recommendation.py      # 53 tests
│   │   ├── test_algo_config.py                 # AlgoConfig loader + all 12 sections
│   │   ├── test_algo_config_technical.py       # Technical params via AlgoConfig
│   │   ├── test_algo_config_signal_cards.py    # Signal card thresholds via AlgoConfig
│   │   ├── test_algo_config_recommendation.py  # Decision logic via AlgoConfig
│   │   ├── test_algo_config_risk_management.py # Risk sizing via AlgoConfig
│   │   ├── test_algo_config_scoring.py         # Scoring weights via AlgoConfig
│   │   ├── test_algo_config_market_regime.py   # Regime thresholds via AlgoConfig
│   │   ├── test_algo_config_stock_archetype.py # Archetype thresholds via AlgoConfig
│   │   ├── test_algo_config_data_completeness.py # Completeness deductions via AlgoConfig
│   │   └── test_algo_config_valuation.py       # Valuation thresholds via AlgoConfig
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── pages/Dashboard.tsx       # Main page
        ├── components/
        │   ├── RecommendationCard.tsx
        │   ├── ScoreBreakdown.tsx
        │   ├── TechnicalChart.tsx
        │   ├── NewsSection.tsx
        │   ├── DataWarnings.tsx
        │   └── MarkdownReport.tsx
        ├── api/stockApi.ts
        └── types/stock.ts
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **OpenAI API key** (optional — news sentiment works without it via keyword fallback)

---

## Setup & Installation

### 1. Clone and navigate

```bash
cd stockButDecisionMaker/usingGptStrategy
```

### 2. Backend setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Edit `backend/.env`:

```env
OPENAI_API_KEY=sk-...            # Optional — enables LLM news sentiment
CACHE_TTL_PRICE_SECONDS=900      # How long to cache price data (default: 15 min)
CACHE_TTL_FUNDAMENTALS_SECONDS=86400  # How long to cache fundamentals (default: 24 h)
LOG_LEVEL=INFO
```

> If `OPENAI_API_KEY` is left empty, news sentiment falls back to a keyword-based classifier automatically. No setup required.

### 3. Frontend setup

```bash
cd ../frontend
npm install
```

---

## Running the Application

Open **two terminals**.

**Terminal 1 — Backend:**

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

> The frontend proxies `/api` requests to the backend automatically — no CORS configuration needed.

---

## Using the Tool

1. **Enter a ticker** in the search box (e.g. `AAPL`, `NVDA`, `SPY`)
2. **Select a risk profile**: Conservative, Moderate, or Aggressive
3. **Click Analyze** — analysis takes 10–30 seconds on first run (yfinance fetches live data)
4. Review the results:
   - **Price header** — current price, 52-week range, period returns, beta, market cap
   - **Data Quality Warnings** — flags for missing data (earnings dates, peer comparison, etc.)
   - **Signal Profile** — 6 color-coded signal dimensions (Momentum, Growth, Valuation, Entry Timing, Sentiment, Risk/Reward)
   - **Signal Cards** — 11 expandable cards with score gauges, BULLISH/BEARISH labels, and top factors
   - **Recommendation Cards** — one per horizon with per-horizon decision label, score, entry/exit plan
   - **Performance Table** — 1W/1M/3M/6M/YTD/1Y/3Y/5Y returns + max drawdown
   - **Score Breakdown** — bar chart of each scoring dimension
   - **Technical Analysis** — moving averages, RSI, MACD, volume trend, support/resistance levels
   - **Fundamental Quality** — revenue growth, margins, FCF, ROE/ROIC/ROA, quick ratio, dividends
   - **Valuation** — P/E, PEG, EV/EBITDA, EV/Sales, P/Book, P/Cash, analyst target distance
   - **Ownership** — insider/institutional ownership & transactions, short float, analyst rec
   - **Volume & Accumulation** — OBV, A/D trend, CMF, VWAP deviation, volume ratios
   - **Earnings** — beat rate, average EPS surprise, upcoming earnings warning
   - **News & Sentiment** — classified news headlines with sentiment badges
   - **Full Markdown Report** — collapsible structured report with signal cards section

---

## API Reference

The backend exposes a REST API. You can call it directly without the frontend.

### Analyze a stock

```http
POST /api/stocks/analyze
Content-Type: application/json
```

**Request body:**

```json
{
  "ticker": "NVDA",
  "horizons": ["short_term", "medium_term", "long_term"],
  "risk_profile": "moderate",
  "max_position_percent": 5,
  "max_loss_percent": 8
}
```

| Field | Type | Required | Default | Options |
|-------|------|----------|---------|---------|
| `ticker` | string | Yes | — | Any US-listed ticker |
| `horizons` | string[] | No | all three | `short_term`, `medium_term`, `long_term` |
| `risk_profile` | string | No | `moderate` | `conservative`, `moderate`, `aggressive` |
| `max_position_percent` | float | No | null | Position size cap (%) |
| `max_loss_percent` | float | No | null | Max acceptable loss (%) |

**Example response (abbreviated):**

```json
{
  "ticker": "NVDA",
  "generated_at": "2026-05-04T23:47:00Z",
  "current_price": 123.45,
  "data_quality": {
    "score": 85,
    "warnings": ["Peer valuation comparison unavailable."]
  },
  "recommendations": [
    {
      "horizon": "short_term",
      "decision": "WAIT_FOR_PULLBACK",
      "score": 72,
      "confidence": "medium_high",
      "summary": "Good momentum but price extended above moving averages.",
      "bullish_factors": ["Strong uptrend: price above 50MA and 200MA", "RSI at 62.3 — healthy momentum"],
      "bearish_factors": ["Stock is extended above key moving averages"],
      "entry_plan": { "preferred_entry": 118.50, "avoid_above": 128.00 },
      "exit_plan": { "stop_loss": 112.00, "first_target": 135.00 },
      "risk_reward": { "downside_percent": 5.5, "upside_percent": 13.9, "ratio": 2.5 },
      "position_sizing": { "suggested_starter_pct_of_full": 25, "max_portfolio_allocation_pct": 5.0 }
    }
  ],
  "markdown_report": "# Stock Decision Report: NVDA\n..."
}
```

### Additional endpoints

```http
GET /api/stocks/{ticker}/report       # Returns markdown report only
GET /api/stocks/{ticker}/technicals   # Returns technical indicators only
GET /api/stocks/{ticker}/news         # Returns news + sentiment only
GET /health                           # Health check
```

**Interactive API docs:** `http://localhost:8000/docs`

---

## Running Tests

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

**768 tests across 27 suites:**

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `test_technical_analysis.py` | 38 | MAs, RSI, MACD, ATR, trend, extension, support/resistance |
| `test_technical_enhanced.py` | 57 | EMA relatives, SMA slopes, perf periods, range distances, volatility |
| `test_volume_indicators.py` | 47 | OBV, A/D, CMF, VWAP deviation, vol dry-up, up/down vol |
| `test_relative_strength.py` | 44 | RS vs QQQ, drawdown, percentile ranks, gap fill |
| `test_fundamental_analysis.py` | 32 | Revenue/EPS growth, margins, FCF, debt, ROE, archetype-adj valuation |
| `test_fundamental_enhanced.py` | 43 | Multi-period growth, ownership, ROA, quick ratio, analyst data |
| `test_earnings_analysis.py` | 29 | Beat rate, EPS surprise, KeyError handling, news sentiment |
| `test_scoring_recommendation.py` | 53 | Weight integrity, composite scoring, all decision rules, risk/reward |
| `test_stock_archetype.py` | 19 | All 8 archetype classifications |
| `test_market_regime.py` | 18 | All 6 regime classifications |
| `test_data_completeness.py` | 16 | Completeness scoring, confidence capping |
| `test_signal_profile.py` | 22 | 6 profile dimensions, label thresholds |
| `test_signal_card_models.py` | 38 | SignalCard Pydantic models, label thresholds, serialization |
| `test_signal_card_service.py` | 52 | All 11 signal card scorers — high/low/missing data scenarios |
| `test_revised_scoring.py` | 19 | Signal card weights, new per-horizon decision labels |
| `test_risk_report_updates.py` | 13 | Risk management, signal profile from cards, markdown report |
| `test_backtest_metrics.py` | 14 | by_regime, by_archetype, portfolio simulation |
| `test_improvements3.py` | 102 | New labels, gates, ATR sizing, regime thresholds |
| `test_algo_config.py` | — | AlgoConfig loader: from_file, from_dict, env override, section validation |
| `test_algo_config_technical.py` | — | Technical indicator params injected via AlgoConfig |
| `test_algo_config_signal_cards.py` | — | Signal card thresholds injected via AlgoConfig |
| `test_algo_config_recommendation.py` | — | Decision logic gates injected via AlgoConfig |
| `test_algo_config_risk_management.py` | — | Position sizing and ATR multipliers via AlgoConfig |
| `test_algo_config_scoring.py` | — | Scoring weights injected via AlgoConfig |
| `test_algo_config_market_regime.py` | — | VIX thresholds and regime weights via AlgoConfig |
| `test_algo_config_stock_archetype.py` | — | Archetype classification thresholds via AlgoConfig |
| `test_algo_config_data_completeness.py` | — | Completeness deductions and caps via AlgoConfig |

**Frontend tests (Vitest):**

```bash
cd frontend
npm test
```

36 tests: `SignalCard.test.tsx` (14) + `DataPanelUpdates.test.tsx` (22)

---

## Scoring System

Composite scores are derived from **11 signal card scores**, weighted per horizon:

### Short-term signal card weights

| Signal Card | Weight |
|------------|--------|
| Momentum | 25% |
| Volume/Accumulation | 20% |
| Entry Timing | 20% |
| Relative Strength | 15% |
| Volatility/Risk | 10% |
| Catalyst | 10% |

### Medium-term signal card weights

| Signal Card | Weight |
|------------|--------|
| Trend | 20% |
| Growth | 20% |
| Relative Strength | 15% |
| Volume/Accumulation | 15% |
| Valuation | 10% |
| Quality | 10% |
| Catalyst | 10% |

### Long-term signal card weights

| Signal Card | Weight |
|------------|--------|
| Growth | 20% |
| Quality | 20% |
| Valuation | 15% |
| Ownership | 15% |
| Trend | 10% |
| Catalyst | 10% |
| Volatility/Risk | 5% |
| Momentum | 5% |

---

## Known Limitations

| Limitation | Impact | Status |
|-----------|--------|--------|
| yfinance `ticker.news` is limited | Sparse news coverage for some tickers | Flagged in UI |
| yfinance `earnings_dates` has known bugs for some tickers | Next earnings date may be missing | Handled gracefully — returns null |
| yfinance rate limits (HTTP 429) | Slow first load; retries automatically | Exponential backoff + 15-min cache |
| Peer valuation comparison not available via yfinance | Can't compare P/E vs sector peers | Flagged in data quality warnings |
| PEG ratio and P/FCF calculated, not provided directly | Approximation if growth data missing | Calculated from available fields |
| News coverage via yfinance is limited | May miss key news items | Flagged as "coverage limited" in UI |
| Sector/macro score is static (50) | Does not reflect current macro conditions | Can be wired to a sector ETF data source later |
| 5-year growth rates often null | yfinance `ticker.info` fields inconsistently available | Gracefully excluded from scoring; flagged as missing data |
| Return percentile ranks are self-relative | Ranks stock's return vs its own 252-day window | Not a true cross-sectional rank vs all US stocks |
| Anchored VWAP requires earnings date | Best-effort; null when earnings date unavailable | Falls back to null with no impact on scoring |

---

## Adding a Real News Data Source

To replace yfinance's limited news with a proper news API:

1. Create a new provider in `backend/app/providers/` (e.g. `newsapi_provider.py`)
2. Implement the same interface as `news_provider.py` — return `list[NewsItem]`
3. Update `backend/app/routers/stock.py` to call your new provider instead of `get_news_items()`

The sentiment service (`news_sentiment_service.py`) is provider-agnostic — it only receives `list[NewsItem]` and classifies them.

---

## Extending the Data Provider

All data providers follow the same pattern: fetch → cache → return typed model. To swap in a paid data source (e.g. Polygon.io, Alpha Vantage):

1. Implement the same return types (`MarketData`, `FundamentalData`, etc.) in a new provider file
2. Replace the provider import in `routers/stock.py`

The analysis and scoring pipeline is completely decoupled from the data source.

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `""` | OpenAI API key for LLM news sentiment. Leave empty to use keyword fallback |
| `CACHE_TTL_PRICE_SECONDS` | `900` | Price data cache TTL (15 min) |
| `CACHE_TTL_FUNDAMENTALS_SECONDS` | `86400` | Fundamentals cache TTL (24 h) |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `ALGO_CONFIG_PATH` | `backend/algo_config.json` | Path to algorithm parameters JSON. Override to load a custom config file |

---

## Customizing Algorithm Parameters

All tunable algorithm parameters — RSI periods, scoring thresholds, decision gate values, position sizing multipliers, etc. — are defined in a single file:

```
backend/algo_config.json
```

This is a structured JSON with 12 top-level sections:

| Section | What It Controls |
|---------|-----------------|
| `technical_indicators` | MA/EMA periods, RSI, MACD, ATR, ADX, Stochastic RSI, Bollinger, OBV/CMF/VWAP windows |
| `technical_scoring` | Score bonus/penalty thresholds for each technical condition |
| `extension_detection` | SMA20/50/200 extension percentage thresholds |
| `stock_archetype` | Classification rules for the 8 stock archetypes |
| `market_regime` | VIX thresholds, SPY/QQQ MA conditions, regime confidence levels |
| `regime_scoring` | Score multipliers applied per market regime |
| `scoring` | Signal card weights per horizon (short/medium/long) |
| `signal_cards` | Internal scoring thresholds for each of the 11 signal cards |
| `decision_logic` | Gate values for short/medium/long-term decision labels |
| `data_completeness` | Completeness deductions and confidence cap thresholds |
| `risk_management` | ATR multipliers, position sizing factors, entry/exit offsets |
| `valuation` | Archetype-adjusted valuation score thresholds |

### Usage patterns

**Default (production):** Services auto-load `algo_config.json` via a module-level singleton:
```python
from app.algo_config import get_algo_config
cfg = get_algo_config()
period = cfg.technical_indicators["rsi_period"]
```

**Override for experiments:** Pass a custom config to any service function:
```python
from app.algo_config import AlgoConfig
cfg = AlgoConfig.from_dict({"technical_indicators": {"rsi_period": 10}, ...})
result = compute_technicals(df, spy_df, algo_config=cfg)
```

**Override via environment variable:**
```bash
ALGO_CONFIG_PATH=/path/to/custom.json python -m backtest.run_backtest ...
```

See `backend/ALGO_PARAMS.md` for a full parameter catalog with descriptions and sensitivity notes.
