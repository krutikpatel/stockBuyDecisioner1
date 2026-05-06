# High Level Design — Stock Decision Tool

---

## 1. System Overview

The Stock Decision Tool is a full-stack application that evaluates any US-listed stock or ETF across three investment horizons (short / medium / long term) and returns a structured recommendation backed by technical, fundamental, valuation, earnings, sentiment, archetype, and market-regime analysis.

```mermaid
C4Context
  title System Context

  Person(user, "Investor", "Enters a ticker and risk profile, reviews structured recommendation")

  System(frontend, "React Frontend", "Dashboard UI — ticker input, recommendation cards, signal profile, regime/archetype badges, charts, markdown report")
  System(backend, "FastAPI Backend", "Analysis engine — archetype classification, regime detection, growth-adjusted valuation, regime-aware scoring, 14-label decision logic, risk management")

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
        RC["RecommendationCard\n14 decision labels · Completeness bars"]
        SC["ScoreBreakdown"]
        TC["TechnicalChart"]
        NW["NewsSection"]
        MR["MarkdownReport"]
    end

    subgraph API["FastAPI Backend (Python 3.12)"]
        Router["POST /api/stocks/analyze\nGET /report · /technicals · /news\nGET /health"]

        subgraph Providers["Data Providers"]
            MP["MarketDataProvider\nyfinance OHLCV + retry"]
            FP["FundamentalProvider\nyfinance .info + statements\n(sector, beta added)"]
            EP["EarningsProvider\nearnings_history + dates"]
            NP["NewsProvider\nyfinance .news"]
            OP["OptionsProvider\noption_chain(nearest_expiry)"]
        end

        subgraph Services["Analysis Services"]
            TA["TechnicalAnalysisService\nMAs · RSI · MACD · ATR\nTrend · Extension · S/R · RS"]
            FA["FundamentalAnalysisService\nRevenue · Margins · FCF · Debt · ROE"]
            AS["StockArchetypeService\nClassify: HYPER_GROWTH / MATURE_VALUE\n/ DEFENSIVE / CYCLICAL / etc."]
            VA["ValuationAnalysisService\nscore_valuation() — generic\nscore_valuation_with_archetype() — growth-adjusted"]
            MR2["MarketRegimeService\nBULL_RISK_ON / BEAR_RISK_OFF\n/ SIDEWAYS_CHOPPY / etc.\nApplies regime weight multipliers"]
            NS["NewsSentimentService\nOpenAI GPT-4o-mini\n(keyword fallback)"]
            DC["DataCompletenessService\nScores 0–100 per gap\nCaps confidence when data thin"]
            SS["ScoringService\nHorizon-specific weights\n+ regime multipliers"]
            RS["RecommendationService\n14 decision labels\nRegime-aware overrides"]
            SP["SignalProfileService\n6 signal dimensions"]
            RM["RiskManagementService\nEntry · Stop-loss · Target · R/R"]
            MDS["MarkdownReportService\nFull structured report"]
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
        TECH["Technical Analysis\n─────────────\nMA(10/20/50/100/200)\nRSI(14), MACD, ATR\nTrend classification\nExtension detection\nSupport / Resistance\nVolume trend\nRS vs SPY + Sector\n→ technical_score 0–100"]

        ARCH["Stock Archetype\n─────────────\nHYPER_GROWTH\nPROFITABLE_GROWTH\nCYCLICAL_GROWTH\nMATURE_VALUE\nTURNAROUND\nSPECULATIVE_STORY\nDEFENSIVE\nCOMMODITY_CYCLICAL"]

        REG["Market Regime\n─────────────\nBULL_RISK_ON\nBULL_NARROW_LEADERSHIP\nSIDEWAYS_CHOPPY\nBEAR_RISK_OFF\nSECTOR_ROTATION\nLIQUIDITY_RALLY\n→ confidence + implication"]

        FUND["Fundamental Analysis\n─────────────\nRevenue growth YoY/QoQ\nGross / Op / Net margin\nFree cash flow\nNet debt\nDebt-to-equity, ROE\n→ fundamental_score 0–100"]

        VAL["Valuation Analysis\n─────────────\nTrailing P/E, Forward P/E\nPEG (calculated)\nPrice/Sales, EV/EBITDA\nP/FCF, FCF Yield\nscore_valuation() — generic\nscore_valuation_with_archetype()\n→ archetype_adjusted_score 0–100"]

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

```mermaid
flowchart TB
    subgraph SubScores["Intermediate Scores (derived per horizon)"]
        TM["technical_momentum\n= technical_score"]
        RS2["relative_strength\n= technical_score"]
        CN["catalyst_news\n= (catalyst + news) / 2"]
        OF["options_flow\n= catalyst_score"]
        MRG["market_regime\n= f(regime, confidence)"]
        RR["risk_reward\n= risk_reward_score"]
        ER["earnings_revision\n= earnings_score"]
        GA["growth_acceleration\n= fundamental_score"]
        TT["technical_trend\n= technical_score"]
        SS2["sector_strength\n= sector_macro_score (real RS)"]
        VRG["valuation_relative_growth\n= archetype_adjusted_score\n  (fallback: valuation_score)"]
        BQ["business_quality\n= fundamental_score"]
        GD["growth_durability\n= fundamental_score"]
        FQ["fcf_quality\n= fundamental_score"]
        BS2["balance_sheet_strength\n= fundamental_score"]
        CM["competitive_moat\n= fundamental_score"]
    end

    subgraph Weights["Horizon-Specific Weights (each sums to 100)"]
        direction TB
        STW["Short-Term\n─────────────\ntechnical_momentum   30%\nrelative_strength    20%\ncatalyst_news        20%\noptions_flow         10%\nmarket_regime        10%\nrisk_reward          10%"]

        MTW["Medium-Term\n─────────────\nearnings_revision         25%\ngrowth_acceleration       20%\ntechnical_trend           20%\nsector_strength           15%\nvaluation_relative_growth 10%\ncatalyst_news             10%"]

        LTW["Long-Term\n─────────────\nbusiness_quality          25%\ngrowth_durability         20%\nfcf_quality               15%\nbalance_sheet_strength    15%\nvaluation_relative_growth 15%\ncompetitive_moat          10%"]
    end

    subgraph RegimeAdjust["Regime Multipliers (applied before composite)"]
        BULL["BULL_RISK_ON\ntechnical_momentum ×1.20\nrelative_strength ×1.15\nvaluation_relative_growth ×0.70"]
        BEAR["BEAR_RISK_OFF\nvaluation_relative_growth ×1.30\nbalance_sheet_strength ×1.25\ntechnical_momentum ×0.90"]
        SIDE["SIDEWAYS_CHOPPY\nmarket_regime ×1.25\nrisk_reward ×1.25"]
    end

    subgraph Composites["Composite Scores (0–100)"]
        STC["short_term composite"]
        MTC["medium_term composite"]
        LTC["long_term composite"]
    end

    SubScores --> RegimeAdjust
    RegimeAdjust --> STW --> STC
    RegimeAdjust --> MTW --> MTC
    RegimeAdjust --> LTW --> LTC
