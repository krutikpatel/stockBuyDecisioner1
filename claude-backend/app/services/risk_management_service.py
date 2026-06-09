from __future__ import annotations

from typing import Optional

from app.algo_config import AlgoConfig, get_algo_config
from app.models.market import SupportResistanceLevels, TechnicalIndicators
from app.models.response import EntryPlan, ExitPlan, PositionSizing, RiskReward


def _atr_size_multiplier(
    atr_pct: float,
    thresholds: Optional[list] = None,
    multipliers: Optional[list] = None,
) -> float:
    """Return a position-size multiplier based on ATR% (ATR / price * 100).

    thresholds and multipliers come from config (or default config if omitted):
      atr_pct < thresholds[0]          → multipliers[0]  (low volatility)
      thresholds[0] <= atr_pct <= t[1] → multipliers[1]  (high volatility)
      atr_pct > thresholds[-1]         → multipliers[-1]  (extreme volatility)

    Note: ATR does NOT reduce the signal score; only affects sizing.
    """
    if thresholds is None:
        thresholds = get_algo_config().risk_management["atr_size_thresholds"]
    if multipliers is None:
        multipliers = get_algo_config().risk_management["atr_size_multipliers"]
    if atr_pct < thresholds[0]:
        return multipliers[0]
    for thresh, mult in zip(thresholds[1:], multipliers[1:-1]):
        if atr_pct <= thresh:
            return mult
    return multipliers[-1]


def _compute_stop_atr(
    entry: float,
    atr: float,
    horizon: str,
    stop_multipliers: Optional[dict] = None,
    default_mult: Optional[float] = None,
) -> float:
    """Compute ATR-based stop loss using config multipliers."""
    if stop_multipliers is None:
        stop_multipliers = get_algo_config().risk_management["atr_stop_multipliers"]
    if default_mult is None:
        default_mult = get_algo_config().risk_management["atr_stop_default_multiplier"]
    mult = stop_multipliers.get(horizon, default_mult)
    return round(entry - mult * atr, 2)


def compute_risk_management(
    price: float,
    technicals: TechnicalIndicators,
    decision: str,
    risk_profile: str = "moderate",
    within_30_days_earnings: bool = False,
    algo_config: Optional[AlgoConfig] = None,
) -> tuple[EntryPlan, ExitPlan, RiskReward, PositionSizing]:
    cfg = algo_config or get_algo_config()
    rm = cfg.risk_management

    sr = technicals.support_resistance
    nearest_support = sr.nearest_support
    nearest_resistance = sr.nearest_resistance

    # Entry plan — factors from config
    buy_now_starter = rm["entry_buy_now_starter_factor"]
    buy_now_avoid = rm["entry_buy_now_avoid_factor"]
    breakout_factor = rm["entry_buy_on_breakout_factor"]
    breakout_avoid = rm["entry_buy_on_breakout_avoid_factor"]
    buy_starter_starter = rm["entry_buy_starter_starter_factor"]
    buy_starter_avoid = rm["entry_buy_starter_avoid_factor"]
    wait_pullback = rm["entry_wait_pullback_factor"]
    wait_starter = rm["entry_wait_starter_factor"]
    wait_avoid = rm["entry_wait_avoid_factor"]
    watchlist_factor = rm["entry_watchlist_factor"]

    if decision in ("BUY_NOW",):
        preferred_entry = round(price, 2)
        starter_entry = round(price * buy_now_starter, 2)
        breakout_entry = None
        avoid_above = round(price * buy_now_avoid, 2)
    elif decision == "WAIT_FOR_PULLBACK":
        preferred_entry = nearest_support if nearest_support else round(price * wait_pullback, 2)
        starter_entry = round(price * wait_starter, 2)
        breakout_entry = None
        avoid_above = round(price * wait_avoid, 2)
    elif decision == "BUY_ON_BREAKOUT":
        preferred_entry = nearest_resistance if nearest_resistance else round(price * breakout_factor, 2)
        starter_entry = round(price * buy_starter_starter, 2)
        breakout_entry = nearest_resistance if nearest_resistance else round(price * breakout_factor, 2)
        avoid_above = round((breakout_entry or price * breakout_factor) * breakout_avoid, 2)
    elif decision == "BUY_STARTER":
        preferred_entry = round(price, 2)
        starter_entry = round(price * buy_starter_starter, 2)
        breakout_entry = None
        avoid_above = round(price * buy_starter_avoid, 2)
    else:  # WATCHLIST / AVOID
        preferred_entry = nearest_support if nearest_support else round(price * watchlist_factor, 2)
        starter_entry = None
        breakout_entry = None
        avoid_above = None

    # Exit plan — stop-loss: ATR-based when available, otherwise support or fixed %
    atr_val = technicals.atr
    entry_ref_for_stop = preferred_entry or price
    horizon_guess = "short_term"  # default (refined by caller if needed)

    stop_multipliers = rm["atr_stop_multipliers"]
    default_mult = rm["atr_stop_default_multiplier"]
    atr_invalidation_extra = rm["atr_invalidation_extra"]
    fallback_stop_support = rm["fallback_stop_support_buffer"]
    fallback_inv_support = rm["fallback_invalidation_support_buffer"]
    fallback_stop_no_support = rm["fallback_stop_no_support"]
    fallback_inv_no_support = rm["fallback_invalidation_no_support"]

    if atr_val is not None and atr_val > 0:
        stop_loss = _compute_stop_atr(entry_ref_for_stop, atr_val, horizon_guess, stop_multipliers, default_mult)
        invalidation = round(stop_loss - atr_val * atr_invalidation_extra, 2)
    elif nearest_support:
        stop_loss = round(nearest_support * fallback_stop_support, 2)
        invalidation = round(nearest_support * fallback_inv_support, 2)
    else:
        stop_loss = round(price * fallback_stop_no_support, 2)
        invalidation = round(price * fallback_inv_no_support, 2)

    # Targets: nearest resistance and next level
    supports = sr.supports or []
    resistances = sr.resistances or []

    first_target_no_res = rm["target_first_no_resistance"]
    second_target_no_res = rm["target_second_no_resistance"]
    first_target = round(resistances[0], 2) if resistances else round(price * first_target_no_res, 2)
    second_target = round(resistances[1], 2) if len(resistances) >= 2 else round(price * second_target_no_res, 2)

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
    position_sizing_cfg = rm["position_sizing"]
    sizing = position_sizing_cfg.get(risk_profile, position_sizing_cfg["moderate"])
    starter_pct = sizing["starter_pct"]
    max_alloc = sizing["max_allocation"]

    # Reduce position size before earnings
    pre_earnings_starter_cut = rm["pre_earnings_starter_cut"]
    pre_earnings_alloc_cut = rm["pre_earnings_allocation_cut"]
    if within_30_days_earnings:
        starter_pct = int(starter_pct * pre_earnings_starter_cut)
        max_alloc = round(max_alloc * pre_earnings_alloc_cut, 1)

    # ATR-based position size adjustment
    atr_size_thresholds = rm["atr_size_thresholds"]
    atr_size_multipliers = rm["atr_size_multipliers"]
    atr_pct = technicals.atr_percent
    if atr_pct is not None:
        atr_mult = _atr_size_multiplier(atr_pct, atr_size_thresholds, atr_size_multipliers)
        if atr_mult < 1.0:
            starter_pct = max(1, int(starter_pct * atr_mult))
            max_alloc = round(max_alloc * atr_mult, 1)

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


# ---------------------------------------------------------------------------
# Backward-compatible module-level alias
# ---------------------------------------------------------------------------

_POSITION_SIZING = get_algo_config().risk_management["position_sizing"]
