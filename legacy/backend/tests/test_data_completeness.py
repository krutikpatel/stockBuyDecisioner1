"""US-006 unit tests: data completeness and confidence scoring."""
import pytest

from app.models.earnings import EarningsData
from app.models.fundamentals import ValuationData
from app.models.news import NewsSummary
from app.models.market import TechnicalIndicators, TrendClassification, SupportResistanceLevels
from app.models.fundamentals import FundamentalData
from app.services.data_completeness_service import (
    compute_completeness,
    AVOID_LOW_CONFIDENCE_THRESHOLD,
)
from app.services.recommendation_service import build_recommendations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_news() -> NewsSummary:
    return NewsSummary(news_score=70.0, positive_count=3, negative_count=1)


def _empty_news() -> NewsSummary:
    return NewsSummary(news_score=50.0, positive_count=0, negative_count=0)


def _news_with_earnings_date() -> EarningsData:
    return EarningsData(
        beat_rate=0.75,
        avg_eps_surprise_pct=3.0,
        within_30_days=False,
        next_earnings_date="2026-08-01",
        earnings_score=65.0,
    )


def _news_without_earnings_date() -> EarningsData:
    return EarningsData(
        beat_rate=0.75,
        avg_eps_surprise_pct=3.0,
        within_30_days=False,
        next_earnings_date=None,
        earnings_score=65.0,
    )


def _valuation_with_peers() -> ValuationData:
    return ValuationData(forward_pe=20.0, valuation_score=65.0, peer_comparison_available=True)


def _valuation_without_peers() -> ValuationData:
    return ValuationData(forward_pe=20.0, valuation_score=65.0, peer_comparison_available=False)


def _make_technicals() -> TechnicalIndicators:
    return TechnicalIndicators(
        ma_10=100.0, ma_20=98.0, ma_50=95.0, ma_100=92.0, ma_200=88.0,
        rsi_14=60.0, macd=0.8, macd_signal=0.3, macd_histogram=0.5,
        atr=1.5, volume_trend="above_average",
        trend=TrendClassification(label="strong_uptrend", description="test"),
        is_extended=False, extension_pct_above_20ma=2.0, extension_pct_above_50ma=5.0,
        support_resistance=SupportResistanceLevels(
            supports=[95.0], resistances=[115.0],
            nearest_support=95.0, nearest_resistance=115.0,
        ),
        rs_vs_spy=1.2, technical_score=75.0,
    )


def _make_fundamentals() -> FundamentalData:
    return FundamentalData(
        revenue_growth_yoy=0.20, operating_margin=0.25,
        free_cash_flow=1_000_000_000, fundamental_score=70.0,
    )


def _scores(composite: float = 75.0) -> dict:
    base = {"technical": 75.0, "fundamental": 70.0, "valuation": 65.0,
            "earnings": 60.0, "news_sentiment": 65.0, "catalyst": 50.0,
            "sector_macro": 50.0, "risk_reward": 50.0}
    return {
        "short_term": {"composite": composite, **base},
        "medium_term": {"composite": composite, **base},
        "long_term": {"composite": composite, **base},
    }


# ---------------------------------------------------------------------------
# compute_completeness unit tests
# ---------------------------------------------------------------------------

class TestComputeCompleteness:

    def test_full_data_returns_100(self):
        completeness, confidence, warnings = compute_completeness(
            news=_full_news(),
            earnings=_news_with_earnings_date(),
            valuation=_valuation_with_peers(),
            has_options_data=True,
            has_sufficient_price_history=True,
        )
        assert completeness == 100.0
        assert confidence == 100.0
        assert warnings == []

    def test_no_news_deducts_15(self):
        completeness, _, _ = compute_completeness(
            news=_empty_news(),
            earnings=_news_with_earnings_date(),
            valuation=_valuation_with_peers(),
            has_options_data=True,
            has_sufficient_price_history=True,
        )
        assert completeness == 85.0

    def test_no_options_data_deducts_15(self):
        completeness, _, _ = compute_completeness(
            news=_full_news(),
            earnings=_news_with_earnings_date(),
            valuation=_valuation_with_peers(),
            has_options_data=False,
            has_sufficient_price_history=True,
        )
        assert completeness == 85.0

    def test_no_earnings_date_deducts_10(self):
        completeness, _, _ = compute_completeness(
            news=_full_news(),
            earnings=_news_without_earnings_date(),
            valuation=_valuation_with_peers(),
            has_options_data=True,
            has_sufficient_price_history=True,
        )
        assert completeness == 90.0

    def test_no_peer_comparison_deducts_5(self):
        completeness, _, _ = compute_completeness(
            news=_full_news(),
            earnings=_news_with_earnings_date(),
            valuation=_valuation_without_peers(),
            has_options_data=True,
            has_sufficient_price_history=True,
        )
        assert completeness == 95.0

    def test_insufficient_price_history_deducts_5(self):
        completeness, _, _ = compute_completeness(
            news=_full_news(),
            earnings=_news_with_earnings_date(),
            valuation=_valuation_with_peers(),
            has_options_data=True,
            has_sufficient_price_history=False,
        )
        assert completeness == 95.0

    def test_no_news_and_no_options_caps_confidence(self):
        """no_news(-15) + no_options(-15) = 70 → still above 60 cap threshold."""
        completeness, confidence, warnings = compute_completeness(
            news=_empty_news(),
            earnings=_news_with_earnings_date(),
            valuation=_valuation_with_peers(),
            has_options_data=False,
            has_sufficient_price_history=True,
        )
        assert completeness == 70.0
        assert confidence == 100.0  # 70 > 60 threshold → not capped
        assert len(warnings) == 2

    def test_completeness_below_60_caps_confidence_at_60(self):
        """All data missing → completeness = 50 → confidence capped at 60."""
        completeness, confidence, warnings = compute_completeness(
            news=_empty_news(),
            earnings=_news_without_earnings_date(),
            valuation=_valuation_without_peers(),
            has_options_data=False,
            has_sufficient_price_history=False,
        )
        assert completeness == 50.0
        assert confidence == 60.0
        assert len(warnings) == 5

    def test_completeness_never_below_zero(self):
        completeness, _, _ = compute_completeness(
            news=_empty_news(),
            earnings=_news_without_earnings_date(),
            valuation=_valuation_without_peers(),
            has_options_data=False,
            has_sufficient_price_history=False,
        )
        assert completeness >= 0.0

    def test_warnings_describe_specific_gaps(self):
        _, _, warnings = compute_completeness(
            news=_empty_news(),
            earnings=_news_without_earnings_date(),
            valuation=_valuation_without_peers(),
            has_options_data=False,
            has_sufficient_price_history=True,
        )
        text = " ".join(warnings).lower()
        assert "news" in text
        assert "earnings" in text
        assert "peer" in text
        assert "options" in text


