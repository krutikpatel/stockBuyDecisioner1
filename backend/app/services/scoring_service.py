from __future__ import annotations

from typing import Optional

from app.algo_config import AlgoConfig, get_algo_config
from app.models.market import MarketRegime, MarketRegimeAssessment, TechnicalIndicators
from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import SignalCards
from app.services.market_regime_service import REGIME_WEIGHT_ADJUSTMENTS


# ---------------------------------------------------------------------------
# Backward-compatible module-level weight dicts (read from default config)
# These are used by tests that import the names directly.
# ---------------------------------------------------------------------------

def _default_scoring() -> dict:
    return get_algo_config().scoring


SHORT_TERM_WEIGHTS: dict[str, int] = _default_scoring()["legacy_short_term_weights"]
MEDIUM_TERM_WEIGHTS: dict[str, int] = _default_scoring()["legacy_medium_term_weights"]
LONG_TERM_WEIGHTS: dict[str, int] = _default_scoring()["legacy_long_term_weights"]

SIGNAL_CARD_SHORT_WEIGHTS: dict[str, int] = _default_scoring()["signal_card_short_weights"]
SIGNAL_CARD_MEDIUM_WEIGHTS: dict[str, int] = _default_scoring()["signal_card_medium_weights"]
SIGNAL_CARD_LONG_WEIGHTS: dict[str, int] = _default_scoring()["signal_card_long_weights"]


def _verify_weights(s: dict) -> None:
    for name, w in [
        ("legacy_short", s["legacy_short_term_weights"]),
        ("legacy_medium", s["legacy_medium_term_weights"]),
        ("legacy_long", s["legacy_long_term_weights"]),
    ]:
        assert sum(w.values()) == 100, f"{name} weights do not sum to 100: {w}"
    for name, w in [
        ("signal_card_short", s["signal_card_short_weights"]),
        ("signal_card_medium", s["signal_card_medium_weights"]),
        ("signal_card_long", s["signal_card_long_weights"]),
    ]:
        assert sum(w.values()) == 100, f"{name} weights do not sum to 100: {w}"


# Validate defaults at import time
_verify_weights(_default_scoring())


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
    algo_config: Optional[AlgoConfig] = None,
) -> dict[str, dict]:
    """Derive horizon composite scores from 11 signal cards.

    Returns a dict mirroring the shape of compute_scores() for drop-in compatibility
    with build_recommendations(). Each horizon dict contains:
    - 'composite': float (0–100)
    - 'weights': dict[str, int] (the card weights used)
    - per-card scores for diagnostics
    """
    cfg = algo_config or get_algo_config()
    s = cfg.scoring
    sc_short = s["signal_card_short_weights"]
    sc_medium = s["signal_card_medium_weights"]
    sc_long = s["signal_card_long_weights"]
    rs = cfg.regime_scoring

    short_composite = _signal_card_composite(cards, sc_short)
    medium_composite = _signal_card_composite(cards, sc_medium)
    long_composite = _signal_card_composite(cards, sc_long)

    # Apply regime adjustments to composites (simple multiplier on composite)
    if regime_assessment is not None:
        regime = regime_assessment.regime
        conf = regime_assessment.confidence / 100.0
        bull_short_coef = rs["bull_short_composite_coef"]
        bull_medium_coef = rs["bull_medium_composite_coef"]
        bear_short_coef = rs["bear_short_composite_coef"]
        bear_medium_coef = rs["bear_medium_composite_coef"]
        if regime == MarketRegime.BULL_RISK_ON:
            short_composite = min(100, short_composite * (1 + conf * bull_short_coef))
            medium_composite = min(100, medium_composite * (1 + conf * bull_medium_coef))
        elif regime == MarketRegime.BEAR_RISK_OFF:
            short_composite = max(0, short_composite * (1 - conf * bear_short_coef))
            medium_composite = max(0, medium_composite * (1 - conf * bear_medium_coef))
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
            "weights": sc_short,
            **card_scores,
        },
        "medium_term": {
            "composite": medium_composite,
            "weights": sc_medium,
            **card_scores,
        },
        "long_term": {
            "composite": long_composite,
            "weights": sc_long,
            **card_scores,
        },
    }


def _regime_score(
    assessment: Optional[MarketRegimeAssessment],
    rs: Optional[dict] = None,
) -> float:
    """Convert regime + confidence into a 0–100 score for SHORT_TERM market_regime slot."""
    if assessment is None:
        return 50.0
    if rs is None:
        rs = get_algo_config().regime_scoring
    regime = assessment.regime
    conf = assessment.confidence
    base = rs["base"]
    bull_coef = rs["bull_coef"]
    bear_coef = rs["bear_coef"]
    narrow_coef = rs["narrow_liquidity_coef"]
    if regime == MarketRegime.BULL_RISK_ON:
        return base + conf * bull_coef
    if regime == MarketRegime.BEAR_RISK_OFF:
        return base - conf * bear_coef
    if regime in (MarketRegime.BULL_NARROW_LEADERSHIP, MarketRegime.LIQUIDITY_RALLY):
        return base + conf * narrow_coef
    return base


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
    algo_config: Optional[AlgoConfig] = None,
) -> dict[str, dict[str, float]]:
    """Return per-horizon weighted composite scores with regime adjustments.

    Derives intermediate scores from input models and applies optional
    MarketRegimeAssessment multipliers before computing each composite.
    """
    cfg = algo_config or get_algo_config()
    s = cfg.scoring
    rs = cfg.regime_scoring
    short_weights = s["legacy_short_term_weights"]
    medium_weights = s["legacy_medium_term_weights"]
    long_weights = s["legacy_long_term_weights"]

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
        "market_regime":      _regime_score(regime_assessment, rs),
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
            "composite": _weighted_average(short_adj, short_weights),
            **all_raw,
            **short_adj,
        },
        "medium_term": {
            "composite": _weighted_average(medium_adj, medium_weights),
            **all_raw,
            **medium_adj,
        },
        "long_term": {
            "composite": _weighted_average(long_adj, long_weights),
            **all_raw,
            **long_adj,
        },
    }
