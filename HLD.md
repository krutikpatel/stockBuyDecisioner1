# High Level Design — Stock Decision Tool

---

## 1. System Overview

The Stock Decision Tool is a full-stack application that evaluates any US-listed stock or ETF across three investment horizons (short / medium / long term) and returns a structured recommendation backed by technical, fundamental, valuation, earnings, sentiment, archetype, and market-regime analysis.

```mermaid
C4Context
  title System Context

  Person(user, "Investor", "Enters a ticker and risk profile, reviews structured recommendation")

  System(frontend, "React Frontend", "Dashboard UI — ticker input, 11 signal cards, recommendation cards, signal profile, regime/archetype badges, performance table, ownership/volume panels, charts, markdown report")
  System(backend, "FastAPI Backend", "Analysis engine — archetype classification, regime detection, growth-adjusted valuation, regime-aware scoring, multi-gate decision logic, ATR-based risk management")

  System_Ext(yfinance, "Yahoo Finance (yfinance)", "Price/OHLCV, fundamentals, earnings, options, news, VIX, QQQ")
  System_Ext(openai, "OpenAI API", "GPT-4o-mini — news headline sentiment classification")

  Rel(user, frontend, "Enters ticker + risk profile, views results", "Browser")
  Rel(frontend, backend, "POST /api/stocks/analyze", "HTTP/JSON")
  Rel(backend, yfinance, "Fetches market data, financials, news, options, VIX, QQQ, sector ETFs", "yfinance SDK / Yahoo Finance API")
  Rel(backend, openai, "Classifies news sentiment", "OpenAI Python SDK (optional)")
```

---

## 2. High-Level Architecture

```mermaid
flowchart TB
    subgraph Browser["Browser (React + TypeScript + Vite)"]
        UI["Dashboard.tsx\nTicker input · Risk profile · Results"]
        RAB["RegimeArchetypeBar\nArchetype badge · Regime badge"]
        SPC["SignalProfileCard\n6 signal dimension cards"]
        SCG["SignalCardsGrid\n11 signal cards (score gauge + factors)"]
        RC["RecommendationCard\nNew per-horizon decision labels\nCompleteness bars"]
        SC["ScoreBreakdown"]
        TC["TechnicalChart"]
        PT["PerformanceTable\n1W/1M/3M/6M/YTD/1Y/3Y/5Y + max DD"]
        OP["OwnershipPanel\nInsider · Institutional · Short · Analyst"]
        VP["VolumePanel\nOBV · A/D · CMF · VWAP dev · vol ratios"]
        NW["NewsSection"]
        MR["MarkdownReport"]
    end

    subgraph API["FastAPI Backend (Python 3.12)"]
        Router["POST /api/stocks/analyze\nGET /report · /technicals · /news\nGET /health"]

        subgraph Providers["Data Providers"]
            MP["MarketDataProvider\nyfinance OHLCV + retry"]
            FP["FundamentalProvider\nyfinance .info + statements\n(sector, beta, growth rates, ownership,\nanalyst data, ROA, quick ratio, etc.)"]
            EP["EarningsProvider\nearnings_history + dates"]
            NP["NewsProvider\nyfinance .news"]
            OP["OptionsProvider\noption_chain(nearest_expiry)"]
        end

        subgraph Services["Analysis Services"]
            TA["TechnicalAnalysisService\nMAs · EMA8/21 · RSI · MACD · ATR · ADX\nStochRSI · Bollinger Bands · SMA slopes\nPerf periods (1W–5Y) · Range distances\nWeekly/Monthly vol · Trend · Extension · S/R · RS\nOBV · A/D · CMF · VWAP · vol ratios\nRS vs QQQ · Percentile ranks · Drawdown · Gap fill"]
            FA["FundamentalAnalysisService\nRevenue · Margins · FCF · Debt · ROE\nROIC · ROA · Quick ratio · LT D/E\nMulti-period EPS/Sales growth\nOwnership · Short float · Analyst data"]
            AS["StockArchetypeService\nClassify: HYPER_GROWTH / MATURE_VALUE\n/ DEFENSIVE / CYCLICAL / etc."]
            VA["ValuationAnalysisService\nscore_valuation() — generic\nscore_valuation_with_archetype() — growth-adjusted\nEV/Sales · P/Book · P/Cash"]
            MR2["MarketRegimeService\nBULL_RISK_ON / BEAR_RISK_OFF\n/ SIDEWAYS_CHOPPY / etc.\nApplies regime weight multipliers"]
            NS["NewsSentimentService\nOpenAI GPT-4o-mini\n(keyword fallback)"]
            DC["DataCompletenessService\nScores 0–100 per gap\nCaps confidence when data thin"]
            SCS["SignalCardService\n11 signal card scorers:\nMomentum · Trend · Entry Timing\nVolume/Accum · Vol/Risk · RS\nGrowth · Valuation · Quality\nOwnership · Catalyst"]
            SS["ScoringService\nSignal-card weighted aggregation\nper horizon + regime multipliers"]
            RS["RecommendationService\nNew per-horizon decision labels\nSignal-card-based decision logic"]
            SP["SignalProfileService\nDerived from signal card scores\n6 signal dimensions"]
            RM["RiskManagementService\nEntry · Stop-loss · Target · R/R"]
            MDS["MarkdownReportService\nSignal cards section + full report"]
        end

        Cache["TTLCache\n15 min price · 24 h fundamentals"]
    end

    subgraph External["External Data Sources"]
        YF["Yahoo Finance\n(yfinance)\nSPY · QQQ · VIX · Sector ETFs"]
        OA["OpenAI API\n(optional)"]
    end

    UI -->|"analyzeStock()"| Router
    Router --> Providers
    Providers -->|retry + cache| YF
    NS --> OA
    Providers --> Services
    Services --> Cache
    Router --> Services
```

