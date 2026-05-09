````md
# Coding Agent Instructions: Stock Buy Decision Tool

## 0. Clarifying Questions Before Implementation

Ask the user these before final implementation decisions:

1. **Tech stack preference**
   - Should this be a web app, CLI tool, mobile app, or backend API first?
   - Preferred stack: React + Spring Boot, React + Python/FastAPI, Next.js full-stack, or something else?

2. **Data source**
   - Which stock data provider will be used?
   - Possible options: Yahoo Finance/yfinance, Alpha Vantage, Polygon.io, Finnhub, Financial Modeling Prep, IEX Cloud, SEC filings, NewsAPI, Benzinga, etc.

3. **Market coverage**
   - US stocks only?
   - ETFs?
   - Crypto?
   - International stocks?

4. **Time horizon**
   - Should the tool always evaluate all 3 horizons?
     - Short-term: days to 4 weeks
     - Medium-term: 1 to 6 months
     - Long-term: 1 to 5+ years

5. **User risk profile**
   - Conservative, moderate, aggressive?
   - Maximum loss tolerance per trade?
   - Maximum portfolio allocation per stock?

6. **Output style**
   - Should output be:
     - Markdown report
     - Scorecard dashboard
     - JSON API response
     - Buy/wait/avoid recommendation
     - All of the above?

7. **Recommendation strictness**
   - Should the tool be conservative and avoid unclear setups?
   - Or should it allow speculative starter positions?

8. **Options data**
   - Should the tool include options data such as implied volatility, expected move, put/call ratio, and unusual options activity?

9. **News analysis**
   - Should news sentiment be simple keyword-based first, or use an LLM-based summarizer/sentiment engine?

10. **Portfolio context**
   - Should the tool analyze one stock independently?
   - Or should it consider the user’s existing holdings, cash, sector exposure, and position size?

---

# 1. Product Goal

Build a real stock decision-support tool that helps a user decide:

- Whether to buy a stock
- Whether to wait for a better entry
- Whether to buy a small starter position
- Whether to avoid the stock
- What data supports the decision
- What price levels matter
- What risks invalidate the thesis

The tool must evaluate the stock across:

1. Short-term trading horizon
2. Medium-term swing/investment horizon
3. Long-term investing horizon

The tool must not blindly output “buy” or “sell.”  
It must provide reasoning, score breakdown, risk factors, entry plan, exit plan, and data gaps.

---

# 2. Default Assumptions

Unless user specifies otherwise, implement with these assumptions:

```md
Application type: Web app + backend API
Frontend: React + TypeScript
Backend: Python FastAPI or Java Spring Boot
Data provider abstraction: yes
Initial data provider: pluggable mock provider + real provider later
Output format: JSON + Markdown report
Market: US-listed stocks and ETFs
Analysis horizons: short-term, medium-term, long-term
Recommendation types: Buy Now, Buy Starter, Wait for Pullback, Watchlist, Avoid
````

---

# 3. Core User Flow

```md
1. User enters ticker symbol.
2. User selects time horizon:
   - Short-term
   - Medium-term
   - Long-term
   - All
3. User selects risk profile:
   - Conservative
   - Moderate
   - Aggressive
4. User optionally enters:
   - Current holdings
   - Intended position size
   - Entry price
   - Target allocation
   - Max acceptable loss
5. System fetches stock data.
6. System fetches company/news data.
7. System computes indicators and scores.
8. System generates:
   - Technical score
   - Fundamental score
   - Valuation score
   - Catalyst score
   - Sentiment score
   - Risk score
   - Final horizon-specific recommendation
9. System shows:
   - Buy/wait/avoid decision
   - Explanation
   - Key levels
   - Entry plan
   - Exit plan
   - Invalidation level
   - Missing data warnings
