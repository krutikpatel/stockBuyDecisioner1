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

---

## Round 2: Indicator Time-Series Cache

### Problem: `compute_technicals` — remaining bottleneck (84% of post-round-1 runtime)

After round 1, `compute_technicals` still takes ~12s per 780 snapshots. It recomputes all 40+ indicators (RSI, MACD, ADX, SMAs, Bollinger Bands, etc.) from scratch for every (ticker, date) pair, even though ~85% of indicators depend only on the stock's own price history and are identical across tickers for the same stock.

### Solution: Indicator cache (`backtest/indicator_cache.py`)

**Indicator classification:**
- **Ticker-only (cacheable, ~85%)**: All indicators using only the stock's own close/high/low/volume — SMAs, EMAs, RSI, MACD, ADX, StochRSI, ATR, Bollinger Bands, volume metrics, performance periods, range distances, support/resistance, etc.
- **Benchmark-dependent (inline, ~15%)**: `rs_vs_spy`, `rs_vs_spy_20d`, `rs_vs_spy_63d`, `rs_vs_qqq`, `rs_vs_sector`, `rs_vs_sector_20d`, `rs_vs_sector_63d` — require SPY/QQQ/sector slices.

**Cache format**: `dict[ticker][date_iso] → TechnicalIndicators` (Pydantic object, RS fields = None in stored version).

**Cache file**: `backtest/cache/indicators.pkl`

**Invalidation**: Auto-rebuilds if `indicators.pkl` missing or `prices.pkl` is newer. Also triggered by `--force-refresh`.

**Correctness**: `technical_score` uses `rs_spy` (±5–10 pts). After loading from cache, `_attach_rs_fields()` computes all 7 RS fields inline and calls `score_technicals()` to recompute `technical_score`. Output is **identical** to a full `compute_technicals` call (verified: 0 mismatches across all fields).

### Round 2 Results

Same benchmark (5 tickers × 156 dates × 3 horizons):

| Run type | Wall time | vs original (68.8s) |
|----------|-----------|---------------------|
| Original (pre-round-1) | 68.8 s | baseline |
| Round 1 (searchsorted + regime cache) | 14.5 s | 4.75x faster |
| Round 2, first run (builds indicator cache) | 5.9 s | **11.7x faster** |
| Round 2, second run (cache loaded from disk) | 0.91 s | **75x faster** |

On subsequent runs (the common case during iterative backtesting), the cache load + RS attachment reduces `compute_technicals` from the dominant cost to effectively zero.

### Round 2 Files Changed

| File | Change |
|------|--------|
| `backtest/indicator_cache.py` | **NEW** — `build_indicator_cache`, `lookup_ticker_indicators`, `_is_stale` |
| `backtest/runner.py` | New `_attach_rs_fields` helper; `force_refresh` param; cache load before main loop; inner-loop cache lookup with fallback |
| `backtest/run_backtest.py` | Pass `force_refresh=args.force_refresh` to `run_backtest()` |

---

## Files Changed (All Rounds)

| File | Change |
|------|--------|
| `backtest/snapshot.py` | `get_price_slice`: `index.map` → `searchsorted` |
| `backtest/outcome.py` | `_get_price_at_offset`, `_max_drawdown_window`: `index.map` → `searchsorted` |
| `backtest/data_loader.py` | Added `_normalize_price_indices`; called on cache load and fresh download |
| `backtest/runner.py` | Per-date regime/VIX cache; indicator cache lookup; `_attach_rs_fields`; `force_refresh` param |
| `backtest/run_backtest.py` | Pass `force_refresh` to `run_backtest()` |
| `backtest/indicator_cache.py` | **NEW** — ticker-only indicator pre-computation and disk cache |
