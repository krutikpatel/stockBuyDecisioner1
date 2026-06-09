from codex_backed.rules.rule_engine import RuleEngine


def test_rule_engine_supports_core_operators():
    engine = RuleEngine()
    snapshot = {
        "price": 100,
        "regime": "BULL_RISK_ON",
        "tags": ["SECTOR_LEADER", "EXPENSIVE_VALUATION"],
        "name": "Quality Growth Leader",
    }

    assert engine.evaluate({"field": "price", "operator": ">=", "value": 90}, snapshot).matched
    assert engine.evaluate({"field": "price", "operator": "<=", "value": 100}, snapshot).matched
    assert engine.evaluate({"field": "price", "operator": ">", "value": 90}, snapshot).matched
    assert engine.evaluate({"field": "price", "operator": "<", "value": 110}, snapshot).matched
    assert engine.evaluate({"field": "regime", "operator": "==", "value": "BULL_RISK_ON"}, snapshot).matched
    assert engine.evaluate({"field": "regime", "operator": "!=", "value": "BEAR_RISK_OFF"}, snapshot).matched
    assert engine.evaluate({"field": "regime", "operator": "in", "value": ["BULL_RISK_ON"]}, snapshot).matched
    assert engine.evaluate({"field": "regime", "operator": "not_in", "value": ["BEAR_RISK_OFF"]}, snapshot).matched
    assert engine.evaluate({"field": "price", "operator": "between", "value": [90, 110]}, snapshot).matched
    assert engine.evaluate({"field": "name", "operator": "contains", "value": "growth"}, snapshot).matched
    assert engine.evaluate({"field": "tags", "operator": "contains", "value": "SECTOR_LEADER"}, snapshot).matched
    assert engine.evaluate({"field": "price", "operator": "exists"}, snapshot).matched
    assert engine.evaluate({"field": "missing_price", "operator": "missing"}, snapshot).matched


def test_rule_engine_supports_all_any_not_and_missing_penalty():
    engine = RuleEngine()
    snapshot = {"rsi14": 31, "market_regime": "SIDEWAYS_CHOPPY"}

    rule = {
        "all": [
            {"field": "rsi14", "operator": "between", "value": [25, 42]},
            {
                "any": [
                    {"field": "market_regime", "operator": "==", "value": "BEAR_RISK_OFF"},
                    {"field": "market_regime", "operator": "==", "value": "SIDEWAYS_CHOPPY"},
                ]
            },
            {"not": {"field": "market_regime", "operator": "==", "value": "BULL_RISK_ON"}},
        ]
    }

    assert engine.evaluate(rule, snapshot).matched

    missing_result = engine.evaluate(
        {"field": "sales_growth_yoy", "operator": ">=", "value": 0.05},
        snapshot,
    )
    assert not missing_result.matched
    assert missing_result.missing_fields == ["sales_growth_yoy"]
    assert missing_result.confidence_penalty == 10.0

