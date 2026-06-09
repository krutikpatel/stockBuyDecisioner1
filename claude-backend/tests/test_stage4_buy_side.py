"""Stage 4: BuySideScorer — verify dislocation-timing decisions for quality stocks."""
from __future__ import annotations

import pytest

from app.features.feature_snapshot import FeatureSnapshot
from two_path_engine.buy_side import BuySideScorer, BuySideResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scorer() -> BuySideScorer:
    return BuySideScorer()


def _oversold_recovering_snap(**overrides) -> FeatureSnapshot:
    """Snapshot representing a quality stock in deep dislocation → should BUY."""
    defaults = dict(
        ticker="OVERSOLD",
        price=100.0,
        rsi14=32.0,               # between 20-40 → +25
        rsi_slope=1.5,            # > 0 → +10
        dist_from_52w_high=-0.25, # <= -0.20 → +15
        breakout_volume_multiple=1.5,  # >= 1.3 → +10
        atr_percent=2.5,          # >= 2.0 → +8
        obv_trend=1,              # > 0 → +7
        vwap_deviation=0.01,      # > 0 → +5
        # Total positive: 80 → BUY
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


def _extended_overbought_snap(**overrides) -> FeatureSnapshot:
    """Snapshot representing an extended/overbought stock → should WAIT."""
    defaults = dict(
        ticker="EXTENDED",
        price=100.0,
        rsi14=75.0,               # > 70 → -20
        sma20_relative=12.0,      # > 8.0 → -15
        dist_from_52w_high=-0.02, # not oversold
        obv_trend=1,              # +7
        # Total: -20 + -15 + 7 = -28 → clamped to 0 → WAIT
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


# ---------------------------------------------------------------------------
# Tests: BUY decision
# ---------------------------------------------------------------------------

def test_oversold_recovering_scores_buy():
    result = _scorer().score(_oversold_recovering_snap())
    assert result.decision == "BUY"


def test_buy_score_range():
    result = _scorer().score(_oversold_recovering_snap())
    assert 0 <= result.score <= 100


def test_buy_score_above_threshold():
    result = _scorer().score(_oversold_recovering_snap())
    assert result.score >= 60


def test_buy_reasons_populated():
    result = _scorer().score(_oversold_recovering_snap())
    assert len(result.reasons) > 0


def test_buy_reasons_include_rsi():
    result = _scorer().score(_oversold_recovering_snap())
    assert any("RSI" in r or "rsi" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Tests: WAIT decision
# ---------------------------------------------------------------------------

def test_extended_snap_scores_wait():
    result = _scorer().score(_extended_overbought_snap())
    assert result.decision == "WAIT"


def test_wait_score_below_threshold():
    result = _scorer().score(_extended_overbought_snap())
    assert result.score < 60


def test_penalty_reasons_appear():
    result = _scorer().score(_extended_overbought_snap())
    penalty_reasons = [r for r in result.reasons if "PENALTY" in r]
    assert len(penalty_reasons) >= 1


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

def test_empty_snap_scores_zero():
    snap = FeatureSnapshot(ticker="EMPTY", price=50.0)
    result = _scorer().score(snap)
    assert result.score == 0.0
    assert result.decision == "WAIT"


def test_score_is_clamped():
    """Score cannot exceed 100 even with all rules firing."""
    snap = _oversold_recovering_snap(
        stochastic_rsi=15.0,       # +8
        chaikin_money_flow=0.05,   # +5
        max_drawdown_3m=-0.20,     # +7
    )
    result = _scorer().score(snap)
    assert result.score <= 100


def test_missing_fields_recorded():
    """Missing fields should be tracked."""
    snap = FeatureSnapshot(ticker="MISS", price=50.0, rsi14=30.0, rsi_slope=1.0)
    result = _scorer().score(snap)
    # dist_from_52w_high is None → missing field
    assert "dist_from_52w_high" in result.missing_fields


def test_result_type():
    result = _scorer().score(_oversold_recovering_snap())
    assert isinstance(result, BuySideResult)
    assert isinstance(result.decision, str)
    assert isinstance(result.score, float)
    assert isinstance(result.reasons, list)


def test_borderline_score_59_is_wait():
    """Score just below threshold → WAIT."""
    snap = FeatureSnapshot(
        ticker="BORDER",
        price=100.0,
        rsi14=32.0,       # +25
        rsi_slope=1.0,    # +10
        # dist_from_52w_high missing → no +15
        # Total: 35 < 60 → WAIT
    )
    result = _scorer().score(snap)
    assert result.decision == "WAIT"
    assert result.score < 60


def test_exact_threshold_is_buy():
    """Score exactly at threshold → BUY."""
    snap = FeatureSnapshot(
        ticker="EXACT",
        price=100.0,
        rsi14=30.0,               # +25
        rsi_slope=2.0,            # +10
        dist_from_52w_high=-0.25, # +15
        breakout_volume_multiple=1.4,  # +10
        # Total = 60 → BUY
    )
    result = _scorer().score(snap)
    assert result.score == pytest.approx(60.0)
    assert result.decision == "BUY"
