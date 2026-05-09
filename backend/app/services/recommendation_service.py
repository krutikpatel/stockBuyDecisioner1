from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.algo_config import AlgoConfig, get_algo_config
from app.models.market import MarketRegime, MarketRegimeAssessment, TechnicalIndicators
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import HorizonRecommendation, SignalCards
from app.services.risk_management_service import compute_risk_management
from app.services.data_completeness_service import (
    compute_completeness,
    AVOID_LOW_CONFIDENCE_THRESHOLD,
)

@dataclass
class RegimeThresholds:
    """Per-regime entry thresholds for short-term decisions."""
    rsi_min: float = 55.0
    rsi_max: float = 68.0
    sma20_max: float = 5.0       # max % above SMA20 for BUY_NOW_CONTINUATION
    rel_vol_min: float = 1.3     # minimum relative volume


def _get_regime_thresholds(regime: str, algo_config: Optional[AlgoConfig] = None) -> RegimeThresholds:
    """Return appropriate entry thresholds for the given market regime."""
    cfg = algo_config or get_algo_config()
    rt = cfg.decision_logic["regime_thresholds"]
    raw = rt.get(regime, rt.get("default", {}))
    if raw:
        return RegimeThresholds(
            rsi_min=raw["rsi_min"],
            rsi_max=raw["rsi_max"],
            sma20_max=raw["sma20_max"],
            rel_vol_min=raw["rel_vol_min"],
        )
    # Fallback (should never happen if config is complete)
    return RegimeThresholds(rsi_min=55.0, rsi_max=68.0, sma20_max=5.0, rel_vol_min=1.3)


# All valid decision labels (US-005 expansion)
ALL_DECISIONS = {
    "BUY_NOW",
    "BUY_STARTER",
    "BUY_STARTER_EXTENDED",          # strong but extended; smaller position
    "BUY_ON_PULLBACK",               # wait for MA retest
    "BUY_ON_BREAKOUT",               # consolidating near resistance
    "BUY_AFTER_EARNINGS",            # wait for earnings confirmation
    "WATCHLIST",
    "WATCHLIST_NEEDS_CATALYST",
    "HOLD_EXISTING_DO_NOT_ADD",
    "AVOID",                         # generic (backward compat)
    "AVOID_BAD_BUSINESS",            # deteriorating fundamentals
    "AVOID_BAD_CHART",               # legacy: price below 50DMA + 200DMA, weak RS
    "AVOID_BAD_RISK_REWARD",         # risk/reward < 1:1
    "AVOID_LOW_CONFIDENCE",          # missing critical data
    # Improvements 3: new precise labels
    "BUY_NOW_CONTINUATION",          # tightened momentum continuation buy
    "OVERSOLD_REBOUND_CANDIDATE",    # RSI 25-42 turning up, rebound setup
    "TRUE_DOWNTREND_AVOID",          # confirmed downtrend with all criteria
    "BROKEN_SUPPORT_AVOID",          # heavy-vol break of key support
}

# Story 7 + Improvements 3: per-horizon decision labels
SHORT_TERM_DECISIONS = {
    "BUY_NOW_CONTINUATION",          # replaces BUY_NOW_MOMENTUM (tightened)
    "BUY_STARTER_STRONG_BUT_EXTENDED",
    "WAIT_FOR_PULLBACK",
    "BUY_ON_PULLBACK",
    "OVERSOLD_REBOUND_CANDIDATE",
    "TRUE_DOWNTREND_AVOID",
    "BROKEN_SUPPORT_AVOID",
    "AVOID_BAD_CHART",               # kept for backward compat fallback
    "AVOID_LOW_CONFIDENCE",
    "WATCHLIST",
}

MEDIUM_TERM_DECISIONS = {
    "BUY_NOW",
    "BUY_STARTER",
    "BUY_ON_PULLBACK",
    "WATCHLIST_NEEDS_CONFIRMATION",
    "AVOID_BAD_BUSINESS",
    "AVOID_LOW_CONFIDENCE",
    "WATCHLIST",
}

LONG_TERM_DECISIONS = {
    "ACCUMULATE_ON_WEAKNESS",
    "BUY_NOW_LONG_TERM",
    "WATCHLIST_VALUATION_TOO_RICH",
    "AVOID_LONG_TERM",
    "AVOID_LOW_CONFIDENCE",
    "WATCHLIST",
}

ALL_DECISIONS = ALL_DECISIONS | SHORT_TERM_DECISIONS | MEDIUM_TERM_DECISIONS | LONG_TERM_DECISIONS


