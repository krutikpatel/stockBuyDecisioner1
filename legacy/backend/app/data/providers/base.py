"""
Abstract base class for market data providers.

All concrete providers (yfinance, polygon, etc.) must implement these methods.
The interface is intentionally narrow — add methods here only when a second
provider needs to implement them.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.news import NewsItem


class MarketDataProvider(ABC):
    """Abstract interface for fetching market data.

    All returned DataFrames use a DatetimeIndex (UTC-naive) and contain at
    minimum a ``Close`` column.  OHLCV columns are included when available.
    """

    # ---------------------------------------------------------------- identity

    @property
    def name(self) -> str:
        """Human-readable provider name (e.g. "yfinance")."""
        return type(self).__name__

    @property
    def supports_point_in_time_fundamentals(self) -> bool:
        """True if the provider can return fundamentals as-of a historical date."""
        return False

    # --------------------------------------------------------- price / history

    @abstractmethod
    def get_price_history(
        self,
        ticker: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Return OHLCV price history between start and end (ISO date strings).

        Returns an empty DataFrame if data is unavailable.
        """

    @abstractmethod
    def get_benchmark_history(
        self,
        ticker: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Return daily OHLCV for a benchmark (SPY, QQQ, sector ETF, etc.)."""

    # ----------------------------------------------------------- fundamentals

    @abstractmethod
    def get_fundamentals(self, ticker: str) -> FundamentalData:
        """Return the most recent fundamental snapshot for ticker."""

    @abstractmethod
    def get_valuation(
        self,
        ticker: str,
        market_cap: Optional[float] = None,
    ) -> ValuationData:
        """Return the most recent valuation snapshot for ticker."""

    # ------------------------------------------------------------- other data

    @abstractmethod
    def get_earnings(self, ticker: str) -> EarningsData:
        """Return the earnings calendar / surprise history for ticker."""

    @abstractmethod
    def get_news(self, ticker: str, limit: int = 20) -> list[NewsItem]:
        """Return recent news items for ticker."""

    @abstractmethod
    def get_company_profile(self, ticker: str) -> dict:
        """Return raw company info dict (sector, industry, market cap, etc.)."""
