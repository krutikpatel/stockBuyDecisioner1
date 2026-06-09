from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleEvaluationResult:
    matched: bool
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    confidence_penalty: float = 0.0


_MISSING_FIELD_PENALTY = 10.0


class RuleEngine:
    """Evaluates JSON logic rules against a flat feature dict.

    Supported logic nodes: all (AND), any (OR), not (negate).
    Supported leaf operators: >=, <=, >, <, ==, !=, in, not_in,
      between (two-element list), exists (not None), missing (is None),
      contains (substring check).

    When a field is None/absent the condition evaluates to False with a
    configurable confidence penalty recorded in missing_fields.
    """

    def __init__(self, missing_field_penalty: float = _MISSING_FIELD_PENALTY):
        self._penalty = missing_field_penalty

    def evaluate(self, rule: dict, snapshot: dict) -> RuleEvaluationResult:
        matched, reasons, missing = self._eval_node(rule, snapshot)
        penalty = len(missing) * self._penalty
        return RuleEvaluationResult(
            matched=matched,
            reasons=reasons,
            missing_fields=list(dict.fromkeys(missing)),
            confidence_penalty=min(penalty, 100.0),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _eval_node(
        self, node: dict, snapshot: dict
    ) -> tuple[bool, list[str], list[str]]:
        """Return (matched, reasons, missing_fields)."""
        if "all" in node:
            return self._eval_all(node["all"], snapshot)
        if "any" in node:
            return self._eval_any(node["any"], snapshot)
        if "not" in node:
            return self._eval_not(node["not"], snapshot)
        # Leaf condition
        matched, reason, field_missing = self._eval_condition(node, snapshot)
        missing = [node["field"]] if field_missing else []
        return matched, [reason], missing

    def _eval_all(
        self, children: list[dict], snapshot: dict
    ) -> tuple[bool, list[str], list[str]]:
        all_reasons: list[str] = []
        all_missing: list[str] = []
        for child in children:
            m, reasons, missing = self._eval_node(child, snapshot)
            all_reasons.extend(reasons)
            all_missing.extend(missing)
            if not m:
                return False, all_reasons, all_missing
        return True, all_reasons, all_missing

    def _eval_any(
        self, children: list[dict], snapshot: dict
    ) -> tuple[bool, list[str], list[str]]:
        all_reasons: list[str] = []
        all_missing: list[str] = []
        for child in children:
            m, reasons, missing = self._eval_node(child, snapshot)
            all_reasons.extend(reasons)
            all_missing.extend(missing)
            if m:
                return True, all_reasons, all_missing
        return False, all_reasons, all_missing

    def _eval_not(
        self, child: dict, snapshot: dict
    ) -> tuple[bool, list[str], list[str]]:
        m, reasons, missing = self._eval_node(child, snapshot)
        return not m, [f"NOT({r})" for r in reasons], missing

    def _eval_condition(
        self, condition: dict, snapshot: dict
    ) -> tuple[bool, str, bool]:
        """Return (matched, human_reason, field_was_missing)."""
        field = condition["field"]
        op = condition["operator"]
        value = condition.get("value")

        if op == "exists":
            present = field in snapshot and snapshot[field] is not None
            return present, f"{field} {'exists' if present else 'is missing'}", False

        if op == "missing":
            absent = field not in snapshot or snapshot[field] is None
            return absent, f"{field} {'is missing' if absent else 'is present'}", False

        actual = snapshot.get(field)
        if actual is None:
            return False, f"{field} is None", True

        matched = self._apply_operator(op, actual, value)
        reason = f"{field} {op} {value} → actual={actual} → {'✓' if matched else '✗'}"
        return matched, reason, False

    @staticmethod
    def _apply_operator(op: str, actual: Any, value: Any) -> bool:
        if op == ">=":
            return actual >= value
        if op == "<=":
            return actual <= value
        if op == ">":
            return actual > value
        if op == "<":
            return actual < value
        if op == "==":
            return actual == value
        if op == "!=":
            return actual != value
        if op == "in":
            return actual in value
        if op == "not_in":
            return actual not in value
        if op == "between":
            lo, hi = value[0], value[1]
            return lo <= actual <= hi
        if op == "contains":
            return str(value).lower() in str(actual).lower()
        raise ValueError(f"Unknown operator: {op!r}")
