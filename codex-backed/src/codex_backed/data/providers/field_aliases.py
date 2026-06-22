from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

# ---------------------------------------------------------------------------
# FMP → canonical field mapping
# Each value is an ordered list of FMP JSON keys to try; the first one present
# in the API response payload is used.
# ---------------------------------------------------------------------------

_FMP_ALIASES_RAW: dict[str, list[str]] = {
    # Income / growth
    "sales_growth_yoy": ["revenueGrowth", "revenue_growth"],
    "eps_growth_yoy": ["epsgrowth", "epsGrowth"],
    "eps_growth_next_year": ["epsGrowthNextYear"],
    "eps_growth_3y": ["threeYEarningsGrowthPerShare", "eps3YGrowth"],
    "eps_growth_5y": ["fiveYEarningsGrowthPerShare", "eps5YGrowth"],
    # Margins
    "gross_margin": ["grossProfitMargin", "grossProfit"],
    "operating_margin": ["operatingProfitMargin", "operatingIncomeRatio"],
    "net_margin": ["netProfitMargin", "netIncomeRatio"],
    # Returns / liquidity
    "free_cash_flow": ["freeCashFlow"],
    "roic": ["returnOnCapitalEmployed", "roic"],
    "roe": ["returnOnEquity", "roe"],
    "roa": ["returnOnAssets", "roa"],
    "debt_to_equity": ["debtEquityRatio", "totalDebtToEquity"],
    "current_ratio": ["currentRatio"],
    # Valuation
    "trailing_pe": ["peRatio", "priceEarningsRatio"],
    "peg_ratio": ["priceEarningsToGrowthRatio", "pegRatio"],
    "price_to_sales": ["priceToSalesRatio", "priceSalesRatio"],
    "ev_to_ebitda": ["enterpriseValueMultiple", "evToEbitda"],
    "price_to_fcf": ["priceToFreeCashFlowsRatio", "priceToFCF"],
    # Earnings calendar
    "earnings_days_away": ["_computed_earnings_days_away"],
    "earnings_within_30_days": ["_computed_earnings_within_30_days"],
    "avg_eps_surprise_pct": ["avgEpsSurprisePct"],
    "beat_rate": ["beatRate"],
    # Company profile
    "market_cap": ["mktCap", "marketCap"],
    "beta": ["beta"],
    "sector": ["sector"],
    "industry": ["industry"],
    "analyst_recommendation": ["ratingScore", "analystRating"],
    "analyst_target_price": ["priceTarget"],
}

FMP_ALIASES: Mapping[str, list[str]] = MappingProxyType(_FMP_ALIASES_RAW)

# Fields that FMP can actually supply at the standard API tier
FMP_SUPPORTED_FIELDS: frozenset[str] = frozenset(FMP_ALIASES.keys())

# ---------------------------------------------------------------------------
# YFinance → canonical field mapping
# ---------------------------------------------------------------------------

_YFINANCE_ALIASES_RAW: dict[str, list[str]] = {
    # Ownership / float (primary FMP gap — these live in yfinance .info)
    "insider_ownership": ["heldPercentInsiders"],
    "institutional_ownership": ["heldPercentInstitutions"],
    "short_float": ["shortPercentOfFloat"],
    # Valuation (yfinance exposes these too — used as supplementary)
    "trailing_pe": ["trailingPE"],
    "forward_pe": ["forwardPE"],
    "peg_ratio": ["pegRatio"],
    "price_to_sales": ["priceToSalesTrailing12Months"],
    # Dividend
    "dividend_yield": ["dividendYield"],
    # Company info
    "market_cap": ["marketCap"],
    "beta": ["beta"],
    "sector": ["sector"],
    "industry": ["industry"],
    "analyst_recommendation": ["recommendationMean"],
    "analyst_target_price": ["targetMeanPrice"],
}

YFINANCE_ALIASES: Mapping[str, list[str]] = MappingProxyType(_YFINANCE_ALIASES_RAW)

YFINANCE_SUPPORTED_FIELDS: frozenset[str] = frozenset(YFINANCE_ALIASES.keys())
