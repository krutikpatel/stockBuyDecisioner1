from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class StockAnalysisRequest(BaseModel):
    ticker: str
    horizons: list[str] = ["short_term", "medium_term", "long_term"]
    risk_profile: str = "moderate"  # conservative | moderate | aggressive
    max_position_percent: Optional[float] = None
    max_loss_percent: Optional[float] = None
    current_holding_shares: Optional[float] = None
    average_cost: Optional[float] = None
