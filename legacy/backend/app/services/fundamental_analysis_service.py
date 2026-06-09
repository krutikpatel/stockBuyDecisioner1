from __future__ import annotations

from typing import Optional

from app.models.fundamentals import FundamentalData


def score_fundamentals(data: FundamentalData) -> float:
    """
    Score 0–100 based on §9 rules from projectPlan.md.
    Starts at 50, adjusts for positive and negative signals.
    """
    score = 50.0

    # Revenue growth YoY (±15)
    rg = data.revenue_growth_yoy
    if rg is not None:
        if rg >= 0.20:
            score += 15
        elif rg >= 0.10:
            score += 8
        elif rg >= 0.05:
            score += 3
        elif rg < 0:
            score -= 15
        # 0–5%: neutral

    # Revenue growth QoQ (±5 bonus / penalty)
    rg_q = data.revenue_growth_qoq
    if rg_q is not None:
        if rg_q >= 0.05:
            score += 5
        elif rg_q < 0:
            score -= 5

    # EPS growth (±10)
    eg = data.eps_growth_yoy
    if eg is not None:
        if eg >= 0.20:
            score += 10
        elif eg >= 0.10:
            score += 5
        elif eg < 0:
            score -= 10

    # Gross margin (±5)
    gm = data.gross_margin
    if gm is not None:
        if gm >= 0.50:
            score += 5
        elif gm >= 0.30:
            score += 2
        elif gm < 0.10:
            score -= 5

    # Operating margin (±5)
    om = data.operating_margin
    if om is not None:
        if om >= 0.20:
            score += 5
        elif om >= 0.10:
            score += 2
        elif om < 0:
            score -= 5

    # Free cash flow (±10)
    fcf = data.free_cash_flow
    if fcf is not None:
        if fcf > 0:
            score += 10
        else:
            score -= 10

    # Free cash flow margin (±5 bonus)
    fcf_m = data.free_cash_flow_margin
    if fcf_m is not None:
        if fcf_m >= 0.15:
            score += 5
        elif fcf_m < 0:
            score -= 5

    # Debt: net_debt relative to FCF or total_debt vs cash (±5)
    nd = data.net_debt
    cash = data.cash
    if nd is not None and cash is not None:
        if nd < 0:  # net cash position
            score += 5
        elif cash and nd > cash * 2:  # high leverage
            score -= 5

    # Debt-to-equity (±5)
    dte = data.debt_to_equity
    if dte is not None:
        if dte < 0.5:
            score += 5
        elif dte > 2.0:
            score -= 5

    # ROE (±5)
    roe = data.roe
    if roe is not None:
        if roe >= 0.20:
            score += 5
        elif roe < 0:
            score -= 5

    return round(max(0.0, min(100.0, score)), 2)
