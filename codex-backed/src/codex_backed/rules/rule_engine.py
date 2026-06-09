from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuleEvaluationResult:
    matched: bool
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    confidence_penalty: float = 0.0


class RuleEngine:
    """Evaluate JSON logic rules against a flat feature dictionary."""

    def __init__(self, missing_field_penalty: float = 10.0):
        self._missing_field_penalty = missing_field_penalty

    def evaluate(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> RuleEvaluationResult:
        matched, reasons, missing = self._eval_node(rule, snapshot)
        unique_missing = list(dict.fromkeys(missing))
        penalty = min(len(unique_missing) * self._missing_field_penalty, 100.0)
        return RuleEvaluationResult(
            matched=matched,
            reasons=reasons,
            missing_fields=unique_missing,
            confidence_penalty=penalty,
        )

    def _eval_node(
        self,
        node: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> tuple[bool, list[str], list[str]]:
        if "all" in node:
            return self._eval_all(node["all"], snapshot)
        if "any" in node:
            return self._eval_any(node["any"], snapshot)
        if "not" in node:
            return self._eval_not(node["not"], snapshot)
        matched, reason, missing = self._eval_condition(node, snapshot)
        field = node.get("field", "<unknown>")
        return matched, [reason], [field] if missing else []

    def _eval_all(
        self,
        nodes: list[dict[str, Any]],
        snapshot: dict[str, Any],
    ) -> tuple[bool, list[str], list[str]]:
        reasons: list[str] = []
        missing: list[str] = []
        for node in nodes:
            matched, node_reasons, node_missing = self._eval_node(node, snapshot)
            reasons.extend(node_reasons)
            missing.extend(node_missing)
            if not matched:
                return False, reasons, missing
        return True, reasons, missing

    def _eval_any(
        self,
        nodes: list[dict[str, Any]],
        snapshot: dict[str, Any],
    ) -> tuple[bool, list[str], list[str]]:
        reasons: list[str] = []
        missing: list[str] = []
        for node in nodes:
            matched, node_reasons, node_missing = self._eval_node(node, snapshot)
            reasons.extend(node_reasons)
            missing.extend(node_missing)
            if matched:
                return True, reasons, missing
        return False, reasons, missing

    def _eval_not(
        self,
        node: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> tuple[bool, list[str], list[str]]:
        matched, reasons, missing = self._eval_node(node, snapshot)
        return not matched, [f"NOT({reason})" for reason in reasons], missing

    def _eval_condition(
        self,
        condition: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> tuple[bool, str, bool]:
        field = condition["field"]
        operator = condition["operator"]
        expected = condition.get("value")

        if operator == "exists":
            matched = field in snapshot and snapshot[field] is not None
            return matched, f"{field} {'exists' if matched else 'is missing'}", False

        if operator == "missing":
            matched = field not in snapshot or snapshot[field] is None
            return matched, f"{field} {'is missing' if matched else 'is present'}", False

        actual = snapshot.get(field)
        if actual is None:
            return False, f"{field} is None", True

        matched = self._apply_operator(operator, actual, expected)
        return matched, f"{field} {operator} {expected} actual={actual}", False

    @staticmethod
    def _apply_operator(operator: str, actual: Any, expected: Any) -> bool:
        if operator == ">=":
            return actual >= expected
        if operator == "<=":
            return actual <= expected
        if operator == ">":
            return actual > expected
        if operator == "<":
            return actual < expected
        if operator == "==":
            return actual == expected
        if operator == "!=":
            return actual != expected
        if operator == "in":
            return actual in expected
        if operator == "not_in":
            return actual not in expected
        if operator == "between":
            low, high = expected
            return low <= actual <= high
        if operator == "contains":
            if isinstance(actual, list):
                return expected in actual
            return str(expected).lower() in str(actual).lower()
        raise ValueError(f"Unknown operator: {operator!r}")

