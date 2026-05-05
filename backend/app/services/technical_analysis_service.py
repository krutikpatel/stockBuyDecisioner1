from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta as ta

from app.models.market import (
    SupportResistanceLevels,
    TechnicalIndicators,
    TrendClassification,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Indicator helpers
# ---------------------------------------------------------------------------

def _sma(series: pd.Series, window: int) -> Optional[float]:
    if len(series) < window:
        return None
    val = series.rolling(window).mean().iloc[-1]
    return round(float(val), 4) if not np.isnan(val) else None


def compute_rsi(series: pd.Series, period: int = 14) -> Optional[float]:
    if len(series) < period + 1:
        return None
    rsi_series = ta.rsi(series, length=period)
    if rsi_series is None or rsi_series.empty:
        return None
    val = rsi_series.iloc[-1]
    return round(float(val), 2) if not np.isnan(val) else None


def compute_macd(series: pd.Series) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if len(series) < 35:
        return None, None, None
    result = ta.macd(series, fast=12, slow=26, signal=9)
    if result is None or result.empty:
        return None, None, None
    macd_val = result.iloc[-1, 0]
    signal_val = result.iloc[-1, 1]
    hist_val = result.iloc[-1, 2]
    to_f = lambda v: round(float(v), 4) if not np.isnan(v) else None
    return to_f(macd_val), to_f(signal_val), to_f(hist_val)


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Optional[float]:
    if len(close) < period + 1:
        return None
    result = ta.atr(high, low, close, length=period)
    if result is None or result.empty:
        return None
    val = result.iloc[-1]
    return round(float(val), 4) if not np.isnan(val) else None


# ---------------------------------------------------------------------------
# Trend classification
# ---------------------------------------------------------------------------

def classify_trend(close: pd.Series, ma_50: Optional[float], ma_200: Optional[float]) -> TrendClassification:
    price = float(close.iloc[-1])

    if ma_50 is None or ma_200 is None:
        return TrendClassification(label="unknown", description="Insufficient data for trend classification.")

    # Detect higher highs / higher lows over last 20 bars
    window = close.tail(20)
    highs = window[window == window.cummax()]
    lows = window[window == window.cummin()]
    higher_highs = len(highs) >= 2 and float(highs.iloc[-1]) > float(highs.iloc[0])
    lower_lows = len(lows) >= 2 and float(lows.iloc[-1]) < float(lows.iloc[0])

    above_50 = price > ma_50
    above_200 = price > ma_200
    golden_cross = ma_50 > ma_200

    if above_50 and above_200 and golden_cross and higher_highs:
        return TrendClassification(
            label="strong_uptrend",
            description="Price above 50MA and 200MA, golden cross in place, higher highs confirmed.",
        )
    if above_200 and (not above_50 or not golden_cross):
        return TrendClassification(
            label="weak_uptrend",
            description="Price above 200MA but below or near 50MA — momentum weakening.",
        )
    if not above_50 and not above_200 and lower_lows:
        return TrendClassification(
            label="downtrend",
            description="Price below 50MA and 200MA with lower lows — bearish trend.",
        )
    return TrendClassification(
        label="sideways",
        description="Price consolidating without clear directional bias.",
    )


# ---------------------------------------------------------------------------
# Extension detection
# ---------------------------------------------------------------------------

def detect_extension(
    price: float,
    ma_20: Optional[float],
    ma_50: Optional[float],
    rsi: Optional[float],
) -> tuple[bool, Optional[float], Optional[float]]:
    ext_20 = None
    ext_50 = None
    extended = False

    if ma_20 and ma_20 > 0:
        ext_20 = round((price - ma_20) / ma_20 * 100, 2)
        if ext_20 > 8:
            extended = True

    if ma_50 and ma_50 > 0:
        ext_50 = round((price - ma_50) / ma_50 * 100, 2)
        if ext_50 > 15:
            extended = True

    if rsi and rsi > 75:
        extended = True

    return extended, ext_20, ext_50


# ---------------------------------------------------------------------------
# Support / resistance via swing high/low
# ---------------------------------------------------------------------------

def find_support_resistance(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 10,
    n_levels: int = 3,
) -> SupportResistanceLevels:
    price = float(close.iloc[-1])

    # Rolling local maxima and minima
    local_highs = high[(high.shift(1) < high) & (high.shift(-1) < high)]
    local_lows = low[(low.shift(1) > low) & (low.shift(-1) > low)]

    # Keep last 60 bars worth of levels
    recent_highs = local_highs.tail(60).tolist()
    recent_lows = local_lows.tail(60).tolist()

    # Cluster close levels (within 1% of each other)
    def cluster(levels: list[float], tol: float = 0.01) -> list[float]:
        if not levels:
            return []
        levels = sorted(set(round(l, 2) for l in levels))
        clusters: list[float] = [levels[0]]
        for lv in levels[1:]:
            if abs(lv - clusters[-1]) / clusters[-1] < tol:
                clusters[-1] = (clusters[-1] + lv) / 2
            else:
                clusters.append(lv)
        return clusters

    supports_raw = [l for l in cluster(recent_lows) if l < price]
    resistances_raw = [l for l in cluster(recent_highs) if l > price]

    supports = sorted(supports_raw, reverse=True)[:n_levels]
    resistances = sorted(resistances_raw)[:n_levels]

    return SupportResistanceLevels(
        supports=[round(s, 4) for s in supports],
        resistances=[round(r, 4) for r in resistances],
        nearest_support=round(supports[0], 4) if supports else None,
        nearest_resistance=round(resistances[0], 4) if resistances else None,
    )


# ---------------------------------------------------------------------------
# Volume trend
# ---------------------------------------------------------------------------

def compute_volume_trend(volume: pd.Series) -> str:
    if len(volume) < 31:
        return "unknown"
    avg_30 = float(volume.iloc[-31:-1].mean())
    current = float(volume.iloc[-1])
    if avg_30 == 0:
        return "unknown"
    ratio = current / avg_30
    if ratio >= 1.3:
        return "above_average"
    if ratio <= 0.7:
        return "below_average"
    return "average"


# ---------------------------------------------------------------------------
# Relative strength
# ---------------------------------------------------------------------------

def compute_relative_strength(
    stock_close: pd.Series,
    benchmark_close: pd.Series,
    period: int = 63,
) -> Optional[float]:
    if len(stock_close) < period or len(benchmark_close) < period:
        return None
    stock_ret = float(stock_close.iloc[-1]) / float(stock_close.iloc[-period]) - 1
    bench_ret = float(benchmark_close.iloc[-1]) / float(benchmark_close.iloc[-period]) - 1
    if bench_ret == 0:
        return None
    return round(stock_ret / abs(bench_ret), 4)


# ---------------------------------------------------------------------------
# Technical score (0–100)
# ---------------------------------------------------------------------------

def score_technicals(
    trend: TrendClassification,
    rsi: Optional[float],
    macd_hist: Optional[float],
    is_extended: bool,
    volume_trend: str,
    rs_spy: Optional[float],
    sr: SupportResistanceLevels,
    price: float,
) -> float:
    score = 50.0

    # Trend contribution (±20)
    trend_scores = {
        "strong_uptrend": 20,
        "weak_uptrend": 5,
        "sideways": -5,
        "downtrend": -20,
        "unknown": 0,
    }
    score += trend_scores.get(trend.label, 0)

    # RSI contribution (±15)
    if rsi is not None:
        if 50 <= rsi <= 70:
            score += 15
        elif 40 <= rsi < 50:
            score += 5
        elif rsi > 75:
            score -= 5  # overbought
        elif rsi < 30:
            score -= 15  # oversold

    # MACD contribution (±10)
    if macd_hist is not None:
        if macd_hist > 0:
            score += 10
        else:
            score -= 10

    # Extension penalty (−10)
    if is_extended:
        score -= 10

    # Volume trend (±5)
    if volume_trend == "above_average":
        score += 5
    elif volume_trend == "below_average":
        score -= 5

    # Relative strength vs SPY (±10)
    if rs_spy is not None:
        if rs_spy > 1.2:
            score += 10
        elif rs_spy > 1.0:
            score += 5
        elif rs_spy < 0.8:
            score -= 10
        elif rs_spy < 1.0:
            score -= 5

    # Support cushion (±5): good if nearest support is within 5%
    if sr.nearest_support and price > 0:
        cushion = (price - sr.nearest_support) / price * 100
        if cushion <= 5:
            score += 5
        elif cushion > 15:
            score -= 5

    return round(max(0.0, min(100.0, score)), 2)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_technicals(
    df: pd.DataFrame,
    spy_df: Optional[pd.DataFrame] = None,
    sector_df: Optional[pd.DataFrame] = None,
) -> TechnicalIndicators:
    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    price = float(close.iloc[-1])

    ma_10 = _sma(close, 10)
    ma_20 = _sma(close, 20)
    ma_50 = _sma(close, 50)
    ma_100 = _sma(close, 100)
    ma_200 = _sma(close, 200)

    rsi = compute_rsi(close)
    macd_val, macd_sig, macd_hist = compute_macd(close)
    atr = compute_atr(high, low, close)

    trend = classify_trend(close, ma_50, ma_200)
    is_extended, ext_20, ext_50 = detect_extension(price, ma_20, ma_50, rsi)
    vol_trend = compute_volume_trend(volume)
    sr = find_support_resistance(high, low, close)

    rs_spy = None
    if spy_df is not None and not spy_df.empty:
        spy_close = spy_df["Close"].squeeze()
        rs_spy = compute_relative_strength(close, spy_close)

    rs_sector = None
    if sector_df is not None and not sector_df.empty:
        sector_close = sector_df["Close"].squeeze()
        rs_sector = compute_relative_strength(close, sector_close)

    tech_score = score_technicals(trend, rsi, macd_hist, is_extended, vol_trend, rs_spy, sr, price)

    return TechnicalIndicators(
        ma_10=ma_10,
        ma_20=ma_20,
        ma_50=ma_50,
        ma_100=ma_100,
        ma_200=ma_200,
        rsi_14=rsi,
        macd=macd_val,
        macd_signal=macd_sig,
        macd_histogram=macd_hist,
        atr=atr,
        volume_trend=vol_trend,
        trend=trend,
        is_extended=is_extended,
        extension_pct_above_20ma=ext_20,
        extension_pct_above_50ma=ext_50,
        support_resistance=sr,
        rs_vs_spy=rs_spy,
        rs_vs_sector=rs_sector,
        technical_score=tech_score,
    )
