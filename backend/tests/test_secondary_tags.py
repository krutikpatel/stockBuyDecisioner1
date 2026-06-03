"""Tests for secondary tag detection via RuleEngine + stock_classification_config."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from app.config.config_loader import MultiSourceConfig
from app.engine.rule_engine import RuleEngine
from app.features.feature_snapshot import FeatureSnapshot


@pytest.fixture(scope="module")
def tag_rules():
    return MultiSourceConfig().secondary_tag_rules


@pytest.fixture(scope="module")
def engine():
    return RuleEngine()


def _detect_tags(snapshot: FeatureSnapshot, tag_rules: dict, engine: RuleEngine) -> list[str]:
    flat = snapshot.to_dict()
    return [tag for tag, rule in tag_rules.items() if engine.evaluate(rule, flat).matched]


def _snap(**kwargs) -> FeatureSnapshot:
    return FeatureSnapshot(ticker="TEST", **kwargs)


# ---------------------------------------------------------------------------
# HIGH_MOMENTUM
# ---------------------------------------------------------------------------

def test_high_momentum_fires(tag_rules, engine):
    snap = _snap(rsi14=65.0, perf_1m=8.0)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "HIGH_MOMENTUM" in tags


def test_high_momentum_no_fire_low_rsi(tag_rules, engine):
    snap = _snap(rsi14=45.0, perf_1m=8.0)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "HIGH_MOMENTUM" not in tags


# ---------------------------------------------------------------------------
# EXPENSIVE_VALUATION
# ---------------------------------------------------------------------------

def test_expensive_valuation_fires_high_pe(tag_rules, engine):
    snap = _snap(forward_pe=55.0)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "EXPENSIVE_VALUATION" in tags


def test_expensive_valuation_fires_high_ps(tag_rules, engine):
    snap = _snap(price_to_sales=15.0)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "EXPENSIVE_VALUATION" in tags


def test_expensive_valuation_no_fire_reasonable(tag_rules, engine):
    snap = _snap(forward_pe=20.0, price_to_sales=3.0)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "EXPENSIVE_VALUATION" not in tags


# ---------------------------------------------------------------------------
# HIGH_ATR
# ---------------------------------------------------------------------------

def test_high_atr_fires(tag_rules, engine):
    snap = _snap(atr_percent=4.0)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "HIGH_ATR" in tags


def test_high_atr_no_fire_low_volatility(tag_rules, engine):
    snap = _snap(atr_percent=2.0)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "HIGH_ATR" not in tags


# ---------------------------------------------------------------------------
# SECTOR_LEADER
# ---------------------------------------------------------------------------

def test_sector_leader_fires(tag_rules, engine):
    snap = _snap(rs_vs_sector_20d=4.5)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "SECTOR_LEADER" in tags


def test_sector_leader_no_fire_below_threshold(tag_rules, engine):
    snap = _snap(rs_vs_sector_20d=1.0)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "SECTOR_LEADER" not in tags


# ---------------------------------------------------------------------------
# EARNINGS_NEAR
# ---------------------------------------------------------------------------

def test_earnings_near_fires(tag_rules, engine):
    snap = _snap(earnings_days_away=7)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "EARNINGS_NEAR" in tags


def test_earnings_near_no_fire_far_away(tag_rules, engine):
    snap = _snap(earnings_days_away=45)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "EARNINGS_NEAR" not in tags


def test_earnings_near_no_fire_when_none(tag_rules, engine):
    snap = _snap(earnings_days_away=None)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "EARNINGS_NEAR" not in tags


# ---------------------------------------------------------------------------
# HIGH_QUALITY
# ---------------------------------------------------------------------------

def test_high_quality_fires(tag_rules, engine):
    snap = _snap(roic=18.0, operating_margin=0.22)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "HIGH_QUALITY" in tags


def test_high_quality_no_fire_low_roic(tag_rules, engine):
    snap = _snap(roic=8.0, operating_margin=0.22)
    tags = _detect_tags(snap, tag_rules, engine)
    assert "HIGH_QUALITY" not in tags


# ---------------------------------------------------------------------------
# Multiple tags can fire simultaneously
# ---------------------------------------------------------------------------

def test_multiple_tags_fire_together(tag_rules, engine):
    snap = _snap(
        rsi14=65.0, perf_1m=8.0,
        atr_percent=4.5,
        earnings_days_away=5,
        rs_vs_sector_20d=4.0,
    )
    tags = _detect_tags(snap, tag_rules, engine)
    assert "HIGH_MOMENTUM" in tags
    assert "HIGH_ATR" in tags
    assert "EARNINGS_NEAR" in tags
    assert "SECTOR_LEADER" in tags


# ---------------------------------------------------------------------------
# No tags when all fields None
# ---------------------------------------------------------------------------

def test_no_tags_when_all_none(tag_rules, engine):
    snap = _snap()
    tags = _detect_tags(snap, tag_rules, engine)
    # Tags that use "exists" check will fire correctly for missing data — others won't
    assert "HIGH_MOMENTUM" not in tags
    assert "EXPENSIVE_VALUATION" not in tags
    assert "HIGH_ATR" not in tags
