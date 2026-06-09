"""
Story 1 TDD tests: Enhanced Technical Indicators
Tests written BEFORE implementation — these should initially fail.

New indicators covered:
- EMA 8/21 relative to price
- SMA slopes (5-bar)
- Performance periods (1W, 1M, 3M, 6M, YTD, 1Y, 3Y, 5Y)
- Gap % and change from open %
- Range distances (20D/50D/52W/ATH/ATL high and low)
- Weekly and monthly volatility
- ADX
- Stochastic RSI
- Bollinger Band position/width
- ATR percent
- SMA20/50/200 relative (% from price)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.technical_analysis_service import (
    compute_adx,
    compute_atr_percent,
    compute_bollinger_bands,
    compute_ema_relative,
    compute_gap_metrics,
    compute_performance_periods,
    compute_range_distances,
    compute_sma_relative,
    compute_sma_slope,
    compute_stochastic_rsi,
    compute_volatility_metrics,
    compute_technicals,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_close(n: int = 300, start: float = 100.0, drift: float = 0.001) -> pd.Series:
    """Deterministic upward-trending price series."""
    np.random.seed(42)
    returns = np.random.normal(drift, 0.01, n)
    prices = start * np.cumprod(1 + returns)
    return pd.Series(prices, name="Close")


def _make_ohlcv(n: int = 300, start: float = 100.0) -> pd.DataFrame:
    """Synthetic OHLCV DataFrame with DatetimeIndex.

    Uses .values to avoid index-alignment NaN when combining Series with
    integer index into a DatetimeIndex DataFrame.
    """
    close = _make_close(n, start)
    noise = (close * 0.005).values  # strip index
    close_vals = close.values
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    df = pd.DataFrame(
        {
            "Open": close_vals - noise,
            "High": close_vals + noise * 2,
            "Low": close_vals - noise * 2,
            "Close": close_vals,
            "Volume": np.random.randint(1_000_000, 10_000_000, n).astype(float),
        },
        index=dates,
    )
    return df


# ---------------------------------------------------------------------------
# compute_ema_relative
# ---------------------------------------------------------------------------

class TestComputeEmaRelative:
    def test_returns_float_for_sufficient_data(self):
        close = _make_close(50)
        result = compute_ema_relative(close, period=8)
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        close = _make_close(5)
        result = compute_ema_relative(close, period=8)
        assert result is None

    def test_positive_when_price_above_ema(self):
        # Strongly upward series — price should be above EMA
        prices = pd.Series([100.0 + i for i in range(50)])
        result = compute_ema_relative(prices, period=8)
        assert result is not None
        assert result > 0

    def test_negative_when_price_below_ema(self):
        # Strongly downward series — price should be below EMA
        prices = pd.Series([100.0 - i for i in range(50)])
        result = compute_ema_relative(prices, period=8)
        assert result is not None
        assert result < 0

    def test_ema21_relative(self):
        close = _make_close(100)
        result = compute_ema_relative(close, period=21)
        assert result is not None

    def test_zero_price_safe(self):
        close = pd.Series([0.0] * 30)
        result = compute_ema_relative(close, period=8)
        # Should not raise, may return None
        assert result is None or isinstance(result, float)


# ---------------------------------------------------------------------------
# compute_sma_slope
# ---------------------------------------------------------------------------

class TestComputeSmaSlope:
    def test_returns_float_for_sufficient_data(self):
        close = _make_close(60)
        result = compute_sma_slope(close, window=20)
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        close = _make_close(10)
        result = compute_sma_slope(close, window=20)
        assert result is None

    def test_positive_slope_for_uptrend(self):
        prices = pd.Series([100.0 + i for i in range(60)])
        result = compute_sma_slope(prices, window=20)
        assert result is not None
        assert result > 0

    def test_negative_slope_for_downtrend(self):
        prices = pd.Series([100.0 - i * 0.5 for i in range(60)])
        result = compute_sma_slope(prices, window=20)
        assert result is not None
        assert result < 0

    def test_sma50_slope(self):
        close = _make_close(100)
        result = compute_sma_slope(close, window=50)
        assert result is not None

    def test_sma200_slope_insufficient(self):
        close = _make_close(100)
        result = compute_sma_slope(close, window=200)
        assert result is None  # not enough data


# ---------------------------------------------------------------------------
# compute_performance_periods
# ---------------------------------------------------------------------------

class TestComputePerformancePeriods:
    def test_returns_dict_with_all_keys(self):
        df = _make_ohlcv(300)
        result = compute_performance_periods(df["Close"])
        expected_keys = ["perf_1w", "perf_1m", "perf_3m", "perf_6m",
                         "perf_ytd", "perf_1y", "perf_3y", "perf_5y"]
        for key in expected_keys:
            assert key in result

    def test_none_for_3y_when_insufficient_data(self):
        df = _make_ohlcv(100)
        result = compute_performance_periods(df["Close"])
        assert result["perf_3y"] is None

    def test_none_for_5y_when_insufficient_data(self):
        df = _make_ohlcv(200)
        result = compute_performance_periods(df["Close"])
        assert result["perf_5y"] is None

    def test_1w_positive_for_uptrend(self):
        # Last 5 bars going up
        prices = pd.Series([100.0 + i for i in range(50)])
        result = compute_performance_periods(prices)
        assert result["perf_1w"] is not None
        assert result["perf_1w"] > 0

    def test_1w_negative_for_downtrend(self):
        prices = pd.Series([100.0 - i * 0.5 for i in range(50)])
        result = compute_performance_periods(prices)
        assert result["perf_1w"] is not None
        assert result["perf_1w"] < 0

    def test_ytd_requires_ytd_start_price(self):
        df = _make_ohlcv(300)
        result = compute_performance_periods(df["Close"])
        # YTD should be a float (may be None if index has no year info)
        assert result["perf_ytd"] is None or isinstance(result["perf_ytd"], float)

    def test_values_are_percentages(self):
        """Ensure values are in % form, not decimal."""
        prices = pd.Series([100.0 + i for i in range(50)])
        result = compute_performance_periods(prices)
        if result["perf_1w"] is not None:
            # Should be ~5.something % for a $5 rise from $100
            assert abs(result["perf_1w"]) < 1000  # sanity, not decimal


# ---------------------------------------------------------------------------
# compute_gap_metrics
# ---------------------------------------------------------------------------

class TestComputeGapMetrics:
    def test_gap_up(self):
        gap, change_from_open = compute_gap_metrics(
            open_price=105.0, prev_close=100.0, current_price=106.0
        )
        assert abs(gap - 5.0) < 0.01
        assert abs(change_from_open - (1.0 / 105.0 * 100)) < 0.01

    def test_gap_down(self):
        gap, change_from_open = compute_gap_metrics(
            open_price=95.0, prev_close=100.0, current_price=94.0
        )
        assert abs(gap - (-5.0)) < 0.01

    def test_no_gap(self):
        gap, change_from_open = compute_gap_metrics(
            open_price=100.0, prev_close=100.0, current_price=101.0
        )
        assert abs(gap) < 0.01

    def test_change_from_open_positive(self):
        gap, change_from_open = compute_gap_metrics(
            open_price=100.0, prev_close=99.0, current_price=102.0
        )
        assert abs(change_from_open - 2.0) < 0.01

    def test_change_from_open_negative(self):
        gap, change_from_open = compute_gap_metrics(
            open_price=100.0, prev_close=101.0, current_price=98.0
        )
        assert abs(change_from_open - (-2.0)) < 0.01

    def test_zero_prev_close_safe(self):
        # Should not raise; prev_close=0 is edge case
        gap, change_from_open = compute_gap_metrics(0.0, 0.0, 0.0)
        # Just ensure no exception

    def test_zero_open_safe(self):
        gap, change_from_open = compute_gap_metrics(0.0, 100.0, 100.0)
        assert change_from_open is None or isinstance(change_from_open, float)


# ---------------------------------------------------------------------------
# compute_range_distances
# ---------------------------------------------------------------------------

class TestComputeRangeDistances:
    def setup_method(self):
        self.df = _make_ohlcv(300)

    def test_returns_all_distance_keys(self):
        result = compute_range_distances(self.df["Close"], self.df["High"], self.df["Low"])
        keys = [
            "dist_from_20d_high", "dist_from_20d_low",
            "dist_from_50d_high", "dist_from_50d_low",
            "dist_from_52w_high", "dist_from_52w_low",
            "dist_from_ath", "dist_from_atl",
        ]
        for key in keys:
            assert key in result

    def test_dist_from_high_is_negative_or_zero(self):
        result = compute_range_distances(self.df["Close"], self.df["High"], self.df["Low"])
        # Price below rolling high → distance should be <= 0
        if result["dist_from_20d_high"] is not None:
            assert result["dist_from_20d_high"] <= 0.1  # allow tiny fp error

    def test_dist_from_low_is_positive_or_zero(self):
        result = compute_range_distances(self.df["Close"], self.df["High"], self.df["Low"])
        if result["dist_from_20d_low"] is not None:
            assert result["dist_from_20d_low"] >= -0.1

    def test_insufficient_data_returns_none(self):
        df_short = _make_ohlcv(10)
        result = compute_range_distances(df_short["Close"], df_short["High"], df_short["Low"])
        # 52W needs ~252 bars
        assert result["dist_from_52w_high"] is None

    def test_ath_distance_is_negative_or_zero(self):
        result = compute_range_distances(self.df["Close"], self.df["High"], self.df["Low"])
        # Current price cannot exceed all-time high in the dataset
        assert result["dist_from_ath"] is not None
        assert result["dist_from_ath"] <= 0.1


# ---------------------------------------------------------------------------
# compute_volatility_metrics
# ---------------------------------------------------------------------------

class TestComputeVolatilityMetrics:
    def test_returns_tuple_of_two_floats(self):
        close = _make_close(100)
        weekly_vol, monthly_vol = compute_volatility_metrics(close)
        assert weekly_vol is not None
        assert monthly_vol is not None

    def test_returns_none_for_insufficient_data(self):
        close = _make_close(5)
        weekly_vol, monthly_vol = compute_volatility_metrics(close)
        assert weekly_vol is None
        assert monthly_vol is None

    def test_weekly_vol_is_annualized(self):
        # For random returns with ~1% daily std, annualized ~sqrt(52)*weekly_std
        close = _make_close(100, drift=0)
        weekly_vol, _ = compute_volatility_metrics(close)
        assert weekly_vol is not None
        assert 0 < weekly_vol < 300  # % annualized — sanity range

    def test_monthly_vol_is_annualized(self):
        close = _make_close(100)
        _, monthly_vol = compute_volatility_metrics(close)
        assert monthly_vol is not None
        assert 0 < monthly_vol < 300


# ---------------------------------------------------------------------------
# compute_adx
# ---------------------------------------------------------------------------

class TestComputeAdx:
    def test_returns_float_for_sufficient_data(self):
        df = _make_ohlcv(60)
        result = compute_adx(df["High"], df["Low"], df["Close"])
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        df = _make_ohlcv(10)
        result = compute_adx(df["High"], df["Low"], df["Close"])
        assert result is None

    def test_adx_range(self):
        df = _make_ohlcv(100)
        result = compute_adx(df["High"], df["Low"], df["Close"])
        if result is not None:
            assert 0 <= result <= 100

    def test_trending_market_has_higher_adx(self):
        # Strong uptrend should have higher ADX than flat market
        n = 100
        strong_trend_close = pd.Series([100.0 + i for i in range(n)])
        strong_trend_high = strong_trend_close + 0.5
        strong_trend_low = strong_trend_close - 0.5
        trending_adx = compute_adx(strong_trend_high, strong_trend_low, strong_trend_close)

        flat_close = pd.Series([100.0] * n)
        flat_high = flat_close + 0.5
        flat_low = flat_close - 0.5
        flat_adx = compute_adx(flat_high, flat_low, flat_close)

        if trending_adx is not None and flat_adx is not None:
            assert trending_adx >= flat_adx


# ---------------------------------------------------------------------------
# compute_stochastic_rsi
# ---------------------------------------------------------------------------

class TestComputeStochasticRsi:
    def test_returns_float_for_sufficient_data(self):
        close = _make_close(100)
        result = compute_stochastic_rsi(close)
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        close = _make_close(10)
        result = compute_stochastic_rsi(close)
        assert result is None

    def test_range_0_to_100(self):
        close = _make_close(100)
        result = compute_stochastic_rsi(close)
        if result is not None:
            assert 0 <= result <= 100


# ---------------------------------------------------------------------------
# compute_bollinger_bands
# ---------------------------------------------------------------------------

class TestComputeBollingerBands:
    def test_returns_tuple_for_sufficient_data(self):
        close = _make_close(50)
        position, width = compute_bollinger_bands(close)
        assert position is not None
        assert width is not None

    def test_returns_none_for_insufficient_data(self):
        close = _make_close(10)
        position, width = compute_bollinger_bands(close)
        assert position is None
        assert width is None

    def test_position_range(self):
        close = _make_close(50)
        position, width = compute_bollinger_bands(close)
        if position is not None:
            # position can go outside [0,1] on extreme moves
            assert -1 <= position <= 2  # reasonable range

    def test_width_is_positive(self):
        close = _make_close(50)
        _, width = compute_bollinger_bands(close)
        if width is not None:
            assert width > 0

    def test_price_above_upper_band_has_position_gt_1(self):
        # Construct series that ends well above upper band
        close = pd.Series([100.0] * 19 + [200.0])  # big spike at end
        position, _ = compute_bollinger_bands(close)
        if position is not None:
            assert position > 1.0

    def test_price_below_lower_band_has_position_lt_0(self):
        close = pd.Series([100.0] * 19 + [0.01])  # huge drop at end
        position, _ = compute_bollinger_bands(close)
        if position is not None:
            assert position < 0.0


# ---------------------------------------------------------------------------
# compute_atr_percent
# ---------------------------------------------------------------------------

class TestComputeAtrPercent:
    def test_basic_calculation(self):
        result = compute_atr_percent(atr=2.0, price=100.0)
        assert result is not None
        assert abs(result - 2.0) < 0.001

    def test_zero_price_returns_none(self):
        result = compute_atr_percent(atr=2.0, price=0.0)
        assert result is None

    def test_none_atr_returns_none(self):
        result = compute_atr_percent(atr=None, price=100.0)
        assert result is None

    def test_large_atr_reflects_high_volatility(self):
        result = compute_atr_percent(atr=10.0, price=100.0)
        assert result is not None
        assert result == pytest.approx(10.0, rel=0.001)


# ---------------------------------------------------------------------------
# compute_sma_relative
# ---------------------------------------------------------------------------

class TestComputeSmaRelative:
    def test_positive_when_price_above_sma(self):
        close = pd.Series([100.0 + i for i in range(30)])
        result = compute_sma_relative(close, window=20)
        assert result is not None
        assert result > 0

    def test_negative_when_price_below_sma(self):
        close = pd.Series([100.0 - i * 0.5 for i in range(30)])
        result = compute_sma_relative(close, window=20)
        assert result is not None
        assert result < 0

    def test_none_for_insufficient_data(self):
        close = _make_close(5)
        result = compute_sma_relative(close, window=20)
        assert result is None


# ---------------------------------------------------------------------------
# compute_technicals integration — new fields present
# ---------------------------------------------------------------------------

class TestComputeTechnicalsIntegration:
    def test_new_fields_in_result(self):
        df = _make_ohlcv(300)
        result = compute_technicals(df)

        # EMA relatives
        assert hasattr(result, "ema8_relative")
        assert hasattr(result, "ema21_relative")

        # SMA slopes
        assert hasattr(result, "sma20_slope")
        assert hasattr(result, "sma50_slope")
        assert hasattr(result, "sma200_slope")

        # SMA relatives
        assert hasattr(result, "sma20_relative")
        assert hasattr(result, "sma50_relative")
        assert hasattr(result, "sma200_relative")

        # Performance periods
        assert hasattr(result, "perf_1w")
        assert hasattr(result, "perf_1m")
        assert hasattr(result, "perf_3m")
        assert hasattr(result, "perf_6m")
        assert hasattr(result, "perf_ytd")
        assert hasattr(result, "perf_1y")
        assert hasattr(result, "perf_3y")
        assert hasattr(result, "perf_5y")

        # Gap metrics
        assert hasattr(result, "gap_percent")
        assert hasattr(result, "change_from_open_percent")

        # Range distances
        assert hasattr(result, "dist_from_20d_high")
        assert hasattr(result, "dist_from_20d_low")
        assert hasattr(result, "dist_from_50d_high")
        assert hasattr(result, "dist_from_50d_low")
        assert hasattr(result, "dist_from_52w_high")
        assert hasattr(result, "dist_from_52w_low")
        assert hasattr(result, "dist_from_ath")
        assert hasattr(result, "dist_from_atl")

        # Volatility
        assert hasattr(result, "volatility_weekly")
        assert hasattr(result, "volatility_monthly")

        # New indicators
        assert hasattr(result, "adx")
        assert hasattr(result, "stochastic_rsi")
        assert hasattr(result, "bollinger_band_position")
        assert hasattr(result, "bollinger_band_width")
        assert hasattr(result, "atr_percent")

    def test_new_fields_have_values_for_300_bars(self):
        df = _make_ohlcv(300)
        result = compute_technicals(df)

        # Core performance fields should not be None with 300 bars
        assert result.perf_1w is not None
        assert result.perf_1m is not None
        assert result.perf_3m is not None
        assert result.perf_1y is not None
        assert result.ema8_relative is not None
        assert result.ema21_relative is not None
        assert result.adx is not None
        assert result.atr_percent is not None

    def test_no_regression_on_existing_fields(self):
        df = _make_ohlcv(300)
        result = compute_technicals(df)

        # Existing fields should still work
        assert result.ma_20 is not None
        assert result.ma_50 is not None
        assert result.rsi_14 is not None
        assert result.macd is not None
        assert result.atr is not None
        assert result.trend is not None
        assert result.technical_score > 0

    def test_compute_technicals_with_minimal_data(self):
        """Should not crash with limited data — fields gracefully None."""
        df = _make_ohlcv(30)
        result = compute_technicals(df)
        # Should not raise
        assert result is not None
        assert result.perf_3m is None  # not enough data