---

## 3. Request Lifecycle

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant API as FastAPI Router
    participant MP as MarketDataProvider
    participant TA as TechnicalAnalysis
    participant FP as FundamentalProvider
    participant AS as StockArchetypeService
    participant VA as ValuationService
    participant EP as EarningsProvider
    participant NP as NewsProvider
    participant OP as OptionsProvider
    participant NS as NewsSentiment
    participant MR2 as MarketRegimeService
    participant DC as DataCompletenessService
    participant SS as ScoringService
    participant RS as RecommendationService
    participant SP as SignalProfileService
    participant RM as RiskManagement
    participant MD as MarkdownReport

    User->>FE: Enter ticker + risk profile → click Analyze
    FE->>API: POST /api/stocks/analyze {ticker, risk_profile}

    API->>MP: get_market_data(ticker) → MarketData + current_price
    API->>MP: get_history(ticker, 1y) → OHLCV DataFrame
    API->>MP: get_history(SPY, 1y) + get_history(QQQ, 1y)
    API->>MP: get_history(sector_ETF, 6mo) → sector DataFrame

    API->>TA: compute_technicals(df, spy_df, sector_df) → TechnicalIndicators

    API->>FP: get_fundamental_data(ticker) → FundamentalData (with sector, beta)
    API->>AS: classify_and_attach(fundamentals, valuation) → archetype + confidence
    API->>VA: score_valuation_with_archetype(valuation, archetype, ...) → archetype_adjusted_score
    API->>FP: get_valuation_data(ticker) → ValuationData

    API->>MP: get_history(^VIX, 1mo) → vix_level
    API->>MR2: classify_regime(spy_hist, qqq_hist, vix_level) → MarketRegimeAssessment

    API->>MP: compute_relative_strength(sector, spy, 63d) → sector_macro_score

    API->>EP: get_earnings_data(ticker) → EarningsData
    API->>NP: get_news_items(ticker) → list[NewsItem]
    API->>NS: classify_news(items) → NewsSummary (GPT-4o-mini or keyword)
    API->>OP: get_options_snapshot(ticker) → put/call ratio → catalyst_score

    API->>DC: compute_completeness(news, earnings, valuation, ...) → completeness, confidence_score, warnings

    API->>SS: compute_scores(technicals, fundamentals, valuation, earnings, news, catalyst_score, sector_macro_score, regime_assessment) → scores{short/medium/long}

    loop for each horizon
        API->>RS: build_recommendations(..., regime_assessment, completeness) → HorizonRecommendation
        RS->>RM: compute_risk_management(price, technicals, decision, risk_profile)
        RM-->>RS: EntryPlan · ExitPlan · RiskReward · PositionSizing
    end

    API->>SP: build_signal_profile(technicals, fundamentals, valuation, earnings, news) → SignalProfile
    API->>MD: generate_markdown(result) → markdown_report string
    API-->>FE: StockAnalysisResult (JSON) with archetype, market_regime, signal_profile
    FE-->>User: Renders cards, signal profile, regime/archetype badges, charts, markdown report
