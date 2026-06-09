# Backtest Guide — Two-Path Decision Engine

Backtests validate whether the engine's decisions predict forward returns. A well-functioning engine should show:

- **BUY** decisions → positive average forward returns, higher win rate
- **AVOID** decisions → negative or flat average forward returns, lower win rate
- **WAIT** and **WATCHLIST** should sit between the two extremes

---

## How the Backtest Works

### No-Lookahead Protocol

For each sampled trading date, all price-derived signals (RSI, OBV, ATR, SMA relatives, drawdown, volume) are computed from data **up to and including that date only**. Future prices are never seen by the engine.

```
actual_date = 2022-06-01

df_slice  = df_full.loc[: "2022-06-01"]   ← only past prices
spy_slice = spy_full.loc[: "2022-06-01"]

technicals = compute_technicals(df_slice)   ← RSI, OBV, etc. computed from df_slice
regime     = classify_regime(spy_slice)

snapshot   = build_feature_snapshot(price=df_slice["Close"].iloc[-1], ...)
decision   = engine.analyze_snapshot(snapshot)   ← no live fetch

# Forward return uses the full df — future prices are needed here
fwd_20d = close[entry_idx + 20] / close[entry_idx] - 1
fwd_60d = close[entry_idx + 60] / close[entry_idx] - 1
```

### Known Limitation: Fundamental Lookahead

Fundamental data (revenue growth, margins, ROE, FCF, debt/equity) is fetched as-of **today** from yfinance. yfinance does not expose point-in-time historical financials. This means:

- The **quality gate** and **avoid-side** signals use current fundamentals, not 2022 fundamentals
- A company that recovered between 2022 and today may be misclassified as quality for historical dates when it was actually deteriorating
- **Buy-side timing signals are fully clean** — they are entirely price-derived

For rigorous quality-gate backtesting, a paid financial data source (Compustat, Bloomberg, Intrinio) is required.

### Forward Return Horizons

| Label | Bars | Approximate calendar length |
|-------|------|----------------------------|
| `fwd_return_20d` | 20 trading bars | ~1 calendar month |
| `fwd_return_60d` | 60 trading bars | ~3 calendar months |

"Bars" means index steps in the daily OHLCV DataFrame, not calendar days. If fewer than `bars` trading sessions remain after the entry date, the return is recorded as `None` and excluded from averages.

### Sampling

Dates are sampled every `--freq` trading bars within `[--start, --end]`. The default is 20 bars (~monthly). A ticker with 2 years of data and `--freq 20` produces approximately 24 sample points.

---

## Running a Backtest

### Setup

```bash
cd claude-backend
source .venv/bin/activate
```

### Quality Universe

Tests whether BUY decisions on strong businesses produce positive returns.

```bash
python -m backtest.run_backtest --two-path \
    --tickers NVDA,AAPL,MSFT,GOOGL,META \
    --start 2022-01-01 \
    --end 2024-01-01
```

### Loser Universe

Tests whether AVOID decisions on deteriorating businesses predict negative returns. Uses the pre-built list of known problem stocks.

```bash
python -m backtest.run_backtest --two-path \
    --tickers loser \
    --start 2022-01-01 \
    --end 2024-01-01
```

The loser universe (`backtest/loser_universe.json`) contains:
```json
["INTC", "PFE", "BABA", "T", "MPW", "DLTR", "WBA", "VFC", "PARA", "BEN", "MO", "CVS", "MMM"]
```

### Mixed Universe

Run quality + loser stocks together to see all four decision buckets in one summary.

```bash
python -m backtest.run_backtest --two-path \
    --tickers NVDA,AAPL,MSFT,GOOGL,INTC,PFE,T,WBA \
    --start 2022-01-01 \
    --end 2024-01-01
```

### Adjusting Sample Frequency

```bash
# Weekly samples (5 trading bars)
python -m backtest.run_backtest --two-path \
    --tickers NVDA,AAPL,MSFT \
    --start 2022-01-01 --end 2023-01-01 \
    --freq 5

# Quarterly samples (63 trading bars)
python -m backtest.run_backtest --two-path \
    --tickers loser \
    --start 2020-01-01 --end 2024-01-01 \
    --freq 63
```

Higher frequency (`--freq 5`) gives more data points but observations are more correlated. Lower frequency (`--freq 63`) gives fewer, more independent observations.

---

## Reading the Output

### Terminal Summary

```
=== Two-Path Backtest Summary ===
  Total observations: 127

  Decision         n      avg 20d   avg 60d   win% 20d
  -------------------------------------------------------
  BUY             42      +3.21%    +6.87%      64.3%
  WAIT            18      +0.41%    +0.93%      55.6%
  AVOID           31      -2.15%    -4.02%      35.5%
  WATCHLIST       12      -0.88%    -1.44%      41.7%
```

