# Finviz-Inspired Datapoint Expansion for Stock Buy Decision Tool

Finviz exposes the right categories for your tool: **Descriptive, Fundamental, Technical, News, ETF, and All** filters, plus result views like Overview, Valuation, Financial, Ownership, Performance, Technical, TA, News, Snapshot, and Stats. It also exposes many sortable fields such as P/E, forward P/E, PEG, EPS growth, sales growth, margins, ownership, short interest, performance, beta, ATR, volatility, SMA relationships, RSI, volume, target price, EV/EBITDA, EV/Sales, and news fields. ([Finviz][1])

Important note: if you use Finviz directly, quotes are delayed 15 minutes for NASDAQ, NYSE, and AMEX, so your real-time trading logic should use another market-data provider for live prices. ([Finviz][1])

---

# 1. New Strategy Principle

Your current model was missing too many **technical and positioning datapoints**.

The revised model should not just ask:

```md
Is the stock cheap?
```

It should ask:

```md
Is the stock technically strong?
Is it extended?
Is it under accumulation?
Is it near breakout?
Is it near support?
Is volume confirming the move?
Is the stock outperforming the market?
Is the sector helping?
Is the move backed by earnings, news, or institutional interest?
```

---

# 2. Finviz Screener Tabs to Convert Into Data Modules

## Module A: Descriptive / Universe Filter

Finviz descriptive filters include exchange, index, sector, industry, country, market cap, dividend yield, short float, analyst recommendation, optionability/shortability, earnings date, average volume, relative volume, current volume, price, target price, IPO date, shares outstanding, float, and themes/sub-themes. ([Finviz][1])

Use these mostly to define:

```md
Tradable universe
Liquidity
Sector/industry context
Market cap category
Stock archetype
Event proximity
Options availability
Short squeeze potential
```

---

## Module B: Fundamental / Valuation Filter

Finviz fundamental filters include P/E, forward P/E, PEG, P/S, P/B, price/cash, price/free cash flow, EV/EBITDA, EV/Sales, dividend growth, EPS growth across multiple periods, sales growth across multiple periods, earnings/revenue surprise, ROA, ROE, ROIC, current ratio, quick ratio, debt/equity, gross margin, operating margin, net margin, payout ratio, insider ownership/transactions, institutional ownership/transactions, and short float. ([Finviz][2])

Use these for:

```md
Growth quality
Valuation relative to growth
Balance sheet risk
Profitability
Ownership pressure
Business quality
Medium/long-term thesis
```

---

## Module C: Technical Filter

Finviz technical filters include performance across today/week/month/quarter/half-year/YTD/year/3-year/5-year/10-year, volatility, RSI, gap, 20-day SMA, 50-day SMA, 200-day SMA, change, change from open, 20-day high/low, 50-day high/low, 52-week high/low, all-time high/low, chart patterns, candlestick patterns, beta, ATR, average volume, relative volume, and current volume. ([Finviz][3])

Use these heavily for:

```md
Short-term entry
Momentum
Trend strength
Breakout quality
Pullback quality
Overextension risk
Volatility-adjusted stop-loss
```

---

# 3. Short-Term Buy Decision Datapoints

Timeframe:

```md
1 day to 4 weeks
```

Main goal:

```md
Good entry timing + momentum + catalyst + risk control
```

## Short-Term Datapoints to Fetch / Compute