```

---

## 4. Analysis Pipeline

```mermaid
flowchart LR
    subgraph Input
        T["Ticker\n+ Risk Profile"]
    end

    subgraph DataLayer["Data Layer (yfinance + TTLCache)"]
        PH["Price History\n1Y daily OHLCV"]
        SPY["SPY History\n1Y (benchmark)"]
        QQQ["QQQ History\n1Y (tech benchmark)"]
        VIX["^VIX History\n1M (regime signal)"]
        SEC["Sector ETF History\n6M"]
        INFO["ticker.info\n(snapshot, incl. sector + beta)"]
        STMT["Quarterly Statements\n(income, balance, cashflow)"]
        EH["Earnings History\n+ next date"]
        NEWS["News Headlines\n(yfinance.news)"]
        OPT["Option Chain\n(nearest expiry)"]
    end

    subgraph AnalysisLayer["Analysis Layer"]
        TECH["Technical Analysis\n─────────────\nMA(10/20/50/100/200) + EMA(8/21)\nSMA slopes (20/50/200) · SMA/EMA relatives\nRSI(14), MACD, ADX, StochRSI\nATR, ATR%, Bollinger Bands (pos/width)\nPerf: 1W/1M/3M/6M/YTD/1Y/3Y/5Y\nGap%, Change-from-open%\nRange dist: 20D/50D/52W/ATH/ATL high+low\nWeekly/Monthly vol · Trend classification\nExtension detection · Support/Resistance\nOBV trend · A/D trend · CMF · VWAP dev\nVol dry-up · Breakout vol mult · Up/Down vol\nRS vs SPY + QQQ + Sector\nReturn percentile ranks (20D/63D/126D/252D)\nMax drawdown (3M, 1Y) · Gap fill · Post-earnings drift\n→ technical_score 0–100"]

        ARCH["Stock Archetype\n─────────────\nHYPER_GROWTH\nPROFITABLE_GROWTH\nCYCLICAL_GROWTH\nMATURE_VALUE\nTURNAROUND\nSPECULATIVE_STORY\nDEFENSIVE\nCOMMODITY_CYCLICAL"]

        REG["Market Regime\n─────────────\nBULL_RISK_ON\nBULL_NARROW_LEADERSHIP\nSIDEWAYS_CHOPPY\nBEAR_RISK_OFF\nSECTOR_ROTATION\nLIQUIDITY_RALLY\n→ confidence + implication"]

        FUND["Fundamental Analysis\n─────────────\nRevenue growth YoY/QoQ/3Y/5Y\nEPS growth TTM/3Y/5Y/next 5Y\nGross / Op / Net margin\nFree cash flow, FCF margin\nNet debt, ROE, ROIC, ROA\nDebt-to-equity, LT D/E, Quick ratio\nInsider/Inst ownership + transactions\nShort float/ratio, analyst rec\n→ fundamental_score 0–100"]

        VAL["Valuation Analysis\n─────────────\nTrailing P/E, Forward P/E\nPEG (calculated)\nPrice/Sales, EV/EBITDA\nP/FCF, FCF Yield\nEV/Sales, P/Book, P/Cash\nscore_valuation() — generic\nscore_valuation_with_archetype()\n→ archetype_adjusted_score 0–100"]

        EARN["Earnings Analysis\n─────────────\nBeat rate (last 8 qtrs)\nAvg EPS surprise %\nNext earnings < 30d?\n→ earnings_score 0–100"]

        SENT["Sentiment Analysis\n─────────────\nGPT-4o-mini per headline\n→ positive/neutral/negative\n→ news_score 0–100"]

        CAT["Catalyst Signal\n─────────────\nPut/call ratio\nPCR < 0.7 → score 65\nPCR > 1.3 → score 35\nelse → score 50"]

        SMAC["Sector Macro\n─────────────\nRS(sector vs SPY, 63d)\n> 1.05 → score 65\n< 0.95 → score 35\nelse → score 50"]
    end

    T --> DataLayer
    PH --> TECH
    SPY --> TECH
    QQQ --> TECH
    SEC --> TECH
    SPY --> SMAC
    SEC --> SMAC
    SPY --> REG
    QQQ --> REG
    VIX --> REG
    INFO --> FUND
    INFO --> VAL
    INFO --> ARCH
    STMT --> FUND
    STMT --> VAL
    ARCH --> VAL
    EH --> EARN
    NEWS --> SENT
    OPT --> CAT
```

---

## 5. Scoring System

Scores are now derived from **11 signal card scores** (each 0–100), weighted per horizon.

```mermaid
flowchart TB
    subgraph Cards["11 Signal Cards (each 0–100)"]
        MOM["Momentum\n1W/1M/3M perf, MACD, RSI slope"]
        TRD["Trend\nPrice vs SMA20/50/200, slopes, ADX"]
        ENT["Entry Timing\nRSI, StochRSI, EMA8/21, VWAP, ATR"]
        VOL["Volume/Accum\nOBV, A/D, CMF, rel vol, up/down vol"]
        VRK["Vol/Risk\nATR%, drawdown, beta, weekly vol"]
        RS2["Relative Strength\nRS vs SPY/QQQ/sector, percentile ranks"]
        GRW["Growth\nEPS/rev growth, EPS surprise"]
        VALU["Valuation\nP/E, fwd P/E, PEG, P/S, EV/EBITDA, P/FCF"]
        QUAL["Quality\nGross/op/net margin, ROE, ROIC, ROA, ratios"]
        OWN["Ownership\nInsider/inst ownership+txn, short float"]
        CAT["Catalyst\nNews score, analyst rec, target dist, earnings"]
    end

    subgraph Weights["Signal Card Weights per Horizon (sums to 100)"]
        direction TB
        STW["Short-Term\n────────────\nMomentum          25%\nVol/Accum         20%\nEntry Timing      20%\nRelative Strength 15%\nVol/Risk          10%\nCatalyst          10%"]

        MTW["Medium-Term\n────────────\nTrend             20%\nGrowth            20%\nRelative Strength 15%\nVol/Accum         15%\nValuation         10%\nQuality           10%\nCatalyst          10%"]

        LTW["Long-Term\n────────────\nGrowth            20%\nQuality           20%\nValuation         15%\nOwnership         15%\nTrend             10%\nCatalyst          10%\nVol/Risk           5%\nMomentum           5%"]
    end

    subgraph Composites["Composite Scores (0–100)"]
        STC["short_term\n→ per-horizon decision label"]
        MTC["medium_term\n→ per-horizon decision label"]
        LTC["long_term\n→ per-horizon decision label"]
    end

    Cards --> STW --> STC
    Cards --> MTW --> MTC
    Cards --> LTW --> LTC
