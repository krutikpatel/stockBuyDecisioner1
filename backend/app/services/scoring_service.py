from __future__ import annotations

from typing import Optional

from app.models.market import MarketRegime, MarketRegimeAssessment, TechnicalIndicators
from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.services.market_regime_service import REGIME_WEIGHT_ADJUSTMENTS

# Horizon-specific weights — each dict must sum to 100.
# Keys map to intermediate scores derived inside compute_scores().

SHORT_TERM_WEIGHTS = {
    "technical_momentum": 30,
    "relative_strength":  20,
    "catalyst_news":      20,
    "options_flow":       10,
    "market_regime":      10,
    "risk_reward":        10,
}

MEDIUM_TERM_WEIGHTS = {
    "earnings_revision":          25,
    "growth_acceleration":        20,
    "technical_trend":            20,
    "sector_strength":            15,
    "valuation_relative_growth":  10,
    "catalyst_news":              10,
}

LONG_TERM_WEIGHTS = {
    "business_quality":           25,
    "growth_durability":          20,
    "fcf_quality":                15,
    "balance_sheet_strength":     15,
    "valuation_relative_growth":  15,
    "competitive_moat":           10,
}

_ALL_WEIGHT_DICTS = [SHORT_TERM_WEIGHTS, MEDIUM_TERM_WEIGHTS, LONG_TERM_WEIGHTS]


def _verify_weights() -> None:
    for w in _ALL_WEIGHT_DICTS:
        assert sum(w.values()) == 100, f"Weights do not sum to 100: {w}"


_verify_weights()


def _regime_score(assessment: Optional[MarketRegimeAssessment]) -> float:
    """Convert regime + confidence into a 0–100 score for SHORT_TERM market_regime slot."""
    if assessment is None:
        return 50.0
    regime = assessment.regime
    conf = assessment.confidence
    if regime == MarketRegime.BULL_RISK_ON:
        return 50.0 + conf * 0.35       # 50–85 range
    if regime == MarketRegime.BEAR_RISK_OFF:
        return 50.0 - conf * 0.35       # 15–50 range
    if regime in (MarketRegime.BULL_NARROW_LEADERSHIP, MarketRegime.LIQUIDITY_RALLY):
        return 50.0 + conf * 0.15
    if regime == MarketRegime.SIDEWAYS_CHOPPY:
        return 50.0
    return 50.0


def _apply_regime_multipliers(
    scores: dict[str, float],
    assessment: Optional[MarketRegimeAssessment],
) -> dict[str, float]:
    """Apply regime multipliers to individual scores (clamped to [0, 100])."""
    if assessment is None:
        return scores
    multipliers = REGIME_WEIGHT_ADJUSTMENTS.get(assessment.regime, {})
    if not multipliers:
        return scores
    adjusted = {}
    for key, val in scores.items():
        mult = multipliers.get(key, 1.0)
        adjusted[key] = round(max(0.0, min(100.0, val * mult)), 2)
    return adjusted


def _weighted_average(scores: dict[str, float], weights: dict[str, int]) -> float:
    total_weight = sum(weights.values())
    total_score = 0.0
    for key, w in weights.items():
        s = scores.get(key, 50.0)  # default 50 if score unavailable
        total_score += s * w
    return round(total_score / total_weight, 2)


def compute_scores(
    technicals: TechnicalIndicators,
    fundamentals: FundamentalData,
    valuation: ValuationData,
    earnings: EarningsData,
    news: NewsSummary,
    catalyst_score: float = 50.0,
    sector_macro_score: float = 50.0,
    risk_reward_score: float = 50.0,
    regime_assessment: Optional[MarketRegimeAssessment] = None,
) -> dict[str, dict[str, float]]:
    """Return per-horizon weighted composite scores with regime adjustments.

    Derives intermediate scores from input models and applies optional
    MarketRegimeAssessment multipliers before computing each composite.
    """
    # Growth-adjusted valuation: prefer archetype_adjusted_score if computed
    val_score = (
        valuation.archetype_adjusted_score
        if valuation.archetype_adjusted_score > 0
        else valuation.valuation_score
    )

    # Intermediate scores — mapped to weight dict keys
    # SHORT_TERM keys
    short_base: dict[str, float] = {
        "technical_momentum": technicals.technical_score,
        "relative_strength":  technicals.technical_score,  # refined in US-007
        "catalyst_news":      round((catalyst_score + news.news_score) / 2, 2),
        "options_flow":       catalyst_score,
        "market_regime":      _regime_score(regime_assessment),
        "risk_reward":        risk_reward_score,
    }

    # MEDIUM_TERM keys
    medium_base: dict[str, float] = {
        "earnings_revision":         earnings.earnings_score,
        "growth_acceleration":       fundamentals.fundamental_score,
        "technical_trend":           technicals.technical_score,
        "sector_strength":           sector_macro_score,
        "valuation_relative_growth": val_score,
        "catalyst_news":             round((catalyst_score + news.news_score) / 2, 2),
    }

    # LONG_TERM keys
    long_base: dict[str, float] = {
        "business_quality":          fundamentals.fundamental_score,
        "growth_durability":         fundamentals.fundamental_score,
        "fcf_quality":               fundamentals.fundamental_score,
        "balance_sheet_strength":    fundamentals.fundamental_score,
        "valuation_relative_growth": val_score,
        "competitive_moat":          fundamentals.fundamental_score,
    }

    # Apply regime multipliers to each horizon's score set
    short_adj = _apply_regime_multipliers(short_base, regime_assessment)
    medium_adj = _apply_regime_multipliers(medium_base, regime_assessment)
    long_adj = _apply_regime_multipliers(long_base, regime_assessment)

    # Also keep all raw sub-scores for diagnostic purposes
    all_raw = {
        "technical": technicals.technical_score,
        "fundamental": fundamentals.fundamental_score,
        "valuation": val_score,
        "earnings": earnings.earnings_score,
        "news_sentiment": news.news_score,
        "catalyst": catalyst_score,
        "sector_macro": sector_macro_score,
        "risk_reward": risk_reward_score,
    }

    return {
        "short_term": {
            "composite": _weighted_average(short_adj, SHORT_TERM_WEIGHTS),
            **all_raw,
            **short_adj,
        },
        "medium_term": {
            "composite": _weighted_average(medium_adj, MEDIUM_TERM_WEIGHTS),
            **all_raw,
            **medium_adj,
        },
        "long_term": {
            "composite": _weighted_average(long_adj, LONG_TERM_WEIGHTS),
            **all_raw,
            **long_adj,
        },
    }
