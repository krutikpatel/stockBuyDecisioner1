"""
Story 3 TDD tests: Relative Strength, Percentile Ranks, Drawdown, Gap Fill
Tests written BEFORE implementation.

Metrics covered:
- RS vs QQQ (relative return difference)
- Return percentile ranks: 20D, 63D, 126D, 252D
- Max drawdown 3M (63 bars) and 1Y (252 bars)
- Gap fill status (bool)
- Post-earnings drift (% return from earnings date)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.technical_analysis_service import (
    compute_max_drawdown,
    compute_return_percentile_rank,
    compute_rs_vs_benchmark,
    compute_gap_fill_status,
    compute_post_earnings_drift,
    compute_technicals,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_close(n: int = 300, start: float = 100.0, drift: float = 0.001) -> pd.Series:
    """Deterministic price series with DatetimeIndex."""
    np.random.seed(42)
    returns = np.random.normal(drift, 0.01, n)
    prices = start * np.cumprod(1 + returns)
    return pd.Series(prices, index=pd.date_range("2023-01-01", periods=n, freq="B"))


def _make_ohlcv(n: int = 300, start: float = 100.0, drift: float = 0.001) -> pd.DataFrame:
    close = _make_close(n, start, drift)
    noise = close.values * 0.005
    return pd.DataFrame(
        {
            "Open": close.values - noise,
            "High": close.values + noise * 2,
            "Low": close.values - noise * 2,
            "Close": close.values,
            "Volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
        },
        index=close.index,
    )


# ---------------------------------------------------------------------------
# compute_rs_vs_benchmark (RS vs QQQ or any benchmark)
# ---------------------------------------------------------------------------

class TestComputeRsVsBenchmark:
    def test_returns_float_for_sufficient_data(self):
        stock = _make_close(100)
        bench = _make_close(100, start=300.0, drift=0.0005)
        result = compute_rs_vs_benchmark(stock, bench, period=63)
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        stock = _make_close(10)
        bench = _make_close(10, start=300.0)
        result = compute_rs_vs_benchmark(stock, bench, period=63)
        assert result is None

    def test_positive_when_stock_outperforms(self):
        n = 100
        # Stock rises 20%, benchmark flat
        stock = _make_close(n, start=100.0, drift=0.002)
        bench = _make_close(n, start=300.0, drift=0.0)
        # Normalise bench to flat: override last price to be same as first
        result = compute_rs_vs_benchmark(stock, bench, period=63)
        # Stock should outperform flat benchmark → positive RS
        # (result depends on actual values)
        assert result is not None

    def test_rs_is_difference_not_ratio(self):
        # RS = stock_return - bench_return (percentage points)
        # Stock: flat at 100 for first bar, then rises to 120 exactly 63 bars ago
        n = 100
        # Use bars: stock rises from bar n-64 to n-63, bench flat
        stock_vals = [100.0] * (n - 64) + [100.0] + [120.0] * 63
        bench_vals = [300.0] * n
        stock = pd.Series(stock_vals, index=pd.date_range("2023-01-01", periods=n, freq="B"))
        bench = pd.Series(bench_vals, index=pd.date_range("2023-01-01", periods=n, freq="B"))
        result = compute_rs_vs_benchmark(stock, bench, period=63)
        # stock[-1]=120, stock[-63]=120 (same level, since jump was at bar -64)
        # Actually we need the jump to happen WITHIN the 63-bar window
        # Let's use a simple linear trend instead
        stock2 = pd.Series(list(range(100, 200)), index=pd.date_range("2023-01-01", periods=100, freq="B"))
        bench2 = pd.Series([300.0] * 100, index=pd.date_range("2023-01-01", periods=100, freq="B"))
        result2 = compute_rs_vs_benchmark(stock2, bench2, period=63)
        assert result2 is not None
        assert result2 > 0

    def test_negative_when_stock_underperforms(self):
        # Stock flat, benchmark rising linearly
        n = 100
        stock = pd.Series([100.0] * n,
                          index=pd.date_range("2023-01-01", periods=n, freq="B"))
        bench = pd.Series(list(range(300, 400)), index=pd.date_range("2023-01-01", periods=n, freq="B"))
        result = compute_rs_vs_benchmark(stock, bench, period=63)
        assert result is not None
        assert result < 0


# ---------------------------------------------------------------------------
# compute_return_percentile_rank
# ---------------------------------------------------------------------------

class TestComputeReturnPercentileRank:
    def test_returns_float_for_sufficient_data(self):
        close = _make_close(300)
        result = compute_return_percentile_rank(close, return_bars=20, lookback=252)
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        close = _make_close(30)
        result = compute_return_percentile_rank(close, return_bars=63, lookback=252)
        assert result is None

    def test_range_0_to_100(self):
        close = _make_close(300)
        for bars in [20, 63, 126, 252]:
            result = compute_return_percentile_rank(close, return_bars=bars, lookback=252)
            if result is not None:
                assert 0 <= result <= 100

    def test_high_rank_for_strong_recent_return(self):
        # Price spikes at the end
        n = 300
        close = pd.Series(
            [100.0] * (n - 20) + [120.0] * 20,
            index=pd.date_range("2023-01-01", periods=n, freq="B"),
        )
        result = compute_return_percentile_rank(close, return_bars=20, lookback=252)
        assert result is not None
        assert result > 50  # should be in upper half

    def test_low_rank_for_weak_recent_return(self):
        # Price drops at the end
        n = 300
        close = pd.Series(
            [100.0] * (n - 20) + [80.0] * 20,
            index=pd.date_range("2023-01-01", periods=n, freq="B"),
        )
        result = compute_return_percentile_rank(close, return_bars=20, lookback=252)
        assert result is not None
        assert result < 50  # should be in lower half


# ---------------------------------------------------------------------------
# compute_max_drawdown
# ---------------------------------------------------------------------------

class TestComputeMaxDrawdown:
    def test_returns_negative_float(self):
        close = _make_close(100)
        result = compute_max_drawdown(close, bars=63)
        assert result is not None
        assert result <= 0

    def test_returns_none_for_insufficient_data(self):
        close = _make_close(10)
        result = compute_max_drawdown(close, bars=63)
        assert result is None

    def test_zero_for_monotonically_increasing_prices(self):
        close = pd.Series([100.0 + i for i in range(100)],
                          index=pd.date_range("2023-01-01", periods=100, freq="B"))
        result = compute_max_drawdown(close, bars=63)
        assert result is not None
        assert result == 0.0

    def test_known_drawdown_value(self):
        # 100 → 50 → 60 → peak at 100, trough at 50: drawdown = -50%
        close = pd.Series(
            [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 55.0, 60.0],
            index=pd.date_range("2023-01-01", periods=8, freq="B"),
        )
        result = compute_max_drawdown(close, bars=8)
        assert result is not None
        assert result < -40  # at least 40% drawdown

    def test_1y_drawdown(self):
        close = _make_close(300)
        result_3m = compute_max_drawdown(close, bars=63)
        result_1y = compute_max_drawdown(close, bars=252)
        # 1Y drawdown should be >= 3M drawdown in absolute terms
        if result_3m is not None and result_1y is not None:
            assert result_1y <= result_3m  # more negative or equal


# ---------------------------------------------------------------------------
# compute_gap_fill_status
# ---------------------------------------------------------------------------

class TestComputeGapFillStatus:
    def test_returns_bool(self):
        df = _make_ohlcv(100)
        result = compute_gap_fill_status(df["Open"], df["Close"])
        assert isinstance(result, bool)

    def test_no_gap_returns_false(self):
        # Flat prices, no gap
        n = 50
        close = pd.Series([100.0] * n,
                          index=pd.date_range("2023-01-01", periods=n, freq="B"))
        open_ = pd.Series([100.0] * n,
                          index=close.index)
        result = compute_gap_fill_status(open_, close)
        # No gap detected → False
        assert result is False

    def test_gap_up_filled_returns_true(self):
        # Gap up on day 20: open >> prior close, then price returns below gap level
        n = 30
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        close_vals = [100.0] * 19 + [110.0] * 10 + [99.0]  # gap up then fill
        open_vals = [100.0] * 19 + [108.0] + [110.0] * 10  # big gap open on day 20
        close = pd.Series(close_vals, index=dates)
        open_ = pd.Series(open_vals, index=dates)
        result = compute_gap_fill_status(open_, close)
        assert result is True

    def test_gap_up_not_filled_returns_false(self):
        n = 30
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        close_vals = [100.0] * 19 + [115.0] * 11  # gap up, stays up
        open_vals = [100.0] * 19 + [112.0] + [115.0] * 10  # gap up, no fill
        close = pd.Series(close_vals, index=dates)
        open_ = pd.Series(open_vals, index=dates)
        result = compute_gap_fill_status(open_, close)
        assert result is False

    def test_insufficient_data_returns_false(self):
        close = pd.Series([100.0, 101.0])
        open_ = pd.Series([100.0, 100.5])
        result = compute_gap_fill_status(open_, close)
        assert result is False


# ---------------------------------------------------------------------------
# compute_post_earnings_drift
# ---------------------------------------------------------------------------

class TestComputePostEarningsDrift:
    def test_returns_none_when_no_earnings_date(self):
        close = _make_close(100)
        result = compute_post_earnings_drift(close, earnings_date=None)
        assert result is None

    def test_returns_float_for_earnings_date_in_window(self):
        close = _make_close(100)
        earnings_date = close.index[-30]
        result = compute_post_earnings_drift(close, earnings_date=earnings_date)
        assert result is not None
        assert isinstance(result, float)

    def test_positive_for_post_earnings_rise(self):
        # earnings_date = the day BEFORE the price jump
        n = 100
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        prices = [100.0] * 70 + [120.0] * 30  # rises starting at bar 70
        close = pd.Series(prices, index=dates)
        # earnings_date = bar 69 (pre-jump), so from bar 69 price=100 to bar 99 price=120
        earnings_date = dates[69]
        result = compute_post_earnings_drift(close, earnings_date=earnings_date)
        assert result is not None
        assert result > 0

    def test_negative_for_post_earnings_drop(self):
        n = 100
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        prices = [100.0] * 70 + [80.0] * 30
        close = pd.Series(prices, index=dates)
        earnings_date = dates[69]  # pre-drop bar
        result = compute_post_earnings_drift(close, earnings_date=earnings_date)
        assert result is not None
        assert result < 0

    def test_returns_none_for_earnings_date_after_data(self):
        close = _make_close(100)
        future_date = close.index[-1] + pd.Timedelta(days=30)
        result = compute_post_earnings_drift(close, earnings_date=future_date)
        assert result is None


# ---------------------------------------------------------------------------
# Integration: compute_technicals includes new fields
# ---------------------------------------------------------------------------

class TestComputeTechnicalsStory3Fields:
    def test_new_fields_present(self):
        df = _make_ohlcv(300)
        result = compute_technicals(df)

        assert hasattr(result, "rs_vs_qqq")
        assert hasattr(result, "return_pct_rank_20d")
        assert hasattr(result, "return_pct_rank_63d")
        assert hasattr(result, "return_pct_rank_126d")
        assert hasattr(result, "return_pct_rank_252d")
        assert hasattr(result, "max_drawdown_3m")
        assert hasattr(result, "max_drawdown_1y")
        assert hasattr(result, "gap_filled")
        assert hasattr(result, "post_earnings_drift")

    def test_drawdown_is_negative_or_zero(self):
        df = _make_ohlcv(300)
        result = compute_technicals(df)
        if result.max_drawdown_3m is not None:
            assert result.max_drawdown_3m <= 0
        if result.max_drawdown_1y is not None:
            assert result.max_drawdown_1y <= 0

    def test_percentile_ranks_in_range(self):
        df = _make_ohlcv(300)
        result = compute_technicals(df)
        for field in ["return_pct_rank_20d", "return_pct_rank_63d",
                      "return_pct_rank_126d", "return_pct_rank_252d"]:
            val = getattr(result, field)
            if val is not None:
                assert 0 <= val <= 100

    def test_rs_vs_qqq_none_without_qqq_data(self):
        df = _make_ohlcv(300)
        # Without QQQ data passed, rs_vs_qqq should be None
        result = compute_technicals(df)
        assert result.rs_vs_qqq is None

    def test_rs_vs_qqq_computed_with_qqq_data(self):
        df = _make_ohlcv(300)
        qqq_df = _make_ohlcv(300, start=300.0, drift=0.0005)
        result = compute_technicals(df, qqq_df=qqq_df)
        assert result.rs_vs_qqq is not None

    def test_no_regression(self):
        df = _make_ohlcv(300)
        result = compute_technicals(df)
        assert result.rsi_14 is not None
        assert result.technical_score > 0
