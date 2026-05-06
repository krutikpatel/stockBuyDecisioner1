from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class StockArchetype:
    HYPER_GROWTH = "HYPER_GROWTH"
    PROFITABLE_GROWTH = "PROFITABLE_GROWTH"
    CYCLICAL_GROWTH = "CYCLICAL_GROWTH"
    MATURE_VALUE = "MATURE_VALUE"
    TURNAROUND = "TURNAROUND"
    SPECULATIVE_STORY = "SPECULATIVE_STORY"
    DEFENSIVE = "DEFENSIVE"
    COMMODITY_CYCLICAL = "COMMODITY_CYCLICAL"

    ALL = [
        HYPER_GROWTH, PROFITABLE_GROWTH, CYCLICAL_GROWTH, MATURE_VALUE,
        TURNAROUND, SPECULATIVE_STORY, DEFENSIVE, COMMODITY_CYCLICAL,
    ]


class FundamentalData(BaseModel):
    revenue_ttm: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    revenue_growth_qoq: Optional[float] = None
    eps_ttm: Optional[float] = None
    eps_growth_yoy: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    free_cash_flow: Optional[float] = None
    free_cash_flow_margin: Optional[float] = None
    cash: Optional[float] = None
    total_debt: Optional[float] = None
    net_debt: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    shares_outstanding: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None
    sector: Optional[str] = None
    beta: Optional[float] = None
    fundamental_score: float = 0.0
    archetype: str = StockArchetype.PROFITABLE_GROWTH
    archetype_confidence: float = 0.0


class ValuationData(BaseModel):
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    price_to_fcf: Optional[float] = None
    fcf_yield: Optional[float] = None
    peer_comparison_available: bool = False
    valuation_score: float = 0.0
    archetype_adjusted_score: float = 0.0  # growth-adjusted score (set after archetype classification)
