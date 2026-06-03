"""
YFinance implementation of MarketDataProvider.

Wraps the existing functions in ``app/providers/`` without duplicating logic.
All caching and retry logic remains inside the wrapped functions.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from app.data.providers.base import MarketDataProvider
from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.news import NewsItem

logger = logging.getLogger(__name__)


class YFinanceProvider(MarketDataProvider):
    """Delegates to the existing ``app/providers/`` functions."""

    @property
    def name(self) -> str:
        return "yfinance"

    # --------------------------------------------------------- price / history

    def get_price_history(
        self,
        ticker: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Download price history using yfinance via the existing provider."""
        try:
            import yfinance as yf
            df = yf.download(
                ticker,
                start=start,
                end=end,
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            return df
        except Exception as exc:
            logger.warning("get_price_history(%s) failed: %s", ticker, exc)
            return pd.DataFrame()

    def get_benchmark_history(
        self,
        ticker: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        return self.get_price_history(ticker, start, end)

    # ----------------------------------------------------------- fundamentals

    def get_fundamentals(self, ticker: str) -> FundamentalData:
        from app.providers.fundamental_provider import get_fundamental_data
        return get_fundamental_data(ticker)

    def get_valuation(
        self,
        ticker: str,
        market_cap: Optional[float] = None,
    ) -> ValuationData:
        from app.providers.fundamental_provider import get_valuation_data
        return get_valuation_data(ticker, market_cap=market_cap)

    # ------------------------------------------------------------- other data

    def get_earnings(self, ticker: str) -> EarningsData:
        from app.providers.earnings_provider import get_earnings_data
        return get_earnings_data(ticker)

    def get_news(self, ticker: str, limit: int = 20) -> list[NewsItem]:
        from app.providers.news_provider import get_news_items
        return get_news_items(ticker, limit=limit)

    def get_company_profile(self, ticker: str) -> dict:
        from app.providers.market_data_provider import get_ticker_info
        return get_ticker_info(ticker)
