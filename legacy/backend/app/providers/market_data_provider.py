from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import yfinance as yf
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.cache.cache_manager import (
    fundamental_cache_key,
    get_cached,
    get_fundamental_cache,
    get_price_cache,
    price_cache_key,
    set_cached,
)
from app.models.market import MarketData

logger = logging.getLogger(__name__)

_SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Utilities": "XLU",
}


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _download_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No price data returned for {ticker}")
    return df


def get_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    key = price_cache_key(ticker, period, interval)
    cached = get_cached(get_price_cache(), key)
    if cached is not None:
        return cached
    df = _download_history(ticker, period, interval)
    # Flatten MultiIndex columns that yfinance sometimes returns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    set_cached(get_price_cache(), key, df)
    return df


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _fetch_info(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info
    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        raise ValueError(f"No info returned for {ticker}")
    return info


def get_ticker_info(ticker: str) -> dict:
    key = fundamental_cache_key(ticker)
    cached = get_cached(get_fundamental_cache(), key)
    if cached is not None:
        return cached
    info = _fetch_info(ticker)
    set_cached(get_fundamental_cache(), key, info)
    return info


def get_market_data(ticker: str) -> MarketData:
    info = get_ticker_info(ticker)
    hist_1y = get_history(ticker, "1y", "1d")
    hist_3m = get_history(ticker, "3mo", "1d")
    hist_6m = get_history(ticker, "6mo", "1d")
    hist_ytd = get_history(ticker, "ytd", "1d")

    current_price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or float(hist_1y["Close"].iloc[-1])
    )

    def _period_return(df: pd.DataFrame) -> Optional[float]:
        if df.empty or len(df) < 2:
            return None
        start = float(df["Close"].iloc[0])
        end = float(df["Close"].iloc[-1])
        return round((end - start) / start * 100, 2) if start else None

    avg_vol_30d = float(hist_1y["Volume"].tail(30).mean()) if len(hist_1y) >= 30 else float(hist_1y["Volume"].mean())

    return MarketData(
        ticker=ticker.upper(),
        current_price=round(float(current_price), 4),
        previous_close=round(float(info.get("previousClose", 0) or hist_1y["Close"].iloc[-2]), 4),
        open=round(float(info.get("open", 0) or hist_1y["Open"].iloc[-1]), 4),
        day_high=round(float(info.get("dayHigh", 0) or hist_1y["High"].iloc[-1]), 4),
        day_low=round(float(info.get("dayLow", 0) or hist_1y["Low"].iloc[-1]), 4),
        volume=float(info.get("volume", 0) or hist_1y["Volume"].iloc[-1]),
        avg_volume_30d=avg_vol_30d,
        market_cap=info.get("marketCap"),
        week_52_high=info.get("fiftyTwoWeekHigh"),
        week_52_low=info.get("fiftyTwoWeekLow"),
        beta=info.get("beta"),
        return_1m=_period_return(get_history(ticker, "1mo", "1d")),
        return_3m=_period_return(hist_3m),
        return_6m=_period_return(hist_6m),
        return_1y=_period_return(hist_1y),
        return_ytd=_period_return(hist_ytd),
    )


def get_sector_etf(ticker: str) -> Optional[str]:
    try:
        info = get_ticker_info(ticker)
        sector = info.get("sector", "")
        return _SECTOR_ETF_MAP.get(sector)
    except Exception:
        return None
