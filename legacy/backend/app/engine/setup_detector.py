from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SetupDetectionResult:
    selected_setup: Optional[str]
    all_matching_setups: list[str]
    blocked_by: dict[str, list[str]]   # setup_name → blocking signals that fired
    confidence: float
    debug_info: dict


class SetupDetector:
    """Combines detected signals into named setups.

    Each setup definition (from technical_setup_config.json) specifies:
      - required_signals: all must be active
      - optional_signals: at least min_required_optional must be active
      - blocking_signals: if any are active, the setup is disqualified
      - priority: lower number = evaluated first (highest priority)

    The first matching setup in priority order is selected.
    """

    def __init__(self, setup_definitions: dict[str, dict]):
        # Sort by priority ascending (1 = highest priority)
        self._setups: list[tuple[str, dict]] = sorted(
            setup_definitions.items(),
            key=lambda kv: kv[1].get("priority", 50),
        )

    def detect(self, active_signals: set[str]) -> SetupDetectionResult:
        matching: list[str] = []
        blocked_by: dict[str, list[str]] = {}

        for name, defn in self._setups:
            required = set(defn.get("required_signals", []))
            optional = set(defn.get("optional_signals", []))
            blocking = set(defn.get("blocking_signals", []))
            min_optional = defn.get("min_required_optional_signals", 0)

            fired_blocking = blocking & active_signals
            if fired_blocking:
                blocked_by[name] = sorted(fired_blocking)
                continue

            if not required.issubset(active_signals):
                continue

            optional_met = len(optional & active_signals)
            if optional_met < min_optional:
                continue

            matching.append(name)

        selected = matching[0] if matching else None
        confidence = _setup_confidence(selected, active_signals, self._setups)

        return SetupDetectionResult(
            selected_setup=selected,
            all_matching_setups=matching,
            blocked_by=blocked_by,
            confidence=confidence,
            debug_info={
                "active_signals": sorted(active_signals),
                "evaluated_setups": [n for n, _ in self._setups],
            },
        )


def _setup_confidence(
    selected: Optional[str],
    active_signals: set[str],
    setups: list[tuple[str, dict]],
) -> float:
    if not selected:
        return 0.0
    for name, defn in setups:
        if name != selected:
            continue
        required = set(defn.get("required_signals", []))
        optional = set(defn.get("optional_signals", []))
        max_optional = len(optional)
        optional_met = len(optional & active_signals)
        base = 60.0
        if max_optional > 0:
            base += 40.0 * (optional_met / max_optional)
        return round(base, 1)
    return 0.0
