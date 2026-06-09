from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class FeatureSnapshot(BaseModel):
    """Flat normalized dict of every feature the rule engine can evaluate.

    Fields are purposefully kept optional so the rule engine can detect
    missing data and apply confidence penalties rather than crashing.
    """

    # --- Identity ---
    ticker: str
    as_of_date: str = ""
    price: float = 0.0
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    avg_volume: Optional[float] = None
    dollar_volume: Optional[float] = None
    beta: Optional[float] = None

    # --- Moving average relatives (% deviation of price from MA) ---
    sma20_relative: Optional[float] = None
    sma50_relative: Optional[float] = None
    sma200_relative: Optional[float] = None
    ema8_relative: Optional[float] = None
    ema21_relative: Optional[float] = None

    # --- MA slopes (5-bar % change) ---
    sma20_slope: Optional[float] = None
    sma50_slope: Optional[float] = None
    sma200_slope: Optional[float] = None

    # --- Momentum indicators ---
    rsi14: Optional[float] = None
    rsi_slope: Optional[float] = None
    macd_histogram: Optional[float] = None
    adx: Optional[float] = None
    stochastic_rsi: Optional[float] = None

    # --- Volatility ---
    atr_percent: Optional[float] = None
    bollinger_band_position: Optional[float] = None
    bollinger_band_width: Optional[float] = None
    volatility_weekly: Optional[float] = None

    # --- Performance periods (%) ---
    perf_1w: Optional[float] = None
    perf_1m: Optional[float] = None
    perf_3m: Optional[float] = None
    perf_6m: Optional[float] = None
    perf_1y: Optional[float] = None
    gap_percent: Optional[float] = None
    change_from_open_percent: Optional[float] = None

    # --- Volume / accumulation ---
    obv_trend: Optional[int] = None
    ad_trend: Optional[int] = None
    chaikin_money_flow: Optional[float] = None
    vwap_deviation: Optional[float] = None
    volume_dryup_ratio: Optional[float] = None
    breakout_volume_multiple: Optional[float] = None
    updown_volume_ratio: Optional[float] = None

    # --- Range distances ---
    dist_from_52w_high: Optional[float] = None
    dist_from_52w_low: Optional[float] = None
    dist_from_20d_high: Optional[float] = None

    # --- Drawdown ---
    max_drawdown_3m: Optional[float] = None
    max_drawdown_1y: Optional[float] = None

    # --- Relative strength ---
    rs_vs_spy: Optional[float] = None
    rs_vs_spy_20d: Optional[float] = None
    rs_vs_spy_63d: Optional[float] = None
    rs_vs_sector_20d: Optional[float] = None
    rs_vs_sector_63d: Optional[float] = None
    return_pct_rank_20d: Optional[float] = None
    return_pct_rank_63d: Optional[float] = None

    # --- Trend ---
    trend_label: str = "sideways"
    is_extended: bool = False
    extension_pct_above_20ma: Optional[float] = None
    extension_pct_above_50ma: Optional[float] = None

    # --- Fundamental (mapped from FundamentalData) ---
    sales_growth_yoy: Optional[float] = None
    sales_growth_qoq: Optional[float] = None
    eps_growth_yoy: Optional[float] = None
    eps_growth_next_year: Optional[float] = None
    eps_growth_3y: Optional[float] = None
    eps_growth_5y: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    free_cash_flow: Optional[float] = None
    roic: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    insider_ownership: Optional[float] = None
    institutional_ownership: Optional[float] = None
    short_float: Optional[float] = None
    analyst_recommendation: Optional[float] = None
    analyst_target_price: Optional[float] = None
    target_price_distance: Optional[float] = None
    dividend_yield: Optional[float] = None

    # --- Valuation ---
    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    price_to_fcf: Optional[float] = None
    fcf_yield: Optional[float] = None
    ev_sales: Optional[float] = None

    # --- Earnings ---
    beat_rate: Optional[float] = None
    avg_eps_surprise_pct: Optional[float] = None
    earnings_days_away: Optional[int] = None
    earnings_within_30_days: bool = False

    # --- Classification context (set by feature builder / engine) ---
    primary_category: str = "PROFITABLE_GROWTH_LEADER"
    secondary_tags: list[str] = []
    market_regime: str = "SIDEWAYS_CHOPPY"
    regime_confidence: float = 0.0
    selected_setup: Optional[str] = None

    # --- Populated by strategy engine during scoring ---
    strategy_score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        """Return flat dict for rule engine evaluation. Includes None values."""
        return self.model_dump()
