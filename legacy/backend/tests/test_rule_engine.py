"""Tests for the generic JSON RuleEngine."""
from __future__ import annotations
import pytest
from app.engine.rule_engine import RuleEngine, RuleEvaluationResult


@pytest.fixture
def engine():
    return RuleEngine()


# ---------------------------------------------------------------------------
# Basic operators
# ---------------------------------------------------------------------------

def test_gte_match(engine):
    r = engine.evaluate({"field": "rsi14", "operator": ">=", "value": 40}, {"rsi14": 50})
    assert r.matched

def test_gte_no_match(engine):
    r = engine.evaluate({"field": "rsi14", "operator": ">=", "value": 60}, {"rsi14": 50})
    assert not r.matched

def test_lte_match(engine):
    r = engine.evaluate({"field": "rsi14", "operator": "<=", "value": 60}, {"rsi14": 50})
    assert r.matched

def test_gt_match(engine):
    r = engine.evaluate({"field": "x", "operator": ">", "value": 0}, {"x": 0.1})
    assert r.matched

def test_lt_match(engine):
    r = engine.evaluate({"field": "x", "operator": "<", "value": 0}, {"x": -0.1})
    assert r.matched

def test_eq_match(engine):
    r = engine.evaluate({"field": "trend_label", "operator": "==", "value": "downtrend"}, {"trend_label": "downtrend"})
    assert r.matched

def test_eq_no_match(engine):
    r = engine.evaluate({"field": "trend_label", "operator": "==", "value": "downtrend"}, {"trend_label": "sideways"})
    assert not r.matched

def test_neq_match(engine):
    r = engine.evaluate({"field": "x", "operator": "!=", "value": "BEAR_RISK_OFF"}, {"x": "BULL_RISK_ON"})
    assert r.matched

def test_in_match(engine):
    r = engine.evaluate({"field": "trend_label", "operator": "in", "value": ["strong_uptrend", "weak_uptrend"]}, {"trend_label": "weak_uptrend"})
    assert r.matched

def test_in_no_match(engine):
    r = engine.evaluate({"field": "trend_label", "operator": "in", "value": ["strong_uptrend", "weak_uptrend"]}, {"trend_label": "sideways"})
    assert not r.matched

def test_not_in_match(engine):
    r = engine.evaluate({"field": "regime", "operator": "not_in", "value": ["BEAR_RISK_OFF"]}, {"regime": "BULL_RISK_ON"})
    assert r.matched

def test_between_match(engine):
    r = engine.evaluate({"field": "rsi14", "operator": "between", "value": [38, 58]}, {"rsi14": 48})
    assert r.matched

def test_between_boundary_low(engine):
    r = engine.evaluate({"field": "rsi14", "operator": "between", "value": [38, 58]}, {"rsi14": 38})
    assert r.matched

def test_between_boundary_high(engine):
    r = engine.evaluate({"field": "rsi14", "operator": "between", "value": [38, 58]}, {"rsi14": 58})
    assert r.matched

def test_between_no_match(engine):
    r = engine.evaluate({"field": "rsi14", "operator": "between", "value": [38, 58]}, {"rsi14": 70})
    assert not r.matched

def test_contains_match(engine):
    r = engine.evaluate({"field": "label", "operator": "contains", "value": "GROWTH"}, {"label": "PROFITABLE_GROWTH_LEADER"})
    assert r.matched

def test_exists_match(engine):
    r = engine.evaluate({"field": "rsi14", "operator": "exists"}, {"rsi14": 55})
    assert r.matched

def test_exists_no_match_none(engine):
    r = engine.evaluate({"field": "rsi14", "operator": "exists"}, {"rsi14": None})
    assert not r.matched

def test_exists_no_match_absent(engine):
    r = engine.evaluate({"field": "rsi14", "operator": "exists"}, {})
    assert not r.matched

def test_missing_match(engine):
    r = engine.evaluate({"field": "earnings_days_away", "operator": "missing"}, {"earnings_days_away": None})
    assert r.matched

def test_missing_no_match(engine):
    r = engine.evaluate({"field": "earnings_days_away", "operator": "missing"}, {"earnings_days_away": 10})
    assert not r.matched

