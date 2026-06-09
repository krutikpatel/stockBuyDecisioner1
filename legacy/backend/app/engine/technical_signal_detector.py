from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.rule_engine import RuleEngine
from app.features.feature_snapshot import FeatureSnapshot


@dataclass
class SignalDetectionResult:
    active_signals: set[str]
    signal_reasons: dict[str, str]
    missing_fields: list[str]
    confidence_penalty: float


class TechnicalSignalDetector:
    """Maps computed indicator values to named boolean signals.

    Each signal is a named JSON rule evaluated by RuleEngine. The signal
    definitions are loaded from technical_setup_config.json at construction
    time. The signal names become the shared vocabulary for SetupDetector
    and StrategyRouter.
    """

    def __init__(self, signal_definitions: dict[str, dict], rule_engine: RuleEngine):
        self._definitions = signal_definitions
        self._engine = rule_engine

    def detect(self, snapshot: FeatureSnapshot) -> SignalDetectionResult:
        flat = snapshot.to_dict()
        active: set[str] = set()
        reasons: dict[str, str] = {}
        all_missing: list[str] = []
        total_penalty = 0.0

        for name, rule in self._definitions.items():
            result = self._engine.evaluate(rule, flat)
            if result.matched:
                active.add(name)
            all_missing.extend(result.missing_fields)
            total_penalty += result.confidence_penalty
            reasons[name] = "; ".join(result.reasons)

        # Deduplicate missing fields while preserving order
        seen: dict[str, None] = {}
        for f in all_missing:
            seen[f] = None

        return SignalDetectionResult(
            active_signals=active,
            signal_reasons=reasons,
            missing_fields=list(seen.keys()),
            confidence_penalty=min(total_penalty, 100.0),
        )
