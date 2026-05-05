from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class EarningsRecord(BaseModel):
    date: Optional[str] = None
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    eps_surprise_pct: Optional[float] = None
    revenue_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None


class EarningsData(BaseModel):
    last_earnings_date: Optional[str] = None
    next_earnings_date: Optional[str] = None
    history: list[EarningsRecord] = []
    avg_eps_surprise_pct: Optional[float] = None
    beat_count: int = 0
    miss_count: int = 0
    beat_rate: Optional[float] = None
    within_30_days: bool = False
    earnings_score: float = 0.0
