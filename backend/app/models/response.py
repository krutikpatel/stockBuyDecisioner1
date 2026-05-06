from __future__ import annotations
from typing import Optional
from pydantic import BaseModel

from app.models.market import MarketData, TechnicalIndicators
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary


# ---------------------------------------------------------------------------
# Signal Card models (Story 5)
# ---------------------------------------------------------------------------

class SignalCardLabel:
    VERY_BULLISH = "VERY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    VERY_BEARISH = "VERY_BEARISH"

    @classmethod
    def from_score(cls, score: float) -> str:
        """Map a 0–100 score to a label using standard thresholds."""
        if score >= 80:
            return cls.VERY_BULLISH
        if score >= 60:
            return cls.BULLISH
        if score >= 40:
            return cls.NEUTRAL
        if score >= 20:
            return cls.BEARISH
        return cls.VERY_BEARISH


class SignalCard(BaseModel):
    name: str
    score: float                          # 0–100
    label: str                            # SignalCardLabel value
    explanation: str
    top_positives: list[str] = []
    top_negatives: list[str] = []
    missing_data_warnings: list[str] = []


class SignalCards(BaseModel):
    momentum: SignalCard
    trend: SignalCard
    entry_timing: SignalCard
    volume_accumulation: SignalCard
    volatility_risk: SignalCard
    relative_strength: SignalCard
    growth: SignalCard
    valuation: SignalCard
    quality: SignalCard
    ownership: SignalCard
    catalyst: SignalCard


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
    signal_cards_weights: dict[str, float] = {}  # card name → weight for this horizon


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
    signal_cards: Optional[SignalCards] = None
    disclaimer: str = (
        "This is a decision-support tool, not financial advice. "
        "The recommendation is based only on available data. "
        "Always verify important information before investing."
    )
