from __future__ import annotations

import logging
from typing import Optional

import yfinance as yf

from app.cache.cache_manager import (
    fundamental_cache_key,
    get_cached,
    get_fundamental_cache,
    set_cached,
)
from app.models.fundamentals import FundamentalData, ValuationData
from app.providers.market_data_provider import get_ticker_info

logger = logging.getLogger(__name__)


def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        return f if f == f else None  # NaN check
    except (TypeError, ValueError):
        return None


def _compute_cagr(series_oldest: float, series_newest: float, years: int) -> Optional[float]:
    """Compute CAGR from oldest to newest value over given years."""
    try:
        if series_oldest and series_oldest > 0 and years > 0:
            return round((series_newest / series_oldest) ** (1.0 / years) - 1, 4)
    except Exception:
        pass
    return None


def get_fundamental_data(ticker: str) -> FundamentalData:
    info = get_ticker_info(ticker)

    revenue_ttm = _safe_float(info.get("totalRevenue"))
    revenue_growth_yoy = _safe_float(info.get("revenueGrowth"))  # decimal e.g. 0.12

    # QoQ revenue growth and multi-period sales growth — from quarterly financials
    revenue_growth_qoq: Optional[float] = None
    sales_growth_ttm: Optional[float] = None
    sales_growth_3y: Optional[float] = None
    sales_growth_5y: Optional[float] = None
    eps_growth_3y: Optional[float] = None
    eps_growth_5y: Optional[float] = None
    try:
        t = yf.Ticker(ticker)
        q_income = t.quarterly_income_stmt
        if q_income is not None and not q_income.empty:
            rev_row = None
            for lbl in ("Total Revenue", "Revenue"):
                if lbl in q_income.index:
                    rev_row = q_income.loc[lbl]
                    break
            if rev_row is not None and len(rev_row) >= 2:
                r0 = float(rev_row.iloc[0])
                r1 = float(rev_row.iloc[1])
                if r1 and r1 != 0:
                    revenue_growth_qoq = round((r0 - r1) / abs(r1), 4)
            # TTM sales growth: sum newest 4 quarters vs sum prior 4 quarters
            if rev_row is not None and len(rev_row) >= 8:
                ttm_rev = sum(float(rev_row.iloc[i]) for i in range(4))
                prior_ttm_rev = sum(float(rev_row.iloc[i]) for i in range(4, 8))
                if prior_ttm_rev and prior_ttm_rev != 0:
                    sales_growth_ttm = round((ttm_rev - prior_ttm_rev) / abs(prior_ttm_rev), 4)

        # Annual income for multi-year growth rates
        a_income = t.income_stmt
        if a_income is not None and not a_income.empty:
            rev_a = None
            for lbl in ("Total Revenue", "Revenue"):
                if lbl in a_income.index:
                    rev_a = a_income.loc[lbl]
                    break
            ni_a = None
            for lbl in ("Net Income", "Net Income Common Stockholders"):
                if lbl in a_income.index:
                    ni_a = a_income.loc[lbl]
                    break

            if rev_a is not None:
                if len(rev_a) >= 4:
                    sales_growth_3y = _compute_cagr(
                        float(rev_a.iloc[3]), float(rev_a.iloc[0]), 3
                    )
                if len(rev_a) >= 6:
                    sales_growth_5y = _compute_cagr(
                        float(rev_a.iloc[5]), float(rev_a.iloc[0]), 5
                    )
            if ni_a is not None:
                if len(ni_a) >= 4:
                    eps_growth_3y = _compute_cagr(
                        float(ni_a.iloc[3]), float(ni_a.iloc[0]), 3
                    )
                if len(ni_a) >= 6:
                    eps_growth_5y = _compute_cagr(
                        float(ni_a.iloc[5]), float(ni_a.iloc[0]), 5
                    )
    except Exception:
        pass

    eps_ttm = _safe_float(info.get("trailingEps"))
    eps_growth_yoy = _safe_float(info.get("earningsGrowth"))
    eps_growth_next_year = _safe_float(info.get("earningsQuarterlyGrowth"))
    eps_growth_ttm = eps_growth_yoy  # same source; alias for clarity
    eps_growth_next_5y = _safe_float(info.get("earningsGrowth5yr"))  # analyst estimate, often None

    gross_margin = _safe_float(info.get("grossMargins"))
    operating_margin = _safe_float(info.get("operatingMargins"))
    net_margin = _safe_float(info.get("profitMargins"))

    free_cash_flow = _safe_float(info.get("freeCashflow"))
    fcf_margin: Optional[float] = None
    if free_cash_flow is not None and revenue_ttm and revenue_ttm != 0:
        fcf_margin = round(free_cash_flow / revenue_ttm, 4)

    cash = _safe_float(info.get("totalCash"))
    total_debt = _safe_float(info.get("totalDebt"))
    net_debt: Optional[float] = None
    if total_debt is not None and cash is not None:
        net_debt = round(total_debt - cash, 2)

    current_ratio = _safe_float(info.get("currentRatio"))
    debt_to_equity = _safe_float(info.get("debtToEquity"))
    shares = _safe_float(info.get("sharesOutstanding"))
    roe = _safe_float(info.get("returnOnEquity"))
    roic = _safe_float(info.get("returnOnAssets"))  # proxy; ROIC not directly available
    sector = info.get("sector") or None
    beta = _safe_float(info.get("beta"))

    # Story 4: new quality metrics
    roa = _safe_float(info.get("returnOnAssets"))
    quick_ratio = _safe_float(info.get("quickRatio"))
    long_term_debt = _safe_float(info.get("longTermDebt"))
    equity = _safe_float(info.get("totalStockholderEquity"))
    long_term_debt_equity: Optional[float] = None
    if long_term_debt is not None and equity and equity != 0:
        long_term_debt_equity = round(long_term_debt / equity, 4)

    # Story 4: ownership & sentiment
    insider_ownership = _safe_float(info.get("heldPercentInsiders"))
    insider_transactions = _safe_float(info.get("insiderTransactions"))
    institutional_ownership = _safe_float(info.get("heldPercentInstitutions"))
    institutional_transactions = _safe_float(info.get("netSharePurchaseActivity"))
    short_float = _safe_float(info.get("shortPercentOfFloat"))
    short_ratio = _safe_float(info.get("shortRatio"))
    analyst_recommendation = _safe_float(info.get("recommendationMean"))
    analyst_target_price = _safe_float(info.get("targetMeanPrice"))
    current_price = _safe_float(info.get("currentPrice"))
    target_price_distance: Optional[float] = None
    if analyst_target_price is not None and current_price and current_price != 0:
        target_price_distance = round((analyst_target_price - current_price) / current_price * 100, 4)
    shares_float = _safe_float(info.get("floatShares"))
    dividend_yield = _safe_float(info.get("dividendYield"))

    return FundamentalData(
        revenue_ttm=revenue_ttm,
        revenue_growth_yoy=revenue_growth_yoy,
        revenue_growth_qoq=revenue_growth_qoq,
        eps_ttm=eps_ttm,
        eps_growth_yoy=eps_growth_yoy,
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        net_margin=net_margin,
        free_cash_flow=free_cash_flow,
        free_cash_flow_margin=fcf_margin,
        cash=cash,
        total_debt=total_debt,
        net_debt=net_debt,
        current_ratio=current_ratio,
        debt_to_equity=debt_to_equity,
        shares_outstanding=shares,
        roe=roe,
        roic=roic,
        sector=sector,
        beta=beta,
        eps_growth_next_year=eps_growth_next_year,
        eps_growth_ttm=eps_growth_ttm,
        eps_growth_3y=eps_growth_3y,
        eps_growth_5y=eps_growth_5y,
        eps_growth_next_5y=eps_growth_next_5y,
        sales_growth_ttm=sales_growth_ttm,
        sales_growth_3y=sales_growth_3y,
        sales_growth_5y=sales_growth_5y,
        roa=roa,
        quick_ratio=quick_ratio,
        long_term_debt_equity=long_term_debt_equity,
        insider_ownership=insider_ownership,
        insider_transactions=insider_transactions,
        institutional_ownership=institutional_ownership,
        institutional_transactions=institutional_transactions,
        short_float=short_float,
        short_ratio=short_ratio,
        analyst_recommendation=analyst_recommendation,
        analyst_target_price=analyst_target_price,
        target_price_distance=target_price_distance,
        shares_float=shares_float,
        dividend_yield=dividend_yield,
    )