|  # | Datapoint                        | Source Type                    | Why It Matters                    |
| -: | -------------------------------- | ------------------------------ | --------------------------------- |
|  1 | Current price                    | Finviz / market data           | Base price for all calculations   |
|  2 | Previous close                   | Market data                    | Gap and day-change calculation    |
|  3 | Open price                       | Market data                    | Intraday strength/weakness        |
|  4 | Day high                         | Market data                    | Breakout/intraday resistance      |
|  5 | Day low                          | Market data                    | Intraday support                  |
|  6 | Price change %                   | Finviz technical               | Immediate momentum                |
|  7 | Change from open %               | Finviz technical               | Intraday buying/selling pressure  |
|  8 | Gap %                            | Finviz technical               | News/earnings reaction            |
|  9 | Current volume                   | Finviz technical/descriptive   | Confirms active participation     |
| 10 | Average volume                   | Finviz technical/descriptive   | Liquidity baseline                |
| 11 | Relative volume                  | Finviz technical/descriptive   | Unusual activity / attention      |
| 12 | Volume vs 20-day average         | Derived                        | Accumulation or distribution      |
| 13 | Volume on up days vs down days   | Derived                        | Buyer/seller dominance            |
| 14 | 1-day performance                | Finviz technical               | Immediate momentum                |
| 15 | 1-week performance               | Finviz technical               | Short-term trend                  |
| 16 | 1-month performance              | Finviz technical               | Swing momentum                    |
| 17 | RSI 14                           | Finviz technical               | Overbought/oversold timing        |
| 18 | RSI slope                        | Derived                        | Momentum improving/deteriorating  |
| 19 | Price vs 20-day SMA              | Finviz technical               | Short-term trend/extension        |
| 20 | Price vs 50-day SMA              | Finviz technical               | Intermediate trend support        |
| 21 | 20-day SMA vs 50-day SMA         | Finviz technical / derived     | Trend alignment                   |
| 22 | SMA20 crossover                  | Finviz technical               | Recent technical trigger          |
| 23 | SMA50 crossover                  | Finviz technical               | Stronger trend shift              |
| 24 | 20-day high/low distance         | Finviz technical               | Breakout or pullback zone         |
| 25 | 50-day high/low distance         | Finviz technical               | Swing range position              |
| 26 | 52-week high distance            | Finviz technical               | Breakout potential or extension   |
| 27 | 52-week low distance             | Finviz technical               | Recovery strength                 |
| 28 | ATR                              | Finviz technical               | Stop-loss and position sizing     |
| 29 | Weekly volatility                | Finviz technical               | Short-term risk                   |
| 30 | Monthly volatility               | Finviz technical               | Swing risk                        |
| 31 | Beta                             | Finviz technical               | Market sensitivity                |
| 32 | Chart pattern                    | Finviz technical               | Breakout/base/pullback context    |
| 33 | Candlestick pattern              | Finviz technical               | Reversal/continuation signal      |
| 34 | Analyst upgrade/downgrade signal | Finviz signal/news             | Near-term catalyst                |
| 35 | Earnings before/after signal     | Finviz signal                  | Event-risk classification         |
| 36 | Major news signal                | Finviz signal/news             | Short-term catalyst               |
| 37 | Optionable                       | Finviz descriptive             | Enables options sentiment/hedging |
| 38 | Short float                      | Finviz descriptive/fundamental | Short squeeze risk                |
| 39 | Float size                       | Finviz descriptive             | Smaller float = sharper moves     |
| 40 | Price vs analyst target          | Finviz descriptive             | Sentiment/expectation gap         |

Finviz also includes screener signals like Top Gainers, Top Losers, New High, New Low, Most Volatile, Most Active, Unusual Volume, Overbought, Oversold, Downgrades, Upgrades, Earnings Before/After, Recent Insider Buying/Selling, Major News, and multiple chart-pattern signals. ([Finviz][1])

---

## Short-Term Model Score

```md
ShortTermScore =
  25% Price Momentum
+ 20% Volume / Relative Volume
+ 15% Trend Alignment
+ 15% Breakout or Pullback Setup
+ 10% Catalyst / News / Earnings Proximity
+ 10% Volatility-Adjusted Risk/Reward
+ 5% Short Interest / Float Pressure
```

## Short-Term Decision Logic

```md
BUY_NOW_MOMENTUM if:
- Price above SMA20, SMA50, and SMA200
- Relative volume > 1.5
- 1-week and 1-month performance positive
- RSI between 50 and 70
- Price is not more than 10% above SMA20
- Breakout or continuation pattern confirmed

BUY_STARTER_STRONG_BUT_EXTENDED if:
- Momentum strong
- Relative volume strong
- RSI > 70 or price too far above SMA20
- No major negative news

WAIT_FOR_PULLBACK if:
- Stock is strong
- Price is near 52-week high
- Price is extended above SMA20/SMA50
- Risk/reward is poor at current price

AVOID_BAD_CHART if:
- Price below SMA50 and SMA200
- Relative strength deteriorating
- Down days have higher volume than up days
- RSI weak and not recovering
```

---

# 4. Medium-Term Buy Decision Datapoints

Timeframe:

