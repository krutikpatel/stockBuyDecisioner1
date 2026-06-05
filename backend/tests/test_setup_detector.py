"""Tests for SetupDetector — verifies correct setup selection from named signals."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from app.engine.setup_detector import SetupDetector, SetupDetectionResult


_CONFIG_PATH = Path(__file__).parent.parent / "config" / "technical_setup_config.json"


@pytest.fixture(scope="module")
def setup_defs():
    return json.loads(_CONFIG_PATH.read_text())["technical_setups"]


@pytest.fixture(scope="module")
def detector(setup_defs):
    return SetupDetector(setup_defs)


# ---------------------------------------------------------------------------
# GROWTH_LEADER_PULLBACK
# ---------------------------------------------------------------------------

def test_growth_leader_pullback_with_all_required(detector):
    signals = {"STRONG_UPTREND", "SMA50_PULLBACK", "RSI_PULLBACK_ZONE"}
    result = detector.detect(signals)
    assert result.selected_setup == "GROWTH_LEADER_PULLBACK"


def test_growth_leader_pullback_with_optional_signals(detector):
    signals = {"STRONG_UPTREND", "SMA50_PULLBACK", "RSI_PULLBACK_ZONE", "VOLUME_DRY_UP", "RS_LEADER_VS_SECTOR"}
    result = detector.detect(signals)
    assert result.selected_setup == "GROWTH_LEADER_PULLBACK"
    assert result.confidence > 60.0


def test_growth_leader_pullback_blocked_by_broken_chart(detector):
    signals = {"STRONG_UPTREND", "SMA50_PULLBACK", "RSI_PULLBACK_ZONE", "TRUE_BROKEN_CHART"}
    result = detector.detect(signals)
    assert result.selected_setup != "GROWTH_LEADER_PULLBACK"
    assert "GROWTH_LEADER_PULLBACK" in result.blocked_by


def test_growth_leader_pullback_missing_required(detector):
    signals = {"SMA50_PULLBACK", "RSI_PULLBACK_ZONE"}  # missing STRONG_UPTREND
    result = detector.detect(signals)
    assert result.selected_setup != "GROWTH_LEADER_PULLBACK"


# ---------------------------------------------------------------------------
# TRUE_BROKEN_CHART_AVOID (priority 1 — always takes precedence)
# ---------------------------------------------------------------------------

def test_broken_chart_takes_priority(detector):
    signals = {"TRUE_BROKEN_CHART", "STRONG_UPTREND", "SMA50_PULLBACK", "RSI_PULLBACK_ZONE"}
    result = detector.detect(signals)
    assert result.selected_setup == "TRUE_BROKEN_CHART_AVOID"


def test_broken_chart_alone(detector):
    signals = {"TRUE_BROKEN_CHART"}
    result = detector.detect(signals)
    assert result.selected_setup == "TRUE_BROKEN_CHART_AVOID"


# ---------------------------------------------------------------------------
# DOWNTREND_REBOUND_CANDIDATE
# ---------------------------------------------------------------------------

def test_rebound_fires_on_oversold_reversal(detector):
    signals = {"OVERSOLD_REVERSAL"}
    result = detector.detect(signals)
    assert result.selected_setup == "DOWNTREND_REBOUND_CANDIDATE"


def test_rebound_with_broken_chart_routes_to_quality_recovery(detector):
    signals = {"OVERSOLD_REVERSAL", "TRUE_BROKEN_CHART"}
    result = detector.detect(signals)
    # BROKEN_CHART_QUALITY_RECOVERY (priority=0) requires both TRUE_BROKEN_CHART + OVERSOLD_REVERSAL
    # and should take precedence over TRUE_BROKEN_CHART_AVOID (priority=1)
    assert result.selected_setup == "BROKEN_CHART_QUALITY_RECOVERY"


# ---------------------------------------------------------------------------
# BREAKOUT_MOMENTUM
# ---------------------------------------------------------------------------

def test_breakout_fires_with_required_and_optional(detector):
    signals = {"BREAKOUT_CONFIRMED", "STRONG_UPTREND"}  # 1 optional met
    result = detector.detect(signals)
    assert result.selected_setup == "BREAKOUT_MOMENTUM"


def test_breakout_no_fire_without_optional(detector):
    # BREAKOUT_MOMENTUM requires min_required_optional_signals=1
    signals = {"BREAKOUT_CONFIRMED"}  # no optional signals
    result = detector.detect(signals)
    assert result.selected_setup != "BREAKOUT_MOMENTUM"


# ---------------------------------------------------------------------------
# No match
# ---------------------------------------------------------------------------

def test_no_match_returns_none(detector):
    result = detector.detect(set())
    assert result.selected_setup is None
    assert result.confidence == 0.0


def test_no_match_empty_matching_list(detector):
    result = detector.detect(set())
    assert result.all_matching_setups == []


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

def test_broken_chart_beats_growth_leader(detector):
    # Both setups could fire if not for priority
    signals = {"TRUE_BROKEN_CHART", "STRONG_UPTREND", "SMA50_PULLBACK", "RSI_PULLBACK_ZONE"}
    result = detector.detect(signals)
    assert result.selected_setup == "TRUE_BROKEN_CHART_AVOID"


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

def test_result_type(detector):
    result = detector.detect({"STRONG_UPTREND", "SMA50_PULLBACK", "RSI_PULLBACK_ZONE"})
    assert isinstance(result, SetupDetectionResult)
    assert isinstance(result.active_signals if hasattr(result, 'active_signals') else result.all_matching_setups, list)
    assert isinstance(result.blocked_by, dict)
    assert isinstance(result.debug_info, dict)


def test_debug_info_contains_active_signals(detector):
    signals = {"STRONG_UPTREND", "SMA50_PULLBACK"}
    result = detector.detect(signals)
    assert "active_signals" in result.debug_info
    assert "STRONG_UPTREND" in result.debug_info["active_signals"]