```

---

## 6. Decision Logic

All 14 decision labels. Regime and data-quality overrides fire before threshold logic.

```mermaid
flowchart TD
    INPUT["Composite Score\n+ TechnicalIndicators\n+ FundamentalData\n+ EarningsData\n+ MarketRegimeAssessment\n+ data_completeness_score"]

    INPUT --> DQ{"data_completeness\n< 55?"}
    DQ -->|Yes| ALC["AVOID_LOW_CONFIDENCE ⬛"]
    DQ -->|No| CHART{"chart_is_weak?\ndowntrend + RS < 0.8"}
    CHART -->|Yes, score<55| ABC["AVOID_BAD_CHART 🔴"]
    CHART -->|No| BIZ{"business_deteriorating?\nrev<0 + (neg margin OR beat<40%)"}
    BIZ -->|Yes, score<55| ABB["AVOID_BAD_BUSINESS 🔴"]
    BIZ -->|No| EARN30{"within 30d earnings?\n55 ≤ score < 70?"}
    EARN30 -->|Yes| BAE["BUY_AFTER_EARNINGS 🔵"]
    EARN30 -->|No| REGIME_BR{"score ≥ 80 AND\nNOT extended?"}
    REGIME_BR -->|Yes, support exists| BN["BUY_NOW 🟢"]
    REGIME_BR -->|Yes, no support| BS["BUY_STARTER 🟢"]
    REGIME_BR -->|No| EXT{"extended AND\nscore ≥ 65?"}
    EXT -->|Yes, BULL regime| BSE["BUY_STARTER_EXTENDED 🟢"]
    EXT -->|Yes, non-bull| BOP["BUY_ON_PULLBACK 🟡"]
    EXT -->|No| SC2{"70 ≤ score < 80?"}
    SC2 -->|Yes| BS2["BUY_STARTER 🟢"]
    SC2 -->|No| SC3{"score ≥ 65?"}
    SC3 -->|Yes| BOP2["BUY_ON_PULLBACK 🟡"]
    SC3 -->|No| SC4{"score < 50?"}
    SC4 -->|Yes| AV["AVOID 🔴"]
    SC4 -->|No| WL["WATCHLIST ⚪"]
