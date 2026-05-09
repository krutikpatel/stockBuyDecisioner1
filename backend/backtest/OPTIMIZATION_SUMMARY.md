# Backtest Performance Optimization Summary

## Benchmark Setup

- **Tickers**: AAPL, MSFT, NVDA, GOOGL, AMZN (5 tickers)
- **Date range**: 2020-01-01 → 2022-12-31 (156 weekly dates = 780 snapshots)
- **Phase**: 3 (full: technical + regime + fundamentals)
- **Tool**: `cProfile` + `pstats`

## Results

| Metric            | Before     | After     | Improvement     |
|-------------------|-----------|-----------|-----------------|
| Total wall time   | 68.8 s    | 14.5 s    | **4.75x faster** |
| Function calls    | 162.7 M   | 59.7 M    | 63% fewer       |
| `attach_outcomes` | 45.0 s    | 0.9 s     | **50x faster**  |
| `run_backtest`    | 23.5 s    | 13.3 s    | 1.8x faster     |

---

## Root Cause Analysis

### Problem 1: `index.map(_normalize_ts)` — 76% of total runtime

**Location**: `backtest/snapshot.py:get_price_slice` and `backtest/outcome.py:_get_price_at_offset` / `_max_drawdown_window`

Every call to these functions ran:
```python
idx = price_df.index.map(_normalize_ts)   # O(N) Python iteration over full index
return price_df[idx <= norm_date]
```

- `_normalize_ts` was called **43,177,056 times**, creating a `pd.Timestamp` object per element.
- `index.map` iterates element-by-element in Python — no vectorisation.
- Called on DataFrames with ~2,500 rows each, for every (ticker, date, slice) combination.

**Breakdown**:
- `get_price_slice`: called 3,120 times (4 slices × 780 snapshots) → 9.7 s
- `_get_price_at_offset`: called 11,700 times (5 lookups × 3 horizons × 780 signals) → 37.3 s
- `_max_drawdown_window`: called 2,340 times → 7.6 s

### Problem 2: Regime + VIX proxy recomputed per ticker

`classify_regime(spy_slice, qqq_slice)` and the VIX proxy calculation (SPY rolling volatility) were called inside the per-ticker loop — once per ticker per date. Since SPY/QQQ are shared across all tickers, these were computed N_tickers times redundantly for every date.

---

## Changes Made

### 1. `backtest/snapshot.py` — `get_price_slice`

Replaced `index.map(_normalize_ts)` (O(N) Python loop) with `searchsorted` (O(log N) binary search):

```python
# Before
idx = price_df.index.map(_normalize_ts)
return price_df[idx <= norm_date]

# After
pos = price_df.index.searchsorted(norm_date, side="right")
return price_df.iloc[:pos]
```

`searchsorted` works directly on the underlying numpy array — no Python-level iteration, no object allocation per element.

### 2. `backtest/outcome.py` — `_get_price_at_offset` and `_max_drawdown_window`

Same fix applied to both helpers:

```python
# Before
idx_norm    = price_df.index.map(_normalize_ts)
future_mask = idx_norm > norm_from
future_rows = price_df[future_mask]

# After
pos = price_df.index.searchsorted(norm_from, side="right")
future_rows = price_df.iloc[pos:]
```

Also simplified `_max_drawdown_window` to use iloc slicing:
```python
window = price_df.iloc[pos : pos + trading_days]
```

### 3. `backtest/data_loader.py` — Pre-normalize price indices

Added `_normalize_price_indices()` helper that strips timezone from all price DataFrame indices once at load time (both from cache and fresh downloads):

```python
def _normalize_price_indices(prices: dict) -> None:
    for ticker, df in list(prices.items()):
        if not df.empty and getattr(df.index, "tz", None) is not None:
            new_df = df.copy()
            new_df.index = df.index.tz_localize(None)
            prices[ticker] = new_df
```

This ensures all DataFrames have a tz-naive `DatetimeIndex`, which is the prerequisite for `searchsorted` to work correctly without needing `_normalize_ts` on individual elements.

### 4. `backtest/runner.py` — Cache regime + VIX proxy per date

Moved SPY/QQQ slice computation, VIX proxy calculation, and `classify_regime` out of the per-ticker inner loop into a pre-computation pass over dates:

```python
# Pre-compute once per date (shared across all tickers)
_date_state: dict[pd.Timestamp, tuple] = {}
for td in test_dates:
    spy_sl = get_price_slice(spy_full, td)
    qqq_sl = get_price_slice(qqq_full, td)
    vix    = ...  # rolling SPY vol
    regime = classify_regime(spy_sl, qqq_sl, vix_level=vix)
    _date_state[td] = (spy_sl, qqq_sl, vix, regime)

# Inside per-ticker loop: just look up
spy_slice, qqq_slice, vix_proxy, regime_assessment = _date_state[test_date]
```

With N tickers, this reduces regime classification from N×D calls to D calls (D = number of dates).

---

## Remaining Hotspots (after optimization)

After these fixes, `compute_technicals` is now the dominant cost at ~12s (84% of remaining time). It computes ~25 indicators per snapshot including pandas rolling operations, ADX, StochRSI, MACD, etc. This is inherently per-ticker computation and harder to cache. Potential further improvements:

- **Incremental indicator computation**: Instead of recomputing indicators on the full price slice each week, maintain a rolling state and update incrementally (complex refactor).
- **Reduce indicator count**: Profile which signal cards actually use which indicators and skip unused ones.
- **Vectorise across dates**: Pre-compute all indicator time-series for a ticker once, then look up values by date — avoids recomputing from scratch every week.

---

## Files Changed

| File | Change |
|------|--------|
| `backtest/snapshot.py` | `get_price_slice`: `index.map` → `searchsorted` |
| `backtest/outcome.py` | `_get_price_at_offset`, `_max_drawdown_window`: `index.map` → `searchsorted` |
| `backtest/data_loader.py` | Added `_normalize_price_indices`; called on cache load and fresh download |
| `backtest/runner.py` | Pre-compute per-date SPY/QQQ/VIX/regime before ticker loop |
