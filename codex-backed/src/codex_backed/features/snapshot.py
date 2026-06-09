from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class FeatureSnapshot:
    """Flat feature snapshot used by config-driven rules."""

    ticker: str
    date: str
    price: float

    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    avg_volume: float | None = None
    dollar_volume: float | None = None
    beta: float | None = None

    sma20_relative: float | None = None
    sma50_relative: float | None = None
    sma200_relative: float | None = None
    ema8_relative: float | None = None
    ema21_relative: float | None = None
    sma20_slope: float | None = None
    sma50_slope: float | None = None
    sma200_slope: float | None = None

    rsi14: float | None = None
    rsi_slope: float | None = None
    macd_histogram: float | None = None
    adx: float | None = None
    stochastic_rsi: float | None = None

    atr_percent: float | None = None
    bollinger_band_position: float | None = None
    bollinger_band_width: float | None = None
    volatility_weekly: float | None = None

    perf_1w: float | None = None
    perf_1m: float | None = None
    perf_3m: float | None = None
    perf_6m: float | None = None
    perf_1y: float | None = None
    gap_percent: float | None = None
    change_from_open_percent: float | None = None

    obv_trend: int | None = None
    ad_trend: int | None = None
    chaikin_money_flow: float | None = None
    vwap_deviation: float | None = None
    volume_dryup_ratio: float | None = None
    breakout_volume_multiple: float | None = None
    updown_volume_ratio: float | None = None

    dist_from_52w_high: float | None = None
    dist_from_52w_low: float | None = None
    dist_from_20d_high: float | None = None
    max_drawdown_3m: float | None = None
    max_drawdown_1y: float | None = None

    rs_vs_spy: float | None = None
    rs_vs_spy_20d: float | None = None
    rs_vs_spy_63d: float | None = None
    rs_vs_sector_20d: float | None = None
    rs_vs_sector_63d: float | None = None
    return_pct_rank_20d: float | None = None
    return_pct_rank_63d: float | None = None

    trend_label: str = "sideways"
    is_extended: bool = False
    extension_pct_above_20ma: float | None = None
    extension_pct_above_50ma: float | None = None

    sales_growth_yoy: float | None = None
    sales_growth_qoq: float | None = None
    eps_growth_yoy: float | None = None
    eps_growth_next_year: float | None = None
    eps_growth_3y: float | None = None
    eps_growth_5y: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    free_cash_flow: float | None = None
    roic: float | None = None
    roe: float | None = None
    roa: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    insider_ownership: float | None = None
    institutional_ownership: float | None = None
    short_float: float | None = None
    analyst_recommendation: float | None = None
    analyst_target_price: float | None = None
    target_price_distance: float | None = None
    dividend_yield: float | None = None

    forward_pe: float | None = None
    trailing_pe: float | None = None
    peg_ratio: float | None = None
    price_to_sales: float | None = None
    ev_to_ebitda: float | None = None
    price_to_fcf: float | None = None
    fcf_yield: float | None = None
    ev_sales: float | None = None

    beat_rate: float | None = None
    avg_eps_surprise_pct: float | None = None
    earnings_days_away: int | None = None
    earnings_within_30_days: bool = False

    primary_category: str = "PROFITABLE_GROWTH_LEADER"
    secondary_tags: list[str] = field(default_factory=list)
    archetype: str | None = None
    market_regime: str = "SIDEWAYS_CHOPPY"
    regime_confidence: float = 0.0
    selected_setup: str | None = None

    sc_momentum: float | None = None
    sc_trend: float | None = None
    sc_entry_timing: float | None = None
    sc_volume_accumulation: float | None = None
    sc_volatility_risk: float | None = None
    sc_relative_strength: float | None = None
    sc_growth: float | None = None
    sc_valuation: float | None = None
    sc_quality: float | None = None
    sc_ownership: float | None = None
    sc_catalyst: float | None = None

    entry_score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