```

---

# 4. Main Features to Implement

## 4.1 Ticker Analysis

The system should accept a ticker and return a complete analysis.

Example request:

```json
{
  "ticker": "NVDA",
  "riskProfile": "moderate",
  "horizons": ["short_term", "medium_term", "long_term"],
  "maxPositionPercent": 5,
  "maxLossPercent": 8
}
```

Example high-level response:

```json
{
  "ticker": "NVDA",
  "currentPrice": 123.45,
  "recommendations": {
    "shortTerm": {
      "decision": "WAIT_FOR_PULLBACK",
      "score": 72,
      "confidence": "medium",
      "summary": "Strong trend, but price is extended above key moving averages."
    },
    "mediumTerm": {
      "decision": "BUY_STARTER",
      "score": 78,
      "confidence": "medium_high",
      "summary": "Fundamentals and earnings momentum are strong, but entry should be staged."
    },
    "longTerm": {
      "decision": "BUY_ON_WEAKNESS",
      "score": 82,
      "confidence": "high",
      "summary": "High-quality company with strong secular tailwinds, but valuation needs discipline."
    }
  }
}
```

---

# 5. Data to Fetch

## 5.1 Stock Market Data

Create a `MarketDataProvider` interface.

It should fetch:

```md
- Current price
- Previous close
- Open
- High
- Low
- Daily volume
- Average 30-day volume
- Market cap
- 52-week high
- 52-week low
- Historical daily OHLCV data
- Historical weekly OHLCV data
- 1-month performance
- 3-month performance
- 6-month performance
- 1-year performance
- YTD performance
- Beta
```

Required historical ranges:

```md
Short-term: at least 6 months daily data
Medium-term: at least 1 year daily data
Long-term: at least 5 years monthly/weekly data if available
```

---

## 5.2 Technical Indicator Data

Calculate internally:

```md
- 10-day moving average
- 20-day moving average
- 50-day moving average
- 100-day moving average
- 200-day moving average
- RSI 14
- MACD
- MACD signal
- MACD histogram
- Average true range
- Relative strength vs S&P 500
- Relative strength vs sector ETF
- Support levels
- Resistance levels
- Breakout levels
- Recent swing highs
- Recent swing lows
- Volume trend
- Accumulation/distribution behavior
```

---

## 5.3 Fundamental Data

Create a `FundamentalDataProvider` interface.

Fetch:

```md
- Revenue TTM
- Revenue growth YoY
- Revenue growth QoQ
- EPS TTM
- EPS growth YoY
- EPS growth QoQ
- Gross margin
- Operating margin
- Net margin
- EBITDA margin
- Free cash flow
- Free cash flow growth
- Free cash flow margin
- Cash
- Total debt
- Net debt
- Current ratio
- Debt-to-equity
- Interest coverage
- Share count
- Share count growth/dilution
- Return on equity
- Return on invested capital
```

---

## 5.4 Valuation Data

Fetch or calculate:

```md
- Trailing P/E
- Forward P/E
- PEG ratio
- Price-to-sales
- EV/sales
- EV/EBITDA
- Price-to-free-cash-flow
- Free cash flow yield
- Valuation compared to 5-year average
- Valuation compared to sector median
- Valuation compared to major peers
```

If peer data is unavailable, return:

```json
{
  "peerComparisonAvailable": false,
  "warning": "Peer comparison data unavailable."
}
```

---

## 5.5 Earnings Data

Create an `EarningsDataProvider`.

Fetch:

```md
- Last earnings date
- Next earnings date
- Last reported EPS
- Expected EPS
- EPS surprise
- Last reported revenue
- Expected revenue
- Revenue surprise
- Guidance raise/cut/maintained
- Last 4 to 8 earnings reactions
- Analyst estimate revisions
- Forward revenue estimates
- Forward EPS estimates
```

Important derived metrics:

```md
- Average post-earnings move
- Beat/miss consistency
- Guidance trend
- Estimate revision trend
- Whether next earnings is within 30 days
```

---

## 5.6 News and Company Event Data

Create a `NewsDataProvider`.

Fetch:

```md
- Company news from last 30 days
- Company news from last 90 days
- Analyst upgrades
- Analyst downgrades
- Price target changes
- Product launch news
- Partnership news
- Customer win news
- Management change news
- Layoff news
- Lawsuit/legal issue news
- Regulatory issue news
- M&A news
- Competitor news
- Sector news
```

For each news item, store:

```json
{
  "title": "string",
  "source": "string",
  "publishedAt": "datetime",
  "url": "string",
  "summary": "string",
  "sentiment": "positive | neutral | negative",
  "importance": "low | medium | high",
  "category": "earnings | analyst | product | legal | macro | sector | management | other"
}
```

---

## 5.7 Optional Options Data

Create an `OptionsDataProvider`.

Fetch if available:

```md
- Implied volatility
- Historical volatility
- Put/call ratio
- Options volume
- Open interest
- Expected move into earnings
- Unusual options activity
- Max pain
- Call/put skew
```

Use this mainly for short-term analysis.

---

# 6. Internal Domain Model

Implement these core models.

```ts
type TimeHorizon = "short_term" | "medium_term" | "long_term";

