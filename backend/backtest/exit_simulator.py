"""
Exit simulation for backtest.

Given an entry price and date, simulates realistic exit prices for different
exit strategies (fixed horizon, ATR stop/target, trailing stop).

Always computes MAE and MFE across the holding window for diagnostic purposes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from backtest.config import HOLDING_PERIODS
from backtest.snapshot import _normalize_ts

logger = logging.getLogger(__name__)

EXIT_METHODS = frozenset({"FIXED_HORIZON", "ATR_STOP_TARGET", "TRAILING_STOP"})
DEFAULT_EXIT_METHOD = "FIXED_HORIZON"


@dataclass
class ExitResult:
    exit_price: Optional[float]
    exit_date: Optional[str]           # ISO date string, or None
    method_used: str
    holding_days: int                  # actual trading days held
    exit_reason: str                   # FIXED_HORIZON / STOP_HIT / TARGET_HIT / TRAILING_STOP_HIT / DATA_END
    pnl_pct: Optional[float]           # (exit - entry) / entry * 100
    mae_pct: Optional[float]           # Maximum Adverse Excursion (worst intra-trade trough)
    mfe_pct: Optional[float]           # Maximum Favorable Excursion (best intra-trade peak)


class ExitSimulator:
    """Simulates realistic exit prices for different exit strategies."""

    def simulate_exit(
        self,
        entry_date: pd.Timestamp,
        entry_price: float,
        price_df: pd.DataFrame,
        method: str = DEFAULT_EXIT_METHOD,
        horizon: str = "short_term",
        atr_stop_multiplier: float = 2.0,
        atr_target_multiplier: float = 3.0,
        trailing_pct: float = 0.15,
    ) -> ExitResult:
        """Simulate the exit for a position.

        price_df must contain full history including bars after entry_date.

        Args:
            entry_date:            Date the position was entered.
            entry_price:           Entry price in dollars.
            price_df:              Full OHLCV price history.
            method:                One of EXIT_METHODS.
            horizon:               "short_term" / "medium_term" / "long_term".
            atr_stop_multiplier:   ATR multiplier for the stop level.
            atr_target_multiplier: ATR multiplier for the profit target.
            trailing_pct:          Trailing stop percentage below peak (0.15 = 15%).
        """
        if method not in EXIT_METHODS:
            raise ValueError(
                f"Unknown exit method '{method}'. Valid: {sorted(EXIT_METHODS)}"
            )

        if price_df.empty or entry_price <= 0:
            return ExitResult(None, None, method, 0, "DATA_UNAVAILABLE", None, None, None)

        norm_date = _normalize_ts(entry_date)
        start_pos = int(price_df.index.searchsorted(norm_date, side="right"))
        max_days = HOLDING_PERIODS.get(horizon, 20)
        end_pos = min(start_pos + max_days, len(price_df))
        window = price_df.iloc[start_pos:end_pos]

        if window.empty:
            return ExitResult(None, None, method, 0, "DATA_END", None, None, None)

        mae_pct, mfe_pct = self._compute_mae_mfe(window, entry_price)

        if method == "FIXED_HORIZON":
            return self._fixed_horizon(window, entry_price, method, mae_pct, mfe_pct)

        if method == "ATR_STOP_TARGET":
            return self._atr_exit(
                price_df, start_pos, window, entry_price, method,
                atr_stop_multiplier, atr_target_multiplier, mae_pct, mfe_pct,
            )

        if method == "TRAILING_STOP":
            return self._trailing_stop(
                window, entry_price, method, trailing_pct, mae_pct, mfe_pct
            )

        return ExitResult(None, None, method, 0, "DATA_END", None, None, None)

    # ----------------------------------------------------------------- private

    @staticmethod
    def _compute_mae_mfe(
        window: pd.DataFrame, entry_price: float
    ) -> tuple[Optional[float], Optional[float]]:
        """MAE = worst trough, MFE = best peak, both as % from entry."""
        has_low  = "Low" in window.columns
        has_high = "High" in window.columns
        lows  = window["Low"].values  if has_low  else window["Close"].values
        highs = window["High"].values if has_high else window["Close"].values
        mae_pct = round((float(lows.min())  - entry_price) / entry_price * 100, 4)
        mfe_pct = round((float(highs.max()) - entry_price) / entry_price * 100, 4)
        return mae_pct, mfe_pct

    @staticmethod
    def _fixed_horizon(
        window: pd.DataFrame,
        entry_price: float,
        method: str,
        mae_pct: Optional[float],
        mfe_pct: Optional[float],
    ) -> ExitResult:
        exit_price = float(window.iloc[-1]["Close"])
        return ExitResult(
            exit_price=exit_price,
            exit_date=str(window.index[-1].date()),
            method_used=method,
            holding_days=len(window),
            exit_reason="FIXED_HORIZON",
            pnl_pct=round((exit_price - entry_price) / entry_price * 100, 4),
            mae_pct=mae_pct,
            mfe_pct=mfe_pct,
        )

    @staticmethod
    def _compute_atr(price_df: pd.DataFrame, pos: int, period: int = 14) -> Optional[float]:
        """Compute ATR over the period bars before pos."""
        start = max(0, pos - period - 1)
        sub = price_df.iloc[start:pos]
        if len(sub) < 2:
            return None
        closes = sub["Close"]
        highs  = sub["High"] if "High" in sub.columns else closes
        lows   = sub["Low"]  if "Low"  in sub.columns else closes
        trs = [
            max(
                float(highs.iloc[i]) - float(lows.iloc[i]),
                abs(float(highs.iloc[i]) - float(closes.iloc[i - 1])),
                abs(float(lows.iloc[i])  - float(closes.iloc[i - 1])),
            )
            for i in range(1, len(sub))
        ]
        return round(sum(trs) / len(trs), 4) if trs else None

    @classmethod
    def _atr_exit(
        cls,
        price_df: pd.DataFrame,
        start_pos: int,
        window: pd.DataFrame,
        entry_price: float,
        method: str,
        stop_mult: float,
        target_mult: float,
        mae_pct: Optional[float],
        mfe_pct: Optional[float],
    ) -> ExitResult:
        atr = cls._compute_atr(price_df, start_pos)
        if not atr:
            # Fall back to fixed horizon when ATR is unavailable
            return cls._fixed_horizon(window, entry_price, method, mae_pct, mfe_pct)

        stop_price   = entry_price - stop_mult   * atr
        target_price = entry_price + target_mult * atr
        has_low  = "Low"  in window.columns
        has_high = "High" in window.columns

        for i, (date, row) in enumerate(window.iterrows()):
            low_  = float(row["Low"])  if has_low  else float(row["Close"])
            high_ = float(row["High"]) if has_high else float(row["Close"])

            if low_ <= stop_price:
                return ExitResult(
                    exit_price=round(stop_price, 4),
                    exit_date=str(date.date()),
                    method_used=method,
                    holding_days=i + 1,
                    exit_reason="STOP_HIT",
                    pnl_pct=round((stop_price - entry_price) / entry_price * 100, 4),
                    mae_pct=mae_pct,
                    mfe_pct=mfe_pct,
                )
            if high_ >= target_price:
                return ExitResult(
                    exit_price=round(target_price, 4),
                    exit_date=str(date.date()),
                    method_used=method,
                    holding_days=i + 1,
                    exit_reason="TARGET_HIT",
                    pnl_pct=round((target_price - entry_price) / entry_price * 100, 4),
                    mae_pct=mae_pct,
                    mfe_pct=mfe_pct,
                )

        return cls._fixed_horizon(window, entry_price, method, mae_pct, mfe_pct)

    @staticmethod
    def _trailing_stop(
        window: pd.DataFrame,
        entry_price: float,
        method: str,
        trailing_pct: float,
        mae_pct: Optional[float],
        mfe_pct: Optional[float],
    ) -> ExitResult:
        peak = entry_price
        has_high = "High" in window.columns
        has_low  = "Low"  in window.columns

        for i, (date, row) in enumerate(window.iterrows()):
            high_ = float(row["High"]) if has_high else float(row["Close"])
            low_  = float(row["Low"])  if has_low  else float(row["Close"])
            peak  = max(peak, high_)
            stop_level = peak * (1.0 - trailing_pct)

            if low_ <= stop_level:
                return ExitResult(
                    exit_price=round(stop_level, 4),
                    exit_date=str(date.date()),
                    method_used=method,
                    holding_days=i + 1,
                    exit_reason="TRAILING_STOP_HIT",
                    pnl_pct=round((stop_level - entry_price) / entry_price * 100, 4),
                    mae_pct=mae_pct,
                    mfe_pct=mfe_pct,
                )

        exit_price = float(window.iloc[-1]["Close"])
        return ExitResult(
            exit_price=exit_price,
            exit_date=str(window.index[-1].date()),
            method_used=method,
            holding_days=len(window),
            exit_reason="FIXED_HORIZON",
            pnl_pct=round((exit_price - entry_price) / entry_price * 100, 4),
            mae_pct=mae_pct,
            mfe_pct=mfe_pct,
        )
