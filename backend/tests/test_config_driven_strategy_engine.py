"""Tests for ConfigDrivenStrategyEngine — verifies scoring and decision logic per engine."""
from __future__ import annotations
import pytest
from app.config.config_loader import MultiSourceConfig
from app.engine.config_driven_strategy_engine import ConfigDrivenStrategyEngine, StrategyEngineResult
from app.engine.rule_engine import RuleEngine
from app.features.feature_snapshot import FeatureSnapshot


@pytest.fixture(scope="module")
def engines() -> dict[str, ConfigDrivenStrategyEngine]:
    config = MultiSourceConfig()
    rule_engine = RuleEngine()
    return {
        name: ConfigDrivenStrategyEngine(name, cfg, rule_engine)
        for name, cfg in config.strategy_engines.items()
    }


def _snap(**kwargs) -> FeatureSnapshot:
    defaults = dict(ticker="TEST", trend_label="sideways", is_extended=False)
    defaults.update(kwargs)
    return FeatureSnapshot(**defaults)


# ---------------------------------------------------------------------------
# growth_leader_pullback — BUY_ON_PULLBACK case
# ---------------------------------------------------------------------------

def test_growth_leader_high_score_buy_on_pullback(engines):
    snap = _snap(
        sma50_relative=2.0,
        sma50_slope=0.3,
        rsi14=48.0,
        volume_dryup_ratio=0.65,
        rs_vs_sector_20d=2.5,
        rs_vs_spy_20d=1.0,
        sales_growth_yoy=0.25,
        operating_margin=0.20,
        market_regime="BULL_RISK_ON",
    )
    result = engines["growth_leader_pullback"].score(snap)
    assert result.recommendation == "BUY_ON_PULLBACK"
    assert result.strategy_score >= 65


def test_growth_leader_partial_score_wait(engines):
    # Only SMA50 pullback and RSI zone met — not enough for BUY_ON_PULLBACK
    snap = _snap(
        sma50_relative=2.0,
        sma50_slope=0.1,
        rsi14=48.0,
        market_regime="SIDEWAYS_CHOPPY",
    )
    result = engines["growth_leader_pullback"].score(snap)
    assert result.recommendation in ("WAIT_FOR_PULLBACK", "WATCHLIST")


def test_growth_leader_no_score_watchlist(engines):
    snap = _snap()  # all None
    result = engines["growth_leader_pullback"].score(snap)
    assert result.recommendation == "WATCHLIST"


def test_growth_leader_score_includes_regime_bonus(engines):
    snap_bull = _snap(
        sma50_relative=2.0, sma50_slope=0.1, rsi14=48.0, market_regime="BULL_RISK_ON"
    )
    snap_side = _snap(
        sma50_relative=2.0, sma50_slope=0.1, rsi14=48.0, market_regime="SIDEWAYS_CHOPPY"
    )
    r_bull = engines["growth_leader_pullback"].score(snap_bull)
    r_side = engines["growth_leader_pullback"].score(snap_side)
    # Bull regime gives +5 bonus
    assert r_bull.strategy_score > r_side.strategy_score


# ---------------------------------------------------------------------------
# downtrend_rebound — OVERSOLD_REBOUND_CANDIDATE case
# ---------------------------------------------------------------------------

def test_rebound_high_score_produces_candidate(engines):
    snap = _snap(
        rsi14=34.0,
        rsi_slope=1.5,
        updown_volume_ratio=1.2,
        perf_1w=1.0,
        sma200_slope=-0.1,
    )
    result = engines["downtrend_rebound"].score(snap)
    assert result.recommendation == "OVERSOLD_REBOUND_CANDIDATE"
    assert result.strategy_score >= 60


def test_rebound_falling_rsi_no_candidate(engines):
    snap = _snap(rsi14=34.0, rsi_slope=-1.0)
    result = engines["downtrend_rebound"].score(snap)
    # Missing rsi_slope_positive rule — score stays below 60
    assert result.recommendation != "OVERSOLD_REBOUND_CANDIDATE"


