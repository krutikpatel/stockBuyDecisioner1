"""
Entry simulation for backtest.

Simulates realistic entry prices for different entry methods instead of
always assuming entry at the same-day signal close.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from backtest.snapshot import _normalize_ts

logger = logging.getLogger(__name__)

ENTRY_METHODS = frozenset({
    "NEXT_CLOSE",
    "NEXT_OPEN",
    "PULLBACK_TO_SMA20",
    "PULLBACK_TO_SMA50",
    "BREAKOUT_CONFIRMATION",
})

DEFAULT_ENTRY_METHOD = "NEXT_CLOSE"


@dataclass
class EntryResult:
    entry_price: Optional[float]   # None if not triggered within max_wait_days
    entry_date: Optional[str]      # ISO date string, or None
    method_used: str
    wait_days: int                 # trading days between signal_date and entry
    not_triggered: bool            # True if pullback/breakout never triggered


class EntrySimulator:
    """Simulates realistic entry prices for a given signal."""

    def simulate_entry(
        self,
        signal_date: pd.Timestamp,
        price_df: pd.DataFrame,
        method: str = DEFAULT_ENTRY_METHOD,
        max_wait_days: int = 10,
    ) -> EntryResult:
        """Return the simulated entry for the given method.

        price_df must contain full history (including bars after signal_date).

        Args:
            signal_date:   Date the signal was generated (entry starts next bar).
            price_df:      Full OHLCV price history for the ticker.
            method:        One of ENTRY_METHODS.
            max_wait_days: Max trading days to wait for pullback/breakout trigger.
        """
        if method not in ENTRY_METHODS:
            raise ValueError(
                f"Unknown entry method '{method}'. Valid: {sorted(ENTRY_METHODS)}"
            )

        if price_df.empty:
            return EntryResult(None, None, method, 0, True)

        norm_date = _normalize_ts(signal_date)
        start_pos = int(price_df.index.searchsorted(norm_date, side="right"))

        if start_pos >= len(price_df):
            return EntryResult(None, None, method, 0, True)

        if method == "NEXT_CLOSE":
            return self._next_close(price_df, start_pos, method)

        if method == "NEXT_OPEN":
            return self._next_open(price_df, start_pos, method)

        if method == "PULLBACK_TO_SMA20":
            return self._sma_pullback(price_df, start_pos, 20, method, max_wait_days)

        if method == "PULLBACK_TO_SMA50":
            return self._sma_pullback(price_df, start_pos, 50, method, max_wait_days)

        if method == "BREAKOUT_CONFIRMATION":
            return self._breakout(price_df, start_pos, method, max_wait_days)

        return EntryResult(None, None, method, 0, True)  # unreachable

    # ----------------------------------------------------------------- private

    @staticmethod
    def _next_close(price_df: pd.DataFrame, start_pos: int, method: str) -> EntryResult:
        row = price_df.iloc[start_pos]
        return EntryResult(
            entry_price=float(row["Close"]),
            entry_date=str(price_df.index[start_pos].date()),
            method_used=method,
            wait_days=0,
            not_triggered=False,
        )

    @staticmethod
    def _next_open(price_df: pd.DataFrame, start_pos: int, method: str) -> EntryResult:
        row = price_df.iloc[start_pos]
        has_open = "Open" in price_df.columns and pd.notna(row.get("Open"))
        price = float(row["Open"]) if has_open else float(row["Close"])
        return EntryResult(
            entry_price=price,
            entry_date=str(price_df.index[start_pos].date()),
            method_used=method,
            wait_days=0,
            not_triggered=False,
        )

    @staticmethod
    def _sma_pullback(
        price_df: pd.DataFrame,
        start_pos: int,
        period: int,
        method: str,
        max_wait_days: int,
    ) -> EntryResult:
        """Enter on first bar where Low touches the rolling SMA."""
        sma = price_df["Close"].rolling(period).mean()
        has_low = "Low" in price_df.columns

        for offset in range(max_wait_days):
            i = start_pos + offset
            if i >= len(price_df):
                break
            sma_val = sma.iloc[i]
            if pd.isna(sma_val):
                continue
            row = price_df.iloc[i]
            low_val = float(row["Low"]) if has_low else float(row["Close"])
            if low_val <= float(sma_val):
                entry = min(float(row["Close"]), float(sma_val))
                return EntryResult(
                    entry_price=round(entry, 4),
                    entry_date=str(price_df.index[i].date()),
                    method_used=method,
                    wait_days=offset + 1,
                    not_triggered=False,
                )

        return EntryResult(None, None, method, max_wait_days, True)

    @staticmethod
    def _breakout(
        price_df: pd.DataFrame,
        start_pos: int,
        method: str,
        max_wait_days: int,
        lookback: int = 20,
    ) -> EntryResult:
        """Enter on first close above the 20-bar resistance with above-avg volume."""
        if start_pos < lookback:
            return EntryResult(None, None, method, 0, True)

        resistance = float(
            price_df["Close"].iloc[start_pos - lookback : start_pos].max()
        )
        avg_vol = (
            float(price_df["Volume"].iloc[start_pos - lookback : start_pos].mean())
            if "Volume" in price_df.columns
            else 0.0
        )

        for offset in range(max_wait_days):
            i = start_pos + offset
            if i >= len(price_df):
                break
            row = price_df.iloc[i]
            close = float(row["Close"])
            vol = float(row.get("Volume", 0)) if "Volume" in price_df.columns else 0.0
            if close > resistance and (avg_vol == 0.0 or vol > avg_vol):
                return EntryResult(
                    entry_price=close,
                    entry_date=str(price_df.index[i].date()),
                    method_used=method,
                    wait_days=offset + 1,
                    not_triggered=False,
                )

        return EntryResult(None, None, method, max_wait_days, True)
