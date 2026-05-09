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
# Story 1: New indicator helpers
# ---------------------------------------------------------------------------

def compute_ema_relative(series: pd.Series, period: int) -> Optional[float]:
    """Return (price - EMA) / EMA * 100 (% deviation of price from EMA).

    Returns None when EMA would be zero or there is insufficient data.
    """
    if len(series) < period:
        return None
    ema_series = series.ewm(span=period, adjust=False).mean()
    ema_val = float(ema_series.iloc[-1])
    price = float(series.iloc[-1])
    if ema_val == 0 or np.isnan(ema_val):
        return None
    return round((price - ema_val) / ema_val * 100, 4)


def compute_sma_slope(series: pd.Series, window: int, slope_bars: int = 5) -> Optional[float]:
    """Return the 5-bar slope of an SMA as a percentage.

    slope = (sma[-1] - sma[-(slope_bars+1)]) / sma[-(slope_bars+1)] * 100
    Returns None when there is insufficient data.
    """
    needed = window + slope_bars
    if len(series) < needed:
        return None
    sma_series = series.rolling(window).mean().dropna()
    if len(sma_series) < slope_bars + 1:
        return None
    prev = float(sma_series.iloc[-(slope_bars + 1)])
    current = float(sma_series.iloc[-1])
    if prev == 0 or np.isnan(prev) or np.isnan(current):
        return None
    return round((current - prev) / prev * 100, 4)


def compute_sma_relative(series: pd.Series, window: int) -> Optional[float]:
    """Return (price - SMA) / SMA * 100.

    Returns None when there is insufficient data or SMA is zero.
    """
    if len(series) < window:
        return None
    sma_val = series.rolling(window).mean().iloc[-1]
    if np.isnan(sma_val) or sma_val == 0:
        return None
    price = float(series.iloc[-1])
    return round((price - float(sma_val)) / float(sma_val) * 100, 4)


def compute_performance_periods(series: pd.Series) -> dict[str, Optional[float]]:
    """Compute % returns over multiple look-back periods.

    Uses positional indexing: 1W=5 bars, 1M=21, 3M=63, 6M=126, 1Y=252,
    3Y=756, 5Y=1260. YTD uses the DatetimeIndex year boundary if available.
    """
    n = len(series)
    price = float(series.iloc[-1])

    def perf(bars: int) -> Optional[float]:
        if n <= bars:
            return None
        prev = float(series.iloc[-(bars + 1)])
        if prev == 0:
            return None
        return round((price / prev - 1) * 100, 4)

    # YTD: look for first bar in current calendar year
    perf_ytd: Optional[float] = None
    if isinstance(series.index, pd.DatetimeIndex):
        current_year = series.index[-1].year
        ytd_mask = series.index.year == current_year
        ytd_bars = series[ytd_mask]
        if len(ytd_bars) > 1:
            ytd_prev = float(ytd_bars.iloc[0])
            if ytd_prev != 0:
                perf_ytd = round((price / ytd_prev - 1) * 100, 4)

    return {
        "perf_1w": perf(5),
        "perf_1m": perf(21),
        "perf_3m": perf(63),
        "perf_6m": perf(126),
        "perf_ytd": perf_ytd,
        "perf_1y": perf(252),
        "perf_3y": perf(756),
        "perf_5y": perf(1260),
    }


def compute_gap_metrics(
    open_price: float, prev_close: float, current_price: float
) -> tuple[Optional[float], Optional[float]]:
    """Return (gap_percent, change_from_open_percent).

    gap_percent = (open - prev_close) / prev_close * 100
    change_from_open_percent = (price - open) / open * 100
    """
    gap: Optional[float] = None
    cfo: Optional[float] = None

    if prev_close and prev_close != 0:
        gap = round((open_price - prev_close) / prev_close * 100, 4)

    if open_price and open_price != 0:
        cfo = round((current_price - open_price) / open_price * 100, 4)

    return gap, cfo


