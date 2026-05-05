# High Level Design — Stock Decision Tool

---

## 1. System Overview

The Stock Decision Tool is a full-stack application that evaluates any US-listed stock or ETF across three investment horizons (short / medium / long term) and returns a structured **Buy / Wait / Avoid** recommendation backed by technical, fundamental, valuation, earnings, and sentiment analysis.

```mermaid
C4Context
  title System Context

  Person(user, "Investor", "Enters a ticker and risk profile, reviews structured recommendation")

  System(frontend, "React Frontend", "Dashboard UI — ticker input, recommendation cards, charts, markdown report")
  System(backend, "FastAPI Backend", "Analysis engine — technical indicators, scoring, decision logic, risk management")

  System_Ext(yfinance, "Yahoo Finance (yfinance)", "Price/OHLCV, fundamentals, earnings, options, news")
  System_Ext(openai, "OpenAI API", "GPT-4o-mini — news headline sentiment classification")

  Rel(user, frontend, "Enters ticker + risk profile, views results", "Browser")
  Rel(frontend, backend, "POST /api/stocks/analyze", "HTTP/JSON")
  Rel(backend, yfinance, "Fetches market data, financials, news, options", "yfinance SDK / Yahoo Finance API")
  Rel(backend, openai, "Classifies news sentiment", "OpenAI Python SDK (optional)")
```

---

## 2. High-Level Architecture

