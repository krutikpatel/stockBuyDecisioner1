"""Phase 4 unit tests: scoring, recommendation, and risk management."""
import pytest

from app.models.market import MarketRegime, MarketRegimeAssessment, TechnicalIndicators, TrendClassification, SupportResistanceLevels
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

    def test_buy_on_pullback_short_term_when_extended(self):
        ti = _make_technicals(is_extended=True)
        decision = _decide_short_term(82, ti)
        assert decision == "BUY_ON_PULLBACK"

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
        from app.services.recommendation_service import ALL_DECISIONS
        assert rec.decision in ALL_DECISIONS
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


# ---------------------------------------------------------------------------
# US-004: Regime-aware scoring tests
# ---------------------------------------------------------------------------

def _make_regime(regime: str, confidence: float = 80.0) -> MarketRegimeAssessment:
    return MarketRegimeAssessment(
        regime=regime,
        confidence=confidence,
        implication="test",
        spy_above_50dma=True,
        spy_above_200dma=True,
        qqq_above_200dma=True,
    )


class TestRegimeAwareScoring:
    def test_new_weight_keys_present_in_result(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = compute_scores(ti, fd, vd, ed, ne)
        assert "technical_momentum" in scores["short_term"]
        assert "earnings_revision" in scores["medium_term"]
        assert "business_quality" in scores["long_term"]

    def test_bull_regime_boosts_short_term_composite(self):
        """Bull regime multipliers should raise the short-term composite."""
        ti = _make_technicals(tech_score=70.0)
        fd = _make_fundamentals(fundamental_score=70.0)
        vd = _make_valuation(valuation_score=70.0)
        ed = _make_earnings()
        ne = _make_news(news_score=70.0)
        no_regime = compute_scores(ti, fd, vd, ed, ne)
        bull_regime = compute_scores(
            ti, fd, vd, ed, ne,
            regime_assessment=_make_regime(MarketRegime.BULL_RISK_ON, 85.0)
        )
        # Bull regime boosts technical_momentum and relative_strength
        # so short-term composite should be >= no-regime composite
        assert bull_regime["short_term"]["composite"] >= no_regime["short_term"]["composite"]

    def test_bear_regime_penalises_momentum_in_medium_term(self):
        """Bear regime should reduce growth_acceleration (which uses fundamental_score)."""
        ti = _make_technicals(tech_score=70.0)
        fd = _make_fundamentals(fundamental_score=70.0)
        vd = _make_valuation(valuation_score=70.0)
        ed = _make_earnings()
        ne = _make_news(news_score=70.0)
        no_regime = compute_scores(ti, fd, vd, ed, ne)
        bear_regime = compute_scores(
            ti, fd, vd, ed, ne,
            regime_assessment=_make_regime(MarketRegime.BEAR_RISK_OFF, 80.0)
        )
        # Bear regime multiplier reduces technical_momentum → lower short-term composite
        assert bear_regime["short_term"]["composite"] <= no_regime["short_term"]["composite"]

    def test_missing_regime_defaults_neutral(self):
        """Without regime_assessment, market_regime slot = 50 and no multipliers."""
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = compute_scores(ti, fd, vd, ed, ne, regime_assessment=None)
        assert scores["short_term"]["market_regime"] == 50.0

    def test_bull_regime_market_regime_score_above_50(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = compute_scores(
            ti, fd, vd, ed, ne,
            regime_assessment=_make_regime(MarketRegime.BULL_RISK_ON, 85.0)
        )
        assert scores["short_term"]["market_regime"] > 50.0

    def test_bear_regime_market_regime_score_below_50(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        scores = compute_scores(
            ti, fd, vd, ed, ne,
            regime_assessment=_make_regime(MarketRegime.BEAR_RISK_OFF, 80.0)
        )
        assert scores["short_term"]["market_regime"] < 50.0

    def test_all_composites_in_valid_range_with_regime(self):
        ti = _make_technicals()
        fd = _make_fundamentals()
        vd = _make_valuation()
        ed = _make_earnings()
        ne = _make_news()
        for regime in MarketRegime.ALL:
            scores = compute_scores(
                ti, fd, vd, ed, ne,
                regime_assessment=_make_regime(regime, 80.0)
            )
            for horizon in ("short_term", "medium_term", "long_term"):
                c = scores[horizon]["composite"]
                assert 0 <= c <= 100, f"{regime}/{horizon}: {c} out of range"


# ---------------------------------------------------------------------------
# US-005: Expanded Decision Labels
# ---------------------------------------------------------------------------

from app.services.recommendation_service import (
    ALL_DECISIONS,
    _decide_short_term,
    _decide_medium_term,
    _decide_long_term,
    _chart_is_weak,
    _business_deteriorating,
)


def _make_weak_chart_technicals() -> TechnicalIndicators:
    """Downtrend + weak relative strength → _chart_is_weak() returns True."""
    return _make_technicals(trend="downtrend", rs_spy=0.6, tech_score=25.0)


def _make_deteriorating_fundamentals() -> FundamentalData:
    """Declining revenue + negative operating margin → _business_deteriorating() True."""
    return FundamentalData(
        revenue_growth_yoy=-0.15,
        operating_margin=-0.08,
        free_cash_flow=-100_000_000,
        fundamental_score=20.0,
    )


def _make_deteriorating_earnings() -> EarningsData:
    return EarningsData(beat_rate=0.30, avg_eps_surprise_pct=-3.0, within_30_days=False, earnings_score=20.0)


class TestExpandedDecisionLabels:

    def test_avoid_bad_chart_when_downtrend_and_weak_rs(self):
        ti = _make_weak_chart_technicals()
        fd = _make_fundamentals(fundamental_score=40.0)
        ed = _make_earnings()
        decision = _decide_short_term(40.0, ti, fundamentals=fd, earnings=ed)
        assert decision == "AVOID_BAD_CHART"

    def test_avoid_bad_business_when_revenue_declining_and_margins_negative(self):
        ti = _make_technicals(trend="strong_uptrend", rs_spy=1.1, tech_score=50.0)
        fd = _make_deteriorating_fundamentals()
        ed = _make_deteriorating_earnings()
        decision = _decide_short_term(45.0, ti, fundamentals=fd, earnings=ed)
        assert decision == "AVOID_BAD_BUSINESS"

    def test_buy_after_earnings_when_earnings_near_and_score_middling(self):
        ti = _make_technicals(is_extended=False)
        fd = _make_fundamentals()
        ed = EarningsData(beat_rate=0.75, avg_eps_surprise_pct=3.0, within_30_days=True, earnings_score=65.0)
        decision = _decide_short_term(62.0, ti, fundamentals=fd, earnings=ed)
        assert decision == "BUY_AFTER_EARNINGS"

    def test_buy_starter_extended_in_bull_regime_when_extended(self):
        ti = _make_technicals(is_extended=True, tech_score=80.0)
        bull = MarketRegimeAssessment(
            regime=MarketRegime.BULL_RISK_ON, confidence=85.0,
            implication="bull", spy_above_50dma=True, spy_above_200dma=True, qqq_above_200dma=True,
        )
        decision = _decide_short_term(75.0, ti, regime=bull)
        assert decision == "BUY_STARTER_EXTENDED"

    def test_buy_on_pullback_in_non_bull_regime_when_extended(self):
        ti = _make_technicals(is_extended=True, tech_score=80.0)
        bear = MarketRegimeAssessment(
            regime=MarketRegime.BEAR_RISK_OFF, confidence=80.0,
            implication="bear", spy_above_50dma=False, spy_above_200dma=False, qqq_above_200dma=False,
        )
        decision = _decide_short_term(75.0, ti, regime=bear)
        assert decision == "BUY_ON_PULLBACK"

    def test_chart_is_weak_helper_requires_both_downtrend_and_low_rs(self):
        downtrend_strong_rs = _make_technicals(trend="downtrend", rs_spy=1.1)
        uptrend_weak_rs = _make_technicals(trend="strong_uptrend", rs_spy=0.5)
        both_weak = _make_technicals(trend="downtrend", rs_spy=0.5)
        assert not _chart_is_weak(downtrend_strong_rs)
        assert not _chart_is_weak(uptrend_weak_rs)
        assert _chart_is_weak(both_weak)

    def test_business_deteriorating_requires_revenue_decline_plus_secondary(self):
        fd_good = FundamentalData(revenue_growth_yoy=0.10, operating_margin=0.15)
        ed_good = EarningsData(beat_rate=0.80)
        fd_bad = _make_deteriorating_fundamentals()
        ed_bad = _make_deteriorating_earnings()
        assert not _business_deteriorating(fd_good, ed_good)
        assert _business_deteriorating(fd_bad, ed_bad)

    def test_all_decisions_constant_contains_expected_labels(self):
        expected = {
            "BUY_NOW", "BUY_STARTER", "BUY_STARTER_EXTENDED", "BUY_ON_PULLBACK",
            "BUY_ON_BREAKOUT", "BUY_AFTER_EARNINGS", "WATCHLIST",
            "AVOID_BAD_BUSINESS", "AVOID_BAD_CHART", "AVOID",
        }
        assert expected.issubset(ALL_DECISIONS)

    def test_avoid_bad_chart_triggers_in_medium_term_for_weak_chart_low_score(self):
        ti = _make_weak_chart_technicals()
        ed = _make_earnings()
        decision = _decide_medium_term(45.0, ti, ed)
        assert decision == "AVOID_BAD_CHART"

    def test_avoid_bad_business_triggers_in_medium_term(self):
        ti = _make_technicals(trend="strong_uptrend", rs_spy=1.1, tech_score=60.0)
        fd = _make_deteriorating_fundamentals()
        ed = _make_deteriorating_earnings()
        decision = _decide_medium_term(55.0, ti, ed, fundamentals=fd)
        assert decision == "AVOID_BAD_BUSINESS"

    def test_avoid_bad_chart_triggers_in_long_term_for_weak_chart_low_score(self):
        ti = _make_weak_chart_technicals()
        fd = _make_fundamentals()
        ed = _make_earnings()
        decision = _decide_long_term(50.0, ti, fundamentals=fd, earnings=ed)
        assert decision == "AVOID_BAD_CHART"

    def test_bull_regime_decision_is_not_generic_avoid_when_strong_chart(self):
        """In BULL_RISK_ON, an expensive stock with strong momentum should not be plain AVOID."""
        ti = _make_technicals(is_extended=False, tech_score=85.0)
        bull = MarketRegimeAssessment(
            regime=MarketRegime.BULL_RISK_ON, confidence=85.0,
            implication="bull", spy_above_50dma=True, spy_above_200dma=True, qqq_above_200dma=True,
        )
        decision = _decide_short_term(82.0, ti, regime=bull)
        assert decision != "AVOID"
        assert decision.startswith("BUY")
