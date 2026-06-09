from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from app.features.feature_snapshot import FeatureSnapshot
from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData
from app.models.market import MarketData, MarketRegimeAssessment, TechnicalIndicators


# Maps the existing 8 StockArchetype constants to the new primary category names
# used in strategy routing and classification configs.
_ARCHETYPE_TO_CATEGORY: dict[str, str] = {
    StockArchetype.HYPER_GROWTH: "HYPER_GROWTH_STORY",
    StockArchetype.PROFITABLE_GROWTH: "PROFITABLE_GROWTH_LEADER",
    StockArchetype.SPECULATIVE_STORY: "SPECULATIVE_CATALYST",
    StockArchetype.DEFENSIVE: "DEFENSIVE_DIVIDEND",
    StockArchetype.COMMODITY_CYCLICAL: "CYCLICAL_RECOVERY",
    StockArchetype.CYCLICAL_GROWTH: "CYCLICAL_RECOVERY",
    StockArchetype.TURNAROUND: "TURNAROUND_RESTRUCTURING",
    StockArchetype.MATURE_VALUE: "MATURE_VALUE",
}


def _earnings_days_away(next_date_str: Optional[str], as_of: str) -> Optional[int]:
    if not next_date_str:
        return None
    try:
        as_of_dt = date.fromisoformat(as_of) if as_of else date.today()
        next_dt = date.fromisoformat(next_date_str[:10])
        delta = (next_dt - as_of_dt).days
        return delta if delta >= 0 else None
    except (ValueError, TypeError):
        return None


