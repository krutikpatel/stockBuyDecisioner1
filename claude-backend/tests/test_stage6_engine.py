"""Stage 6: TwoPathEngine orchestrator — verify correct routing and output structure."""
from __future__ import annotations

import pytest

from app.features.feature_snapshot import FeatureSnapshot
from two_path_engine.engine import TwoPathDecision, TwoPathEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> TwoPathEngine:
    return TwoPathEngine()


def _quality_intact_snap(**overrides) -> FeatureSnapshot:
    """Passes quality gate AND has strong buy-side signals."""
    defaults = dict(
        ticker="NVDA_SYN",
        price=500.0,
        # Quality gate pass
        gross_margin=0.60,
        operating_margin=0.25,
        roe=30.0,
        free_cash_flow=5e9,
        debt_to_equity=0.3,
        current_ratio=3.0,
        # Buy-side timing signals → BUY
        rsi14=30.0,               # +25
        rsi_slope=2.0,            # +10
        dist_from_52w_high=-0.25, # +15
        breakout_volume_multiple=1.5,  # +10
        atr_percent=3.0,          # +8
        obv_trend=1,              # +7
        vwap_deviation=0.02,      # +5
        # Score: 80 → BUY
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


def _quality_intact_wait_snap(**overrides) -> FeatureSnapshot:
    """Passes quality gate but has poor buy-side timing → WAIT."""
    defaults = dict(
        ticker="AAPL_SYN",
        price=200.0,
        # Quality gate pass
        gross_margin=0.45,
        operating_margin=0.30,
        roe=140.0,
        free_cash_flow=100e9,
        debt_to_equity=1.5,
        current_ratio=1.5,
        # Overbought signals → WAIT
        rsi14=78.0,               # -20
        sma20_relative=10.0,      # -15
        # Score: -35 → clamped to 0 → WAIT
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


def _deteriorating_snap(**overrides) -> FeatureSnapshot:
    """Fails quality gate AND has strong deterioration signals → AVOID."""
    defaults = dict(
        ticker="INTC_SYN",
        price=25.0,
        # Quality gate fail
        gross_margin=0.40,
        operating_margin=-0.10,   # fails op margin check
        roe=2.0,
        free_cash_flow=-1e9,      # fails ROE+FCF check
        debt_to_equity=1.5,
        current_ratio=1.2,
        # Avoid-side deterioration
        sales_growth_yoy=-0.08,   # +20
        sales_growth_qoq=-0.03,   # +10
        beat_rate=0.30,           # +15
        debt_to_equity_avoid=None,
        eps_growth_yoy=-0.20,     # +10
    )
    # Remove non-standard key
    defaults.pop("debt_to_equity_avoid", None)
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


def _watchlist_snap(**overrides) -> FeatureSnapshot:
    """Fails quality gate but only minor deterioration → WATCHLIST."""
    defaults = dict(
        ticker="WARN_SYN",
        price=40.0,
        gross_margin=0.20,        # fails quality gate
        operating_margin=-0.10,
        roe=1.0,
        free_cash_flow=-1e6,
        # Only single deterioration signal
        eps_growth_yoy=-0.03,     # +10
    )
    defaults.update(overrides)
    return FeatureSnapshot(**defaults)


# ---------------------------------------------------------------------------
# Tests: quality_intact → BUY
# ---------------------------------------------------------------------------

def test_quality_snap_routes_to_quality_intact():
    engine = _engine()
    decision = engine.analyze_snapshot(_quality_intact_snap())
    assert decision.path_taken == "quality_intact"


def test_quality_snap_buy_decision():
    engine = _engine()
    decision = engine.analyze_snapshot(_quality_intact_snap())
    assert decision.decision == "BUY"


def test_quality_snap_score_above_60():
    engine = _engine()
    decision = engine.analyze_snapshot(_quality_intact_snap())
    assert decision.score >= 60


# ---------------------------------------------------------------------------
# Tests: quality_intact → WAIT
# ---------------------------------------------------------------------------

def test_quality_overbought_routes_to_quality_intact():
    engine = _engine()
    decision = engine.analyze_snapshot(_quality_intact_wait_snap())
    assert decision.path_taken == "quality_intact"


def test_quality_overbought_wait_decision():
    engine = _engine()
    decision = engine.analyze_snapshot(_quality_intact_wait_snap())
    assert decision.decision == "WAIT"


# ---------------------------------------------------------------------------
# Tests: deteriorating_business → AVOID
# ---------------------------------------------------------------------------

def test_deteriorating_snap_routes_to_deteriorating_business():
    engine = _engine()
    decision = engine.analyze_snapshot(_deteriorating_snap())
    assert decision.path_taken == "deteriorating_business"


def test_deteriorating_snap_avoid_or_watchlist():
    engine = _engine()
    decision = engine.analyze_snapshot(_deteriorating_snap())
    assert decision.decision in ("AVOID", "WATCHLIST")


# ---------------------------------------------------------------------------
# Tests: deteriorating_business → WATCHLIST
# ---------------------------------------------------------------------------

def test_watchlist_snap_routes_to_deteriorating_business():
    engine = _engine()
    decision = engine.analyze_snapshot(_watchlist_snap())
    assert decision.path_taken == "deteriorating_business"


def test_watchlist_snap_watchlist_decision():
    engine = _engine()
    decision = engine.analyze_snapshot(_watchlist_snap())
    assert decision.decision == "WATCHLIST"


# ---------------------------------------------------------------------------
# Tests: TwoPathDecision structure
# ---------------------------------------------------------------------------

def test_decision_has_all_fields():
    engine = _engine()
    d = engine.analyze_snapshot(_quality_intact_snap())
    assert isinstance(d, TwoPathDecision)
    assert isinstance(d.ticker, str)
    assert isinstance(d.path_taken, str)
    assert isinstance(d.decision, str)
    assert isinstance(d.score, float)
    assert isinstance(d.reasons, list)
    assert isinstance(d.gate_reasons, list)
    assert isinstance(d.missing_fields, list)


def test_decision_ticker_matches_snapshot():
    engine = _engine()
    snap = _quality_intact_snap()
    d = engine.analyze_snapshot(snap)
    assert d.ticker == snap.ticker


def test_path_taken_valid_values():
    engine = _engine()
    for snap in [_quality_intact_snap(), _deteriorating_snap()]:
        d = engine.analyze_snapshot(snap)
        assert d.path_taken in ("quality_intact", "deteriorating_business")


def test_decision_valid_values():
    engine = _engine()
    for snap in [_quality_intact_snap(), _quality_intact_wait_snap(),
                 _deteriorating_snap(), _watchlist_snap()]:
        d = engine.analyze_snapshot(snap)
        assert d.decision in ("BUY", "WAIT", "AVOID", "WATCHLIST")


def test_score_in_range():
    engine = _engine()
    for snap in [_quality_intact_snap(), _quality_intact_wait_snap()]:
        d = engine.analyze_snapshot(snap)
        assert 0 <= d.score <= 100


def test_snapshot_attached():
    engine = _engine()
    snap = _quality_intact_snap()
    d = engine.analyze_snapshot(snap)
    assert d.snapshot is snap


# ---------------------------------------------------------------------------
# Tests: gate reasons present
# ---------------------------------------------------------------------------

def test_quality_path_gate_reasons():
    engine = _engine()
    d = engine.analyze_snapshot(_quality_intact_snap())
    assert len(d.gate_reasons) > 0


def test_deteriorating_path_gate_reasons_explain_failure():
    engine = _engine()
    d = engine.analyze_snapshot(_deteriorating_snap())
    assert len(d.gate_reasons) > 0
    # At least one reason should mention a specific field
    assert any(any(kw in r for kw in ("operating_margin", "gross_margin", "ROE", "FCF"))
               for r in d.gate_reasons)