type RecommendationDecision =
  | "BUY_NOW"
  | "BUY_STARTER"
  | "WAIT_FOR_PULLBACK"
  | "BUY_ON_BREAKOUT"
  | "WATCHLIST"
  | "AVOID";

type RiskProfile = "conservative" | "moderate" | "aggressive";

interface StockAnalysisRequest {
  ticker: string;
  horizons: TimeHorizon[];
  riskProfile: RiskProfile;
  maxPositionPercent?: number;
  maxLossPercent?: number;
  currentHoldingShares?: number;
  averageCost?: number;
}

interface StockAnalysisResult {
  ticker: string;
  generatedAt: string;
  currentPrice: number;
  dataQuality: DataQualityReport;
  marketData: MarketDataSummary;
  technicals: TechnicalSummary;
  fundamentals: FundamentalSummary;
  valuation: ValuationSummary;
  earnings: EarningsSummary;
  news: NewsSummary;
  recommendations: HorizonRecommendation[];
  markdownReport: string;
}
```

---

# 7. Scoring System

Use a 0–100 score for each category.

Core scoring categories:

```md
1. Technical score
2. Fundamental score
3. Valuation score
4. Earnings score
5. Catalyst score
6. News/sentiment score
7. Sector/macro score
8. Risk/reward score
```

Each horizon should use different weights.

---

## 7.1 Short-Term Weighting

Short-term focuses on chart, momentum, volume, catalyst, and risk.

```json
{
  "technical": 35,
  "catalyst": 20,
  "newsSentiment": 15,
  "riskReward": 15,
  "sectorMacro": 10,
  "fundamental": 5
}
```

Short-term recommendation logic:

```md
BUY_NOW if:
- Score >= 80
- Price is above 20-day and 50-day moving averages
- Volume confirms strength
- RSI is not extremely overbought
- Clear support is nearby
- Risk/reward is at least 2:1

BUY_STARTER if:
- Score 70–79
- Setup is promising
- But stock is slightly extended or catalyst risk exists

WAIT_FOR_PULLBACK if:
- Score >= 65
- Fundamentals/news are good
- But price is far above 20-day or 50-day moving average

AVOID if:
- Score < 50
- Price breaks key support
- Bad news or earnings risk is high
```

---

## 7.2 Medium-Term Weighting

Medium-term focuses on earnings, guidance, sector trend, and technical trend.

```json
{
  "fundamental": 25,
  "earnings": 25,
  "technical": 20,
  "valuation": 15,
  "catalyst": 10,
  "riskReward": 5
}
```

Medium-term recommendation logic:

```md
BUY_NOW if:
- Score >= 82
- Earnings estimates are rising
- Guidance is strong
- Price is in healthy uptrend
- Valuation is acceptable

BUY_STARTER if:
- Score 72–81
- Thesis is strong
- But entry timing is imperfect

WAIT_FOR_PULLBACK if:
- Score >= 68
- Business is strong
- But stock is technically extended

WATCHLIST if:
- Score 55–67
- Some positives exist
- But confirmation is missing

AVOID if:
- Score < 55
- Revenue growth is slowing
- Margins are compressing
- Guidance is weak
```

---

## 7.3 Long-Term Weighting

Long-term focuses on business quality, moat, free cash flow, balance sheet, and valuation.

```json
{
  "fundamental": 35,
  "valuation": 20,
  "earnings": 15,
  "riskReward": 10,
  "sectorMacro": 10,
  "technical": 5,
  "newsSentiment": 5
}
```

Long-term recommendation logic:

```md
BUY_NOW if:
- Score >= 85
- Business quality is excellent
- Valuation is reasonable
- Balance sheet is strong
- Long-term growth is durable