def _confidence(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 65:
        return "medium_high"
    if score >= 50:
        return "medium"
    return "low"


def _is_bull_regime(regime: Optional[MarketRegimeAssessment]) -> bool:
    if regime is None:
        return False
    return regime.regime in (MarketRegime.BULL_RISK_ON, MarketRegime.LIQUIDITY_RALLY)


def _is_bear_regime(regime: Optional[MarketRegimeAssessment]) -> bool:
    if regime is None:
        return False
    return regime.regime == MarketRegime.BEAR_RISK_OFF


def _chart_is_weak(technicals: TechnicalIndicators) -> bool:
    """Price below 200DMA (downtrend) AND weak relative strength."""
    downtrend = technicals.trend.label == "downtrend"
    weak_rs = technicals.rs_vs_spy is not None and technicals.rs_vs_spy < 0.8
    return downtrend and weak_rs


def _business_deteriorating(fundamentals: FundamentalData, earnings: EarningsData) -> bool:
    """Revenue declining + earnings miss history → bad business signal."""
    rev_declining = (
        fundamentals.revenue_growth_yoy is not None
        and fundamentals.revenue_growth_yoy < 0
    )
    op_margin_negative = (
        fundamentals.operating_margin is not None
        and fundamentals.operating_margin < -0.05
    )
    poor_beats = earnings.beat_rate is not None and earnings.beat_rate < 0.40
    return rev_declining and (op_margin_negative or poor_beats)


def _classify_52w_position(technicals: TechnicalIndicators) -> str:
    """Return a bucket label based on distance from the 52-week high.

    Buckets (dist_from_52w_high is negative, e.g. -5 means 5% below high):
    - "near_52w_high"      : 0 to -3%   (breakout candidate territory)
    - "healthy_pullback"   : -3% to -10%
    - "extended_pullback"  : -10% to -15%
    - "rebound_territory"  : -15% to -35%
    - "avoid_zone"         : < -35%
    - "unknown"            : field is None
    """
    dist = technicals.dist_from_52w_high
    if dist is None:
        return "unknown"
    # dist is negative (price below 52W high)
    if dist >= -3.0:
        return "near_52w_high"
    if dist >= -10.0:
        return "healthy_pullback"
    if dist >= -15.0:
        return "extended_pullback"
    if dist >= -35.0:
        return "rebound_territory"
    return "avoid_zone"


def _classify_bad_chart(technicals: TechnicalIndicators) -> str:
    """Split old AVOID_BAD_CHART into three precise sub-labels.

    Priority order:
    1. OVERSOLD_REBOUND_CANDIDATE — RSI 25-42 turning up with improving price action
    2. BROKEN_SUPPORT_AVOID      — heavy-volume break of SMA50 with weak close
    3. TRUE_DOWNTREND_AVOID      — full confirmed downtrend (default)
    """
    t = technicals
    rsi = t.rsi_14
    rsi_slope = t.rsi_slope

    # --- Check OVERSOLD_REBOUND_CANDIDATE first (most actionable) ---
    rsi_in_rebound_range = rsi is not None and 25.0 <= rsi <= 42.0
    rsi_turning_up = rsi_slope is not None and rsi_slope > 0
    # Price action improving: perf_1w > 0 or green close
    perf_5d_ok = (t.perf_1w is not None and t.perf_1w >= 0) or (
        t.change_from_open_percent is not None and t.change_from_open_percent > 0
    )
    rel_vol_ok = t.breakout_volume_multiple is not None and t.breakout_volume_multiple >= 1.2
    # Not in active crash (SMA200 not steeply falling)
    sma200_not_crashing = t.sma200_slope is None or t.sma200_slope >= -0.5

    if rsi_in_rebound_range and rsi_turning_up and perf_5d_ok and rel_vol_ok and sma200_not_crashing:
        return "OVERSOLD_REBOUND_CANDIDATE"

    # --- Check BROKEN_SUPPORT_AVOID ---
    heavy_vol_break = t.volume_dryup_ratio is not None and t.volume_dryup_ratio > 1.5
    weak_close = t.change_from_open_percent is not None and t.change_from_open_percent < -1.0
    rsi_falling = rsi is not None and rsi < 40.0 and (rsi_slope is None or rsi_slope < 0)

    if heavy_vol_break and weak_close and rsi_falling:
        return "BROKEN_SUPPORT_AVOID"

    # --- Default: TRUE_DOWNTREND_AVOID ---
    return "TRUE_DOWNTREND_AVOID"


def _rs_continuation_ok(technicals: TechnicalIndicators) -> bool:
    """Return True when RS vs SPY and sector is positive for all periods (continuation buy).

    If all RS fields are None (data unavailable), returns True (permissive — don't
    block signal when we cannot measure it).  If any available field is negative, block.
    """
    t = technicals
    spy20 = t.rs_vs_spy_20d
    spy63 = t.rs_vs_spy_63d
    sector20 = t.rs_vs_sector_20d
    # All None → no RS data available, don't block
    if spy20 is None and spy63 is None and sector20 is None:
        return True
    # Any available field negative → block
    if spy20 is not None and spy20 <= 0:
        return False
    if spy63 is not None and spy63 <= 0:
        return False
    if sector20 is not None and sector20 <= 0:
        return False
    return True


def _rs_leader(technicals: TechnicalIndicators) -> bool:
    """Return True when stock is clearly outperforming (leader) across all RS dimensions."""
    t = technicals
    spy20 = t.rs_vs_spy_20d
    spy63 = t.rs_vs_spy_63d
    sector20 = t.rs_vs_sector_20d
    if spy20 is None or spy63 is None or sector20 is None:
        return False
    return spy20 >= 3.0 and spy63 >= 5.0 and sector20 >= 2.0


def _rs_avoid(technicals: TechnicalIndicators) -> bool:
    """Return True when RS is weak enough to warrant avoidance."""
    t = technicals
    spy20 = t.rs_vs_spy_20d
    spy63 = t.rs_vs_spy_63d
    sector20 = t.rs_vs_sector_20d
    if spy20 is not None and spy20 < -5.0:
        return True
    if spy63 is not None and spy63 < -10.0:
        return True
    if sector20 is not None and sector20 < -5.0:
        return True
    return False


def _perf_gates(technicals: TechnicalIndicators, context: str) -> bool:
    """Gate performance-based filters.

    context == "continuation": returns True if perf is in ideal continuation range
    context == "chasing":      returns True if performance is too hot (chasing signal)
    context == "rebound":      returns True if stock has been weak enough for rebound setup
    """
    t = technicals
    p1w = t.perf_1w
    p1m = t.perf_1m
    rsi_slope = t.rsi_slope

    if context == "continuation":
        if p1w is None or p1m is None:
            return True  # insufficient data → don't block
        return 0.0 <= p1w <= 6.0 and 3.0 <= p1m <= 15.0

    if context == "chasing":
        if p1w is not None and p1w > 10.0:
            return True
        if p1m is not None and p1m > 25.0:
            return True
        return False

    if context == "rebound":
        if p1m is None:
            return False
        rebound_weakness = p1m < -10.0
        improving = (p1w is not None and p1w >= -1.0) or (rsi_slope is not None and rsi_slope > 0)
        return rebound_weakness and improving

    return False


def _is_pullback_to_sma50(
    technicals: TechnicalIndicators,
    archetype: Optional[str] = None,
) -> bool:
    """Return True when price is in a clean pullback-to-SMA50 zone.

    Standard criteria:
    - sma50_relative in [-3%, +5%]
    - sma20_relative <= +8%
    - RSI between 40 and 58
    - RSI slope >= -2 (stabilizing or rising)
    - perf_1m >= -12%
    - perf_3m > 0
    - volume_dryup_ratio < 0.85
    - rs_vs_sector_20d >= -3%
    - price above SMA200 (sma200_relative > -100 is always true; use trend)
    - SMA50 slope >= 0

    Hyper-growth override (archetype == "HYPER_GROWTH"):
    - sma50_relative in [-5%, +8%]
    - RSI between 38 and 62
    """
    t = technicals

    # SMA50 distance boundaries
    if archetype == "HYPER_GROWTH":
        sma50_low, sma50_high = -5.0, 8.0
        rsi_low, rsi_high = 38.0, 62.0
    else:
        sma50_low, sma50_high = -3.0, 5.0
        rsi_low, rsi_high = 40.0, 58.0

    # SMA50 distance check
    if t.sma50_relative is None:
        return False
    if not (sma50_low <= t.sma50_relative <= sma50_high):
        return False

    # SMA20 not too extended
    if t.sma20_relative is not None and t.sma20_relative > 8.0:
        return False

    # RSI range
    if t.rsi_14 is None:
        return False
    if not (rsi_low <= t.rsi_14 <= rsi_high):
        return False

    # RSI slope stabilizing or rising
    if t.rsi_slope is not None and t.rsi_slope < -2.0:
        return False

    # 1M return not worse than -12%
    if t.perf_1m is not None and t.perf_1m < -12.0:
        return False

    # 3M return positive
    if t.perf_3m is not None and t.perf_3m <= 0:
        return False

    # Volume dry-up: pullback should have drying volume
    if t.volume_dryup_ratio is not None and t.volume_dryup_ratio >= 0.85:
        return False

    # RS vs sector not too weak
    if t.rs_vs_sector_20d is not None and t.rs_vs_sector_20d < -3.0:
        return False

    # SMA50 slope should be non-negative (not a falling 50MA)
    if t.sma50_slope is not None and t.sma50_slope < 0:
        return False

    return True


def _build_factors(
    technicals: TechnicalIndicators,
    fundamentals: FundamentalData,
    valuation: ValuationData,
    earnings: EarningsData,
    news: NewsSummary,
    horizon: str,
    regime: Optional[MarketRegimeAssessment] = None,
) -> tuple[list[str], list[str]]:
    bullish: list[str] = []
    bearish: list[str] = []
    bull_regime = _is_bull_regime(regime)

    # Technical factors
    trend_label = technicals.trend.label
    if trend_label == "strong_uptrend":
        bullish.append("Strong uptrend: price above 50MA and 200MA with golden cross")
    elif trend_label == "downtrend":
        bearish.append("Downtrend: price below key moving averages")

    if technicals.rsi_14 is not None:
        if 50 <= technicals.rsi_14 <= 70:
            bullish.append(f"RSI at {technicals.rsi_14:.1f} — healthy momentum")
        elif technicals.rsi_14 > 75:
            bearish.append(f"RSI at {technicals.rsi_14:.1f} — overbought territory")
        elif technicals.rsi_14 < 35:
            bearish.append(f"RSI at {technicals.rsi_14:.1f} — oversold / weak momentum")

    if technicals.macd_histogram is not None:
        if technicals.macd_histogram > 0:
            bullish.append("MACD histogram positive — bullish momentum")
        else:
            bearish.append("MACD histogram negative — bearish momentum")

    if technicals.is_extended:
        bearish.append("Stock is extended above key moving averages — poor risk/reward entry")

    if technicals.volume_trend == "above_average":
        bullish.append("Volume above 30-day average — institutional interest")
    elif technicals.volume_trend == "below_average":
        bearish.append("Volume below average — weak conviction")

    if technicals.rs_vs_spy is not None:
        if technicals.rs_vs_spy > 1.2:
            bullish.append("Strong relative strength vs S&P 500")
        elif technicals.rs_vs_spy < 0.8:
            bearish.append("Underperforming S&P 500 in relative terms")

    # Fundamental factors (medium/long-term emphasis)
    if horizon in ("medium_term", "long_term"):
        fg = fundamentals.revenue_growth_yoy
        if fg is not None:
            if fg >= 0.15:
                bullish.append(f"Revenue growth {fg*100:.0f}% YoY — strong top-line")
            elif fg < 0:
                bearish.append(f"Revenue declining {abs(fg)*100:.0f}% YoY")

        if fundamentals.free_cash_flow is not None:
            if fundamentals.free_cash_flow > 0:
                bullish.append("Positive free cash flow")
            else:
                bearish.append("Negative free cash flow — cash burn risk")

        if fundamentals.net_debt is not None and fundamentals.net_debt < 0:
            bullish.append("Net cash position — strong balance sheet")

    # Valuation factors — regime-aware
    if horizon in ("medium_term", "long_term"):
        fpe = valuation.forward_pe
        if fpe is not None:
            if fpe <= 20:
                bullish.append(f"Forward P/E of {fpe:.1f}x — reasonable valuation")
            elif fpe > 40 and not bull_regime:
                bearish.append(f"Forward P/E of {fpe:.1f}x — extended valuation")
            elif fpe > 40 and bull_regime:
                bearish.append(f"Forward P/E of {fpe:.1f}x — elevated but regime is supportive")
        peg = valuation.peg_ratio
        if peg is not None and peg <= 1.5:
            bullish.append(f"PEG ratio {peg:.2f} — growth at reasonable price")

    # Regime factor
    if regime is not None:
        if _is_bull_regime(regime):
            bullish.append(f"Market regime: {regime.regime} — supports growth/momentum stocks")
        elif _is_bear_regime(regime):
            bearish.append(f"Market regime: {regime.regime} — risk-off environment")

    # Earnings factors
    if earnings.beat_rate is not None:
        if earnings.beat_rate >= 0.75:
            bullish.append(f"Consistent earnings beats ({earnings.beat_rate*100:.0f}% beat rate)")
        elif earnings.beat_rate < 0.40:
            bearish.append("Poor earnings beat history")
    if earnings.within_30_days:
        bearish.append("Earnings within 30 days — binary event risk")

    # News/sentiment
    if news.positive_count > news.negative_count:
        bullish.append(f"Mostly positive recent news ({news.positive_count} positive headlines)")
    elif news.negative_count > news.positive_count:
        bearish.append(f"Mostly negative recent news ({news.negative_count} negative headlines)")

    return bullish[:5], bearish[:5]


def _decide_short_term(
    score: float,
    technicals: TechnicalIndicators,
    fundamentals: Optional[FundamentalData] = None,
    earnings: Optional[EarningsData] = None,
    regime: Optional[MarketRegimeAssessment] = None,
) -> str:
    bull = _is_bull_regime(regime)
    bear = _is_bear_regime(regime)

    # Bad chart override — always applies regardless of regime
    if _chart_is_weak(technicals) and score < 55:
        return "AVOID_BAD_CHART"

    # Business deterioration check
    if fundamentals is not None and earnings is not None:
        if _business_deteriorating(fundamentals, earnings) and score < 55:
            return "AVOID_BAD_BUSINESS"

    # Upcoming earnings — wait for confirmation if already uncertain
    if earnings is not None and earnings.within_30_days and 55 <= score < 70:
        return "BUY_AFTER_EARNINGS"

    if score >= 80 and not technicals.is_extended:
        sr = technicals.support_resistance
        if sr.nearest_support:
            return "BUY_NOW"
        return "BUY_STARTER"

    # Extended stock handling — regime-aware
    if technicals.is_extended and score >= 65:
        if bull:
            return "BUY_STARTER_EXTENDED"  # Bull regime: still buyable, just smaller size
        return "BUY_ON_PULLBACK"            # Non-bull: wait for pullback

    if 70 <= score < 80:
        return "BUY_STARTER"
    if score >= 65:
        return "BUY_ON_PULLBACK"

    if score < 50:
        # In bear regime, be more specific about why
        if bear and _chart_is_weak(technicals):
            return "AVOID_BAD_CHART"
        return "AVOID"

    return "WATCHLIST"


def _decide_medium_term(
    score: float,
    technicals: TechnicalIndicators,
    earnings: EarningsData,
    fundamentals: Optional[FundamentalData] = None,
    regime: Optional[MarketRegimeAssessment] = None,
) -> str:
    # Bad business override
    if fundamentals is not None and _business_deteriorating(fundamentals, earnings):
        if score < 65:
            return "AVOID_BAD_BUSINESS"

    if _chart_is_weak(technicals) and score < 55:
        return "AVOID_BAD_CHART"

    if score >= 82 and not technicals.is_extended:
        return "BUY_NOW"
    if 72 <= score < 82 or (score >= 82 and technicals.is_extended):
        return "BUY_STARTER"
    if score >= 68 and technicals.is_extended:
        return "BUY_STARTER_EXTENDED" if _is_bull_regime(regime) else "BUY_ON_PULLBACK"
    if score >= 68:
        return "BUY_ON_PULLBACK"
    if 55 <= score < 68:
        return "WATCHLIST"
    return "AVOID"


def _decide_long_term(
    score: float,
    technicals: TechnicalIndicators,
    fundamentals: Optional[FundamentalData] = None,
    earnings: Optional[EarningsData] = None,
    regime: Optional[MarketRegimeAssessment] = None,
) -> str:
    if fundamentals is not None and earnings is not None:
        if _business_deteriorating(fundamentals, earnings):
            if score < 65:
                return "AVOID_BAD_BUSINESS"

    if _chart_is_weak(technicals) and score < 60:
        return "AVOID_BAD_CHART"

    if score >= 85 and not technicals.is_extended:
        return "BUY_NOW"
    if 75 <= score < 85:
        return "BUY_STARTER"
    if score >= 75 and technicals.is_extended:
        return "BUY_ON_BREAKOUT"
    if 60 <= score < 75:
        return "WATCHLIST"
    return "AVOID"


def _decide_short_term_v2(
    score: float,
    technicals: TechnicalIndicators,
    regime: Optional[MarketRegimeAssessment] = None,
    archetype: Optional[str] = None,
    algo_config: Optional[AlgoConfig] = None,
) -> str:
    """Short-term decision labels with strict Improvements-3 criteria.

    Priority order:
    1. Avoid / confidence overrides
    2. Oversold rebound candidate
    3. BUY_NOW_CONTINUATION (all strict gates must pass)
    4. BUY_STARTER_STRONG_BUT_EXTENDED (extended but buyable)
    5. WAIT_FOR_PULLBACK (chasing / overextended)
    6. BUY_ON_PULLBACK (precise SMA50 pullback criteria)
    7. WATCHLIST / fallback avoids
    """
    t = technicals
    regime_str = regime.regime if regime is not None else MarketRegime.BULL_RISK_ON
    thresholds = _get_regime_thresholds(regime_str, algo_config=algo_config)

    # --- 1. Bad chart / avoid overrides ---
    if _chart_is_weak(t) and score < 50:
        return _classify_bad_chart(t)
    if score < 40:
        return _classify_bad_chart(t)

    # --- 2. Oversold rebound candidate (even for low scores) ---
    if (
        t.rsi_14 is not None and 25.0 <= t.rsi_14 <= 42.0
        and t.rsi_slope is not None and t.rsi_slope > 0
        and (
            (t.perf_1w is not None and t.perf_1w >= 0)
            or (t.change_from_open_percent is not None and t.change_from_open_percent > 0)
        )
        and t.breakout_volume_multiple is not None and t.breakout_volume_multiple >= 1.2
    ):
        return "OVERSOLD_REBOUND_CANDIDATE"

    # --- WAIT_FOR_PULLBACK: chasing / over-extended gates (check before scoring gates) ---
    is_chasing = _perf_gates(t, "chasing")
    sma20_above_10 = t.sma20_relative is not None and t.sma20_relative > 10.0
    rsi_too_hot = t.rsi_14 is not None and t.rsi_14 > 72.0
    if is_chasing or sma20_above_10:
        return "WAIT_FOR_PULLBACK"

    # --- 3. BUY_ON_PULLBACK priority in SIDEWAYS_CHOPPY ---
    # In sideways regimes, prefer pullback entries over continuation buys
    if regime_str == MarketRegime.SIDEWAYS_CHOPPY and score >= 55:
        if _is_pullback_to_sma50(t, archetype=archetype):
            return "BUY_ON_PULLBACK"

    # --- 3. BUY_NOW_CONTINUATION (all gates must pass) ---
    if score >= 70 and not t.is_extended:
        rsi = t.rsi_14
        sma20 = t.sma20_relative
        sma50 = t.sma50_relative
        rsi_slope = t.rsi_slope
        rel_vol = t.breakout_volume_multiple

        rsi_ok = rsi is None or (thresholds.rsi_min <= rsi <= thresholds.rsi_max)
        sma20_ok = sma20 is None or (0.0 <= sma20 <= thresholds.sma20_max)
        sma50_ok = sma50 is None or sma50 <= 12.0
        slopes_ok = (t.sma20_slope is None or t.sma20_slope >= 0) and (
            t.sma50_slope is None or t.sma50_slope >= 0
        )
        rsi_slope_ok = rsi_slope is None or rsi_slope >= 0
        vol_ok = rel_vol is None or rel_vol >= thresholds.rel_vol_min
        rs_ok = _rs_continuation_ok(t)
        # In BULL_NARROW_LEADERSHIP, require leader RS
        if regime_str == MarketRegime.BULL_NARROW_LEADERSHIP:
            rs_ok = _rs_leader(t)
        perf_ok = _perf_gates(t, "continuation")

        if rsi_ok and sma20_ok and sma50_ok and slopes_ok and rsi_slope_ok and vol_ok and rs_ok and perf_ok:
            return "BUY_NOW_CONTINUATION"

        # Not all gates passed — fall through to extended / pullback checks

    # --- 4. BUY_STARTER_STRONG_BUT_EXTENDED ---
    if score >= 70:
        sma20 = t.sma20_relative
        rsi = t.rsi_14
        extended_sma20 = sma20 is not None and 5.0 < sma20 <= 10.0
        extended_rsi = rsi is not None and thresholds.rsi_max < rsi <= 76.0
        if t.is_extended or extended_sma20 or extended_rsi:
            return "BUY_STARTER_STRONG_BUT_EXTENDED"

        # High score but RS or perf gate failed → prefer pullback
        if _is_pullback_to_sma50(t, archetype=archetype):
            return "BUY_ON_PULLBACK"
        return "WAIT_FOR_PULLBACK"

    # --- 5. WAIT_FOR_PULLBACK (overbought RSI, score 55-70) ---
    if score >= 55 and rsi_too_hot:
        return "WAIT_FOR_PULLBACK"

    # --- 6. BUY_ON_PULLBACK (score 55+ with precise pullback criteria) ---
    if score >= 55 and _is_pullback_to_sma50(t, archetype=archetype):
        return "BUY_ON_PULLBACK"

    # --- 7. Fallback ---
    if score >= 55:
        return "WAIT_FOR_PULLBACK"
    return "WATCHLIST"


def _decide_medium_term_v2(
    score: float,
    technicals: TechnicalIndicators,
    fundamentals: Optional[FundamentalData],
    earnings: EarningsData,
    algo_config: Optional[AlgoConfig] = None,
) -> str:
    """New medium-term decision labels (Story 7)."""
    cfg = algo_config or get_algo_config()
    dl = cfg.decision_logic
    buy_now_min = dl["medium_term_buy_now_min"]
    buy_starter_min = dl["medium_term_buy_starter_min"]
    watchlist_min = dl["medium_term_watchlist_min"]

    if fundamentals is not None and _business_deteriorating(fundamentals, earnings) and score < buy_starter_min:
        return "AVOID_BAD_BUSINESS"
    if score >= buy_now_min:
        if not technicals.is_extended:
            return "BUY_NOW"
        return "BUY_STARTER"
    if score >= buy_starter_min:
        if technicals.is_extended:
            return "BUY_ON_PULLBACK"
        return "BUY_STARTER"
    if score >= watchlist_min:
        return "WATCHLIST_NEEDS_CONFIRMATION"
    return "AVOID_BAD_BUSINESS"


def _decide_long_term_v2(
    score: float,
    fundamentals: Optional[FundamentalData],
    earnings: Optional[EarningsData],
    valuation_score: Optional[float],
    algo_config: Optional[AlgoConfig] = None,
) -> str:
    """New long-term decision labels (Story 7)."""
    cfg = algo_config or get_algo_config()
    dl = cfg.decision_logic
    buy_now_min = dl["long_term_buy_now_min"]
    accumulate_min = dl["long_term_accumulate_min"]
    watchlist_min = dl["long_term_watchlist_min"]
    val_gate = dl["long_term_valuation_gate"]
    val_score_gate = dl["long_term_valuation_score_gate"]

    if fundamentals is not None and earnings is not None:
        if _business_deteriorating(fundamentals, earnings) and score < accumulate_min:
            return "AVOID_LONG_TERM"
    # Expensive valuation relative to score
    if valuation_score is not None and valuation_score < val_gate and score < val_score_gate:
        return "WATCHLIST_VALUATION_TOO_RICH"
    if score >= buy_now_min:
        return "BUY_NOW_LONG_TERM"
    if score >= accumulate_min:
        return "ACCUMULATE_ON_WEAKNESS"
    if score >= watchlist_min:
        return "WATCHLIST_VALUATION_TOO_RICH"
    return "AVOID_LONG_TERM"


def _summary(decision: str, score: float, horizon: str, technicals: TechnicalIndicators) -> str:
    hor = horizon.replace("_", "-")
    summaries = {
        # Improvements 3: new precise labels
        "BUY_NOW_CONTINUATION": f"Tight momentum continuation signal. Score {score:.0f}/100 — RSI 55-68, within 5% of SMA20, positive RS. Entry timing is ideal.",
        "OVERSOLD_REBOUND_CANDIDATE": f"Oversold rebound setup. Score {score:.0f}/100 — RSI turning up from 25-42, selling pressure fading. Small position, tight stop.",
        "TRUE_DOWNTREND_AVOID": f"Confirmed downtrend. Score {score:.0f}/100 — price below both SMAs, death cross, weak RS. Avoid until trend repairs.",
        "BROKEN_SUPPORT_AVOID": f"Heavy-volume support break. Score {score:.0f}/100 — price broke key support on high volume with weak close. Stand aside.",
        # Story 7 labels
        "BUY_STARTER_STRONG_BUT_EXTENDED": f"Strong {hor} setup but price is extended. Score {score:.0f}/100. Start with a half position and add on pullback.",
        "WAIT_FOR_PULLBACK": f"Good setup but not an ideal entry. Score {score:.0f}/100. Wait for a pullback to moving average support.",
        "ACCUMULATE_ON_WEAKNESS": f"Strong long-term thesis. Score {score:.0f}/100. Accumulate gradually on any weakness.",
        "BUY_NOW_LONG_TERM": f"Excellent long-term setup. Score {score:.0f}/100 — quality business at a reasonable valuation.",
        "WATCHLIST_NEEDS_CONFIRMATION": f"Improving picture but needs confirmation. Score {score:.0f}/100. Add to watchlist and monitor catalysts.",
        "WATCHLIST_VALUATION_TOO_RICH": f"Good business but valuation is stretched for a long-term entry. Score {score:.0f}/100. Wait for better pricing.",
        "AVOID_LONG_TERM": f"Not suitable for long-term holding. Score {score:.0f}/100 — deteriorating fundamentals or excessive valuation.",
        # Original labels
        "BUY_NOW": f"Strong setup across {hor} indicators. Score {score:.0f}/100 — favorable risk/reward.",
        "BUY_STARTER": f"Promising {hor} thesis. Score {score:.0f}/100. Consider a starter position and add on pullbacks.",
        "BUY_STARTER_EXTENDED": f"Strong {hor} setup but price is extended. Score {score:.0f}/100. Regime is supportive — use a smaller starter position.",
        "BUY_ON_PULLBACK": f"Good {hor} setup but {'price extended above moving averages.' if technicals.is_extended else 'entry timing is imperfect.'} Score {score:.0f}/100. Wait for pullback to key moving average.",
        "BUY_ON_BREAKOUT": f"Long-term thesis is strong but extension limits entry now. Score {score:.0f}/100. Buy on confirmed breakout with volume.",
        "BUY_AFTER_EARNINGS": f"Setup looks promising but earnings event is near. Score {score:.0f}/100. Wait for earnings confirmation before entering.",
        "WATCHLIST": f"Some positives but confirmation is missing. Score {score:.0f}/100. Add to watchlist and monitor.",
        "WATCHLIST_NEEDS_CATALYST": f"Setup is building but needs a catalyst. Score {score:.0f}/100. Watch for an upgrade, guidance raise, or technical breakout.",
        "HOLD_EXISTING_DO_NOT_ADD": f"Existing position is fine but don't chase here. Score {score:.0f}/100.",
        "AVOID_BAD_BUSINESS": f"Business fundamentals are deteriorating. Score {score:.0f}/100. Revenue declining and/or margins compressing — avoid new positions.",
        "AVOID_BAD_CHART": f"Technical picture is weak. Score {score:.0f}/100. Price below key moving averages with weak relative strength — wait for repair.",
        "AVOID_BAD_RISK_REWARD": f"Risk/reward is unfavorable. Score {score:.0f}/100. Upside does not justify downside at current entry.",
        "AVOID_LOW_CONFIDENCE": f"Insufficient data for reliable recommendation. Score {score:.0f}/100. Proceed with caution.",
        "AVOID": f"Score {score:.0f}/100 — multiple negative signals. Risk outweighs potential reward.",
    }
    return summaries.get(decision, f"Score {score:.0f}/100.")


def build_recommendations(
    technicals: TechnicalIndicators,
    fundamentals: FundamentalData,
    valuation: ValuationData,
    earnings: EarningsData,
    news: NewsSummary,
    scores: dict[str, dict[str, float]],
    horizons: list[str],
    risk_profile: str,
    current_price: float,
    regime_assessment: Optional[MarketRegimeAssessment] = None,
    has_options_data: bool = False,
    has_sufficient_price_history: bool = True,
    signal_cards: Optional[SignalCards] = None,
    algo_config: Optional[AlgoConfig] = None,
) -> list[HorizonRecommendation]:
    recs: list[HorizonRecommendation] = []

    completeness, confidence_score, completeness_warnings = compute_completeness(
        news=news,
        earnings=earnings,
        valuation=valuation,
        has_options_data=has_options_data,
        has_sufficient_price_history=has_sufficient_price_history,
    )

    for horizon in horizons:
        if horizon not in scores:
            continue
        horizon_scores = scores[horizon]
        composite = horizon_scores["composite"]

        # Determine signal card weights for this horizon (from scores dict if available)
        horizon_weights: dict[str, float] = {}
        if "weights" in horizon_scores:
            horizon_weights = {k: float(v) for k, v in horizon_scores["weights"].items()}

        # Use signal-card-based decision logic when signal cards provided
        val_score = None
        if signal_cards is not None:
            val_score = signal_cards.valuation.score

        if completeness < AVOID_LOW_CONFIDENCE_THRESHOLD:
            decision = "AVOID_LOW_CONFIDENCE"
        elif signal_cards is not None:
            # New signal-card-based decision logic (Story 7)
            if horizon == "short_term":
                decision = _decide_short_term_v2(composite, technicals, algo_config=algo_config)
            elif horizon == "medium_term":
                decision = _decide_medium_term_v2(composite, technicals, fundamentals, earnings, algo_config=algo_config)
            else:
                decision = _decide_long_term_v2(composite, fundamentals, earnings, val_score, algo_config=algo_config)
        elif horizon == "short_term":
            decision = _decide_short_term(composite, technicals, fundamentals, earnings, regime_assessment)
        elif horizon == "medium_term":
            decision = _decide_medium_term(composite, technicals, earnings, fundamentals, regime_assessment)
        else:
            decision = _decide_long_term(composite, technicals, fundamentals, earnings, regime_assessment)

        bullish, bearish = _build_factors(technicals, fundamentals, valuation, earnings, news, horizon, regime_assessment)
        summary = _summary(decision, composite, horizon, technicals)
        confidence = _confidence(composite)

        entry, exit_, rr, sizing = compute_risk_management(
            price=current_price,
            technicals=technicals,
            decision=decision,
            risk_profile=risk_profile,
            within_30_days_earnings=earnings.within_30_days,
        )

        warnings = list(completeness_warnings)
        if news.coverage_limited:
            warnings.append("News coverage may be limited — yfinance news data.")

        recs.append(
            HorizonRecommendation(
                horizon=horizon,
                decision=decision,
                score=composite,
                confidence=confidence,
                confidence_score=confidence_score,
                data_completeness_score=completeness,
                summary=summary,
                bullish_factors=bullish,
                bearish_factors=bearish,
                entry_plan=entry,
                exit_plan=exit_,
                risk_reward=rr,
                position_sizing=sizing,
                data_warnings=warnings,
                signal_cards_weights=horizon_weights,
            )
        )

    return recs