```

---

## 6. Decision Logic

Decision labels are **horizon-specific**, derived from signal-card-weighted composite scores plus multi-gate technical filters. Short-term decisions use the strictest gate logic; medium and long-term use simpler score-based routing.

### Short-Term Labels (multi-gate, regime-aware)

Short-term routing uses `_decide_short_term_v2()` with priority-ordered gates:

| Label | Routing Condition |
|-------|------------------|
| `BUY_NOW_CONTINUATION` | Score ≥ 75 **AND** RSI 55–68 (regime-adj) **AND** SMA20 0–5% **AND** SMA50 0–12% **AND** RS vs SPY/sector all positive **AND** 1W 0–6% **AND** 1M 3–15% **AND** rel-vol ≥ 1.3 |
| `BUY_STARTER_STRONG_BUT_EXTENDED` | Score ≥ 65 but SMA20 +5–10% (mildly extended) |
| `BUY_ON_PULLBACK` | Near SMA50 (−3% to +5%), RSI 40–58, vol dry-up < 0.85, RS vs sector ≥ −3% |
| `WAIT_FOR_PULLBACK` | Chasing avoidance: SMA20 > +10% **or** 1W > +10% **or** 1M > +25% |
| `OVERSOLD_REBOUND_CANDIDATE` | RSI 25–42 + turning up + improving price action + rel-vol ≥ 1.2 |
| `TRUE_DOWNTREND_AVOID` | Confirmed death cross + SMA200 falling + RS weak (default bad-chart fallback) |
| `BROKEN_SUPPORT_AVOID` | Heavy-volume break (dry-up > 1.5) + weak close + RSI falling |
| `WATCHLIST` | Score ≥ 50 but no buy gates met |

**Regime adjustments** (via `RegimeThresholds`):

| Regime | RSI range | SMA20 max | Rel-vol min | Notes |
|--------|-----------|-----------|-------------|-------|
| LIQUIDITY_RALLY | 55–74 | 8% | 1.2 | Relaxed — risk-on environment |
| BULL_RISK_ON | 55–68 | 5% | 1.3 | Standard thresholds |
| SIDEWAYS_CHOPPY | 40–58 | 3% | 1.3 | BUY_ON_PULLBACK checked first |
| BEAR_RISK_OFF | blocks all continuation | — | — | Only rebound/pullback allowed |
| BULL_NARROW_LEADERSHIP | 55–68 | 5% | 1.3 | Requires RS leader status |

### Medium-Term Labels

| Label | Trigger |
|-------|---------|
| `BUY_NOW` | Score ≥ 75 |
| `BUY_STARTER` | Score 65–74 |
| `BUY_ON_PULLBACK` | Score 55–64 |
| `WATCHLIST_NEEDS_CONFIRMATION` | Score 45–54 |
| `AVOID_BAD_BUSINESS` | Score < 45 |

### Long-Term Labels

| Label | Trigger |
|-------|---------|
| `BUY_NOW_LONG_TERM` | Score ≥ 75 |
| `ACCUMULATE_ON_WEAKNESS` | Score 60–74 |
| `WATCHLIST_VALUATION_TOO_RICH` | Score 45–59 |
| `AVOID_LONG_TERM` | Score < 45 |

---

## 7. Data Completeness & Confidence

```mermaid
flowchart LR
    subgraph Deductions["Completeness Deductions"]
        D1["No news items: -15"]
        D2["No options data: -15"]
        D3["No next earnings date: -10"]
        D4["No peer comparison: -5"]
        D5["Insufficient price history: -5"]
    end

    subgraph Rules["Confidence Rules"]
        R1["completeness < 60 → confidence_score capped at 60"]
        R2["completeness < 55 → decision forced to AVOID_LOW_CONFIDENCE"]
        R3["Full data → completeness = 100, confidence_score = 100"]
    end

    Deductions --> COMP["data_completeness_score\n(0–100)"]
    COMP --> Rules
    Rules --> REC["HorizonRecommendation\n.data_completeness_score\n.confidence_score\n.data_warnings"]
