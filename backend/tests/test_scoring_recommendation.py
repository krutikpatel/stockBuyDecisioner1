"""Phase 4 unit tests: scoring, recommendation, and risk management."""
import pytest

from app.models.market import TechnicalIndicators, TrendClassification, SupportResistanceLevels
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.services.scoring_service import (
    SHORT_TERM_WEIGHTS,
    MEDIUM_TERM_WEIGHTS,
    LONG_TERM_WEIGHTS,
    compute_scores,
)
from app.services.recommendation_service import (
    _decide_short_term,
    _decide_medium_term,
    _decide_long_term,
    _confidence,
    build_recommendations,
)
from app.services.risk_management_service import compute_risk_management


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_technicals(
    trend: str = "strong_uptrend",
    rsi: float = 60.0,
    macd_hist: float = 0.5,
    is_extended: bool = False,
    volume_trend: str = "above_average",
    rs_spy: float = 1.2,
    tech_score: float = 75.0,
    nearest_support: float = 95.0,
    nearest_resistance: float = 115.0,
) -> TechnicalIndicators:
    return TechnicalIndicators(
        ma_10=100.0, ma_20=98.0, ma_50=95.0, ma_100=92.0, ma_200=88.0,
        rsi_14=rsi,
        macd=0.8, macd_signal=0.3, macd_histogram=macd_hist,
        atr=1.5,
        volume_trend=volume_trend,
        trend=TrendClassification(label=trend, description="test"),
        is_extended=is_extended,
        extension_pct_above_20ma=2.0,
        extension_pct_above_50ma=5.0,
        support_resistance=SupportResistanceLevels(
            supports=[nearest_support],
            resistances=[nearest_resistance],
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
        ),
        rs_vs_spy=rs_spy,
        technical_score=tech_score,
    )


def _make_fundamentals(fundamental_score: float = 70.0) -> FundamentalData:
    return FundamentalData(
        revenue_growth_yoy=0.20,
        eps_growth_yoy=0.25,
        gross_margin=0.60,
        operating_margin=0.25,
        free_cash_flow=1_000_000_000,
        fundamental_score=fundamental_score,
    )


def _make_valuation(valuation_score: float = 65.0) -> ValuationData:
    return ValuationData(
        forward_pe=18.0,
        peg_ratio=1.2,
        price_to_sales=3.0,
        ev_to_ebitda=12.0,
        fcf_yield=5.0,
        valuation_score=valuation_score,
    )


def _make_earnings(beat_rate: float = 0.75, avg_surprise: float = 4.0, within_30: bool = False) -> EarningsData:
    return EarningsData(
        beat_rate=beat_rate,
        avg_eps_surprise_pct=avg_surprise,
        within_30_days=within_30,
        earnings_score=60.0,
    )


def _make_news(news_score: float = 65.0) -> NewsSummary:
    return NewsSummary(news_score=news_score, positive_count=3, negative_count=1)


# ---------------------------------------------------------------------------
# Weight integrity tests
# ---------------------------------------------------------------------------

class TestWeights:
    def test_short_term_weights_sum_to_100(self):
        assert sum(SHORT_TERM_WEIGHTS.values()) == 100

    def test_medium_term_weights_sum_to_100(self):
        assert sum(MEDIUM_TERM_WEIGHTS.values()) == 100

    def test_long_term_weights_sum_to_100(self):
        assert sum(LONG_TERM_WEIGHTS.values()) == 100


# ---------------------------------------------------------------------------
# Scoring service tests
# ---------------------------------------------------------------------------

