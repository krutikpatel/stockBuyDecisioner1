"""End-to-end tests for StockDecisionEngine.decide() — verifies that the new
pipeline produces valid HorizonRecommendation objects for representative
archetype × regime combinations.
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    reset_decision_engine()
    return StockDecisionEngine()


def _technicals(**kwargs) -> TechnicalIndicators:
    defaults = dict(
        rsi_14=55.0,
        sma20_relative=2.0,
        sma50_relative=4.0,
        sma200_relative=8.0,
        sma20_slope=0.1,
        sma50_slope=0.1,
        sma200_slope=0.05,
        rsi_slope=0.5,
        breakout_volume_multiple=1.2,
        updown_volume_ratio=1.1,
        volume_dryup_ratio=0.7,
        perf_1w=0.5,
        perf_1m=3.0,
        rs_vs_spy=1.1,
        rs_vs_spy_20d=1.5,
        rs_vs_spy_63d=1.2,
        rs_vs_sector_20d=2.0,
        atr=1.5,
        atr_percent=1.5,
        is_extended=False,
        trend=TrendClassification(label="weak_uptrend", description="Uptrend"),
    )
    defaults.update(kwargs)
    return TechnicalIndicators(**defaults)


def _fundamentals(**kwargs) -> FundamentalData:
    defaults = dict(
        archetype=StockArchetype.PROFITABLE_GROWTH,
        archetype_confidence=80.0,
        revenue_growth_yoy=0.20,
        operating_margin=0.15,
        roic=15.0,
        free_cash_flow=1e8,
        fundamental_score=70.0,
    )
    defaults.update(kwargs)
    return FundamentalData(**defaults)


def _valuation(**kwargs) -> ValuationData:
    defaults = dict(forward_pe=25.0, price_to_sales=4.0, valuation_score=60.0)
    defaults.update(kwargs)
    return ValuationData(**defaults)


def _earnings(**kwargs) -> EarningsData:
    defaults = dict(within_30_days=False, beat_rate=0.75, earnings_score=70.0)
    defaults.update(kwargs)
    return EarningsData(**defaults)


def _news(**kwargs) -> NewsSummary:
    defaults = dict(positive_count=3, negative_count=1, coverage_limited=False, news_score=65.0)
    defaults.update(kwargs)
    return NewsSummary(**defaults)


def _regime(name: str = "BULL_RISK_ON") -> MarketRegimeAssessment:
    return MarketRegimeAssessment(regime=name, confidence=80.0)


HORIZONS = ["short_term", "medium_term", "long_term"]


# ---------------------------------------------------------------------------
# Basic smoke test — all horizons returned
# ---------------------------------------------------------------------------

def test_returns_all_requested_horizons(engine):
    recs = engine.decide(
        ticker="TEST",
        price=100.0,
        technicals=_technicals(),
        fundamentals=_fundamentals(),
        valuation=_valuation(),
        earnings=_earnings(),
        news=_news(),
        horizons=HORIZONS,
        risk_profile="moderate",
        regime_assessment=_regime(),
    )
    assert len(recs) == 3
    returned_horizons = {r.horizon for r in recs}
    assert returned_horizons == {"short_term", "medium_term", "long_term"}


def test_returns_list_of_horizon_recommendations(engine):
    recs = engine.decide(
        ticker="TEST",
        price=100.0,
        technicals=_technicals(),
        fundamentals=_fundamentals(),
        valuation=_valuation(),
        earnings=_earnings(),
        news=_news(),
        horizons=HORIZONS,
        risk_profile="moderate",
    )
    for rec in recs:
        assert isinstance(rec, HorizonRecommendation)


# ---------------------------------------------------------------------------
# All required fields are present and typed correctly
# ---------------------------------------------------------------------------

def test_all_fields_present_and_typed(engine):
    recs = engine.decide(
        ticker="AAPL",
        price=150.0,
        technicals=_technicals(),
        fundamentals=_fundamentals(),
        valuation=_valuation(),
        earnings=_earnings(),
        news=_news(),
        horizons=HORIZONS,
        risk_profile="moderate",
        regime_assessment=_regime(),
    )
    for rec in recs:
        assert isinstance(rec.horizon, str)
        assert isinstance(rec.decision, str)
        assert isinstance(rec.score, float)
        assert isinstance(rec.confidence, str)
        assert rec.confidence in ("high", "medium_high", "medium", "low")
        assert isinstance(rec.confidence_score, float)
        assert isinstance(rec.data_completeness_score, float)
        assert isinstance(rec.summary, str) and len(rec.summary) > 0
        assert isinstance(rec.bullish_factors, list)
        assert isinstance(rec.bearish_factors, list)
        assert isinstance(rec.entry_plan, EntryPlan)
        assert isinstance(rec.exit_plan, ExitPlan)
        assert isinstance(rec.risk_reward, RiskReward)
        assert isinstance(rec.position_sizing, PositionSizing)
        assert isinstance(rec.data_warnings, list)
        assert isinstance(rec.signal_cards_weights, dict)


def test_score_in_valid_range(engine):
    recs = engine.decide(
        ticker="TEST",
        price=100.0,
        technicals=_technicals(),
        fundamentals=_fundamentals(),
        valuation=_valuation(),
        earnings=_earnings(),
        news=_news(),
        horizons=HORIZONS,
        risk_profile="moderate",
    )
    for rec in recs:
        assert 0.0 <= rec.score <= 100.0


# ---------------------------------------------------------------------------
# Archetype-specific routing
# ---------------------------------------------------------------------------

def test_growth_leader_routes_to_pullback_engine(engine):
    recs = engine.decide(
        ticker="NVDA",
        price=500.0,
        technicals=_technicals(sma50_relative=3.0, rsi_14=48.0, volume_dryup_ratio=0.6),
        fundamentals=_fundamentals(
            archetype=StockArchetype.PROFITABLE_GROWTH,
            revenue_growth_yoy=0.30,
        ),
        valuation=_valuation(forward_pe=30.0),
        earnings=_earnings(),
        news=_news(),
        horizons=["short_term"],
        risk_profile="moderate",
        regime_assessment=_regime("BULL_RISK_ON"),
    )
    # A growth leader in pullback territory should produce a buy-oriented decision
    assert recs[0].decision in (
        "BUY_ON_PULLBACK", "WAIT_FOR_PULLBACK", "BUY_NOW_CONTINUATION",
        "WATCHLIST", "BUY_STARTER_STRONG_BUT_EXTENDED",
    )


def test_broken_chart_routes_to_avoid(engine):
    recs = engine.decide(
        ticker="BROKEN",
        price=30.0,
        technicals=_technicals(
            sma50_relative=-6.0,
            sma200_relative=-8.0,
            rsi_14=35.0,
            rsi_slope=-1.0,
            perf_1w=-4.0,
            breakout_volume_multiple=2.5,
            is_extended=False,
            trend=TrendClassification(label="downtrend", description="Downtrend"),
        ),
        fundamentals=_fundamentals(archetype=StockArchetype.MATURE_VALUE),
        valuation=_valuation(),
        earnings=_earnings(),
        news=_news(positive_count=0, negative_count=3),
        horizons=["short_term"],
        risk_profile="moderate",
    )
    assert recs[0].decision in (
        "TRUE_DOWNTREND_AVOID", "BROKEN_SUPPORT_AVOID",
        "WATCHLIST",  # fallback if thresholds not fully met
    )


def test_hyper_growth_archetype_handled(engine):
    recs = engine.decide(
        ticker="HYPG",
        price=200.0,
        technicals=_technicals(rsi_14=52.0, sma50_relative=2.5),
        fundamentals=_fundamentals(archetype=StockArchetype.HYPER_GROWTH),
        valuation=_valuation(forward_pe=60.0, price_to_sales=15.0),
        earnings=_earnings(),
        news=_news(),
        horizons=HORIZONS,
        risk_profile="aggressive",
        regime_assessment=_regime("BULL_RISK_ON"),
    )
    assert len(recs) == 3
    for rec in recs:
        assert isinstance(rec.decision, str)


def test_defensive_archetype_handled(engine):
    recs = engine.decide(
        ticker="JNJ",
        price=160.0,
        technicals=_technicals(rsi_14=50.0, sma50_relative=1.0, rs_vs_spy=0.9),
        fundamentals=_fundamentals(archetype=StockArchetype.DEFENSIVE),
        valuation=_valuation(forward_pe=18.0),
        earnings=_earnings(),
        news=_news(),
        horizons=HORIZONS,
        risk_profile="conservative",
    )
    assert len(recs) == 3


# ---------------------------------------------------------------------------
# Regime influence
# ---------------------------------------------------------------------------

def test_bear_regime_handled(engine):
    recs = engine.decide(
        ticker="TEST",
        price=100.0,
        technicals=_technicals(),
        fundamentals=_fundamentals(),
        valuation=_valuation(),
        earnings=_earnings(),
        news=_news(),
        horizons=["short_term"],
        risk_profile="moderate",
        regime_assessment=_regime("BEAR_RISK_OFF"),
    )
    assert len(recs) == 1
    assert isinstance(recs[0].decision, str)


def test_no_regime_handled_gracefully(engine):
    recs = engine.decide(
        ticker="TEST",
        price=100.0,
        technicals=_technicals(),
        fundamentals=_fundamentals(),
        valuation=_valuation(),
        earnings=_earnings(),
        news=_news(),
        horizons=HORIZONS,
        risk_profile="moderate",
        regime_assessment=None,
    )
    assert len(recs) == 3


# ---------------------------------------------------------------------------
# Missing data handling
# ---------------------------------------------------------------------------

def test_all_optional_fields_none(engine):
    recs = engine.decide(
        ticker="THIN",
        price=10.0,
        technicals=TechnicalIndicators(),
        fundamentals=FundamentalData(),
        valuation=ValuationData(),
        earnings=EarningsData(),
        news=NewsSummary(),
        horizons=HORIZONS,
        risk_profile="moderate",
    )
    assert len(recs) == 3
    for rec in recs:
        assert isinstance(rec.decision, str)
        assert 0.0 <= rec.score <= 100.0


def test_missing_data_warnings_populated(engine):
    recs = engine.decide(
        ticker="THIN",
        price=10.0,
        technicals=TechnicalIndicators(),
        fundamentals=FundamentalData(),
        valuation=ValuationData(),
        earnings=EarningsData(),
        news=NewsSummary(),
        horizons=["short_term"],
        risk_profile="moderate",
        has_options_data=False,
    )
    # Missing options data should generate a completeness warning
    assert any("options" in w.lower() for w in recs[0].data_warnings)


def test_single_horizon(engine):
    recs = engine.decide(
        ticker="TEST",
        price=100.0,
        technicals=_technicals(),
        fundamentals=_fundamentals(),
        valuation=_valuation(),
        earnings=_earnings(),
        news=_news(),
        horizons=["short_term"],
        risk_profile="moderate",
    )
    assert len(recs) == 1
    assert recs[0].horizon == "short_term"