```

---

## 8. Signal Profile

Six human-readable signal dimensions derived from sub-scores, displayed as color-coded cards.

| Dimension | Labels | Source |
|-----------|--------|--------|
| `momentum` | VERY_BULLISH → VERY_BEARISH | technical_score + is_extended |
| `growth` | VERY_BULLISH → VERY_BEARISH | fundamental_score |
| `valuation` | ATTRACTIVE / FAIR / ELEVATED / RISKY | archetype_adjusted_score |
| `entry_timing` | IDEAL / ACCEPTABLE / EXTENDED / VERY_EXTENDED | is_extended + extension_pct |
| `sentiment` | VERY_BULLISH → VERY_BEARISH | news_score |
| `risk_reward` | EXCELLENT / GOOD / ACCEPTABLE / POOR | (earnings_score + technical_score) / 2 |

---

## 9. Risk Management Output

```mermaid
flowchart LR
    subgraph Inputs
        PR["Current Price"]
        SR["Support / Resistance\nLevels"]
        DEC["Decision label"]
        RP["Risk Profile\nconservative / moderate / aggressive"]
        EW["Earnings within 30d?"]
        ATR["ATR (Average True Range)\n+ ATR%"]
    end

    subgraph RiskMgmt["RiskManagementService"]
        EP["EntryPlan\n─────────────\npreferred_entry\nstarter_entry\nbreakout_entry\navoid_above"]
        EXP["ExitPlan\n─────────────\nstop_loss (ATR-based when available)\ninvalidation_level\nfirst_target\nsecond_target"]
        RR["RiskReward\n─────────────\ndownside %\nupside %\nratio (≥ 2.0 for BUY)"]
        PS["PositionSizing\n─────────────\nstarter % of full\nmax portfolio %\nConservative: 15% / 3%\nModerate:     25% / 5%\nAggressive:   40% / 8%\nEarnings halving applies\nATR% multiplier: <4%=1.0x, 4–7%=0.55x, >7%=0.30x"]
    end

    subgraph ATRStops["ATR-Based Stops"]
        ATRST["Short-term:  entry − 1.5 × ATR\nMedium-term: entry − 2.0 × ATR\nLong-term:   entry − 2.5 × ATR\n(falls back to support-based when ATR unavailable)"]
    end

    Inputs --> RiskMgmt
    RiskMgmt --> EP
    RiskMgmt --> EXP
    RiskMgmt --> RR
    RiskMgmt --> PS
    ATR --> ATRStops
    ATRStops --> EXP
```

---

## 10. Frontend Component Tree

```mermaid
flowchart TD
    App["App.tsx"]
    App --> Dash["Dashboard.tsx\nState: ticker, riskProfile, result, loading, error"]

    Dash -->|"POST /api/stocks/analyze"| API["stockApi.ts\naxios wrapper"]

    Dash --> RAB["RegimeArchetypeBar.tsx\nArchetype badge (color by type)\nRegime badge (green/red/yellow dot)\nConfidence % shown on each"]

    Dash --> DW["DataWarnings.tsx\nYellow warning panel\nfor missing data flags"]

    Dash --> SPC["SignalProfileCard.tsx\n6 color-coded signal cells:\nMomentum · Growth · Valuation\nEntry Timing · Sentiment · Risk/Reward"]

    Dash --> SCG2["SignalCardsGrid.tsx\n11 signal cards in responsive grid\nScore gauge · Label badge · Expand factors"]
    SCG2 --> SCard["SignalCard.tsx\nScore bar · BULLISH/BEARISH label\nTop positives / negatives / missing data"]

    Dash --> RC["RecommendationCard.tsx × 3\nNew per-horizon decision labels\nScore bar · Confidence bar\nData completeness bar\nBullish/bearish factors\nEntry / Exit / R/R plan"]

    Dash --> PT2["PerformanceTable.tsx\n1W/1M/3M/6M/YTD/1Y/3Y/5Y returns\nMax drawdown 3M / 1Y"]

    Dash --> SB["ScoreBreakdown.tsx\nHorizontal bar chart\nper sub-score dimension"]

    Dash --> TCH["TechnicalChart.tsx\nMA table · RSI · MACD\nVolume · Trend · RS\nSupport / Resistance levels"]

    Dash --> Fund["Fundamental Quality\n(inline grid)\n+ROA, ROIC, ROE, quick ratio\n+LT D/E, net margin, rev QoQ\n+dividend yield"]

    Dash --> Val["Valuation\n(inline grid)\n+EV/Sales, P/Book, P/Cash\n+analyst target distance"]

    Dash --> OPN["OwnershipPanel.tsx\nInsider/inst ownership + transactions\nShort float · Analyst rec · Target dist"]

    Dash --> VPN["VolumePanel.tsx\nOBV/A/D trend · CMF · VWAP dev\nUp/down vol · Vol dry-up · Breakout vol"]

    Dash --> Earn["Earnings\n(inline grid)"]

    Dash --> NS["NewsSection.tsx\nPositive / Negative / Neutral\nnews lists with badges"]

    Dash --> MRP["MarkdownReport.tsx\nCollapsible details element\nreact-markdown renderer\n(now includes signal cards table)"]
