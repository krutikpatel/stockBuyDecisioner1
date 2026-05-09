"""
Pre-computes and disk-caches TechnicalIndicators (ticker-only fields) for all
(ticker, test_date) pairs.

RS fields that depend on benchmark DataFrames (spy/qqq/sector) are left as
None in the cache and computed inline by runner._attach_rs_fields after lookup.
technical_score in cached objects is a placeholder (computed with rs_spy=None)
and is always overwritten by _attach_rs_fields before use.

Cache file : backtest/cache/indicators.pkl
Cache format: dict[ticker_str, dict[date_iso_str, TechnicalIndicators]]
              e.g. cache["AAPL"]["2022-01-03"] → TechnicalIndicators(...)

Invalidation:
  - Auto-rebuild if indicators.pkl is missing.
  - Auto-rebuild if prices.pkl is newer than indicators.pkl (price data changed).
  - Force-rebuild if force_refresh=True (e.g. --force-refresh CLI flag).
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

import pandas as pd

from app.models.market import TechnicalIndicators
from app.services.technical_analysis_service import compute_technicals
from backtest.config import CACHE_DIR, MIN_ROWS_FOR_ANALYSIS
from backtest.snapshot import get_price_slice

logger = logging.getLogger(__name__)

INDICATOR_CACHE_PATH: Path = Path(CACHE_DIR) / "indicators.pkl"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_stale() -> bool:
    """Return True if the indicator cache needs to be rebuilt.

    Rebuilds when:
    - indicators.pkl does not exist, OR
    - prices.pkl is newer than indicators.pkl (underlying data changed).
    """
    if not INDICATOR_CACHE_PATH.exists():
        return True
    prices_path = Path(CACHE_DIR) / "prices.pkl"
    if not prices_path.exists():
        return False
    return prices_path.stat().st_mtime > INDICATOR_CACHE_PATH.stat().st_mtime


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_indicator_cache(
    prices: dict[str, pd.DataFrame],
    tickers: list[str],
    test_dates: list[pd.Timestamp],
    force_refresh: bool = False,
) -> dict[str, dict[str, TechnicalIndicators]]:
    """Load indicator cache from disk, or build and save it if missing/stale.

    For each (ticker, test_date) pair, calls compute_technicals with no
    benchmark args (spy/qqq/sector).  RS fields remain None; technical_score
    is a placeholder.  Both are corrected at lookup time by _attach_rs_fields.

    Args:
        prices:        Price dict from data_loader (tz-naive DatetimeIndex).
        tickers:       List of stock tickers to process.
        test_dates:    Ordered list of weekly Monday timestamps.
        force_refresh: Ignore on-disk cache and rebuild from scratch.

    Returns:
        Nested dict: cache[ticker][date_iso] -> TechnicalIndicators.
    """
    if not force_refresh and not _is_stale():
        logger.info("Loading indicator cache from %s…", INDICATOR_CACHE_PATH)
        with open(INDICATOR_CACHE_PATH, "rb") as f:
            cache = pickle.load(f)
        total_entries = sum(len(v) for v in cache.values())
        logger.info(
            "Indicator cache loaded: %d tickers, %d entries",
            len(cache), total_entries,
        )
        return cache

    logger.info(
        "Building indicator cache for %d tickers × %d dates…",
        len(tickers), len(test_dates),
    )
    print(
        f"\nBuilding indicator cache: {len(tickers)} tickers × "
        f"{len(test_dates)} dates = {len(tickers) * len(test_dates)} snapshots"
    )

    cache: dict[str, dict[str, TechnicalIndicators]] = {}
    total = len(tickers) * len(test_dates)
    done = 0

    for ticker_idx, ticker in enumerate(tickers, 1):
        price_full = prices.get(ticker, pd.DataFrame())
        if price_full.empty:
            done += len(test_dates)
            continue

        per_date: dict[str, TechnicalIndicators] = {}

        for test_date in test_dates:
            done += 1
            if done % 500 == 0 or done == total:
                pct = done / total * 100
                print(
                    f"  [{ticker_idx}/{len(tickers)}] {ticker} — "
                    f"{done}/{total} ({pct:.0f}%)          ",
                    end="\r", flush=True,
                )

            price_slice = get_price_slice(price_full, test_date)
            if len(price_slice) < MIN_ROWS_FOR_ANALYSIS:
                continue

            try:
                # No spy/qqq/sector → RS fields stay None; technical_score is placeholder
                ti = compute_technicals(price_slice)
                per_date[test_date.date().isoformat()] = ti
            except Exception as exc:
                logger.debug(
                    "indicator_cache: failed for %s %s: %s",
                    ticker, test_date.date(), exc,
                )

        cache[ticker] = per_date

    total_entries = sum(len(v) for v in cache.values())
    print(f"\nIndicator cache built: {len(cache)} tickers, {total_entries} entries.")

    INDICATOR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDICATOR_CACHE_PATH, "wb") as f:
        pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Indicator cache saved to %s", INDICATOR_CACHE_PATH)

    return cache


def lookup_ticker_indicators(
    cache: dict[str, dict[str, TechnicalIndicators]],
    ticker: str,
    test_date: pd.Timestamp,
) -> Optional[TechnicalIndicators]:
    """Return the cached TechnicalIndicators for (ticker, test_date), or None.

    A None return means the caller should fall back to full compute_technicals.
    """
    per_date = cache.get(ticker)
    if per_date is None:
        return None
    return per_date.get(test_date.date().isoformat())