def compute_range_distances(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
) -> dict[str, Optional[float]]:
    """Compute % distances from price to rolling high/low boundaries.

    All distances relative to current price:
    - dist_from_Xd_high: negative (price below the high)
    - dist_from_Xd_low:  positive (price above the low)
    - dist_from_ath: negative or zero
    - dist_from_atl: positive or zero
    """
    price = float(close.iloc[-1])
    n = len(close)

    def pct_dist(ref: float) -> Optional[float]:
        if ref == 0:
            return None
        return round((price / ref - 1) * 100, 4)

    def rolling_high(bars: int) -> Optional[float]:
        if n < bars:
            return None
        return float(high.rolling(bars).max().iloc[-1])

    def rolling_low(bars: int) -> Optional[float]:
        if n < bars:
            return None
        return float(low.rolling(bars).min().iloc[-1])

    rh20 = rolling_high(20)
    rl20 = rolling_low(20)
    rh50 = rolling_high(50)
    rl50 = rolling_low(50)
    rh252 = rolling_high(252)
    rl252 = rolling_low(252)
    ath = float(high.max()) if n > 0 else None
    atl = float(low.min()) if n > 0 else None

    return {
        "dist_from_20d_high": pct_dist(rh20) if rh20 is not None else None,
        "dist_from_20d_low": pct_dist(rl20) if rl20 is not None else None,
        "dist_from_50d_high": pct_dist(rh50) if rh50 is not None else None,
        "dist_from_50d_low": pct_dist(rl50) if rl50 is not None else None,
        "dist_from_52w_high": pct_dist(rh252) if rh252 is not None else None,
        "dist_from_52w_low": pct_dist(rl252) if rl252 is not None else None,
        "dist_from_ath": pct_dist(ath) if ath is not None else None,
        "dist_from_atl": pct_dist(atl) if atl is not None else None,
    }


def compute_volatility_metrics(
    series: pd.Series,
) -> tuple[Optional[float], Optional[float]]:
    """Return (weekly_volatility, monthly_volatility) as annualized percentages.

    Weekly: std of 5-bar (weekly) returns × sqrt(52) × 100
    Monthly: std of 21-bar (monthly) returns × sqrt(12) × 100
    Requires at least 10 bars for weekly, 24 bars for monthly.
    """
    n = len(series)

    weekly_vol: Optional[float] = None
    monthly_vol: Optional[float] = None

    # Weekly returns: sample every 5 bars
    if n >= 10:
        weekly_prices = series.iloc[::5]
        weekly_returns = weekly_prices.pct_change().dropna()
        if len(weekly_returns) >= 2:
            weekly_vol = round(float(weekly_returns.std() * np.sqrt(52)) * 100, 4)

    # Monthly returns: sample every 21 bars
    if n >= 24:
        monthly_prices = series.iloc[::21]
        monthly_returns = monthly_prices.pct_change().dropna()
        if len(monthly_returns) >= 2:
            monthly_vol = round(float(monthly_returns.std() * np.sqrt(12)) * 100, 4)

    return weekly_vol, monthly_vol


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> Optional[float]:
    """Return the Average Directional Index (ADX) using Wilder's smoothing.

    Implemented manually to avoid pandas_ta incompatibility with pandas >= 3.0.
    Returns None when there is insufficient data.
    """
    if len(close) < period * 2 + 1:
        return None

    prev_close = close.shift(1)

    # True Range
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    # Directional movement
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=close.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=close.index,
    )

    alpha = 1.0 / period
    atr_w = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_w
    minus_di = 100.0 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_w

    di_sum = plus_di + minus_di
    dx = pd.Series(
        np.where(di_sum == 0, 0.0, 100.0 * (plus_di - minus_di).abs() / di_sum),
        index=close.index,
    )
    adx = dx.ewm(alpha=alpha, adjust=False).mean()

    val = adx.iloc[-1]
    if np.isnan(val):
        return None
    return round(float(val), 2)


