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
    # --- Existing moving averages ---
    ma_10: Optional[float] = None
    ma_20: Optional[float] = None
    ma_50: Optional[float] = None
    ma_100: Optional[float] = None
    ma_200: Optional[float] = None

    # --- EMA relatives (% deviation of price from EMA) ---
    ema8_relative: Optional[float] = None
    ema21_relative: Optional[float] = None

    # --- SMA relatives (% deviation of price from SMA) ---
    sma20_relative: Optional[float] = None
    sma50_relative: Optional[float] = None
    sma200_relative: Optional[float] = None

    # --- SMA slopes (5-bar % change) ---
    sma20_slope: Optional[float] = None
    sma50_slope: Optional[float] = None
    sma200_slope: Optional[float] = None

    # --- Momentum indicators ---
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    adx: Optional[float] = None
    stochastic_rsi: Optional[float] = None

    # --- Volatility ---
    atr: Optional[float] = None
    atr_percent: Optional[float] = None
    bollinger_band_position: Optional[float] = None
    bollinger_band_width: Optional[float] = None
    volatility_weekly: Optional[float] = None
    volatility_monthly: Optional[float] = None

    # --- Performance periods (% returns) ---
    perf_1w: Optional[float] = None
    perf_1m: Optional[float] = None
    perf_3m: Optional[float] = None
    perf_6m: Optional[float] = None
    perf_ytd: Optional[float] = None
    perf_1y: Optional[float] = None
    perf_3y: Optional[float] = None
    perf_5y: Optional[float] = None

    # --- Intraday metrics ---
    gap_percent: Optional[float] = None
    change_from_open_percent: Optional[float] = None

    # --- Range distances (% from price to range boundary) ---
    dist_from_20d_high: Optional[float] = None
    dist_from_20d_low: Optional[float] = None
    dist_from_50d_high: Optional[float] = None
    dist_from_50d_low: Optional[float] = None
    dist_from_52w_high: Optional[float] = None
    dist_from_52w_low: Optional[float] = None
    dist_from_ath: Optional[float] = None
    dist_from_atl: Optional[float] = None

    # --- Volume trend ---
    volume_trend: str = "unknown"  # above_average | below_average | average

    # --- Volume / accumulation indicators (Story 2) ---
    obv_trend: int = 0               # +1 rising, -1 falling, 0 flat
    ad_trend: int = 0                # +1 rising, -1 falling, 0 flat
    chaikin_money_flow: Optional[float] = None
    vwap_deviation: Optional[float] = None          # % deviation from 20D VWAP
    anchored_vwap_deviation: Optional[float] = None # % deviation from earnings-anchored VWAP
    volume_dryup_ratio: Optional[float] = None      # recent vol / prior vol; < 1 = drying up
    breakout_volume_multiple: Optional[float] = None  # current vol / 20D avg vol
    updown_volume_ratio: Optional[float] = None     # up-day vol / down-day vol

    # --- Trend / extension ---
    trend: TrendClassification = TrendClassification(label="sideways", description="No clear trend")
    is_extended: bool = False
    extension_pct_above_20ma: Optional[float] = None
    extension_pct_above_50ma: Optional[float] = None

    # --- Support / resistance ---
    support_resistance: SupportResistanceLevels = SupportResistanceLevels(supports=[], resistances=[])

    # --- Relative strength ---
    rs_vs_spy: Optional[float] = None
    rs_vs_qqq: Optional[float] = None
    rs_vs_sector: Optional[float] = None

    # --- Return percentile ranks (Story 3) ---
    return_pct_rank_20d: Optional[float] = None
    return_pct_rank_63d: Optional[float] = None
    return_pct_rank_126d: Optional[float] = None
    return_pct_rank_252d: Optional[float] = None

    # --- Drawdown metrics (Story 3) ---
    max_drawdown_3m: Optional[float] = None
    max_drawdown_1y: Optional[float] = None

    # --- Gap / post-earnings (Story 3) ---
    gap_filled: bool = False
    post_earnings_drift: Optional[float] = None

    # --- Composite score ---
    technical_score: float = 0.0
