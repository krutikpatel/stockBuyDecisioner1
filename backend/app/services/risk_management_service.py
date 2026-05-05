from __future__ import annotations

from typing import Optional

from app.models.market import SupportResistanceLevels, TechnicalIndicators
from app.models.response import EntryPlan, ExitPlan, PositionSizing, RiskReward


_POSITION_SIZING = {
    "conservative": {"starter_pct": 15, "max_allocation": 3.0},
    "moderate": {"starter_pct": 25, "max_allocation": 5.0},
    "aggressive": {"starter_pct": 40, "max_allocation": 8.0},
}


def compute_risk_management(
    price: float,
    technicals: TechnicalIndicators,
    decision: str,
    risk_profile: str = "moderate",
    within_30_days_earnings: bool = False,
) -> tuple[EntryPlan, ExitPlan, RiskReward, PositionSizing]:
    sr = technicals.support_resistance

    nearest_support = sr.nearest_support
    nearest_resistance = sr.nearest_resistance

    # Entry plan
    if decision in ("BUY_NOW",):
        preferred_entry = round(price, 2)
        starter_entry = round(price * 1.005, 2)
        breakout_entry = None
        avoid_above = round(price * 1.08, 2)
    elif decision == "WAIT_FOR_PULLBACK":
        preferred_entry = nearest_support if nearest_support else round(price * 0.95, 2)
        starter_entry = round(price * 0.98, 2)
        breakout_entry = None
        avoid_above = round(price * 1.05, 2)
    elif decision == "BUY_ON_BREAKOUT":
        preferred_entry = nearest_resistance if nearest_resistance else round(price * 1.03, 2)
        starter_entry = round(price * 1.01, 2)
        breakout_entry = nearest_resistance if nearest_resistance else round(price * 1.03, 2)
        avoid_above = round((breakout_entry or price * 1.03) * 1.03, 2)
    elif decision == "BUY_STARTER":
        preferred_entry = round(price, 2)
        starter_entry = round(price * 1.01, 2)
        breakout_entry = None
        avoid_above = round(price * 1.06, 2)
    else:  # WATCHLIST / AVOID
        preferred_entry = nearest_support if nearest_support else round(price * 0.90, 2)
        starter_entry = None
        breakout_entry = None
        avoid_above = None

    # Exit plan
    # Stop-loss: just below nearest support, or fixed % below entry
    if nearest_support:
        stop_loss = round(nearest_support * 0.99, 2)
        invalidation = round(nearest_support * 0.98, 2)
    else:
        stop_loss = round(price * 0.92, 2)
        invalidation = round(price * 0.90, 2)

    # Targets: nearest resistance and next level
    supports = sr.supports or []
    resistances = sr.resistances or []

    first_target = round(resistances[0], 2) if resistances else round(price * 1.10, 2)
    second_target = round(resistances[1], 2) if len(resistances) >= 2 else round(price * 1.20, 2)

    # Risk/reward
    entry_ref = preferred_entry or price
    downside_abs = entry_ref - stop_loss
    upside_abs = first_target - entry_ref
    downside_pct = round(downside_abs / entry_ref * 100, 2) if entry_ref else None
    upside_pct = round(upside_abs / entry_ref * 100, 2) if entry_ref else None
    rr_ratio: Optional[float] = None
    if downside_abs and downside_abs > 0:
        rr_ratio = round(upside_abs / downside_abs, 2)

    # Position sizing
    sizing_cfg = _POSITION_SIZING.get(risk_profile, _POSITION_SIZING["moderate"])
    starter_pct = sizing_cfg["starter_pct"]
    max_alloc = sizing_cfg["max_allocation"]

    # Reduce position size before earnings
    if within_30_days_earnings:
        starter_pct = int(starter_pct * 0.5)
        max_alloc = round(max_alloc * 0.7, 1)

    return (
        EntryPlan(
            preferred_entry=preferred_entry,
            starter_entry=starter_entry,
            breakout_entry=breakout_entry,
            avoid_above=avoid_above,
        ),
        ExitPlan(
            stop_loss=stop_loss,
            invalidation_level=invalidation,
            first_target=first_target,
            second_target=second_target,
        ),
        RiskReward(
            downside_percent=downside_pct,
            upside_percent=upside_pct,
            ratio=rr_ratio,
        ),
        PositionSizing(
            suggested_starter_pct_of_full=starter_pct,
            max_portfolio_allocation_pct=max_alloc,
        ),
    )