BUY_STARTER if:
- Score 75–84
- Business quality is strong
- But valuation is somewhat expensive

BUY_ON_WEAKNESS if:
- Score >= 75
- Long-term thesis is strong
- But current valuation or technical extension is a concern

WATCHLIST if:
- Score 60–74
- Company is promising
- But valuation or fundamentals need improvement

AVOID if:
- Score < 60
- Business quality is weak
- Balance sheet is risky
- Long-term thesis is unclear
```

---

# 8. Technical Analysis Rules

Implement these rules.

## 8.1 Trend Classification

```md
Strong uptrend:
- Price > 50-day MA
- Price > 200-day MA
- 50-day MA > 200-day MA
- Higher highs and higher lows

Weak uptrend:
- Price > 200-day MA
- But price is near or below 50-day MA

Sideways:
- Price moving between support and resistance
- Moving averages flat

Downtrend:
- Price < 50-day MA
- Price < 200-day MA
- Lower highs and lower lows
```

---

## 8.2 Extension Detection

Stock is extended if:

```md
- Price is more than 8–10% above 20-day MA, or
- Price is more than 15–20% above 50-day MA, or
- RSI > 75, or
- Stock has moved up sharply for several days with declining volume
```

When extended:

```md
- Do not recommend full position
- Prefer WAIT_FOR_PULLBACK or BUY_STARTER
```

---

## 8.3 Pullback Quality

Healthy pullback if:

```md
- Pullback volume is below average
- Price holds 20-day or 50-day moving average
- RSI resets to 40–55
- No major negative news
- Sector remains strong
```

Unhealthy pullback if:

```md
- Price falls on high volume
- Price breaks 50-day MA
- Price breaks previous support
- Negative news appears
- Sector is weak
```

---

## 8.4 Breakout Quality

Strong breakout if:

```md
- Price closes above resistance
- Volume is 30–50% above average
- Stock outperforms S&P 500
- Stock outperforms sector ETF
- No immediate overhead resistance
```

Weak breakout if:

```md
- Breakout happens on low volume
- Price reverses below breakout level
- Market is weak
- Sector is weak
```

---

# 9. Fundamental Analysis Rules

## 9.1 Positive Fundamental Signals

Score higher if:

```md
- Revenue growth is accelerating
- EPS growth is positive and accelerating
- Gross margin is stable or expanding
- Operating margin is expanding
- Free cash flow is positive and growing
- Balance sheet has more cash than debt
- Share count is stable or declining
- Guidance is raised
- Analyst estimates are revised upward
```

---

## 9.2 Negative Fundamental Signals

Score lower if:

```md
- Revenue growth is slowing
- EPS growth is negative
- Margins are compressing
- Free cash flow is negative
- Debt is rising quickly
- Share count is increasing materially
- Guidance is cut
- Analysts reduce estimates
```

---

# 10. Valuation Rules

## 10.1 Valuation Is Attractive If

```md
- Forward P/E is below historical average
- PEG ratio is near or below 1.5
- Free cash flow yield is attractive
- Price-to-sales is reasonable versus growth
- Valuation is lower than peers despite similar or better growth
```

---

## 10.2 Valuation Is Risky If

```md
- Forward P/E is much higher than historical average
- PEG ratio is high
- Price-to-sales is high while growth is slowing
- Free cash flow yield is very low
- Company must execute perfectly to justify price
```

---

# 11. News and Sentiment Rules

## 11.1 Positive News

Classify as positive if news includes:

```md
- Raised guidance
- Major customer win
- Strong earnings
- Product launch with commercial impact
- Analyst upgrade
- Price target increase
- Partnership with major company
- Regulatory approval
- Insider buying
```

---

## 11.2 Negative News

Classify as negative if news includes:

```md
- Guidance cut
- Earnings miss
- Revenue slowdown
- Margin pressure
- Lawsuit
- Regulatory investigation
- Product failure
- Major customer loss
- Analyst downgrade due to fundamentals
- Insider selling cluster
```

---

## 11.3 Sentiment Scoring

```md
News sentiment score:
- 80–100: mostly positive high-impact news
- 60–79: mildly positive or mixed-positive news
- 40–59: neutral or mixed news
- 20–39: negative news
- 0–19: severe negative news or thesis-breaking event
```

---

# 12. Risk Management Rules

For every recommendation, generate:

```md
- Suggested entry zone
- Support level
- Resistance level
- Stop-loss/invalidation level
- Upside target
- Downside risk
- Risk/reward ratio
- Suggested position size
```

## 12.1 Position Size Logic

Default:

```md
Conservative:
- Starter: 10–20% of intended position
- Full: max 3% portfolio allocation

