"""
Story 6 TDD tests: 11 Signal Card Scoring Engine
Tests written BEFORE implementation.

Tests cover:
- Each of the 11 signal card scorers: high-score, low-score, missing-data cases
- SignalCard output fields (score, label, explanation, top_positives/negatives, warnings)
- score_all_cards() returns SignalCards with all 11 populated
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from app.models.market import TechnicalIndicators, TrendClassification, SupportResistanceLevels
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import SignalCard, SignalCardLabel, SignalCards

# Required nested objects for TechnicalIndicators
_TREND = TrendClassification(label="sideways", description="No clear trend")
_SR = SupportResistanceLevels(supports=[], resistances=[])
from app.services.signal_card_service import (
    score_momentum,
    score_trend,
    score_entry_timing,
    score_volume_accumulation,
    score_volatility_risk,
    score_relative_strength,
    score_growth,
    score_valuation,
    score_quality,
    score_ownership,
    score_catalyst,
    score_all_cards,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bullish_tech() -> TechnicalIndicators:
    """Strongly bullish technical indicators."""
    return TechnicalIndicators(
        trend=_TREND,
        support_resistance=_SR,
        rsi_14=58.0,
        macd_line=2.5,
        macd_signal=1.0,
        macd_histogram=1.5,
        ema8_relative=0.03,
        ema21_relative=0.05,
        sma20_relative=0.04,
        sma50_relative=0.06,
        sma200_relative=0.12,
        sma20_slope=0.002,
        sma50_slope=0.003,
        sma200_slope=0.001,
        adx=32.0,
        stochastic_rsi=0.55,
        atr_percent=1.5,
        bollinger_band_position=0.65,
        bollinger_band_width=0.04,
        perf_1w=2.0,
        perf_1m=5.0,
        perf_3m=12.0,
        perf_6m=20.0,
        perf_1y=35.0,
        vwap_deviation=0.02,
        obv_trend=1,
        ad_trend=1,
        chaikin_money_flow=0.15,
        volume_dryup_ratio=0.6,
        breakout_volume_multiple=2.0,
        updown_volume_ratio=1.4,
        rs_vs_qqq=5.0,
        return_pct_rank_20d=75.0,
        return_pct_rank_63d=80.0,
        max_drawdown_3m=-5.0,
        max_drawdown_1y=-12.0,
        technical_score=80.0,
        trend_score=75.0,
        volatility_weekly=0.18,
        volatility_monthly=0.20,
        dist_from_52w_high=-3.0,
        dist_from_52w_low=45.0,
    )


def _bearish_tech() -> TechnicalIndicators:
    """Strongly bearish technical indicators."""
    return TechnicalIndicators(
        trend=_TREND,
        support_resistance=_SR,
        rsi_14=28.0,
        macd_line=-2.5,
        macd_signal=-1.0,
        macd_histogram=-1.5,
        ema8_relative=-0.05,
        ema21_relative=-0.07,
        sma20_relative=-0.06,
        sma50_relative=-0.08,
        sma200_relative=-0.15,
        sma20_slope=-0.003,
        sma50_slope=-0.002,
        sma200_slope=-0.001,
        adx=35.0,
        stochastic_rsi=0.1,
        atr_percent=4.0,
        bollinger_band_position=0.1,
        bollinger_band_width=0.08,
        perf_1w=-4.0,
        perf_1m=-10.0,
        perf_3m=-20.0,
        perf_6m=-30.0,
        perf_1y=-40.0,
        vwap_deviation=-0.05,
        obv_trend=-1,
        ad_trend=-1,
        chaikin_money_flow=-0.2,
        volume_dryup_ratio=1.5,
        breakout_volume_multiple=0.5,
        updown_volume_ratio=0.6,
        rs_vs_qqq=-8.0,
        return_pct_rank_20d=15.0,
        return_pct_rank_63d=10.0,
        max_drawdown_3m=-25.0,
        max_drawdown_1y=-40.0,
        technical_score=20.0,
        trend_score=15.0,
        volatility_weekly=0.45,
        volatility_monthly=0.50,
        dist_from_52w_high=-35.0,
        dist_from_52w_low=5.0,
    )


def _good_fundamentals() -> FundamentalData:
    return FundamentalData(
        revenue_ttm=1_000_000_000,
        revenue_growth_yoy=0.25,
        revenue_growth_qoq=0.06,
        eps_ttm=5.0,
        eps_growth_yoy=0.20,
        gross_margin=0.65,
        operating_margin=0.25,
        net_margin=0.20,
        free_cash_flow=200_000_000,
        free_cash_flow_margin=0.20,
        current_ratio=2.5,
        debt_to_equity=30.0,
        roe=0.22,
        roic=0.18,
        roa=0.12,
        quick_ratio=1.8,
        long_term_debt_equity=0.3,
        sales_growth_ttm=0.22,
        sales_growth_3y=0.18,
        eps_growth_next_year=0.18,
        insider_ownership=0.08,
        insider_transactions=500_000,
        institutional_ownership=0.75,
        institutional_transactions=0.02,
        short_float=0.03,
        short_ratio=2.0,
        analyst_recommendation=1.8,
        analyst_target_price=200.0,
        target_price_distance=25.0,
        dividend_yield=0.015,
        beta=1.1,
        sector="Technology",
    )


def _weak_fundamentals() -> FundamentalData:
    return FundamentalData(
        revenue_ttm=500_000_000,
        revenue_growth_yoy=-0.05,
        eps_ttm=-1.0,
        eps_growth_yoy=-0.30,
        gross_margin=0.30,
        operating_margin=-0.05,
        net_margin=-0.08,
        free_cash_flow=-50_000_000,
        current_ratio=0.8,
        debt_to_equity=200.0,
        roe=-0.10,
        roic=-0.05,
        roa=-0.04,
        quick_ratio=0.5,
        long_term_debt_equity=2.5,
        sales_growth_ttm=-0.05,
        insider_ownership=0.01,
        insider_transactions=-200_000,
        institutional_ownership=0.30,
        institutional_transactions=-0.03,
        short_float=0.20,
        short_ratio=8.0,
        analyst_recommendation=4.0,
        analyst_target_price=80.0,
        target_price_distance=-10.0,
        beta=2.2,
        sector="Technology",
    )


def _good_valuation() -> ValuationData:
    return ValuationData(
        trailing_pe=18.0,
        forward_pe=15.0,
        peg_ratio=1.2,
        price_to_sales=3.0,
        ev_to_ebitda=12.0,
        price_to_fcf=20.0,
        fcf_yield=5.0,
        ev_sales=3.5,
        price_to_book=4.0,
    )


def _expensive_valuation() -> ValuationData:
    return ValuationData(
        trailing_pe=80.0,
        forward_pe=60.0,
        peg_ratio=5.0,
        price_to_sales=20.0,
        ev_to_ebitda=50.0,
        price_to_fcf=100.0,
        fcf_yield=1.0,
        ev_sales=18.0,
        price_to_book=25.0,
    )


def _good_earnings() -> EarningsData:
    return EarningsData(
        beat_rate=0.85,
        avg_eps_surprise_pct=6.0,
        last_earnings_date="2024-10-15",
        next_earnings_date="2025-01-20",
        within_30_days=False,
        earnings_score=80.0,
    )


def _good_news() -> NewsSummary:
    return NewsSummary(
        news_score=80.0,
        positive_count=5,
        negative_count=1,
        neutral_count=2,
    )


# ---------------------------------------------------------------------------
# score_momentum
# ---------------------------------------------------------------------------

class TestScoreMomentum:
    def test_high_score_bullish_tech(self):
        card = score_momentum(_bullish_tech())
        assert card.score >= 60
        assert card.label in (SignalCardLabel.BULLISH, SignalCardLabel.VERY_BULLISH)

    def test_low_score_bearish_tech(self):
        card = score_momentum(_bearish_tech())
        assert card.score < 50
        assert card.label in (SignalCardLabel.VERY_BEARISH, SignalCardLabel.BEARISH)

    def test_returns_signal_card(self):
        card = score_momentum(_bullish_tech())
        assert isinstance(card, SignalCard)
        assert card.name == "momentum"

    def test_missing_data_handled_gracefully(self):
        ti = TechnicalIndicators()  # all None
        card = score_momentum(ti)
        assert isinstance(card, SignalCard)
        assert 0 <= card.score <= 100

    def test_has_explanation(self):
        card = score_momentum(_bullish_tech())
        assert len(card.explanation) > 0


# ---------------------------------------------------------------------------
# score_trend
# ---------------------------------------------------------------------------

class TestScoreTrend:
    def test_high_score_bullish_tech(self):
        card = score_trend(_bullish_tech())
        assert card.score >= 60

    def test_low_score_bearish_tech(self):
        card = score_trend(_bearish_tech())
        assert card.score < 50

    def test_returns_signal_card(self):
        card = score_trend(_bullish_tech())
        assert isinstance(card, SignalCard)
        assert card.name == "trend"

    def test_missing_data_graceful(self):
        card = score_trend(TechnicalIndicators())
        assert 0 <= card.score <= 100


# ---------------------------------------------------------------------------
# score_entry_timing
# ---------------------------------------------------------------------------

class TestScoreEntryTiming:
    def test_ideal_rsi_range(self):
        ti = _bullish_tech()
        ti.rsi_14 = 55.0  # ideal 45-65
        card = score_entry_timing(ti)
        assert card.score >= 50

    def test_overbought_penalized(self):
        ti = _bullish_tech()
        ti.rsi_14 = 82.0  # overbought
        card = score_entry_timing(ti)
        # Score should be lower than when RSI is ideal
        ti2 = _bullish_tech()
        ti2.rsi_14 = 55.0
        card2 = score_entry_timing(ti2)
        assert card.score <= card2.score

    def test_returns_signal_card(self):
        card = score_entry_timing(_bullish_tech())
        assert isinstance(card, SignalCard)
        assert card.name == "entry_timing"

    def test_missing_data_graceful(self):
        card = score_entry_timing(TechnicalIndicators())
        assert 0 <= card.score <= 100


# ---------------------------------------------------------------------------
# score_volume_accumulation
# ---------------------------------------------------------------------------

class TestScoreVolumeAccumulation:
    def test_high_score_bullish_volume(self):
        card = score_volume_accumulation(_bullish_tech())
        assert card.score >= 60

    def test_low_score_bearish_volume(self):
        card = score_volume_accumulation(_bearish_tech())
        assert card.score < 50

    def test_returns_signal_card(self):
        card = score_volume_accumulation(_bullish_tech())
        assert isinstance(card, SignalCard)
        assert card.name == "volume_accumulation"

    def test_missing_data_graceful(self):
        card = score_volume_accumulation(TechnicalIndicators())
        assert 0 <= card.score <= 100


# ---------------------------------------------------------------------------
# score_volatility_risk
# ---------------------------------------------------------------------------

class TestScoreVolatilityRisk:
    def test_low_volatility_scores_well(self):
        card = score_volatility_risk(_bullish_tech())
        assert card.score >= 50

    def test_high_volatility_scores_poorly(self):
        card = score_volatility_risk(_bearish_tech())
        assert card.score < 60

    def test_returns_signal_card(self):
        card = score_volatility_risk(_bullish_tech())
        assert isinstance(card, SignalCard)
        assert card.name == "volatility_risk"

    def test_missing_data_graceful(self):
        card = score_volatility_risk(TechnicalIndicators())
        assert 0 <= card.score <= 100


# ---------------------------------------------------------------------------
# score_relative_strength
# ---------------------------------------------------------------------------

class TestScoreRelativeStrength:
    def test_high_rs_scores_well(self):
        card = score_relative_strength(_bullish_tech())
        assert card.score >= 60

    def test_low_rs_scores_poorly(self):
        card = score_relative_strength(_bearish_tech())
        assert card.score < 50

    def test_returns_signal_card(self):
        card = score_relative_strength(_bullish_tech())
        assert isinstance(card, SignalCard)
        assert card.name == "relative_strength"

    def test_missing_data_graceful(self):
        card = score_relative_strength(TechnicalIndicators())
        assert 0 <= card.score <= 100
        assert len(card.missing_data_warnings) > 0


# ---------------------------------------------------------------------------
# score_growth
# ---------------------------------------------------------------------------

class TestScoreGrowth:
    def test_strong_growth_scores_high(self):
        card = score_growth(_good_fundamentals(), _good_earnings())
        assert card.score >= 60

    def test_weak_growth_scores_low(self):
        card = score_growth(_weak_fundamentals(), _good_earnings())
        assert card.score < 50

    def test_returns_signal_card(self):
        card = score_growth(_good_fundamentals(), _good_earnings())
        assert isinstance(card, SignalCard)
        assert card.name == "growth"

    def test_missing_data_graceful(self):
        card = score_growth(FundamentalData(), EarningsData())
        assert 0 <= card.score <= 100

    def test_missing_data_adds_warnings(self):
        card = score_growth(FundamentalData(), EarningsData())
        assert len(card.missing_data_warnings) > 0


# ---------------------------------------------------------------------------
# score_valuation
# ---------------------------------------------------------------------------

class TestScoreValuation:
    def test_cheap_valuation_scores_high(self):
        card = score_valuation(_good_valuation())
        assert card.score >= 55

    def test_expensive_valuation_scores_low(self):
        card = score_valuation(_expensive_valuation())
        assert card.score < 45

    def test_returns_signal_card(self):
        card = score_valuation(_good_valuation())
        assert isinstance(card, SignalCard)
        assert card.name == "valuation"

    def test_missing_data_graceful(self):
        card = score_valuation(ValuationData())
        assert 0 <= card.score <= 100


# ---------------------------------------------------------------------------
# score_quality
# ---------------------------------------------------------------------------

class TestScoreQuality:
    def test_high_quality_scores_well(self):
        card = score_quality(_good_fundamentals())
        assert card.score >= 60

    def test_poor_quality_scores_low(self):
        card = score_quality(_weak_fundamentals())
        assert card.score < 50

    def test_returns_signal_card(self):
        card = score_quality(_good_fundamentals())
        assert isinstance(card, SignalCard)
        assert card.name == "quality"

    def test_missing_data_graceful(self):
        card = score_quality(FundamentalData())
        assert 0 <= card.score <= 100


# ---------------------------------------------------------------------------
# score_ownership
# ---------------------------------------------------------------------------

class TestScoreOwnership:
    def test_strong_ownership_scores_well(self):
        card = score_ownership(_good_fundamentals())
        assert card.score >= 55

    def test_weak_ownership_scores_poorly(self):
        card = score_ownership(_weak_fundamentals())
        assert card.score < 50

    def test_returns_signal_card(self):
        card = score_ownership(_good_fundamentals())
        assert isinstance(card, SignalCard)
        assert card.name == "ownership"

    def test_missing_data_graceful(self):
        card = score_ownership(FundamentalData())
        assert 0 <= card.score <= 100

    def test_high_short_float_is_noted(self):
        fd = _good_fundamentals()
        fd.short_float = 0.25  # 25% short float
        card = score_ownership(fd)
        # High short float could be squeeze risk — should be in positives or negatives
        all_factors = card.top_positives + card.top_negatives + card.missing_data_warnings
        assert len(all_factors) > 0


# ---------------------------------------------------------------------------
# score_catalyst
# ---------------------------------------------------------------------------

class TestScoreCatalyst:
    def test_good_catalysts_score_high(self):
        card = score_catalyst(_good_fundamentals(), _good_earnings(), _good_news())
        assert card.score >= 55

    def test_poor_catalysts_score_low(self):
        fd = _weak_fundamentals()
        earnings = EarningsData(beat_rate=0.25, avg_eps_surprise_pct=-3.0, earnings_score=20.0)
        news = NewsSummary(news_score=15.0, positive_count=1, negative_count=5, neutral_count=2)
        card = score_catalyst(fd, earnings, news)
        assert card.score < 50

    def test_returns_signal_card(self):
        card = score_catalyst(_good_fundamentals(), _good_earnings(), _good_news())
        assert isinstance(card, SignalCard)
        assert card.name == "catalyst"

    def test_missing_data_graceful(self):
        card = score_catalyst(FundamentalData(), EarningsData(), NewsSummary())
        assert 0 <= card.score <= 100


# ---------------------------------------------------------------------------
# score_all_cards integration
# ---------------------------------------------------------------------------

class TestScoreAllCards:
    def test_returns_signal_cards(self):
        result = score_all_cards(
            technicals=_bullish_tech(),
            fundamentals=_good_fundamentals(),
            valuation=_good_valuation(),
            earnings=_good_earnings(),
            news=_good_news(),
        )
        assert isinstance(result, SignalCards)

    def test_all_11_cards_populated(self):
        result = score_all_cards(
            technicals=_bullish_tech(),
            fundamentals=_good_fundamentals(),
            valuation=_good_valuation(),
            earnings=_good_earnings(),
            news=_good_news(),
        )
        for attr in [
            "momentum", "trend", "entry_timing", "volume_accumulation",
            "volatility_risk", "relative_strength", "growth", "valuation",
            "quality", "ownership", "catalyst",
        ]:
            card = getattr(result, attr)
            assert isinstance(card, SignalCard), f"{attr} card missing or wrong type"
            assert 0 <= card.score <= 100, f"{attr} score out of range: {card.score}"

    def test_bullish_scenario_mostly_bullish(self):
        result = score_all_cards(
            technicals=_bullish_tech(),
            fundamentals=_good_fundamentals(),
            valuation=_good_valuation(),
            earnings=_good_earnings(),
            news=_good_news(),
        )
        scores = [
            result.momentum.score, result.trend.score,
            result.growth.score, result.quality.score,
        ]
        assert sum(s >= 55 for s in scores) >= 3  # at least 3 of 4 should be bullish

    def test_bearish_scenario_mostly_bearish(self):
        result = score_all_cards(
            technicals=_bearish_tech(),
            fundamentals=_weak_fundamentals(),
            valuation=_expensive_valuation(),
            earnings=EarningsData(beat_rate=0.25, avg_eps_surprise_pct=-2.0, earnings_score=25.0),
            news=NewsSummary(news_score=15.0, negative_count=4, positive_count=1, neutral_count=1),
        )
        scores = [
            result.momentum.score, result.trend.score,
            result.growth.score, result.quality.score,
        ]
        assert sum(s < 50 for s in scores) >= 3

    def test_all_none_inputs_no_crash(self):
        result = score_all_cards(
            technicals=TechnicalIndicators(),
            fundamentals=FundamentalData(),
            valuation=ValuationData(),
            earnings=EarningsData(),
            news=NewsSummary(),
        )
        assert isinstance(result, SignalCards)
        for attr in [
            "momentum", "trend", "entry_timing", "volume_accumulation",
            "volatility_risk", "relative_strength", "growth", "valuation",
            "quality", "ownership", "catalyst",
        ]:
            card = getattr(result, attr)
            assert 0 <= card.score <= 100
