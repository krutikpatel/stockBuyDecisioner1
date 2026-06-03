"""Parity tests — verify that both the legacy path and the new engine path
produce HorizonRecommendation objects with the same field names and types.

These tests run both pipelines with identical inputs and assert structural
parity, NOT value equality (the two engines use different scoring logic).
"""
from __future__ import annotations

import pytest

from app.engine.stock_decision_engine import StockDecisionEngine, reset_decision_engine
from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData
from app.models.market import MarketRegimeAssessment, TechnicalIndicators, TrendClassification
from app.models.news import NewsSummary
from app.models.response import (
    EntryPlan, ExitPlan, HorizonRecommendation, PositionSizing, RiskReward,
)
from app.services.recommendation_service import build_recommendations
from app.services.scoring_service import compute_scores_from_signal_cards
from app.services.signal_card_service import score_all_cards


HORIZONS = ["short_term", "medium_term", "long_term"]

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _base_technicals() -> TechnicalIndicators:
    return TechnicalIndicators(
        rsi_14=55.0,
        sma20_relative=2.0,
        sma50_relative=3.0,
        sma200_relative=6.0,
        sma20_slope=0.1,
        sma50_slope=0.1,
        sma200_slope=0.05,
        rsi_slope=0.3,
        breakout_volume_multiple=1.3,
        updown_volume_ratio=1.2,
        volume_dryup_ratio=0.75,
        perf_1w=0.5,
        perf_1m=2.5,
        rs_vs_spy=1.1,
        rs_vs_spy_20d=1.4,
        rs_vs_sector_20d=1.8,
        atr=1.5,
        atr_percent=1.5,
        is_extended=False,
        trend=TrendClassification(label="weak_uptrend", description="Uptrend"),
    )


def _base_fundamentals() -> FundamentalData:
    return FundamentalData(
        archetype=StockArchetype.PROFITABLE_GROWTH,
        archetype_confidence=75.0,
        revenue_growth_yoy=0.18,
        operating_margin=0.14,
        roic=14.0,
        free_cash_flow=5e7,
        fundamental_score=65.0,
    )


def _base_valuation() -> ValuationData:
    return ValuationData(
        forward_pe=24.0,
        price_to_sales=3.5,
        valuation_score=58.0,
        peer_comparison_available=True,
    )


def _base_earnings() -> EarningsData:
    return EarningsData(
        within_30_days=False,
        beat_rate=0.70,
        next_earnings_date="2030-06-01",
        earnings_score=68.0,
    )


def _base_news() -> NewsSummary:
    return NewsSummary(
        positive_count=2, negative_count=1, coverage_limited=False, news_score=62.0,
    )


def _regime() -> MarketRegimeAssessment:
    return MarketRegimeAssessment(regime="BULL_RISK_ON", confidence=75.0)


def _run_legacy(price: float = 120.0) -> list[HorizonRecommendation]:
    technicals = _base_technicals()
    fundamentals = _base_fundamentals()
    valuation = _base_valuation()
    earnings = _base_earnings()
    news = _base_news()
    regime = _regime()

    signal_cards = score_all_cards(technicals, fundamentals, valuation, earnings, news)
    scores = compute_scores_from_signal_cards(cards=signal_cards, regime_assessment=regime)
    return build_recommendations(
        technicals=technicals,
        fundamentals=fundamentals,
        valuation=valuation,
        earnings=earnings,
        news=news,
        scores=scores,
        horizons=HORIZONS,
        risk_profile="moderate",
        current_price=price,
        regime_assessment=regime,
        has_options_data=True,
        signal_cards=signal_cards,
    )


def _run_new(price: float = 120.0) -> list[HorizonRecommendation]:
    reset_decision_engine()
    engine = StockDecisionEngine()
    return engine.decide(
        ticker="PARITY",
        price=price,
        technicals=_base_technicals(),
        fundamentals=_base_fundamentals(),
        valuation=_base_valuation(),
        earnings=_base_earnings(),
        news=_base_news(),
        horizons=HORIZONS,
        risk_profile="moderate",
        regime_assessment=_regime(),
        has_options_data=True,
    )


