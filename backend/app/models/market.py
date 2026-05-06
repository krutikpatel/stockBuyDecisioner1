from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class MarketRegime:
    BULL_RISK_ON = "BULL_RISK_ON"
    BULL_NARROW_LEADERSHIP = "BULL_NARROW_LEADERSHIP"
    SIDEWAYS_CHOPPY = "SIDEWAYS_CHOPPY"
    BEAR_RISK_OFF = "BEAR_RISK_OFF"
    SECTOR_ROTATION = "SECTOR_ROTATION"
    LIQUIDITY_RALLY = "LIQUIDITY_RALLY"

    ALL = [
        BULL_RISK_ON, BULL_NARROW_LEADERSHIP, SIDEWAYS_CHOPPY,
        BEAR_RISK_OFF, SECTOR_ROTATION, LIQUIDITY_RALLY,
    ]


class MarketRegimeAssessment(BaseModel):
    regime: str = MarketRegime.SIDEWAYS_CHOPPY
    confidence: float = 0.0
    implication: str = ""
    spy_above_50dma: Optional[bool] = None
    spy_above_200dma: Optional[bool] = None
    qqq_above_200dma: Optional[bool] = None
    vix_level: Optional[float] = None


class OHLCVBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketData(BaseModel):
    ticker: str
    current_price: float
    previous_close: float
    open: float
    day_high: float
    day_low: float
    volume: float
    avg_volume_30d: float
    market_cap: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    beta: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_1y: Optional[float] = None
    return_ytd: Optional[float] = None


class TrendClassification(BaseModel):
    label: str  # strong_uptrend | weak_uptrend | sideways | downtrend
    description: str


class SupportResistanceLevels(BaseModel):
    supports: list[float]
    resistances: list[float]
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None


class TechnicalIndicators(BaseModel):
    ma_10: Optional[float] = None
    ma_20: Optional[float] = None
    ma_50: Optional[float] = None
    ma_100: Optional[float] = None
    ma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    atr: Optional[float] = None
    volume_trend: str = "unknown"  # above_average | below_average | average
    trend: TrendClassification
    is_extended: bool = False
    extension_pct_above_20ma: Optional[float] = None
    extension_pct_above_50ma: Optional[float] = None
    support_resistance: SupportResistanceLevels
    rs_vs_spy: Optional[float] = None
    rs_vs_sector: Optional[float] = None
    technical_score: float = 0.0
