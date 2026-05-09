"""
Builds time-sliced analysis inputs for a given (ticker, test_date).

All data is strictly filtered to information available on or before test_date,
ensuring zero look-ahead bias.

Phase-gate behaviour:
  phase=1 or 2 : technical + regime only; fundamentals are neutral placeholders
  phase=3       : adds time-sliced fundamentals constructed from quarterly filings
                  with a 45-trading-day filing lag
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.models.fundamentals import FundamentalData, ValuationData, StockArchetype
from app.models.earnings import EarningsData, EarningsRecord
from app.models.news import NewsSummary
from backtest.config import SECTOR_ETF_MAP, MIN_ROWS_FOR_ANALYSIS

logger = logging.getLogger(__name__)

# Approximate quarterly filing lag in calendar days (10-K: 60–90 days; 10-Q: 40 days)
FILING_LAG_DAYS: int = 45


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        return f if f == f else None  # filter NaN
    except (TypeError, ValueError):
        return None


def _normalize_ts(ts) -> pd.Timestamp:
    """Strip timezone from a timestamp for consistent comparison."""
    t = pd.Timestamp(ts)
    if t.tz is not None:
        t = t.tz_localize(None)
    return t


def _filter_stmt_cols(stmt: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Keep only columns (quarter end-dates) filed on or before *cutoff*."""
    if stmt is None or stmt.empty:
        return pd.DataFrame()
    keep = [c for c in stmt.columns if _normalize_ts(c) <= cutoff]
    return stmt[keep] if keep else pd.DataFrame()


def _stmt_row(stmt: pd.DataFrame, *labels: str) -> Optional[pd.Series]:
    """Return the first matching row from a financial statement DataFrame."""
    for lbl in labels:
        if lbl in stmt.index:
            return stmt.loc[lbl]
    return None


def _ttm(row: Optional[pd.Series], n: int = 4) -> Optional[float]:
    """Sum the most recent *n* quarterly values (trailing-twelve-months)."""
    if row is None or row.empty:
        return None
    try:
        vals = [float(v) for v in row.iloc[:n] if pd.notna(v)]
        return sum(vals) if vals else None
    except Exception:
        return None


def _latest(row: Optional[pd.Series]) -> Optional[float]:
    """Return the most recent non-null value from a quarterly row."""
    if row is None or row.empty:
        return None
    for v in row.iloc:
        f = _safe_float(v)
        if f is not None:
            return f
    return None


# ---------------------------------------------------------------------------
# Price slicing
# ---------------------------------------------------------------------------

def get_price_slice(price_df: pd.DataFrame, test_date: pd.Timestamp) -> pd.DataFrame:
    """Return price rows up to and including *test_date* (tz-naive safe).

    Uses searchsorted (O(log N)) instead of index.map (O(N)) for speed.
    Assumes price_df.index is already tz-naive (enforced by data_loader).
    """
    if price_df.empty:
        return pd.DataFrame()
    norm_date = _normalize_ts(test_date)
    pos = price_df.index.searchsorted(norm_date, side="right")
    return price_df.iloc[:pos]


# ---------------------------------------------------------------------------
# Neutral / placeholder data (Phase 1–2)
# ---------------------------------------------------------------------------

def neutral_news() -> NewsSummary:
    """Neutral news summary used when historical news is unavailable."""
    return NewsSummary(
        items=[],
        news_score=50.0,
        coverage_limited=True,
        positive_count=0,
        negative_count=0,
        neutral_count=0,
    )


def neutral_fundamentals() -> FundamentalData:
    """Placeholder fundamentals for Phase 1–2 (technical-only backtest)."""
    return FundamentalData(
        fundamental_score=50.0,
        archetype=StockArchetype.MATURE_VALUE,
    )


def neutral_valuation() -> ValuationData:
    """Placeholder valuation for Phase 1–2."""
    return ValuationData(
        valuation_score=50.0,
        archetype_adjusted_score=50.0,
        peer_comparison_available=False,
    )


def neutral_earnings() -> EarningsData:
    """Placeholder earnings for Phase 1–2."""
    return EarningsData(
        earnings_score=50.0,
        history=[],
        beat_count=0,
        miss_count=0,
    )


# ---------------------------------------------------------------------------
# Phase 3: time-sliced fundamental snapshot
# ---------------------------------------------------------------------------

