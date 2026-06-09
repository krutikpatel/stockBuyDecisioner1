"""Tests for MultiSourceConfig — verifies config loading and property access."""
from __future__ import annotations
import pytest
from app.config.config_loader import MultiSourceConfig, get_multi_config, reset_multi_config


@pytest.fixture
def config():
    return MultiSourceConfig()


def test_config_loads_without_error(config):
    assert config is not None


def test_universe_filters_has_min_price(config):
    uf = config.universe_filters
    assert "min_price" in uf
    assert uf["min_price"] > 0


def test_sector_benchmarks_has_technology(config):
    sb = config.sector_benchmarks
    assert "Technology" in sb
    assert sb["Technology"] == "XLK"


def test_market_regime_rules_present(config):
    mrr = config.market_regime_rules
    assert "vix_bear_high_threshold" in mrr
    assert "regime_weight_adjustments" in mrr


def test_regime_weight_adjustments_has_bull(config):
    adj = config.regime_weight_adjustments
    assert "BULL_RISK_ON" in adj
    assert "BEAR_RISK_OFF" in adj


def test_active_provider_is_yfinance(config):
    assert config.active_provider == "yfinance"


def test_primary_categories_list(config):
    cats = config.primary_categories
    assert isinstance(cats, list)
    assert "PROFITABLE_GROWTH_LEADER" in cats
    assert "HYPER_GROWTH_STORY" in cats


def test_archetype_rules_present(config):
    rules = config.archetype_rules
    assert "hyper_growth_rev_yoy_min" in rules


def test_secondary_tag_rules_present(config):
    tags = config.secondary_tag_rules
    assert "EXPENSIVE_VALUATION" in tags
    assert "HIGH_ATR" in tags
    assert "EARNINGS_NEAR" in tags
    assert "SECTOR_LEADER" in tags


def test_signal_definitions_has_all_signals(config):
    sigs = config.signal_definitions
    expected = [
        "STRONG_UPTREND", "SMA50_PULLBACK", "RSI_PULLBACK_ZONE",
        "VOLUME_DRY_UP", "BREAKOUT_CONFIRMED", "RS_LEADER_VS_SECTOR",
        "TRUE_BROKEN_CHART", "BROKEN_SUPPORT", "OVERSOLD_REVERSAL",
        "EXTENDED_ABOVE_SMA20",
    ]
    for s in expected:
        assert s in sigs, f"Missing signal: {s}"


def test_setup_definitions_has_all_setups(config):
    setups = config.setup_definitions
    expected = [
        "GROWTH_LEADER_PULLBACK", "TRUE_BROKEN_CHART_AVOID",
        "DOWNTREND_REBOUND_CANDIDATE", "BREAKOUT_MOMENTUM",
    ]
    for s in expected:
        assert s in setups, f"Missing setup: {s}"


def test_strategy_router_rules_list(config):
    rules = config.strategy_router_rules
    assert isinstance(rules, list)
    assert len(rules) > 0


def test_strategy_engines_has_4_engines(config):
    engines = config.strategy_engines
    expected = [
        "growth_leader_pullback", "downtrend_rebound",
        "true_broken_chart_avoid", "quality_growth_expensive_but_working",
    ]
    for e in expected:
        assert e in engines, f"Missing engine: {e}"


def test_frozen_params_not_empty(config):
    assert len(config.frozen_params) > 0


def test_singleton_returns_same_instance():
    reset_multi_config()
    a = get_multi_config()
    b = get_multi_config()
    assert a is b


def test_reset_creates_new_instance():
    reset_multi_config()
    a = get_multi_config()
    reset_multi_config()
    b = get_multi_config()
    assert a is not b
