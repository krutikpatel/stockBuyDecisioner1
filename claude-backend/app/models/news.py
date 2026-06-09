from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    source: Optional[str] = None
    published_at: Optional[str] = None
    url: Optional[str] = None
    summary: Optional[str] = None
    sentiment: str = "neutral"   # positive | neutral | negative
    importance: str = "low"       # low | medium | high
    category: str = "other"       # earnings | analyst | product | legal | macro | sector | management | other


class NewsSummary(BaseModel):
    items: list[NewsItem] = []
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    news_score: float = 50.0
    coverage_limited: bool = True
