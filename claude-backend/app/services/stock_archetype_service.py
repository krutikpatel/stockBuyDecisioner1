from __future__ import annotations

from typing import Optional

from app.algo_config import AlgoConfig, get_algo_config
from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData


def classify_archetype(
    fundamentals: FundamentalData,
    valuation: ValuationData,
    algo_config: Optional[AlgoConfig] = None,
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
    cfg = algo_config or get_algo_config()
    sa = cfg.stock_archetype

    defensive_sectors = set(sa["defensive_sectors"])
    commodity_sectors = set(sa["commodity_sectors"])
    cyclical_sectors = set(sa["cyclical_sectors"])

    spec_ps_high_growth = sa["speculative_ps_high_growth_min"]
    spec_high_growth_rev = sa["speculative_high_growth_rev_min"]
    spec_ps_hard = sa["speculative_ps_hard_min"]
    spec_ps_high_conf = sa["speculative_ps_high_growth_confidence"]
    spec_ps_hard_conf = sa["speculative_ps_hard_confidence"]

    hyper_rev_min = sa["hyper_growth_rev_yoy_min"]
    hyper_rev_alt = sa["hyper_growth_rev_alt_min"]
    hyper_fpe_min = sa["hyper_growth_fpe_min"]
    hyper_alt_conf = sa["hyper_growth_alt_confidence"]

    def_beta_max = sa["defensive_beta_max"]
    def_high_conf = sa["defensive_high_confidence"]
    def_low_conf = sa["defensive_low_confidence"]
    commodity_conf = sa["commodity_cyclical_confidence"]
    cyclical_beta_min = sa["cyclical_beta_min"]
    cyclical_conf = sa["cyclical_growth_confidence"]

    prof_rev_min = sa["profitable_growth_rev_min"]
    turn_eps_min = sa["turnaround_eps_growth_min"]
    turn_rev_qoq_min = sa["turnaround_rev_qoq_min"]
    turn_slow_max = sa["turnaround_slow_growth_max"]
    turn_conf = sa["turnaround_confidence"]
    mature_rev_max = sa["mature_value_rev_max"]
    mature_conf = sa["mature_value_confidence"]
    default_conf = sa["default_confidence"]

    rev_yoy = fundamentals.revenue_growth_yoy
    op_margin = fundamentals.operating_margin
    fcf = fundamentals.free_cash_flow
    eps = fundamentals.eps_ttm
    beta = fundamentals.beta
    sector = fundamentals.sector or ""

    fpe = valuation.forward_pe
    ps = valuation.price_to_sales
    eps_growth = fundamentals.eps_growth_yoy
    rev_qoq = fundamentals.revenue_growth_qoq

    # 1. SPECULATIVE_STORY
    is_unprofitable = eps is not None and eps < 0
    high_ps = ps is not None and ps > spec_ps_high_growth
    high_growth_unprofitable = is_unprofitable and rev_yoy is not None and rev_yoy > spec_high_growth_rev
    if high_ps and high_growth_unprofitable:
        return StockArchetype.SPECULATIVE_STORY, spec_ps_high_conf
    if ps is not None and ps > spec_ps_hard:
        return StockArchetype.SPECULATIVE_STORY, spec_ps_hard_conf

    # 2. HYPER_GROWTH
    if rev_yoy is not None and rev_yoy > hyper_rev_min:
        conf = min(95.0, 70.0 + (rev_yoy - hyper_rev_min) * 100)
        return StockArchetype.HYPER_GROWTH, round(conf, 1)
    if rev_yoy is not None and rev_yoy > hyper_rev_alt and fpe is not None and fpe > hyper_fpe_min:
        return StockArchetype.HYPER_GROWTH, hyper_alt_conf

    # 3. DEFENSIVE
    if sector in defensive_sectors and (beta is None or beta < def_beta_max):
        return StockArchetype.DEFENSIVE, def_high_conf
    if sector in defensive_sectors:
        return StockArchetype.DEFENSIVE, def_low_conf

    # 4. COMMODITY_CYCLICAL
    if sector in commodity_sectors:
        return StockArchetype.COMMODITY_CYCLICAL, commodity_conf

    # 5. CYCLICAL_GROWTH
    if beta is not None and beta > cyclical_beta_min and sector in cyclical_sectors:
        return StockArchetype.CYCLICAL_GROWTH, cyclical_conf

    # 6. PROFITABLE_GROWTH
    positive_ops = (op_margin is not None and op_margin > 0) or (fcf is not None and fcf > 0)
    if rev_yoy is not None and rev_yoy > prof_rev_min and positive_ops:
        conf = min(85.0, 65.0 + (rev_yoy - prof_rev_min) * 100)
        return StockArchetype.PROFITABLE_GROWTH, round(conf, 1)

    # 7. TURNAROUND
    eps_recovering = eps_growth is not None and eps_growth > turn_eps_min
    rev_recovering = rev_qoq is not None and rev_qoq > turn_rev_qoq_min
    was_slow_growth = rev_yoy is None or rev_yoy < turn_slow_max
    if was_slow_growth and (eps_recovering or rev_recovering) and eps is not None and eps > 0:
        return StockArchetype.TURNAROUND, turn_conf

    # 8. MATURE_VALUE
    slow_growth = rev_yoy is None or rev_yoy < mature_rev_max
    profitable = (fcf is not None and fcf > 0) or (eps is not None and eps > 0)
    if slow_growth and profitable:
        return StockArchetype.MATURE_VALUE, mature_conf

    # Default fallback
    return StockArchetype.PROFITABLE_GROWTH, default_conf


def classify_and_attach(
    fundamentals: FundamentalData,
    valuation: ValuationData,
    algo_config: Optional[AlgoConfig] = None,
) -> FundamentalData:
    """Classify archetype and attach result directly to FundamentalData."""
    archetype, confidence = classify_archetype(fundamentals, valuation, algo_config=algo_config)
    fundamentals.archetype = archetype
    fundamentals.archetype_confidence = confidence
    return fundamentals


# ---------------------------------------------------------------------------
# Backward-compatible module-level sector set aliases
# ---------------------------------------------------------------------------

def _default_sa() -> dict:
    return get_algo_config().stock_archetype


_DEFENSIVE_SECTORS = set(_default_sa()["defensive_sectors"])
_COMMODITY_SECTORS = set(_default_sa()["commodity_sectors"])
_CYCLICAL_SECTORS = set(_default_sa()["cyclical_sectors"])
