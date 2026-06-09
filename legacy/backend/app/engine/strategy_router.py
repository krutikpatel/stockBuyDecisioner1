from __future__ import annotations

from dataclasses import dataclass, field

from app.config.config_loader import MultiSourceConfig
from app.engine.rule_engine import RuleEngine
from app.features.feature_snapshot import FeatureSnapshot


@dataclass
class StrategyRoutingResult:
    selected_strategy: str
    matched_rule_id: str
    confidence: float
    debug_info: dict = field(default_factory=dict)


class StrategyRouter:
    """Routes a FeatureSnapshot to the appropriate strategy engine.

    Rules are evaluated in descending priority order (highest priority number
    first). The first matching rule wins. If no rule matches, the fallback
    strategy from config is used.

    The snapshot must have primary_category, selected_setup, secondary_tags,
    and market_regime set before routing.
    """

    def __init__(self, config: MultiSourceConfig, rule_engine: RuleEngine):
        # Sort rules by priority descending so highest priority is evaluated first
        self._rules: list[dict] = sorted(
            config.strategy_router_rules,
            key=lambda r: r.get("priority", 0),
            reverse=True,
        )
        self._fallback: str = config.strategy_router_fallback
        self._engine = rule_engine

    def route(self, snapshot: FeatureSnapshot) -> StrategyRoutingResult:
        flat = snapshot.to_dict()
        evaluated: list[str] = []

        for rule in self._rules:
            rule_id = rule.get("id", "unknown")
            evaluated.append(rule_id)
            result = self._engine.evaluate(rule["logic"], flat)
            if result.matched:
                return StrategyRoutingResult(
                    selected_strategy=rule["strategy"],
                    matched_rule_id=rule_id,
                    confidence=max(0.0, 100.0 - result.confidence_penalty),
                    debug_info={
                        "evaluated_rules": evaluated,
                        "matched_reasons": result.reasons,
                    },
                )

        return StrategyRoutingResult(
            selected_strategy=self._fallback,
            matched_rule_id="fallback",
            confidence=30.0,
            debug_info={"evaluated_rules": evaluated, "matched_reasons": ["No routing rule matched"]},
        )