```mermaid
flowchart TB
    subgraph Browser["Browser (React + TypeScript + Vite)"]
        UI["Dashboard.tsx\nTicker input · Risk profile · Results"]
        RC["RecommendationCard"]
        SC["ScoreBreakdown"]
        TC["TechnicalChart"]
        NW["NewsSection"]
        MR["MarkdownReport"]
    end

    subgraph API["FastAPI Backend (Python 3.12)"]
        Router["POST /api/stocks/analyze\nGET /report · /technicals · /news\nGET /health"]

        subgraph Providers["Data Providers"]
            MP["MarketDataProvider\nyfinance OHLCV + retry"]
            FP["FundamentalProvider\nyfinance .info + statements"]
            EP["EarningsProvider\nearnings_history + dates"]
            NP["NewsProvider\nyfinance .news"]
            OP["OptionsProvider\noption_chain(nearest_expiry)"]
        end

        subgraph Services["Analysis Services"]
            TA["TechnicalAnalysisService\nMAs · RSI · MACD · ATR\nTrend · Extension · S/R · RS"]
            FA["FundamentalAnalysisService\nRevenue · Margins · FCF · Debt · ROE"]
            VA["ValuationAnalysisService\nP/E · PEG · P/S · EV/EBITDA · P/FCF"]
            NS["NewsSentimentService\nOpenAI GPT-4o-mini\n(keyword fallback)"]
            SS["ScoringService\nHorizon-weighted composite"]
            RS["RecommendationService\nDecision rules → BUY/WAIT/AVOID"]
            RM["RiskManagementService\nEntry · Stop-loss · Target · R/R"]
            MDS["MarkdownReportService\nFull structured report"]
        end

        Cache["TTLCache\n15 min price · 24 h fundamentals"]
    end

    subgraph External["External Data Sources"]
        YF["Yahoo Finance\n(yfinance)"]
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
    participant EP as EarningsProvider
    participant NP as NewsProvider
    participant OP as OptionsProvider
    participant NS as NewsSentiment
    participant SS as ScoringService
    participant RS as RecommendationService
    participant RM as RiskManagement
    participant MD as MarkdownReport

    User->>FE: Enter ticker + risk profile → click Analyze
    FE->>API: POST /api/stocks/analyze {ticker, risk_profile}

    API->>MP: get_market_data(ticker) → MarketData + current_price
    API->>MP: get_history(ticker, 1y) → OHLCV DataFrame
    API->>MP: get_history(SPY, 1y) → SPY DataFrame
    API->>MP: get_history(sector_ETF, 1y) → sector DataFrame

    API->>TA: compute_technicals(df, spy_df, sector_df) → TechnicalIndicators

    API->>FP: get_fundamental_data(ticker) → FundamentalData
    API->>FP: get_valuation_data(ticker) → ValuationData

    API->>EP: get_earnings_data(ticker) → EarningsData

    API->>NP: get_news_items(ticker) → list[NewsItem]
    API->>NS: classify_news(items) → NewsSummary (GPT-4o-mini or keyword)

    API->>OP: get_options_snapshot(ticker) → put/call ratio → catalyst_score

    API->>SS: compute_scores(technicals, fundamentals, valuation, earnings, news, catalyst_score) → scores{short/medium/long}

    loop for each horizon
        API->>RS: build_recommendations(..., scores, horizon) → HorizonRecommendation
        RS->>RM: compute_risk_management(price, technicals, decision, risk_profile)
        RM-->>RS: EntryPlan · ExitPlan · RiskReward · PositionSizing
    end

    API->>MD: generate_markdown(result) → markdown_report string
    API-->>FE: StockAnalysisResult (JSON)
    FE-->>User: Renders cards, charts, markdown report
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
        SPY["SPY History\n(benchmark)"]
        SEC["Sector ETF History"]
        INFO["ticker.info\n(snapshot)"]
        STMT["Quarterly Statements\n(income, balance, cashflow)"]
        EH["Earnings History\n+ next date"]
        NEWS["News Headlines\n(yfinance.news)"]
        OPT["Option Chain\n(nearest expiry)"]
    end

    subgraph AnalysisLayer["Analysis Layer"]
        TECH["Technical Analysis\n─────────────\nMA(10/20/50/100/200)\nRSI(14), MACD, ATR\nTrend classification\nExtension detection\nSupport / Resistance\nVolume trend\nRS vs SPY + Sector\n→ technical_score 0–100"]

        FUND["Fundamental Analysis\n─────────────\nRevenue growth YoY/QoQ\nGross / Op / Net margin\nFree cash flow\nNet debt\nDebt-to-equity, ROE\n→ fundamental_score 0–100"]

        VAL["Valuation Analysis\n─────────────\nTrailing P/E, Forward P/E\nPEG (calculated)\nPrice/Sales\nEV/EBITDA\nP/FCF, FCF Yield\n→ valuation_score 0–100"]

        EARN["Earnings Analysis\n─────────────\nBeat rate (last 8 qtrs)\nAvg EPS surprise %\nNext earnings < 30d?\n→ earnings_score 0–100"]

        SENT["Sentiment Analysis\n─────────────\nGPT-4o-mini per headline\n→ positive/neutral/negative\n→ news_score 0–100"]

        CAT["Catalyst Signal\n─────────────\nPut/call ratio\nPCR < 0.7 → score 65\nPCR > 1.3 → score 35\nelse → score 50"]
    end

    T --> DataLayer
    PH --> TECH
    SPY --> TECH
    SEC --> TECH
    INFO --> FUND
    INFO --> VAL
    STMT --> FUND
    STMT --> VAL
    EH --> EARN
    NEWS --> SENT
    OPT --> CAT
```

---

## 5. Scoring System

```mermaid
flowchart TB
    subgraph SubScores["Sub-Scores (0–100 each)"]
        TS["technical_score"]
        FS["fundamental_score"]
        VS["valuation_score"]
        ES["earnings_score"]
        NS["news_score"]
        CS["catalyst_score"]
        SM["sector_macro_score\n(static: 50)"]
        RR["risk_reward_score"]
    end

    subgraph Weights["Horizon-Specific Weights"]
        direction TB
        STW["Short-Term\n─────────────\nTechnical     35%\nCatalyst      20%\nNews          15%\nRisk/Reward   15%\nSector/Macro  10%\nFundamental    5%"]

        MTW["Medium-Term\n─────────────\nFundamental   25%\nEarnings      25%\nTechnical     20%\nValuation     15%\nCatalyst      10%\nRisk/Reward    5%"]

        LTW["Long-Term\n─────────────\nFundamental   35%\nValuation     20%\nEarnings      15%\nRisk/Reward   10%\nSector/Macro  10%\nTechnical      5%\nNews           5%"]
    end

    subgraph Composites["Composite Scores"]
        STC["short_term\ncomposite 0–100"]
        MTC["medium_term\ncomposite 0–100"]
        LTC["long_term\ncomposite 0–100"]
    end

    SubScores --> STW --> STC
    SubScores --> MTW --> MTC
    SubScores --> LTW --> LTC
```

