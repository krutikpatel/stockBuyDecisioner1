from __future__ import annotations

from app.models.market import TechnicalIndicators
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary

# Horizon-specific weights per §7.1 / 7.2 / 7.3 of projectPlan.md
# Each weight dict must sum to 100

SHORT_TERM_WEIGHTS = {
    "technical": 35,
    "catalyst": 20,
    "news_sentiment": 15,
    "risk_reward": 15,
    "sector_macro": 10,
    "fundamental": 5,
}

MEDIUM_TERM_WEIGHTS = {
    "fundamental": 25,
    "earnings": 25,
    "technical": 20,
    "valuation": 15,
    "catalyst": 10,
    "risk_reward": 5,
}

LONG_TERM_WEIGHTS = {
    "fundamental": 35,
    "valuation": 20,
    "earnings": 15,
    "risk_reward": 10,
    "sector_macro": 10,
    "technical": 5,
    "news_sentiment": 5,
}

_ALL_WEIGHT_DICTS = [SHORT_TERM_WEIGHTS, MEDIUM_TERM_WEIGHTS, LONG_TERM_WEIGHTS]


def _verify_weights() -> None:
    for w in _ALL_WEIGHT_DICTS:
        assert sum(w.values()) == 100, f"Weights do not sum to 100: {w}"


_verify_weights()


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
) -> dict[str, dict[str, float]]:
    """
    Returns per-horizon weighted composite scores.
    """
    base_scores = {
        "technical": technicals.technical_score,
        "fundamental": fundamentals.fundamental_score,
        "valuation": valuation.valuation_score,
        "earnings": earnings.earnings_score,
        "news_sentiment": news.news_score,
        "catalyst": catalyst_score,
        "sector_macro": sector_macro_score,
        "risk_reward": risk_reward_score,
    }

    return {
        "short_term": {
            "composite": _weighted_average(base_scores, SHORT_TERM_WEIGHTS),
            **base_scores,
        },
        "medium_term": {
            "composite": _weighted_average(base_scores, MEDIUM_TERM_WEIGHTS),
            **base_scores,
        },
        "long_term": {
            "composite": _weighted_average(base_scores, LONG_TERM_WEIGHTS),
            **base_scores,
        },
    }
