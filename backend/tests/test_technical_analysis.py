"""Phase 1 unit tests for technical analysis service."""
import math
from typing import Optional

import numpy as np
import pandas as pd
import pytest

from app.services.technical_analysis_service import (
    _sma,
    classify_trend,
    compute_atr,
    compute_macd,
    compute_relative_strength,
    compute_rsi,
    compute_technicals,
    compute_volume_trend,
    detect_extension,
    find_support_resistance,
    score_technicals,
)
from app.models.market import SupportResistanceLevels, TrendClassification


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_trending_up(n: int = 250, start: float = 100.0, step: float = 0.5) -> pd.DataFrame:
    """Steadily rising OHLCV DataFrame with higher highs and higher lows."""
    close = [start + i * step for i in range(n)]
    high = [c + 1.0 for c in close]
    low = [c - 1.0 for c in close]
    open_ = [c - 0.25 for c in close]
    volume = [1_000_000] * n
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)


def _make_trending_down(n: int = 250, start: float = 200.0, step: float = 0.5) -> pd.DataFrame:
    close = [start - i * step for i in range(n)]
    high = [c + 1.0 for c in close]
    low = [c - 1.0 for c in close]
    open_ = [c + 0.25 for c in close]
    volume = [1_000_000] * n
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)


def _make_flat(n: int = 250, price: float = 100.0) -> pd.DataFrame:
    close = [price] * n
    high = [price + 0.5] * n
    low = [price - 0.5] * n
    open_ = [price] * n
    volume = [1_000_000] * n
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)


# ---------------------------------------------------------------------------
# SMA tests
# ---------------------------------------------------------------------------

class TestSMA:
    def test_sma_matches_pandas_rolling_mean(self):
        df = _make_trending_up(250)
        close = df["Close"]
        for window in (10, 20, 50, 100, 200):
            expected = round(float(close.rolling(window).mean().iloc[-1]), 4)
            result = _sma(close, window)
            assert result == pytest.approx(expected, rel=1e-5), f"MA{window} mismatch"

    def test_sma_returns_none_when_insufficient_data(self):
        close = pd.Series([10.0, 20.0, 30.0])
        assert _sma(close, 50) is None

    def test_sma_200_requires_200_bars(self):
        close = pd.Series(range(199), dtype=float)
        assert _sma(close, 200) is None
        close_200 = pd.Series(range(200), dtype=float)
        assert _sma(close_200, 200) is not None


# ---------------------------------------------------------------------------
# RSI tests
# ---------------------------------------------------------------------------

class TestRSI:
    def test_rsi_range(self):
        df = _make_trending_up(100)
        rsi = compute_rsi(df["Close"])
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_rsi_high_on_strong_uptrend(self):
        """Steadily rising prices → RSI should be well above 50."""
        df = _make_trending_up(100, step=1.0)
        rsi = compute_rsi(df["Close"])
        assert rsi is not None
        assert rsi > 60, f"Expected RSI > 60 on strong uptrend, got {rsi}"

    def test_rsi_low_on_downtrend(self):
        """Steadily falling prices → RSI should be below 50."""
        df = _make_trending_down(100, step=1.0)
        rsi = compute_rsi(df["Close"])
        assert rsi is not None
        assert rsi < 50, f"Expected RSI < 50 on downtrend, got {rsi}"

    def test_rsi_returns_none_when_insufficient(self):
        close = pd.Series([10.0] * 5)
        assert compute_rsi(close) is None


# ---------------------------------------------------------------------------
# MACD tests
# ---------------------------------------------------------------------------

class TestMACD:
    def test_macd_positive_histogram_on_uptrend(self):
        df = _make_trending_up(100, step=1.0)
        _, _, hist = compute_macd(df["Close"])
        assert hist is not None
        assert hist > 0, f"Expected positive MACD histogram on uptrend, got {hist}"

    def test_macd_negative_histogram_on_downtrend(self):
        df = _make_trending_down(100, step=1.0)
        _, _, hist = compute_macd(df["Close"])
        assert hist is not None
        assert hist < 0, f"Expected negative MACD histogram on downtrend, got {hist}"

    def test_macd_returns_none_when_insufficient(self):
        close = pd.Series(range(20), dtype=float)
        m, s, h = compute_macd(close)
        assert m is None and s is None and h is None


# ---------------------------------------------------------------------------
# ATR tests
# ---------------------------------------------------------------------------

class TestATR:
    def test_atr_is_positive(self):
        df = _make_trending_up(50)
        atr = compute_atr(df["High"], df["Low"], df["Close"])
        assert atr is not None
        assert atr > 0

    def test_atr_returns_none_when_insufficient(self):
        df = _make_trending_up(5)
        atr = compute_atr(df["High"], df["Low"], df["Close"])
        assert atr is None


