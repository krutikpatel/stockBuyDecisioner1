from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSize:
    label: str
    base_size_multiplier: float
    final_size_multiplier: float
    applied_caps: list[str]


def compute_position_size(
    *,
    entry_label: str,
    atr_percent: float | None,
    earnings_days_away: int | None,
    risk_config: dict,
) -> PositionSize:
    sizing = risk_config["position_sizing"]
    caps = risk_config["risk_caps"]
    earnings = risk_config["earnings_risk"]

    base = float(sizing.get(entry_label, 0.0))
    final = base
    applied: list[str] = []

    if atr_percent is not None and atr_percent >= float(caps["high_atr_threshold_pct"]):
        cap_multiplier = float(caps["high_atr_position_cap_pct"]) / 100.0
        final = min(final, base * cap_multiplier)
        applied.append("HIGH_ATR_CAP")

    if earnings_days_away is not None:
        if earnings_days_away <= int(earnings["avoid_new_entries_within_days"]):
            final = 0.0
            applied.append("EARNINGS_AVOID")
        elif earnings_days_away <= int(earnings["starter_only_within_days"]):
            starter = float(sizing.get("BUY_STARTER", final))
            final = min(final, starter)
            applied.append("EARNINGS_STARTER_ONLY")

    return PositionSize(
        label=entry_label,
        base_size_multiplier=round(base, 4),
        final_size_multiplier=round(final, 4),
        applied_caps=applied,
    )