---

## 6. Decision Logic

```mermaid
flowchart TD
    SC["Composite Score\n+ TechnicalIndicators"]

    SC --> ST["Short-Term\nDecision"]
    SC --> MT["Medium-Term\nDecision"]
    SC --> LT["Long-Term\nDecision"]

    ST --> ST1{"score ≥ 80\nAND NOT extended?"}
    ST1 -->|Yes| ST2{"nearest_support\nexists?"}
    ST2 -->|Yes| BN1["BUY_NOW 🟢"]
    ST2 -->|No| BS1["BUY_STARTER 🟢"]
    ST1 -->|No| ST3{"extended AND\nscore ≥ 65?"}
    ST3 -->|Yes| WP1["WAIT_FOR_PULLBACK 🟡"]
    ST3 -->|No| ST4{"70 ≤ score < 80?"}
    ST4 -->|Yes| BS2["BUY_STARTER 🟢"]
    ST4 -->|No| ST5{"score ≥ 65?"}
    ST5 -->|Yes| WP2["WAIT_FOR_PULLBACK 🟡"]
    ST5 -->|No| ST6{"score < 50?"}
    ST6 -->|Yes| AV1["AVOID 🔴"]
    ST6 -->|No| WL1["WATCHLIST ⚪"]

    MT --> MT1{"score ≥ 82\nAND NOT extended?"}
    MT1 -->|Yes| BN2["BUY_NOW 🟢"]
    MT1 -->|No| MT2{"72 ≤ score < 82\nOR (≥82 + extended)?"}
    MT2 -->|Yes| BS3["BUY_STARTER 🟢"]
    MT2 -->|No| MT3{"score ≥ 68?"}
    MT3 -->|Yes| WP3["WAIT_FOR_PULLBACK 🟡"]
    MT3 -->|No| MT4{"55 ≤ score < 68?"}
    MT4 -->|Yes| WL2["WATCHLIST ⚪"]
    MT4 -->|No| AV2["AVOID 🔴"]

    LT --> LT1{"score ≥ 85\nAND NOT extended?"}
    LT1 -->|Yes| BN3["BUY_NOW 🟢"]
    LT1 -->|No| LT2{"75 ≤ score < 85?"}
    LT2 -->|Yes| BS4["BUY_STARTER 🟢"]
    LT2 -->|No| LT3{"≥75 + extended?"}
    LT3 -->|Yes| BOB["BUY_ON_BREAKOUT 🔵"]
    LT3 -->|No| LT4{"60 ≤ score < 75?"}
    LT4 -->|Yes| WL3["WATCHLIST ⚪"]
    LT4 -->|No| AV3["AVOID 🔴"]
```

---

## 7. Risk Management Output

```mermaid
flowchart LR
    subgraph Inputs
        PR["Current Price"]
        SR["Support / Resistance\nLevels"]
        DEC["Decision\n(BUY_NOW / BUY_STARTER / …)"]
        RP["Risk Profile\nconservative / moderate / aggressive"]
        EW["Earnings within 30d?"]
    end

    subgraph RiskMgmt["RiskManagementService"]
        EP["EntryPlan\n─────────────\npreferred_entry\nstarter_entry\nbreakout_entry\navoid_above"]
        EXP["ExitPlan\n─────────────\nstop_loss\ninvalidation_level\nfirst_target\nsecond_target"]
        RR["RiskReward\n─────────────\ndownside %\nupside %\nratio (≥ 2.0 for BUY)"]
        PS["PositionSizing\n─────────────\nstarter % of full\nmax portfolio %\nConservative: 15% / 3%\nModerate:     25% / 5%\nAggressive:   40% / 8%"]
    end

    Inputs --> RiskMgmt
    RiskMgmt --> EP
    RiskMgmt --> EXP
    RiskMgmt --> RR
    RiskMgmt --> PS
```

---

## 8. Frontend Component Tree