```

---

## 11. Data Model

```mermaid
classDiagram
    class StockAnalysisRequest {
        +str ticker
        +list~str~ horizons
        +str risk_profile
        +float max_position_percent
        +float max_loss_percent
    }

    class StockAnalysisResult {
        +str ticker
        +str generated_at
        +float current_price
        +DataQualityReport data_quality
        +MarketData market_data
        +TechnicalIndicators technicals
        +FundamentalData fundamentals
        +ValuationData valuation
        +EarningsData earnings
        +NewsSummary news
        +SignalCards signal_cards
        +list~HorizonRecommendation~ recommendations
        +str markdown_report
        +str archetype
        +float archetype_confidence
        +str market_regime
        +float regime_confidence
        +SignalProfile signal_profile
    }

    class SignalCard {
        +str name
        +float score
        +str label
        +str explanation
        +list~str~ top_positives
        +list~str~ top_negatives
        +list~str~ missing_data_warnings
    }

    class SignalCards {
        +SignalCard momentum
        +SignalCard trend
        +SignalCard entry_timing
        +SignalCard volume_accumulation
        +SignalCard volatility_risk
        +SignalCard relative_strength
        +SignalCard growth
        +SignalCard valuation
        +SignalCard quality
        +SignalCard ownership
        +SignalCard catalyst
    }

    class SignalProfile {
        +str momentum
        +str growth
        +str valuation
        +str entry_timing
        +str sentiment
        +str risk_reward
    }

    class MarketRegimeAssessment {
        +str regime
        +float confidence
        +str implication
        +bool spy_above_50dma
        +bool spy_above_200dma
        +bool qqq_above_200dma
        +float vix_level
    }

    class HorizonRecommendation {
        +str horizon
        +str decision
        +float score
        +str confidence
        +float confidence_score
        +float data_completeness_score
        +str summary
        +list~str~ bullish_factors
        +list~str~ bearish_factors
        +EntryPlan entry_plan
        +ExitPlan exit_plan
        +RiskReward risk_reward
        +PositionSizing position_sizing
        +list~str~ data_warnings
        +dict signal_cards_weights
    }

    class FundamentalData {
        +float revenue_ttm
        +float revenue_growth_yoy
        +float revenue_growth_qoq
        +float gross_margin
        +float operating_margin
        +float net_margin
        +float free_cash_flow
        +float net_debt
        +float debt_to_equity
        +float long_term_debt_equity
        +float current_ratio
        +float quick_ratio
        +float roe
        +float roic
        +float roa
        +float eps_growth_ttm
        +float eps_growth_3y
        +float eps_growth_5y
        +float sales_growth_3y
        +float insider_ownership
        +float insider_transactions
        +float institutional_ownership
        +float short_float
        +float analyst_recommendation
        +float target_price_distance
        +float dividend_yield
        +str sector
        +float beta
        +str archetype
        +float archetype_confidence
        +float fundamental_score
    }

    class ValuationData {
        +float trailing_pe
        +float forward_pe
        +float peg_ratio
        +float price_to_sales
        +float ev_to_ebitda
        +float price_to_fcf
        +float fcf_yield
        +float ev_sales
        +float price_to_book
        +float price_to_cash
        +float valuation_score
        +float archetype_adjusted_score
    }

    StockAnalysisResult "1" --> "1" SignalCards
    StockAnalysisResult "1" --> "1" SignalProfile
    StockAnalysisResult "1" --> "1" MarketRegimeAssessment : via regime fields
    StockAnalysisResult "1" --> "1" FundamentalData
    StockAnalysisResult "1" --> "1" ValuationData
    StockAnalysisResult "1" --> "3" HorizonRecommendation
    SignalCards "1" --> "11" SignalCard
```

---

## 12. Caching Strategy

```mermaid
flowchart LR
    subgraph Incoming["Incoming Request"]
        REQ["GET /analyze\n{ticker}"]
    end

    subgraph Cache["TTLCache (cachetools)"]
        PC["Price Cache\nKey: (ticker, period, interval)\nTTL: 15 minutes"]
        FC["Fundamental Cache\nKey: fundamental:{ticker}\nTTL: 24 hours"]
    end

    subgraph Origin["Origin: yfinance"]
        YF["Yahoo Finance API\n(rate-limited, 429-prone)"]
    end

    subgraph Retry["Retry Policy (tenacity)"]
        EXP["Exponential backoff\nmin=2s, max=30s\n3 attempts\n+ random jitter"]
    end

    REQ --> PC
    PC -->|"HIT"| RESP["Serve from cache"]
    PC -->|"MISS"| EXP
    EXP --> YF
    YF -->|"429 Too Many Requests"| EXP
    YF -->|"200 OK"| PC
    PC --> RESP

    REQ --> FC
    FC -->|"HIT"| RESP
    FC -->|"MISS"| YF