```md
1 to 6 months
```

Main goal:

```md
Find stocks with trend + earnings momentum + sector support
```

## Medium-Term Datapoints to Fetch / Compute

|  # | Datapoint                         | Source Type                    | Why It Matters            |
| -: | --------------------------------- | ------------------------------ | ------------------------- |
|  1 | 1-month performance               | Finviz technical               | Recent strength           |
|  2 | Quarter performance               | Finviz technical               | Swing trend               |
|  3 | Half-year performance             | Finviz technical               | Medium-term trend         |
|  4 | YTD performance                   | Finviz technical               | Institutional trend       |
|  5 | Price vs 50-day SMA               | Finviz technical               | Core swing trend          |
|  6 | Price vs 200-day SMA              | Finviz technical               | Major trend filter        |
|  7 | 50-day SMA vs 200-day SMA         | Finviz technical / derived     | Bull/bear structure       |
|  8 | 50-day high/low distance          | Finviz technical               | Base/pullback position    |
|  9 | 52-week high/low distance         | Finviz technical               | Momentum leadership       |
| 10 | ATR                               | Finviz technical               | Swing stop sizing         |
| 11 | Monthly volatility                | Finviz technical               | Risk profile              |
| 12 | Beta                              | Finviz technical               | Market sensitivity        |
| 13 | Relative volume trend             | Finviz / derived               | Institutional interest    |
| 14 | Average volume                    | Finviz                         | Liquidity                 |
| 15 | Market cap                        | Finviz descriptive             | Size/risk category        |
| 16 | Sector                            | Finviz descriptive             | Sector rotation           |
| 17 | Industry                          | Finviz descriptive             | Peer comparison           |
| 18 | Analyst recommendation            | Finviz descriptive             | Sentiment baseline        |
| 19 | Analyst target price distance     | Finviz descriptive             | Upside expectation        |
| 20 | Earnings date                     | Finviz descriptive             | Catalyst timing           |
| 21 | EPS surprise                      | Finviz fundamental             | Earnings momentum         |
| 22 | Revenue surprise                  | Finviz fundamental             | Sales execution           |
| 23 | EPS growth this year              | Finviz fundamental             | Current-year growth       |
| 24 | EPS growth next year              | Finviz fundamental             | Forward growth            |
| 25 | EPS growth quarter-over-quarter   | Finviz fundamental             | Acceleration              |
| 26 | EPS growth TTM                    | Finviz fundamental             | Profit trend              |
| 27 | Sales growth quarter-over-quarter | Finviz fundamental             | Demand acceleration       |
| 28 | Sales growth TTM                  | Finviz fundamental             | Revenue trend             |
| 29 | Gross margin                      | Finviz fundamental             | Business quality          |
| 30 | Operating margin                  | Finviz fundamental             | Operating leverage        |
| 31 | Net profit margin                 | Finviz fundamental             | Profitability             |
| 32 | ROE                               | Finviz fundamental             | Return quality            |
| 33 | ROIC                              | Finviz fundamental             | Capital efficiency        |
| 34 | Debt/equity                       | Finviz fundamental             | Balance-sheet risk        |
| 35 | Current ratio                     | Finviz fundamental             | Liquidity safety          |
| 36 | Institutional ownership           | Finviz fundamental             | Sponsorship               |
| 37 | Institutional transactions        | Finviz fundamental             | Accumulation/distribution |
| 38 | Insider transactions              | Finviz fundamental             | Insider confidence        |
| 39 | Short float                       | Finviz fundamental/descriptive | Squeeze or skepticism     |
| 40 | Forward P/E                       | Finviz fundamental             | Forward valuation         |
| 41 | PEG                               | Finviz fundamental             | Growth-adjusted valuation |
| 42 | P/S                               | Finviz fundamental             | Growth-stock valuation    |
| 43 | EV/Sales                          | Finviz fundamental             | Enterprise valuation      |
| 44 | EV/EBITDA                         | Finviz fundamental             | Profit valuation          |
| 45 | Price/free cash flow              | Finviz fundamental             | Cash-flow valuation       |

Finviz’s fundamental filters include forward P/E, PEG, P/S, P/B, price/free cash flow, EV/EBITDA, EV/Sales, EPS growth, sales growth, earnings/revenue surprise, returns, liquidity ratios, debt/equity, margins, ownership, and institutional transaction fields. ([Finviz][2])