```mermaid
flowchart TD
    App["App.tsx"]
    App --> Dash["Dashboard.tsx\nState: ticker, riskProfile, result, loading, error"]

    Dash -->|"POST /api/stocks/analyze"| API["stockApi.ts\naxios wrapper"]

    Dash --> DW["DataWarnings.tsx\nYellow warning panel\nfor missing data flags"]

    Dash --> RC["RecommendationCard.tsx × 3\nOne per horizon\nDecision badge · Score bar\nBullish/bearish factors\nEntry / Exit / R/R plan"]

    Dash --> SB["ScoreBreakdown.tsx\nHorizontal bar chart\nper sub-score dimension"]

    Dash --> TCH["TechnicalChart.tsx\nMA table · RSI · MACD\nVolume · Trend · RS\nSupport / Resistance levels"]

    Dash --> Fund["Fundamental Quality\n(inline grid)"]
    Dash --> Val["Valuation\n(inline grid)"]
    Dash --> Earn["Earnings\n(inline grid)"]

    Dash --> NS["NewsSection.tsx\nPositive / Negative / Neutral\nnews lists with badges"]

    Dash --> MRP["MarkdownReport.tsx\nCollapsible details element\nreact-markdown renderer"]
```

---

## 9. Data Model

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
    }

    class HorizonRecommendation {
        +str horizon
        +str decision
        +float score
        +str confidence
        +str summary
        +list~str~ bullish_factors
        +list~str~ bearish_factors
        +EntryPlan entry_plan
        +ExitPlan exit_plan
        +RiskReward risk_reward
        +PositionSizing position_sizing
    }

    class TechnicalIndicators {
        +float ma_10..ma_200
        +float rsi_14
        +float macd_histogram
        +float atr
        +TrendClassification trend
        +bool is_extended
        +str volume_trend
        +float rs_vs_spy
        +SupportResistanceLevels support_resistance
        +float technical_score
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
    }

    class EarningsData {
        +str last_earnings_date
        +str next_earnings_date
        +list~EarningsRecord~ history
        +float beat_rate
        +float avg_eps_surprise_pct
        +bool within_30_days
        +float earnings_score
    }

    class NewsSummary {
        +list~NewsItem~ items
        +int positive_count
        +int negative_count
        +int neutral_count
        +float news_score
        +bool coverage_limited
    }

    StockAnalysisRequest --> StockAnalysisResult : produces
    StockAnalysisResult "1" --> "1" TechnicalIndicators
    StockAnalysisResult "1" --> "1" FundamentalData
    StockAnalysisResult "1" --> "1" ValuationData
    StockAnalysisResult "1" --> "1" EarningsData
    StockAnalysisResult "1" --> "1" NewsSummary
    StockAnalysisResult "1" --> "3" HorizonRecommendation
```

---

## 10. Caching Strategy

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

## 11. Backtest Architecture

```mermaid
flowchart TD
    subgraph CLI["CLI Entry Point"]
        RUN["run_backtest.py\n--tickers --start --end --risk-profile"]
    end

    subgraph DataLoader["Phase 1 · Data Pre-loader (data_loader.py)"]
        FETCH["Fetch 3-year daily price history\nfor all tickers + SPY + sector ETFs"]
        QFETCH["Fetch quarterly statements\nincome · balance · cashflow\nearnings_history · earnings_dates"]
        DISK["Disk cache\nbacktest_results/cache/\nprices.pkl · quarterly.pkl"]
    end

    subgraph Runner["Phase 2 · Weekly Loop (runner.py)"]
        DATES["Generate weekly Mondays\n2024-05-06 → 2026-05-04\n~105 test dates"]
        SNAP["Snapshot Builder (snapshot.py)\nSlice price to test_date\nFilter quarterly stmts by date\nBuild FundamentalData · ValuationData · EarningsData"]
        PIPE["Production Pipeline\ncompute_technicals()\ncompute_scores()\nbuild_recommendations()"]
        SIG["Signal Record\nticker · date · horizon\ndecision · score · price\nsub-scores · entry/stop/target"]
    end

    subgraph Outcome["Phase 3 · Outcome Evaluator (outcome.py)"]
        FWD["Look up exit price\nat date + N trading days\nshort: 20d · medium: 65d · long: 252d"]
        RET["Compute\nforward_return %\nspy_return %\nexcess_return %"]
    end

    subgraph Metrics["Phase 4 · Metrics (metrics.py)"]
        BD["by_decision\nwin rate · avg return · vs SPY"]
        BSB["by_score_bucket\n0–40 · 40–55 · 55–70 · 70–85 · 85–100"]
        BT["by_ticker\nper-ticker win rate + alpha"]
        MB["monthly_breakdown\ntime-series of model accuracy"]
        SIM["portfolio_simulation\nBUY signals vs SPY buy-and-hold"]
    end

    subgraph Output["Phase 5 · Report (report.py)"]
        CSV["raw_signals.csv\nsummary_by_decision.csv\nsummary_by_ticker.csv"]
        HTML["report.html\nSelf-contained · Embedded matplotlib charts"]
        JSON["report.json\nFull metrics as JSON"]
    end

    CLI --> DataLoader
    FETCH --> DISK
    QFETCH --> DISK
    DISK --> Runner
    DATES --> Runner
    Runner --> SNAP
    SNAP --> PIPE
    PIPE --> SIG
    SIG --> Outcome
    FWD --> RET
    RET --> Metrics
    Metrics --> Output
