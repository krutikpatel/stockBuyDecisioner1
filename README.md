# Stock Decision Tool

A full-stack stock decision-support tool that evaluates any US-listed stock or ETF across three investment horizons and returns a structured **Buy / Wait / Avoid** recommendation — with scoring, entry/exit plans, risk management, and a full markdown report.

> **Disclaimer:** This is a decision-support tool, not financial advice. Always verify important information before investing.

---

## What It Does

Enter a ticker symbol and choose a risk profile. The tool:

1. Fetches live market, fundamental, valuation, earnings, news, and options data via [yfinance](https://github.com/ranaroussi/yfinance)
2. Computes 15+ technical indicators (moving averages, RSI, MACD, ATR, support/resistance, relative strength)
3. Scores each dimension (Technical, Fundamental, Valuation, Earnings, News/Sentiment) on a 0–100 scale
4. Applies **horizon-specific weights** to produce a composite score for each time frame
5. Applies decision rules to output one of: `BUY_NOW`, `BUY_STARTER`, `WAIT_FOR_PULLBACK`, `BUY_ON_BREAKOUT`, `WATCHLIST`, or `AVOID`
6. Generates an entry plan, exit plan, stop-loss level, risk/reward ratio, and position sizing suggestion
7. Classifies news sentiment using **OpenAI gpt-4o-mini** (falls back to keyword-based classifier if no API key)
8. Generates a full Markdown report

### Three Horizons

| Horizon | Time Frame | Key Drivers |
|---------|-----------|-------------|
| Short-term | Days to 4 weeks | Technical setup, momentum, volume, catalyst |
| Medium-term | 1–6 months | Earnings, guidance, fundamental trend |
| Long-term | 1–5+ years | Business quality, FCF, valuation, balance sheet |

### Decision Outputs

| Decision | Badge Color | Meaning |
|----------|-------------|---------|
| `BUY_NOW` | Green | Strong setup, favorable risk/reward |
| `BUY_STARTER` | Emerald | Good thesis, imperfect timing — size in partially |
| `WAIT_FOR_PULLBACK` | Yellow | Good setup but stock is extended |
| `BUY_ON_BREAKOUT` | Blue | Strong long-term thesis, wait for confirmed breakout |
| `WATCHLIST` | Gray | Monitoring — confirmation missing |
| `AVOID` | Red | Multiple negative signals |

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
│   ├── app/
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
│   ├── tests/                  # 125 unit tests
│   │   ├── test_technical_analysis.py    # 38 tests
│   │   ├── test_fundamental_analysis.py  # 24 tests
│   │   ├── test_earnings_analysis.py     # 29 tests
│   │   └── test_scoring_recommendation.py # 34 tests
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
   - **Recommendation Cards** — one per horizon with decision badge, score, bullish/bearish factors, entry/exit plan
   - **Score Breakdown** — bar chart of each scoring dimension
   - **Technical Analysis** — moving averages, RSI, MACD, volume trend, support/resistance levels
   - **Fundamental Quality** — revenue growth, margins, FCF, debt
   - **Valuation** — P/E, PEG, EV/EBITDA, P/FCF, FCF yield
   - **Earnings** — beat rate, average EPS surprise, upcoming earnings warning
   - **News & Sentiment** — classified news headlines with sentiment badges
   - **Full Markdown Report** — collapsible structured report (great for printing/saving)

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

**125 tests across 4 suites:**

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `test_technical_analysis.py` | 38 | MAs, RSI, MACD, ATR, trend, extension, support/resistance, RS, scoring |
| `test_fundamental_analysis.py` | 24 | Revenue/EPS growth, margins, FCF, debt, ROE, PEG/P/FCF calculation |
| `test_earnings_analysis.py` | 29 | Beat rate, EPS surprise, KeyError handling, news sentiment, OpenAI mock |
| `test_scoring_recommendation.py` | 34 | Weight integrity, composite scoring, all decision rules, risk/reward |

---

## Scoring System

Each horizon uses a different weighting of the sub-scores:

### Short-term weights

| Dimension | Weight |
|-----------|--------|
| Technical | 35% |
| Catalyst / Options | 20% |
| News / Sentiment | 15% |
| Risk / Reward | 15% |
| Sector / Macro | 10% |
| Fundamental | 5% |

### Medium-term weights

| Dimension | Weight |
|-----------|--------|
| Fundamental | 25% |
| Earnings | 25% |
| Technical | 20% |
| Valuation | 15% |
| Catalyst | 10% |
| Risk / Reward | 5% |

### Long-term weights

| Dimension | Weight |
|-----------|--------|
| Fundamental | 35% |
| Valuation | 20% |
| Earnings | 15% |
| Risk / Reward | 10% |
| Sector / Macro | 10% |
| Technical | 5% |
| News / Sentiment | 5% |

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