# ---------------------------------------------------------------------------
# Required field presence — both paths must expose the same fields
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = [
    "horizon", "decision", "score", "confidence", "confidence_score",
    "data_completeness_score", "summary", "bullish_factors", "bearish_factors",
    "entry_plan", "exit_plan", "risk_reward", "position_sizing",
    "data_warnings", "signal_cards_weights",
]


@pytest.mark.parametrize("field", _REQUIRED_FIELDS)
def test_legacy_has_field(field):
    recs = _run_legacy()
    for rec in recs:
        assert hasattr(rec, field), f"Legacy output missing field: {field}"


@pytest.mark.parametrize("field", _REQUIRED_FIELDS)
def test_new_engine_has_field(field):
    recs = _run_new()
    for rec in recs:
        assert hasattr(rec, field), f"New engine output missing field: {field}"


# ---------------------------------------------------------------------------
# Field type parity — both paths must return the same types
# ---------------------------------------------------------------------------

_FIELD_TYPES = {
    "horizon": str,
    "decision": str,
    "score": float,
    "confidence": str,
    "confidence_score": float,
    "data_completeness_score": float,
    "summary": str,
    "bullish_factors": list,
    "bearish_factors": list,
    "entry_plan": EntryPlan,
    "exit_plan": ExitPlan,
    "risk_reward": RiskReward,
    "position_sizing": PositionSizing,
    "data_warnings": list,
    "signal_cards_weights": dict,
}


@pytest.mark.parametrize("field,expected_type", list(_FIELD_TYPES.items()))
def test_legacy_field_type(field, expected_type):
    recs = _run_legacy()
    for rec in recs:
        value = getattr(rec, field)
        assert isinstance(value, expected_type), (
            f"Legacy {field}: expected {expected_type.__name__}, got {type(value).__name__}"
        )


@pytest.mark.parametrize("field,expected_type", list(_FIELD_TYPES.items()))
def test_new_engine_field_type(field, expected_type):
    recs = _run_new()
    for rec in recs:
        value = getattr(rec, field)
        assert isinstance(value, expected_type), (
            f"New engine {field}: expected {expected_type.__name__}, got {type(value).__name__}"
        )


# ---------------------------------------------------------------------------
# Value constraint parity
# ---------------------------------------------------------------------------

def test_both_paths_return_three_horizons():
    assert len(_run_legacy()) == 3
    assert len(_run_new()) == 3


def test_both_paths_return_expected_horizons():
    legacy_horizons = {r.horizon for r in _run_legacy()}
    new_horizons = {r.horizon for r in _run_new()}
    assert legacy_horizons == {"short_term", "medium_term", "long_term"}
    assert new_horizons == {"short_term", "medium_term", "long_term"}


def test_both_paths_score_in_valid_range():
    for rec in _run_legacy() + _run_new():
        assert 0.0 <= rec.score <= 100.0, f"{rec.horizon}: score {rec.score} out of range"


def test_both_paths_confidence_valid_label():
    valid = {"high", "medium_high", "medium", "low"}
    for rec in _run_legacy() + _run_new():
        assert rec.confidence in valid, f"{rec.horizon}: unexpected confidence {rec.confidence!r}"


def test_both_paths_summary_non_empty():
    for rec in _run_legacy() + _run_new():
        assert rec.summary, f"{rec.horizon}: empty summary"


def test_both_paths_decision_non_empty():
    for rec in _run_legacy() + _run_new():
        assert rec.decision, f"{rec.horizon}: empty decision"


def test_both_paths_confidence_score_in_range():
    for rec in _run_legacy() + _run_new():
        assert 0.0 <= rec.confidence_score <= 100.0


def test_both_paths_data_completeness_in_range():
    for rec in _run_legacy() + _run_new():
        assert 0.0 <= rec.data_completeness_score <= 100.0