def compute_stochastic_rsi(
    series: pd.Series,
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> Optional[float]:
    """Return the Stochastic RSI %K value (0–100).

    Returns None when there is insufficient data.
    """
    min_len = period * 2 + smooth_k + smooth_d
    if len(series) < min_len:
        return None
    result = ta.stochrsi(series, length=period, rsi_length=period, k=smooth_k, d=smooth_d)
    if result is None or result.empty:
        return None
    k_col = [c for c in result.columns if "STOCHRSIk" in c]
    if not k_col:
        return None
    val = result[k_col[0]].iloc[-1]
    if np.isnan(val):
        return None
    return round(float(val), 2)


def compute_bollinger_bands(
    series: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[Optional[float], Optional[float]]:
    """Return (bollinger_band_position, bollinger_band_width).

    position = (price - lower) / (upper - lower)   [can exceed [0,1]]
    width    = (upper - lower) / middle * 100        [%]
    """
    if len(series) < period:
        return None, None
    result = ta.bbands(series, length=period, std=std_dev)
    if result is None or result.empty:
        return None, None

    upper_col = [c for c in result.columns if "BBU" in c]
    lower_col = [c for c in result.columns if "BBL" in c]
    mid_col = [c for c in result.columns if "BBM" in c]
    if not upper_col or not lower_col or not mid_col:
        return None, None

    upper = float(result[upper_col[0]].iloc[-1])
    lower = float(result[lower_col[0]].iloc[-1])
    middle = float(result[mid_col[0]].iloc[-1])
    price = float(series.iloc[-1])

    if np.isnan(upper) or np.isnan(lower) or np.isnan(middle):
        return None, None

    band_range = upper - lower
    position: Optional[float] = None
    width: Optional[float] = None

    if band_range != 0:
        position = round((price - lower) / band_range, 4)
    if middle != 0:
        width = round(band_range / middle * 100, 4)

    return position, width


def compute_atr_percent(atr: Optional[float], price: float) -> Optional[float]:
    """Return ATR as a percentage of current price.

    Returns None when ATR is None or price is zero.
    """
    if atr is None or price == 0:
        return None
    return round(atr / price * 100, 4)


# ---------------------------------------------------------------------------
# Story 2: Volume & Accumulation indicators
# ---------------------------------------------------------------------------

def compute_obv_trend(close: pd.Series, volume: pd.Series, slope_bars: int = 10) -> int:
    """Return OBV trend as +1 (rising), -1 (falling), or 0 (flat/insufficient data).

    OBV is cumulated: add volume on up days, subtract on down days.
    Trend is determined by the sign of the OBV slope over `slope_bars`.
    """
    if len(close) < slope_bars + 2:
        return 0

    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (direction * volume).cumsum()

    prev = float(obv.iloc[-(slope_bars + 1)])
    current = float(obv.iloc[-1])
    if prev == 0:
        return 0
    slope = (current - prev) / abs(prev)
    if slope > 0.01:
        return 1
    if slope < -0.01:
        return -1
    return 0


def compute_ad_trend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    slope_bars: int = 10,
) -> int:
    """Return Accumulation/Distribution Line trend: +1, -1, or 0.

    MFM = ((close - low) - (high - close)) / (high - low)
    MFV = MFM * volume
    A/D = cumulative sum of MFV
    """
    if len(close) < slope_bars + 2:
        return 0

    hl_range = high - low
    # Avoid division by zero when high == low
    mfm = pd.Series(
        np.where(
            hl_range == 0,
            0.0,
            ((close - low) - (high - close)) / hl_range,
        ),
        index=close.index,
    )
    ad = (mfm * volume).cumsum()

    prev = float(ad.iloc[-(slope_bars + 1)])
    current = float(ad.iloc[-1])
    slope = current - prev
    if abs(slope) == 0:
        return 0
    # Normalise by abs(prev) if non-zero, otherwise by magnitude
    norm = abs(prev) if abs(prev) > 0 else abs(slope)
    normalised = slope / norm
    if normalised > 0.01:
        return 1
    if normalised < -0.01:
        return -1
    return 0


def compute_chaikin_money_flow(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> Optional[float]:
    """Return Chaikin Money Flow over `period` bars.

    CMF = sum(MFV, period) / sum(volume, period)
    MFV = ((close - low) - (high - close)) / (high - low) * volume
    Returns None when insufficient data or total volume is zero.
    """
    if len(close) < period:
        return None

    hl_range = high - low
    mfm = pd.Series(
        np.where(
            hl_range == 0,
            0.0,
            ((close - low) - (high - close)) / hl_range,
        ),
        index=close.index,
    )
    mfv = mfm * volume

    total_vol = float(volume.iloc[-period:].sum())
    if total_vol == 0:
        return None

    cmf = float(mfv.iloc[-period:].sum()) / total_vol
    if np.isnan(cmf):
        return None
    return round(cmf, 4)


def compute_vwap_deviation(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> Optional[float]:
    """Return % deviation of current price from the 20-day VWAP.

    VWAP = sum(typical_price * volume, period) / sum(volume, period)
    deviation = (price - VWAP) / VWAP * 100
    Returns None when insufficient data or VWAP is zero.
    """
    if len(close) < period:
        return None

    typical = (high + low + close) / 3
    total_vol = float(volume.iloc[-period:].sum())
    if total_vol == 0:
        return None

    vwap = float((typical * volume).iloc[-period:].sum()) / total_vol
    if vwap == 0 or np.isnan(vwap):
        return None

    price = float(close.iloc[-1])
    return round((price - vwap) / vwap * 100, 4)


def compute_anchored_vwap_deviation(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    earnings_date: Optional[pd.Timestamp],
) -> Optional[float]:
    """Return % deviation from VWAP anchored to the last earnings date.

    Requires a DatetimeIndex. Returns None when:
    - earnings_date is None
    - earnings_date is not in the index
    - fewer than 2 bars exist since the earnings date
    """
    if earnings_date is None:
        return None

    if not isinstance(close.index, pd.DatetimeIndex):
        return None

    # Find the first bar on or after the earnings date
    mask = close.index >= earnings_date
    if not mask.any():
        return None

    c_slice = close[mask]
    h_slice = high[mask]
    l_slice = low[mask]
    v_slice = volume[mask]

    if len(c_slice) < 2:
        return None

    typical = (h_slice + l_slice + c_slice) / 3
    total_vol = float(v_slice.sum())
    if total_vol == 0:
        return None

    vwap = float((typical * v_slice).sum()) / total_vol
    if vwap == 0 or np.isnan(vwap):
        return None

    price = float(c_slice.iloc[-1])
    return round((price - vwap) / vwap * 100, 4)


def compute_volume_dryup_ratio(volume: pd.Series, recent_bars: int = 3, ref_bars: int = 10) -> Optional[float]:
    """Return ratio of recent average volume to prior reference average.

    ratio = avg(volume[-recent:]) / avg(volume[-(recent+ref):-recent])
    < 1 means volume drying up; > 1 means volume expanding.
    Returns None when insufficient data.
    """
    needed = recent_bars + ref_bars
    if len(volume) < needed:
        return None

    recent_avg = float(volume.iloc[-recent_bars:].mean())
    ref_avg = float(volume.iloc[-(recent_bars + ref_bars):-recent_bars].mean())

    if ref_avg == 0:
        return None
    return round(recent_avg / ref_avg, 4)


def compute_updown_volume_ratio(
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> Optional[float]:
    """Return ratio of up-day volume to down-day volume over `period` bars.

    Returns None when insufficient data or no down days.
    """
    if len(close) < period + 1:
        return None

    close_slice = close.iloc[-period:]
    vol_slice = volume.iloc[-period:]
    price_change = close_slice.diff().iloc[1:]
    vol_aligned = vol_slice.iloc[1:]

    up_vol = float(vol_aligned[price_change > 0].sum())
    down_vol = float(vol_aligned[price_change < 0].sum())

    if down_vol == 0:
        return None if up_vol == 0 else None  # all up-days edge case
    return round(up_vol / down_vol, 4)


def _compute_breakout_volume_multiple(volume: pd.Series, period: int = 20) -> Optional[float]:
    """Return current volume / average volume over `period` bars (relative volume)."""
    if len(volume) < period + 1:
        return None
    avg_vol = float(volume.iloc[-(period + 1):-1].mean())
    if avg_vol == 0:
        return None
    current_vol = float(volume.iloc[-1])
    return round(current_vol / avg_vol, 4)


# ---------------------------------------------------------------------------
# Story 3: Relative strength vs QQQ, percentile ranks, drawdown, gap fill
# ---------------------------------------------------------------------------

def compute_rs_vs_benchmark(
    stock_close: pd.Series,
    bench_close: pd.Series,
    period: int = 63,
) -> Optional[float]:
    """Return relative strength of stock vs a benchmark as a percentage-point difference.

    RS = stock_period_return% - bench_period_return%
    Positive = stock outperforms, negative = underperforms.
    Returns None when insufficient data.
    """
    if len(stock_close) < period or len(bench_close) < period:
        return None

    stock_ret = (float(stock_close.iloc[-1]) / float(stock_close.iloc[-period]) - 1) * 100
    bench_ret = (float(bench_close.iloc[-1]) / float(bench_close.iloc[-period]) - 1) * 100
    return round(stock_ret - bench_ret, 4)


def compute_return_percentile_rank(
    close: pd.Series,
    return_bars: int,
    lookback: int = 252,
) -> Optional[float]:
    """Return the percentile rank (0–100) of the most recent N-bar return
    compared to all rolling N-bar returns over the past `lookback` bars.

    A high rank means recent return is strong relative to history.
    Returns None when insufficient data.
    """
    needed = return_bars + lookback
    if len(close) < needed:
        return None

    # Most recent N-bar return
    current_ret = float(close.iloc[-1]) / float(close.iloc[-(return_bars + 1)]) - 1

    # Historical distribution of N-bar returns over lookback window
    window = close.iloc[-(lookback + return_bars):]
    historical_rets = window.pct_change(return_bars).dropna()

    if len(historical_rets) < 2:
        return None

    rank = float((historical_rets < current_ret).sum()) / len(historical_rets) * 100
    return round(rank, 2)


def compute_max_drawdown(close: pd.Series, bars: int) -> Optional[float]:
    """Return max peak-to-trough drawdown (%) over the last `bars` bars.

    Result is <= 0 (or 0 for monotonically increasing prices).
    Returns None when insufficient data.
    """
    if len(close) < bars:
        return None

    window = close.iloc[-bars:]
    rolling_max = window.cummax()
    drawdown = (window - rolling_max) / rolling_max * 100
    result = float(drawdown.min())
    return round(result, 4)


def compute_gap_fill_status(open_: pd.Series, close: pd.Series, min_gap_pct: float = 2.0) -> bool:
    """Return True if the most recent significant gap has been filled.

    A gap is detected when today's open differs from yesterday's close by >= `min_gap_pct`%.
    Gap is 'filled' when subsequent price action returns to the pre-gap level.

    Returns False when no significant gap is found or data is insufficient.
    """
    if len(close) < 5 or len(open_) < 2:
        return False

    # Find the most recent gap (scan backwards from 2nd last bar to avoid current)
    for i in range(len(close) - 2, max(0, len(close) - 30), -1):
        prev_close = float(close.iloc[i - 1])
        curr_open = float(open_.iloc[i])
        if prev_close == 0:
            continue

        gap_pct = (curr_open - prev_close) / prev_close * 100

        if abs(gap_pct) >= min_gap_pct:
            # Gap found at bar i. Check if subsequent bars fill it.
            gap_level = prev_close  # pre-gap close level
            subsequent_close = close.iloc[i:]
            if gap_pct > 0:
                # Gap up: filled if price drops back to gap_level
                filled = (subsequent_close <= gap_level).any()
            else:
                # Gap down: filled if price rises back to gap_level
                filled = (subsequent_close >= gap_level).any()
            return bool(filled)

    return False


def compute_post_earnings_drift(
    close: pd.Series,
    earnings_date: Optional[pd.Timestamp],
) -> Optional[float]:
    """Return % return from the first bar on/after earnings_date to current price.

    Returns None when earnings_date is None, not in the index range, or < 2 bars available.
    """
    if earnings_date is None:
        return None

    if not isinstance(close.index, pd.DatetimeIndex):
        return None

    mask = close.index >= earnings_date
    if not mask.any():
        return None

    slice_after = close[mask]
    if len(slice_after) < 2:
        return None

    earnings_price = float(slice_after.iloc[0])
    current_price = float(slice_after.iloc[-1])
    if earnings_price == 0:
        return None

    return round((current_price / earnings_price - 1) * 100, 4)


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


def compute_rsi_slope(series: pd.Series, rsi_period: int = 14, slope_bars: int = 5) -> Optional[float]:
    """Return the 5-bar slope of the RSI series.

    slope = rsi[-1] - rsi[-(slope_bars+1)]
    Positive = momentum improving, negative = deteriorating.
    Returns None when there is insufficient data.
    """
    needed = rsi_period + slope_bars + 1
    if len(series) < needed:
        return None
    rsi_series = ta.rsi(series, length=rsi_period)
    if rsi_series is None or rsi_series.empty:
        return None
    rsi_clean = rsi_series.dropna()
    if len(rsi_clean) < slope_bars + 1:
        return None
    prev = float(rsi_clean.iloc[-(slope_bars + 1)])
    current = float(rsi_clean.iloc[-1])
    if np.isnan(prev) or np.isnan(current):
        return None
    return round(current - prev, 2)


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
    qqq_df: Optional[pd.DataFrame] = None,
    last_earnings_date: Optional[pd.Timestamp] = None,
) -> TechnicalIndicators:
    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    price = float(close.iloc[-1])

    # --- Existing MAs ---
    ma_10 = _sma(close, 10)
    ma_20 = _sma(close, 20)
    ma_50 = _sma(close, 50)
    ma_100 = _sma(close, 100)
    ma_200 = _sma(close, 200)

    # --- EMA relatives ---
    ema8_rel = compute_ema_relative(close, 8)
    ema21_rel = compute_ema_relative(close, 21)

    # --- SMA relatives ---
    sma20_rel = compute_sma_relative(close, 20)
    sma50_rel = compute_sma_relative(close, 50)
    sma200_rel = compute_sma_relative(close, 200)

    # --- SMA slopes ---
    sma20_slope = compute_sma_slope(close, 20)
    sma50_slope = compute_sma_slope(close, 50)
    sma200_slope = compute_sma_slope(close, 200)

    # --- Momentum indicators ---
    rsi = compute_rsi(close)
    rsi_slope_val = compute_rsi_slope(close)
    macd_val, macd_sig, macd_hist = compute_macd(close)
    adx_val = compute_adx(high, low, close)
    stoch_rsi = compute_stochastic_rsi(close)

    # --- Volatility ---
    atr = compute_atr(high, low, close)
    atr_pct = compute_atr_percent(atr, price)
    bb_position, bb_width = compute_bollinger_bands(close)
    weekly_vol, monthly_vol = compute_volatility_metrics(close)

    # --- Performance periods ---
    perfs = compute_performance_periods(close)

    # --- Gap / intraday metrics ---
    open_price = float(df["Open"].squeeze().iloc[-1]) if "Open" in df.columns else price
    prev_close = float(close.iloc[-2]) if len(close) > 1 else price
    gap_pct, change_from_open = compute_gap_metrics(open_price, prev_close, price)

    # --- Range distances ---
    range_dists = compute_range_distances(close, high, low)

    # --- Volume / accumulation (Story 2) ---
    obv_trend_val = compute_obv_trend(close, volume)
    ad_trend_val = compute_ad_trend(high, low, close, volume)
    cmf = compute_chaikin_money_flow(high, low, close, volume)
    vwap_dev = compute_vwap_deviation(high, low, close, volume)
    anchored_vwap_dev: Optional[float] = None  # populated externally when earnings date known
    vol_dryup = compute_volume_dryup_ratio(volume)
    breakout_vol_mult = _compute_breakout_volume_multiple(volume)
    updown_vol = compute_updown_volume_ratio(close, volume)

    # --- Existing derivations ---
    trend = classify_trend(close, ma_50, ma_200)
    is_extended, ext_20, ext_50 = detect_extension(price, ma_20, ma_50, rsi)
    vol_trend = compute_volume_trend(volume)
    sr = find_support_resistance(high, low, close)

    rs_spy = None
    rs_spy_20d = None
    rs_spy_63d = None
    if spy_df is not None and not spy_df.empty:
        spy_close = spy_df["Close"].squeeze()
        rs_spy = compute_relative_strength(close, spy_close)
        rs_spy_20d = compute_rs_vs_benchmark(close, spy_close, period=20)
        rs_spy_63d = compute_rs_vs_benchmark(close, spy_close, period=63)

    rs_qqq = None
    if qqq_df is not None and not qqq_df.empty:
        qqq_close = qqq_df["Close"].squeeze()
        rs_qqq = compute_rs_vs_benchmark(close, qqq_close, period=63)

    rs_sector = None
    rs_sector_20d = None
    rs_sector_63d = None
    if sector_df is not None and not sector_df.empty:
        sector_close = sector_df["Close"].squeeze()
        rs_sector = compute_relative_strength(close, sector_close)
        rs_sector_20d = compute_rs_vs_benchmark(close, sector_close, period=20)
        rs_sector_63d = compute_rs_vs_benchmark(close, sector_close, period=63)

    # --- Story 3: Percentile ranks, drawdown, gap fill, post-earnings drift ---
    rank_20d = compute_return_percentile_rank(close, return_bars=20, lookback=252)
    rank_63d = compute_return_percentile_rank(close, return_bars=63, lookback=252)
    rank_126d = compute_return_percentile_rank(close, return_bars=126, lookback=252)
    rank_252d = compute_return_percentile_rank(close, return_bars=252, lookback=252)

    dd_3m = compute_max_drawdown(close, bars=63)
    dd_1y = compute_max_drawdown(close, bars=252)

    open_series = df["Open"].squeeze() if "Open" in df.columns else close
    gap_fill = compute_gap_fill_status(open_series, close)

    post_earn_drift = compute_post_earnings_drift(close, last_earnings_date)

    # Anchored VWAP from earnings (Story 2 + Story 3 integration)
    anchored_vwap_dev = compute_anchored_vwap_deviation(
        high, low, close, volume, earnings_date=last_earnings_date
    )

    tech_score = score_technicals(trend, rsi, macd_hist, is_extended, vol_trend, rs_spy, sr, price)

    return TechnicalIndicators(
        # Existing MAs
        ma_10=ma_10,
        ma_20=ma_20,
        ma_50=ma_50,
        ma_100=ma_100,
        ma_200=ma_200,
        # EMA relatives
        ema8_relative=ema8_rel,
        ema21_relative=ema21_rel,
        # SMA relatives
        sma20_relative=sma20_rel,
        sma50_relative=sma50_rel,
        sma200_relative=sma200_rel,
        # SMA slopes
        sma20_slope=sma20_slope,
        sma50_slope=sma50_slope,
        sma200_slope=sma200_slope,
        # Momentum
        rsi_14=rsi,
        rsi_slope=rsi_slope_val,
        macd=macd_val,
        macd_signal=macd_sig,
        macd_histogram=macd_hist,
        adx=adx_val,
        stochastic_rsi=stoch_rsi,
        # Volatility
        atr=atr,
        atr_percent=atr_pct,
        bollinger_band_position=bb_position,
        bollinger_band_width=bb_width,
        volatility_weekly=weekly_vol,
        volatility_monthly=monthly_vol,
        # Performance
        perf_1w=perfs["perf_1w"],
        perf_1m=perfs["perf_1m"],
        perf_3m=perfs["perf_3m"],
        perf_6m=perfs["perf_6m"],
        perf_ytd=perfs["perf_ytd"],
        perf_1y=perfs["perf_1y"],
        perf_3y=perfs["perf_3y"],
        perf_5y=perfs["perf_5y"],
        # Intraday
        gap_percent=gap_pct,
        change_from_open_percent=change_from_open,
        # Range distances
        dist_from_20d_high=range_dists["dist_from_20d_high"],
        dist_from_20d_low=range_dists["dist_from_20d_low"],
        dist_from_50d_high=range_dists["dist_from_50d_high"],
        dist_from_50d_low=range_dists["dist_from_50d_low"],
        dist_from_52w_high=range_dists["dist_from_52w_high"],
        dist_from_52w_low=range_dists["dist_from_52w_low"],
        dist_from_ath=range_dists["dist_from_ath"],
        dist_from_atl=range_dists["dist_from_atl"],
        # Volume / accumulation (Story 2)
        obv_trend=obv_trend_val,
        ad_trend=ad_trend_val,
        chaikin_money_flow=cmf,
        vwap_deviation=vwap_dev,
        anchored_vwap_deviation=anchored_vwap_dev,
        volume_dryup_ratio=vol_dryup,
        breakout_volume_multiple=breakout_vol_mult,
        updown_volume_ratio=updown_vol,
        # Volume / trend / extension
        volume_trend=vol_trend,
        trend=trend,
        is_extended=is_extended,
        extension_pct_above_20ma=ext_20,
        extension_pct_above_50ma=ext_50,
        # Support / resistance
        support_resistance=sr,
        # Relative strength
        rs_vs_spy=rs_spy,
        rs_vs_qqq=rs_qqq,
        rs_vs_sector=rs_sector,
        rs_vs_spy_20d=rs_spy_20d,
        rs_vs_spy_63d=rs_spy_63d,
        rs_vs_sector_20d=rs_sector_20d,
        rs_vs_sector_63d=rs_sector_63d,
        # Story 3: percentile ranks
        return_pct_rank_20d=rank_20d,
        return_pct_rank_63d=rank_63d,
        return_pct_rank_126d=rank_126d,
        return_pct_rank_252d=rank_252d,
        # Story 3: drawdown
        max_drawdown_3m=dd_3m,
        max_drawdown_1y=dd_1y,
        # Story 3: gap fill & post-earnings drift
        gap_filled=gap_fill,
        post_earnings_drift=post_earn_drift,
        # Score
        technical_score=tech_score,
    )
