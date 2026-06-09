"""Stage 5: AvoidSideScorer — verify deterioration decisions."""
from __future__ import annotations

import pytest

from app.features.feature_snapshot import FeatureSnapshot
from two_path_engine.avoid_side import AvoidSideScorer, AvoidSideResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scorer() -> AvoidSideScorer:
    return AvoidSideScorer()


def _multi_deterioration_snap(**overrides) -> FeatureSnapshot:
    """Snapshot with multiple confirmed deterioration signals → AVOID."""
    defaults = dict(
        ticker="AVOID_ME",
        price=30.0,
        sales_growth_yoy=-0.10,    # <= 0 → +20
        sales_growth_qoq=-0.05,    # < 0 → +10
        operating_margin=-0.08,    # < -0.05 → +20
        beat_rate=0.25,            # < 0.40 → +15
        # Total: 65 → AVOID
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


def _early_warning_snap(**overrides) -> FeatureSnapshot:
    """Snapshot with one early-warning signal only → WATCHLIST."""
    defaults = dict(
        ticker="WATCHLIST",
        price=50.0,
        eps_growth_yoy=-0.05,      # < 0 → +10
        # All other fields None or healthy
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


# ---------------------------------------------------------------------------
# Tests: AVOID decision
# ---------------------------------------------------------------------------

def test_multi_deterioration_scores_avoid():
    result = _scorer().score(_multi_deterioration_snap())
    assert result.decision == "AVOID"


def test_avoid_score_above_threshold():
    result = _scorer().score(_multi_deterioration_snap())
    assert result.score >= 60


def test_avoid_score_range():
    result = _scorer().score(_multi_deterioration_snap())
    assert 0 <= result.score <= 100


def test_avoid_reasons_populated():
    result = _scorer().score(_multi_deterioration_snap())
    assert len(result.reasons) >= 3


# ---------------------------------------------------------------------------
# Tests: WATCHLIST decision
# ---------------------------------------------------------------------------

def test_early_warning_scores_watchlist():
    result = _scorer().score(_early_warning_snap())
    assert result.decision == "WATCHLIST"


def test_watchlist_score_below_threshold():
    result = _scorer().score(_early_warning_snap())
    assert result.score < 60


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

def test_clean_snap_scores_zero():
    """A snapshot with no deterioration signals scores 0."""
    snap = FeatureSnapshot(
        ticker="CLEAN",
        price=100.0,
        sales_growth_yoy=0.20,     # not declining
        operating_margin=0.15,     # not negative
        beat_rate=0.80,            # high
        debt_to_equity=0.5,        # low
        free_cash_flow=1e9,        # positive
        sma200_relative=5.0,       # above SMA200
    )
    result = _scorer().score(snap)
    assert result.score == 0.0
    assert result.decision == "WATCHLIST"


def test_score_clamped_to_100():
    """Score cannot exceed 100."""
    snap = _multi_deterioration_snap(
        debt_to_equity=160,        # > 150 → +15
        free_cash_flow=-5e8,       # < 0 → +10
        sma200_relative=-20.0,     # < -15 → +8
        eps_growth_yoy=-0.15,      # < 0 → +10
        gross_margin=0.10,         # < 0.20 → +12
        current_ratio=0.7,         # < 0.8 → +8
        roe=-10.0,                 # < 0 → +7
    )
    result = _scorer().score(snap)
    assert result.score <= 100


def test_empty_snap_scores_zero():
    snap = FeatureSnapshot(ticker="EMPTY", price=50.0)
    result = _scorer().score(snap)
    assert result.score == 0.0
    assert result.decision == "WATCHLIST"


def test_result_type():
    result = _scorer().score(_multi_deterioration_snap())
    assert isinstance(result, AvoidSideResult)
    assert isinstance(result.decision, str)
    assert isinstance(result.score, float)
    assert isinstance(result.reasons, list)


def test_revenue_declining_yoy_fires():
    snap = FeatureSnapshot(ticker="REV", price=50.0, sales_growth_yoy=-0.01)
    result = _scorer().score(snap)
    assert any("Revenue" in r or "revenue" in r for r in result.reasons)


def test_op_margin_negative_fires():
    snap = FeatureSnapshot(ticker="OM", price=50.0, operating_margin=-0.10)
    result = _scorer().score(snap)
    assert any("margin" in r.lower() or "operating" in r.lower() for r in result.reasons)


def test_fcf_negative_fires():
    snap = FeatureSnapshot(ticker="FCF", price=50.0, free_cash_flow=-1e6)
    result = _scorer().score(snap)
    assert any("FCF" in r or "cash" in r.lower() for r in result.reasons)


def test_debt_equity_high_fires():
    snap = FeatureSnapshot(ticker="DEBT", price=50.0, debt_to_equity=160)  # > 150% threshold
    result = _scorer().score(snap)
    assert any("Debt" in r or "debt" in r for r in result.reasons)