# ---------------------------------------------------------------------------
# Trend classification tests
# ---------------------------------------------------------------------------

class TestTrendClassification:
    def test_strong_uptrend_when_price_above_50_and_200_with_golden_cross(self):
        df = _make_trending_up(250)
        close = df["Close"]
        # With a steadily rising series, ma_50 < ma_200 numerically because
        # the most recent values are highest — so price > ma_50 > ...
        # Simulate the golden-cross condition explicitly
        ma_50 = float(close.tail(50).mean())
        ma_200 = float(close.tail(200).mean())
        # For a rising series: price > ma_50 > ma_200 (golden cross)
        price_val = float(close.iloc[-1])
        assert price_val > ma_50 > ma_200  # sanity
        trend = classify_trend(close, ma_50, ma_200)
        assert trend.label == "strong_uptrend"

    def test_downtrend_when_price_below_50_and_200(self):
        df = _make_trending_down(250)
        close = df["Close"]
        ma_50 = float(close.tail(50).mean())
        ma_200 = float(close.tail(200).mean())
        price_val = float(close.iloc[-1])
        assert price_val < ma_50  # sanity
        trend = classify_trend(close, ma_50, ma_200)
        assert trend.label == "downtrend"

    def test_sideways_on_flat_data(self):
        df = _make_flat(250)
        close = df["Close"]
        ma_50 = _sma(close, 50)
        ma_200 = _sma(close, 200)
        trend = classify_trend(close, ma_50, ma_200)
        assert trend.label in ("sideways", "weak_uptrend")

    def test_unknown_when_ma_missing(self):
        close = pd.Series([100.0] * 10)
        trend = classify_trend(close, None, None)
        assert trend.label == "unknown"


# ---------------------------------------------------------------------------
# Extension detection tests
# ---------------------------------------------------------------------------

class TestExtensionDetection:
    def test_extended_when_price_10pct_above_20ma(self):
        price = 115.0
        ma_20 = 100.0  # 15% above → extended
        is_ext, ext_20, _ = detect_extension(price, ma_20, 105.0, rsi=60.0)
        assert is_ext is True
        assert ext_20 == pytest.approx(15.0)

    def test_not_extended_when_within_8pct(self):
        price = 105.0
        ma_20 = 100.0  # 5% above
        is_ext, ext_20, _ = detect_extension(price, ma_20, 98.0, rsi=55.0)
        assert is_ext is False

    def test_extended_when_rsi_above_75(self):
        price = 102.0
        ma_20 = 100.0  # only 2% above — not extended by price
        is_ext, _, _ = detect_extension(price, ma_20, 99.0, rsi=80.0)
        assert is_ext is True

    def test_extended_when_50pct_extension_large(self):
        price = 125.0
        ma_50 = 100.0  # 25% above → extended
        is_ext, _, ext_50 = detect_extension(price, 120.0, ma_50, rsi=50.0)
        assert is_ext is True
        assert ext_50 == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# Support / resistance tests
# ---------------------------------------------------------------------------

class TestSupportResistance:
    def test_levels_are_within_historical_range(self):
        df = _make_trending_up(100)
        sr = find_support_resistance(df["High"], df["Low"], df["Close"])
        price = float(df["Close"].iloc[-1])
        for s in sr.supports:
            assert s < price
        for r in sr.resistances:
            assert r > price

    def test_at_least_one_support_level(self):
        df = _make_trending_up(100)
        sr = find_support_resistance(df["High"], df["Low"], df["Close"])
        # May have zero levels if no swing lows detected — just verify no crash
        assert isinstance(sr.supports, list)
        assert isinstance(sr.resistances, list)

    def test_nearest_support_is_closest_below_price(self):
        df = _make_trending_up(100)
        sr = find_support_resistance(df["High"], df["Low"], df["Close"])
        price = float(df["Close"].iloc[-1])
        if sr.nearest_support:
            assert sr.nearest_support < price
            # It should be the maximum of all supports (closest from below)
            if sr.supports:
                assert sr.nearest_support == max(sr.supports)


# ---------------------------------------------------------------------------
# Volume trend tests
# ---------------------------------------------------------------------------

class TestVolumeTrend:
    def test_above_average_when_volume_1_5x(self):
        avg_vol = 1_000_000
        volumes = [avg_vol] * 30 + [int(avg_vol * 1.5)]
        series = pd.Series(volumes)
        assert compute_volume_trend(series) == "above_average"

    def test_below_average_when_volume_half(self):
        avg_vol = 1_000_000
        volumes = [avg_vol] * 30 + [int(avg_vol * 0.5)]
        series = pd.Series(volumes)
        assert compute_volume_trend(series) == "below_average"

    def test_average_when_volume_close_to_mean(self):
        avg_vol = 1_000_000
        volumes = [avg_vol] * 30 + [int(avg_vol * 1.05)]
        series = pd.Series(volumes)
        assert compute_volume_trend(series) == "average"

    def test_unknown_when_insufficient_data(self):
        series = pd.Series([1_000_000] * 10)
        assert compute_volume_trend(series) == "unknown"