def build_historical_fundamentals(
    ticker: str,
    test_date: pd.Timestamp,
    quarterly_data: dict,
    price_at_date: float,
) -> tuple[FundamentalData, ValuationData, EarningsData]:
    """Build FundamentalData, ValuationData, and EarningsData from historical
    quarterly filings available as of *test_date* minus the filing lag.

    Args:
        ticker: Stock symbol (used only for logging).
        test_date: The simulated "today" date.
        quarterly_data: Pre-fetched dict with keys:
            income_stmt, balance_sheet, cashflow,
            earnings_history, earnings_dates, info_snapshot.
        price_at_date: Closing price on test_date (for valuation ratios).

    Returns:
        (FundamentalData, ValuationData, EarningsData)
    """
    cutoff = test_date - pd.Timedelta(days=FILING_LAG_DAYS)

    income   = _filter_stmt_cols(quarterly_data.get("income_stmt",   pd.DataFrame()), cutoff)
    balance  = _filter_stmt_cols(quarterly_data.get("balance_sheet",  pd.DataFrame()), cutoff)
    cashflow = _filter_stmt_cols(quarterly_data.get("cashflow",       pd.DataFrame()), cutoff)
    eh_raw   = quarterly_data.get("earnings_history", pd.DataFrame())
    ed_raw   = quarterly_data.get("earnings_dates",   pd.DataFrame())
    info     = quarterly_data.get("info_snapshot",    {})

    # ── Income statement ───────────────────────────────────────────────────
    rev_row = _stmt_row(income, "Total Revenue", "Revenue")
    gp_row  = _stmt_row(income, "Gross Profit")
    oi_row  = _stmt_row(income, "Operating Income", "EBIT")
    ni_row  = _stmt_row(income, "Net Income")
    eps_row = _stmt_row(income, "Diluted EPS", "Basic EPS")

    revenue_ttm            = _ttm(rev_row)
    gross_profit_ttm       = _ttm(gp_row)
    operating_income_ttm   = _ttm(oi_row)
    net_income_ttm         = _ttm(ni_row)
    eps_ttm                = _ttm(eps_row)

    gross_margin:     Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin:       Optional[float] = None
    if revenue_ttm and revenue_ttm != 0:
        if gross_profit_ttm is not None:
            gross_margin = round(gross_profit_ttm / revenue_ttm, 4)
        if operating_income_ttm is not None:
            operating_margin = round(operating_income_ttm / revenue_ttm, 4)
        if net_income_ttm is not None:
            net_margin = round(net_income_ttm / revenue_ttm, 4)

    # YoY revenue growth
    revenue_growth_yoy: Optional[float] = None
    if rev_row is not None and len(rev_row) >= 5:
        try:
            r0 = _ttm(rev_row, 4)
            r1 = _ttm(rev_row.iloc[4:8], 4)
            if r0 and r1 and r1 != 0:
                revenue_growth_yoy = round((r0 - r1) / abs(r1), 4)
        except Exception:
            pass
    if revenue_growth_yoy is None:
        revenue_growth_yoy = _safe_float(info.get("revenueGrowth"))

    # ── Cash flow ──────────────────────────────────────────────────────────
    fcf_row   = _stmt_row(cashflow, "Free Cash Flow")
    ocf_row   = _stmt_row(cashflow, "Operating Cash Flow",
                          "Cash Flow From Continuing Operating Activities")
    capex_row = _stmt_row(cashflow, "Capital Expenditure", "Capital Expenditures")

    free_cash_flow: Optional[float] = None
    if fcf_row is not None:
        free_cash_flow = _ttm(fcf_row)
    elif ocf_row is not None and capex_row is not None:
        ocf   = _ttm(ocf_row)
        capex = _ttm(capex_row)
        if ocf is not None and capex is not None:
            free_cash_flow = ocf + capex  # capex is typically negative

    fcf_margin: Optional[float] = None
    if free_cash_flow is not None and revenue_ttm and revenue_ttm != 0:
        fcf_margin = round(free_cash_flow / revenue_ttm, 4)

    # ── Balance sheet ──────────────────────────────────────────────────────
    cash_row        = _stmt_row(balance, "Cash And Cash Equivalents", "Cash", "Cash Financial")
    debt_row        = _stmt_row(balance, "Total Debt", "Long Term Debt")
    curr_assets_row = _stmt_row(balance, "Current Assets", "Total Current Assets")
    curr_liab_row   = _stmt_row(balance, "Current Liabilities", "Total Current Liabilities")
    equity_row      = _stmt_row(balance, "Stockholders Equity",
                                "Total Equity Gross Minority Interest")
    shares_row      = _stmt_row(balance, "Share Issued", "Ordinary Shares Number")

    cash       = _latest(cash_row)
    total_debt = _latest(debt_row)
    net_debt: Optional[float] = None
    if total_debt is not None and cash is not None:
        net_debt = round(total_debt - cash, 2)

    current_ratio: Optional[float] = None
    ca = _latest(curr_assets_row)
    cl = _latest(curr_liab_row)
    if ca and cl and cl != 0:
        current_ratio = round(ca / cl, 4)

    equity = _latest(equity_row)
    debt_to_equity: Optional[float] = None
    if total_debt is not None and equity and equity != 0:
        debt_to_equity = round(total_debt / equity, 4)

    shares = _latest(shares_row) or _safe_float(info.get("sharesOutstanding"))

    roe: Optional[float] = None
    if net_income_ttm is not None and equity and equity != 0:
        roe = round(net_income_ttm / equity, 4)

    fundamentals = FundamentalData(
        revenue_ttm=revenue_ttm,
        revenue_growth_yoy=revenue_growth_yoy,
        revenue_growth_qoq=None,
        eps_ttm=eps_ttm,
        eps_growth_yoy=_safe_float(info.get("earningsGrowth")),
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
        roic=None,
    )

    # ── Valuation ──────────────────────────────────────────────────────────
    market_cap = (shares * price_at_date) if shares else None

    trailing_pe: Optional[float] = None
    if eps_ttm and eps_ttm != 0 and price_at_date:
        trailing_pe = round(price_at_date / eps_ttm, 2)

    price_to_sales: Optional[float] = None
    if market_cap and revenue_ttm and revenue_ttm != 0:
        price_to_sales = round(market_cap / revenue_ttm, 4)

    price_to_fcf: Optional[float] = None
    fcf_yield_val: Optional[float] = None
    if market_cap and free_cash_flow and free_cash_flow > 0:
        price_to_fcf  = round(market_cap / free_cash_flow, 2)
        fcf_yield_val = round(free_cash_flow / market_cap * 100, 4)

    ev_to_ebitda = _safe_float(info.get("enterpriseToEbitda"))  # current snapshot (limitation)

    peg_ratio: Optional[float] = None
    eps_growth = _safe_float(info.get("earningsGrowth"))
    if trailing_pe is not None and eps_growth and eps_growth > 0:
        peg_ratio = round(trailing_pe / (eps_growth * 100), 4)

    valuation = ValuationData(
        trailing_pe=trailing_pe,
        forward_pe=None,
        peg_ratio=peg_ratio,
        price_to_sales=price_to_sales,
        ev_to_ebitda=ev_to_ebitda,
        price_to_fcf=price_to_fcf,
        fcf_yield=fcf_yield_val,
        peer_comparison_available=False,
    )

    # ── Earnings history ───────────────────────────────────────────────────
    history: list[EarningsRecord] = []
    beat_count    = 0
    miss_count    = 0
    surprise_pcts: list[float] = []

    if not eh_raw.empty:
        for _, row in eh_raw.iterrows():
            try:
                row_date = _normalize_ts(row.name) if hasattr(row, "name") else None
                if row_date is not None and row_date > test_date:
                    continue  # future earnings → skip

                surp     = _safe_float(row.get("surprisePercent"))
                eps_est  = _safe_float(row.get("epsEstimate"))
                eps_act  = _safe_float(row.get("epsActual"))

                if surp is not None:
                    surprise_pcts.append(surp)
                    if surp >= 0:
                        beat_count += 1
                    else:
                        miss_count += 1

                history.append(EarningsRecord(
                    date=str(row_date) if row_date is not None else None,
                    eps_estimate=eps_est,
                    eps_actual=eps_act,
                    eps_surprise_pct=surp,
                ))
            except Exception:
                continue

    avg_surprise = round(sum(surprise_pcts) / len(surprise_pcts), 2) if surprise_pcts else None
    beat_rate    = (
        round(beat_count / (beat_count + miss_count), 4)
        if (beat_count + miss_count) > 0 else None
    )

    # Earnings dates (past + next)
    last_date: Optional[str] = None
    next_date: Optional[str] = None
    within_30 = False

    if not ed_raw.empty:
        try:
            idx_norm   = ed_raw.index.map(_normalize_ts)
            past_mask  = idx_norm <= test_date
            future_mask = idx_norm > test_date

            past_dates   = idx_norm[past_mask]
            future_dates = idx_norm[future_mask]

            if len(past_dates) > 0:
                last_date = str(past_dates[0])
            if len(future_dates) > 0:
                next_dt   = future_dates[-1]
                next_date = str(next_dt)
                within_30 = 0 <= (next_dt - test_date).days <= 30
        except Exception as exc:
            logger.debug("earnings_dates processing failed: %s", exc)

    # Earnings score
    earnings_score_val = 50.0
    if beat_rate is not None:
        if beat_rate >= 0.80:
            earnings_score_val += 20
        elif beat_rate >= 0.60:
            earnings_score_val += 10
        elif beat_rate < 0.40:
            earnings_score_val -= 15
    if avg_surprise is not None:
        if avg_surprise >= 5:
            earnings_score_val += 15
        elif avg_surprise >= 2:
            earnings_score_val += 8
        elif avg_surprise < 0:
            earnings_score_val -= 15
    if within_30:
        earnings_score_val -= 10
    earnings_score_val = round(max(0.0, min(100.0, earnings_score_val)), 2)

    earnings = EarningsData(
        last_earnings_date=last_date,
        next_earnings_date=next_date,
        history=history[:8],
        avg_eps_surprise_pct=avg_surprise,
        beat_count=beat_count,
        miss_count=miss_count,
        beat_rate=beat_rate,
        within_30_days=within_30,
        earnings_score=earnings_score_val,
    )

    return fundamentals, valuation, earnings
