"""Tests for TechnicalSignalDetector — verifies correct signals fire from FeatureSnapshot."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from app.engine.rule_engine import RuleEngine
from app.engine.technical_signal_detector import TechnicalSignalDetector, SignalDetectionResult
from app.features.feature_snapshot import FeatureSnapshot


_CONFIG_PATH = Path(__file__).parent.parent / "config" / "technical_setup_config.json"


@pytest.fixture(scope="module")
def signal_defs():
    return json.loads(_CONFIG_PATH.read_text())["signal_definitions"]


@pytest.fixture(scope="module")
def detector(signal_defs):
    return TechnicalSignalDetector(signal_defs, RuleEngine())


def _snap(**kwargs) -> FeatureSnapshot:
    defaults = dict(
        ticker="TEST",
        trend_label="sideways",
        is_extended=False,
    )
    defaults.update(kwargs)
    return FeatureSnapshot(**defaults)


# ---------------------------------------------------------------------------
# STRONG_UPTREND
# ---------------------------------------------------------------------------

def test_strong_uptrend_fires(detector):
    snap = _snap(sma50_relative=3.0, sma200_relative=8.0, trend_label="strong_uptrend")
    result = detector.detect(snap)
    assert "STRONG_UPTREND" in result.active_signals


def test_strong_uptrend_no_fire_below_sma50(detector):
    snap = _snap(sma50_relative=-2.0, sma200_relative=8.0, trend_label="strong_uptrend")
    result = detector.detect(snap)
    assert "STRONG_UPTREND" not in result.active_signals


def test_strong_uptrend_no_fire_downtrend_label(detector):
    snap = _snap(sma50_relative=3.0, sma200_relative=8.0, trend_label="downtrend")
    result = detector.detect(snap)
    assert "STRONG_UPTREND" not in result.active_signals


# ---------------------------------------------------------------------------
# SMA50_PULLBACK
# ---------------------------------------------------------------------------

def test_sma50_pullback_fires(detector):
    snap = _snap(sma50_relative=1.5, sma50_slope=0.2)
    result = detector.detect(snap)
    assert "SMA50_PULLBACK" in result.active_signals


def test_sma50_pullback_no_fire_below_zone(detector):
    snap = _snap(sma50_relative=-7.0, sma50_slope=0.2)
    result = detector.detect(snap)
    assert "SMA50_PULLBACK" not in result.active_signals


def test_sma50_pullback_no_fire_falling_slope(detector):
    snap = _snap(sma50_relative=2.0, sma50_slope=-0.5)
    result = detector.detect(snap)
    assert "SMA50_PULLBACK" not in result.active_signals


# ---------------------------------------------------------------------------
# RSI_PULLBACK_ZONE
# ---------------------------------------------------------------------------

def test_rsi_pullback_fires(detector):
    snap = _snap(rsi14=48.0)
    result = detector.detect(snap)
    assert "RSI_PULLBACK_ZONE" in result.active_signals


def test_rsi_pullback_no_fire_overbought(detector):
    snap = _snap(rsi14=72.0)
    result = detector.detect(snap)
    assert "RSI_PULLBACK_ZONE" not in result.active_signals


def test_rsi_pullback_no_fire_oversold(detector):
    snap = _snap(rsi14=30.0)
    result = detector.detect(snap)
    assert "RSI_PULLBACK_ZONE" not in result.active_signals


# ---------------------------------------------------------------------------
# VOLUME_DRY_UP
# ---------------------------------------------------------------------------

def test_volume_dryup_fires(detector):
    snap = _snap(volume_dryup_ratio=0.6)
    result = detector.detect(snap)
    assert "VOLUME_DRY_UP" in result.active_signals


def test_volume_dryup_no_fire_high_volume(detector):
    snap = _snap(volume_dryup_ratio=1.2)
    result = detector.detect(snap)
    assert "VOLUME_DRY_UP" not in result.active_signals


# ---------------------------------------------------------------------------
# TRUE_BROKEN_CHART
# ---------------------------------------------------------------------------

def test_true_broken_chart_fires(detector):
    snap = _snap(trend_label="downtrend", sma50_relative=-8.0, sma200_relative=-5.0)
    result = detector.detect(snap)
    assert "TRUE_BROKEN_CHART" in result.active_signals


def test_true_broken_chart_no_fire_uptrend(detector):
    snap = _snap(trend_label="strong_uptrend", sma50_relative=3.0, sma200_relative=10.0)
    result = detector.detect(snap)
    assert "TRUE_BROKEN_CHART" not in result.active_signals


def test_true_broken_chart_no_fire_mild_downtrend(detector):
    snap = _snap(trend_label="downtrend", sma50_relative=-3.0, sma200_relative=-1.0)
    result = detector.detect(snap)
    # sma50_relative must be < -5
    assert "TRUE_BROKEN_CHART" not in result.active_signals


# ---------------------------------------------------------------------------
# OVERSOLD_REVERSAL
# ---------------------------------------------------------------------------

def test_oversold_reversal_fires(detector):
    snap = _snap(rsi14=35.0, rsi_slope=1.5)
    result = detector.detect(snap)
    assert "OVERSOLD_REVERSAL" in result.active_signals


def test_oversold_reversal_no_fire_rsi_falling(detector):
    snap = _snap(rsi14=35.0, rsi_slope=-1.0)
    result = detector.detect(snap)
    assert "OVERSOLD_REVERSAL" not in result.active_signals


def test_oversold_reversal_no_fire_rsi_too_high(detector):
    snap = _snap(rsi14=50.0, rsi_slope=2.0)
    result = detector.detect(snap)
    assert "OVERSOLD_REVERSAL" not in result.active_signals


# ---------------------------------------------------------------------------
# EXTENDED_ABOVE_SMA20
# ---------------------------------------------------------------------------

def test_extended_fires(detector):
    snap = _snap(sma20_relative=12.0)
    result = detector.detect(snap)
    assert "EXTENDED_ABOVE_SMA20" in result.active_signals


def test_extended_no_fire_normal(detector):
    snap = _snap(sma20_relative=3.0)
    result = detector.detect(snap)
    assert "EXTENDED_ABOVE_SMA20" not in result.active_signals


# ---------------------------------------------------------------------------
# Missing field handling
# ---------------------------------------------------------------------------

def test_missing_field_does_not_crash(detector):
    snap = _snap()  # all indicator fields None
    result = detector.detect(snap)
    assert isinstance(result, SignalDetectionResult)
    assert len(result.missing_fields) > 0


def test_missing_field_adds_confidence_penalty(detector):
    snap = _snap()  # all indicator fields None
    result = detector.detect(snap)
    assert result.confidence_penalty > 0


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

def test_result_has_all_expected_fields(detector):
    snap = _snap(rsi14=48.0, sma50_relative=2.0, sma50_slope=0.3)
    result = detector.detect(snap)
    assert isinstance(result.active_signals, set)
    assert isinstance(result.signal_reasons, dict)
    assert isinstance(result.missing_fields, list)
    assert isinstance(result.confidence_penalty, float)


def test_all_signal_names_in_reasons(detector, signal_defs):
    snap = _snap()
    result = detector.detect(snap)
    for name in signal_defs:
        assert name in result.signal_reasons