class TestScoringService:
    def test_returns_all_three_horizons(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = compute_scores(ti, fd, vd, ed, ne)
        assert "short_term" in scores
        assert "medium_term" in scores
        assert "long_term" in scores

    def test_composite_score_in_valid_range(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = compute_scores(ti, fd, vd, ed, ne)
        for horizon in ("short_term", "medium_term", "long_term"):
            c = scores[horizon]["composite"]
            assert 0 <= c <= 100, f"{horizon} composite {c} out of range"

    def test_high_sub_scores_yield_high_composite(self):
        ti = _make_technicals(tech_score=90.0)
        fd = _make_fundamentals(fundamental_score=90.0)
        vd = _make_valuation(valuation_score=90.0)
        ed = _make_earnings()
        ne = _make_news(news_score=90.0)
        scores = compute_scores(ti, fd, vd, ed, ne, catalyst_score=90.0, sector_macro_score=90.0, risk_reward_score=90.0)
        for horizon in ("short_term", "medium_term", "long_term"):
            assert scores[horizon]["composite"] > 80

    def test_low_sub_scores_yield_low_composite(self):
        ti = _make_technicals(tech_score=10.0)
        fd = _make_fundamentals(fundamental_score=10.0)
        vd = _make_valuation(valuation_score=10.0)
        ed = _make_earnings()
        ne = _make_news(news_score=10.0)
        scores = compute_scores(ti, fd, vd, ed, ne, catalyst_score=10.0, sector_macro_score=10.0, risk_reward_score=10.0)
        for horizon in ("short_term", "medium_term", "long_term"):
            assert scores[horizon]["composite"] < 40


# ---------------------------------------------------------------------------
# Decision logic tests
# ---------------------------------------------------------------------------

class TestDecisionLogic:
    def test_buy_now_short_term_when_score_ge_80_not_extended(self):
        ti = _make_technicals(is_extended=False)
        decision = _decide_short_term(82, ti)
        assert decision == "BUY_NOW"

    def test_buy_starter_short_term_when_score_70_to_79(self):
        ti = _make_technicals(is_extended=False)
        decision = _decide_short_term(74, ti)
        assert decision == "BUY_STARTER"

    def test_wait_for_pullback_short_term_when_extended(self):
        ti = _make_technicals(is_extended=True)
        decision = _decide_short_term(82, ti)
        assert decision == "WAIT_FOR_PULLBACK"

    def test_avoid_short_term_when_score_below_50(self):
        ti = _make_technicals(is_extended=False)
        decision = _decide_short_term(45, ti)
        assert decision == "AVOID"

    def test_buy_now_medium_term_when_score_ge_82_not_extended(self):
        ti = _make_technicals(is_extended=False)
        ed = _make_earnings()
        decision = _decide_medium_term(84, ti, ed)
        assert decision == "BUY_NOW"

    def test_buy_starter_medium_term_when_72_to_81(self):
        ti = _make_technicals(is_extended=False)
        ed = _make_earnings()
        decision = _decide_medium_term(75, ti, ed)
        assert decision == "BUY_STARTER"

    def test_watchlist_medium_term_when_55_to_67(self):
        ti = _make_technicals(is_extended=False)
        ed = _make_earnings()
        decision = _decide_medium_term(60, ti, ed)
        assert decision == "WATCHLIST"

    def test_avoid_medium_term_when_below_55(self):
        ti = _make_technicals(is_extended=False)
        ed = _make_earnings()
        decision = _decide_medium_term(50, ti, ed)
        assert decision == "AVOID"

    def test_buy_now_long_term_when_score_ge_85_not_extended(self):
        ti = _make_technicals(is_extended=False)
        decision = _decide_long_term(87, ti)
        assert decision == "BUY_NOW"

    def test_buy_starter_long_term_when_75_to_84(self):
        ti = _make_technicals(is_extended=False)
        decision = _decide_long_term(78, ti)
        assert decision == "BUY_STARTER"

    def test_watchlist_long_term_when_60_to_74(self):
        ti = _make_technicals(is_extended=False)
        decision = _decide_long_term(65, ti)
        assert decision == "WATCHLIST"

    def test_avoid_long_term_when_below_60(self):
        ti = _make_technicals(is_extended=False)
        decision = _decide_long_term(55, ti)
        assert decision == "AVOID"


# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_high_confidence_at_80_plus(self):
        assert _confidence(85) == "high"

    def test_medium_high_at_65_to_79(self):
        assert _confidence(70) == "medium_high"

    def test_medium_at_50_to_64(self):
        assert _confidence(55) == "medium"

    def test_low_below_50(self):
        assert _confidence(40) == "low"


# ---------------------------------------------------------------------------
# Risk management tests
# ---------------------------------------------------------------------------

class TestRiskManagement:
    def _ti(self, **kwargs) -> TechnicalIndicators:
        return _make_technicals(**kwargs)

    def test_preferred_entry_le_price_when_waiting(self):
        ti = self._ti()
        price = 100.0
        entry, exit_, rr, sizing = compute_risk_management(price, ti, "WAIT_FOR_PULLBACK")
        assert entry.preferred_entry <= price

    def test_stop_loss_below_entry(self):
        ti = self._ti()
        price = 100.0
        entry, exit_, rr, sizing = compute_risk_management(price, ti, "BUY_NOW")
        assert exit_.stop_loss < (entry.preferred_entry or price)

    def test_rr_ratio_positive_when_buy_now(self):
        ti = self._ti()
        price = 100.0
        entry, exit_, rr, sizing = compute_risk_management(price, ti, "BUY_NOW")
        if rr.ratio is not None:
            assert rr.ratio > 0

    def test_rr_ratio_ge_2_when_good_setup(self):
        # With nearest support at 95 and nearest resistance at 115 on price 100:
        # downside = 100 - (95 * 0.99) = 5.95, upside = 115 - 100 = 15 → R/R > 2
        ti = self._ti(nearest_support=95.0, nearest_resistance=115.0)
        price = 100.0
        entry, exit_, rr, sizing = compute_risk_management(price, ti, "BUY_NOW")
        if rr.ratio is not None:
            assert rr.ratio >= 2.0, f"R/R {rr.ratio} < 2.0"

    def test_earnings_reduces_position_size(self):
        ti = self._ti()
        _, _, _, size_normal = compute_risk_management(100.0, ti, "BUY_NOW", within_30_days_earnings=False)
        _, _, _, size_earnings = compute_risk_management(100.0, ti, "BUY_NOW", within_30_days_earnings=True)
        assert size_earnings.suggested_starter_pct_of_full < size_normal.suggested_starter_pct_of_full

    def test_aggressive_larger_position_than_conservative(self):
        ti = self._ti()
        _, _, _, conservative = compute_risk_management(100.0, ti, "BUY_NOW", risk_profile="conservative")
        _, _, _, aggressive = compute_risk_management(100.0, ti, "BUY_NOW", risk_profile="aggressive")
        assert aggressive.max_portfolio_allocation_pct > conservative.max_portfolio_allocation_pct


# ---------------------------------------------------------------------------
# build_recommendations integration
# ---------------------------------------------------------------------------

class TestBuildRecommendations:
    def test_returns_correct_number_of_recommendations(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = {
            "short_term": {"composite": 75.0, "technical": 75.0, "fundamental": 70.0, "valuation": 65.0, "earnings": 60.0, "news_sentiment": 65.0, "catalyst": 50.0, "sector_macro": 50.0, "risk_reward": 50.0},
            "medium_term": {"composite": 72.0, "technical": 75.0, "fundamental": 70.0, "valuation": 65.0, "earnings": 60.0, "news_sentiment": 65.0, "catalyst": 50.0, "sector_macro": 50.0, "risk_reward": 50.0},
            "long_term": {"composite": 68.0, "technical": 75.0, "fundamental": 70.0, "valuation": 65.0, "earnings": 60.0, "news_sentiment": 65.0, "catalyst": 50.0, "sector_macro": 50.0, "risk_reward": 50.0},
        }
        recs = build_recommendations(ti, fd, vd, ed, ne, scores, ["short_term", "medium_term", "long_term"], "moderate", 100.0)
        assert len(recs) == 3

    def test_each_recommendation_has_required_fields(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = {
            "short_term": {"composite": 80.0, "technical": 80.0, "fundamental": 70.0, "valuation": 65.0, "earnings": 60.0, "news_sentiment": 65.0, "catalyst": 50.0, "sector_macro": 50.0, "risk_reward": 50.0},
        }
        recs = build_recommendations(ti, fd, vd, ed, ne, scores, ["short_term"], "moderate", 100.0)
        rec = recs[0]
        assert rec.decision in ("BUY_NOW", "BUY_STARTER", "WAIT_FOR_PULLBACK", "BUY_ON_BREAKOUT", "WATCHLIST", "AVOID")
        assert rec.entry_plan is not None
        assert rec.exit_plan is not None
        assert rec.risk_reward is not None
        assert rec.position_sizing is not None
        assert len(rec.data_warnings) >= 1  # at least peer comparison warning

    def test_data_warnings_include_peer_comparison(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = {"short_term": {"composite": 70.0, "technical": 70.0, "fundamental": 70.0, "valuation": 65.0, "earnings": 60.0, "news_sentiment": 65.0, "catalyst": 50.0, "sector_macro": 50.0, "risk_reward": 50.0}}
        recs = build_recommendations(ti, fd, vd, ed, ne, scores, ["short_term"], "moderate", 100.0)
        assert any("Peer" in w for w in recs[0].data_warnings)

    def test_buy_now_when_all_high_scores(self):
        ti = _make_technicals(is_extended=False, tech_score=90.0)
        fd = _make_fundamentals(fundamental_score=90.0)
        vd = _make_valuation(valuation_score=90.0)
        ed = _make_earnings()
        ne = _make_news(news_score=90.0)
        scores = {"short_term": {"composite": 85.0, "technical": 90.0, "fundamental": 90.0, "valuation": 90.0, "earnings": 70.0, "news_sentiment": 90.0, "catalyst": 90.0, "sector_macro": 90.0, "risk_reward": 90.0}}
        recs = build_recommendations(ti, fd, vd, ed, ne, scores, ["short_term"], "moderate", 100.0)
        assert recs[0].decision == "BUY_NOW"

    def test_avoid_when_all_low_scores(self):
        ti = _make_technicals(trend="downtrend", is_extended=False, tech_score=20.0)
        fd = _make_fundamentals(fundamental_score=20.0)
        vd = _make_valuation(valuation_score=20.0)
        ed = _make_earnings(beat_rate=0.0, avg_surprise=-5.0)
        ne = _make_news(news_score=10.0)
        scores = {"short_term": {"composite": 25.0, "technical": 20.0, "fundamental": 20.0, "valuation": 20.0, "earnings": 20.0, "news_sentiment": 10.0, "catalyst": 20.0, "sector_macro": 20.0, "risk_reward": 20.0}}
        recs = build_recommendations(ti, fd, vd, ed, ne, scores, ["short_term"], "moderate", 100.0)
        assert recs[0].decision == "AVOID"
