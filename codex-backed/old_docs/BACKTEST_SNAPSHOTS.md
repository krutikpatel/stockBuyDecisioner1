# Backtest Snapshots

A running log of baseline snapshots taken before making significant changes. Each entry captures the full metric set so regressions are easy to spot.

Each trade is simulated under both exit horizons, so short_term and medium_term trade counts always sum to the total. Results are shown separately for each horizon.

---

## 2026-06-12 — `baseline_20260612`

**Context:** Post entry-optimization loop (entry_exp_71–99). Configs reflect the most restrictive entry filters after ~30 entry-tuning iterations. Recording as pre-change baseline.

### Run Info

| Metric | Value |
|--------|-------|
| Tickers | 199 |
| Feature rows | 158,208 |
| Entry decisions | 158,208 |
| Total trades (both horizons) | 102 |

### Short-term Results

| Metric | Value |
|--------|-------|
| Trades | 51 |
| Avg return | 17.57% |
| Median return | 11.99% |
| Win rate | 98.04% |
| Profit factor | 205.53 |

### Medium-term Results

| Metric | Value |
|--------|-------|
| Trades | 51 |
| Avg return | 12.63% |
| Median return | 0.05% |
| Win rate | 98.04% |
| Profit factor | 111.50 |

### By Entry Label

| Label | Trades | Avg return | Win rate |
|-------|--------|------------|----------|
| BUY_FULL | 32 | 14.79% | 100.0% |
| BUY_STARTER | 70 | 15.24% | 97.14% |

### By Exit Reason

| Exit reason | Trades | Avg return | Win rate |
|-------------|--------|------------|----------|
| TRAILING_STOP_EXIT | 46 | 18.70% | 100.0% |
| STOP_LOSS_EXIT | 42 | -0.20% | 95.24% |
| MAX_SIM_WINDOW_EXIT | 14 | 49.16% | 100.0% |

### Setup Distribution

| Setup | Total signals | Actionable | Actionable rate |
|-------|--------------|------------|-----------------|
| BROKEN_CHART_QUALITY_RECOVERY | 526 | 102 | 19.4% |
| BREAKOUT_MOMENTUM | 2,048 | 0 | 0.0% |
| DOWNTREND_REBOUND_CANDIDATE | 6,126 | 0 | 0.0% |
| GROWTH_LEADER_PULLBACK | 1,718 | 0 | 0.0% |
| TRUE_BROKEN_CHART_AVOID | 1,370 | 0 | 0.0% |

### Notable Tickers

| Ticker | Trades | Avg return |
|--------|--------|------------|
| MU | 2 | 143.17% |
| QCOM | 2 | 62.91% |
| NUE | 2 | 37.31% |
| DD | 4 | 34.07% |
| PEG | 2 | 29.95% |
| ROKU | 10 | 0.01% |

### Flags / Known Issues

- Only `BROKEN_CHART_QUALITY_RECOVERY` produces trades; all other setups are fully blocked — likely over-tightened entry filters from the optimization loop.
- 98% win rate with 102 trades is a red flag for overfitting.
- ROKU (10 trades, ~0% avg) inflates trade count without real edge; stop-loss exits near breakeven.
- Median (2.39%) vs mean (15.10%) gap is large — a handful of outliers (MU, QCOM) drive the average.

### Config state (feature cache key)

`0084d622d2366aff`
