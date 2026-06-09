from __future__ import annotations

from typing import Optional

from app.algo_config import AlgoConfig, get_algo_config
from app.models.fundamentals import StockArchetype, ValuationData


def _desc(val: float, tiers: list, pts: list) -> float:
    """Score for descending metrics (lower is better: P/E, P/S, EV/EBITDA, PEG)."""
    for i, t in enumerate(tiers):
        if val <= t:
            return pts[i]
    return pts[-1]


def _asc(val: float, tiers: list, pts: list) -> float:
    """Score for ascending metrics (higher is better: FCF yield, Rule of 40)."""
    for i, t in enumerate(tiers):
        if val >= t:
            return pts[i]
    return pts[-1]


def score_valuation(data: ValuationData, algo_config: Optional[AlgoConfig] = None) -> float:
    """Score 0–100. Attractive valuation = higher score.

    This archetype-neutral version is kept for backward compatibility.
    Use score_valuation_with_archetype() for growth-adjusted scoring.
    """
    cfg = algo_config or get_algo_config()
    sc = cfg.valuation["standard"]
    score = cfg.valuation["base_score"]

    if data.forward_pe is not None:
        score += _desc(data.forward_pe, sc["fpe_tiers"], sc["fpe_pts"])

    if data.peg_ratio is not None:
        score += _desc(data.peg_ratio, sc["peg_tiers"], sc["peg_pts"])

    if data.price_to_sales is not None:
        score += _desc(data.price_to_sales, sc["ps_tiers"], sc["ps_pts"])

    if data.ev_to_ebitda is not None:
        score += _desc(data.ev_to_ebitda, sc["ev_ebitda_tiers"], sc["ev_ebitda_pts"])

    if data.fcf_yield is not None:
        score += _asc(data.fcf_yield, sc["fcf_yield_tiers"], sc["fcf_yield_pts"])

    tpe = data.trailing_pe
    if tpe is not None:
        if tpe <= sc["trailing_pe_good"]:
            score += sc["trailing_pe_good_pts"]
        elif tpe > sc["trailing_pe_bad"]:
            score += sc["trailing_pe_bad_pts"]

    return round(max(0.0, min(100.0, score)), 2)


def score_valuation_with_archetype(
    data: ValuationData,
    archetype: str,
    revenue_growth_yoy: Optional[float] = None,
    operating_margin: Optional[float] = None,
    gross_margin: Optional[float] = None,
    algo_config: Optional[AlgoConfig] = None,
) -> float:
    """Growth-adjusted valuation score tailored to the stock's archetype.

    Returns a score 0–100 where higher = better valuation quality for
    *this type* of stock. Prevents raw P/E from killing growth-stock scores.
    All tier boundaries and points are read from algo_config.valuation.
    """
    cfg = algo_config or get_algo_config()
    score = cfg.valuation["base_score"]
    fpe = data.forward_pe
    peg = data.peg_ratio
    ps = data.price_to_sales
    ev = data.ev_to_ebitda
    fcf_yield = data.fcf_yield

    if archetype in (StockArchetype.HYPER_GROWTH, StockArchetype.SPECULATIVE_STORY):
        hg = cfg.valuation["hyper_growth"]

        # Rule of 40: revenue_growth_pct + operating_margin_pct ≥ 40 is healthy
        if revenue_growth_yoy is not None and operating_margin is not None:
            rule_of_40 = (revenue_growth_yoy * 100) + (operating_margin * 100)
            score += _asc(rule_of_40, hg["rule_of_40_tiers"], hg["rule_of_40_pts"])

        # PEG is the primary signal for growth stocks
        if peg is not None:
            score += _desc(peg, hg["peg_tiers"], hg["peg_pts"])

        # P/E: soften penalty heavily — only use when no PEG
        if fpe is not None and peg is None:
            score += _desc(fpe, hg["fpe_no_peg_tiers"], hg["fpe_no_peg_pts"])

        # P/S: only penalise if gross margin is also low
        if ps is not None:
            high_gm = gross_margin is not None and gross_margin > hg["ps_high_margin_threshold"]
            pts = hg["ps_pts_high_margin"] if high_gm else hg["ps_pts_normal"]
            score += _desc(ps, hg["ps_tiers"], pts)

        # FCF yield bonus if generating cash despite fast growth
        if fcf_yield is not None:
            score += _asc(fcf_yield, hg["fcf_yield_tiers"], hg["fcf_yield_pts"])

    elif archetype == StockArchetype.MATURE_VALUE:
        mv = cfg.valuation["mature_value"]

        if fpe is not None:
            score += _desc(fpe, mv["fpe_tiers"], mv["fpe_pts"])

        if fcf_yield is not None:
            score += _asc(fcf_yield, mv["fcf_yield_tiers"], mv["fcf_yield_pts"])

        if peg is not None:
            score += _desc(peg, mv["peg_tiers"], mv["peg_pts"])

        if ps is not None:
            score += _desc(ps, mv["ps_tiers"], mv["ps_pts"])

        if ev is not None:
            score += _desc(ev, mv["ev_ebitda_tiers"], mv["ev_ebitda_pts"])

    elif archetype == StockArchetype.CYCLICAL_GROWTH:
        cg = cfg.valuation["cyclical_growth"]

        if ev is not None:
            score += _desc(ev, cg["ev_ebitda_tiers"], cg["ev_ebitda_pts"])

        if fcf_yield is not None:
            score += _asc(fcf_yield, cg["fcf_yield_tiers"], cg["fcf_yield_pts"])

        # Don't trust very low P/E as a buy signal for cyclicals
        if fpe is not None:
            score += _desc(fpe, cg["fpe_tiers"], cg["fpe_pts"])

    elif archetype in (StockArchetype.DEFENSIVE, StockArchetype.COMMODITY_CYCLICAL):
        df = cfg.valuation["defensive"]

        if fpe is not None:
            score += _desc(fpe, df["fpe_tiers"], df["fpe_pts"])

        if fcf_yield is not None:
            score += _asc(fcf_yield, df["fcf_yield_tiers"], df["fcf_yield_pts"])

        if ps is not None:
            score += _desc(ps, df["ps_tiers"], df["ps_pts"])

    else:
        # PROFITABLE_GROWTH and TURNAROUND — moderate approach
        return score_valuation(data, algo_config=algo_config)

    return round(max(0.0, min(100.0, score)), 2)