---

## Medium-Term Model Score

```md
MediumTermScore =
  20% Technical Trend
+ 20% Earnings Momentum
+ 15% Sales / EPS Growth Acceleration
+ 15% Sector / Industry Strength
+ 10% Institutional Accumulation
+ 10% Growth-Adjusted Valuation
+ 5% Balance Sheet
+ 5% Catalyst Timing
```

## Medium-Term Decision Logic

```md
BUY_NOW if:
- Price above SMA50 and SMA200
- Quarter and half-year performance positive
- EPS and sales growth are positive or accelerating
- Recent earnings/revenue surprise positive
- Sector trend is supportive
- Valuation is acceptable relative to growth

BUY_STARTER if:
- Fundamentals and trend are strong
- But price is extended near 52-week high
- Or earnings date is close

BUY_ON_PULLBACK if:
- Strong medium-term trend
- Price pulls back toward SMA50
- Volume dries up on pullback
- No fundamental deterioration

WATCHLIST_NEEDS_CONFIRMATION if:
- Good business
- But technical trend is sideways
- Or earnings estimates/news not yet confirming

AVOID_BAD_BUSINESS if:
- Sales growth slowing
- EPS growth negative
- Margins compressing
- Debt high
- Institutional transactions negative
```

---

# 5. Long-Term Buy Decision Datapoints

Timeframe:

```md
1 to 5+ years
```

Main goal:

```md
Find durable compounders or secular winners, without overpaying blindly
```

## Long-Term Datapoints to Fetch / Compute

|  # | Datapoint                  | Source Type                    | Why It Matters                    |
| -: | -------------------------- | ------------------------------ | --------------------------------- |
|  1 | Market cap                 | Finviz descriptive             | Size and maturity                 |
|  2 | Sector                     | Finviz descriptive             | Secular trend context             |
|  3 | Industry                   | Finviz descriptive             | Competitive comparison            |
|  4 | Theme                      | Finviz descriptive             | AI, cloud, semis, quantum, etc.   |
|  5 | Sub-theme                  | Finviz descriptive             | More precise secular bucket       |
|  6 | IPO date                   | Finviz descriptive             | Business maturity                 |
|  7 | Shares outstanding         | Finviz descriptive             | Dilution/share structure          |
|  8 | Float                      | Finviz descriptive             | Share availability                |
|  9 | Dividend yield             | Finviz descriptive/fundamental | Income/defensive profile          |
| 10 | Dividend growth 1-year     | Finviz fundamental             | Shareholder returns               |
| 11 | Dividend growth 3-year     | Finviz fundamental             | Consistency                       |
| 12 | Dividend growth 5-year     | Finviz fundamental             | Long-term income growth           |
| 13 | P/E                        | Finviz fundamental             | Current earnings valuation        |
| 14 | Forward P/E                | Finviz fundamental             | Forward earnings valuation        |
| 15 | PEG                        | Finviz fundamental             | Growth-adjusted valuation         |
| 16 | P/S                        | Finviz fundamental             | Revenue valuation                 |
| 17 | P/B                        | Finviz fundamental             | Asset valuation                   |
| 18 | Price/cash                 | Finviz fundamental             | Balance-sheet valuation           |
| 19 | Price/free cash flow       | Finviz fundamental             | Cash-flow valuation               |
| 20 | EV/EBITDA                  | Finviz fundamental             | Enterprise profit valuation       |
| 21 | EV/Sales                   | Finviz fundamental             | Enterprise revenue valuation      |
| 22 | EPS growth past 3 years    | Finviz fundamental             | Historical earnings power         |
| 23 | EPS growth past 5 years    | Finviz fundamental             | Long-term earnings trend          |
| 24 | EPS growth next 5 years    | Finviz fundamental             | Forward compounding expectation   |
| 25 | Sales growth past 3 years  | Finviz fundamental             | Durable demand                    |
| 26 | Sales growth past 5 years  | Finviz fundamental             | Multi-year revenue trend          |
| 27 | Sales growth TTM           | Finviz fundamental             | Current business momentum         |
| 28 | Gross margin               | Finviz fundamental             | Moat/pricing power                |
| 29 | Operating margin           | Finviz fundamental             | Operating leverage                |
| 30 | Net margin                 | Finviz fundamental             | Profit quality                    |
| 31 | ROA                        | Finviz fundamental             | Asset efficiency                  |
| 32 | ROE                        | Finviz fundamental             | Equity efficiency                 |
| 33 | ROIC                       | Finviz fundamental             | Long-term compounding quality     |
| 34 | Current ratio              | Finviz fundamental             | Liquidity safety                  |
| 35 | Quick ratio                | Finviz fundamental             | More conservative liquidity       |
| 36 | Long-term debt/equity      | Finviz fundamental             | Debt risk                         |
| 37 | Total debt/equity          | Finviz fundamental             | Capital structure                 |
| 38 | Insider ownership          | Finviz fundamental             | Founder/management alignment      |
| 39 | Insider transactions       | Finviz fundamental             | Insider confidence                |
| 40 | Institutional ownership    | Finviz fundamental             | Institutional sponsorship         |
| 41 | Institutional transactions | Finviz fundamental             | Sponsorship trend                 |
| 42 | 3-year performance         | Finviz technical               | Long-term stock behavior          |
| 43 | 5-year performance         | Finviz technical               | Compounding history               |
| 44 | 10-year performance        | Finviz technical               | Long-cycle winner check           |
| 45 | All-time high distance     | Finviz technical               | Secular strength or recovery risk |
| 46 | All-time low distance      | Finviz technical               | Long-term recovery context        |
| 47 | 200-day SMA relationship   | Finviz technical               | Long-term trend health            |
| 48 | Beta                       | Finviz technical               | Portfolio volatility              |
| 49 | Short interest             | Finviz sortable field          | Long-term skepticism              |
| 50 | Analyst recommendation     | Finviz descriptive             | Sentiment checkpoint              |

