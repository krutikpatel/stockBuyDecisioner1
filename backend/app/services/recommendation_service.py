from __future__ import annotations

from typing import Optional

from app.models.market import TechnicalIndicators
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import HorizonRecommendation
from app.services.risk_management_service import compute_risk_management


def _confidence(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 65:
        return "medium_high"
    if score >= 50:
        return "medium"
    return "low"


def _build_factors(
    technicals: TechnicalIndicators,
    fundamentals: FundamentalData,
    valuation: ValuationData,
    earnings: EarningsData,
    news: NewsSummary,
    horizon: str,
) -> tuple[list[str], list[str]]:
    bullish: list[str] = []
    bearish: list[str] = []

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

    # Valuation factors
    if horizon in ("medium_term", "long_term"):
        fpe = valuation.forward_pe
        if fpe is not None:
            if fpe <= 20:
                bullish.append(f"Forward P/E of {fpe:.1f}x — reasonable valuation")
            elif fpe > 40:
                bearish.append(f"Forward P/E of {fpe:.1f}x — extended valuation")
        peg = valuation.peg_ratio
        if peg is not None and peg <= 1.5:
            bullish.append(f"PEG ratio {peg:.2f} — growth at reasonable price")

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


def _decide_short_term(score: float, technicals: TechnicalIndicators) -> str:
    """Decision rules per §7.1."""
    if score >= 80 and not technicals.is_extended:
        sr = technicals.support_resistance
        if sr.nearest_support:
            return "BUY_NOW"
        return "BUY_STARTER"
    # Extended stock → wait for pullback regardless of score (§8.2 rule)
    if technicals.is_extended and score >= 65:
        return "WAIT_FOR_PULLBACK"
    if 70 <= score < 80:
        return "BUY_STARTER"
    if score >= 65:
        return "WAIT_FOR_PULLBACK"
    if score < 50:
        return "AVOID"
    return "WATCHLIST"


def _decide_medium_term(score: float, technicals: TechnicalIndicators, earnings: EarningsData) -> str:
    """Decision rules per §7.2."""
    if score >= 82 and not technicals.is_extended:
        return "BUY_NOW"
    if 72 <= score < 82 or (score >= 82 and technicals.is_extended):
        return "BUY_STARTER"
    if score >= 68 and technicals.is_extended:
        return "WAIT_FOR_PULLBACK"
    if score >= 68:
        return "WAIT_FOR_PULLBACK"
    if 55 <= score < 68:
        return "WATCHLIST"
    return "AVOID"


def _decide_long_term(score: float, technicals: TechnicalIndicators) -> str:
    """Decision rules per §7.3."""
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
    summaries = {
        "BUY_NOW": f"Strong setup across {horizon.replace('_', '-')} indicators. Score {score:.0f}/100 — favorable risk/reward.",
        "BUY_STARTER": f"Promising {horizon.replace('_', '-')} thesis. Score {score:.0f}/100. Consider a starter position and add on pullbacks.",
        "WAIT_FOR_PULLBACK": f"Good fundamentals but {'price extended above moving averages.' if technicals.is_extended else 'entry timing is imperfect.'} Score {score:.0f}/100. Wait for a better entry.",
        "BUY_ON_BREAKOUT": f"Long-term thesis is strong but valuation or extension limits entry now. Score {score:.0f}/100. Buy on confirmed breakout.",
        "WATCHLIST": f"Some positives but confirmation is missing. Score {score:.0f}/100. Add to watchlist and monitor.",
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
) -> list[HorizonRecommendation]:
    recs: list[HorizonRecommendation] = []

    for horizon in horizons:
        if horizon not in scores:
            continue
        horizon_scores = scores[horizon]
        composite = horizon_scores["composite"]

        if horizon == "short_term":
            decision = _decide_short_term(composite, technicals)
        elif horizon == "medium_term":
            decision = _decide_medium_term(composite, technicals, earnings)
        else:
            decision = _decide_long_term(composite, technicals)

        bullish, bearish = _build_factors(technicals, fundamentals, valuation, earnings, news, horizon)
        summary = _summary(decision, composite, horizon, technicals)
        confidence = _confidence(composite)

        entry, exit_, rr, sizing = compute_risk_management(
            price=current_price,
            technicals=technicals,
            decision=decision,
            risk_profile=risk_profile,
            within_30_days_earnings=earnings.within_30_days,
        )

        warnings: list[str] = []
        if valuation.peer_comparison_available is False:
            warnings.append("Peer valuation comparison unavailable.")
        if news.coverage_limited:
            warnings.append("News coverage may be limited — yfinance news data.")
        if earnings.next_earnings_date is None:
            warnings.append("Next earnings date could not be determined.")

        recs.append(
            HorizonRecommendation(
                horizon=horizon,
                decision=decision,
                score=composite,
                confidence=confidence,
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
