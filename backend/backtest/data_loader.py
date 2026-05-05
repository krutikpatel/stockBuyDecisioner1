"""
Pre-fetches and disk-caches all historical data needed for backtesting.
Run once before backtesting; subsequent runs reload from cache.
"""
from __future__ import annotations

import os
import pickle
import time
import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtest.config import (
    BACKTEST_TICKERS,
    SECTOR_ETF_MAP,
    HISTORY_START,
    BACKTEST_END,
    CACHE_DIR,
)

logger = logging.getLogger(__name__)


def _cache_path(name: str) -> Path:
    path = Path(CACHE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path / name


def _fetch_price_history(ticker: str) -> pd.DataFrame:
    """Fetch full daily OHLCV history for a ticker."""
    logger.info("Fetching price history: %s", ticker)
    try:
        df = yf.download(
            ticker,
            start=HISTORY_START,
            end=BACKTEST_END,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if df.empty:
            logger.warning("No price data for %s", ticker)
            return pd.DataFrame()

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        # Normalize index to tz-naive for consistent slicing
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        return df
    except Exception as e:
        logger.error("Failed to fetch price history for %s: %s", ticker, e)
        return pd.DataFrame()


def _fetch_quarterly_data(ticker: str) -> dict:
    """Fetch quarterly financial statements and earnings history."""
    logger.info("Fetching quarterly data: %s", ticker)
    result = {
        "income_stmt": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "earnings_history": pd.DataFrame(),
        "earnings_dates": pd.DataFrame(),
        "info_snapshot": {},
    }
    try:
        t = yf.Ticker(ticker)

        try:
            stmt = t.quarterly_income_stmt
            if stmt is not None and not stmt.empty:
                result["income_stmt"] = stmt
        except Exception as e:
            logger.warning("quarterly_income_stmt failed for %s: %s", ticker, e)

        try:
            bs = t.quarterly_balance_sheet
            if bs is not None and not bs.empty:
                result["balance_sheet"] = bs
        except Exception as e:
            logger.warning("quarterly_balance_sheet failed for %s: %s", ticker, e)

        try:
            cf = t.quarterly_cashflow
            if cf is not None and not cf.empty:
                result["cashflow"] = cf
        except Exception as e:
            logger.warning("quarterly_cashflow failed for %s: %s", ticker, e)

        try:
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                result["earnings_history"] = eh
        except Exception as e:
            logger.warning("earnings_history failed for %s: %s", ticker, e)

        try:
            ed = t.earnings_dates
            if ed is not None and not ed.empty:
                result["earnings_dates"] = ed
        except Exception as e:
            logger.warning("earnings_dates failed for %s: %s", ticker, e)

        try:
            result["info_snapshot"] = t.info or {}
        except Exception as e:
            logger.warning("ticker.info failed for %s: %s", ticker, e)

    except Exception as e:
        logger.error("Failed to fetch quarterly data for %s: %s", ticker, e)

    return result


def load_all_data(force_refresh: bool = False, extra_tickers: list[str] | None = None) -> dict:
    """
    Load all backtest data. Fetches from yfinance on first run,
    then reads from parquet/pickle cache on subsequent runs.

    Returns:
        {
          "prices": {ticker: pd.DataFrame},
          "quarterly": {ticker: dict},
        }
    """
    prices_cache = _cache_path("prices.pkl")
    quarterly_cache = _cache_path("quarterly.pkl")

    if not force_refresh and prices_cache.exists() and quarterly_cache.exists():
        logger.info("Loading data from cache...")
        with open(prices_cache, "rb") as f:
            prices = pickle.load(f)
        with open(quarterly_cache, "rb") as f:
            quarterly = pickle.load(f)
        logger.info("Cache loaded: %d price series, %d quarterly datasets", len(prices), len(quarterly))
        return {"prices": prices, "quarterly": quarterly}

    # Collect all tickers needed (stocks + SPY + all sector ETFs + any extras)
    all_price_tickers = set(BACKTEST_TICKERS) | {"SPY"}
    for etf in SECTOR_ETF_MAP.values():
        if etf:
            all_price_tickers.add(etf)
    extra = set(extra_tickers or [])
    all_price_tickers |= extra

    # Tickers that need quarterly fundamental data
    all_fundamental_tickers = list(set(BACKTEST_TICKERS) | extra)

    prices: dict[str, pd.DataFrame] = {}
    quarterly: dict[str, dict] = {}

    print(f"\nFetching price history for {len(all_price_tickers)} tickers...")
    for i, ticker in enumerate(sorted(all_price_tickers), 1):
        print(f"  [{i}/{len(all_price_tickers)}] {ticker}", end="\r", flush=True)
        prices[ticker] = _fetch_price_history(ticker)
        time.sleep(0.3)  # polite rate limit

    print(f"\nFetching quarterly fundamentals for {len(all_fundamental_tickers)} tickers...")
    for i, ticker in enumerate(all_fundamental_tickers, 1):
        print(f"  [{i}/{len(all_fundamental_tickers)}] {ticker}", end="\r", flush=True)
        quarterly[ticker] = _fetch_quarterly_data(ticker)
        time.sleep(0.5)

    print("\nSaving to cache...")
    with open(prices_cache, "wb") as f:
        pickle.dump(prices, f)
    with open(quarterly_cache, "wb") as f:
        pickle.dump(quarterly, f)

    logger.info("Data cached: %d price series, %d quarterly datasets", len(prices), len(quarterly))
    return {"prices": prices, "quarterly": quarterly}