Finviz includes theme and sub-theme classification, including areas like artificial intelligence, cloud computing, semiconductors, quantum computing, cybersecurity, robotics, energy, software, and many others. ([Finviz][1])

---

## Long-Term Model Score

```md
LongTermScore =
  20% Business Quality
+ 20% Revenue / EPS Durability
+ 15% Margin Quality
+ 15% ROIC / ROE / ROA
+ 10% Balance Sheet Strength
+ 10% Growth-Adjusted Valuation
+ 5% Insider / Institutional Alignment
+ 5% Long-Term Price Trend
```

## Long-Term Decision Logic

```md
ACCUMULATE_ON_WEAKNESS if:
- Business quality is high
- Sales/EPS growth durable
- Margins strong or expanding
- ROIC/ROE strong
- Balance sheet acceptable
- Stock is expensive but justified by growth

BUY_NOW_LONG_TERM if:
- Business quality strong
- Valuation reasonable relative to growth
- 200-day trend healthy
- No major deterioration in margins or growth

WATCHLIST_VALUATION_TOO_RICH if:
- Great business
- But PEG, forward P/E, EV/Sales, or P/FCF are extreme
- Price is far above long-term trend

AVOID_LONG_TERM if:
- Sales/EPS growth weak
- Margins deteriorating
- Debt high
- ROIC poor
- Stock only moves due to hype, not business progress
```

---

# 6. Technical Indicators Your Tool Should Add Beyond Current Version

Finviz gives you several high-value technical fields, especially performance, volatility, RSI, gap, SMA20/SMA50/SMA200, change, high/low ranges, chart patterns, candlestick patterns, beta, ATR, volume, and relative volume. ([Finviz][3])

But your engine should compute additional indicators internally from OHLCV data.

## Add These Derived Technical Indicators

