# Backtest Plan: Stock Decision Tool

> This document describes the design, architecture, and methodology for backtesting the Stock Decision Tool against 2 years of historical data.

---

## Goal

Validate whether the tool's Buy/Wait/Avoid signals actually predict better forward price performance. Run the decision engine weekly over ~104 weeks (2024-05-01 → 2026-05-04) across 20 representative tickers (~2,080 total analysis snapshots) and measure win rates, average returns, and performance vs. a buy-and-hold SPY baseline.

---

## Look-Ahead Bias Prevention

All data fed into the engine on a given backtest date uses only information available *on or before* that date.

| Data Type | Source | Historical Approach |
|-----------|--------|---------------------|
| Price / OHLCV | yfinance | Slice full history `df = df[df.index <= test_date]` |
| SPY / sector ETF | yfinance | Same date slice |
| Fundamentals | yfinance quarterly statements | Filter by `reportDate <= test_date` |
| Earnings history | yfinance | Filter `earnings_dates` index `<= test_date` |
| News sentiment | yfinance (no historical data) | Default `news_score = 50` (neutral) |
| Options / catalyst | yfinance (live only) | Default `catalyst_score = 50` (neutral) |
| Sector/macro | Static | Always `50` (same as production) |

---

## Architecture

```
backend/
  backtest/
    __init__.py
    config.py          # Tickers, date range, holding periods
    data_loader.py     # Pre-fetches + disk-caches all historical data as parquet
    snapshot.py        # Builds time-sliced analysis inputs for a given date
    runner.py          # Main backtest loop
    outcome.py         # Computes forward returns at 4w / 13w / 52w
    metrics.py         # Win rates, score correlation, per-ticker stats
    report.py          # Generates CSV + self-contained HTML report
    run_backtest.py    # CLI entry point
```

**Reuses existing services without modification:**
- `app.services.technical_analysis_service.compute_technicals()`
- `app.services.scoring_service.compute_scores()`
- `app.services.recommendation_service.build_recommendations()`
- `app.services.fundamental_analysis_service.score_fundamentals()`
- `app.services.valuation_analysis_service.score_valuation()`
- `app.providers.earnings_provider.score_earnings()`

---

## Ticker Selection (20 tickers)

| Category | Tickers |
|----------|---------|
| Large-cap tech | AAPL, MSFT, NVDA, GOOGL |
| Large-cap non-tech | JPM, JNJ, XOM, WMT |
| Mid-cap growth | CRWD, DKNG, ENPH, SQ |
| Small-cap | MVIS, PLUG, ARRY, CLOV |
| ETFs | SPY, QQQ, IWM, GLD |

---

## Test Schedule

- **Start:** 2024-05-06 (first Monday on/after 2024-05-01)
- **End:** 2026-05-04
- **Frequency:** Every Monday (business-day adjusted forward if holiday)
- **~104 test dates × 20 tickers = ~2,080 analysis snapshots**

---

## Holding Periods

| Horizon | Forward Window | Trading Days |
|---------|---------------|--------------|
| `short_term` | +4 weeks | 20 |
| `medium_term` | +13 weeks | 65 |
| `long_term` | +52 weeks | 252 |

---

## Outcome Metrics (Human-Readable)

### 1. Win Rate by Decision Type
Per decision (BUY_NOW, BUY_STARTER, WAIT_FOR_PULLBACK, BUY_ON_BREAKOUT, WATCHLIST, AVOID):
- Count of signals
- Average forward return
- Win rate (% of signals with positive forward return)
- Average excess return vs. SPY over same period

### 2. Score-to-Return Correlation
Signals bucketed by score (0–40, 40–55, 55–70, 70–85, 85–100):
- Average forward return per bucket
- Validates that higher scores → better outcomes

### 3. Per-Ticker Summary
- Total signals, avg composite score, avg short-term return, avg excess return

### 4. vs. Buy-and-Hold Baseline
- Simulated portfolio: invest $1 at each BUY_NOW/BUY_STARTER signal, sell at holding period end
- Compare CAGR vs. holding SPY for same 2-year period

---

## Output Files

```
backend/backtest_results/
  raw_signals.csv          # One row per (ticker, date, horizon): decision, score, forward_return, excess_return
  summary_by_decision.csv  # Win rates & avg returns per decision type
  summary_by_ticker.csv    # Per-ticker performance stats
  report.html              # Self-contained HTML with tables + matplotlib charts (no external JS)
  report.json              # Same data as JSON
  cache/                   # Parquet files caching 3-year price history per ticker
```

---

## CLI Usage

```bash
cd backend
source .venv/bin/activate

# Quick test (2 tickers, 1 year)
python -m backtest.run_backtest --tickers AAPL SPY --start 2025-05-01

# Full 2-year backtest (all 20 tickers, ~15–30 min)
python -m backtest.run_backtest

# Custom date range
python -m backtest.run_backtest --start 2024-05-01 --end 2026-05-04 --risk-profile moderate
```

---

## Known Limitations

| Limitation | Impact |
|-----------|--------|
| News & options data not available historically | Sentiment and catalyst scores default to 50 (neutral); short-term accuracy may be understated |
| yfinance `.info` is a live snapshot | Fundamental data (market cap, current ratios) is not perfectly point-in-time; quarterly statements are used where available |
| Small-cap tickers may have sparse data | Signals are skipped if price history < 252 rows at test date |
| Long-term horizon outcome unavailable for recent dates | Signals in the last 52 weeks have no `long_term` forward return |
