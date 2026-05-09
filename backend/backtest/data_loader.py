"""
Pre-fetches and disk-caches all historical data needed for backtesting.
Run once before backtesting; subsequent runs reload from cache.

Cache layout (under CACHE_DIR):
  prices.pkl      — dict[ticker, DataFrame]   (OHLCV, tz-naive DatetimeIndex)
  quarterly.pkl   — dict[ticker, dict]         (income_stmt, balance_sheet, …)
"""
from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtest.config import (
    BACKTEST_TICKERS,
    BENCHMARK_TICKERS,
    SECTOR_ETF_MAP,
    HISTORY_START,
    BACKTEST_END,
    CACHE_DIR,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_price_indices(prices: dict) -> None:
    """Strip timezone from all price DataFrame indices in-place.

    Ensures all DataFrames have a tz-naive DatetimeIndex so that
    searchsorted works correctly without per-row _normalize_ts calls.
    """
    for ticker, df in list(prices.items()):
        if not df.empty and getattr(df.index, "tz", None) is not None:
            new_df = df.copy()
            new_df.index = df.index.tz_localize(None)
            prices[ticker] = new_df

def _cache_path(name: str) -> Path:
    path = Path(CACHE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path / name


def _fetch_price_history(ticker: str) -> pd.DataFrame:
    """Fetch full daily OHLCV history for a single ticker."""
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
            logger.warning("No price data returned for %s", ticker)
            return pd.DataFrame()

        # Flatten MultiIndex columns that yfinance sometimes returns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        # Normalise index to tz-naive for consistent slicing
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        return df
    except Exception as exc:
        logger.error("Failed to fetch price history for %s: %s", ticker, exc)
        return pd.DataFrame()


def _fetch_quarterly_data(ticker: str) -> dict:
    """Fetch quarterly financial statements and earnings data for one ticker."""
    logger.info("Fetching quarterly data: %s", ticker)
    result: dict = {
        "income_stmt":     pd.DataFrame(),
        "balance_sheet":   pd.DataFrame(),
        "cashflow":        pd.DataFrame(),
        "earnings_history": pd.DataFrame(),
        "earnings_dates":  pd.DataFrame(),
        "info_snapshot":   {},
    }
    try:
        t = yf.Ticker(ticker)

        for attr, key in [
            ("quarterly_income_stmt",  "income_stmt"),
            ("quarterly_balance_sheet", "balance_sheet"),
            ("quarterly_cashflow",     "cashflow"),
            ("earnings_history",       "earnings_history"),
            ("earnings_dates",         "earnings_dates"),
        ]:
            try:
                data = getattr(t, attr, None)
                if data is not None and not data.empty:
                    result[key] = data
            except Exception as exc:
                logger.warning("%s failed for %s: %s", attr, ticker, exc)

        try:
            result["info_snapshot"] = t.info or {}
        except Exception as exc:
            logger.warning("ticker.info failed for %s: %s", ticker, exc)

    except Exception as exc:
        logger.error("Failed to fetch quarterly data for %s: %s", ticker, exc)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_all_data(
    force_refresh: bool = False,
    extra_tickers: list[str] | None = None,
) -> dict:
    """Load all backtest data (price + quarterly fundamentals).

    On first run, or when *force_refresh=True*, fetches from yfinance and
    writes to pickle cache files.  Subsequent runs load from cache.

    Args:
        force_refresh: Re-download everything even if cache exists.
        extra_tickers: Additional stock tickers beyond BACKTEST_TICKERS.

    Returns:
        {
          "prices":    {ticker: pd.DataFrame},   # OHLCV
          "quarterly": {ticker: dict},            # fundamentals
        }
    """
    prices_cache   = _cache_path("prices.pkl")
    quarterly_cache = _cache_path("quarterly.pkl")

    if not force_refresh and prices_cache.exists() and quarterly_cache.exists():
        logger.info("Loading data from cache (%s)…", CACHE_DIR)
        with open(prices_cache, "rb") as f:
            prices = pickle.load(f)
        with open(quarterly_cache, "rb") as f:
            quarterly = pickle.load(f)
        _normalize_price_indices(prices)
        logger.info(
            "Cache loaded: %d price series, %d quarterly datasets",
            len(prices), len(quarterly),
        )
        return {"prices": prices, "quarterly": quarterly}

    # ── Determine tickers to fetch ─────────────────────────────────────────
    extra = set(extra_tickers or [])
    stock_tickers = set(BACKTEST_TICKERS) | extra

    # Price tickers: stocks + benchmarks + unique sector ETFs
    all_price_tickers: set[str] = stock_tickers | set(BENCHMARK_TICKERS)
    for etf in SECTOR_ETF_MAP.values():
        if etf:
            all_price_tickers.add(etf)

    # Quarterly data only for individual stocks (not ETFs/benchmarks)
    all_fundamental_tickers = sorted(stock_tickers)

    # ── Fetch prices ───────────────────────────────────────────────────────
    prices: dict[str, pd.DataFrame] = {}
    sorted_price_tickers = sorted(all_price_tickers)
    print(f"\nFetching price history for {len(sorted_price_tickers)} tickers…")
    for i, ticker in enumerate(sorted_price_tickers, 1):
        print(f"  [{i}/{len(sorted_price_tickers)}] {ticker}          ", end="\r", flush=True)
        prices[ticker] = _fetch_price_history(ticker)
        time.sleep(0.3)  # polite rate-limit
    print()  # newline after progress

    # ── Fetch fundamentals ─────────────────────────────────────────────────
    quarterly: dict[str, dict] = {}
    print(f"Fetching quarterly fundamentals for {len(all_fundamental_tickers)} tickers…")
    for i, ticker in enumerate(all_fundamental_tickers, 1):
        print(f"  [{i}/{len(all_fundamental_tickers)}] {ticker}          ", end="\r", flush=True)
        quarterly[ticker] = _fetch_quarterly_data(ticker)
        time.sleep(0.5)
    print()

    # ── Normalise indices before caching and returning ─────────────────────
    _normalize_price_indices(prices)

    # ── Persist cache ──────────────────────────────────────────────────────
    print("Saving to cache…")
    with open(prices_cache, "wb") as f:
        pickle.dump(prices, f)
    with open(quarterly_cache, "wb") as f:
        pickle.dump(quarterly, f)

    logger.info(
        "Data cached: %d price series, %d quarterly datasets",
        len(prices), len(quarterly),
    )
    return {"prices": prices, "quarterly": quarterly}
