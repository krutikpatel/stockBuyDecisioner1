from __future__ import annotations

from typing import Optional

from app.models.fundamentals import StockArchetype, ValuationData


def score_valuation(data: ValuationData) -> float:
    """Score 0–100. Attractive valuation = higher score.

    This archetype-neutral version is kept for backward compatibility.
    Use score_valuation_with_archetype() for growth-adjusted scoring.
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


def score_valuation_with_archetype(
    data: ValuationData,
    archetype: str,
    revenue_growth_yoy: Optional[float] = None,
    operating_margin: Optional[float] = None,
    gross_margin: Optional[float] = None,
) -> float:
    """Growth-adjusted valuation score tailored to the stock's archetype.

    Returns a score 0–100 where higher = better valuation quality for
    *this type* of stock. Prevents raw P/E from killing growth-stock scores.
    """
    score = 50.0
    fpe = data.forward_pe
    peg = data.peg_ratio
    ps = data.price_to_sales
    ev = data.ev_to_ebitda
    fcf_yield = data.fcf_yield
    tpe = data.trailing_pe

    if archetype in (StockArchetype.HYPER_GROWTH, StockArchetype.SPECULATIVE_STORY):
        # Rule of 40: revenue_growth_pct + operating_margin_pct ≥ 40 is healthy
        rule_of_40: Optional[float] = None
        if revenue_growth_yoy is not None and operating_margin is not None:
            rule_of_40 = (revenue_growth_yoy * 100) + (operating_margin * 100)

        if rule_of_40 is not None:
            if rule_of_40 >= 60:
                score += 15
            elif rule_of_40 >= 40:
                score += 8
            elif rule_of_40 >= 20:
                score += 0
            else:
                score -= 10

        # PEG is the primary signal for growth stocks
        if peg is not None:
            if peg <= 1.0:
                score += 15
            elif peg <= 1.5:
                score += 8
            elif peg <= 2.5:
                score += 0
            elif peg <= 4.0:
                score -= 8
            else:
                score -= 15

        # P/E: soften penalty heavily — growth stocks deserve high multiples
        if fpe is not None and peg is None:
            if fpe <= 30:
                score += 10
            elif fpe <= 50:
                score += 0
            elif fpe <= 80:
                score -= 5  # much softer than original -20
            else:
                score -= 10

        # P/S: only penalise if gross margin is also low
        if ps is not None:
            high_gm = gross_margin is not None and gross_margin > 0.60
            if ps <= 10:
                score += 5
            elif ps <= 20:
                score += 0
            elif ps <= 40 and high_gm:
                score += 0  # high margin justifies high P/S
            elif ps <= 40:
                score -= 5
            else:
                score -= 10

        # FCF yield bonus if generating cash despite fast growth
        if fcf_yield is not None:
            if fcf_yield >= 3:
                score += 10
            elif fcf_yield >= 1:
                score += 5
            elif fcf_yield < 0:
                score -= 5  # softer penalty for growth-stage capex

    elif archetype == StockArchetype.MATURE_VALUE:
        # Traditional scoring applies with extra weight on FCF yield
        if fpe is not None:
            if fpe <= 12:
                score += 20
            elif fpe <= 18:
                score += 12
            elif fpe <= 25:
                score += 0
            elif fpe <= 35:
                score -= 12
            else:
                score -= 20

        if fcf_yield is not None:
            if fcf_yield >= 6:
                score += 15
            elif fcf_yield >= 3:
                score += 8
            elif fcf_yield >= 1:
                score += 3
            elif fcf_yield < 0:
                score -= 15

        if peg is not None:
            if peg <= 1.0:
                score += 10
            elif peg <= 1.5:
                score += 5
            elif peg > 2.5:
                score -= 10

        if ps is not None:
            if ps <= 2:
                score += 8
            elif ps <= 5:
                score += 3
            elif ps > 10:
                score -= 8

        if ev is not None:
            if ev <= 10:
                score += 10
            elif ev <= 15:
                score += 5
            elif ev > 25:
                score -= 10

    elif archetype == StockArchetype.CYCLICAL_GROWTH:
        # Use EV/EBITDA but don't reward ultra-low P/E (may be peak earnings)
        if ev is not None:
            if ev <= 8:
                score += 5  # low EV may = peak cycle, careful
            elif ev <= 15:
                score += 10
            elif ev <= 25:
                score += 0
            elif ev <= 40:
                score -= 8
            else:
                score -= 15

        if fcf_yield is not None:
            if fcf_yield >= 5:
                score += 10
            elif fcf_yield >= 2:
                score += 5
            elif fcf_yield < 0:
                score -= 10

        # Don't trust very low P/E as a buy signal for cyclicals
        if fpe is not None:
            if fpe <= 10:
                score += 3  # may be near peak earnings, soften reward
            elif fpe <= 20:
                score += 8
            elif fpe <= 30:
                score += 0
            elif fpe <= 40:
                score -= 8
            else:
                score -= 15

    elif archetype in (StockArchetype.DEFENSIVE, StockArchetype.COMMODITY_CYCLICAL):
        # Standard scoring but FCF and stability matter more
        if fpe is not None:
            if fpe <= 15:
                score += 15
            elif fpe <= 20:
                score += 8
            elif fpe <= 30:
                score += 0
            elif fpe <= 40:
                score -= 10
            else:
                score -= 18

        if fcf_yield is not None:
            if fcf_yield >= 5:
                score += 12
            elif fcf_yield >= 2:
                score += 6
            elif fcf_yield < 0:
                score -= 12

        if ps is not None:
            if ps <= 2:
                score += 8
            elif ps <= 5:
                score += 3
            elif ps > 10:
                score -= 5

    else:
        # PROFITABLE_GROWTH and TURNAROUND — moderate approach
        score = score_valuation(data)
        return score

    return round(max(0.0, min(100.0, score)), 2)