Moderate:
- Starter: 20–35% of intended position
- Full: max 5% portfolio allocation

Aggressive:
- Starter: 25–50% of intended position
- Full: max 8–10% portfolio allocation
```

Before earnings:

```md
- Reduce suggested position size by 30–50%
- Unless user explicitly accepts earnings gap risk
```

---

# 13. Recommendation Output

Each horizon recommendation must include:

```json
{
  "horizon": "short_term",
  "decision": "WAIT_FOR_PULLBACK",
  "score": 74,
  "confidence": "medium",
  "summary": "Strong momentum but currently extended.",
  "bullishFactors": [],
  "bearishFactors": [],
  "entryPlan": {
    "preferredEntry": 100.0,
    "starterEntry": 105.0,
    "breakoutEntry": 112.0,
    "avoidAbove": 118.0
  },
  "exitPlan": {
    "stopLoss": 96.0,
    "invalidationLevel": 94.0,
    "firstTarget": 115.0,
    "secondTarget": 125.0
  },
  "riskReward": {
    "downsidePercent": 8.5,
    "upsidePercent": 18.0,
    "ratio": 2.1
  },
  "positionSizing": {
    "suggestedStarterPercentOfFullPosition": 25,
    "maxPortfolioAllocationPercent": 5
  },
  "dataWarnings": []
}
```

---

# 14. Markdown Report Generation

Generate a Markdown report with this structure:

```md
# Stock Decision Report: [TICKER]

## Final Summary

- Short-term decision:
- Medium-term decision:
- Long-term decision:
- Overall bias:
- Confidence:
- Main reason:

---

## Current Market Data

- Current price:
- 52-week high:
- 52-week low:
- Market cap:
- 1-month return:
- 3-month return:
- 6-month return:
- 1-year return:
- YTD return:

---

## Technical Setup

- Trend:
- 20-day MA:
- 50-day MA:
- 200-day MA:
- RSI:
- MACD:
- Volume trend:
- Support:
- Resistance:
- Is stock extended? Yes/No

---

## Fundamental Quality

- Revenue growth:
- EPS growth:
- Gross margin:
- Operating margin:
- Free cash flow:
- Debt:
- Cash:
- Share count trend:
- Guidance:

---

## Valuation

- Forward P/E:
- PEG:
- Price/sales:
- EV/EBITDA:
- Free cash flow yield:
- Compared to peers:
- Compared to historical average:

---

## Earnings and Catalysts

- Last earnings date:
- Next earnings date:
- EPS surprise:
- Revenue surprise:
- Guidance trend:
- Analyst estimate revisions:
- Upcoming catalysts:

---

## News and Sentiment

### Positive News

- Item 1
- Item 2

### Negative News

- Item 1
- Item 2

### Sentiment Summary

- Overall sentiment:

---

## Short-Term Recommendation

- Decision:
- Score:
- Reason:
- Buy zone:
- Wait zone:
- Stop-loss:
- Target:
- Risk/reward:

---

## Medium-Term Recommendation

- Decision:
- Score:
- Reason:
- Buy zone:
- Add-on level:
- Stop-loss/invalidation:
- Review trigger:

---

## Long-Term Recommendation

- Decision:
- Score:
- Reason:
- Accumulation zone:
- Thesis:
- Long-term risks:
- Sell/invalidation trigger:

