"""
Attaches forward returns to each signal record.

For every signal, looks up the closing price N trading days after the signal date
and computes:
  - forward_return       : % price change over the holding period
  - spy_return           : SPY % change over the same period
  - qqq_return           : QQQ % change over the same period
  - excess_return        : forward_return - spy_return
  - excess_return_vs_qqq : forward_return - qqq_return
  - max_drawdown_period  : worst intra-period trough from entry price
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from backtest.config import HOLDING_PERIODS
from backtest.snapshot import _normalize_ts

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_price_at_offset(
    price_df: pd.DataFrame,
    from_date: pd.Timestamp,
    trading_days_offset: int,
) -> Optional[float]:
    """Return the closing price *trading_days_offset* trading days after *from_date*.

    Returns None if the required date is beyond available data.
    """
    if price_df.empty:
        return None

    norm_from   = _normalize_ts(from_date)
    idx_norm    = price_df.index.map(_normalize_ts)
    future_mask = idx_norm > norm_from
    future_rows = price_df[future_mask]

    if len(future_rows) < trading_days_offset:
        return None

    return float(future_rows["Close"].iloc[trading_days_offset - 1])


def _max_drawdown_window(
    price_df: pd.DataFrame,
    from_date: pd.Timestamp,
    trading_days: int,
    entry_price: float,
) -> Optional[float]:
    """Compute the maximum intra-period drawdown from *entry_price*.

    Returns the worst trough as a negative percentage (e.g. -8.3 means -8.3%).
    Returns None if data is unavailable.
    """
    if price_df.empty or entry_price <= 0:
        return None

    norm_from   = _normalize_ts(from_date)
    idx_norm    = price_df.index.map(_normalize_ts)
    future_mask = idx_norm > norm_from
    window      = price_df[future_mask].iloc[:trading_days]

    if window.empty:
        return None

    closes  = window["Close"].values
    lows    = window["Low"].values if "Low" in window.columns else closes
    min_low = float(lows.min())
    dd      = (min_low - entry_price) / entry_price * 100
    return round(dd, 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def attach_outcomes(
    signals: list[dict],
    prices: dict[str, pd.DataFrame],
) -> list[dict]:
    """Fill forward-return fields for every signal record in-place.

    Args:
        signals: List of signal dicts produced by runner.run_backtest().
        prices:  Price dict from data_loader (includes SPY, QQQ, and all stocks).

    Returns:
        The same list with outcome columns filled where data is available.
        Signals whose holding period extends beyond available data remain None.
    """
    spy_df = prices.get("SPY", pd.DataFrame())
    qqq_df = prices.get("QQQ", pd.DataFrame())

    resolved     = 0
    unresolved   = 0

    for sig in signals:
        ticker       = sig["ticker"]
        horizon      = sig["horizon"]
        signal_date  = pd.Timestamp(sig["date"])
        holding_days = HOLDING_PERIODS.get(horizon, 20)

        price_df    = prices.get(ticker, pd.DataFrame())
        entry_price = sig.get("price")

        if entry_price is None or price_df.empty:
            unresolved += 1
            continue

        # Forward prices
        exit_price = _get_price_at_offset(price_df, signal_date, holding_days)
        spy_entry  = _get_price_at_offset(spy_df,   signal_date - pd.Timedelta(days=1), 1)
        spy_exit   = _get_price_at_offset(spy_df,   signal_date, holding_days)
        qqq_entry  = _get_price_at_offset(qqq_df,   signal_date - pd.Timedelta(days=1), 1)
        qqq_exit   = _get_price_at_offset(qqq_df,   signal_date, holding_days)

        # Forward return (stock)
        if exit_price is not None:
            sig["forward_return"] = round(
                (exit_price - entry_price) / entry_price * 100, 4
            )
            resolved += 1
        else:
            sig["forward_return"] = None
            unresolved += 1

        # SPY benchmark return
        if spy_entry is not None and spy_exit is not None:
            spy_ret = (spy_exit - spy_entry) / spy_entry * 100
            sig["spy_return"] = round(spy_ret, 4)
            if sig["forward_return"] is not None:
                sig["excess_return"] = round(sig["forward_return"] - spy_ret, 4)
        else:
            sig["spy_return"]   = None
            sig["excess_return"] = None

        # QQQ benchmark return
        if qqq_entry is not None and qqq_exit is not None:
            qqq_ret = (qqq_exit - qqq_entry) / qqq_entry * 100
            sig["qqq_return"] = round(qqq_ret, 4)
            if sig["forward_return"] is not None:
                sig["excess_return_vs_qqq"] = round(sig["forward_return"] - qqq_ret, 4)
        else:
            sig["qqq_return"]          = None
            sig["excess_return_vs_qqq"] = None

        # Max drawdown during the holding period
        sig["max_drawdown_period"] = _max_drawdown_window(
            price_df, signal_date, holding_days, entry_price
        )

    logger.info(
        "Outcomes attached: %d resolved, %d unresolved (future or missing data)",
        resolved, unresolved,
    )
    return signals
