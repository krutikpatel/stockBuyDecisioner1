"""Tests for StrategyRouter — verifies correct strategy engine selection."""
from __future__ import annotations
import pytest
from app.config.config_loader import MultiSourceConfig
from app.engine.rule_engine import RuleEngine
from app.engine.strategy_router import StrategyRouter, StrategyRoutingResult
from app.features.feature_snapshot import FeatureSnapshot


@pytest.fixture(scope="module")
def router():
    config = MultiSourceConfig()
    return StrategyRouter(config, RuleEngine())


def _snap(**kwargs) -> FeatureSnapshot:
    defaults = dict(ticker="TEST", trend_label="sideways", is_extended=False)
    defaults.update(kwargs)
    return FeatureSnapshot(**defaults)


# ---------------------------------------------------------------------------
# TRUE_BROKEN_CHART_AVOID — priority 100, must win regardless
# ---------------------------------------------------------------------------

def test_broken_chart_routes_to_avoid(router):
    snap = _snap(selected_setup="TRUE_BROKEN_CHART_AVOID")
    result = router.route(snap)
    assert result.selected_strategy == "true_broken_chart_avoid"


def test_broken_chart_wins_over_growth_leader(router):
    snap = _snap(
        selected_setup="TRUE_BROKEN_CHART_AVOID",
        primary_category="PROFITABLE_GROWTH_LEADER",
        market_regime="BULL_RISK_ON",
    )
    result = router.route(snap)
    assert result.selected_strategy == "true_broken_chart_avoid"


# ---------------------------------------------------------------------------
# growth_leader_pullback
# ---------------------------------------------------------------------------

def test_growth_leader_pullback_routes_correctly(router):
    snap = _snap(
        primary_category="PROFITABLE_GROWTH_LEADER",
        selected_setup="GROWTH_LEADER_PULLBACK",
        market_regime="BULL_RISK_ON",
    )
    result = router.route(snap)
    assert result.selected_strategy == "growth_leader_pullback"


def test_hyper_growth_pullback_routes_correctly(router):
    snap = _snap(
        primary_category="HYPER_GROWTH_STORY",
        selected_setup="GROWTH_LEADER_PULLBACK",
        market_regime="SIDEWAYS_CHOPPY",
    )
    result = router.route(snap)
    assert result.selected_strategy == "growth_leader_pullback"


def test_growth_leader_pullback_blocked_in_bear(router):
    snap = _snap(
        primary_category="PROFITABLE_GROWTH_LEADER",
        selected_setup="GROWTH_LEADER_PULLBACK",
        market_regime="BEAR_RISK_OFF",
    )
    result = router.route(snap)
    assert result.selected_strategy != "growth_leader_pullback"


def test_mature_value_pullback_does_not_route_to_growth(router):
    snap = _snap(
        primary_category="MATURE_VALUE",
        selected_setup="GROWTH_LEADER_PULLBACK",
        market_regime="BULL_RISK_ON",
    )
    result = router.route(snap)
    assert result.selected_strategy != "growth_leader_pullback"


# ---------------------------------------------------------------------------
# quality_growth_expensive_but_working
# ---------------------------------------------------------------------------

def test_expensive_sector_leader_routes_correctly(router):
    snap = _snap(
        primary_category="PROFITABLE_GROWTH_LEADER",
        selected_setup=None,
        secondary_tags=["EXPENSIVE_VALUATION", "SECTOR_LEADER"],
        market_regime="BULL_RISK_ON",
    )
    result = router.route(snap)
    assert result.selected_strategy == "quality_growth_expensive_but_working"


def test_expensive_not_sector_leader_does_not_route(router):
    snap = _snap(
        secondary_tags=["EXPENSIVE_VALUATION"],
        market_regime="BULL_RISK_ON",
    )
    result = router.route(snap)
    assert result.selected_strategy != "quality_growth_expensive_but_working"


# ---------------------------------------------------------------------------
# downtrend_rebound
# ---------------------------------------------------------------------------

def test_rebound_candidate_routes_correctly(router):
    snap = _snap(selected_setup="DOWNTREND_REBOUND_CANDIDATE")
    result = router.route(snap)
    assert result.selected_strategy == "downtrend_rebound"


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def test_no_match_falls_back(router):
    snap = _snap()  # no setup, no category match
    result = router.route(snap)
    assert result.selected_strategy == "watchlist_low_confidence"
    assert result.matched_rule_id == "fallback"


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

def test_result_type(router):
    snap = _snap(selected_setup="DOWNTREND_REBOUND_CANDIDATE")
    result = router.route(snap)
    assert isinstance(result, StrategyRoutingResult)
    assert isinstance(result.selected_strategy, str)
    assert isinstance(result.confidence, float)
    assert isinstance(result.debug_info, dict)


def test_matched_rule_id_returned(router):
    snap = _snap(
        primary_category="PROFITABLE_GROWTH_LEADER",
        selected_setup="GROWTH_LEADER_PULLBACK",
        market_regime="BULL_RISK_ON",
    )
    result = router.route(snap)
    assert result.matched_rule_id != ""
    assert result.matched_rule_id != "fallback"
