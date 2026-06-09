from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExitEvent:
    event_index: int
    event_date: str | None
    event_type: str
    event_price: float
    position_pct_before: float
    position_pct_after: float
    realized_return_pct: float
    reason: str


@dataclass(frozen=True)
class SimulatedTrade:
    ticker: str
    signal_index: int
    entry_index: int
    entry_price: float
    initial_stop: float
    target_1: float
    target_1_hit: bool
    partial_exit_pct: float
    exit_index: int
    exit_date: str | None
    exit_price: float
    exit_reason: str
    days_held: int
    realized_return_pct: float
    mae_pct: float
    mfe_pct: float
    mfe_capture_pct: float | None
    events: list[ExitEvent] = field(default_factory=list)
