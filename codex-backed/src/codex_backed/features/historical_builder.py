from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from codex_backed.data.bars import find_index_on_or_before


@dataclass(frozen=True)
class HistoricalFeatureOptions:
    start: str
    end: str
    horizons: set[str]
    signal_frequency: str = "weekly"


def build_historical_feature_rows(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    tickers: list[str],
    options: HistoricalFeatureOptions,
) -> list[dict[str, Any]]:
    """Build FeatureSnapshot-compatible rows from normalized OHLCV bars."""

    spy_features = _build_frame_features(bars_by_ticker.get("SPY", []))
    spy_regime = _build_spy_regime(spy_features)
    rows: list[dict[str, Any]] = []

    for ticker in tickers:
        bars = bars_by_ticker.get(ticker, [])
        if not bars:
            continue
        features = _build_frame_features(bars)
        if features.empty:
            continue
        signal_dates = _select_signal_dates(features, options)
        for date_iso in signal_dates:
            idx = features.index.get_loc(date_iso)
            row = _row_to_feature_dict(ticker, features.iloc[idx], date_iso)
            _add_relative_strength(row, features, spy_features, date_iso)
            regime, confidence = _regime_for_date(spy_regime, date_iso)
            row["market_regime"] = regime
            row["regime_confidence"] = confidence
            for horizon in sorted(options.horizons):
                rows.append({**row, "horizon": horizon})

    rows.sort(key=lambda item: (item["ticker"], item["date"], item["horizon"]))
    return rows


def _build_frame_features(bars: list[dict[str, Any]]) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame()
    df = pd.DataFrame(bars).copy()
    if df.empty:
        return df
    df["date"] = df["date"].astype(str).str[:10]
    df = df.sort_values("date").set_index("date")
    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    for window in (20, 50, 200):
        sma = close.rolling(window, min_periods=window).mean()
        df[f"sma{window}"] = sma
        df[f"sma{window}_relative"] = _pct(close, sma)
        df[f"sma{window}_slope"] = _pct(sma, sma.shift(5))

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["rsi14"] = 100.0 - (100.0 / (1.0 + rs))
    df["rsi_slope"] = df["rsi14"] - df["rsi14"].shift(5)

    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    df["atr"] = true_range.rolling(14, min_periods=14).mean()
    df["atr_percent"] = df["atr"] / close * 100.0

    for name, periods in [("perf_1w", 5), ("perf_1m", 21), ("perf_3m", 63), ("perf_6m", 126), ("perf_1y", 252)]:
        df[name] = _pct(close, close.shift(periods))

    df["gap_percent"] = _pct(df["open"], prev_close)
    df["change_from_open_percent"] = _pct(close, df["open"])

    avg_vol_5 = volume.rolling(5, min_periods=5).mean()
    avg_vol_20 = volume.rolling(20, min_periods=20).mean()
    df["volume_dryup_ratio"] = avg_vol_5 / avg_vol_20
    df["breakout_volume_multiple"] = volume / avg_vol_20.shift(1)
    up_volume = volume.where(close > prev_close, 0.0).rolling(20, min_periods=20).sum()
    down_volume = volume.where(close < prev_close, 0.0).rolling(20, min_periods=20).sum()
    df["updown_volume_ratio"] = up_volume / down_volume.replace(0, pd.NA)

    high_20 = high.rolling(20, min_periods=20).max()
    high_252 = high.rolling(252, min_periods=60).max()
    low_252 = low.rolling(252, min_periods=60).min()
    df["dist_from_20d_high"] = _pct(close, high_20)
    df["dist_from_52w_high"] = _pct(close, high_252)
    df["dist_from_52w_low"] = _pct(close, low_252)
    df["max_drawdown_3m"] = _pct(close, close.rolling(63, min_periods=20).max())
    df["max_drawdown_1y"] = _pct(close, close.rolling(252, min_periods=60).max())

    df["trend_label"] = "sideways"
    df.loc[(close > df["sma50"]) & (df["sma50"] > df["sma200"]) & (df["sma50_slope"] > 0), "trend_label"] = "strong_uptrend"
    df.loc[(close > df["sma50"]) & (df["sma50_slope"] >= 0) & (df["trend_label"] == "sideways"), "trend_label"] = "weak_uptrend"
    df.loc[(close < df["sma50"]) & (close < df["sma200"]) & (df["sma50_slope"] < 0), "trend_label"] = "downtrend"
    df["is_extended"] = df["sma20_relative"] > 8.0
    df["extension_pct_above_20ma"] = df["sma20_relative"]
    df["extension_pct_above_50ma"] = df["sma50_relative"]
    return df


def _pct(value: pd.Series, base: pd.Series) -> pd.Series:
    return (value / base - 1.0) * 100.0


def _select_signal_dates(df: pd.DataFrame, options: HistoricalFeatureOptions) -> list[str]:
    scoped = df[(df.index >= options.start) & (df.index <= options.end)]
    if options.signal_frequency == "daily":
        return list(scoped.index)
    if options.signal_frequency != "weekly":
        raise ValueError(f"Unsupported signal_frequency: {options.signal_frequency}")
    return [date for pos, date in enumerate(scoped.index) if pos % 5 == 0]


