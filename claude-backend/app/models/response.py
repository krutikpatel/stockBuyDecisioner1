from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class EntryPlan(BaseModel):
    preferred_entry: Optional[float] = None
    starter_entry: Optional[float] = None
    breakout_entry: Optional[float] = None
    avoid_above: Optional[float] = None


class ExitPlan(BaseModel):
    stop_loss: Optional[float] = None
    invalidation_level: Optional[float] = None
    first_target: Optional[float] = None
    second_target: Optional[float] = None


class RiskReward(BaseModel):
    downside_percent: Optional[float] = None
    upside_percent: Optional[float] = None
    ratio: Optional[float] = None


class PositionSizing(BaseModel):
    suggested_starter_pct_of_full: int = 25
    max_portfolio_allocation_pct: float = 5.0
