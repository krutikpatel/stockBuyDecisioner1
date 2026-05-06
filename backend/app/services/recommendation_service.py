from __future__ import annotations

from typing import Optional

from app.models.market import MarketRegime, MarketRegimeAssessment, TechnicalIndicators
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import HorizonRecommendation
from app.services.risk_management_service import compute_risk_management
from app.services.data_completeness_service import (
    compute_completeness,
    AVOID_LOW_CONFIDENCE_THRESHOLD,
)

# All valid decision labels (US-005 expansion)
ALL_DECISIONS = {
    "BUY_NOW",
    "BUY_STARTER",
    "BUY_STARTER_EXTENDED",   # strong but extended; smaller position
    "BUY_ON_PULLBACK",        # wait for MA retest
    "BUY_ON_BREAKOUT",        # consolidating near resistance
    "BUY_AFTER_EARNINGS",     # wait for earnings confirmation
    "WATCHLIST",
    "WATCHLIST_NEEDS_CATALYST",
    "HOLD_EXISTING_DO_NOT_ADD",
    "AVOID",                  # generic (backward compat)
    "AVOID_BAD_BUSINESS",     # deteriorating fundamentals
    "AVOID_BAD_CHART",        # price below 50DMA + 200DMA, weak RS
    "AVOID_BAD_RISK_REWARD",  # risk/reward < 1:1
    "AVOID_LOW_CONFIDENCE",   # missing critical data
}


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


def _summary(decision: str, score: float, horizon: str, technicals: TechnicalIndicators) -> str:
    hor = horizon.replace("_", "-")
    summaries = {
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

        if completeness < AVOID_LOW_CONFIDENCE_THRESHOLD:
            decision = "AVOID_LOW_CONFIDENCE"
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
            )
        )

    return recs
