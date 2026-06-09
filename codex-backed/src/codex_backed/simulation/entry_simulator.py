from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EntryExecution:
    entry_price: float | None
    entry_index: int | None
    entry_date: str | None
    method_used: str
    wait_days: int
    triggered: bool


class EntryExecutionSimulator:
    """Simulate simple historical entries on list-of-dict OHLCV bars."""

    VALID_METHODS = {
        "NEXT_OPEN",
        "NEXT_CLOSE",
        "PULLBACK_TO_SMA20",
        "PULLBACK_TO_SMA50",
        "BREAKOUT_CONFIRMATION",
    }

    def simulate(
        self,
        bars: list[dict[str, Any]],
        *,
        signal_index: int,
        method: str,
        max_wait_days: int,
    ) -> EntryExecution:
        if method not in self.VALID_METHODS:
            raise ValueError(f"Unknown entry method: {method}")
        start = signal_index + 1
        if start >= len(bars):
            return EntryExecution(None, None, None, method, 0, False)

        if method == "NEXT_OPEN":
            bar = bars[start]
            return EntryExecution(float(bar.get("open", bar["close"])), start, bar.get("date"), method, 0, True)
        if method == "NEXT_CLOSE":
            bar = bars[start]
            return EntryExecution(float(bar["close"]), start, bar.get("date"), method, 0, True)
        if method == "PULLBACK_TO_SMA20":
            return self._pullback_to_sma(bars, start, method, max_wait_days, 20)
        if method == "PULLBACK_TO_SMA50":
            return self._pullback_to_sma(bars, start, method, max_wait_days, 50)
        return self._breakout_confirmation(bars, start, method, max_wait_days)

    @staticmethod
    def _pullback_to_sma(
        bars: list[dict[str, Any]],
        start: int,
        method: str,
        max_wait_days: int,
        period: int,
    ) -> EntryExecution:
        for offset in range(max_wait_days + 1):
            idx = start + offset
            if idx >= len(bars):
                break
            if idx + 1 < period:
                continue
            sma = sum(float(bar["close"]) for bar in bars[idx + 1 - period : idx + 1]) / period
            low = float(bars[idx].get("low", bars[idx]["close"]))
            if low <= sma:
                return EntryExecution(
                    round(min(float(bars[idx]["close"]), sma), 4),
                    idx,
                    bars[idx].get("date"),
                    method,
                    offset,
                    True,
                )
        return EntryExecution(None, None, None, method, max_wait_days, False)

    @staticmethod
    def _breakout_confirmation(
        bars: list[dict[str, Any]],
        start: int,
        method: str,
        max_wait_days: int,
        lookback: int = 20,
    ) -> EntryExecution:
        if start < lookback:
            return EntryExecution(None, None, None, method, 0, False)
        resistance = max(float(bar["close"]) for bar in bars[start - lookback : start])
        avg_volume = sum(float(bar.get("volume", 0.0)) for bar in bars[start - lookback : start]) / lookback
        for offset in range(max_wait_days + 1):
            idx = start + offset
            if idx >= len(bars):
                break
            close = float(bars[idx]["close"])
            volume = float(bars[idx].get("volume", 0.0))
            if close > resistance and (avg_volume == 0.0 or volume > avg_volume):
                return EntryExecution(close, idx, bars[idx].get("date"), method, offset, True)
        return EntryExecution(None, None, None, method, max_wait_days, False)