def build_feature_snapshot(
    ticker: str,
    price: float,
    technicals: TechnicalIndicators,
    fundamentals: FundamentalData,
    valuation: ValuationData,
    earnings: EarningsData,
    market_data: Optional[MarketData] = None,
    regime_assessment: Optional[MarketRegimeAssessment] = None,
    as_of_date: Optional[str] = None,
) -> FeatureSnapshot:
    """Flatten all computed service outputs into a single FeatureSnapshot.

    Pure adapter — no scoring logic. All None values pass through unchanged
    so the rule engine can detect and penalize missing fields.
    """
    as_of = as_of_date or datetime.today().strftime("%Y-%m-%d")

    days_away = _earnings_days_away(earnings.next_earnings_date, as_of)
    primary_category = _ARCHETYPE_TO_CATEGORY.get(
        fundamentals.archetype, "PROFITABLE_GROWTH_LEADER"
    )
    regime = regime_assessment.regime if regime_assessment else "SIDEWAYS_CHOPPY"
    regime_conf = regime_assessment.confidence if regime_assessment else 0.0

    return FeatureSnapshot(
        # Identity
        ticker=ticker,
        as_of_date=as_of,
        price=price,
        sector=fundamentals.sector,
        market_cap=market_data.market_cap if market_data else None,
        avg_volume=market_data.avg_volume_30d if market_data else None,
        dollar_volume=(
            market_data.avg_volume_30d * price if market_data and market_data.avg_volume_30d else None
        ),
        beta=fundamentals.beta,

        # Moving averages
        sma20_relative=technicals.sma20_relative,
        sma50_relative=technicals.sma50_relative,
        sma200_relative=technicals.sma200_relative,
        ema8_relative=technicals.ema8_relative,
        ema21_relative=technicals.ema21_relative,
        sma20_slope=technicals.sma20_slope,
        sma50_slope=technicals.sma50_slope,
        sma200_slope=technicals.sma200_slope,

        # Momentum
        rsi14=technicals.rsi_14,
        rsi_slope=technicals.rsi_slope,
        macd_histogram=technicals.macd_histogram,
        adx=technicals.adx,
        stochastic_rsi=technicals.stochastic_rsi,

        # Volatility
        atr_percent=technicals.atr_percent,
        bollinger_band_position=technicals.bollinger_band_position,
        bollinger_band_width=technicals.bollinger_band_width,
        volatility_weekly=technicals.volatility_weekly,

        # Performance
        perf_1w=technicals.perf_1w,
        perf_1m=technicals.perf_1m,
        perf_3m=technicals.perf_3m,
        perf_6m=technicals.perf_6m,
        perf_1y=technicals.perf_1y,
        gap_percent=technicals.gap_percent,
        change_from_open_percent=technicals.change_from_open_percent,

        # Volume / accumulation
        obv_trend=technicals.obv_trend,
        ad_trend=technicals.ad_trend,
        chaikin_money_flow=technicals.chaikin_money_flow,
        vwap_deviation=technicals.vwap_deviation,
        volume_dryup_ratio=technicals.volume_dryup_ratio,
        breakout_volume_multiple=technicals.breakout_volume_multiple,
        updown_volume_ratio=technicals.updown_volume_ratio,

        # Range distances
        dist_from_52w_high=technicals.dist_from_52w_high,
        dist_from_52w_low=technicals.dist_from_52w_low,
        dist_from_20d_high=technicals.dist_from_20d_high,

        # Drawdown
        max_drawdown_3m=technicals.max_drawdown_3m,
        max_drawdown_1y=technicals.max_drawdown_1y,

        # Relative strength
        rs_vs_spy=technicals.rs_vs_spy,
        rs_vs_spy_20d=technicals.rs_vs_spy_20d,
        rs_vs_spy_63d=technicals.rs_vs_spy_63d,
        rs_vs_sector_20d=technicals.rs_vs_sector_20d,
        rs_vs_sector_63d=technicals.rs_vs_sector_63d,
        return_pct_rank_20d=technicals.return_pct_rank_20d,
        return_pct_rank_63d=technicals.return_pct_rank_63d,

        # Trend
        trend_label=technicals.trend.label,
        is_extended=technicals.is_extended,
        extension_pct_above_20ma=technicals.extension_pct_above_20ma,
        extension_pct_above_50ma=technicals.extension_pct_above_50ma,

        # Fundamental
        sales_growth_yoy=fundamentals.revenue_growth_yoy,
        sales_growth_qoq=fundamentals.revenue_growth_qoq,
        eps_growth_yoy=fundamentals.eps_growth_yoy,
        eps_growth_next_year=fundamentals.eps_growth_next_year,
        eps_growth_3y=fundamentals.eps_growth_3y,
        eps_growth_5y=fundamentals.eps_growth_5y,
        gross_margin=fundamentals.gross_margin,
        operating_margin=fundamentals.operating_margin,
        net_margin=fundamentals.net_margin,
        free_cash_flow=fundamentals.free_cash_flow,
        roic=fundamentals.roic,
        roe=fundamentals.roe,
        roa=fundamentals.roa,
        debt_to_equity=fundamentals.debt_to_equity,
        current_ratio=fundamentals.current_ratio,
        insider_ownership=fundamentals.insider_ownership,
        institutional_ownership=fundamentals.institutional_ownership,
        short_float=fundamentals.short_float,
        analyst_recommendation=fundamentals.analyst_recommendation,
        analyst_target_price=fundamentals.analyst_target_price,
        target_price_distance=fundamentals.target_price_distance,
        dividend_yield=fundamentals.dividend_yield,

        # Valuation
        forward_pe=valuation.forward_pe,
        trailing_pe=valuation.trailing_pe,
        peg_ratio=valuation.peg_ratio,
        price_to_sales=valuation.price_to_sales,
        ev_to_ebitda=valuation.ev_to_ebitda,
        price_to_fcf=valuation.price_to_fcf,
        fcf_yield=valuation.fcf_yield,
        ev_sales=valuation.ev_sales,

        # Earnings
        beat_rate=earnings.beat_rate,
        avg_eps_surprise_pct=earnings.avg_eps_surprise_pct,
        earnings_days_away=days_away,
        earnings_within_30_days=earnings.within_30_days,

        # Classification context
        primary_category=primary_category,
        market_regime=regime,
        regime_confidence=regime_conf,
    )