| Column | Meaning |
|--------|---------|
| `n` | Number of observations with available forward return data |
| `avg 20d` | Average 20-bar (≈1 month) forward return across all observations |
| `avg 60d` | Average 60-bar (≈3 month) forward return across all observations |
| `win% 20d` | Percentage of observations with positive 20-bar forward return |

### What Good Results Look Like

| Signal | Healthy sign |
|--------|-------------|
| BUY avg 20d > +2% | Buy-side timing is adding meaningful value |
| AVOID avg 20d < −1% | Avoid signal is identifying genuine losers |
| BUY win% > 55% | Better than a coin flip on direction |
| AVOID win% < 45% | Deteriorating stocks mostly keep falling |
| BUY avg > WAIT avg | Timing signal is discriminating, not random |

The engine is not expected to be right every time. A BUY with 60% win rate and +3% average return is commercially valuable even though 40% of trades lose.

### CSV Output

Results are saved to `backtest/results/two_path_YYYYMMDD_HHMMSS.csv`.

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | str | Ticker symbol |
| `date` | str (ISO) | Sampled trading date |
| `path_taken` | str | `quality_intact` or `deteriorating_business` |
| `decision` | str | `BUY`, `WAIT`, `AVOID`, or `WATCHLIST` |
| `score` | float | Engine score [0, 100] |
| `fwd_return_20d` | float \| None | % return over next 20 trading bars |
| `fwd_return_60d` | float \| None | % return over next 60 trading bars |
| `reasons` | str | Top 5 fired rules, semicolon-separated |

`None` in forward return columns means insufficient future data existed at that date (usually near the `--end` boundary).

---

## Analyzing the CSV

The CSV is designed to be loaded into pandas or Excel for deeper analysis.

### Example: pandas analysis

```python
import pandas as pd

df = pd.read_csv("backtest/results/two_path_20240601_093000.csv")

# Filter only BUY decisions with sufficient data
buys = df[(df["decision"] == "BUY") & df["fwd_return_20d"].notna()]

print(f"BUY observations:  {len(buys)}")
print(f"Average 20d return: {buys['fwd_return_20d'].mean():.2f}%")
print(f"Win rate:           {(buys['fwd_return_20d'] > 0).mean():.1%}")

# Score buckets: does a higher score predict better returns?
buys["score_bucket"] = pd.cut(buys["score"], bins=[0, 65, 75, 85, 100],
                               labels=["60-65", "65-75", "75-85", "85+"])
print(buys.groupby("score_bucket")["fwd_return_20d"].mean())

# Per-ticker breakdown
print(df.groupby(["ticker", "decision"])["fwd_return_20d"].mean().unstack())
```

### Score Bucket Analysis

A useful sanity check: do higher-scoring BUY decisions produce better returns than lower-scoring ones? If score=80 and score=62 produce the same returns, the scoring rules above the threshold are not adding information.

### Regime Breakdown

The snapshot records `market_regime` in the FeatureSnapshot. You can extract this from the reasons column or add it to the snapshot-to-CSV mapping in `run_backtest.py` to break returns down by regime (bull vs bear vs choppy).

---

## Interpreting Results Carefully

### Sample Size

With 5 tickers and 2 years at monthly frequency, you get ~120 observations total. With 4 decision buckets, that is ~30 per bucket on average — too few for statistical confidence. Run more tickers or longer periods before drawing strong conclusions.

A minimum of 50 observations per decision bucket is a reasonable threshold for trusting the averages.

### Survivorship Bias

All tickers in the analysis must have historical data available. Stocks that were acquired, delisted, or went bankrupt have incomplete data and may be excluded. This inflates measured returns for the avoid universe because the worst outcomes (total loss) are missing.

### Fundamental Lookahead (Repeated)

If a stock that was deteriorating in 2022 recovered by 2024, the quality gate will pass it for all 2022 dates using its current (recovered) fundamentals. Those observations will be on the quality-intact path, which inflates BUY/WAIT return quality. The buy-side *timing* signals are not affected since they are price-derived.

---

## Modifying the Loser Universe

Edit `backtest/loser_universe.json` to add or remove tickers:

```json
["INTC", "PFE", "BABA", "T", "MPW", "DLTR", "WBA", "VFC",
 "PARA", "BEN", "MO", "CVS", "MMM"]
```

Good candidates for the loser universe: stocks with multi-year revenue decline, sustained margin compression, repeated earnings misses, and significant equity destruction. The purpose is to validate that the engine correctly routes them to AVOID.