---

## Final Action Plan

- Buy now:
- Buy starter:
- Wait for pullback:
- Avoid:
- Review after:

---

## Data Quality Warnings

- Missing data:
- Stale data:
- Low confidence areas:
```

---

# 15. UI Requirements

## 15.1 Dashboard Page

Show:

```md
- Ticker search box
- Current price card
- Final recommendation card
- Short-term score
- Medium-term score
- Long-term score
- Technical chart
- Support/resistance table
- Fundamental scorecard
- Valuation scorecard
- News sentiment section
- Entry/exit plan
```

---

## 15.2 Recommendation Cards

Each card should show:

```md
Horizon: Short-term / Medium-term / Long-term
Decision: Buy Now / Buy Starter / Wait / Watchlist / Avoid
Score: 0–100
Confidence: Low / Medium / High
Main reason:
Top bullish factors:
Top bearish factors:
Suggested action:
```

---

## 15.3 Visual Indicators

Use simple badges:

```md
BUY_NOW: Green
BUY_STARTER: Light green
WAIT_FOR_PULLBACK: Yellow
BUY_ON_BREAKOUT: Blue
WATCHLIST: Gray
AVOID: Red
```

---

# 16. Backend Architecture

Use modular services.

```md
src/
  providers/
    MarketDataProvider
    FundamentalDataProvider
    EarningsDataProvider
    NewsDataProvider
    OptionsDataProvider

  services/
    TechnicalAnalysisService
    FundamentalAnalysisService
    ValuationAnalysisService
    EarningsAnalysisService
    NewsSentimentService
    RiskManagementService
    ScoringService
    RecommendationService
    MarkdownReportService

  models/
    StockAnalysisRequest
    StockAnalysisResult
    MarketData
    TechnicalIndicators
    FundamentalData
    ValuationData
    EarningsData
    NewsItem
    Recommendation

  controllers/
    StockAnalysisController

  tests/
    technical-analysis.test
    scoring-service.test
    recommendation-service.test
    markdown-report.test
```

---

# 17. API Endpoints

## 17.1 Analyze Stock

```http
POST /api/stocks/analyze
```

Request:

```json
{
  "ticker": "MU",
  "horizons": ["short_term", "medium_term", "long_term"],
  "riskProfile": "moderate",
  "maxPositionPercent": 5,
  "maxLossPercent": 8
}
```

Response:

```json
{
  "ticker": "MU",
  "generatedAt": "2026-05-04T15:00:00Z",
  "currentPrice": 0,
  "recommendations": [],
  "markdownReport": ""
}
```

---

## 17.2 Get Markdown Report

```http
GET /api/stocks/{ticker}/report
```

---

## 17.3 Get Technical Summary

```http
GET /api/stocks/{ticker}/technicals
```

---

## 17.4 Get News Summary

```http
GET /api/stocks/{ticker}/news
```

---

# 18. Data Quality Requirements

The tool must detect and report:

```md
- Missing price data
- Stale price data
- Missing earnings data
- Missing valuation data
- Missing news data
- Incomplete technical history
- Unsupported ticker
- Low confidence due to insufficient data
```

Never hide missing data.

Example:

```json
{
  "dataQuality": {
    "score": 78,
    "warnings": [
      "Options data unavailable.",
      "Peer valuation comparison unavailable.",
      "Only 6 months of historical data available."
    ]
  }
}
```

---

# 19. Safety and Disclaimer Requirements

Every report should include:

```md
This is a decision-support tool, not financial advice.
The recommendation is based only on available data.
The user should verify important information before investing.
```

Also:

```md
- Do not guarantee returns.
- Do not say "this stock will go up."
- Say "setup is favorable" or "risk/reward is attractive."
- Always show risks.
- Always show invalidation levels.
```

---

# 20. MVP Scope

Implement MVP in this order:

## Phase 1: Core Analysis Engine

```md
- Accept ticker
- Fetch/mock price data
- Calculate moving averages
- Calculate RSI
- Calculate trend classification
- Identify basic support/resistance
- Generate technical score
```

## Phase 2: Fundamentals and Valuation

```md
- Fetch/mock fundamental data
- Calculate fundamental score
- Calculate valuation score
- Detect valuation risk
```

## Phase 3: News and Earnings

```md
- Fetch/mock earnings data
- Fetch/mock news data
- Classify news sentiment
- Detect upcoming catalyst risk
```

## Phase 4: Recommendation Engine

```md
- Combine scores using horizon-specific weights
- Generate Buy/Wait/Avoid recommendation
- Generate entry plan
- Generate exit plan
- Generate position sizing
```

## Phase 5: Frontend Dashboard

```md
- Ticker input
- Scorecards
- Recommendation cards
- Markdown report view
- Technical data table
- News summary section
```

---

# 21. Acceptance Criteria

The implementation is complete when:

```md
- User can enter a ticker.
- System returns short-term, medium-term, and long-term recommendations.
- Each recommendation includes score, decision, confidence, explanation, risks, entry plan, and exit plan.
- System identifies whether the stock is extended.
- System identifies support and resistance levels.
- System generates a Markdown report.
- System shows data-quality warnings.
- System works with mocked data even before real API integration.
- Code is modular enough to swap data providers.
- Unit tests exist for scoring and recommendation logic.
```

---

# 22. Example Coding Agent Prompt

Use this directly with a coding agent:

```md
You are a senior full-stack engineer building a stock decision-support tool.