```

**Full label set (14):**

| Label | Color | Trigger |
|-------|-------|---------|
| `BUY_NOW` | 🟢 Green | Score ≥ 80, not extended, support exists |
| `BUY_STARTER` | 🟢 Emerald | Score 70–79, or ≥80 + extended |
| `BUY_STARTER_EXTENDED` | 🟢 Teal | Extended + score ≥ 65 + BULL regime |
| `BUY_ON_PULLBACK` | 🟡 Cyan | Extended + score ≥ 65 (non-bull) |
| `BUY_ON_BREAKOUT` | 🔵 Blue | Long-term only: ≥75 + extended |
| `BUY_AFTER_EARNINGS` | 🔵 Indigo | Earnings within 30d + 55 ≤ score < 70 |
| `WATCHLIST` | ⚪ Slate | 50 ≤ score < 65 |
| `WATCHLIST_NEEDS_CATALYST` | ⚪ Slate | Reserved for future use |
| `HOLD_EXISTING_DO_NOT_ADD` | 🟠 Orange | Reserved for position management |
| `AVOID_BAD_BUSINESS` | 🔴 Dark Red | Rev declining + neg margin or poor beat rate |
| `AVOID_BAD_CHART` | 🔴 Rose | Downtrend + RS vs SPY < 0.8 |
| `AVOID_BAD_RISK_REWARD` | 🔴 Red | Reserved |
| `AVOID_LOW_CONFIDENCE` | ⬛ Neutral | Data completeness < 55 |
| `AVOID` | 🔴 Red | Score < 50, no specific override |

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
        DEC["Decision (14 labels)"]
        RP["Risk Profile\nconservative / moderate / aggressive"]
        EW["Earnings within 30d?"]
    end

    subgraph RiskMgmt["RiskManagementService"]
        EP["EntryPlan\n─────────────\npreferred_entry\nstarter_entry\nbreakout_entry\navoid_above"]
        EXP["ExitPlan\n─────────────\nstop_loss\ninvalidation_level\nfirst_target\nsecond_target"]
        RR["RiskReward\n─────────────\ndownside %\nupside %\nratio (≥ 2.0 for BUY)"]
        PS["PositionSizing\n─────────────\nstarter % of full\nmax portfolio %\nConservative: 15% / 3%\nModerate:     25% / 5%\nAggressive:   40% / 8%\nEarnings halving applies"]
    end

    Inputs --> RiskMgmt
    RiskMgmt --> EP
    RiskMgmt --> EXP
    RiskMgmt --> RR
    RiskMgmt --> PS
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

    Dash --> RC["RecommendationCard.tsx × 3\nOne per horizon\n14 decision labels with distinct badge colors\nScore bar · Confidence bar\nData completeness bar\nPer-rec data warnings\nBullish/bearish factors\nEntry / Exit / R/R plan"]

    Dash --> SB["ScoreBreakdown.tsx\nHorizontal bar chart\nper sub-score dimension"]

    Dash --> TCH["TechnicalChart.tsx\nMA table · RSI · MACD\nVolume · Trend · RS\nSupport / Resistance levels"]

    Dash --> Fund["Fundamental Quality\n(inline grid)"]
    Dash --> Val["Valuation\n(inline grid)"]
    Dash --> Earn["Earnings\n(inline grid)"]

    Dash --> NS["NewsSection.tsx\nPositive / Negative / Neutral\nnews lists with badges"]

    Dash --> MRP["MarkdownReport.tsx\nCollapsible details element\nreact-markdown renderer"]
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
        +list~HorizonRecommendation~ recommendations
        +str markdown_report
        +str archetype
        +float archetype_confidence
        +str market_regime
        +float regime_confidence
        +SignalProfile signal_profile
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
    }

    class FundamentalData {
        +float revenue_ttm
        +float revenue_growth_yoy
        +float gross_margin
        +float operating_margin
        +float free_cash_flow
        +float net_debt
        +float debt_to_equity
        +float roe
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
        +float valuation_score
        +float archetype_adjusted_score
    }

    StockAnalysisResult "1" --> "1" SignalProfile
    StockAnalysisResult "1" --> "1" MarketRegimeAssessment : via regime fields
    StockAnalysisResult "1" --> "1" FundamentalData
    StockAnalysisResult "1" --> "1" ValuationData
    StockAnalysisResult "1" --> "3" HorizonRecommendation
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

## 17. Known Limitations & Design Decisions

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
