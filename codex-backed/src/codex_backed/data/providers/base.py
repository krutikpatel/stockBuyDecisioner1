from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """Raised when a data provider cannot fulfil a request."""

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.capabilities import ProviderCapabilities


@runtime_checkable
class PriceProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    def fetch_history_batch(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[dict]]:
        """Return normalized OHLCV bars per ticker.  May omit tickers with no data."""
        ...

    def fetch_live_batch(
        self,
        tickers: list[str],
        period: str = "2y",
        interval: str = "1d",
    ) -> dict[str, list[dict]]:
        """Return the latest bars (including today's partial bar if intraday) per ticker."""
        ...


@runtime_checkable
class FundamentalsProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    def prefetch_batch(
        self,
        tickers: list[str],
        date_range: tuple[date, date],
    ) -> None:
        """Warm the in-memory cache.  Called ONCE per backtest, before workers fork.

        After this returns, get_snapshot must be O(1) and must not perform I/O.
        """
        ...

    def get_snapshot(
        self,
        ticker: str,
        as_of_date: date,
    ) -> FundamentalsSnapshot:
        """In-memory snapshot lookup.  Must not perform I/O.

        Returns an all-None snapshot if prefetch did not cover this (ticker, date).
        Never raises on missing data.
        """
        ...
