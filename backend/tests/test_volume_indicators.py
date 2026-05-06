"""
Story 2 TDD tests: Volume & Accumulation Indicators
Tests written BEFORE implementation.

Indicators covered:
- OBV trend score (+1 rising, 0 flat, -1 falling)
- Accumulation/Distribution Line trend score
- Chaikin Money Flow (20-period)
- VWAP deviation % (20-day)
- Anchored VWAP deviation (from last earnings date)
- Volume dry-up ratio
- Breakout volume multiple
- Up/down volume ratio
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.technical_analysis_service import (
    compute_ad_trend,
    compute_chaikin_money_flow,
    compute_obv_trend,
    compute_updown_volume_ratio,
    compute_volume_dryup_ratio,
    compute_vwap_deviation,
    compute_anchored_vwap_deviation,
    compute_technicals,
)


# ---------------------------------------------------------------------------
# Fixtures (reuse pattern from Story 1)
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 60, start: float = 100.0, up: bool = True) -> pd.DataFrame:
    """Synthetic OHLCV with controlled direction."""
    np.random.seed(7)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    drift = 0.002 if up else -0.002
    returns = np.random.normal(drift, 0.008, n)
    close_vals = start * np.cumprod(1 + returns)
    noise = close_vals * 0.004
    volume = np.random.randint(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {
            "Open": close_vals - noise,
            "High": close_vals + noise * 2,
            "Low": close_vals - noise * 2,
            "Close": close_vals,
            "Volume": volume,
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# compute_obv_trend
# ---------------------------------------------------------------------------

class TestComputeObvTrend:
    def test_returns_int_for_sufficient_data(self):
        df = _make_ohlcv(30)
        result = compute_obv_trend(df["Close"], df["Volume"])
        assert result in (-1, 0, 1)

    def test_rising_obv_in_uptrend(self):
        # All days close higher → all volume adds to OBV → OBV rising
        n = 30
        close = pd.Series([100.0 + i for i in range(n)])
        volume = pd.Series([1_000_000.0] * n)
        result = compute_obv_trend(close, volume)
        assert result == 1

    def test_falling_obv_in_downtrend(self):
        # All days close lower → all volume subtracts from OBV → OBV falling
        n = 30
        close = pd.Series([100.0 - i * 0.5 for i in range(n)])
        volume = pd.Series([1_000_000.0] * n)
        result = compute_obv_trend(close, volume)
        assert result == -1

    def test_returns_zero_for_insufficient_data(self):
        df = _make_ohlcv(5)
        result = compute_obv_trend(df["Close"], df["Volume"])
        assert result == 0

    def test_uptrend_df_gives_valid_result(self):
        # With random noise, a slight uptrend may not guarantee rising OBV,
        # but the result must be a valid score.
        df = _make_ohlcv(40, up=True)
        result = compute_obv_trend(df["Close"], df["Volume"])
        assert result in (-1, 0, 1)


# ---------------------------------------------------------------------------
# compute_ad_trend
# ---------------------------------------------------------------------------

class TestComputeAdTrend:
    def test_returns_int_for_sufficient_data(self):
        df = _make_ohlcv(30)
        result = compute_ad_trend(df["High"], df["Low"], df["Close"], df["Volume"])
        assert result in (-1, 0, 1)

    def test_returns_zero_for_insufficient_data(self):
        df = _make_ohlcv(3)
        result = compute_ad_trend(df["High"], df["Low"], df["Close"], df["Volume"])
        assert result == 0

    def test_close_near_high_gives_rising_ad(self):
        # When close is near the high (strong close), MFM is high → AD rises
        n = 30
        close = pd.Series([100.0] * n)
        high = pd.Series([101.0] * n)   # close near high
        low = pd.Series([95.0] * n)
        volume = pd.Series([1_000_000.0] * n)
        result = compute_ad_trend(high, low, close, volume)
        assert result == 1

    def test_close_near_low_gives_falling_ad(self):
        # When close is near the low, MFM is negative → AD falls
        n = 30
        close = pd.Series([96.0] * n)
        high = pd.Series([101.0] * n)
        low = pd.Series([95.0] * n)  # close near low
        volume = pd.Series([1_000_000.0] * n)
        result = compute_ad_trend(high, low, close, volume)
        assert result == -1


# ---------------------------------------------------------------------------
# compute_chaikin_money_flow
# ---------------------------------------------------------------------------

class TestComputeChaikinMoneyFlow:
    def test_returns_float_for_sufficient_data(self):
        df = _make_ohlcv(30)
        result = compute_chaikin_money_flow(df["High"], df["Low"], df["Close"], df["Volume"])
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        df = _make_ohlcv(5)
        result = compute_chaikin_money_flow(df["High"], df["Low"], df["Close"], df["Volume"])
        assert result is None

    def test_range_minus1_to_1(self):
        df = _make_ohlcv(30)
        result = compute_chaikin_money_flow(df["High"], df["Low"], df["Close"], df["Volume"])
        if result is not None:
            assert -1.0 <= result <= 1.0

    def test_positive_when_close_near_high(self):
        n = 25
        close = pd.Series([100.0] * n)
        high = pd.Series([101.0] * n)
        low = pd.Series([95.0] * n)
        volume = pd.Series([1_000_000.0] * n)
        result = compute_chaikin_money_flow(high, low, close, volume)
        assert result is not None
        assert result > 0

    def test_negative_when_close_near_low(self):
        n = 25
        close = pd.Series([96.0] * n)
        high = pd.Series([101.0] * n)
        low = pd.Series([95.0] * n)
        volume = pd.Series([1_000_000.0] * n)
        result = compute_chaikin_money_flow(high, low, close, volume)
        assert result is not None
        assert result < 0

    def test_zero_volume_safe(self):
        n = 25
        close = pd.Series([100.0] * n)
        high = pd.Series([101.0] * n)
        low = pd.Series([99.0] * n)
        volume = pd.Series([0.0] * n)
        result = compute_chaikin_money_flow(high, low, close, volume)
        assert result is None or result == 0.0

    def test_equal_high_low_safe(self):
        n = 25
        close = pd.Series([100.0] * n)
        high = pd.Series([100.0] * n)
        low = pd.Series([100.0] * n)
        volume = pd.Series([1_000_000.0] * n)
        result = compute_chaikin_money_flow(high, low, close, volume)
        # Should not raise; returns None or 0
        assert result is None or result == 0.0


# ---------------------------------------------------------------------------
# compute_vwap_deviation
# ---------------------------------------------------------------------------

class TestComputeVwapDeviation:
    def test_returns_float_for_sufficient_data(self):
        df = _make_ohlcv(25)
        result = compute_vwap_deviation(df["High"], df["Low"], df["Close"], df["Volume"])
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        df = _make_ohlcv(5)
        result = compute_vwap_deviation(df["High"], df["Low"], df["Close"], df["Volume"])
        assert result is None

    def test_zero_when_price_equals_vwap(self):
        # Constant price, constant volume → VWAP = price → deviation = 0
        n = 25
        close = pd.Series([100.0] * n)
        high = pd.Series([100.0] * n)
        low = pd.Series([100.0] * n)
        volume = pd.Series([1_000_000.0] * n)
        result = compute_vwap_deviation(high, low, close, volume)
        assert result is not None
        assert abs(result) < 0.01

    def test_positive_when_price_above_vwap(self):
        # Price rises at end above the historical VWAP average
        n = 25
        close = pd.Series([100.0] * (n - 1) + [110.0])
        high = close + 0.5
        low = close - 0.5
        volume = pd.Series([1_000_000.0] * n)
        result = compute_vwap_deviation(high, low, close, volume)
        assert result is not None
        assert result > 0


# ---------------------------------------------------------------------------
# compute_anchored_vwap_deviation
# ---------------------------------------------------------------------------

class TestComputeAnchoredVwapDeviation:
    def test_returns_none_when_no_earnings_date(self):
        df = _make_ohlcv(60)
        result = compute_anchored_vwap_deviation(
            df["High"], df["Low"], df["Close"], df["Volume"],
            earnings_date=None,
        )
        assert result is None

    def test_returns_float_when_earnings_date_in_window(self):
        df = _make_ohlcv(60)
        # Use a date 30 bars back
        earnings_date = df.index[-30]
        result = compute_anchored_vwap_deviation(
            df["High"], df["Low"], df["Close"], df["Volume"],
            earnings_date=earnings_date,
        )
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_when_earnings_date_after_data(self):
        df = _make_ohlcv(60)
        # A date after the last bar → no data after it
        future_date = df.index[-1] + pd.Timedelta(days=30)
        result = compute_anchored_vwap_deviation(
            df["High"], df["Low"], df["Close"], df["Volume"],
            earnings_date=future_date,
        )
        assert result is None

    def test_returns_none_when_less_than_2_bars_since_earnings(self):
        df = _make_ohlcv(60)
        # Earnings date = yesterday (1 bar of data since)
        earnings_date = df.index[-1]
        result = compute_anchored_vwap_deviation(
            df["High"], df["Low"], df["Close"], df["Volume"],
            earnings_date=earnings_date,
        )
        assert result is None


# ---------------------------------------------------------------------------
# compute_volume_dryup_ratio
# ---------------------------------------------------------------------------

class TestComputeVolumeDryupRatio:
    def test_returns_float_for_sufficient_data(self):
        df = _make_ohlcv(20)
        result = compute_volume_dryup_ratio(df["Volume"])
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        df = _make_ohlcv(5)
        result = compute_volume_dryup_ratio(df["Volume"])
        assert result is None

    def test_lt_1_when_volume_drying_up(self):
        # Last 3 bars have much lower volume than prior 10
        volume = pd.Series([5_000_000.0] * 13 + [100_000.0] * 3)
        result = compute_volume_dryup_ratio(volume)
        assert result is not None
        assert result < 1.0

    def test_gt_1_when_volume_surging(self):
        # Last 3 bars have much higher volume
        volume = pd.Series([100_000.0] * 13 + [5_000_000.0] * 3)
        result = compute_volume_dryup_ratio(volume)
        assert result is not None
        assert result > 1.0

    def test_approx_1_for_constant_volume(self):
        volume = pd.Series([1_000_000.0] * 20)
        result = compute_volume_dryup_ratio(volume)
        assert result is not None
        assert abs(result - 1.0) < 0.01


# ---------------------------------------------------------------------------
# compute_updown_volume_ratio
# ---------------------------------------------------------------------------

class TestComputeUpdownVolumeRatio:
    def test_returns_float_for_sufficient_data(self):
        df = _make_ohlcv(25)
        result = compute_updown_volume_ratio(df["Close"], df["Volume"])
        assert result is not None
        assert isinstance(result, float)

    def test_returns_none_for_insufficient_data(self):
        df = _make_ohlcv(3)
        result = compute_updown_volume_ratio(df["Close"], df["Volume"])
        assert result is None

    def test_high_ratio_for_all_up_days(self):
        n = 25
        close = pd.Series([100.0 + i for i in range(n)])  # all up
        volume = pd.Series([1_000_000.0] * n)
        result = compute_updown_volume_ratio(close, volume)
        # All volume on up days → ratio should be very large or undefined
        # Implementation should handle no down days gracefully
        assert result is None or result > 1.0

    def test_low_ratio_for_all_down_days(self):
        n = 25
        close = pd.Series([100.0 - i * 0.5 for i in range(n)])  # all down
        volume = pd.Series([1_000_000.0] * n)
        result = compute_updown_volume_ratio(close, volume)
        assert result is None or result < 1.0

    def test_equal_ratio_for_alternating_days(self):
        # Alternating up/down with equal volume → ratio ≈ 1.0
        n = 20
        prices = [100.0 + (1 if i % 2 == 0 else -1) for i in range(n)]
        close = pd.Series(prices)
        volume = pd.Series([1_000_000.0] * n)
        result = compute_updown_volume_ratio(close, volume)
        if result is not None:
            assert 0.5 <= result <= 2.0  # approximately balanced


# ---------------------------------------------------------------------------
# Integration: compute_technicals includes new volume fields
# ---------------------------------------------------------------------------

class TestComputeTechnicalsVolumeFields:
    def test_new_volume_fields_present(self):
        df = _make_ohlcv(60)
        result = compute_technicals(df)
        assert hasattr(result, "obv_trend")
        assert hasattr(result, "ad_trend")
        assert hasattr(result, "chaikin_money_flow")
        assert hasattr(result, "vwap_deviation")
        assert hasattr(result, "volume_dryup_ratio")
        assert hasattr(result, "breakout_volume_multiple")
        assert hasattr(result, "updown_volume_ratio")

    def test_breakout_volume_multiple_is_positive(self):
        df = _make_ohlcv(60)
        result = compute_technicals(df)
        if result.breakout_volume_multiple is not None:
            assert result.breakout_volume_multiple > 0

    def test_obv_trend_is_minus1_0_or_1(self):
        df = _make_ohlcv(60)
        result = compute_technicals(df)
        assert result.obv_trend in (-1, 0, 1)

    def test_cmf_in_range(self):
        df = _make_ohlcv(60)
        result = compute_technicals(df)
        if result.chaikin_money_flow is not None:
            assert -1.0 <= result.chaikin_money_flow <= 1.0

    def test_no_regression_existing_fields(self):
        df = _make_ohlcv(300)
        result = compute_technicals(df)
        assert result.rsi_14 is not None
        assert result.macd is not None
        assert result.technical_score > 0