```

---

## 13. Backtest Architecture

```mermaid
flowchart TD
    subgraph CLI["CLI Entry Point"]
        RUN["run_backtest.py\n--tickers --start --end --risk-profile"]
    end

    subgraph DataLoader["Phase 1 · Data Pre-loader (data_loader.py)"]
        FETCH["Fetch 3-year daily price history\nfor all tickers + SPY + QQQ + sector ETFs"]
        QFETCH["Fetch quarterly statements\nincome · balance · cashflow\nearnings_history · earnings_dates"]
        DISK["Disk cache\nbacktest_results/cache/\nprices.pkl · quarterly.pkl"]
    end

    subgraph Runner["Phase 2 · Weekly Loop (runner.py)"]
        DATES["Generate weekly Mondays\n2024-05-06 → 2026-05-04\n~105 test dates"]
        SNAP["Snapshot Builder (snapshot.py)\nSlice price to test_date\nFilter quarterly stmts by date\nBuild FundamentalData · ValuationData · EarningsData"]
        ARCH2["classify_and_attach() → archetype\nscore_valuation_with_archetype()"]
        REG2["classify_regime(spy, qqq, vix=20)\n→ MarketRegimeAssessment"]
        SMAC2["compute_relative_strength(sector, spy, 63d)\n→ sector_macro_score (real RS)"]
        PIPE["Production Pipeline\ncompute_technicals()\ncompute_scores(regime_assessment)\nbuild_recommendations(regime_assessment)"]
        SIG["Signal Record\nticker · date · horizon\ndecision · score · archetype · market_regime\nprice · sub-scores · entry/stop/target\nforward_return · spy_return · qqq_return\nexcess_return · excess_return_vs_qqq"]
    end

    subgraph Outcome["Phase 3 · Outcome Evaluator (outcome.py)"]
        FWD["Look up exit price\nat date + N trading days\nshort: 20d · medium: 65d · long: 252d"]
        RET["Compute\nforward_return %\nspy_return %\nqqq_return %\nexcess_return vs SPY\nexcess_return_vs_qqq"]
    end

    subgraph Metrics["Phase 4 · Metrics (metrics.py)"]
        BD["by_decision (14 labels)\nwin rate · avg return · vs SPY"]
        BSB["by_score_bucket\n0–40 · 40–55 · 55–70 · 70–85 · 85–100"]
        BT["by_ticker\nper-ticker win rate + alpha"]
        BRG["by_regime\nBULL_RISK_ON / BEAR_RISK_OFF / …\nwin rate · avg_return · excess_vs_qqq"]
        BAT["by_archetype\nHYPER_GROWTH / MATURE_VALUE / …\nwin rate · avg_score · best_decision"]
        MB["monthly_breakdown\ntime-series of model accuracy"]
        SIM["portfolio_simulation\nBUY signals vs SPY buy-and-hold\n+ QQQ comparison"]
    end

    subgraph Output["Phase 5 · Report (report.py)"]
        CSV["raw_signals.csv\nsummary_by_decision.csv\nsummary_by_ticker.csv"]
        HTML["report.html\nSelf-contained · Embedded matplotlib charts"]
        JSON["report.json\nFull metrics as JSON\nIncludes by_regime + by_archetype"]
    end

    CLI --> DataLoader
    FETCH --> DISK
    QFETCH --> DISK
    DISK --> Runner
    DATES --> Runner
    Runner --> SNAP
    SNAP --> ARCH2
    ARCH2 --> REG2
    REG2 --> SMAC2
    SMAC2 --> PIPE
    PIPE --> SIG
    SIG --> Outcome
    FWD --> RET
    RET --> Metrics
    Metrics --> Output
```

---

## 14. Look-Ahead Bias Prevention (Backtest)

```mermaid
flowchart LR
    subgraph TestDate["Test Date: 2024-09-02"]
        direction TB
        PRICE["✅ Price history sliced\ndf[df.index ≤ 2024-09-02]"]
        SPY2["✅ SPY + QQQ sliced\nsame cutoff"]
        QSTMT["✅ Quarterly statements filtered\nonly columns (quarters) filed ≤ 2024-09-02"]
        EHIST["✅ Earnings history filtered\nonly records reported ≤ 2024-09-02"]
        NEWS2["⚠️ News sentiment\nNo historical data → default 50 (neutral)"]
        OPTS["⚠️ Options catalyst\nNo historical data → default 50 (neutral)"]
        REGIME3["⚠️ VIX level\nProxy 20.0 (flat) — no historical VIX in backtest"]
    end

    subgraph Engine["Analysis Engine\n(unchanged from production)"]
        TECH2["compute_technicals()"]
        ARCH3["classify_and_attach()"]
        SCORE2["compute_scores(regime)"]
        RECS["build_recommendations(regime)"]
    end

    PRICE --> TECH2
    SPY2 --> TECH2
    QSTMT --> ARCH3
    ARCH3 --> SCORE2
    EHIST --> SCORE2
    NEWS2 --> SCORE2
    OPTS --> SCORE2
    TECH2 --> SCORE2
    SCORE2 --> RECS
```

---

## 15. API Reference

```mermaid
flowchart LR
    subgraph Endpoints["REST API  (base: /api/stocks)"]
        A["POST /analyze\nFull analysis — all providers + scoring + report\nBody: {ticker, horizons, risk_profile}\nResponse: StockAnalysisResult\n(includes archetype, market_regime, signal_profile)"]
        B["GET /{ticker}/report\nMarkdown report only\nResponse: {ticker, report}"]
        C["GET /{ticker}/technicals\nTechnical indicators only\nResponse: TechnicalIndicators"]
        D["GET /{ticker}/news\nNews + sentiment only\nResponse: NewsSummary"]
        E["GET /health → {status: ok}"]
    end

    subgraph Client["Frontend"]
        FE2["stockApi.ts\naxios · /api proxied to :8000"]
    end

    FE2 -->|"Primary call"| A
    FE2 -.->|"Optional"| B
    FE2 -.->|"Optional"| C
    FE2 -.->|"Optional"| D
