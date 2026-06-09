"""Avoid-side deterioration scorer for stocks that failed the quality gate."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.engine.rule_engine import RuleEngine
from app.features.feature_snapshot import FeatureSnapshot

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "avoid_side_deterioration_config.json"


@dataclass
class AvoidSideResult:
    score: float
    decision: str          # "AVOID" | "WATCHLIST"
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


class AvoidSideScorer:
    """Point-accumulation scorer for the avoid-side (deteriorating-business) path.

    Iterates over rules defined in avoid_side_deterioration_config.json.
    Each rule that fires adds points (higher = more confirmed deterioration).
    Final score is clamped to [0, 100].
    Decision: AVOID if score >= threshold, else WATCHLIST (early warning).
    """

    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or _CONFIG_PATH
        with open(path) as f:
            self._config = json.load(f)
        self._engine = RuleEngine()
        self._avoid_threshold: float = self._config["decision_thresholds"]["avoid_min_score"]

    def score(self, snapshot: FeatureSnapshot) -> AvoidSideResult:
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
                fired_reasons.append(f"[+{pts}] {rule['reason']}")

        score = max(0.0, min(100.0, total_points))
        decision = "AVOID" if score >= self._avoid_threshold else "WATCHLIST"

        return AvoidSideResult(
            score=score,
            decision=decision,
            reasons=fired_reasons,
            missing_fields=list(dict.fromkeys(all_missing)),
        )
