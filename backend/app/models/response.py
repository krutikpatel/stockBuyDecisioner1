from __future__ import annotations
from typing import Optional
from pydantic import BaseModel

from app.models.market import MarketData, TechnicalIndicators
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary


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


class HorizonRecommendation(BaseModel):
    horizon: str
    decision: str
    score: float
    confidence: str
    confidence_score: float = 100.0     # 0–100; reduced when data is missing
    data_completeness_score: float = 100.0  # 0–100; tracks how much data was available
    summary: str
    bullish_factors: list[str] = []
    bearish_factors: list[str] = []
    entry_plan: EntryPlan
    exit_plan: ExitPlan
    risk_reward: RiskReward
    position_sizing: PositionSizing
    data_warnings: list[str] = []


class DataQualityReport(BaseModel):
    score: float
    warnings: list[str] = []


# Valid label sets for SignalProfile fields
_MOMENTUM_LABELS = {"VERY_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "VERY_BEARISH"}
_VALUATION_LABELS = {"ATTRACTIVE", "FAIR", "ELEVATED", "RISKY"}
_ENTRY_LABELS = {"IDEAL", "ACCEPTABLE", "EXTENDED", "VERY_EXTENDED"}
_RISK_LABELS = {"EXCELLENT", "GOOD", "ACCEPTABLE", "POOR"}


class SignalProfile(BaseModel):
    momentum: str       # VERY_BULLISH | BULLISH | NEUTRAL | BEARISH | VERY_BEARISH
    growth: str         # VERY_BULLISH | BULLISH | NEUTRAL | BEARISH | VERY_BEARISH
    valuation: str      # ATTRACTIVE | FAIR | ELEVATED | RISKY
    entry_timing: str   # IDEAL | ACCEPTABLE | EXTENDED | VERY_EXTENDED
    sentiment: str      # VERY_BULLISH | BULLISH | NEUTRAL | BEARISH | VERY_BEARISH
    risk_reward: str    # EXCELLENT | GOOD | ACCEPTABLE | POOR


class StockAnalysisResult(BaseModel):
    ticker: str
    generated_at: str
    current_price: float
    data_quality: DataQualityReport
    market_data: MarketData
    technicals: TechnicalIndicators
    fundamentals: FundamentalData
    valuation: ValuationData
    earnings: EarningsData
    news: NewsSummary
    recommendations: list[HorizonRecommendation]
    markdown_report: str
    archetype: str = "PROFITABLE_GROWTH"
    archetype_confidence: float = 0.0
    market_regime: str = "SIDEWAYS_CHOPPY"
    regime_confidence: float = 0.0
    signal_profile: Optional[SignalProfile] = None
    disclaimer: str = (
        "This is a decision-support tool, not financial advice. "
        "The recommendation is based only on available data. "
        "Always verify important information before investing."
    )
