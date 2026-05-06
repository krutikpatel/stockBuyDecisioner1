from __future__ import annotations

from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData

_DEFENSIVE_SECTORS = {"Healthcare", "Consumer Defensive", "Utilities"}
_COMMODITY_SECTORS = {"Energy", "Basic Materials"}
_CYCLICAL_SECTORS = {"Energy", "Basic Materials", "Industrials", "Consumer Cyclical"}


def classify_archetype(
    fundamentals: FundamentalData,
    valuation: ValuationData,
) -> tuple[str, float]:
    """Return (archetype, confidence 0-100).

    Priority order:
    1. SPECULATIVE_STORY — unprofitable high-growth or very high P/S
    2. HYPER_GROWTH — very fast revenue growth
    3. DEFENSIVE — low-beta defensive sector
    4. COMMODITY_CYCLICAL — energy/materials
    5. CYCLICAL_GROWTH — high-beta cyclical sector
    6. PROFITABLE_GROWTH — solid growth + positive economics
    7. TURNAROUND — recovering from decline
    8. MATURE_VALUE — slow growth, stable cash flows
    """
    rev_yoy = fundamentals.revenue_growth_yoy  # decimal, e.g. 0.25 = 25%
    op_margin = fundamentals.operating_margin
    fcf = fundamentals.free_cash_flow
    eps = fundamentals.eps_ttm
    gross_margin = fundamentals.gross_margin
    beta = fundamentals.beta
    sector = fundamentals.sector or ""

    fpe = valuation.forward_pe
    ps = valuation.price_to_sales
    eps_growth = fundamentals.eps_growth_yoy
    rev_qoq = fundamentals.revenue_growth_qoq

    # 1. SPECULATIVE_STORY
    # High P/S with negative earnings, or extremely high P/S regardless
    is_unprofitable = eps is not None and eps < 0
    high_ps = ps is not None and ps > 20
    high_growth_unprofitable = (
        is_unprofitable
        and rev_yoy is not None
        and rev_yoy > 0.20
    )
    if high_ps and high_growth_unprofitable:
        return StockArchetype.SPECULATIVE_STORY, 80.0
    if ps is not None and ps > 40:
        return StockArchetype.SPECULATIVE_STORY, 70.0

    # 2. HYPER_GROWTH
    # Revenue growing > 30%, or > 20% with high forward P/E
    if rev_yoy is not None and rev_yoy > 0.30:
        conf = min(95.0, 70.0 + (rev_yoy - 0.30) * 100)
        return StockArchetype.HYPER_GROWTH, round(conf, 1)
    if rev_yoy is not None and rev_yoy > 0.20 and fpe is not None and fpe > 40:
        return StockArchetype.HYPER_GROWTH, 72.0

    # 3. DEFENSIVE
    if sector in _DEFENSIVE_SECTORS and (beta is None or beta < 0.8):
        return StockArchetype.DEFENSIVE, 80.0
    if sector in _DEFENSIVE_SECTORS:
        return StockArchetype.DEFENSIVE, 65.0

    # 4. COMMODITY_CYCLICAL
    if sector in _COMMODITY_SECTORS:
        return StockArchetype.COMMODITY_CYCLICAL, 78.0

    # 5. CYCLICAL_GROWTH
    if beta is not None and beta > 1.3 and sector in _CYCLICAL_SECTORS:
        return StockArchetype.CYCLICAL_GROWTH, 72.0

    # 6. PROFITABLE_GROWTH
    # Revenue growing > 15% with positive operating economics
    positive_ops = (op_margin is not None and op_margin > 0) or (fcf is not None and fcf > 0)
    if rev_yoy is not None and rev_yoy > 0.15 and positive_ops:
        conf = min(85.0, 65.0 + (rev_yoy - 0.15) * 100)
        return StockArchetype.PROFITABLE_GROWTH, round(conf, 1)

    # 7. TURNAROUND
    # Recovering: eps improving, recent quarterly revenue recovery, but still slow annual growth
    eps_recovering = eps_growth is not None and eps_growth > 0.10
    rev_recovering = rev_qoq is not None and rev_qoq > 0.05
    was_slow_growth = rev_yoy is None or rev_yoy < 0.10
    if was_slow_growth and (eps_recovering or rev_recovering) and eps is not None and eps > 0:
        return StockArchetype.TURNAROUND, 60.0

    # 8. MATURE_VALUE
    slow_growth = rev_yoy is None or rev_yoy < 0.10
    profitable = (fcf is not None and fcf > 0) or (eps is not None and eps > 0)
    if slow_growth and profitable:
        return StockArchetype.MATURE_VALUE, 68.0

    # Default fallback
    return StockArchetype.PROFITABLE_GROWTH, 40.0


def classify_and_attach(fundamentals: FundamentalData, valuation: ValuationData) -> FundamentalData:
    """Classify archetype and attach result directly to FundamentalData."""
    archetype, confidence = classify_archetype(fundamentals, valuation)
    fundamentals.archetype = archetype
    fundamentals.archetype_confidence = confidence
    return fundamentals