def _row_to_feature_dict(ticker: str, row: pd.Series, date_iso: str) -> dict[str, Any]:
    fields = {
        "ticker": ticker,
        "date": date_iso,
        "price": _clean(row.get("close")),
        "sma20_relative": _clean(row.get("sma20_relative")),
        "sma50_relative": _clean(row.get("sma50_relative")),
        "sma200_relative": _clean(row.get("sma200_relative")),
        "sma20_slope": _clean(row.get("sma20_slope")),
        "sma50_slope": _clean(row.get("sma50_slope")),
        "sma200_slope": _clean(row.get("sma200_slope")),
        "rsi14": _clean(row.get("rsi14")),
        "rsi_slope": _clean(row.get("rsi_slope")),
        "atr_percent": _clean(row.get("atr_percent")),
        "perf_1w": _clean(row.get("perf_1w")),
        "perf_1m": _clean(row.get("perf_1m")),
        "perf_3m": _clean(row.get("perf_3m")),
        "perf_6m": _clean(row.get("perf_6m")),
        "perf_1y": _clean(row.get("perf_1y")),
        "gap_percent": _clean(row.get("gap_percent")),
        "change_from_open_percent": _clean(row.get("change_from_open_percent")),
        "volume_dryup_ratio": _clean(row.get("volume_dryup_ratio")),
        "breakout_volume_multiple": _clean(row.get("breakout_volume_multiple")),
        "updown_volume_ratio": _clean(row.get("updown_volume_ratio")),
        "dist_from_20d_high": _clean(row.get("dist_from_20d_high")),
        "dist_from_52w_high": _clean(row.get("dist_from_52w_high")),
        "dist_from_52w_low": _clean(row.get("dist_from_52w_low")),
        "max_drawdown_3m": _clean(row.get("max_drawdown_3m")),
        "max_drawdown_1y": _clean(row.get("max_drawdown_1y")),
        "trend_label": row.get("trend_label") or "sideways",
        "is_extended": bool(row.get("is_extended", False)),
        "extension_pct_above_20ma": _clean(row.get("extension_pct_above_20ma")),
        "extension_pct_above_50ma": _clean(row.get("extension_pct_above_50ma")),
        "primary_category": "TECHNICAL_NATIVE",
        "archetype": "TECHNICAL_NATIVE",
    }
    return fields


def _add_relative_strength(row: dict[str, Any], features: pd.DataFrame, spy_features: pd.DataFrame, date_iso: str) -> None:
    spy_idx = find_index_on_or_before([{"date": date} for date in spy_features.index], date_iso)
    if spy_idx is None or spy_features.empty:
        row["rs_vs_spy_20d"] = None
        row["rs_vs_spy_63d"] = None
        row["rs_vs_spy"] = None
        return
    spy_row = spy_features.iloc[spy_idx]
    ticker_row = features.loc[date_iso]
    rs20 = _spread(ticker_row.get("perf_1m"), spy_row.get("perf_1m"))
    rs63 = _spread(ticker_row.get("perf_3m"), spy_row.get("perf_3m"))
    row["rs_vs_spy_20d"] = rs20
    row["rs_vs_spy_63d"] = rs63
    row["rs_vs_spy"] = rs20


def _spread(value: Any, benchmark: Any) -> float | None:
    value = _clean(value)
    benchmark = _clean(benchmark)
    if value is None or benchmark is None:
        return None
    return round(value - benchmark, 4)


def _build_spy_regime(spy_features: pd.DataFrame) -> dict[str, tuple[str, float]]:
    regimes: dict[str, tuple[str, float]] = {}
    if spy_features.empty:
        return regimes
    for date_iso, row in spy_features.iterrows():
        close = row.get("close")
        sma50 = row.get("sma50")
        sma200 = row.get("sma200")
        sma50_slope = row.get("sma50_slope")
        if pd.isna(sma50) or pd.isna(sma200):
            regimes[date_iso] = ("SIDEWAYS_CHOPPY", 40.0)
        elif close > sma50 and sma50 > sma200 and sma50_slope >= 0:
            regimes[date_iso] = ("BULL_RISK_ON", 75.0)
        elif close < sma50 and close < sma200:
            regimes[date_iso] = ("BEAR_RISK_OFF", 70.0)
        elif close > sma50 and close < sma200:
            regimes[date_iso] = ("LIQUIDITY_RALLY", 60.0)
        else:
            regimes[date_iso] = ("SIDEWAYS_CHOPPY", 55.0)
    return regimes


def _regime_for_date(regimes: dict[str, tuple[str, float]], date_iso: str) -> tuple[str, float]:
    if not regimes:
        return "SIDEWAYS_CHOPPY", 20.0
    dates = [{"date": date} for date in regimes]
    idx = find_index_on_or_before(dates, date_iso)
    if idx is None:
        return "SIDEWAYS_CHOPPY", 20.0
    return regimes[list(regimes)[idx]]


def _clean(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        return None
    return round(float(value), 4)
