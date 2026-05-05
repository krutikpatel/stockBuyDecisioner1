from __future__ import annotations

from typing import Optional

from app.models.fundamentals import ValuationData


def score_valuation(data: ValuationData) -> float:
    """
    Score 0–100 per §10 rules from projectPlan.md.
    Attractive valuation = higher score.
    """
    score = 50.0

    # Forward P/E (±20)
    fpe = data.forward_pe
    if fpe is not None:
        if fpe <= 15:
            score += 20
        elif fpe <= 20:
            score += 10
        elif fpe <= 30:
            score += 0
        elif fpe <= 40:
            score -= 10
        else:
            score -= 20

    # PEG ratio (±15)
    peg = data.peg_ratio
    if peg is not None:
        if peg <= 1.0:
            score += 15
        elif peg <= 1.5:
            score += 8
        elif peg <= 2.0:
            score += 0
        elif peg <= 3.0:
            score -= 10
        else:
            score -= 15

    # Price-to-sales (±10)
    ps = data.price_to_sales
    if ps is not None:
        if ps <= 2:
            score += 10
        elif ps <= 5:
            score += 5
        elif ps <= 10:
            score += 0
        elif ps <= 20:
            score -= 5
        else:
            score -= 10

    # EV/EBITDA (±10)
    ev = data.ev_to_ebitda
    if ev is not None:
        if ev <= 10:
            score += 10
        elif ev <= 15:
            score += 5
        elif ev <= 25:
            score += 0
        elif ev <= 40:
            score -= 5
        else:
            score -= 10

    # FCF yield (±10)
    fcf_yield = data.fcf_yield
    if fcf_yield is not None:
        if fcf_yield >= 5:
            score += 10
        elif fcf_yield >= 2:
            score += 5
        elif fcf_yield < 0:
            score -= 10

    # Trailing P/E sanity (±5)
    tpe = data.trailing_pe
    if tpe is not None:
        if tpe <= 20:
            score += 5
        elif tpe > 60:
            score -= 5

    return round(max(0.0, min(100.0, score)), 2)