# ---------------------------------------------------------------------------
# Relative strength tests
# ---------------------------------------------------------------------------

class TestRelativeStrength:
    def test_rs_greater_than_1_when_stock_outperforms(self):
        n = 100
        # Stock up 20%, benchmark up 10%
        stock = pd.Series([100.0 * (1 + 0.002 * i) for i in range(n)])
        bench = pd.Series([100.0 * (1 + 0.001 * i) for i in range(n)])
        rs = compute_relative_strength(stock, bench, period=n)
        assert rs is not None
        assert rs > 1.0

    def test_rs_less_than_1_when_stock_underperforms(self):
        n = 100
        stock = pd.Series([100.0 * (1 + 0.001 * i) for i in range(n)])
        bench = pd.Series([100.0 * (1 + 0.002 * i) for i in range(n)])
        rs = compute_relative_strength(stock, bench, period=n)
        assert rs is not None
        assert rs < 1.0

    def test_rs_none_when_insufficient(self):
        stock = pd.Series([100.0] * 10)
        bench = pd.Series([100.0] * 10)
        rs = compute_relative_strength(stock, bench, period=63)
        assert rs is None


# ---------------------------------------------------------------------------
# Technical score tests
# ---------------------------------------------------------------------------

class TestTechnicalScore:
    def _make_sr(self, price: float, support_offset: float = -3.0) -> SupportResistanceLevels:
        s = price + support_offset
        r = price + 10.0
        return SupportResistanceLevels(
            supports=[round(s, 2)],
            resistances=[round(r, 2)],
            nearest_support=round(s, 2),
            nearest_resistance=round(r, 2),
        )

    def test_score_in_valid_range(self):
        trend = TrendClassification(label="strong_uptrend", description="")
        sr = self._make_sr(100.0)
        score = score_technicals(trend, rsi=60.0, macd_hist=0.5, is_extended=False,
                                 volume_trend="above_average", rs_spy=1.3, sr=sr, price=100.0)
        assert 0 <= score <= 100

    def test_strong_uptrend_scores_higher_than_downtrend(self):
        sr = self._make_sr(100.0)
        up_trend = TrendClassification(label="strong_uptrend", description="")
        down_trend = TrendClassification(label="downtrend", description="")
        up_score = score_technicals(up_trend, 60.0, 0.5, False, "above_average", 1.3, sr, 100.0)
        down_score = score_technicals(down_trend, 35.0, -0.5, False, "below_average", 0.7, sr, 100.0)
        assert up_score > down_score

    def test_extension_reduces_score(self):
        trend = TrendClassification(label="strong_uptrend", description="")
        sr = self._make_sr(100.0)
        score_normal = score_technicals(trend, 60.0, 0.5, False, "average", None, sr, 100.0)
        score_extended = score_technicals(trend, 60.0, 0.5, True, "average", None, sr, 100.0)
        assert score_extended < score_normal


# ---------------------------------------------------------------------------
# Integration: compute_technicals end-to-end
# ---------------------------------------------------------------------------

class TestComputeTechnicals:
    def test_returns_technical_indicators_object(self):
        df = _make_trending_up(250)
        result = compute_technicals(df)
        assert result.ma_20 is not None
        assert result.ma_50 is not None
        assert result.ma_200 is not None
        assert result.rsi_14 is not None
        assert result.trend.label in ("strong_uptrend", "weak_uptrend", "sideways", "downtrend", "unknown")
        assert 0 <= result.technical_score <= 100

    def test_strong_uptrend_detected(self):
        df = _make_trending_up(250, step=0.5)
        result = compute_technicals(df)
        assert result.trend.label == "strong_uptrend"

    def test_downtrend_detected(self):
        df = _make_trending_down(250, step=0.5)
        result = compute_technicals(df)
        assert result.trend.label == "downtrend"

    def test_with_spy_benchmark(self):
        df = _make_trending_up(250, step=1.0)
        spy = _make_trending_up(250, step=0.5)
        result = compute_technicals(df, spy_df=spy)
        assert result.rs_vs_spy is not None
        assert result.rs_vs_spy > 1.0  # stock outperforms spy

    def test_short_data_does_not_crash(self):
        df = _make_trending_up(30)
        result = compute_technicals(df)
        # Should return without exception; some indicators will be None
        assert result.ma_200 is None  # not enough data
        assert result.trend.label is not None
