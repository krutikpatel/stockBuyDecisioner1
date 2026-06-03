from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.rule_engine import RuleEngine
from app.features.feature_snapshot import FeatureSnapshot


@dataclass
class StrategyEngineResult:
    strategy_name: str
    strategy_score: float
    recommendation: str
    reasons: list[str]
    missing_data: list[str]
    confidence: float
    risk_inputs: dict = field(default_factory=dict)


class ConfigDrivenStrategyEngine:
    """Scores a FeatureSnapshot using JSON-defined rules and produces a recommendation.

    The engine config (from strategy_logic_config.json) contains:
      - score_rules: list of point-awarding rules
      - valuation_penalty_rules: optional negative-point rules (subtracted)
      - decision_thresholds: ordered list of (logic, recommendation) pairs
      - fallback_recommendation: used when no threshold matches
      - risk_overrides: secondary-tag-keyed risk adjustments

    After scoring:
      1. snapshot.strategy_score is set to the accumulated points
      2. snapshot.confidence is set to the base confidence (100 - missing penalty)
      3. Decision thresholds are evaluated against the updated snapshot
    """

    def __init__(self, engine_name: str, engine_config: dict, rule_engine: RuleEngine):
        self._name = engine_name
        self._config = engine_config
        self._engine = rule_engine

    def score(self, snapshot: FeatureSnapshot) -> StrategyEngineResult:
        flat = snapshot.to_dict()
        total_score = 0.0
        fired_reasons: list[str] = []
        all_missing: list[str] = []

        # Accumulate positive score rules
        for rule in self._config.get("score_rules", []):
            result = self._engine.evaluate(rule["logic"], flat)
            all_missing.extend(result.missing_fields)
            if result.matched:
                total_score += rule["points"]
                fired_reasons.append(rule["reason"])

        # Subtract valuation penalty rules (if engine has them)
        for rule in self._config.get("valuation_penalty_rules", []):
            result = self._engine.evaluate(rule["logic"], flat)
            all_missing.extend(result.missing_fields)
            if result.matched:
                total_score += rule["points"]  # points are negative
                fired_reasons.append(rule["reason"])

        total_score = max(0.0, min(total_score, self._config.get("max_possible_score", 100.0)))

        # Compute confidence from missing field penalty
        unique_missing = list(dict.fromkeys(all_missing))
        penalty = len(unique_missing) * 10.0
        confidence = max(0.0, min(100.0 - penalty, 100.0))

        # Update snapshot for threshold evaluation
        snapshot.strategy_score = total_score
        snapshot.confidence = confidence
        updated_flat = snapshot.to_dict()

        # Evaluate decision thresholds in order
        recommendation = self._config.get("fallback_recommendation", "WATCHLIST")
        for threshold in self._config.get("decision_thresholds", []):
            result = self._engine.evaluate(threshold["logic"], updated_flat)
            if result.matched:
                recommendation = threshold["recommendation"]
                break

        risk_inputs = self._build_risk_inputs(snapshot)

        return StrategyEngineResult(
            strategy_name=self._name,
            strategy_score=total_score,
            recommendation=recommendation,
            reasons=fired_reasons,
            missing_data=unique_missing,
            confidence=confidence,
            risk_inputs=risk_inputs,
        )

    def _build_risk_inputs(self, snapshot: FeatureSnapshot) -> dict:
        """Build risk modifier inputs based on secondary tag overrides."""
        overrides = self._config.get("risk_overrides", {})
        active_overrides = {}
        for tag in snapshot.secondary_tags:
            if tag in overrides:
                active_overrides[tag] = overrides[tag]
        return {
            "active_overrides": active_overrides,
            "secondary_tags": snapshot.secondary_tags,
            "atr_percent": snapshot.atr_percent,
            "earnings_days_away": snapshot.earnings_days_away,
        }
