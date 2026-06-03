"""
Persistent parquet-based cache for backtest data.

Layout:
  data/cache/raw/{provider}/{data_type}/{ticker}_{interval}_{start}_{end}.parquet

Each parquet file has a companion ``.meta.json`` written by cache_metadata.py.

This cache is parallel to the existing pickle-based TTLCache — it writes
parquet files for long-term reuse in backtest runs while leaving the live
API's in-memory cache untouched.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from app.data.cache.cache_metadata import (
    CacheMetadata,
    load_metadata,
    make_metadata,
    save_metadata,
)

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "cache" / "raw"
SCHEMA_VERSION = 1


class ParquetCacheStore:
    """Reads and writes parquet files with companion metadata JSON.

    Usage:
        store = ParquetCacheStore()
        if store.has_coverage("AAPL", "yfinance", "price", "1d", "2022-01-01", "2023-01-01"):
            df = store.read("AAPL", "yfinance", "price", "1d", "2022-01-01", "2023-01-01")
        else:
            df = fetch_from_provider(...)
            store.write(df, "AAPL", "yfinance", "price", "1d", "2022-01-01", "2023-01-01")
    """

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        self._root = Path(cache_dir or _DEFAULT_CACHE_DIR)
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ public

    def has_coverage(
        self,
        ticker: str,
        provider: str,
        data_type: str,
        interval: str,
        start: str,
        end: str,
    ) -> bool:
        """True if a valid parquet file exists covering [start, end]."""
        path = self._path(ticker, provider, data_type, interval, start, end)
        if not path.exists():
            return False
        meta = load_metadata(path)
        if meta is None or meta.schema_version != SCHEMA_VERSION:
            return False
        return True

    def read(
        self,
        ticker: str,
        provider: str,
        data_type: str,
        interval: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Read a cached DataFrame. Caller must check has_coverage() first."""
        path = self._path(ticker, provider, data_type, interval, start, end)
        df = pd.read_parquet(path)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        logger.debug("Cache HIT: %s", path.name)
        return df

    def write(
        self,
        df: pd.DataFrame,
        ticker: str,
        provider: str,
        data_type: str,
        interval: str,
        start: str,
        end: str,
        adjusted_prices: bool = True,
    ) -> Path:
        """Write df to a parquet file and save companion metadata.

        Returns the path of the written parquet file.
        """
        path = self._path(ticker, provider, data_type, interval, start, end)
        path.parent.mkdir(parents=True, exist_ok=True)

        df_to_write = df.copy()
        if df_to_write.index.tz is not None:
            df_to_write.index = df_to_write.index.tz_localize(None)

        df_to_write.to_parquet(path, engine="pyarrow", compression="snappy")

        meta = make_metadata(
            ticker=ticker,
            provider=provider,
            data_type=data_type,
            interval=interval,
            start=start,
            end=end,
            row_count=len(df_to_write),
            columns=list(df_to_write.columns),
            adjusted_prices=adjusted_prices,
            schema_version=SCHEMA_VERSION,
        )
        save_metadata(path, meta)
        logger.debug("Cache WRITE: %s (%d rows)", path.name, len(df_to_write))
        return path

    def get_missing_ranges(
        self,
        ticker: str,
        provider: str,
        data_type: str,
        interval: str,
        requested_start: str,
        requested_end: str,
    ) -> list[tuple[str, str]]:
        """Return (start, end) gaps in the cache for the requested range.

        Currently uses a simple single-shard model: either the exact shard
        exists or the entire range is returned as missing.
        """
        if self.has_coverage(
            ticker, provider, data_type, interval, requested_start, requested_end
        ):
            return []
        return [(requested_start, requested_end)]

    def metadata(
        self,
        ticker: str,
        provider: str,
        data_type: str,
        interval: str,
        start: str,
        end: str,
    ) -> Optional[CacheMetadata]:
        """Return metadata for a shard, or None if it doesn't exist."""
        path = self._path(ticker, provider, data_type, interval, start, end)
        return load_metadata(path)

    # ----------------------------------------------------------------- private

    def _path(
        self,
        ticker: str,
        provider: str,
        data_type: str,
        interval: str,
        start: str,
        end: str,
    ) -> Path:
        filename = f"{ticker}_{interval}_{start}_{end}.parquet"
        return self._root / provider / data_type / filename
