# Backtesting the Stock Decision Tool

## Table of Contents

1. [What Is Backtesting Here?](#1-what-is-backtesting-here)
2. [What We Test](#2-what-we-test)
3. [Three Phases Explained](#3-three-phases-explained)
4. [Architecture Overview](#4-architecture-overview)
5. [How to Run](#5-how-to-run)
6. [Output Files](#6-output-files)
7. [How to Interpret Results](#7-how-to-interpret-results)
8. [Success Criteria](#8-success-criteria)
9. [Known Limitations](#9-known-limitations)
10. [Extending the Backtest](#10-extending-the-backtest)

---

## 1. What Is Backtesting Here?

Most people think of backtesting as "did buying stock X when the model said BUY make money?" That is a necessary but insufficient question.

This backtesting framework asks harder, more useful questions:

- **Did `BUY_NOW_MOMENTUM` beat SPY/QQQ over the next 20 trading days** — not just go up?
- **Did `AVOID_BAD_CHART` signals have higher drawdowns** than BUY signals?
- **Does the model's performance degrade in bear markets** (BEAR_RISK_OFF regime)?
- **Are HYPER_GROWTH archetype signals priced differently than MATURE_VALUE signals?**
- **Which of the 11 signal cards (momentum, growth, valuation, etc.) are actually predictive?**
- **Does a higher composite score reliably predict better forward returns?**

In short: we are **validating a decision engine**, not a price predictor.

### Why This Matters

A model that always says "BUY" in a bull market will look great. A model that actually has skill should:

1. Show that its BUY labels outperform SPY **in excess return terms**
2. Show that AVOID labels have lower returns or higher drawdowns than BUY labels
3. Work across different market regimes (not just 2023–2024 AI boom)
4. Work for different types of stocks (not just NVDA-style growth)
5. Show score monotonicity: higher confidence → better outcomes

---

## 2. What We Test

### 2.1 Signal Labels

The tool produces **14 distinct decision labels** split across 3 horizons:

| Horizon | Labels |
|---------|--------|
| Short-term (20D) | `BUY_NOW_MOMENTUM`, `BUY_STARTER_STRONG_BUT_EXTENDED`, `WAIT_FOR_PULLBACK`, `AVOID_BAD_CHART` |
| Medium-term (63D) | `BUY_NOW`, `BUY_STARTER`, `BUY_ON_PULLBACK`, `WATCHLIST_NEEDS_CONFIRMATION`, `AVOID_BAD_BUSINESS` |
| Long-term (252D) | `BUY_NOW_LONG_TERM`, `ACCUMULATE_ON_WEAKNESS`, `WATCHLIST_VALUATION_TOO_RICH`, `AVOID_LONG_TERM` |

For each label, we compute: signal count, average return, win rate (>0%), benchmark win rate (beats SPY), average excess return vs SPY, average max drawdown during the holding period, and profit factor.

### 2.2 Score Buckets

The composite score (0–100) is bucketed into 8 ranges. We test whether higher scores produce better forward returns — a basic monotonicity check that validates the scoring system.

### 2.3 Market Regimes

Every snapshot is tagged with one of 6 regimes classified from historical SPY/QQQ data:

- `BULL_RISK_ON` — SPY above all key MAs, broad participation
- `BULL_NARROW_LEADERSHIP` — SPY up but QQQ diverging, breadth weak
- `SIDEWAYS_CHOPPY` — neither bulls nor bears in control
- `BEAR_RISK_OFF` — SPY below 200DMA, VIX elevated
- `SECTOR_ROTATION` — cross-sector divergence, no clear trend
- `LIQUIDITY_RALLY` — sharp recovery with narrow participation

We compute a **Regime × Decision heatmap**: for each (regime, decision) combination, what was the average excess return vs SPY? This reveals whether e.g. `AVOID_BAD_CHART` performs well specifically in bear regimes, or whether `BUY_NOW_MOMENTUM` generates alpha mostly during bull regimes.

### 2.4 Stock Archetypes (Phase 3)

The tool classifies each stock into one of 8 archetypes:

| Archetype | Description |
|-----------|-------------|
| `HYPER_GROWTH` | Revenue growing >40% YoY, often pre-profit or early-profit |
| `PROFITABLE_GROWTH` | 20–40% revenue growth with improving margins |
| `CYCLICAL_GROWTH` | Growth tied to economic cycle |
| `MATURE_VALUE` | Slow growth, strong cash flows, dividend profile |
| `TURNAROUND` | Recovering from losses or negative revenue trends |
| `SPECULATIVE_STORY` | Narrative-driven, limited or no revenue |
| `DEFENSIVE` | Low volatility, steady cash flows (healthcare, utilities) |
| `COMMODITY_CYCLICAL` | Revenue driven by commodity pricing |

We test: do the same decision labels perform differently for different archetypes? A `BUY_NOW` for a `HYPER_GROWTH` stock should have different risk/reward than `BUY_NOW` for a `MATURE_VALUE` stock.

### 2.5 Signal Card Effectiveness (Phase 3)

The tool scores 11 "signal cards" (each 0–100):

| Card | What It Measures |
|------|-----------------|
| Momentum | RSI, MACD, price velocity |
| Trend | SMA alignment, ADX, trend classification |
| Entry Timing | % above/below MAs, extension detection |
| Volume/Accumulation | OBV, A/D line, CMF, VWAP deviation |
| Volatility/Risk | ATR, Bollinger Band width, drawdown metrics |
| Relative Strength | RS vs SPY, QQQ, sector ETF |
| Growth | Revenue/EPS growth rates, margins |
| Valuation | P/E, PEG, P/S, EV/EBITDA, FCF yield |
| Quality | Gross/operating margins, ROE, ROIC, balance sheet |
| Ownership | Institutional/insider ownership, short interest |
| Catalyst | Analyst ratings, news sentiment, earnings proximity |

For each card, we compute the **correlation with forward returns** and **quartile return analysis** (do high-scoring signals on each card outperform low-scoring ones?). This reveals which signal cards are actually predictive.

---

## 3. Three Phases Explained

The backtest is structured in three phases of increasing data richness.

### Phase 1: Technical-Only

**What it uses:** Price, volume, 55+ technical indicators, SPY/QQQ for RS and regime.

**What it avoids:** Any fundamental data (which risks survivorship bias and look-ahead via annual reports).

**Why start here:** Technical data is clean, historical, and free of look-ahead bias. Phase 1 validates the core framework before adding complexity.

**Fundamental placeholders:** Growth=50, valuation=50, quality=50 (all neutral). The signal cards for growth, valuation, quality, ownership will score approximately 50 across the board.

**VIX proxy:** Since historical VIX data requires a separate download, Phase 1 approximates VIX using rolling 20-day SPY return volatility × √252. This captures the same fear/complacency signal.

### Phase 2: Regime Overlay

Same as Phase 1, but the **regime classification is validated and regime-split metrics are added** to the report. This phase checks:

- Are regime classifications sensible? (e.g., dates in March 2020 should show BEAR_RISK_OFF)
- Does the model's performance differ materially across regimes?
- Do AVOID signals prove more valuable specifically in BEAR_RISK_OFF periods?

Phase 2 adds the Regime × Decision heatmap to the report.

### Phase 3: Fundamentals + Archetype

Adds **time-sliced fundamentals** constructed from quarterly filings with a 45-calendar-day lag (accounting for 10-Q filing deadlines). This means:

- On 2020-05-01, you only use earnings data filed on or before 2020-03-17
- This prevents using Q1 2020 earnings (filed May 2020) to evaluate a April 2020 signal

With real fundamentals:
- All 11 signal cards score based on actual data, not neutral 50s
- Archetype classification becomes meaningful
- Growth, valuation, quality, and ownership cards are properly populated

**Important limitation:** Some fundamental data points (analyst target prices, institutional ownership %) are only available as current values, not historical. These are flagged in the report and represent an accepted approximation. The main financial metrics (revenue, margins, EPS, debt) are properly time-sliced.

---

## 4. Architecture Overview

```
backend/backtest/
├── config.py           Tickers, date ranges, horizons, slippage, paths
├── data_loader.py      Pre-fetch + pickle-cache OHLCV and quarterly fundamentals
├── snapshot.py         Time-slice all data to test_date; build fundamentals from filings
├── runner.py           Main loop: for each (ticker, week) → emit SignalRecord list
├── outcome.py          Attach forward returns and benchmark returns
├── metrics.py          Aggregate: by_decision, by_regime, by_archetype, by_signal_card
├── report.py           Self-contained HTML report + CSV exports
└── run_backtest.py     CLI entry point
```

### Data Flow

```
load_all_data()
    ↓  prices (OHLCV) + quarterly (financials)
    ↓
run_backtest()  ← for each (ticker, Monday)
    ├── get_price_slice()          no-look-ahead price slice
    ├── compute_technicals()       55+ indicators
    ├── build_historical_fundamentals()  (Phase 3) quarterly filings with lag
    ├── classify_regime()          historical SPY/QQQ → regime
    ├── score_all_cards()          11 signal cards
    ├── compute_scores_from_signal_cards()
    ├── build_recommendations()    per-horizon decision labels
    └── emit SignalRecord
    ↓
attach_outcomes()
    ├── exit_price at +N trading days
    ├── spy_return / qqq_return over same period
    ├── excess_return = stock_return - spy_return
    └── max_drawdown_period = worst trough during holding window
    ↓
build_all_horizons_metrics()
    ├── by_decision, by_score_bucket, by_ticker
    ├── by_regime, by_regime_decision    (Phase 2+)
    ├── by_archetype, by_archetype_decision  (Phase 3)
    └── by_signal_card                   (Phase 3)
    ↓
generate_report()
    ├── report.html (self-contained, opens offline)
    └── *.csv files (one per metric section per horizon)
```

### Signal Record Schema

Each snapshot emits one record per horizon (3 records per ticker per week):

```
ticker            AAPL
date              2022-03-07
horizon           short_term
decision          BUY_NOW_MOMENTUM
score             72.4
confidence        medium_high
market_regime     BULL_NARROW_LEADERSHIP
archetype         HYPER_GROWTH          ← UNKNOWN in Phase 1-2
phase             3
price             167.30
technical_score   68.5
fundamental_score 74.2                  ← 50.0 in Phase 1-2
valuation_score   45.1                  ← 50.0 in Phase 1-2
earnings_score    65.0
trend             strong_uptrend
rsi               62.4
is_extended       False
sc_momentum       78.5                  ← 11 signal card scores
sc_trend          71.0
...
forward_return    +8.32%                ← filled by outcome.py
spy_return        +3.10%
excess_return     +5.22%
max_drawdown_period  -4.1%
```

---

## 5. How to Run

### Prerequisites

```bash
cd backend

# Install dependencies (if not already installed)
pip install yfinance pandas numpy pandas-ta
```

### Quick Smoke Test (2 minutes)

Validates the pipeline with 2 tickers and 1 year of data:

```bash
cd backend
python -m backtest.run_backtest \
  --tickers AAPL,MSFT \
  --start 2022-01-01 \
  --end 2023-01-01 \
  --phase 1
```

Expected output:
- `backend/backtest/results/signals_with_outcomes.csv` (~300 rows)
- `backend/backtest/results/report.html` — open in browser

### Phase 2 Smoke Test (verify regime metrics)

```bash
python -m backtest.run_backtest \
  --tickers AAPL,MSFT,NVDA \
  --start 2021-01-01 \
  --end 2023-01-01 \
  --phase 2
```

Check: `report.html` contains a "Regime Performance" section with a heatmap table.

### Phase 3 Smoke Test (with fundamentals)

```bash
python -m backtest.run_backtest \
  --tickers AAPL,MSFT,NVDA \
  --start 2021-01-01 \
  --end 2023-01-01 \
  --phase 3
```

Check: archetype column in CSV is not always "UNKNOWN"; report has "Archetype Performance" and "Signal Card Effectiveness" sections.

### Full Run (all 20 tickers, 2018–2025)

```bash
python -m backtest.run_backtest --phase 3
```

This takes 20–45 minutes on first run (data download). Subsequent runs use the pickle cache and take ~5–15 minutes.

Expected output: ~20,000+ signal records across 3 horizons.

### Re-download All Data

```bash
python -m backtest.run_backtest --force-refresh --phase 3
```

### All CLI Options

```
--tickers        Comma-separated tickers (default: all 20 in config)
--start          Backtest start date YYYY-MM-DD (default: 2018-01-01)
--end            Backtest end date YYYY-MM-DD (default: 2025-12-31)
--phase          1, 2, or 3 (default: 3)
--risk-profile   conservative | moderate | aggressive (default: moderate)
--force-refresh  Re-download all data even if cache exists
--output-dir     Directory for results (default: backtest/results/)
--no-report      Skip HTML report (still writes CSVs)
```

---

## 6. Output Files

All files are written to `backend/backtest/results/` (or the `--output-dir` you specify).

### HTML Report

`report.html` — Self-contained, opens offline in any browser. Sections:

- **Executive Summary:** Key metrics at a glance across all horizons
- **Performance by Horizon:** Tabbed view (short/medium/long) with:
  - Decision label performance table
  - Score bucket analysis
  - Portfolio simulation (equal-weight buy signals vs SPY)
  - Regime × Decision heatmap (Phase 2+)
  - Archetype performance (Phase 3)
  - Signal card effectiveness (Phase 3)
  - Per-ticker performance
  - Monthly breakdown timeline
- **Cross-Horizon Summary:** Quick comparison of all 3 horizons

### CSV Files

| File | Contents |
|------|---------|
| `signals_with_outcomes.csv` | All signal records with forward returns |
| `short_term_by_decision.csv` | Decision label metrics (short-term) |
| `medium_term_by_decision.csv` | Decision label metrics (medium-term) |
| `long_term_by_decision.csv` | Decision label metrics (long-term) |
| `*_by_score_bucket.csv` | Score bucket analysis per horizon |
| `*_by_ticker.csv` | Per-stock performance per horizon |
| `*_by_regime.csv` | Regime performance per horizon (Phase 2+) |
| `*_by_regime_decision.csv` | Regime × Decision cross-tab (Phase 2+) |
| `*_by_archetype.csv` | Archetype performance (Phase 3) |
| `*_by_archetype_decision.csv` | Archetype × Decision cross-tab (Phase 3) |
| `*_by_signal_card.csv` | Signal card correlation with returns (Phase 3) |
| `*_monthly.csv` | Monthly time-series breakdown per horizon |

### Cache Files

`backend/backtest/cache/prices.pkl` and `quarterly.pkl` — pickle files of downloaded data. Delete these and run with `--force-refresh` to re-download.

---

## 7. How to Interpret Results

### 7.1 Win Rate

**Win rate** = percentage of signals where the stock was higher at the end of the holding period.

- A random strategy in a rising market might have 55–60% win rate.
- We care more about **benchmark-relative win rate** (beats SPY? yes/no).
- A BUY signal with 55% win rate but -3% average excess return is actually bad.

### 7.2 Excess Return vs SPY

**Excess return** = `forward_return - spy_return` over the same holding period.

This is the primary measure of signal quality. A positive average excess return means the model added alpha — the stocks it flagged as BUY outperformed what you would have earned in SPY over the same dates.

- **+3% average excess return** = strong signal
- **0–1%** = weak but possibly still useful (combined with drawdown reduction)
- **Negative average excess return** = the signal is destructive (worse than just buying SPY)

### 7.3 Average Max Drawdown

**Max drawdown during the holding period** = worst intra-period trough from entry price.

- For AVOID signals, we want to see this is worse (more negative) than BUY signals.
- A good AVOID signal might have average max drawdown of -15% vs -5% for BUY signals.
- High max drawdown for BUY signals indicates poor entry timing even if final return is positive.

### 7.4 Profit Factor

**Profit factor** = total gains ÷ total losses (as absolute values).

- > 1.5 = strong
- 1.0–1.5 = marginal
- < 1.0 = signal destroys value

### 7.5 Score Monotonicity

Look at the **Score Bucket Analysis** table. A well-calibrated model should show:
- Higher score buckets (87–100) have better average returns than lower buckets (0–12)
- The progression should be roughly monotone — each higher bucket outperforms the lower one
- If score buckets are random, the scoring system isn't working

### 7.6 Regime Heatmap

Look at the **Regime × Decision heatmap**:
- `BUY_NOW_MOMENTUM` in `BULL_RISK_ON` should show high positive excess return
- `BUY_NOW_MOMENTUM` in `BEAR_RISK_OFF` might show negative excess return (false signals)
- `AVOID_BAD_CHART` in `BEAR_RISK_OFF` should show the highest negative return (confirming avoids matter most in downturns)

### 7.7 Signal Card Correlation

Look at the **Signal Card Effectiveness** table:
- Correlation close to +1.0 = this card strongly predicts positive returns
- Correlation near 0 = this card doesn't contribute predictive value
- Quartile analysis: Q4 (highest-scoring signals) should have better average returns than Q1 (lowest-scoring)

---

## 8. Success Criteria

From `backTestingImprovements1.md` (Section 21):

1. **`BUY_NOW_MOMENTUM` beats SPY/QQQ/sector over 5D–20D** — positive average excess return
2. **`BUY_STARTER_STRONG_BUT_EXTENDED` has lower drawdown than `BUY_NOW_MOMENTUM`** — more cautious label = better risk control
3. **`WAIT_FOR_PULLBACK` improves entry risk/reward** — even if it misses some moves
4. **`AVOID_BAD_CHART` has worse forward returns or higher drawdowns than BUY labels** — avoids should be right
5. **`AVOID_BAD_BUSINESS` underperforms over 3–12 months** — fundamental avoids should predict weakness
6. **Higher score buckets outperform lower score buckets** — monotone improvement in score → return
7. **Results hold outside 2024–2025** — model works across different market environments (test 2018–2021 separately)
8. **Model works by archetype** — not just on HYPER_GROWTH/AI-boom names
9. **Regime overlay reduces false positives** — BUY signals in BEAR_RISK_OFF should have worse outcomes
10. **Valuation helps long-term risk control** — high valuation score correlates with better long-term returns without destroying short-term momentum trades

### Red Flags

These indicate the model is broken or the backtest has a flaw:

- AVOID signals outperform BUY signals
- Lower score buckets outperform higher buckets
- All 6 market regimes show identical performance
- Win rates are above 70% (suspiciously good — check for look-ahead bias)
- Zero `BEAR_RISK_OFF` signals in 2018 Q4, 2020 Q1, or 2022 (regime classifier broken)

---

## 9. Known Limitations

### 9.1 Data Quality

- **yfinance data quality:** yfinance may have gaps, splits-adjusted price errors, or stale data. Do not use this backtest for live trading decisions.
- **Quarterly statement timing:** yfinance returns quarterly statements as they exist today, with columns timestamped at period-end. Actual EDGAR filing dates may differ by weeks. The 45-day lag is an approximation.
- **Survivorship bias:** The 20-ticker universe is chosen based on 2025 knowledge. Stocks that failed or were acquired (e.g., SVB, Twitter/X) are not included. This inflates performance.
- **Look-ahead in `info_snapshot`:** Some fields in yfinance's `ticker.info` (analyst targets, institutional ownership) reflect current values, not historical values as of the test date. These affect the ownership and catalyst signal cards in Phase 3.

### 9.2 No Live Order Execution

- The backtest simulates entry at the closing price on the signal date and exit at the closing price N trading days later.
- Real execution would incur slippage (currently set to 0.0% in `config.py`), bid-ask spread, and market impact.
- Set `SLIPPAGE` in `config.py` to a realistic value (0.1–0.5%) to stress-test results.

### 9.3 No Position Sizing or Portfolio Construction

- Each signal is treated independently with equal weight.
- The portfolio simulation is a simple arithmetic mean of trade returns, not a true compounded portfolio.
- A real portfolio would have concentration limits, correlation adjustments, and exit rules (stop-loss, trailing stop).

### 9.4 Historical News and Options Data

- News sentiment and options flow cannot be historically reconstructed from yfinance.
- All backtest snapshots use **neutral news** (score=50) and **no options data**.
- The catalyst signal card scores are based on analyst ratings and earnings data only.
- This means the backtest **underestimates** the impact of news/options signal cards.

### 9.5 Fixed VIX Proxy

- Historical VIX is not fetched; instead, rolling SPY 20-day volatility × √252 is used as a proxy.
- This approximates but does not exactly replicate VIX behavior during stress events (VIX can spike higher due to options market dynamics not captured in realized volatility).

---

## 10. Extending the Backtest

### Add More Tickers

Edit `BACKTEST_TICKERS` in `backend/backtest/config.py`. Add the ticker's sector ETF to `SECTOR_ETF_MAP`. Run with `--force-refresh` to download new data.

### Change Holding Periods

Edit `HOLDING_PERIODS` in `config.py`. Add new key-value pairs or change existing ones. Corresponding changes needed in `runner.py` `HORIZONS` list.

### Add New Metrics

Add a new function to `metrics.py` following the `_by_X(df)` pattern. Call it in `build_metrics()`. Add an HTML rendering function in `report.py` and include it in `_build_horizon_html()`.

### Add Slippage

Set `SLIPPAGE` in `config.py` to a float (e.g., `0.001` = 0.1%). In `outcome.py`'s `attach_outcomes()`, apply it: `forward_return -= SLIPPAGE * 100 * 2` (round-trip).

### Add Historical VIX

Replace the synthetic VIX proxy in `runner.py` with real CBOE VIX data:
```python
import yfinance as yf
vix_full = yf.download("^VIX", start=HISTORY_START, end=BACKTEST_END, auto_adjust=True)
vix_slice = get_price_slice(vix_full, test_date)
vix_proxy = float(vix_slice["Close"].iloc[-1]) if not vix_slice.empty else None
```

Add `^VIX` download to `data_loader.py`.

### Test Walk-Forward (Out-of-Sample)

Run the backtest on separate periods to test for overfitting:
```bash
# In-sample: 2018-2021
python -m backtest.run_backtest --start 2018-01-01 --end 2021-12-31 --output-dir backtest/results/in_sample/

# Out-of-sample: 2022-2025
python -m backtest.run_backtest --start 2022-01-01 --end 2025-12-31 --output-dir backtest/results/out_of_sample/
```

If the model performs dramatically worse out-of-sample, it has been overfitted to the 2020–2024 bull market environment.

### Add Ablation Testing

Test model versions with one signal card removed (set to neutral 50):
- In `runner.py`, after `score_all_cards()`, override one card's score to 50.0 before calling `compute_scores_from_signal_cards()`.
- Compare the resulting report to the full model to quantify each card's marginal contribution.
