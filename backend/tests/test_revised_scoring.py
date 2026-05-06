"""
Story 7 TDD tests: Revised Horizon Scoring & Recommendation Engine
Tests written BEFORE implementation.

Coverage:
- compute_scores_from_signal_cards(): derive horizon composite scores from SignalCards
- New decision labels per horizon
- HorizonRecommendation.signal_cards_weights populated
- Regime multipliers still apply to signal-card-based scores
- build_recommendations_from_signal_cards() integration
"""
from __future__ import annotations

import pytest

from app.models.market import (
    TechnicalIndicators,
    TrendClassification,
    SupportResistanceLevels,
    MarketRegime,
    MarketRegimeAssessment,
)
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import SignalCard, SignalCardLabel, SignalCards, HorizonRecommendation
from app.services.signal_card_service import score_all_cards
from app.services.scoring_service import compute_scores_from_signal_cards
from app.services.recommendation_service import (
    build_recommendations,
    SHORT_TERM_DECISIONS,
    MEDIUM_TERM_DECISIONS,
    LONG_TERM_DECISIONS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TREND = TrendClassification(label="sideways", description="No clear trend")
_SR = SupportResistanceLevels(supports=[], resistances=[])


def _make_card(score: float, name: str = "test") -> SignalCard:
    return SignalCard(
        name=name,
        score=score,
        label=SignalCardLabel.from_score(score),
        explanation="test",
        top_positives=[],
        top_negatives=[],
    )


def _bullish_cards() -> SignalCards:
    """All signal cards at high scores — should produce a BUY recommendation."""
    return SignalCards(
        momentum=_make_card(80.0, "momentum"),
        trend=_make_card(75.0, "trend"),
        entry_timing=_make_card(70.0, "entry_timing"),
        volume_accumulation=_make_card(72.0, "volume_accumulation"),
        volatility_risk=_make_card(70.0, "volatility_risk"),
        relative_strength=_make_card(78.0, "relative_strength"),
        growth=_make_card(80.0, "growth"),
        valuation=_make_card(65.0, "valuation"),
        quality=_make_card(75.0, "quality"),
        ownership=_make_card(68.0, "ownership"),
        catalyst=_make_card(72.0, "catalyst"),
    )


def _bearish_cards() -> SignalCards:
    """All signal cards at low scores — should produce an AVOID recommendation."""
    return SignalCards(
        momentum=_make_card(20.0, "momentum"),
        trend=_make_card(15.0, "trend"),
        entry_timing=_make_card(25.0, "entry_timing"),
        volume_accumulation=_make_card(20.0, "volume_accumulation"),
        volatility_risk=_make_card(20.0, "volatility_risk"),
        relative_strength=_make_card(15.0, "relative_strength"),
        growth=_make_card(20.0, "growth"),
        valuation=_make_card(25.0, "valuation"),
        quality=_make_card(20.0, "quality"),
        ownership=_make_card(18.0, "ownership"),
        catalyst=_make_card(22.0, "catalyst"),
    )


def _neutral_cards() -> SignalCards:
    return SignalCards(
        momentum=_make_card(50.0, "momentum"),
        trend=_make_card(50.0, "trend"),
        entry_timing=_make_card(50.0, "entry_timing"),
        volume_accumulation=_make_card(50.0, "volume_accumulation"),
        volatility_risk=_make_card(50.0, "volatility_risk"),
        relative_strength=_make_card(50.0, "relative_strength"),
        growth=_make_card(50.0, "growth"),
        valuation=_make_card(50.0, "valuation"),
        quality=_make_card(50.0, "quality"),
        ownership=_make_card(50.0, "ownership"),
        catalyst=_make_card(50.0, "catalyst"),
    )


def _make_tech() -> TechnicalIndicators:
    return TechnicalIndicators(trend=_TREND, support_resistance=_SR)


def _make_fundamentals() -> FundamentalData:
    return FundamentalData(
        revenue_growth_yoy=0.15,
        operating_margin=0.15,
        fundamental_score=65.0,
    )


def _make_earnings() -> EarningsData:
    return EarningsData(beat_rate=0.70, earnings_score=60.0)


def _make_news() -> NewsSummary:
    return NewsSummary(news_score=60.0)


def _make_valuation() -> ValuationData:
    return ValuationData(forward_pe=22.0, valuation_score=55.0)


# ---------------------------------------------------------------------------
# compute_scores_from_signal_cards
# ---------------------------------------------------------------------------

class TestComputeScoresFromSignalCards:
    def test_returns_dict_with_three_horizons(self):
        result = compute_scores_from_signal_cards(_bullish_cards())
        assert "short_term" in result
        assert "medium_term" in result
        assert "long_term" in result

    def test_each_horizon_has_composite(self):
        result = compute_scores_from_signal_cards(_bullish_cards())
        for horizon in ("short_term", "medium_term", "long_term"):
            assert "composite" in result[horizon]
            assert 0 <= result[horizon]["composite"] <= 100

    def test_bullish_cards_produce_high_composite(self):
        result = compute_scores_from_signal_cards(_bullish_cards())
        for horizon in ("short_term", "medium_term", "long_term"):
            assert result[horizon]["composite"] >= 60, \
                f"{horizon} composite too low for bullish cards: {result[horizon]['composite']}"

    def test_bearish_cards_produce_low_composite(self):
        result = compute_scores_from_signal_cards(_bearish_cards())
        for horizon in ("short_term", "medium_term", "long_term"):
            assert result[horizon]["composite"] <= 40, \
                f"{horizon} composite too high for bearish cards: {result[horizon]['composite']}"

    def test_neutral_cards_produce_midrange_composite(self):
        result = compute_scores_from_signal_cards(_neutral_cards())
        for horizon in ("short_term", "medium_term", "long_term"):
            # Neutral cards should produce roughly 50
            assert 40 <= result[horizon]["composite"] <= 60

    def test_returns_signal_cards_weights_per_horizon(self):
        result = compute_scores_from_signal_cards(_bullish_cards())
        for horizon in ("short_term", "medium_term", "long_term"):
            assert "weights" in result[horizon]
            weights = result[horizon]["weights"]
            assert isinstance(weights, dict)
            assert len(weights) > 0
            # Weights should sum to ~100
            assert abs(sum(weights.values()) - 100) < 1

    def test_short_term_emphasizes_momentum_and_volume(self):
        result = compute_scores_from_signal_cards(_bullish_cards())
        weights = result["short_term"]["weights"]
        # Momentum should be largest or near-largest weight for short-term
        assert "momentum" in weights
        assert "volume_accumulation" in weights
        assert weights["momentum"] >= 15  # at least 15%

    def test_long_term_emphasizes_growth_and_quality(self):
        result = compute_scores_from_signal_cards(_bullish_cards())
        weights = result["long_term"]["weights"]
        assert "growth" in weights
        assert "quality" in weights
        assert weights["growth"] >= 15
        assert weights["quality"] >= 15


# ---------------------------------------------------------------------------
# New decision label constants
# ---------------------------------------------------------------------------

class TestDecisionLabelConstants:
    def test_short_term_decisions_exist(self):
        assert hasattr(SHORT_TERM_DECISIONS, "__contains__")  # iterable/set
        assert "BUY_NOW_MOMENTUM" in SHORT_TERM_DECISIONS
        assert "BUY_STARTER_STRONG_BUT_EXTENDED" in SHORT_TERM_DECISIONS
        assert "WAIT_FOR_PULLBACK" in SHORT_TERM_DECISIONS
        assert "AVOID_BAD_CHART" in SHORT_TERM_DECISIONS

    def test_medium_term_decisions_exist(self):
        assert "BUY_NOW" in MEDIUM_TERM_DECISIONS
        assert "BUY_STARTER" in MEDIUM_TERM_DECISIONS
        assert "BUY_ON_PULLBACK" in MEDIUM_TERM_DECISIONS
        assert "WATCHLIST_NEEDS_CONFIRMATION" in MEDIUM_TERM_DECISIONS
        assert "AVOID_BAD_BUSINESS" in MEDIUM_TERM_DECISIONS

    def test_long_term_decisions_exist(self):
        assert "ACCUMULATE_ON_WEAKNESS" in LONG_TERM_DECISIONS
        assert "BUY_NOW_LONG_TERM" in LONG_TERM_DECISIONS
        assert "WATCHLIST_VALUATION_TOO_RICH" in LONG_TERM_DECISIONS
        assert "AVOID_LONG_TERM" in LONG_TERM_DECISIONS


# ---------------------------------------------------------------------------
# build_recommendations with signal_cards
# ---------------------------------------------------------------------------

class TestBuildRecommendationsWithSignalCards:
    def _build(self, cards: SignalCards, horizons=None) -> list[HorizonRecommendation]:
        horizons = horizons or ["short_term", "medium_term", "long_term"]
        scores = compute_scores_from_signal_cards(cards)
        return build_recommendations(
            technicals=_make_tech(),
            fundamentals=_make_fundamentals(),
            valuation=_make_valuation(),
            earnings=_make_earnings(),
            news=_make_news(),
            scores=scores,
            horizons=horizons,
            risk_profile="moderate",
            current_price=150.0,
            signal_cards=cards,
        )

    def test_returns_list_of_recommendations(self):
        recs = self._build(_bullish_cards())
        assert isinstance(recs, list)
        assert len(recs) == 3

    def test_each_rec_has_signal_cards_weights(self):
        recs = self._build(_bullish_cards())
        for rec in recs:
            assert isinstance(rec.signal_cards_weights, dict)
            assert len(rec.signal_cards_weights) > 0

    def test_bullish_cards_produce_buy_short_term(self):
        recs = self._build(_bullish_cards())
        short = next(r for r in recs if r.horizon == "short_term")
        # Should produce a BUY-type decision
        assert any(short.decision.startswith("BUY") for _ in [True]), \
            f"Expected BUY decision for bullish short-term, got: {short.decision}"

    def test_bearish_cards_produce_avoid_short_term(self):
        recs = self._build(_bearish_cards())
        short = next(r for r in recs if r.horizon == "short_term")
        assert "AVOID" in short.decision or "WAIT" in short.decision, \
            f"Expected AVOID/WAIT for bearish short-term, got: {short.decision}"

    def test_decision_is_valid_label(self):
        all_valid = SHORT_TERM_DECISIONS | MEDIUM_TERM_DECISIONS | LONG_TERM_DECISIONS | {
            "AVOID_LOW_CONFIDENCE", "WATCHLIST"
        }
        recs = self._build(_neutral_cards())
        for rec in recs:
            assert rec.decision in all_valid, f"Invalid decision: {rec.decision}"

    def test_scores_in_range_0_to_100(self):
        recs = self._build(_bullish_cards())
        for rec in recs:
            assert 0 <= rec.score <= 100

    def test_signal_cards_weights_sum_to_100(self):
        recs = self._build(_bullish_cards())
        for rec in recs:
            total = sum(rec.signal_cards_weights.values())
            assert abs(total - 100) < 1, f"Weights don't sum to 100 for {rec.horizon}: {total}"


# ---------------------------------------------------------------------------
# Regime multipliers still work
# ---------------------------------------------------------------------------

class TestRegimeMultipliersWithSignalCards:
    def _build_with_regime(self, cards: SignalCards, regime: MarketRegime) -> list[HorizonRecommendation]:
        regime_assessment = MarketRegimeAssessment(
            regime=regime,
            confidence=80.0,
            vix_level=18.0,
        )
        scores = compute_scores_from_signal_cards(cards, regime_assessment=regime_assessment)
        return build_recommendations(
            technicals=_make_tech(),
            fundamentals=_make_fundamentals(),
            valuation=_make_valuation(),
            earnings=_make_earnings(),
            news=_make_news(),
            scores=scores,
            horizons=["short_term"],
            risk_profile="moderate",
            current_price=150.0,
            signal_cards=cards,
            regime_assessment=regime_assessment,
        )

    def test_bull_regime_increases_short_term_score(self):
        neutral = _neutral_cards()
        bull_recs = self._build_with_regime(neutral, MarketRegime.BULL_RISK_ON)
        bear_recs = self._build_with_regime(neutral, MarketRegime.BEAR_RISK_OFF)
        bull_score = bull_recs[0].score
        bear_score = bear_recs[0].score
        assert bull_score >= bear_score, f"Bull {bull_score} should be >= bear {bear_score}"
