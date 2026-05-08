"""
Signal Card Scoring Engine (Story 6)

Implements 11 signal card scorers that replace the old composite score as the
primary output. Each scorer returns a SignalCard with a 0–100 score, label,
explanation, top positives/negatives, and missing-data warnings.

Missing inputs are handled gracefully: each input is optional; missing fields
are simply excluded from scoring and noted in missing_data_warnings.
"""
from __future__ import annotations

from typing import Optional

from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.market import TechnicalIndicators
from app.models.news import NewsSummary
from app.models.response import SignalCard, SignalCardLabel, SignalCards


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _score_to_card(
    name: str,
    raw: float,
    total_possible: float,
    positives: list[str],
    negatives: list[str],
    warnings: list[str],
    explanation_parts: list[str],
) -> SignalCard:
    if total_possible > 0:
        score = _clamp(raw / total_possible * 100)
    else:
        score = 50.0
    label = SignalCardLabel.from_score(score)
    explanation = " ".join(explanation_parts) if explanation_parts else f"{name.replace('_', ' ').title()} analysis."
    return SignalCard(
        name=name,
        score=round(score, 1),
        label=label,
        explanation=explanation,
        top_positives=positives[:5],
        top_negatives=negatives[:5],
        missing_data_warnings=warnings,
    )


# ---------------------------------------------------------------------------
# 1. Momentum
# ---------------------------------------------------------------------------