Build an application that accepts a stock ticker and evaluates whether the user should buy now, buy a starter position, wait for a pullback, watchlist, or avoid.

The tool must evaluate the stock across three horizons:

1. Short-term: days to 4 weeks
2. Medium-term: 1 to 6 months
3. Long-term: 1 to 5+ years

Implement a modular system with the following services:

- MarketDataProvider
- FundamentalDataProvider
- EarningsDataProvider
- NewsDataProvider
- TechnicalAnalysisService
- FundamentalAnalysisService
- ValuationAnalysisService
- NewsSentimentService
- RiskManagementService
- ScoringService
- RecommendationService
- MarkdownReportService

Start with mock providers so the application works without paid APIs. Design provider interfaces so real APIs can be added later.

The system must calculate:

- Moving averages: 10, 20, 50, 100, 200
- RSI 14
- MACD
- Average volume
- Volume trend
- Trend classification
- Support and resistance levels
- Extension from moving averages
- Risk/reward ratio

The system must score:

- Technical setup
- Fundamentals
- Valuation
- Earnings
- Catalysts
- News/sentiment
- Sector/macro
- Risk/reward

Use different score weights for short-term, medium-term, and long-term recommendations.

Recommendation outputs must include:

- Decision
- Score
- Confidence
- Bullish factors
- Bearish factors
- Entry plan
- Exit plan
- Stop-loss/invalidation level
- Position sizing suggestion
- Data-quality warnings
- Markdown report

Important constraints:

- Do not provide guaranteed return predictions.
- Do not hide missing data.
- Always include risks.
- Always include invalidation levels.
- Always include a financial disclaimer.
- Make the code modular, testable, and extensible.

Build the MVP first:

1. Backend API endpoint: POST /api/stocks/analyze
2. Mock data providers
3. Technical analysis engine
4. Scoring engine
5. Recommendation engine
6. Markdown report generator
7. Basic frontend dashboard

After MVP, make it easy to plug in real data providers.
```

---

# 23. My Recommended Implementation Direction

For your background, I would build it as:

```md
Frontend:
- React + TypeScript
- Tailwind CSS
- Recharts for charts

Backend:
- Spring Boot if you want portfolio value as a Java backend engineer
- Or FastAPI if you want faster data/ML/news-analysis iteration

Best portfolio version:
- React frontend
- Spring Boot backend
- Python analysis microservice optional later
- PostgreSQL for saved analyses
- Redis for caching ticker results
- External stock/news provider abstraction
```

The most important part is not the UI.
The most impressive part is the **decision engine**:

```md
Raw data → normalized facts → indicators → scorecards → horizon-specific recommendation → markdown decision report
```

That will make this look like a real senior-level stock analysis product, not just a basic stock dashboard.