# ---------------------------------------------------------------------------
# true_broken_chart_avoid — always avoids
# ---------------------------------------------------------------------------

def test_broken_chart_returns_avoid_label(engines):
    snap = _snap(sma50_relative=-8.0, sma200_relative=-5.0)
    result = engines["true_broken_chart_avoid"].score(snap)
    assert result.recommendation in ("BROKEN_SUPPORT_AVOID", "TRUE_DOWNTREND_AVOID")


def test_broken_support_scoring(engines):
    snap = _snap(
        perf_1w=-4.0,
        breakout_volume_multiple=2.0,
    )
    result = engines["true_broken_chart_avoid"].score(snap)
    # Score >= 50 → BROKEN_SUPPORT_AVOID; else TRUE_DOWNTREND_AVOID fallback
    assert result.recommendation == "BROKEN_SUPPORT_AVOID"


# ---------------------------------------------------------------------------
# quality_growth_expensive_but_working
# ---------------------------------------------------------------------------

def test_expensive_but_working_high_score(engines):
    snap = _snap(
        rs_vs_spy_20d=4.0,
        rs_vs_sector_20d=3.0,
        sales_growth_yoy=0.20,
        eps_growth_yoy=0.18,
        roic=20.0,
        atr_percent=2.5,
    )
    result = engines["quality_growth_expensive_but_working"].score(snap)
    assert result.recommendation == "BUY_STARTER_STRONG_BUT_EXTENDED"


def test_expensive_valuation_penalty_applied(engines):
    snap_extreme = _snap(
        rs_vs_spy_20d=4.0, rs_vs_sector_20d=3.0,
        sales_growth_yoy=0.20, eps_growth_yoy=0.18,
        roic=20.0, atr_percent=2.5,
        forward_pe=90.0, price_to_sales=30.0,
    )
    snap_normal = _snap(
        rs_vs_spy_20d=4.0, rs_vs_sector_20d=3.0,
        sales_growth_yoy=0.20, eps_growth_yoy=0.18,
        roic=20.0, atr_percent=2.5,
    )
    r_extreme = engines["quality_growth_expensive_but_working"].score(snap_extreme)
    r_normal = engines["quality_growth_expensive_but_working"].score(snap_normal)
    assert r_normal.strategy_score > r_extreme.strategy_score


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

def test_result_type(engines):
    snap = _snap()
    result = engines["growth_leader_pullback"].score(snap)
    assert isinstance(result, StrategyEngineResult)
    assert isinstance(result.strategy_score, float)
    assert isinstance(result.recommendation, str)
    assert isinstance(result.reasons, list)
    assert isinstance(result.missing_data, list)
    assert isinstance(result.confidence, float)
    assert isinstance(result.risk_inputs, dict)


def test_score_bounded_0_to_max(engines):
    snap = _snap(
        sma50_relative=2.0, sma50_slope=0.3, rsi14=48.0,
        volume_dryup_ratio=0.5, rs_vs_sector_20d=3.0, rs_vs_spy_20d=2.0,
        sales_growth_yoy=0.30, operating_margin=0.25, market_regime="BULL_RISK_ON",
    )
    result = engines["growth_leader_pullback"].score(snap)
    assert 0.0 <= result.strategy_score <= 100.0


def test_missing_data_reduces_confidence(engines):
    full_snap = _snap(rsi14=48.0, sma50_relative=2.0, sma50_slope=0.2)
    empty_snap = _snap()
    r_full = engines["growth_leader_pullback"].score(full_snap)
    r_empty = engines["growth_leader_pullback"].score(empty_snap)
    assert r_full.confidence > r_empty.confidence


def test_risk_inputs_populated_with_tags(engines):
    snap = _snap(
        secondary_tags=["HIGH_ATR", "EARNINGS_NEAR"],
        atr_percent=4.5,
        earnings_days_away=5,
    )
    result = engines["growth_leader_pullback"].score(snap)
    assert "active_overrides" in result.risk_inputs
    assert "HIGH_ATR" in result.risk_inputs["active_overrides"]
    assert "EARNINGS_NEAR" in result.risk_inputs["active_overrides"]
