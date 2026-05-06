from __future__ import annotations

from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.market import TechnicalIndicators
from app.models.news import NewsSummary
from app.models.response import SignalCards, SignalProfile


def _momentum_label(technical_score: float, is_extended: bool) -> str:
    if technical_score >= 80 and not is_extended:
        return "VERY_BULLISH"
    if technical_score >= 65:
        return "BULLISH"
    if technical_score >= 50:
        return "NEUTRAL"
    if technical_score >= 35:
        return "BEARISH"
    return "VERY_BEARISH"


def _growth_label(fundamental_score: float) -> str:
    if fundamental_score >= 80:
        return "VERY_BULLISH"
    if fundamental_score >= 65:
        return "BULLISH"
    if fundamental_score >= 50:
        return "NEUTRAL"
    if fundamental_score >= 35:
        return "BEARISH"
    return "VERY_BEARISH"


def _valuation_label(valuation_score: float) -> str:
    if valuation_score >= 70:
        return "ATTRACTIVE"
    if valuation_score >= 55:
        return "FAIR"
    if valuation_score >= 40:
        return "ELEVATED"
    return "RISKY"


def _entry_label(technicals: TechnicalIndicators) -> str:
    ext_20 = technicals.extension_pct_above_20ma or 0.0
    if technicals.is_extended and ext_20 >= 15:
        return "VERY_EXTENDED"
    if technicals.is_extended:
        return "EXTENDED"
    trend = technicals.trend.label
    if trend == "strong_uptrend" and not technicals.is_extended:
        return "IDEAL"
    return "ACCEPTABLE"


def _sentiment_label(news_score: float) -> str:
    if news_score >= 75:
        return "VERY_BULLISH"
    if news_score >= 60:
        return "BULLISH"
    if news_score >= 40:
        return "NEUTRAL"
    if news_score >= 25:
        return "BEARISH"
    return "VERY_BEARISH"


def _risk_reward_label(earnings_score: float, technical_score: float) -> str:
    combined = (earnings_score + technical_score) / 2
    if combined >= 75:
        return "EXCELLENT"
    if combined >= 60:
        return "GOOD"
    if combined >= 45:
        return "ACCEPTABLE"
    return "POOR"


def build_signal_profile_from_cards(cards: SignalCards) -> SignalProfile:
    """Derive a SignalProfile from 11 signal card scores (Story 8)."""
    mom_score = cards.momentum.score
    growth_score = cards.growth.score
    val_score = cards.valuation.score
    entry_score = cards.entry_timing.score
    catalyst_score = cards.catalyst.score
    vol_score = cards.volatility_risk.score

    def _bullbear(score: float) -> str:
        if score >= 80:
            return "VERY_BULLISH"
        if score >= 60:
            return "BULLISH"
        if score >= 40:
            return "NEUTRAL"
        if score >= 20:
            return "BEARISH"
        return "VERY_BEARISH"

    def _val_label(score: float) -> str:
        if score >= 70:
            return "ATTRACTIVE"
        if score >= 55:
            return "FAIR"
        if score >= 40:
            return "ELEVATED"
        return "RISKY"

    def _entry_label(score: float) -> str:
        if score >= 75:
            return "IDEAL"
        if score >= 55:
            return "ACCEPTABLE"
        if score >= 35:
            return "EXTENDED"
        return "VERY_EXTENDED"

    def _risk_label(score: float) -> str:
        if score >= 75:
            return "EXCELLENT"
        if score >= 60:
            return "GOOD"
        if score >= 45:
            return "ACCEPTABLE"
        return "POOR"

    return SignalProfile(
        momentum=_bullbear(mom_score),
        growth=_bullbear(growth_score),
        valuation=_val_label(val_score),
        entry_timing=_entry_label(entry_score),
        sentiment=_bullbear(catalyst_score),
        risk_reward=_risk_label(vol_score),
    )


def build_signal_profile(
    technicals: TechnicalIndicators,
    fundamentals: FundamentalData,
    valuation: ValuationData,
    earnings: EarningsData,
    news: NewsSummary,
) -> SignalProfile:
    """Derive a human-readable signal profile from model sub-scores."""
    val_score = (
        valuation.archetype_adjusted_score
        if valuation.archetype_adjusted_score > 0
        else valuation.valuation_score
    )

    return SignalProfile(
        momentum=_momentum_label(technicals.technical_score, technicals.is_extended),
        growth=_growth_label(fundamentals.fundamental_score),
        valuation=_valuation_label(val_score),
        entry_timing=_entry_label(technicals),
        sentiment=_sentiment_label(news.news_score),
        risk_reward=_risk_reward_label(earnings.earnings_score, technicals.technical_score),
    )
