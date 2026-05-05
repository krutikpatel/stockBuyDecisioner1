"""
Computes forward returns for each signal.
Uses pre-cached price data to look up the price at signal_date + holding_period.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from backtest.config import HOLDING_PERIODS
from backtest.snapshot import get_price_slice, _normalize_ts

logger = logging.getLogger(__name__)


def _get_price_at_offset(
    price_df: pd.DataFrame,
    from_date: pd.Timestamp,
    trading_days_offset: int,
) -> Optional[float]:
    """
    Return the closing price `trading_days_offset` trading days after `from_date`.
    Returns None if date is in the future or data is unavailable.
    """
    if price_df.empty:
        return None

    norm_from = _normalize_ts(from_date)
    idx_norm = price_df.index.map(_normalize_ts)
    future_mask = idx_norm > norm_from
    future_prices = price_df[future_mask]

    if len(future_prices) < trading_days_offset:
        return None

    return float(future_prices["Close"].iloc[trading_days_offset - 1])


def attach_outcomes(
    signals: list[dict],
    prices: dict[str, pd.DataFrame],
) -> list[dict]:
    """
    For each signal, compute:
      - forward_return: % price change over the holding period
      - spy_return: SPY % change over the same period
      - excess_return: forward_return - spy_return

    Modifies signals in-place and returns the list.
    """
    spy_df = prices.get("SPY", pd.DataFrame())

    for sig in signals:
        ticker = sig["ticker"]
        horizon = sig["horizon"]
        signal_date = pd.Timestamp(sig["date"])
        holding_days = HOLDING_PERIODS.get(horizon, 20)

        price_df = prices.get(ticker, pd.DataFrame())
        entry_price = sig.get("price")

        if entry_price is None or price_df.empty:
            continue

        exit_price = _get_price_at_offset(price_df, signal_date, holding_days)
        spy_entry = _get_price_at_offset(spy_df, signal_date - pd.Timedelta(days=1), 1)
        spy_exit = _get_price_at_offset(spy_df, signal_date, holding_days)

        if exit_price is not None:
            sig["forward_return"] = round((exit_price - entry_price) / entry_price * 100, 4)
        else:
            sig["forward_return"] = None  # outcome not yet available

        if spy_entry is not None and spy_exit is not None:
            spy_ret = (spy_exit - spy_entry) / spy_entry * 100
            sig["spy_return"] = round(spy_ret, 4)
            if sig["forward_return"] is not None:
                sig["excess_return"] = round(sig["forward_return"] - spy_ret, 4)
        else:
            sig["spy_return"] = None
            sig["excess_return"] = None

    resolved = sum(1 for s in signals if s["forward_return"] is not None)
    logger.info("Outcomes attached: %d/%d signals resolved", resolved, len(signals))
    return signals