```

---

## 12. Look-Ahead Bias Prevention (Backtest)

```mermaid
flowchart LR
    subgraph TestDate["Test Date: 2024-09-02"]
        direction TB
        PRICE["✅ Price history sliced\ndf[df.index ≤ 2024-09-02]"]
        SPY2["✅ SPY sliced\nsame cutoff"]
        QSTMT["✅ Quarterly statements filtered\nonly columns (quarters) filed ≤ 2024-09-02"]
        EHIST["✅ Earnings history filtered\nonly records reported ≤ 2024-09-02"]
        NEWS2["⚠️ News sentiment\nNo historical data → default 50 (neutral)"]
        OPTS["⚠️ Options catalyst\nNo historical data → default 50 (neutral)"]
    end

    subgraph Engine["Analysis Engine\n(unchanged from production)"]
        TECH2["compute_technicals()"]
        SCORE2["compute_scores()"]
        RECS["build_recommendations()"]
    end

    PRICE --> TECH2
    SPY2 --> TECH2
    QSTMT --> SCORE2
    EHIST --> SCORE2
    NEWS2 --> SCORE2
    OPTS --> SCORE2
    TECH2 --> SCORE2
    SCORE2 --> RECS
```

---

## 13. API Reference

```mermaid
flowchart LR
    subgraph Endpoints["REST API  (base: /api/stocks)"]
        A["POST /analyze\nFull analysis — all providers + scoring + report\nBody: {ticker, horizons, risk_profile}\nResponse: StockAnalysisResult"]
        B["GET /{ticker}/report\nMarkdown report only\nResponse: {ticker, report}"]
        C["GET /{ticker}/technicals\nTechnical indicators only\nResponse: TechnicalIndicators"]
        D["GET /{ticker}/news\nNews + sentiment only\nResponse: NewsSummary"]
        E["GET /health\nHealth check\nResponse: {status: ok}"]
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

## 14. Technology Stack

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

## 15. Known Limitations & Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **In-memory TTLCache** (no Redis) | Zero infra dependency for MVP | Cache lost on server restart; not shared across workers |
| **yfinance for all data** | Free, no API key required | Rate-limited (HTTP 429); limited news coverage; no historical options data |
| **OpenAI optional** | Tool works without API key (keyword fallback) | Keyword classifier is less accurate than GPT-4o-mini |
| **Static sector/macro score (50)** | No reliable free sector data via yfinance | Doesn't reflect real macro conditions |
| **No peer comparison** | yfinance doesn't support sector-level P/E comparison | Flags in data quality warnings |
| **Valuation penalizes high-multiple growth** | Conservative P/E / PEG scoring | Underscores expensive-but-growing tech names like NVDA, PLTR |
| **Backtest news/options = 50** | No historical news sentiment or options data available | Short-term backtest accuracy understated |
| **No database** | Simplicity; all state in HTTP response | No history, no user accounts, stateless |
