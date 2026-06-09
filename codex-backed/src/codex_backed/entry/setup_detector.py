from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codex_backed.rules.rule_engine import RuleEngine


@dataclass(frozen=True)
class SignalMatch:
    name: str
    matched: bool
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SetupDetectionResult:
    selected_setup: str | None
    matched_signals: list[str]
    blocked_signals: list[str]
    optional_signals: list[str]
    missing_fields: list[str]


class EntrySetupDetector:
    """Detect the highest-priority technical setup for a feature snapshot."""

    def __init__(self, technical_setup_config: dict[str, Any], rule_engine: RuleEngine | None = None):
        self._config = technical_setup_config
        self._engine = rule_engine or RuleEngine()

    def detect(self, snapshot: dict[str, Any]) -> SetupDetectionResult:
        signal_matches = self._evaluate_signals(snapshot)
        setup_defs = self._config.get("entry_setups") or self._config.get("technical_setups") or {}
        missing_fields: list[str] = []

        for setup_name, setup in sorted(setup_defs.items(), key=lambda item: item[1].get("priority", 999)):
            required = setup.get("required_signals", [])
            optional = setup.get("optional_signals", [])
            blocking = setup.get("blocking_signals", [])
            min_optional = int(setup.get("min_required_optional_signals", 0))

            matched_required = [name for name in required if signal_matches.get(name, SignalMatch(name, False)).matched]
            matched_optional = [name for name in optional if signal_matches.get(name, SignalMatch(name, False)).matched]
            matched_blocking = [name for name in blocking if signal_matches.get(name, SignalMatch(name, False)).matched]

            for name in required + optional + blocking:
                missing_fields.extend(signal_matches.get(name, SignalMatch(name, False)).missing_fields)

            if len(matched_required) != len(required):
                continue
            if matched_blocking:
                continue
            if len(matched_optional) < min_optional:
                continue

            return SetupDetectionResult(
                selected_setup=setup_name,
                matched_signals=matched_required,
                blocked_signals=matched_blocking,
                optional_signals=matched_optional,
                missing_fields=list(dict.fromkeys(missing_fields)),
            )

        all_matched = [name for name, match in signal_matches.items() if match.matched]
        all_missing: list[str] = []
        for match in signal_matches.values():
            all_missing.extend(match.missing_fields)
        return SetupDetectionResult(
            selected_setup=None,
            matched_signals=all_matched,
            blocked_signals=[],
            optional_signals=[],
            missing_fields=list(dict.fromkeys(all_missing)),
        )

    def _evaluate_signals(self, snapshot: dict[str, Any]) -> dict[str, SignalMatch]:
        matches: dict[str, SignalMatch] = {}
        for name, raw_logic in self._config.get("signal_definitions", {}).items():
            logic = _strip_description(raw_logic)
            result = self._engine.evaluate(logic, snapshot)
            matches[name] = SignalMatch(
                name=name,
                matched=result.matched,
                missing_fields=result.missing_fields,
            )
        return matches


def _strip_description(logic: dict[str, Any]) -> dict[str, Any]:
    if "description" not in logic:
        return logic
    return {key: value for key, value in logic.items() if key != "description"}

