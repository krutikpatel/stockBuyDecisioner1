from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime
from typing import Any


def normalize_price_frame(df) -> list[dict[str, Any]]:
    """Convert a pandas OHLCV DataFrame into lower-case bar dictionaries."""
    bars: list[dict[str, Any]] = []
    if df is None or getattr(df, "empty", True):
        return bars

    for idx, row in df.iterrows():
        date_str = _date_to_iso(idx)
        close = _row_get(row, "Close", "close")
        if close is None:
            continue
        open_ = _row_get(row, "Open", "open", default=close)
        high = _row_get(row, "High", "high", default=close)
        low = _row_get(row, "Low", "low", default=close)
        volume = _row_get(row, "Volume", "volume", default=0.0)
        bars.append(
            {
                "date": date_str,
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
            }
        )
    return bars


def build_date_index(bars: list[dict[str, Any]]) -> dict[str, int]:
    return {bar["date"]: idx for idx, bar in enumerate(bars)}


def find_index_on_or_before(bars: list[dict[str, Any]], date_iso: str) -> int | None:
    if not bars:
        return None
    dates = [bar["date"] for bar in bars]
    pos = bisect_right(dates, date_iso) - 1
    if pos < 0:
        return None
    return pos


def _date_to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)[:10]


def _row_get(row, *names: str, default=None):
    for name in names:
        try:
            value = row[name]
        except (KeyError, TypeError):
            continue
        if value == value:
            return value
    return default

