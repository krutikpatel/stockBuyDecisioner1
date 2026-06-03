"""
Attaches forward returns to each signal record.

For every signal, looks up the closing price N trading days after the signal date
and computes:
  - forward_return       : % price change over the holding period
  - spy_return           : SPY % change over the same period
  - qqq_return           : QQQ % change over the same period
  - excess_return        : forward_return - spy_return
  - excess_return_vs_qqq : forward_return - qqq_return
  - max_drawdown_period  : worst intra-period trough from entry price (MAE proxy)
  - mfe_pct              : best intra-period peak from entry price (MFE)

Optional entry/exit method params activate simulation paths that write additional
`sim_` columns alongside the default columns (backward-compatible).
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

    Uses searchsorted (O(log N)) instead of index.map (O(N)).
    Returns None if the required date is beyond available data.
    """
    if price_df.empty:
        return None

    norm_from = _normalize_ts(from_date)
    pos = price_df.index.searchsorted(norm_from, side="right")
    future_rows = price_df.iloc[pos:]

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

    Uses searchsorted (O(log N)) instead of index.map (O(N)).
    Returns the worst trough as a negative percentage (e.g. -8.3 means -8.3%).
    Returns None if data is unavailable.
    """
    if price_df.empty or entry_price <= 0:
        return None

    norm_from = _normalize_ts(from_date)
    pos = price_df.index.searchsorted(norm_from, side="right")
    window = price_df.iloc[pos : pos + trading_days]

    if window.empty:
        return None

    closes  = window["Close"].values
    lows    = window["Low"].values if "Low" in window.columns else closes
    min_low = float(lows.min())
    dd      = (min_low - entry_price) / entry_price * 100
    return round(dd, 4)


def _max_favorable_window(
    price_df: pd.DataFrame,
    from_date: pd.Timestamp,
    trading_days: int,
    entry_price: float,
) -> Optional[float]:
    """Compute the maximum intra-period favorable excursion from *entry_price*.

    Returns the best peak as a positive percentage (e.g. 12.5 means +12.5%).
    Returns None if data is unavailable.
    """
    if price_df.empty or entry_price <= 0:
        return None

    norm_from = _normalize_ts(from_date)
    pos = price_df.index.searchsorted(norm_from, side="right")
    window = price_df.iloc[pos : pos + trading_days]

    if window.empty:
        return None

    closes   = window["Close"].values
    highs    = window["High"].values if "High" in window.columns else closes
    max_high = float(highs.max())
    mfe      = (max_high - entry_price) / entry_price * 100
    return round(mfe, 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def attach_outcomes(
    signals: list[dict],
    prices: dict[str, pd.DataFrame],
    entry_method: Optional[str] = None,
    exit_method: Optional[str] = None,
) -> list[dict]:
    """Fill forward-return fields for every signal record in-place.

    Args:
        signals:      List of signal dicts produced by runner.run_backtest().
        prices:       Price dict from data_loader (includes SPY, QQQ, and all stocks).
        entry_method: Optional entry simulation method (e.g. "NEXT_OPEN",
                      "PULLBACK_TO_SMA20").  When None, uses the signal's own
                      closing price as entry (current behavior, backward-compatible).
                      When specified, writes additional `sim_entry_*` columns.
        exit_method:  Optional exit simulation method (e.g. "ATR_STOP_TARGET",
                      "TRAILING_STOP").  When None, uses fixed-horizon exit
                      (current behavior, backward-compatible).
                      When specified, writes additional `sim_exit_*` columns.

    Returns:
        The same list with outcome columns filled where data is available.
        Signals whose holding period extends beyond available data remain None.
    """
    spy_df = prices.get("SPY", pd.DataFrame())
    qqq_df = prices.get("QQQ", pd.DataFrame())

    # Lazy-import simulators only when needed to avoid cost at import time
    entry_sim = None
    exit_sim  = None
    if entry_method is not None:
        from backtest.entry_simulator import EntrySimulator
        entry_sim = EntrySimulator()
    if exit_method is not None:
        from backtest.exit_simulator import ExitSimulator
        exit_sim = ExitSimulator()

    resolved   = 0
    unresolved = 0

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

        # Forward prices (default fixed-horizon)
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
            sig["spy_return"]    = None
            sig["excess_return"] = None

        # QQQ benchmark return
        if qqq_entry is not None and qqq_exit is not None:
            qqq_ret = (qqq_exit - qqq_entry) / qqq_entry * 100
            sig["qqq_return"] = round(qqq_ret, 4)
            if sig["forward_return"] is not None:
                sig["excess_return_vs_qqq"] = round(sig["forward_return"] - qqq_ret, 4)
        else:
            sig["qqq_return"]           = None
            sig["excess_return_vs_qqq"] = None

        # Max drawdown during the holding period (MAE proxy)
        sig["max_drawdown_period"] = _max_drawdown_window(
            price_df, signal_date, holding_days, entry_price
        )

        # MFE — maximum favorable excursion
        sig["mfe_pct"] = _max_favorable_window(
            price_df, signal_date, holding_days, entry_price
        )

        # ── Optional: simulated entry ──────────────────────────────────────
        if entry_sim is not None:
            er = entry_sim.simulate_entry(
                signal_date=signal_date,
                price_df=price_df,
                method=entry_method,
            )
            sig["sim_entry_price"]       = er.entry_price
            sig["sim_entry_date"]        = er.entry_date
            sig["sim_entry_wait_days"]   = er.wait_days
            sig["sim_entry_triggered"]   = not er.not_triggered

        # ── Optional: simulated exit ───────────────────────────────────────
        if exit_sim is not None:
            # Use simulated entry price/date if available, else default
            sim_ep    = sig.get("sim_entry_price") or entry_price
            sim_edate = pd.Timestamp(sig["sim_entry_date"]) if sig.get("sim_entry_date") else signal_date

            xr = exit_sim.simulate_exit(
                entry_date=sim_edate,
                entry_price=sim_ep,
                price_df=price_df,
                method=exit_method,
                horizon=horizon,
            )
            sig["sim_forward_return"] = xr.pnl_pct
            sig["sim_exit_date"]      = xr.exit_date
            sig["sim_exit_reason"]    = xr.exit_reason
            sig["sim_holding_days"]   = xr.holding_days
            sig["mae_pct"]            = xr.mae_pct
            sig["mfe_sim_pct"]        = xr.mfe_pct

    logger.info(
        "Outcomes attached: %d resolved, %d unresolved (future or missing data)",
        resolved, unresolved,
    )
    return signals
