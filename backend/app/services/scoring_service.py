from __future__ import annotations

from typing import Optional

from app.models.market import MarketRegime, MarketRegimeAssessment, TechnicalIndicators
from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import SignalCards
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


# ---------------------------------------------------------------------------
# Signal-card-based horizon weights (Story 7)
# Keys are signal card names from SignalCards model
# ---------------------------------------------------------------------------

SIGNAL_CARD_SHORT_WEIGHTS: dict[str, int] = {
    "momentum": 25,
    "volume_accumulation": 20,
    "entry_timing": 20,
    "relative_strength": 15,
    "volatility_risk": 10,
    "catalyst": 10,
}

SIGNAL_CARD_MEDIUM_WEIGHTS: dict[str, int] = {
    "trend": 20,
    "growth": 20,
    "relative_strength": 15,
    "volume_accumulation": 15,
    "valuation": 10,
    "quality": 10,
    "catalyst": 10,
}

SIGNAL_CARD_LONG_WEIGHTS: dict[str, int] = {
    "growth": 20,
    "quality": 20,
    "valuation": 15,
    "ownership": 15,
    "trend": 10,
    "catalyst": 10,
    "volatility_risk": 5,
    "momentum": 5,
}

assert sum(SIGNAL_CARD_SHORT_WEIGHTS.values()) == 100
assert sum(SIGNAL_CARD_MEDIUM_WEIGHTS.values()) == 100
assert sum(SIGNAL_CARD_LONG_WEIGHTS.values()) == 100


def _signal_card_composite(cards: SignalCards, weights: dict[str, int]) -> float:
    """Compute weighted composite from SignalCards and a weight dict."""
    total_score = 0.0
    total_weight = sum(weights.values())
    for card_name, weight in weights.items():
        card = getattr(cards, card_name, None)
        score = card.score if card is not None else 50.0
        total_score += score * weight
    return round(total_score / total_weight, 2)


def compute_scores_from_signal_cards(
    cards: SignalCards,
    regime_assessment: Optional[MarketRegimeAssessment] = None,
) -> dict[str, dict]:
    """Derive horizon composite scores from 11 signal cards.

    Returns a dict mirroring the shape of compute_scores() for drop-in compatibility
    with build_recommendations(). Each horizon dict contains:
    - 'composite': float (0–100)
    - 'weights': dict[str, int] (the card weights used)
    - per-card scores for diagnostics
    """
    short_composite = _signal_card_composite(cards, SIGNAL_CARD_SHORT_WEIGHTS)
    medium_composite = _signal_card_composite(cards, SIGNAL_CARD_MEDIUM_WEIGHTS)
    long_composite = _signal_card_composite(cards, SIGNAL_CARD_LONG_WEIGHTS)

    # Apply regime adjustments to composites (simple multiplier on composite)
    if regime_assessment is not None:
        regime = regime_assessment.regime
        conf = regime_assessment.confidence / 100.0
        if regime == MarketRegime.BULL_RISK_ON:
            short_composite = min(100, short_composite * (1 + conf * 0.1))
            medium_composite = min(100, medium_composite * (1 + conf * 0.05))
        elif regime == MarketRegime.BEAR_RISK_OFF:
            short_composite = max(0, short_composite * (1 - conf * 0.1))
            medium_composite = max(0, medium_composite * (1 - conf * 0.05))
        short_composite = round(short_composite, 2)
        medium_composite = round(medium_composite, 2)

    # Per-card scores for diagnostics
    card_scores = {
        name: getattr(cards, name).score
        for name in ["momentum", "trend", "entry_timing", "volume_accumulation",
                     "volatility_risk", "relative_strength", "growth", "valuation",
                     "quality", "ownership", "catalyst"]
        if hasattr(cards, name)
    }

    return {
        "short_term": {
            "composite": short_composite,
            "weights": SIGNAL_CARD_SHORT_WEIGHTS,
            **card_scores,
        },
        "medium_term": {
            "composite": medium_composite,
            "weights": SIGNAL_CARD_MEDIUM_WEIGHTS,
            **card_scores,
        },
        "long_term": {
            "composite": long_composite,
            "weights": SIGNAL_CARD_LONG_WEIGHTS,
            **card_scores,
        },
    }


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