```

---

## 16. Technology Stack

```mermaid
mindmap
  root((Stock Decision Tool))
    Backend
      Python 3.12
      FastAPI + uvicorn
      yfinance 0.2.50
      pandas + pandas-ta
      OpenAI SDK GPT-4o-mini
      cachetools TTLCache
      tenacity retry
      pydantic v2
      algo_config.json — centralized parameter store
    Frontend
      React 18 + TypeScript
      Vite 5
      Tailwind CSS v4
      recharts
      react-markdown
      axios
    Backtest
      yfinance historical data
      QQQ + SPY benchmark comparison
      by_regime + by_archetype metrics
      matplotlib charts
      pandas DataFrames
      Pickle disk cache
    Infrastructure
      No database
      In-memory cache only
      No Docker required
      Local dev only
```

---

## 17. Algorithm Configuration System

All tunable algorithm parameters are stored in `backend/algo_config.json` and loaded via `app/algo_config.py`. No parameter values are hardcoded in service modules.

```mermaid
flowchart LR
    subgraph Config["algo_config.json (12 sections)"]
        TI["technical_indicators\nRSI, MACD, ATR, MA periods"]
        TS["technical_scoring\nBonus/penalty thresholds"]
        SM["scoring\nSignal card weights per horizon"]
        DL["decision_logic\nGate values for BUY/AVOID labels"]
        RM["risk_management\nATR multipliers, sizing factors"]
        MR["market_regime\nVIX thresholds, regime confidences"]
        SC["signal_cards\nPer-card scoring thresholds"]
        VA["valuation\nArchetype-adjusted score thresholds"]
        DC["data_completeness\nDeduction amounts, confidence caps"]
        SA["stock_archetype\nClassification rules for 8 archetypes"]
        EX["extension_detection\nSMA extension % thresholds"]
        RS["regime_scoring\nScore multipliers per regime"]
    end

    subgraph Loader["app/algo_config.py"]
        AC["AlgoConfig class\n─────────────\nfrom_file(path) — load JSON\nfrom_dict(data) — inline dict\nget_algo_config() — singleton\nreset_algo_config() — test util"]
        ENV["ALGO_CONFIG_PATH env var\noverrides default path"]
    end

    subgraph Services["Analysis Services"]
        SVC["Each service function accepts\nalgo_config: Optional[AlgoConfig] = None\n(falls back to singleton if None)"]
    end

    Config --> Loader
    ENV --> Loader
    Loader --> Services
```

**Key design properties:**
- All service functions accept `algo_config` as an optional parameter — backward-compatible with callers that pass nothing
- Default singleton loaded from `algo_config.json` on first call; override via `ALGO_CONFIG_PATH`
- Tests inject custom configs via `AlgoConfig.from_dict({...})` for isolated parameter testing
- `reset_algo_config()` clears the singleton between tests when `ALGO_CONFIG_PATH` changes

See `backend/ALGO_PARAMS.md` for a full parameter catalog with descriptions, types, and sensitivity notes.

---

## 18. Known Limitations & Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **In-memory TTLCache** (no Redis) | Zero infra dependency for MVP | Cache lost on server restart; not shared across workers |
| **yfinance for all data** | Free, no API key required | Rate-limited (HTTP 429); limited news coverage; no historical options data |
| **OpenAI optional** | Tool works without API key (keyword fallback) | Keyword classifier is less accurate than GPT-4o-mini |
| **Sector macro score from real RS** | 6-month RS of sector ETF vs SPY — replaces static 50 | Threshold-based (65/50/35), not continuous |
| **Archetype defaults to PROFITABLE_GROWTH** | Safest fallback when data is ambiguous | May underweight hyper-growth signals for borderline cases |
| **VIX proxy = 20.0 in backtest** | No historical VIX available without a paid source | Regime classification in backtest is less accurate than production |
| **No peer comparison** | yfinance doesn't support sector-level P/E comparison | Flags in data quality warnings; -5 completeness deduction |
| **Growth-adjusted valuation (archetype-aware)** | Prevents NVDA/PLTR/AVGO from being penalised by raw P/E | HYPER_GROWTH stocks now score fairly; MATURE_VALUE scored conservatively |
| **Backtest news/options = 50** | No historical news sentiment or options data available | Short-term backtest accuracy understated |
| **No database** | Simplicity; all state in HTTP response | No history, no user accounts, stateless |
| **5Y growth rates from yfinance** | `ticker.info` fields inconsistently available | Many stocks will show null for `eps_growth_5y`, `sales_growth_5y`; scored as missing data |
| **Anchored VWAP requires earnings date** | Fetched from EarningsProvider best-effort | Falls back to null when earnings date unavailable |
| **Return percentile ranks are self-relative** | Rank stock's return vs its own 252D window | Not a true cross-sectional rank vs all US stocks |
