"""Buy-side dislocation-timing scorer for quality stocks."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.engine.rule_engine import RuleEngine
from app.features.feature_snapshot import FeatureSnapshot

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "buy_side_timing_config.json"


@dataclass
class BuySideResult:
    score: float
    decision: str          # "BUY" | "WAIT"
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


class BuySideScorer:
    """Point-accumulation scorer for the buy-side (quality-intact) path.

    Iterates over rules defined in buy_side_timing_config.json.
    Each rule that fires adds (or subtracts) points.
    Final score is clamped to [0, 100].
    Decision: BUY if score >= threshold, else WAIT.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or _CONFIG_PATH
        with open(path) as f:
            self._config = json.load(f)
        self._engine = RuleEngine()
        self._buy_threshold: float = self._config["decision_thresholds"]["buy_min_score"]

    def score(self, snapshot: FeatureSnapshot) -> BuySideResult:
        snap_dict = snapshot.to_dict()
        rules = self._config["rules"]

        total_points: float = 0.0
        fired_reasons: list[str] = []
        all_missing: list[str] = []

        for rule in rules:
            result = self._engine.evaluate(rule["logic"], snap_dict)
            if result.missing_fields:
                all_missing.extend(result.missing_fields)
            if result.matched:
                pts = rule["points"]
                total_points += pts
                fired_reasons.append(f"[{pts:+d}] {rule['reason']}")

        score = max(0.0, min(100.0, total_points))
        decision = "BUY" if score >= self._buy_threshold else "WAIT"

        return BuySideResult(
            score=score,
            decision=decision,
            reasons=fired_reasons,
            missing_fields=list(dict.fromkeys(all_missing)),
        )
