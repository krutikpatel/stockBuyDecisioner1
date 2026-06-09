from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StopTarget:
    initial_stop: float
    target_1: float
    risk_per_share: float
    initial_risk_pct: float


def compute_atr(bars: list[dict[str, Any]], entry_index: int, period: int = 14) -> float | None:
    start = max(0, entry_index - period)
    window = bars[start : entry_index + 1]
    if len(window) < 2:
        return None
    true_ranges: list[float] = []
    for idx in range(1, len(window)):
        high = float(window[idx].get("high", window[idx]["close"]))
        low = float(window[idx].get("low", window[idx]["close"]))
        prev_close = float(window[idx - 1]["close"])
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    if not true_ranges:
        return None
    return sum(true_ranges) / len(true_ranges)


def compute_stop_target(
    bars: list[dict[str, Any]],
    *,
    entry_index: int,
    entry_price: float,
    stop_config: dict,
    partial_profit_config: dict,
    fallback_stop_pct: float = 5.0,
) -> StopTarget:
    atr = compute_atr(bars, entry_index)
    atr_multiplier = float(stop_config.get("atr_multiplier", 2.0))
    support_buffer_pct = float(stop_config.get("support_buffer_pct", 1.0))
    method = stop_config.get("method", "atr_or_support")

    atr_stop = entry_price - atr_multiplier * atr if atr is not None else None
    support_stop = _support_stop(bars, entry_index, support_buffer_pct)

    if method == "atr":
        stop = atr_stop
    elif method == "support":
        stop = support_stop
    else:
        candidates = [value for value in [atr_stop, support_stop] if value is not None]
        stop = max(candidates) if candidates else None

    if stop is None or stop >= entry_price:
        stop = entry_price * (1.0 - fallback_stop_pct / 100.0)

    risk = entry_price - stop
    target = entry_price + float(partial_profit_config.get("target_r_multiple", 2.0)) * risk
    return StopTarget(
        initial_stop=round(stop, 4),
        target_1=round(target, 4),
        risk_per_share=round(risk, 4),
        initial_risk_pct=round(risk / entry_price * 100.0, 4),
    )


def _support_stop(bars: list[dict[str, Any]], entry_index: int, support_buffer_pct: float, lookback: int = 10) -> float | None:
    start = max(0, entry_index - lookback)
    window = bars[start : entry_index + 1]
    if not window:
        return None
    low = min(float(bar.get("low", bar["close"])) for bar in window)
    return low * (1.0 - support_buffer_pct / 100.0)