def test_unknown_operator_raises(engine):
    with pytest.raises(ValueError, match="Unknown operator"):
        engine.evaluate({"field": "x", "operator": "BOGUS", "value": 1}, {"x": 1})


# ---------------------------------------------------------------------------
# Logical nodes
# ---------------------------------------------------------------------------

def test_all_both_match(engine):
    r = engine.evaluate(
        {"all": [
            {"field": "rsi14", "operator": ">=", "value": 38},
            {"field": "rsi14", "operator": "<=", "value": 58},
        ]},
        {"rsi14": 48},
    )
    assert r.matched

def test_all_one_fails(engine):
    r = engine.evaluate(
        {"all": [
            {"field": "rsi14", "operator": ">=", "value": 38},
            {"field": "rsi14", "operator": "<=", "value": 45},
        ]},
        {"rsi14": 50},
    )
    assert not r.matched

def test_any_one_matches(engine):
    r = engine.evaluate(
        {"any": [
            {"field": "rsi14", "operator": ">", "value": 70},
            {"field": "rsi14", "operator": "<", "value": 30},
        ]},
        {"rsi14": 25},
    )
    assert r.matched

def test_any_none_match(engine):
    r = engine.evaluate(
        {"any": [
            {"field": "rsi14", "operator": ">", "value": 70},
            {"field": "rsi14", "operator": "<", "value": 30},
        ]},
        {"rsi14": 50},
    )
    assert not r.matched

def test_not_negates_match(engine):
    r = engine.evaluate(
        {"not": {"field": "trend_label", "operator": "==", "value": "downtrend"}},
        {"trend_label": "strong_uptrend"},
    )
    assert r.matched

def test_not_negates_no_match(engine):
    r = engine.evaluate(
        {"not": {"field": "trend_label", "operator": "==", "value": "downtrend"}},
        {"trend_label": "downtrend"},
    )
    assert not r.matched

def test_nested_all_inside_any(engine):
    rule = {
        "any": [
            {"all": [
                {"field": "a", "operator": ">", "value": 10},
                {"field": "b", "operator": ">", "value": 10},
            ]},
            {"field": "c", "operator": ">", "value": 10},
        ]
    }
    assert engine.evaluate(rule, {"a": 5, "b": 5, "c": 20}).matched
    assert engine.evaluate(rule, {"a": 15, "b": 15, "c": 0}).matched
    assert not engine.evaluate(rule, {"a": 5, "b": 5, "c": 5}).matched


# ---------------------------------------------------------------------------
# Missing field handling
# ---------------------------------------------------------------------------

def test_none_field_not_matched(engine):
    r = engine.evaluate({"field": "rsi14", "operator": ">=", "value": 40}, {"rsi14": None})
    assert not r.matched

def test_none_field_recorded_in_missing(engine):
    r = engine.evaluate({"field": "rsi14", "operator": ">=", "value": 40}, {"rsi14": None})
    assert "rsi14" in r.missing_fields

def test_absent_field_not_matched(engine):
    r = engine.evaluate({"field": "rsi14", "operator": ">=", "value": 40}, {})
    assert not r.matched
    assert "rsi14" in r.missing_fields

def test_confidence_penalty_applied(engine):
    r = engine.evaluate({"field": "rsi14", "operator": ">=", "value": 40}, {"rsi14": None})
    assert r.confidence_penalty > 0

def test_confidence_penalty_multiple_missing(engine):
    r = engine.evaluate(
        {"all": [
            {"field": "rsi14", "operator": ">=", "value": 40},
            {"field": "adx", "operator": ">=", "value": 20},
        ]},
        {"rsi14": None, "adx": None},
    )
    # Each missing field adds penalty, but all short-circuits after first None
    assert r.confidence_penalty >= 10.0

def test_no_missing_penalty_when_fields_present(engine):
    r = engine.evaluate({"field": "rsi14", "operator": ">=", "value": 40}, {"rsi14": 50})
    assert r.confidence_penalty == 0.0
    assert r.missing_fields == []

def test_reasons_populated(engine):
    r = engine.evaluate({"field": "rsi14", "operator": ">=", "value": 40}, {"rsi14": 50})
    assert len(r.reasons) > 0
    assert "rsi14" in r.reasons[0]
