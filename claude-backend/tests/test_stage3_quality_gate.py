"""Stage 3: QualityGate — verify AND-logic splits quality vs deteriorating stocks."""
from __future__ import annotations

import pytest

from app.algo_config import AlgoConfig
from app.features.feature_snapshot import FeatureSnapshot
from two_path_engine.quality_gate import QualityGate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _quality_snap(**overrides) -> FeatureSnapshot:
    """Build a snapshot that passes all quality gate checks by default."""
    defaults = dict(
        ticker="QUALITY",
        price=100.0,
        gross_margin=0.55,        # > 0.30 ✓
        operating_margin=0.20,    # > -0.05 ✓
        roe=20.0,                 # > 5.0 ✓
        free_cash_flow=1e9,       # > 0 ✓
        debt_to_equity=0.5,       # < 2.0 ✓
        current_ratio=2.0,        # > 1.0 ✓
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


def _bad_snap(**overrides) -> FeatureSnapshot:
    """Build a snapshot that fails multiple quality gate checks."""
    defaults = dict(
        ticker="DETERIORATING",
        price=50.0,
        gross_margin=0.15,        # < 0.30 ✗
        operating_margin=-0.10,   # < -0.05 ✗
        roe=-5.0,                 # < 5.0 ✗
        free_cash_flow=-1e8,      # < 0 ✗
        debt_to_equity=3.0,       # > 2.0 ✗
        current_ratio=0.6,        # < 1.0 ✗
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


def _gate() -> QualityGate:
    return QualityGate()


# ---------------------------------------------------------------------------
# Tests: quality stocks pass
# ---------------------------------------------------------------------------

def test_quality_snap_passes():
    result = _gate().evaluate(_quality_snap())
    assert result.passes is True


def test_quality_passes_reasons_populated():
    result = _gate().evaluate(_quality_snap())
    assert len(result.reasons) > 0


# ---------------------------------------------------------------------------
# Tests: deteriorating stocks fail
# ---------------------------------------------------------------------------

def test_bad_snap_fails():
    result = _gate().evaluate(_bad_snap())
    assert result.passes is False


def test_bad_snap_reasons_populated():
    result = _gate().evaluate(_bad_snap())
    assert len(result.reasons) >= 3  # multiple failures expected


# ---------------------------------------------------------------------------
# Tests: individual failure conditions
# ---------------------------------------------------------------------------

def test_fails_gross_margin_below_min():
    snap = _quality_snap(gross_margin=0.25)  # below 0.30
    result = _gate().evaluate(snap)
    assert result.passes is False
    assert any("gross_margin" in r for r in result.reasons)


def test_passes_gross_margin_at_threshold():
    snap = _quality_snap(gross_margin=0.30)  # exactly at min
    result = _gate().evaluate(snap)
    assert result.passes is True


def test_fails_op_margin_below_min():
    snap = _quality_snap(operating_margin=-0.06)  # below -0.05
    result = _gate().evaluate(snap)
    assert result.passes is False
    assert any("operating_margin" in r for r in result.reasons)


def test_passes_op_margin_at_threshold():
    snap = _quality_snap(operating_margin=-0.05)  # exactly at min
    result = _gate().evaluate(snap)
    assert result.passes is True


def test_fails_roe_and_fcf_both_bad():
    snap = _quality_snap(roe=0.02, free_cash_flow=-1e6)  # roe < 0.05 (2%), fcf < 0
    result = _gate().evaluate(snap)
    assert result.passes is False


def test_passes_roe_fails_fcf():
    """ROE alone satisfies the condition (fcf_substitutes_roe)."""
    snap = _quality_snap(roe=10.0, free_cash_flow=-1e6)
    result = _gate().evaluate(snap)
    assert result.passes is True


def test_passes_fcf_fails_roe():
    """Positive FCF substitutes for low ROE."""
    snap = _quality_snap(roe=2.0, free_cash_flow=5e8)
    result = _gate().evaluate(snap)
    assert result.passes is True


def test_fails_debt_equity_too_high():
    snap = _quality_snap(debt_to_equity=210)  # > 200 (210% leverage)
    result = _gate().evaluate(snap)
    assert result.passes is False
    assert any("debt_to_equity" in r for r in result.reasons)


def test_passes_debt_equity_at_threshold():
    snap = _quality_snap(debt_to_equity=200)  # exactly 200% = 2× leverage
    result = _gate().evaluate(snap)
    assert result.passes is True


def test_fails_current_ratio_low():
    snap = _quality_snap(current_ratio=0.8)
    result = _gate().evaluate(snap)
    assert result.passes is False
    assert any("current_ratio" in r for r in result.reasons)


def test_passes_current_ratio_at_threshold():
    snap = _quality_snap(current_ratio=1.0)
    result = _gate().evaluate(snap)
    assert result.passes is True


# ---------------------------------------------------------------------------
# Tests: missing data handling
# ---------------------------------------------------------------------------

def test_missing_gross_margin_fails():
    snap = _quality_snap(gross_margin=None)
    result = _gate().evaluate(snap)
    assert result.passes is False
    assert any("gross_margin" in r for r in result.reasons)


def test_missing_op_margin_fails():
    snap = _quality_snap(operating_margin=None)
    result = _gate().evaluate(snap)
    assert result.passes is False


def test_missing_debt_equity_does_not_fail():
    """Missing debt/equity — we can't confirm violation, so gate doesn't fail it."""
    snap = _quality_snap(debt_to_equity=None)
    result = _gate().evaluate(snap)
    # No explicit debt_to_equity failure when data is missing
    assert result.passes is True


def test_missing_current_ratio_does_not_fail():
    snap = _quality_snap(current_ratio=None)
    result = _gate().evaluate(snap)
    assert result.passes is True


# ---------------------------------------------------------------------------
# Tests: custom config
# ---------------------------------------------------------------------------

def test_custom_config_stricter_gross_margin():
    custom_cfg = AlgoConfig.from_dict({
        "quality_gate": {
            "gross_margin_min": 0.50,
            "op_margin_min": -0.05,
            "roe_min": 0.05,
            "fcf_substitutes_roe": True,
            "debt_equity_max": 200,
            "current_ratio_min": 1.0,
        }
    })
    gate = QualityGate(algo_config=custom_cfg)
    snap = _quality_snap(gross_margin=0.45)  # passes default (0.30) but fails stricter (0.50)
    result = gate.evaluate(snap)
    assert result.passes is False
