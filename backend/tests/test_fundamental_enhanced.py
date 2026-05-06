"""
Story 4 TDD tests: Enhanced Fundamental Data Provider
Tests written BEFORE implementation using mocked yfinance data.

New fields covered:
FundamentalData:
  eps_growth_next_year, eps_growth_ttm, eps_growth_3y, eps_growth_5y,
  eps_growth_next_5y, sales_growth_ttm, sales_growth_3y, sales_growth_5y,
  roa, quick_ratio, long_term_debt_equity, insider_ownership,
  insider_transactions, institutional_ownership, institutional_transactions,
  short_float, short_ratio, analyst_recommendation, analyst_target_price,
  target_price_distance, shares_float, dividend_yield

ValuationData:
  ev_sales, price_to_book, price_to_cash
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models.fundamentals import FundamentalData, ValuationData


# ---------------------------------------------------------------------------
# Helpers: mock ticker.info dicts
# ---------------------------------------------------------------------------

def _full_info(overrides: dict | None = None) -> dict:
    """Return a comprehensive mock yfinance ticker.info dict."""
    base = {
        # Existing fields
        "totalRevenue": 100_000_000,
        "revenueGrowth": 0.20,
        "trailingEps": 5.0,
        "earningsGrowth": 0.15,
        "grossMargins": 0.60,
        "operatingMargins": 0.25,
        "profitMargins": 0.20,
        "freeCashflow": 15_000_000,
        "totalCash": 20_000_000,
        "totalDebt": 10_000_000,
        "currentRatio": 2.5,
        "debtToEquity": 40.0,
        "sharesOutstanding": 10_000_000,
        "returnOnEquity": 0.18,
        "returnOnAssets": 0.10,
        "sector": "Technology",
        "beta": 1.2,
        # New fields
        "earningsQuarterlyGrowth": 0.12,          # eps_growth_next_year proxy
        "pegRatio": 1.5,
        "trailingPE": 30.0,
        "forwardPE": 25.0,
        "priceToSalesTrailing12Months": 5.0,
        "enterpriseToEbitda": 18.0,
        "enterpriseValue": 500_000_000,
        "marketCap": 300_000_000,
        "quickRatio": 1.8,
        "longTermDebt": 8_000_000,
        "totalStockholderEquity": 50_000_000,
        "heldPercentInsiders": 0.05,
        "heldPercentInstitutions": 0.72,
        "netSharePurchaseActivity": 0.02,
        "insiderTransactions": 500_000,
        "shortPercentOfFloat": 0.04,
        "shortRatio": 3.2,
        "recommendationMean": 2.1,
        "targetMeanPrice": 180.0,
        "currentPrice": 150.0,
        "floatShares": 9_000_000,
        "firstTradeDateEpochUtc": 1_000_000_000,
        "dividendYield": 0.015,
        "priceToBook": 8.5,
        "totalAssets": 80_000_000,
        "netIncomeToCommon": 8_000_000,
    }
    if overrides:
        base.update(overrides)
    return base


def _mock_ticker(info: dict, quarterly_income=None, annual_income=None):
    """Return a mock yfinance Ticker with controllable data."""
    t = MagicMock()
    t.info = info

    if quarterly_income is not None:
        t.quarterly_income_stmt = quarterly_income
    else:
        import pandas as pd
        import numpy as np
        cols = pd.date_range("2023-01-01", periods=5, freq="QE")
        t.quarterly_income_stmt = pd.DataFrame(
            {
                c: {
                    "Total Revenue": 100_000_000 + i * 5_000_000,
                    "Net Income": 8_000_000 + i * 500_000,
                }
                for i, c in enumerate(cols)
            }
        )

    if annual_income is not None:
        t.income_stmt = annual_income
    else:
        import pandas as pd
        cols = pd.date_range("2020-01-01", periods=5, freq="YE")
        t.income_stmt = pd.DataFrame(
            {
                c: {
                    "Total Revenue": 60_000_000 + i * 10_000_000,
                    "Net Income": 5_000_000 + i * 1_000_000,
                }
                for i, c in enumerate(cols)
            }
        )

    return t


# ---------------------------------------------------------------------------
# FundamentalData model: new fields exist
# ---------------------------------------------------------------------------

class TestFundamentalDataModelFields:
    """Verify new fields are declared on FundamentalData."""

    def test_eps_growth_next_year_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "eps_growth_next_year")
        assert fd.eps_growth_next_year is None

    def test_eps_growth_ttm_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "eps_growth_ttm")

    def test_eps_growth_3y_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "eps_growth_3y")

    def test_eps_growth_5y_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "eps_growth_5y")

    def test_eps_growth_next_5y_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "eps_growth_next_5y")

    def test_sales_growth_ttm_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "sales_growth_ttm")

    def test_sales_growth_3y_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "sales_growth_3y")

    def test_sales_growth_5y_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "sales_growth_5y")

    def test_roa_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "roa")

    def test_quick_ratio_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "quick_ratio")

    def test_long_term_debt_equity_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "long_term_debt_equity")

    def test_insider_ownership_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "insider_ownership")

    def test_insider_transactions_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "insider_transactions")

    def test_institutional_ownership_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "institutional_ownership")

    def test_institutional_transactions_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "institutional_transactions")

    def test_short_float_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "short_float")

    def test_short_ratio_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "short_ratio")

    def test_analyst_recommendation_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "analyst_recommendation")

    def test_analyst_target_price_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "analyst_target_price")

    def test_target_price_distance_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "target_price_distance")

    def test_shares_float_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "shares_float")

    def test_dividend_yield_field(self):
        fd = FundamentalData()
        assert hasattr(fd, "dividend_yield")


# ---------------------------------------------------------------------------
# ValuationData model: new fields
# ---------------------------------------------------------------------------

class TestValuationDataModelFields:
    def test_ev_sales_field(self):
        vd = ValuationData()
        assert hasattr(vd, "ev_sales")
        assert vd.ev_sales is None

    def test_price_to_book_field(self):
        vd = ValuationData()
        assert hasattr(vd, "price_to_book")

    def test_price_to_cash_field(self):
        vd = ValuationData()
        assert hasattr(vd, "price_to_cash")


# ---------------------------------------------------------------------------
# get_fundamental_data: new fields populated correctly
# ---------------------------------------------------------------------------

class TestGetFundamentalDataNewFields:
    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_quick_ratio_populated(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.quick_ratio == pytest.approx(1.8, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_insider_ownership_populated(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.insider_ownership == pytest.approx(0.05, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_institutional_ownership_populated(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.institutional_ownership == pytest.approx(0.72, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_short_float_populated(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.short_float == pytest.approx(0.04, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_analyst_recommendation_populated(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.analyst_recommendation == pytest.approx(2.1, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_analyst_target_price_populated(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.analyst_target_price == pytest.approx(180.0, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_target_price_distance_calculated(self, mock_yf, mock_info):
        info = _full_info({"currentPrice": 150.0, "targetMeanPrice": 180.0})
        mock_info.return_value = info
        mock_yf.return_value = _mock_ticker(info)

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        # (180 - 150) / 150 * 100 = 20%
        assert result.target_price_distance == pytest.approx(20.0, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_roa_from_info(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.roa is not None
        assert isinstance(result.roa, float)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_dividend_yield_populated(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.dividend_yield == pytest.approx(0.015, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_shares_float_populated(self, mock_yf, mock_info):
        mock_info.return_value = _full_info()
        mock_yf.return_value = _mock_ticker(_full_info())

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.shares_float == pytest.approx(9_000_000, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_missing_fields_return_none(self, mock_yf, mock_info):
        """Fields absent from ticker.info must return None without exception."""
        sparse_info = {
            "totalRevenue": 100_000_000,
            "sector": "Technology",
        }
        mock_info.return_value = sparse_info
        mock_yf.return_value = _mock_ticker(sparse_info)

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.quick_ratio is None
        assert result.insider_ownership is None
        assert result.short_float is None
        assert result.analyst_recommendation is None
        assert result.target_price_distance is None

    @patch("app.providers.fundamental_provider.get_ticker_info")
    @patch("app.providers.fundamental_provider.yf.Ticker")
    def test_sales_growth_ttm_computed(self, mock_yf, mock_info):
        """sales_growth_ttm derived from quarterly income statement."""
        import pandas as pd
        info = _full_info()
        mock_info.return_value = info
        # Two years of quarterly data: q0..q3 = TTM, q4..q7 = prior TTM
        cols = pd.date_range("2022-01-01", periods=8, freq="QE")
        quarterly = pd.DataFrame(
            {c: {"Total Revenue": 20_000_000 + i * 2_000_000} for i, c in enumerate(cols)}
        )
        t = _mock_ticker(info, quarterly_income=quarterly)
        mock_yf.return_value = t

        from app.providers.fundamental_provider import get_fundamental_data
        result = get_fundamental_data("AAPL")
        assert result.sales_growth_ttm is not None
        # TTM (cols 0-3): 20M+22M+24M+26M = 92M; Prior TTM (cols 4-7): 28+30+32+34 = 124M
        # growth = (92 - 124) / 124 ≈ -0.258  → negative
        # (columns ordered newest-first so actual computation depends on implementation)
        assert isinstance(result.sales_growth_ttm, float)


# ---------------------------------------------------------------------------
# get_valuation_data: new fields
# ---------------------------------------------------------------------------

class TestGetValuationDataNewFields:
    @patch("app.providers.fundamental_provider.get_ticker_info")
    def test_ev_sales_calculated(self, mock_info):
        info = _full_info({"enterpriseValue": 500_000_000, "totalRevenue": 100_000_000})
        mock_info.return_value = info

        from app.providers.fundamental_provider import get_valuation_data
        result = get_valuation_data("AAPL")
        # 500M / 100M = 5.0
        assert result.ev_sales == pytest.approx(5.0, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    def test_ev_sales_none_when_revenue_zero(self, mock_info):
        info = _full_info({"enterpriseValue": 500_000_000, "totalRevenue": 0})
        mock_info.return_value = info

        from app.providers.fundamental_provider import get_valuation_data
        result = get_valuation_data("AAPL")
        assert result.ev_sales is None

    @patch("app.providers.fundamental_provider.get_ticker_info")
    def test_price_to_book_populated(self, mock_info):
        info = _full_info({"priceToBook": 8.5})
        mock_info.return_value = info

        from app.providers.fundamental_provider import get_valuation_data
        result = get_valuation_data("AAPL")
        assert result.price_to_book == pytest.approx(8.5, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    def test_price_to_cash_calculated(self, mock_info):
        # price_to_cash = price / (totalCash / sharesOutstanding)
        info = _full_info({
            "currentPrice": 150.0,
            "totalCash": 30_000_000,
            "sharesOutstanding": 10_000_000,
        })
        mock_info.return_value = info

        from app.providers.fundamental_provider import get_valuation_data
        result = get_valuation_data("AAPL")
        # cash per share = 30M / 10M = 3.0; price_to_cash = 150 / 3 = 50
        assert result.price_to_cash == pytest.approx(50.0, rel=0.01)

    @patch("app.providers.fundamental_provider.get_ticker_info")
    def test_price_to_cash_none_when_no_cash(self, mock_info):
        info = _full_info({"totalCash": None, "currentPrice": 150.0})
        mock_info.return_value = info

        from app.providers.fundamental_provider import get_valuation_data
        result = get_valuation_data("AAPL")
        assert result.price_to_cash is None

    @patch("app.providers.fundamental_provider.get_ticker_info")
    def test_missing_fields_return_none_gracefully(self, mock_info):
        mock_info.return_value = {"trailingPE": 25.0}

        from app.providers.fundamental_provider import get_valuation_data
        result = get_valuation_data("AAPL")
        assert result.ev_sales is None
        assert result.price_to_book is None
        assert result.price_to_cash is None
