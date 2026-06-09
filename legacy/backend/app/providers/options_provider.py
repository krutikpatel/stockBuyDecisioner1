from __future__ import annotations

import logging
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)


class OptionsSnapshot:
    def __init__(self):
        self.implied_volatility: Optional[float] = None
        self.put_call_ratio: Optional[float] = None
        self.total_call_volume: Optional[float] = None
        self.total_put_volume: Optional[float] = None
        self.total_call_oi: Optional[float] = None
        self.total_put_oi: Optional[float] = None
        self.nearest_expiry: Optional[str] = None
        self.available: bool = False


def get_options_snapshot(ticker: str) -> OptionsSnapshot:
    snap = OptionsSnapshot()
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return snap

        nearest = expirations[0]
        snap.nearest_expiry = nearest
        chain = t.option_chain(nearest)

        calls = chain.calls
        puts = chain.puts

        if calls is not None and not calls.empty:
            call_vol = float(calls["volume"].fillna(0).sum())
            call_oi = float(calls["openInterest"].fillna(0).sum())
            avg_iv = calls["impliedVolatility"].dropna().mean()
            snap.total_call_volume = call_vol
            snap.total_call_oi = call_oi
            if avg_iv == avg_iv:  # NaN check
                snap.implied_volatility = round(float(avg_iv) * 100, 2)  # as %

        if puts is not None and not puts.empty:
            put_vol = float(puts["volume"].fillna(0).sum())
            put_oi = float(puts["openInterest"].fillna(0).sum())
            snap.total_put_volume = put_vol
            snap.total_put_oi = put_oi

        call_vol_val = snap.total_call_volume or 0
        put_vol_val = snap.total_put_volume or 0
        if call_vol_val > 0:
            snap.put_call_ratio = round(put_vol_val / call_vol_val, 4)

        snap.available = True
    except Exception as e:
        logger.warning("Options data unavailable for %s: %s", ticker, e)

    return snap
