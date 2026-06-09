"""Tests for US-002: Market Regime Engine."""
import numpy as np
import pandas as pd
import pytest

from app.models.market import MarketRegime, MarketRegimeAssessment
from app.services.market_regime_service import classify_regime, REGIME_WEIGHT_ADJUSTMENTS


def _make_df(n: int, start: float, slope: float) -> pd.DataFrame:
    """Create a simple trending OHLCV DataFrame."""
    closes = [start + i * slope for i in range(n)]
    return pd.DataFrame({
        "Open": closes,
        "High": [c * 1.005 for c in closes],
        "Low": [c * 0.995 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * n,
    })


def _spy_bull(n: int = 250) -> pd.DataFrame:
    """SPY in a steady uptrend — price well above both 50DMA and 200DMA."""
    return _make_df(n, start=300.0, slope=1.0)  # strongly rising


def _spy_bear(n: int = 250) -> pd.DataFrame:
    """SPY in a downtrend — price well below 200DMA."""
    return _make_df(n, start=500.0, slope=-1.0)  # starts high then falls


def _spy_sideways(n: int = 250) -> pd.DataFrame:
    """SPY oscillating near the 200DMA."""
    closes = [400.0 + 5 * np.sin(i * 0.1) for i in range(n)]
    return pd.DataFrame({
        "Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [1e6] * n
    })


def _qqq_bull(n: int = 250) -> pd.DataFrame:
    return _make_df(n, start=350.0, slope=1.2)


class TestBullRegime:
    def test_spy_above_both_mas_low_vix(self):
        spy = _spy_bull()
        qqq = _qqq_bull()
        result = classify_regime(spy, qqq, vix_level=15.0)
        assert result.regime == MarketRegime.BULL_RISK_ON
        assert result.confidence >= 80

    def test_spy_above_both_mas_no_vix(self):
        spy = _spy_bull()
        qqq = _qqq_bull()
        result = classify_regime(spy, qqq, vix_level=None)
        assert result.regime in (MarketRegime.BULL_RISK_ON, MarketRegime.BULL_NARROW_LEADERSHIP)

    def test_spy_above_200dma_but_below_50dma_sideways(self):
        """Start high, then correct — above 200DMA but below 50DMA."""
        n = 250
        # Build: first 200 bars rising (sets high 200DMA), then 50 bars declining
        closes = [300.0 + i * 0.8 for i in range(200)] + [460.0 - i * 2 for i in range(50)]
        spy = pd.DataFrame({"Close": closes, "Open": closes, "High": closes, "Low": closes, "Volume": [1e6] * n})
        result = classify_regime(spy, None, vix_level=22.0)
        assert result.regime == MarketRegime.SIDEWAYS_CHOPPY


class TestBearRegime:
    def test_spy_below_200dma_high_vix(self):
        spy = _spy_bear()
        result = classify_regime(spy, None, vix_level=30.0)
        assert result.regime == MarketRegime.BEAR_RISK_OFF
        assert result.confidence >= 70

    def test_spy_below_200dma_qqq_also_below(self):
        spy = _spy_bear()
        qqq = _make_df(250, start=400.0, slope=-1.0)
        result = classify_regime(spy, qqq, vix_level=28.0)
        assert result.regime == MarketRegime.BEAR_RISK_OFF

    def test_spy_below_200dma_moderate_vix(self):
        spy = _spy_bear()
        result = classify_regime(spy, None, vix_level=22.0)
        # SPY below 200DMA + VIX > 20 → still BEAR or SIDEWAYS
        assert result.regime in (MarketRegime.BEAR_RISK_OFF, MarketRegime.SIDEWAYS_CHOPPY)


class TestSidewaysRegime:
    def test_oscillating_spy(self):
        spy = _spy_sideways()
        result = classify_regime(spy, None, vix_level=18.0)
        # Oscillating around a level → SIDEWAYS or BULL depending on exact close
        assert result.regime in (MarketRegime.SIDEWAYS_CHOPPY, MarketRegime.BULL_RISK_ON,
                                  MarketRegime.BULL_NARROW_LEADERSHIP)

    def test_missing_vix_defaults_sideways_with_low_confidence(self):
        spy = _spy_sideways()
        result = classify_regime(spy, None, vix_level=None)
        # Without VIX we have less info → confidence should be moderate
        assert result.confidence < 90


class TestMissingData:
    def test_no_spy_data_defaults_sideways_low_confidence(self):
        result = classify_regime(None, None, vix_level=None)
        assert result.regime == MarketRegime.SIDEWAYS_CHOPPY
        assert result.confidence <= 30

    def test_empty_spy_defaults_sideways(self):
        result = classify_regime(pd.DataFrame(), None, vix_level=25.0)
        assert result.regime == MarketRegime.SIDEWAYS_CHOPPY

    def test_too_short_spy_defaults_sideways(self):
        spy = _make_df(30, 400.0, 0.5)  # only 30 bars, need 50
        result = classify_regime(spy, None, vix_level=15.0)
        assert result.regime == MarketRegime.SIDEWAYS_CHOPPY


class TestResultFields:
    def test_result_has_all_fields(self):
        spy = _spy_bull()
        result = classify_regime(spy, _qqq_bull(), vix_level=14.0)
        assert isinstance(result, MarketRegimeAssessment)
        assert result.regime in MarketRegime.ALL
        assert 0 <= result.confidence <= 100
        assert len(result.implication) > 0

    def test_spy_above_200dma_flag_set(self):
        spy = _spy_bull()
        result = classify_regime(spy, None, vix_level=15.0)
        assert result.spy_above_200dma is True
        assert result.spy_above_50dma is True

    def test_bear_flags_set(self):
        spy = _spy_bear()
        result = classify_regime(spy, None, vix_level=30.0)
        assert result.spy_above_200dma is False

    def test_vix_stored_in_result(self):
        spy = _spy_bull()
        result = classify_regime(spy, None, vix_level=16.5)
        assert result.vix_level == 16.5


class TestRegimeWeightAdjustments:
    def test_bull_regime_has_adjustments(self):
        adj = REGIME_WEIGHT_ADJUSTMENTS[MarketRegime.BULL_RISK_ON]
        assert adj["technical_momentum"] > 1.0
        assert adj["valuation_relative_growth"] < 1.0

    def test_bear_regime_has_adjustments(self):
        adj = REGIME_WEIGHT_ADJUSTMENTS[MarketRegime.BEAR_RISK_OFF]
        assert adj["valuation_relative_growth"] > 1.0
        assert adj["balance_sheet_strength"] > 1.0
        assert adj["technical_momentum"] < 1.0

    def test_all_regimes_have_adjustment_maps(self):
        for regime in MarketRegime.ALL:
            assert regime in REGIME_WEIGHT_ADJUSTMENTS