|  # | Indicator                       | Best Horizon  | Why Add It                  |
| -: | ------------------------------- | ------------- | --------------------------- |
|  1 | EMA 8                           | Short         | Fast momentum               |
|  2 | EMA 21                          | Short/Medium  | Swing trend                 |
|  3 | SMA 10                          | Short         | Near-term trend             |
|  4 | SMA 20 slope                    | Short         | Trend acceleration          |
|  5 | SMA 50 slope                    | Medium        | Trend quality               |
|  6 | SMA 200 slope                   | Long          | Long-term regime            |
|  7 | MACD line                       | Short/Medium  | Momentum shift              |
|  8 | MACD signal                     | Short/Medium  | Confirmation                |
|  9 | MACD histogram                  | Short         | Acceleration                |
| 10 | Bollinger Band position         | Short         | Extension/compression       |
| 11 | Bollinger Band width            | Short/Medium  | Volatility squeeze          |
| 12 | Keltner Channel position        | Short         | Trend extension             |
| 13 | ADX                             | Medium        | Trend strength              |
| 14 | +DI / -DI                       | Medium        | Directional dominance       |
| 15 | Stochastic RSI                  | Short         | Pullback timing             |
| 16 | Williams %R                     | Short         | Overbought/oversold         |
| 17 | On-Balance Volume               | Short/Medium  | Accumulation                |
| 18 | Accumulation/Distribution Line  | Medium        | Institutional pressure      |
| 19 | Chaikin Money Flow              | Short/Medium  | Buying/selling pressure     |
| 20 | VWAP                            | Short         | Intraday/short-term quality |
| 21 | Anchored VWAP from earnings     | Medium        | Post-earnings support       |
| 22 | Anchored VWAP from breakout     | Medium        | Trend support               |
| 23 | Relative strength vs SPY        | All           | Market-relative alpha       |
| 24 | Relative strength vs QQQ        | Growth stocks | Tech/growth alpha           |
| 25 | Relative strength vs sector ETF | All           | Sector leadership           |
| 26 | 20-day return percentile        | Short         | Rank-based momentum         |
| 27 | 63-day return percentile        | Medium        | Quarter momentum            |
| 28 | 126-day return percentile       | Medium        | Half-year leadership        |
| 29 | 252-day return percentile       | Long          | Annual momentum             |
| 30 | Volume dry-up ratio             | Short/Medium  | Pullback quality            |
| 31 | Breakout volume multiple        | Short         | Breakout confirmation       |
| 32 | Down-volume/up-volume ratio     | Medium        | Distribution risk           |
| 33 | Distance from nearest support   | Short         | Risk calculation            |
| 34 | Distance to resistance          | Short         | Upside calculation          |
| 35 | Risk/reward ratio               | All           | Entry quality               |
| 36 | Max drawdown 3M                 | Medium        | Risk profile                |
| 37 | Max drawdown 1Y                 | Long          | Long-term volatility        |
| 38 | Gap fill status                 | Short         | Post-news behavior          |
| 39 | Earnings gap direction          | Short/Medium  | Institutional reaction      |
| 40 | Post-earnings drift             | Medium        | Earnings momentum           |

---

# 7. Revised Feature Groups for Your Tool

## Group 1: Entry Timing Features

Use mostly for short-term.

```md
- RSI 14
- Stochastic RSI
- Price vs SMA20
- Price vs EMA8
- Price vs EMA21
- Gap %
- Change from open
- Candlestick pattern
- Distance to 20-day high
- Distance to 20-day low
- ATR-based stop distance
- VWAP position
```

---

## Group 2: Momentum Features

Use for short and medium term.

```md
- 1-week performance
- 1-month performance
- Quarter performance
- Half-year performance
- YTD performance
- Price vs SMA50
- SMA20/SMA50 relationship
- MACD histogram
- Relative strength vs SPY
- Relative strength vs QQQ
- Relative strength vs sector ETF
- 52-week high distance
```

---

## Group 3: Breakout / Pullback Features

Use for short and medium term.

```md
- 20-day high/low
- 50-day high/low
- 52-week high/low
- All-time high/low
- Chart pattern
- Horizontal support/resistance
- Trendline resistance
- Trendline support
- Wedge pattern
- Triangle pattern
- Channel pattern
- Double bottom
- Double top
- Head and shoulders
- Inverse head and shoulders
```

---

## Group 4: Volume / Accumulation Features

Use for short and medium term.

```md
- Current volume
- Average volume
- Relative volume
- Breakout volume multiple
- Up-volume/down-volume ratio
- Volume dry-up during pullback
- OBV trend
- Accumulation/distribution trend
- Chaikin Money Flow
- Institutional transactions
```

---

## Group 5: Volatility / Risk Features

Use for all horizons.

```md
- ATR
- Weekly volatility
- Monthly volatility
- Beta
- ATR percentage of price
- Stop-loss distance
- Gap risk
- Earnings expected move
- Max drawdown 3M
- Max drawdown 1Y
- Risk/reward ratio
```