def score_momentum(ti: TechnicalIndicators) -> SignalCard:
    """Score based on price momentum: perf periods, MACD, RSI trend, SMA position."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Performance periods (1W, 1M, 3M)
    for attr, weight, label in [
        ("perf_1w", 10, "1-week"), ("perf_1m", 15, "1-month"), ("perf_3m", 20, "3-month"),
    ]:
        val = getattr(ti, attr, None)
        if val is not None:
            total += weight
            if val > 0:
                pts = min(weight, weight * (1 + val / 20))
                raw += pts
                pos.append(f"{label} perf +{val:.1f}%")
            else:
                neg.append(f"{label} perf {val:.1f}%")
        else:
            warn.append(f"{label} performance unavailable")

    # MACD histogram
    hist = ti.macd_histogram
    if hist is not None:
        total += 15
        if hist > 0:
            raw += min(15, 7.5 + hist * 5)
            pos.append("MACD histogram positive")
        else:
            neg.append("MACD histogram negative")
    else:
        warn.append("MACD unavailable")

    # RSI 14
    rsi = ti.rsi_14
    if rsi is not None:
        total += 15
        if 45 <= rsi <= 65:
            raw += 15
            pos.append(f"RSI {rsi:.0f} — momentum sweet spot")
        elif 65 < rsi <= 75:
            raw += 9
        elif rsi > 75:
            raw += 4
            neg.append(f"RSI {rsi:.0f} — overbought")
        elif 35 <= rsi < 45:
            raw += 6
        else:
            raw += 0
            neg.append(f"RSI {rsi:.0f} — weak / oversold")
    else:
        warn.append("RSI unavailable")

    # RSI slope (improving vs deteriorating momentum)
    rsi_slope = ti.rsi_slope
    if rsi_slope is not None:
        total += 10
        if rsi_slope >= 5:
            raw += 10
            pos.append(f"RSI slope +{rsi_slope:.1f} — momentum accelerating")
        elif rsi_slope >= 1:
            raw += 7
            pos.append(f"RSI slope +{rsi_slope:.1f} — momentum improving")
        elif rsi_slope >= -1:
            raw += 5
        elif rsi_slope >= -5:
            raw += 2
            neg.append(f"RSI slope {rsi_slope:.1f} — momentum fading")
        else:
            neg.append(f"RSI slope {rsi_slope:.1f} — momentum deteriorating")
    else:
        warn.append("RSI slope unavailable")

    # Price above EMA8 and EMA21
    for attr, label, weight in [("ema8_relative", "EMA8", 10), ("ema21_relative", "EMA21", 10)]:
        val = getattr(ti, attr, None)
        if val is not None:
            total += weight
            if val > 0:
                raw += weight
                pos.append(f"Price above {label}")
            else:
                neg.append(f"Price below {label}")
        else:
            warn.append(f"{label} relative unavailable")

    parts = [f"Momentum score driven by short- to medium-term price performance and MACD."]
    return _score_to_card("momentum", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 2. Trend
# ---------------------------------------------------------------------------

def score_trend(ti: TechnicalIndicators) -> SignalCard:
    """Score based on trend structure: SMA stack, slopes, ADX."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Price vs SMAs (20, 50, 200)
    for attr, label, weight in [
        ("sma20_relative", "SMA20", 15),
        ("sma50_relative", "SMA50", 15),
        ("sma200_relative", "SMA200", 20),
    ]:
        val = getattr(ti, attr, None)
        if val is not None:
            total += weight
            if val > 0:
                raw += weight
                pos.append(f"Price above {label} (+{val*100:.1f}%)")
            else:
                neg.append(f"Price below {label} ({val*100:.1f}%)")
        else:
            warn.append(f"{label} relative unavailable")

    # SMA slopes
    for attr, label, weight in [
        ("sma20_slope", "SMA20 slope", 10),
        ("sma50_slope", "SMA50 slope", 15),
    ]:
        val = getattr(ti, attr, None)
        if val is not None:
            total += weight
            if val > 0:
                raw += weight
                pos.append(f"{label} rising")
            else:
                neg.append(f"{label} falling")
        else:
            warn.append(f"{label} unavailable")

    # ADX (trend strength)
    adx = ti.adx
    if adx is not None:
        total += 15
        if adx >= 30:
            raw += 15
            pos.append(f"ADX {adx:.0f} — strong trend")
        elif adx >= 20:
            raw += 10
        else:
            raw += 5
            neg.append(f"ADX {adx:.0f} — weak trend")
    else:
        warn.append("ADX unavailable")

    # 6M and 1Y performance (trend confirmation)
    for attr, label, weight in [("perf_6m", "6-month", 5), ("perf_1y", "1-year", 5)]:
        val = getattr(ti, attr, None)
        if val is not None:
            total += weight
            if val > 0:
                raw += weight
                pos.append(f"{label} trend positive (+{val:.1f}%)")
            else:
                neg.append(f"{label} trend negative ({val:.1f}%)")
        else:
            warn.append(f"{label} performance unavailable")

    parts = ["Trend score reflects SMA stack alignment, slope direction, and ADX trend strength."]
    return _score_to_card("trend", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 3. Entry Timing
# ---------------------------------------------------------------------------

def score_entry_timing(ti: TechnicalIndicators) -> SignalCard:
    """Score based on entry quality: RSI, StochRSI, VWAP, Bollinger, gap."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # RSI: 45–65 is ideal entry zone
    rsi = ti.rsi_14
    if rsi is not None:
        total += 25
        if 45 <= rsi <= 65:
            raw += 25
            pos.append(f"RSI {rsi:.0f} — ideal entry zone (45–65)")
        elif 35 <= rsi < 45:
            raw += 18
            pos.append(f"RSI {rsi:.0f} — mild pullback, decent entry")
        elif 65 < rsi <= 70:
            raw += 15
        elif rsi > 70:
            raw += 5
            neg.append(f"RSI {rsi:.0f} — overbought, extended entry")
        else:
            raw += 5
            neg.append(f"RSI {rsi:.0f} — oversold / momentum breakdown")
    else:
        warn.append("RSI unavailable")

    # Stochastic RSI
    srsi = ti.stochastic_rsi
    if srsi is not None:
        total += 15
        if 0.2 <= srsi <= 0.6:
            raw += 15
            pos.append("StochRSI in healthy range")
        elif srsi > 0.8:
            raw += 5
            neg.append("StochRSI overbought")
        elif srsi < 0.2:
            raw += 8
        else:
            raw += 10
    else:
        warn.append("StochRSI unavailable")

    # VWAP position
    vwap_dev = ti.vwap_deviation
    if vwap_dev is not None:
        total += 15
        if 0 <= vwap_dev <= 0.03:
            raw += 15
            pos.append("Price near/above VWAP — institutional support")
        elif vwap_dev > 0.03:
            raw += 8
            neg.append("Price extended above VWAP")
        else:
            raw += 5
            neg.append("Price below VWAP")
    else:
        warn.append("VWAP deviation unavailable")

    # Bollinger Band position (0 = lower band, 1 = upper band; 0.3–0.7 is healthy)
    bb_pos = ti.bollinger_band_position
    if bb_pos is not None:
        total += 10
        if 0.3 <= bb_pos <= 0.7:
            raw += 10
            pos.append("Price within Bollinger Band midrange")
        elif bb_pos > 0.85:
            raw += 3
            neg.append("Price at upper Bollinger Band — extended")
        elif bb_pos < 0.15:
            raw += 5
        else:
            raw += 7
    else:
        warn.append("Bollinger Band position unavailable")

    # EMA8 relative (near-term support)
    ema8 = ti.ema8_relative
    if ema8 is not None:
        total += 10
        if 0 <= ema8 <= 0.03:
            raw += 10
            pos.append("Price close to EMA8 — tight entry")
        elif ema8 > 0.03:
            raw += 5
            neg.append("Price extended above EMA8")
        else:
            raw += 3
    else:
        warn.append("EMA8 relative unavailable")

    # RSI slope (entry is better when momentum is recovering/building)
    rsi_slope = ti.rsi_slope
    if rsi_slope is not None:
        total += 10
        if rsi_slope >= 3:
            raw += 10
            pos.append(f"RSI slope +{rsi_slope:.1f} — momentum building, good entry")
        elif rsi_slope >= 0:
            raw += 7
        elif rsi_slope >= -3:
            raw += 3
            neg.append(f"RSI slope {rsi_slope:.1f} — momentum fading at entry")
        else:
            raw += 1
            neg.append(f"RSI slope {rsi_slope:.1f} — avoid entry, momentum declining")
    else:
        warn.append("RSI slope unavailable")

    # Gap %: small gap up is fine, large gap up is extended
    gap = ti.gap_percent
    if gap is not None:
        total += 5
        if -1 <= gap <= 1:
            raw += 5
        elif gap > 3:
            raw += 1
            neg.append(f"Large gap up {gap:.1f}% — risky entry")
        else:
            raw += 3
    else:
        warn.append("Gap% unavailable")

    parts = ["Entry timing measures RSI zone, RSI slope, StochRSI, VWAP support, and Bollinger Band position."]
    return _score_to_card("entry_timing", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 4. Volume / Accumulation
# ---------------------------------------------------------------------------

def score_volume_accumulation(ti: TechnicalIndicators) -> SignalCard:
    """Score based on OBV, A/D, CMF, relative volume, up/down ratio."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # OBV trend
    obv = ti.obv_trend
    if obv is not None:
        total += 20
        if obv == 1:
            raw += 20
            pos.append("OBV rising — accumulation confirmed")
        elif obv == -1:
            neg.append("OBV falling — distribution signal")
        else:
            raw += 10

    # A/D trend
    ad = ti.ad_trend
    if ad is not None:
        total += 15
        if ad == 1:
            raw += 15
            pos.append("A/D line rising")
        elif ad == -1:
            neg.append("A/D line falling — institutional selling")
        else:
            raw += 7

    # Chaikin Money Flow
    cmf = ti.chaikin_money_flow
    if cmf is not None:
        total += 20
        if cmf > 0.1:
            raw += 20
            pos.append(f"CMF {cmf:.2f} — strong buying pressure")
        elif cmf > 0:
            raw += 12
            pos.append(f"CMF {cmf:.2f} — mild buying pressure")
        elif cmf < -0.1:
            neg.append(f"CMF {cmf:.2f} — distribution")
        else:
            raw += 5
    else:
        warn.append("Chaikin Money Flow unavailable")

    # Breakout volume multiple
    bvol = ti.breakout_volume_multiple
    if bvol is not None:
        total += 20
        if bvol >= 1.5:
            raw += 20
            pos.append(f"Volume {bvol:.1f}× avg — breakout confirmation")
        elif bvol >= 1.0:
            raw += 12
        else:
            raw += 5
            neg.append(f"Volume {bvol:.1f}× avg — below average")
    else:
        warn.append("Breakout volume multiple unavailable")

    # Up/down volume ratio
    udv = ti.updown_volume_ratio
    if udv is not None:
        total += 15
        if udv >= 1.3:
            raw += 15
            pos.append(f"Up/down volume ratio {udv:.1f} — buyers in control")
        elif udv >= 1.0:
            raw += 10
        else:
            neg.append(f"Up/down volume ratio {udv:.1f} — sellers dominant")
    else:
        warn.append("Up/down volume ratio unavailable")

    # Volume dry-up (low volume on pullback = bullish)
    vdu = ti.volume_dryup_ratio
    if vdu is not None:
        total += 10
        if vdu < 0.7:
            raw += 10
            pos.append("Volume dry-up on pullback — healthy consolidation")
        elif vdu > 1.2:
            raw += 3
            neg.append("Heavy volume on pullback — distribution concern")
        else:
            raw += 6
    else:
        warn.append("Volume dry-up ratio unavailable")

    parts = ["Volume/accumulation score measures institutional buying pressure via OBV, CMF, and volume ratios."]
    return _score_to_card("volume_accumulation", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 5. Volatility / Risk
# ---------------------------------------------------------------------------

def score_volatility_risk(ti: TechnicalIndicators) -> SignalCard:
    """Score based on drawdown, ATR%, weekly vol, beta, distance from highs."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Max drawdown 3M (less negative = better)
    dd3m = ti.max_drawdown_3m
    if dd3m is not None:
        total += 25
        if dd3m >= -5:
            raw += 25
            pos.append(f"3M max drawdown {dd3m:.1f}% — contained")
        elif dd3m >= -10:
            raw += 18
        elif dd3m >= -20:
            raw += 10
            neg.append(f"3M drawdown {dd3m:.1f}% — notable")
        else:
            raw += 3
            neg.append(f"3M drawdown {dd3m:.1f}% — severe")
    else:
        warn.append("3M drawdown unavailable")

    # Max drawdown 1Y
    dd1y = ti.max_drawdown_1y
    if dd1y is not None:
        total += 15
        if dd1y >= -10:
            raw += 15
        elif dd1y >= -25:
            raw += 8
        else:
            raw += 2
            neg.append(f"1Y drawdown {dd1y:.1f}% — high risk")
    else:
        warn.append("1Y drawdown unavailable")

    # ATR%
    atr_pct = ti.atr_percent
    if atr_pct is not None:
        total += 20
        if atr_pct <= 1.5:
            raw += 20
            pos.append(f"ATR {atr_pct:.1f}% — low intraday risk")
        elif atr_pct <= 3.0:
            raw += 13
        elif atr_pct <= 5.0:
            raw += 7
            neg.append(f"ATR {atr_pct:.1f}% — elevated volatility")
        else:
            raw += 2
            neg.append(f"ATR {atr_pct:.1f}% — very high volatility")
    else:
        warn.append("ATR% unavailable")

    # Weekly volatility
    wvol = ti.volatility_weekly
    if wvol is not None:
        total += 15
        if wvol <= 0.20:
            raw += 15
            pos.append(f"Weekly vol {wvol*100:.0f}% ann — moderate")
        elif wvol <= 0.40:
            raw += 8
        else:
            raw += 2
            neg.append(f"Weekly vol {wvol*100:.0f}% ann — high")
    else:
        warn.append("Weekly volatility unavailable")

    # Beta (not on TechnicalIndicators — gracefully skip)
    beta = getattr(ti, "beta", None)
    if beta is not None:
        total += 15
        if 0.5 <= beta <= 1.3:
            raw += 15
            pos.append(f"Beta {beta:.1f} — market-aligned risk")
        elif beta <= 1.8:
            raw += 8
        else:
            raw += 3
            neg.append(f"Beta {beta:.1f} — high market sensitivity")
    else:
        warn.append("Beta unavailable")

    # Distance from 52W high (far from high = survived big drawdown)
    d52h = ti.dist_from_52w_high
    if d52h is not None:
        total += 10
        if d52h >= -5:
            raw += 10
            pos.append("Near 52-week high — relative strength")
        elif d52h >= -15:
            raw += 6
        else:
            raw += 2
            neg.append(f"{abs(d52h):.0f}% below 52W high")
    else:
        warn.append("52W high distance unavailable")

    parts = ["Volatility/risk score rewards low drawdown, contained ATR, and moderate beta."]
    return _score_to_card("volatility_risk", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 6. Relative Strength
# ---------------------------------------------------------------------------

def score_relative_strength(ti: TechnicalIndicators) -> SignalCard:
    """Score based on RS vs QQQ, return percentile ranks."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # RS vs QQQ
    rs_qqq = ti.rs_vs_qqq
    if rs_qqq is not None:
        total += 30
        if rs_qqq >= 5:
            raw += 30
            pos.append(f"RS vs QQQ +{rs_qqq:.1f}% — strong outperformance")
        elif rs_qqq >= 0:
            raw += 18
            pos.append(f"RS vs QQQ +{rs_qqq:.1f}%")
        elif rs_qqq >= -5:
            raw += 10
            neg.append(f"RS vs QQQ {rs_qqq:.1f}%")
        else:
            neg.append(f"RS vs QQQ {rs_qqq:.1f}% — underperforming badly")
    else:
        warn.append("RS vs QQQ unavailable (QQQ benchmark data not fetched)")

    # Return percentile ranks
    for attr, label, weight in [
        ("return_pct_rank_20d", "20D", 15),
        ("return_pct_rank_63d", "63D", 20),
        ("return_pct_rank_126d", "126D", 15),
        ("return_pct_rank_252d", "252D", 20),
    ]:
        val = getattr(ti, attr, None)
        if val is not None:
            total += weight
            if val >= 75:
                raw += weight
                pos.append(f"{label} return rank {val:.0f}th percentile — top quartile")
            elif val >= 50:
                raw += weight * 0.65
            elif val >= 25:
                raw += weight * 0.35
                neg.append(f"{label} return rank {val:.0f}th percentile")
            else:
                neg.append(f"{label} return rank {val:.0f}th percentile — bottom quartile")
        else:
            warn.append(f"{label} return percentile rank unavailable")

    parts = ["Relative strength score compares returns vs QQQ and measures return percentile ranks."]
    return _score_to_card("relative_strength", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 7. Growth
# ---------------------------------------------------------------------------

def score_growth(fd: FundamentalData, earnings: EarningsData) -> SignalCard:
    """Score based on EPS/revenue growth rates and earnings surprise history."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Revenue growth YoY
    rev_yoy = fd.revenue_growth_yoy
    if rev_yoy is not None:
        total += 20
        if rev_yoy >= 0.20:
            raw += 20
            pos.append(f"Revenue growth {rev_yoy*100:.0f}% YoY — strong")
        elif rev_yoy >= 0.10:
            raw += 14
            pos.append(f"Revenue growth {rev_yoy*100:.0f}% YoY")
        elif rev_yoy >= 0:
            raw += 8
        else:
            neg.append(f"Revenue declining {rev_yoy*100:.0f}% YoY")
    else:
        warn.append("Revenue growth YoY unavailable")

    # QoQ revenue growth (acceleration signal)
    rev_qoq = fd.revenue_growth_qoq
    if rev_qoq is not None:
        total += 10
        if rev_qoq >= 0.05:
            raw += 10
            pos.append(f"Revenue accelerating QoQ +{rev_qoq*100:.1f}%")
        elif rev_qoq >= 0:
            raw += 7
        else:
            neg.append(f"Revenue decelerating QoQ {rev_qoq*100:.1f}%")
    else:
        warn.append("QoQ revenue growth unavailable")

    # EPS growth YoY
    eps_yoy = fd.eps_growth_yoy
    if eps_yoy is not None:
        total += 20
        if eps_yoy >= 0.20:
            raw += 20
            pos.append(f"EPS growth {eps_yoy*100:.0f}% YoY")
        elif eps_yoy >= 0.10:
            raw += 13
        elif eps_yoy >= 0:
            raw += 8
        else:
            neg.append(f"EPS declining {eps_yoy*100:.0f}% YoY")
    else:
        warn.append("EPS growth YoY unavailable")

    # EPS next year estimate
    eps_ny = fd.eps_growth_next_year
    if eps_ny is not None:
        total += 10
        if eps_ny >= 0.15:
            raw += 10
            pos.append(f"EPS next year est. +{eps_ny*100:.0f}%")
        elif eps_ny >= 0:
            raw += 6
        else:
            neg.append(f"EPS next year est. {eps_ny*100:.0f}%")
    else:
        warn.append("EPS next-year estimate unavailable")

    # Sales growth TTM
    sg_ttm = fd.sales_growth_ttm
    if sg_ttm is not None:
        total += 10
        if sg_ttm >= 0.15:
            raw += 10
            pos.append(f"Sales TTM growth {sg_ttm*100:.0f}%")
        elif sg_ttm >= 0:
            raw += 6
        else:
            neg.append(f"Sales TTM {sg_ttm*100:.0f}%")
    else:
        warn.append("Sales growth TTM unavailable")

    # Multi-year EPS durability (3Y and 5Y EPS growth)
    eps_3y = fd.eps_growth_3y
    if eps_3y is not None:
        total += 10
        if eps_3y >= 0.15:
            raw += 10
            pos.append(f"EPS 3Y CAGR {eps_3y*100:.0f}% — durable growth")
        elif eps_3y >= 0.05:
            raw += 6
        elif eps_3y >= 0:
            raw += 3
        else:
            neg.append(f"EPS 3Y CAGR {eps_3y*100:.0f}% — declining trend")
    else:
        warn.append("EPS 3-year growth unavailable")

    # Multi-year sales durability (3Y sales growth)
    sg_3y = fd.sales_growth_3y
    if sg_3y is not None:
        total += 8
        if sg_3y >= 0.10:
            raw += 8
            pos.append(f"Sales 3Y CAGR {sg_3y*100:.0f}% — durable revenue")
        elif sg_3y >= 0.05:
            raw += 5
        elif sg_3y >= 0:
            raw += 2
        else:
            neg.append(f"Sales 3Y CAGR {sg_3y*100:.0f}%")
    else:
        warn.append("Sales 3-year growth unavailable")

    # Forward EPS durability (next 5Y)
    eps_next5y = fd.eps_growth_next_5y
    if eps_next5y is not None:
        total += 7
        if eps_next5y >= 0.15:
            raw += 7
            pos.append(f"EPS next 5Y est. {eps_next5y*100:.0f}% — strong forward growth")
        elif eps_next5y >= 0.08:
            raw += 4
        else:
            raw += 1
            neg.append(f"EPS next 5Y est. {eps_next5y*100:.0f}% — weak outlook")
    else:
        warn.append("EPS next-5-year estimate unavailable")

    # Earnings beat rate
    beat_rate = earnings.beat_rate
    if beat_rate is not None:
        total += 20
        if beat_rate >= 0.75:
            raw += 20
            pos.append(f"Earnings beat rate {beat_rate*100:.0f}% — consistent")
        elif beat_rate >= 0.5:
            raw += 12
        else:
            neg.append(f"Beat rate {beat_rate*100:.0f}% — misses common")
    else:
        warn.append("Earnings beat rate unavailable")

    # Avg earnings surprise
    surprise = earnings.avg_eps_surprise_pct
    if surprise is not None:
        total += 10
        if surprise >= 5:
            raw += 10
            pos.append(f"Avg earnings surprise +{surprise:.1f}%")
        elif surprise >= 2:
            raw += 7
        elif surprise >= 0:
            raw += 4
        else:
            neg.append(f"Avg earnings surprise {surprise:.1f}% — misses")
    else:
        warn.append("Avg earnings surprise unavailable")

    parts = ["Growth card assesses EPS/revenue growth rates and earnings beat consistency."]
    return _score_to_card("growth", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 8. Valuation
# ---------------------------------------------------------------------------

def score_valuation(vd: ValuationData) -> SignalCard:
    """Score based on P/E, PEG, P/S, EV/EBITDA, P/FCF, EV/Sales."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Forward P/E
    fpe = vd.forward_pe
    if fpe is not None:
        total += 20
        if fpe <= 15:
            raw += 20
            pos.append(f"Forward P/E {fpe:.1f} — attractive")
        elif fpe <= 25:
            raw += 13
        elif fpe <= 40:
            raw += 7
            neg.append(f"Forward P/E {fpe:.1f} — elevated")
        else:
            raw += 2
            neg.append(f"Forward P/E {fpe:.1f} — expensive")
    else:
        warn.append("Forward P/E unavailable")

    # PEG ratio
    peg = vd.peg_ratio
    if peg is not None:
        total += 20
        if peg <= 1.0:
            raw += 20
            pos.append(f"PEG {peg:.2f} — undervalued vs growth")
        elif peg <= 1.5:
            raw += 14
            pos.append(f"PEG {peg:.2f} — reasonable")
        elif peg <= 2.5:
            raw += 8
            neg.append(f"PEG {peg:.2f} — slightly rich")
        else:
            raw += 2
            neg.append(f"PEG {peg:.2f} — overvalued vs growth")
    else:
        warn.append("PEG ratio unavailable")

    # P/S ratio
    ps = vd.price_to_sales
    if ps is not None:
        total += 15
        if ps <= 3:
            raw += 15
            pos.append(f"P/S {ps:.1f} — value territory")
        elif ps <= 8:
            raw += 9
        elif ps <= 15:
            raw += 5
            neg.append(f"P/S {ps:.1f} — premium")
        else:
            raw += 1
            neg.append(f"P/S {ps:.1f} — very expensive")
    else:
        warn.append("Price/Sales unavailable")

    # EV/EBITDA
    ev_ebitda = vd.ev_to_ebitda
    if ev_ebitda is not None:
        total += 15
        if ev_ebitda <= 12:
            raw += 15
            pos.append(f"EV/EBITDA {ev_ebitda:.1f} — attractive")
        elif ev_ebitda <= 20:
            raw += 9
        elif ev_ebitda <= 35:
            raw += 4
            neg.append(f"EV/EBITDA {ev_ebitda:.1f} — elevated")
        else:
            raw += 1
            neg.append(f"EV/EBITDA {ev_ebitda:.1f} — expensive")
    else:
        warn.append("EV/EBITDA unavailable")

    # FCF yield
    fcfy = vd.fcf_yield
    if fcfy is not None:
        total += 15
        if fcfy >= 5:
            raw += 15
            pos.append(f"FCF yield {fcfy:.1f}% — strong cash return")
        elif fcfy >= 2:
            raw += 9
        elif fcfy >= 0:
            raw += 4
        else:
            neg.append("Negative FCF yield")
    else:
        warn.append("FCF yield unavailable")

    # EV/Sales
    evs = vd.ev_sales
    if evs is not None:
        total += 15
        if evs <= 3:
            raw += 15
            pos.append(f"EV/Sales {evs:.1f} — low multiple")
        elif evs <= 8:
            raw += 9
        elif evs <= 15:
            raw += 4
            neg.append(f"EV/Sales {evs:.1f} — premium multiple")
        else:
            raw += 1
            neg.append(f"EV/Sales {evs:.1f} — very expensive")
    else:
        warn.append("EV/Sales unavailable")

    parts = ["Valuation card scores multiple metrics: P/E, PEG, P/S, EV/EBITDA, FCF yield, EV/Sales."]
    return _score_to_card("valuation", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 9. Quality
# ---------------------------------------------------------------------------

def score_quality(fd: FundamentalData) -> SignalCard:
    """Score based on margins, ROE, ROIC, ROA, balance sheet health."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Gross margin
    gm = fd.gross_margin
    if gm is not None:
        total += 15
        if gm >= 0.50:
            raw += 15
            pos.append(f"Gross margin {gm*100:.0f}% — excellent")
        elif gm >= 0.30:
            raw += 9
        else:
            raw += 3
            neg.append(f"Gross margin {gm*100:.0f}% — thin")
    else:
        warn.append("Gross margin unavailable")

    # Operating margin
    om = fd.operating_margin
    if om is not None:
        total += 15
        if om >= 0.20:
            raw += 15
            pos.append(f"Operating margin {om*100:.0f}%")
        elif om >= 0.10:
            raw += 9
        elif om >= 0:
            raw += 4
        else:
            neg.append(f"Operating margin {om*100:.0f}% — loss-making")
    else:
        warn.append("Operating margin unavailable")

    # ROE
    roe = fd.roe
    if roe is not None:
        total += 15
        if roe >= 0.20:
            raw += 15
            pos.append(f"ROE {roe*100:.0f}% — high return")
        elif roe >= 0.10:
            raw += 9
        elif roe >= 0:
            raw += 4
        else:
            neg.append(f"ROE {roe*100:.0f}% — negative")
    else:
        warn.append("ROE unavailable")

    # ROIC
    roic = fd.roic
    if roic is not None:
        total += 15
        if roic >= 0.15:
            raw += 15
            pos.append(f"ROIC {roic*100:.0f}% — above cost of capital")
        elif roic >= 0.08:
            raw += 9
        elif roic >= 0:
            raw += 4
        else:
            neg.append(f"ROIC {roic*100:.0f}% — destroying value")
    else:
        warn.append("ROIC unavailable")

    # ROA
    roa = fd.roa
    if roa is not None:
        total += 10
        if roa >= 0.10:
            raw += 10
            pos.append(f"ROA {roa*100:.0f}% — efficient assets")
        elif roa >= 0.05:
            raw += 6
        elif roa >= 0:
            raw += 3
        else:
            neg.append(f"ROA {roa*100:.0f}% — negative")
    else:
        warn.append("ROA unavailable")

    # Current ratio
    cr = fd.current_ratio
    if cr is not None:
        total += 10
        if cr >= 2.0:
            raw += 10
            pos.append(f"Current ratio {cr:.1f} — strong liquidity")
        elif cr >= 1.2:
            raw += 7
        else:
            raw += 2
            neg.append(f"Current ratio {cr:.1f} — liquidity risk")
    else:
        warn.append("Current ratio unavailable")

    # Quick ratio
    qr = fd.quick_ratio
    if qr is not None:
        total += 10
        if qr >= 1.5:
            raw += 10
            pos.append(f"Quick ratio {qr:.1f} — excellent liquidity")
        elif qr >= 1.0:
            raw += 7
        else:
            raw += 2
            neg.append(f"Quick ratio {qr:.1f} — tight")
    else:
        warn.append("Quick ratio unavailable")

    # Debt/equity (total)
    de = fd.debt_to_equity
    if de is not None:
        total += 7
        if de <= 50:
            raw += 7
            pos.append(f"D/E {de:.0f}% — low leverage")
        elif de <= 100:
            raw += 4
        elif de <= 200:
            raw += 2
            neg.append(f"D/E {de:.0f}% — high leverage")
        else:
            neg.append(f"D/E {de:.0f}% — very high leverage")
    else:
        warn.append("Debt/equity unavailable")

    # Long-term debt/equity (more conservative balance sheet measure)
    ltde = fd.long_term_debt_equity
    if ltde is not None:
        total += 8
        if ltde <= 30:
            raw += 8
            pos.append(f"LT Debt/Equity {ltde:.0f}% — conservative long-term leverage")
        elif ltde <= 80:
            raw += 5
        elif ltde <= 150:
            raw += 2
            neg.append(f"LT Debt/Equity {ltde:.0f}% — elevated long-term debt")
        else:
            neg.append(f"LT Debt/Equity {ltde:.0f}% — heavy long-term debt load")
    else:
        warn.append("Long-term debt/equity unavailable")

    parts = ["Quality card scores profitability margins, return ratios (ROE/ROIC/ROA), and balance sheet strength (D/E, LT debt/equity, liquidity ratios)."]
    return _score_to_card("quality", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 10. Ownership
# ---------------------------------------------------------------------------

def score_ownership(fd: FundamentalData) -> SignalCard:
    """Score based on insider/institutional ownership, short float."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Insider ownership
    ins_own = fd.insider_ownership
    if ins_own is not None:
        total += 15
        if ins_own >= 0.10:
            raw += 15
            pos.append(f"Insider ownership {ins_own*100:.0f}% — strong alignment")
        elif ins_own >= 0.03:
            raw += 10
            pos.append(f"Insider ownership {ins_own*100:.0f}%")
        else:
            raw += 5
            neg.append(f"Low insider ownership {ins_own*100:.1f}%")
    else:
        warn.append("Insider ownership unavailable")

    # Insider transactions (net buying)
    ins_tx = fd.insider_transactions
    if ins_tx is not None:
        total += 20
        if ins_tx > 0:
            raw += 20
            pos.append("Insiders net buying — bullish signal")
        elif ins_tx < 0:
            neg.append("Insiders net selling")
        else:
            raw += 10
    else:
        warn.append("Insider transactions unavailable")

    # Institutional ownership
    inst_own = fd.institutional_ownership
    if inst_own is not None:
        total += 15
        if 0.50 <= inst_own <= 0.90:
            raw += 15
            pos.append(f"Institutional ownership {inst_own*100:.0f}% — well-sponsored")
        elif inst_own < 0.30:
            raw += 5
            neg.append(f"Low institutional ownership {inst_own*100:.0f}%")
        else:
            raw += 9
    else:
        warn.append("Institutional ownership unavailable")

    # Institutional transactions (net buying)
    inst_tx = fd.institutional_transactions
    if inst_tx is not None:
        total += 20
        if inst_tx > 0:
            raw += 20
            pos.append("Institutions net accumulating")
        elif inst_tx < 0:
            neg.append("Institutions net distributing")
        else:
            raw += 10
    else:
        warn.append("Institutional transactions unavailable")

    # Short float
    sf = fd.short_float
    if sf is not None:
        total += 20
        if sf <= 0.05:
            raw += 20
            pos.append(f"Short float {sf*100:.1f}% — low short interest")
        elif sf <= 0.10:
            raw += 12
        elif sf <= 0.20:
            raw += 6
            neg.append(f"Short float {sf*100:.0f}% — elevated")
        else:
            # High short float: squeeze potential — note as dual signal
            raw += 8
            pos.append(f"Short float {sf*100:.0f}% — squeeze potential")
            neg.append(f"Short float {sf*100:.0f}% — high risk signal")
    else:
        warn.append("Short float unavailable")

    # Short ratio (days to cover)
    sr = fd.short_ratio
    if sr is not None:
        total += 10
        if sr <= 3:
            raw += 10
        elif sr <= 7:
            raw += 6
        else:
            raw += 2
            neg.append(f"Short ratio {sr:.1f} days — crowded short")
    else:
        warn.append("Short ratio unavailable")

    parts = ["Ownership card measures insider/institutional positioning and short interest dynamics."]
    return _score_to_card("ownership", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 11. Catalyst
# ---------------------------------------------------------------------------

def score_catalyst(fd: FundamentalData, earnings: EarningsData, news: NewsSummary) -> SignalCard:
    """Score based on analyst recommendations, news sentiment, earnings proximity, target price."""
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Analyst recommendation (1=Strong Buy, 5=Strong Sell)
    rec = fd.analyst_recommendation
    if rec is not None:
        total += 25
        if rec <= 1.5:
            raw += 25
            pos.append(f"Analyst consensus {rec:.1f} — Strong Buy")
        elif rec <= 2.5:
            raw += 18
            pos.append(f"Analyst consensus {rec:.1f} — Buy")
        elif rec <= 3.5:
            raw += 10
        elif rec <= 4.0:
            raw += 4
            neg.append(f"Analyst consensus {rec:.1f} — Underperform")
        else:
            neg.append(f"Analyst consensus {rec:.1f} — Sell")
    else:
        warn.append("Analyst recommendation unavailable")

    # Target price distance
    tpd = fd.target_price_distance
    if tpd is not None:
        total += 20
        if tpd >= 20:
            raw += 20
            pos.append(f"Analyst target +{tpd:.0f}% upside")
        elif tpd >= 10:
            raw += 14
            pos.append(f"Analyst target +{tpd:.0f}% upside")
        elif tpd >= 0:
            raw += 8
        else:
            neg.append(f"Analyst target {tpd:.0f}% — stock above consensus")
    else:
        warn.append("Analyst target price unavailable")

    # News score (0–100 from NewsSummary)
    ns = news.news_score
    if ns is not None:
        total += 25
        if ns >= 70:
            raw += 25
            pos.append(f"News score {ns:.0f}/100 — positive coverage")
        elif ns >= 55:
            raw += 18
            pos.append(f"News score {ns:.0f}/100 — mildly positive")
        elif ns >= 45:
            raw += 12
        elif ns >= 30:
            raw += 5
            neg.append(f"News score {ns:.0f}/100 — negative sentiment")
        else:
            neg.append(f"News score {ns:.0f}/100 — very negative")
    else:
        warn.append("News score unavailable")

    # Earnings beat rate (recent catalyst quality)
    beat_rate = earnings.beat_rate
    if beat_rate is not None:
        total += 15
        if beat_rate >= 0.75:
            raw += 15
            pos.append(f"Beat rate {beat_rate*100:.0f}% — reliable catalyst")
        elif beat_rate >= 0.50:
            raw += 9
        else:
            neg.append(f"Beat rate {beat_rate*100:.0f}% — inconsistent")
    else:
        warn.append("Earnings beat rate unavailable")

    # Earnings proximity: within 30 days = upcoming catalyst
    within_30 = earnings.within_30_days
    if within_30 is True:
        total += 15
        # Upcoming earnings = catalyst opportunity; slight positive
        raw += 10
        pos.append("Earnings within 30 days — upcoming catalyst")
    elif within_30 is False:
        total += 15
        raw += 12  # no binary risk event imminent
        pos.append("No imminent earnings risk")
    else:
        warn.append("Earnings date unavailable")

    parts = ["Catalyst card weighs analyst ratings, news sentiment, target price upside, and earnings history."]
    return _score_to_card("catalyst", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def score_all_cards(
    technicals: TechnicalIndicators,
    fundamentals: FundamentalData,
    valuation: ValuationData,
    earnings: EarningsData,
    news: NewsSummary,
) -> SignalCards:
    """Compute all 11 signal cards and return a SignalCards container."""
    return SignalCards(
        momentum=score_momentum(technicals),
        trend=score_trend(technicals),
        entry_timing=score_entry_timing(technicals),
        volume_accumulation=score_volume_accumulation(technicals),
        volatility_risk=score_volatility_risk(technicals),
        relative_strength=score_relative_strength(technicals),
        growth=score_growth(fundamentals, earnings),
        valuation=score_valuation(valuation),
        quality=score_quality(fundamentals),
        ownership=score_ownership(fundamentals),
        catalyst=score_catalyst(fundamentals, earnings, news),
    )
