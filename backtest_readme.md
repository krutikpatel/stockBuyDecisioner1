# Backtest Engine — Usage Guide

Backtests the Stock Decision Tool against 2 years of historical weekly data to measure whether its Buy/Wait/Avoid signals actually predict better price outcomes.

> **Disclaimer:** This is a decision-support validation tool, not financial advice. Backtest results do not guarantee future performance.

---

## What It Does

For each Monday over the test window (~104 weeks), the engine:

1. Slices price history to that date (no look-ahead bias)
2. Runs the full analysis pipeline: `compute_technicals()` → `compute_scores()` → `build_recommendations()`
3. Uses quarterly financial statements filtered to that date for fundamentals
4. Defaults news sentiment and options catalyst to neutral (50) — historical data unavailable
5. Records the decision, composite score, and all sub-scores
6. Later computes the actual forward return 4 weeks / 13 weeks / 52 weeks out

Then aggregates results into:
- **Win rate by decision type** (did BUY_NOW outperform AVOID?)
- **Score → return correlation** (do higher scores → better outcomes?)
- **Per-ticker stats** (which tickers is the model best/worst at?)
- **Portfolio simulation** vs. buy-and-hold SPY

---

## Setup

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt   # includes matplotlib, lxml
```

---

## Running the Backtest

### Quick test (2 tickers, ~7 months)

```bash
cd backend
source .venv/bin/activate
python -m backtest.run_backtest --tickers AAPL SPY --start 2025-10-01
```

Runtime: ~2–3 minutes (fetches price + fundamental data once, caches to disk).

### Full 2-year backtest (all 20 tickers)

```bash
python -m backtest.run_backtest
```

Runtime: ~20–40 minutes on first run (fetches ~27 price series + 20 sets of quarterly data). Subsequent runs reuse cache and take ~10–20 minutes for the analysis loop.

### Custom date range

```bash
python -m backtest.run_backtest --start 2024-05-01 --end 2026-05-04 --risk-profile aggressive
```

### Force re-fetch (clear cache)

```bash
python -m backtest.run_backtest --refresh-cache
```

---

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--tickers` | All 20 | Space-separated list of tickers to test |
| `--start` | 2024-05-06 | Backtest start date (YYYY-MM-DD) |
| `--end` | 2026-05-04 | Backtest end date (YYYY-MM-DD) |
| `--risk-profile` | moderate | `conservative` / `moderate` / `aggressive` |
| `--refresh-cache` | off | Force yfinance re-fetch (ignores cached parquet) |
| `--no-report` | off | Skip HTML/JSON generation, only save CSVs |

---

## Tickers Tested

| Category | Tickers |
|----------|---------|
| Large-cap tech | AAPL, MSFT, NVDA, GOOGL |
| Large-cap non-tech | JPM, JNJ, XOM, WMT |
| Mid-cap growth | CRWD, DKNG, ENPH, COIN |
| Small-cap | MVIS, PLUG, ARRY, CLOV |
| ETFs | SPY, QQQ, IWM, GLD |

---

## Output Files

All results are saved to `backend/backtest_results/`:

| File | Description |
|------|-------------|
| `raw_signals.csv` | One row per (ticker, date, horizon) — decision, score, forward_return, excess_return |
| `summary_by_decision.csv` | Win rate, avg return, avg vs SPY per decision type |
| `summary_by_ticker.csv` | Per-ticker performance statistics |
| `report.html` | Self-contained HTML report with embedded charts (open in any browser) |
| `report.json` | Same data as JSON for programmatic use |
| `cache/prices.pkl` | Cached 3-year daily price history (~27 tickers) |
| `cache/quarterly.pkl` | Cached quarterly financial statements (20 tickers) |

---

## Understanding the Results

### Win Rate by Decision Type

The key validation: **BUY_NOW signals should have higher win rates than WATCHLIST/AVOID**. If the model is working, you'd expect:

```
BUY_NOW        →  win rate ~60–70%,  avg return > 0
BUY_STARTER    →  win rate ~55–65%,  avg return > 0
WAIT_FOR_PULL. →  win rate ~50%,     avg return ≈ 0
WATCHLIST      →  win rate ~50%,     avg return ≈ 0
AVOID          →  win rate < 50%,    avg return < 0
```

### Score → Return Correlation

Signals are grouped into score buckets (0–40, 40–55, 55–70, 70–85, 85–100). If the scoring system is predictive, avg forward return should increase monotonically with score. A positive correlation coefficient validates the scoring model.

### Avg Excess Return vs. SPY

`excess_return = ticker_return - SPY_return` over the same window. A positive avg excess return on BUY signals means the model adds value beyond a passive SPY investment.

### Portfolio Simulation

Simulates equal-weight $1 at every BUY_NOW / BUY_STARTER signal. Annualized return ≈ avg trade return × periods per year (short-term: 13, medium: 4, long: 1). Compare to the "SPY Annualized" figure — the difference is the model's **alpha**.

---

## Architecture

```
backend/backtest/
  config.py        — Tickers, date range, holding periods
  data_loader.py   — Fetches + caches 3-year price + quarterly data
  snapshot.py      — Builds time-sliced inputs for a given date
  runner.py        — Main weekly loop
  outcome.py       — Forward return computation
  metrics.py       — Win rates, score correlation, per-ticker stats
  report.py        — CSV + HTML/JSON report generation
  run_backtest.py  — CLI entry point
```

The backtest **reuses the production analysis pipeline without modification**:
- `app.services.technical_analysis_service.compute_technicals()`
- `app.services.scoring_service.compute_scores()`
- `app.services.recommendation_service.build_recommendations()`

---

## Look-Ahead Bias Prevention

| Data Type | How Handled |
|-----------|------------|
| Price / OHLCV | Sliced to `df[df.index <= test_date]` |
| SPY / sector ETF | Same date slice |
| Quarterly financials | Columns filtered: only quarters filed `<= test_date` |
| Earnings history | Records filtered: only dates `<= test_date` |
| News sentiment | Defaults to 50 (neutral) — no historical data available |
| Options / catalyst | Defaults to 50 (neutral) — no historical data available |

---

## Known Limitations

| Limitation | Impact |
|-----------|--------|
| News and options not available historically | Short-term scores slightly underestimated; real-world model would use live news |
| yfinance `.info` fields (market cap, beta) are live snapshots | Minor inaccuracy for historical fundamental ratios |
| ETFs (SPY, QQQ, IWM, GLD) have no fundamental data | Fundamental/valuation scores default to 50 for ETFs; technical signals still valid |
| Small-cap tickers may have sparse history | Signals skipped if < 252 rows of price data at test date |
| Long-term outcomes unavailable for signals < 52 weeks ago | Last ~52 weeks of signals have no `long_term` forward return |
| `lxml` required for `earnings_dates` | Install with `pip install lxml`; handled gracefully if missing |