# ---------------------------------------------------------------------------
# Integration: completeness fields populate HorizonRecommendation
# ---------------------------------------------------------------------------

class TestCompletenessInRecommendations:

    def test_full_data_sets_completeness_100(self):
        recs = build_recommendations(
            technicals=_make_technicals(),
            fundamentals=_make_fundamentals(),
            valuation=_valuation_with_peers(),
            earnings=_news_with_earnings_date(),
            news=_full_news(),
            scores=_scores(75.0),
            horizons=["short_term"],
            risk_profile="moderate",
            current_price=100.0,
            has_options_data=True,
            has_sufficient_price_history=True,
        )
        assert recs[0].data_completeness_score == 100.0
        assert recs[0].confidence_score == 100.0

    def test_missing_data_reduces_completeness(self):
        recs = build_recommendations(
            technicals=_make_technicals(),
            fundamentals=_make_fundamentals(),
            valuation=_valuation_without_peers(),
            earnings=_news_without_earnings_date(),
            news=_empty_news(),
            scores=_scores(75.0),
            horizons=["short_term"],
            risk_profile="moderate",
            current_price=100.0,
            has_options_data=False,
            has_sufficient_price_history=True,
        )
        assert recs[0].data_completeness_score < 70.0

    def test_low_completeness_forces_avoid_low_confidence(self):
        """Completeness = 50 (< 55 threshold) → decision must be AVOID_LOW_CONFIDENCE."""
        recs = build_recommendations(
            technicals=_make_technicals(),
            fundamentals=_make_fundamentals(),
            valuation=_valuation_without_peers(),
            earnings=_news_without_earnings_date(),
            news=_empty_news(),
            scores=_scores(85.0),  # high score, should be BUY_NOW — but overridden
            horizons=["short_term"],
            risk_profile="moderate",
            current_price=100.0,
            has_options_data=False,
            has_sufficient_price_history=False,
        )
        assert recs[0].decision == "AVOID_LOW_CONFIDENCE"

    def test_high_score_not_overridden_when_completeness_sufficient(self):
        recs = build_recommendations(
            technicals=_make_technicals(),
            fundamentals=_make_fundamentals(),
            valuation=_valuation_with_peers(),
            earnings=_news_with_earnings_date(),
            news=_full_news(),
            scores=_scores(85.0),
            horizons=["short_term"],
            risk_profile="moderate",
            current_price=100.0,
            has_options_data=True,
            has_sufficient_price_history=True,
        )
        assert recs[0].decision == "BUY_NOW"

    def test_all_horizons_get_completeness_fields(self):
        recs = build_recommendations(
            technicals=_make_technicals(),
            fundamentals=_make_fundamentals(),
            valuation=_valuation_with_peers(),
            earnings=_news_with_earnings_date(),
            news=_full_news(),
            scores=_scores(72.0),
            horizons=["short_term", "medium_term", "long_term"],
            risk_profile="moderate",
            current_price=100.0,
        )
        for rec in recs:
            assert hasattr(rec, "data_completeness_score")
            assert hasattr(rec, "confidence_score")
            assert 0 <= rec.data_completeness_score <= 100
            assert 0 <= rec.confidence_score <= 100

    def test_warnings_list_populated_from_completeness(self):
        recs = build_recommendations(
            technicals=_make_technicals(),
            fundamentals=_make_fundamentals(),
            valuation=_valuation_without_peers(),
            earnings=_news_without_earnings_date(),
            news=_full_news(),
            scores=_scores(72.0),
            horizons=["short_term"],
            risk_profile="moderate",
            current_price=100.0,
            has_options_data=False,
        )
        warnings_text = " ".join(recs[0].data_warnings).lower()
        assert "options" in warnings_text
        assert "peer" in warnings_text
        assert "earnings" in warnings_text
