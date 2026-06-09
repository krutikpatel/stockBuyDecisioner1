from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codex_backed.entry.labels import EntryLabel
from codex_backed.entry.setup_detector import EntrySetupDetector, SetupDetectionResult
from codex_backed.features.snapshot import FeatureSnapshot
from codex_backed.rules.rule_engine import RuleEngine


@dataclass(frozen=True)
class EntryDecision:
    ticker: str
    date: str
    horizon: str
    entry_label: str
    entry_score: float
    confidence: float
    selected_setup: str | None
    entry_strategy: str
    reasons: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    matched_signals: list[str] = field(default_factory=list)
    optional_signals: list[str] = field(default_factory=list)

    @property
    def is_actionable(self) -> bool:
        return self.entry_label in {
            EntryLabel.BUY_STARTER.value,
            EntryLabel.BUY_FULL.value,
            EntryLabel.BUY_AGGRESSIVE.value,
        }


class EntryDecisionEngine:
    """Config-driven entry router and scorer."""

    def __init__(
        self,
        entry_config: dict[str, Any],
        technical_setup_config: dict[str, Any],
        rule_engine: RuleEngine | None = None,
    ):
        self._entry_config = entry_config
        self._engine = rule_engine or RuleEngine()
        self._setup_detector = EntrySetupDetector(technical_setup_config, self._engine)

    def decide(self, snapshot: FeatureSnapshot, horizon: str) -> EntryDecision:
        setup_result = self._setup_detector.detect(snapshot.to_dict())
        enriched = snapshot.to_dict()
        enriched["selected_setup"] = setup_result.selected_setup

        strategy_name = self._route(enriched)
        decision = self._score_strategy(
            strategy_name=strategy_name,
            snapshot=enriched,
            base_snapshot=snapshot,
            horizon=horizon,
            setup_result=setup_result,
        )
        return decision

    def _route(self, snapshot: dict[str, Any]) -> str:
        router = self._entry_config["entry_router"]
        rules = sorted(router.get("rules", []), key=lambda rule: rule.get("priority", 0), reverse=True)
        for rule in rules:
            if self._engine.evaluate(rule["logic"], snapshot).matched:
                return rule["entry_engine"]
        return router["fallback_entry_engine"]

    def _score_strategy(
        self,
        *,
        strategy_name: str,
        snapshot: dict[str, Any],
        base_snapshot: FeatureSnapshot,
        horizon: str,
        setup_result: SetupDetectionResult,
    ) -> EntryDecision:
        strategy = self._entry_config["entry_engines"][strategy_name]
        score = 0.0
        reasons: list[str] = []
        missing_fields: list[str] = list(setup_result.missing_fields)

        for rule in strategy.get("score_rules", []):
            result = self._engine.evaluate(rule["logic"], snapshot)
            missing_fields.extend(result.missing_fields)
            if result.matched:
                score += float(rule.get("points", 0))
                reasons.append(rule.get("reason", rule["id"]))

        for rule in strategy.get("penalty_rules", []):
            result = self._engine.evaluate(rule["logic"], snapshot)
            missing_fields.extend(result.missing_fields)
            if result.matched:
                score += float(rule.get("points", 0))
                reasons.append(rule.get("reason", rule["id"]))

        max_score = float(strategy.get("max_score", 100))
        score = max(0.0, min(score, max_score))
        unique_missing = list(dict.fromkeys(missing_fields))
        confidence = max(0.0, 100.0 - len(unique_missing) * 10.0)

        threshold_snapshot = dict(snapshot)
        threshold_snapshot["entry_score"] = score
        threshold_snapshot["confidence"] = confidence

        label = strategy.get("fallback_label", EntryLabel.NO_TRADE.value)
        for threshold in strategy.get("decision_thresholds", []):
            if self._engine.evaluate(threshold["logic"], threshold_snapshot).matched:
                label = threshold["label"]
                break

        return EntryDecision(
            ticker=base_snapshot.ticker,
            date=base_snapshot.date,
            horizon=horizon,
            entry_label=label,
            entry_score=score,
            confidence=confidence,
            selected_setup=setup_result.selected_setup,
            entry_strategy=strategy_name,
            reasons=reasons,
            missing_data=unique_missing,
            matched_signals=setup_result.matched_signals,
            optional_signals=setup_result.optional_signals,
        )

