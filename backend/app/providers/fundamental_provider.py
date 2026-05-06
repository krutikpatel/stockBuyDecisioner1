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


def get_fundamental_data(ticker: str) -> FundamentalData:
    info = get_ticker_info(ticker)

    revenue_ttm = _safe_float(info.get("totalRevenue"))
    revenue_growth_yoy = _safe_float(info.get("revenueGrowth"))  # decimal e.g. 0.12

    # QoQ revenue growth — attempt from quarterly financials
    revenue_growth_qoq: Optional[float] = None
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
    except Exception:
        pass

    eps_ttm = _safe_float(info.get("trailingEps"))
    eps_growth_yoy = _safe_float(info.get("earningsGrowth"))

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

    return ValuationData(
        trailing_pe=trailing_pe,
        forward_pe=forward_pe,
        peg_ratio=peg_ratio,
        price_to_sales=price_to_sales,
        ev_to_ebitda=ev_to_ebitda,
        price_to_fcf=price_to_fcf,
        fcf_yield=fcf_yield,
        peer_comparison_available=False,
    )