def get_valuation_data(ticker: str, market_cap: Optional[float] = None) -> ValuationData:
    info = get_ticker_info(ticker)

    trailing_pe = _safe_float(info.get("trailingPE"))
    forward_pe = _safe_float(info.get("forwardPE"))
    price_to_sales = _safe_float(info.get("priceToSalesTrailing12Months"))
    ev_to_ebitda = _safe_float(info.get("enterpriseToEbitda"))

    # PEG: forward P/E / eps growth rate
    peg_ratio = _safe_float(info.get("pegRatio"))
    if peg_ratio is None and forward_pe is not None:
        eps_growth = _safe_float(info.get("earningsGrowth"))
        if eps_growth and eps_growth > 0:
            peg_ratio = round(forward_pe / (eps_growth * 100), 4)

    # P/FCF: market cap / free cash flow
    price_to_fcf: Optional[float] = None
    fcf_yield: Optional[float] = None
    cap = market_cap or _safe_float(info.get("marketCap"))
    fcf = _safe_float(info.get("freeCashflow"))
    if cap and fcf and fcf > 0:
        price_to_fcf = round(cap / fcf, 2)
        fcf_yield = round(fcf / cap * 100, 4)

    # Story 4: EV/Sales
    ev_sales: Optional[float] = None
    ev = _safe_float(info.get("enterpriseValue"))
    rev = _safe_float(info.get("totalRevenue"))
    if ev is not None and rev and rev != 0:
        ev_sales = round(ev / rev, 4)

    # Story 4: Price/Book
    price_to_book = _safe_float(info.get("priceToBook"))

    # Story 4: Price/Cash = current_price / cash_per_share
    price_to_cash: Optional[float] = None
    current_price = _safe_float(info.get("currentPrice"))
    total_cash = _safe_float(info.get("totalCash"))
    shares = _safe_float(info.get("sharesOutstanding"))
    if current_price and total_cash and shares and shares != 0:
        cash_per_share = total_cash / shares
        if cash_per_share != 0:
            price_to_cash = round(current_price / cash_per_share, 4)

    return ValuationData(
        trailing_pe=trailing_pe,
        forward_pe=forward_pe,
        peg_ratio=peg_ratio,
        price_to_sales=price_to_sales,
        ev_to_ebitda=ev_to_ebitda,
        price_to_fcf=price_to_fcf,
        fcf_yield=fcf_yield,
        ev_sales=ev_sales,
        price_to_book=price_to_book,
        price_to_cash=price_to_cash,
        peer_comparison_available=False,
    )
