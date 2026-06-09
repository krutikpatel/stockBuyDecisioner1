from __future__ import annotations

from typing import Any

from codex_backed.features.snapshot import FeatureSnapshot


def build_feature_snapshot_from_mapping(values: dict[str, Any]) -> FeatureSnapshot:
    """Build a FeatureSnapshot from a flat mapping.

    This adapter is intentionally permissive for the first implementation phase:
    callers can pass rows from historical signal CSVs or future service adapters.
    Unknown keys are ignored and missing values remain None/defaulted.
    """
    allowed = set(FeatureSnapshot.__dataclass_fields__)
    filtered = {key: value for key, value in values.items() if key in allowed}
    required = {"ticker", "date", "price"}
    missing_required = [key for key in required if key not in filtered]
    if missing_required:
        raise ValueError(f"Missing required snapshot fields: {missing_required}")
    return FeatureSnapshot(**filtered)