---

## Group 6: Growth / Earnings Features

Use mostly for medium and long term.

```md
- EPS growth this year
- EPS growth next year
- EPS growth quarter-over-quarter
- EPS growth TTM
- EPS growth past 3 years
- EPS growth past 5 years
- EPS growth next 5 years
- Sales growth quarter-over-quarter
- Sales growth TTM
- Sales growth past 3 years
- Sales growth past 5 years
- EPS surprise
- Revenue surprise
```

---

## Group 7: Quality / Profitability Features

Use mostly for long term.

```md
- Gross margin
- Operating margin
- Net margin
- ROA
- ROE
- ROIC
- Current ratio
- Quick ratio
- Debt/equity
- Long-term debt/equity
- Free cash flow valuation
```

---

## Group 8: Valuation Features

Use mostly for medium and long term.

```md
- P/E
- Forward P/E
- PEG
- P/S
- P/B
- Price/cash
- Price/free cash flow
- EV/EBITDA
- EV/Sales
- Price vs analyst target
```

---

## Group 9: Ownership / Positioning Features

Use for all horizons.

```md
- Insider ownership
- Insider transactions
- Institutional ownership
- Institutional transactions
- Short float
- Short interest
- Short interest ratio
- Float
- Shares outstanding
- Optionable
- Shortable
```

---

# 8. Recommended New Data Contract

```ts
interface TechnicalDecisionFeatures {
  price: number;
  changePercent: number;
  changeFromOpenPercent: number;
  gapPercent: number;

  performance1W: number;
  performance1M: number;
  performance3M: number;
  performance6M: number;
  performanceYTD: number;
  performance1Y: number;

  sma20Relative: number;
  sma50Relative: number;
  sma200Relative: number;
  sma20Slope: number;
  sma50Slope: number;
  sma200Slope: number;

  ema8Relative?: number;
  ema21Relative?: number;

  rsi14: number;
  macd?: number;
  macdSignal?: number;
  macdHistogram?: number;
  adx?: number;
  stochasticRsi?: number;

  atr: number;
  atrPercent: number;
  volatilityWeek: number;
  volatilityMonth: number;
  beta: number;

  averageVolume: number;
  currentVolume: number;
  relativeVolume: number;
  volumeTrendScore: number;
  accumulationDistributionScore?: number;
  obvTrendScore?: number;

  distanceFrom20DayHigh: number;
  distanceFrom50DayHigh: number;
  distanceFrom52WeekHigh: number;
  distanceFromAllTimeHigh: number;

  distanceFrom20DayLow: number;
  distanceFrom50DayLow: number;
  distanceFrom52WeekLow: number;
  distanceFromAllTimeLow: number;

  chartPattern?: string;
  candlestickPattern?: string;

  relativeStrengthVsSPY: number;
  relativeStrengthVsQQQ: number;
  relativeStrengthVsSectorETF: number;

  supportLevel: number;
  resistanceLevel: number;
  riskRewardRatio: number;
}
```

---

# 9. Updated Recommendation Engine

## New Short-Term Weighting

```md
Short-term:
- Technical momentum: 25%
- Relative volume / accumulation: 20%
- Entry quality: 20%
- Relative strength: 15%
- Volatility-adjusted risk/reward: 10%
- Catalyst/news/earnings timing: 10%
```

## New Medium-Term Weighting

```md
Medium-term:
- Technical trend: 20%
- Earnings/sales growth acceleration: 20%
- Relative strength vs market/sector: 15%
- Volume/institutional accumulation: 15%
- Growth-adjusted valuation: 10%
- Profitability/margins: 10%
- Catalyst/earnings date: 10%
```

## New Long-Term Weighting

```md
Long-term:
- Revenue/EPS durability: 20%
- Profitability and ROIC: 20%
- Balance sheet quality: 15%
- Growth-adjusted valuation: 15%
- Long-term trend strength: 10%
- Sector/theme tailwind: 10%
- Ownership/sponsorship: 5%
- Drawdown/volatility risk: 5%
```

---

# 10. Coding Agent Instruction Add-On

Use this directly:

```md
# Task: Expand Stock Decision Tool With Finviz-Inspired Technical and Fundamental Datapoints

The current stock decision tool is missing too many technical indicators and market-structure datapoints.

Use Finviz screener categories as inspiration:
- Descriptive
- Fundamental
- Technical
- News
- All

Add support for at least these data groups:

1. Entry timing
2. Momentum
3. Trend alignment
4. Breakout/pullback setup
5. Volume/accumulation
6. Volatility/risk
7. Relative strength
8. Growth/earnings
9. Quality/profitability
10. Growth-adjusted valuation
11. Ownership/positioning
12. Catalyst/news

Required technical fields:
- Current price
- Previous close
- Open
- High
- Low
- Change %
- Change from open %
- Gap %
- Current volume
- Average volume
- Relative volume
- 1-week performance
- 1-month performance
- Quarter performance
- Half-year performance
- YTD performance
- 1-year performance
- 3-year performance
- 5-year performance
- RSI 14
- ATR
- Weekly volatility
- Monthly volatility
- Beta
- Price vs SMA20
- Price vs SMA50
- Price vs SMA200
- SMA20/SMA50 relationship
- SMA50/SMA200 relationship
- 20-day high/low distance
- 50-day high/low distance
- 52-week high/low distance
- All-time high/low distance
- Chart pattern
- Candlestick pattern
- Support level
- Resistance level
- Risk/reward ratio
- Relative strength vs SPY
- Relative strength vs QQQ
- Relative strength vs sector ETF

Additional internally computed indicators:
- EMA8
- EMA21
- MACD
- MACD signal
- MACD histogram
- ADX
- Stochastic RSI
- Bollinger Band position
- Bollinger Band width
- VWAP
- Anchored VWAP from last earnings
- OBV
- Accumulation/distribution
- Chaikin Money Flow
- Volume dry-up ratio
- Breakout volume multiple
- Up-volume/down-volume ratio
- Max drawdown 3M
- Max drawdown 1Y

Required fundamental/valuation fields:
- P/E
- Forward P/E
- PEG
- P/S
- P/B
- Price/cash
- Price/free cash flow
- EV/EBITDA
- EV/Sales
- EPS growth this year
- EPS growth next year
- EPS growth quarter-over-quarter
- EPS growth TTM
- EPS growth past 3 years
- EPS growth past 5 years
- EPS growth next 5 years
- Sales growth quarter-over-quarter
- Sales growth TTM
- Sales growth past 3 years
- Sales growth past 5 years
- EPS surprise
- Revenue surprise
- Gross margin
- Operating margin
- Net margin
- ROA
- ROE
- ROIC
- Current ratio
- Quick ratio
- Debt/equity
- Long-term debt/equity
- Insider ownership
- Insider transactions
- Institutional ownership
- Institutional transactions
- Short float
- Short interest ratio
- Analyst recommendation
- Target price distance

Do not collapse all these into one generic score.

Create separate signal cards:
- Momentum
- Trend
- Entry timing
- Volume/accumulation
- Volatility/risk
- Relative strength
- Growth
- Valuation
- Quality
- Ownership
- Catalyst

Each signal card should output:
- score: 0–100
- label: VERY_BEARISH | BEARISH | NEUTRAL | BULLISH | VERY_BULLISH
- explanation
- top positive factors
- top negative factors
- missing data warnings

Then generate horizon-specific recommendations:
- Short-term
- Medium-term
- Long-term
```

---

# 11. Biggest Practical Improvement

For your next version, the most important upgrade is this:

```md
Do not let valuation dominate technical momentum.
Do not let one composite score hide strong signals.
Do not treat missing news/options data as neutral.
Do not use the same features for short, medium, and long horizons.
```

Your new tool should say things like:

```md
Short-term:
Bullish momentum, high relative volume, but extended above SMA20. Wait for pullback.

Medium-term:
Strong earnings and sales acceleration, good trend, institutional support. Buy starter.

Long-term:
Great business quality but valuation risk high. Accumulate only on weakness.
```

That is much closer to a real trading/investing decision engine.

[1]: https://finviz.com/screener "Free Stock Screener"
[2]: https://finviz.com/screener.ashx?ft=2&v=111 "Stock Screener - Overview "
[3]: https://finviz.com/screener.ashx?ft=3&v=111 "Stock Screener - Overview "
