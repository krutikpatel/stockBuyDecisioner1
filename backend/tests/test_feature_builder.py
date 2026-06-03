"""Tests for build_feature_snapshot() adapter in feature_builder.py."""
from __future__ import annotations
import pytest
from app.features.feature_builder import build_feature_snapshot, _ARCHETYPE_TO_CATEGORY
from app.features.feature_snapshot import FeatureSnapshot
from app.models.market import TechnicalIndicators, TrendClassification, SupportResistanceLevels, MarketData, MarketRegimeAssessment
from app.models.fundamentals import FundamentalData, ValuationData, StockArchetype
from app.models.earnings import EarningsData


_TREND_UP = TrendClassification(label="strong_uptrend", description="Strong uptrend")
_TREND_DOWN = TrendClassification(label="downtrend", description="Downtrend")
_SR = SupportResistanceLevels(supports=[], resistances=[])


def _make_technicals(**kwargs) -> TechnicalIndicators:
    defaults = dict(
        trend=_TREND_UP,
        support_resistance=_SR,
        rsi_14=55.0,
        sma50_relative=2.0,
        sma200_relative=10.0,
        perf_1m=5.0,
        rs_vs_spy_20d=3.0,
    )
    defaults.update(kwargs)
    return TechnicalIndicators(**defaults)


def _make_fundamentals(**kwargs) -> FundamentalData:
    defaults = dict(
        archetype=StockArchetype.PROFITABLE_GROWTH,
        revenue_growth_yoy=0.20,
        operating_margin=0.18,
        sector="Technology",
    )
    defaults.update(kwargs)
    return FundamentalData(**defaults)


def _make_valuation(**kwargs) -> ValuationData:
    defaults = dict(forward_pe=30.0, peg_ratio=1.5)
    defaults.update(kwargs)
    return ValuationData(**defaults)


def _make_earnings(**kwargs) -> EarningsData:
    defaults = dict(beat_rate=0.75)
    defaults.update(kwargs)
    return EarningsData(**defaults)


def _make_market_data(**kwargs) -> MarketData:
    return MarketData(
        ticker="TEST",
        current_price=100.0,
        previous_close=99.0,
        open=99.5,
        day_high=101.0,
        day_low=98.0,
        volume=1_000_000,
        avg_volume_30d=2_000_000,
        market_cap=50_000_000_000,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------

def test_snapshot_returns_correct_type():
    snap = build_feature_snapshot(
        ticker="AAPL",
        price=150.0,
        technicals=_make_technicals(),
        fundamentals=_make_fundamentals(),
        valuation=_make_valuation(),
        earnings=_make_earnings(),
    )
    assert isinstance(snap, FeatureSnapshot)
    assert snap.ticker == "AAPL"
    assert snap.price == 150.0


def test_technical_fields_mapped():
    tech = _make_technicals(rsi_14=62.0, sma50_relative=3.5, adx=28.0)
    snap = build_feature_snapshot("X", 100.0, tech, _make_fundamentals(), _make_valuation(), _make_earnings())
    assert snap.rsi14 == 62.0
    assert snap.sma50_relative == 3.5
    assert snap.adx == 28.0


def test_trend_label_extracted():
    tech = _make_technicals(trend=_TREND_DOWN)
    snap = build_feature_snapshot("X", 100.0, tech, _make_fundamentals(), _make_valuation(), _make_earnings())
    assert snap.trend_label == "downtrend"


def test_fundamental_fields_mapped():
    fund = _make_fundamentals(revenue_growth_yoy=0.30, operating_margin=0.22)
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), fund, _make_valuation(), _make_earnings())
    assert snap.sales_growth_yoy == 0.30
    assert snap.operating_margin == 0.22


def test_valuation_fields_mapped():
    val = _make_valuation(forward_pe=45.0, peg_ratio=2.5)
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), val, _make_earnings())
    assert snap.forward_pe == 45.0
    assert snap.peg_ratio == 2.5


def test_earnings_beat_rate_mapped():
    earn = _make_earnings(beat_rate=0.80)
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), earn)
    assert snap.beat_rate == 0.80


# ---------------------------------------------------------------------------
# Archetype translation
# ---------------------------------------------------------------------------

def test_archetype_translated_to_primary_category():
    fund = _make_fundamentals(archetype=StockArchetype.HYPER_GROWTH)
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), fund, _make_valuation(), _make_earnings())
    assert snap.primary_category == "HYPER_GROWTH_STORY"


def test_all_archetypes_have_mapping():
    for archetype in StockArchetype.ALL:
        assert archetype in _ARCHETYPE_TO_CATEGORY, f"Missing mapping for {archetype}"


def test_unknown_archetype_defaults():
    fund = _make_fundamentals(archetype="UNKNOWN_TYPE")
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), fund, _make_valuation(), _make_earnings())
    assert snap.primary_category == "PROFITABLE_GROWTH_LEADER"


# ---------------------------------------------------------------------------
# Market data and regime
# ---------------------------------------------------------------------------

def test_market_data_populates_volume_and_cap():
    md = _make_market_data()
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings(), market_data=md)
    assert snap.market_cap == 50_000_000_000
    assert snap.avg_volume == 2_000_000


def test_market_data_none_gives_none_fields():
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings(), market_data=None)
    assert snap.market_cap is None
    assert snap.avg_volume is None


def test_regime_assessment_mapped():
    regime = MarketRegimeAssessment(regime="BULL_RISK_ON", confidence=0.85)
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings(), regime_assessment=regime)
    assert snap.market_regime == "BULL_RISK_ON"
    assert snap.regime_confidence == 0.85


def test_no_regime_defaults_sideways():
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings())
    assert snap.market_regime == "SIDEWAYS_CHOPPY"


# ---------------------------------------------------------------------------
# Earnings days calculation
# ---------------------------------------------------------------------------

def test_earnings_days_computed():
    earn = _make_earnings(next_earnings_date="2026-06-20")
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), earn, as_of_date="2026-06-02")
    assert snap.earnings_days_away == 18


def test_earnings_days_none_when_no_date():
    earn = _make_earnings(next_earnings_date=None)
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), earn)
    assert snap.earnings_days_away is None


def test_earnings_days_none_when_past():
    earn = _make_earnings(next_earnings_date="2026-01-01")
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), earn, as_of_date="2026-06-02")
    assert snap.earnings_days_away is None


# ---------------------------------------------------------------------------
# to_dict round-trip
# ---------------------------------------------------------------------------

def test_to_dict_includes_all_none_fields():
    snap = build_feature_snapshot("X", 100.0, _make_technicals(), _make_fundamentals(), _make_valuation(), _make_earnings())
    d = snap.to_dict()
    assert isinstance(d, dict)
    assert "rsi14" in d
    assert "forward_pe" in d


def test_to_dict_values_match_snapshot_fields():
    tech = _make_technicals(rsi_14=71.0)
    snap = build_feature_snapshot("X", 100.0, tech, _make_fundamentals(), _make_valuation(), _make_earnings())
    assert snap.to_dict()["rsi14"] == 71.0
