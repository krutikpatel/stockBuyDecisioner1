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

from app.algo_config import AlgoConfig, get_algo_config
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

def score_momentum(ti: TechnicalIndicators, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on price momentum: perf periods, MACD, RSI trend, SMA position."""
    cfg = algo_config or get_algo_config()
    mc = cfg.signal_cards["momentum"]

    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Performance periods (1W, 1M, 3M)
    for attr, weight, label in [
        ("perf_1w", mc["perf_1w_weight"], "1-week"),
        ("perf_1m", mc["perf_1m_weight"], "1-month"),
        ("perf_3m", mc["perf_3m_weight"], "3-month"),
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
        total += mc["macd_weight"]
        if hist > 0:
            raw += min(mc["macd_max_pts"], mc["macd_base_pts"] + hist * mc["macd_scale"])
            pos.append("MACD histogram positive")
        else:
            neg.append("MACD histogram negative")
    else:
        warn.append("MACD unavailable")

    # RSI 14 — inverted: oversold-recovery is the top tier (mean-reversion alpha)
    rsi = ti.rsi_14
    rsi_slope = ti.rsi_slope  # read slope here for combined RSI+slope tier logic
    if rsi is not None:
        total += mc["rsi_weight"]
        oversold_max = mc.get("rsi_oversold_max", 35)
        early_min = mc.get("rsi_early_recovery_min", 35)
        early_max = mc.get("rsi_early_recovery_max", 50)
        neutral_min = mc.get("rsi_neutral_min", 50)
        neutral_max = mc.get("rsi_neutral_max", 65)
        ext_min = mc.get("rsi_extended_min", 65)
        ext_max = mc.get("rsi_extended_max", 80)
        slope_rising = rsi_slope is not None and rsi_slope > 0
        if rsi < oversold_max:
            if slope_rising:
                raw += mc.get("rsi_oversold_rising_pts", 15)
                pos.append(f"RSI {rsi:.0f} turning up from oversold — strong recovery signal")
            else:
                raw += mc.get("rsi_oversold_falling_pts", 5)
                neg.append(f"RSI {rsi:.0f} — oversold but still falling, wait for turn")
        elif rsi < early_max:
            if slope_rising:
                raw += mc.get("rsi_early_recovery_rising_pts", 10)
                pos.append(f"RSI {rsi:.0f} rising — early recovery momentum")
            else:
                raw += mc.get("rsi_early_recovery_falling_pts", 4)
                neg.append(f"RSI {rsi:.0f} — pullback not yet stabilised")
        elif rsi <= neutral_max:
            raw += mc.get("rsi_neutral_pts", 8)
        elif rsi <= ext_max:
            raw += mc.get("rsi_extended_pts", 4)
            neg.append(f"RSI {rsi:.0f} — extended, limited near-term upside")
        else:
            raw += mc.get("rsi_overbought_pts", 0)
            neg.append(f"RSI {rsi:.0f} — overbought, avoid new entries")
    else:
        warn.append("RSI unavailable")

    # RSI slope (already read above; scored separately for weight contribution)
    slope_pts = mc["rsi_slope_pts"]  # [strong_up, mild_up, flat, mild_down, strong_down]
    if rsi_slope is not None:
        total += mc["rsi_slope_weight"]
        if rsi_slope >= mc["rsi_slope_strong_up"]:
            raw += slope_pts[0]
            pos.append(f"RSI slope +{rsi_slope:.1f} — momentum accelerating")
        elif rsi_slope >= mc["rsi_slope_mild_up"]:
            raw += slope_pts[1]
            pos.append(f"RSI slope +{rsi_slope:.1f} — momentum improving")
        elif rsi_slope >= mc["rsi_slope_mild_down"]:
            raw += slope_pts[2]
        elif rsi_slope >= mc["rsi_slope_strong_down"]:
            raw += slope_pts[3]
            neg.append(f"RSI slope {rsi_slope:.1f} — momentum fading")
        else:
            raw += slope_pts[4]
            neg.append(f"RSI slope {rsi_slope:.1f} — momentum deteriorating")
    else:
        warn.append("RSI slope unavailable")

    # Price above EMA8 and EMA21
    for attr, label, weight in [
        ("ema8_relative", "EMA8", mc["ema8_weight"]),
        ("ema21_relative", "EMA21", mc["ema21_weight"]),
    ]:
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

    # Late-phase momentum penalty — stocks that ran >20% in 3M AND are overbought (RSI>70)
    # have poor forward returns (parabolic moves tend to mean-revert)
    perf_3m_val = getattr(ti, "perf_3m", None) or 0.0
    rsi_val = getattr(ti, "rsi_14", None) or 50.0
    if (perf_3m_val > mc.get("late_phase_perf3m_threshold", 20.0)
            and rsi_val > mc.get("late_phase_rsi_threshold", 70.0)):
        raw = max(0.0, raw - mc.get("late_phase_penalty_pts", 12))
        neg.append(f"Late-phase signal: +{perf_3m_val:.1f}% 3M run with RSI {rsi_val:.0f} — mean-reversion risk")

    parts = ["Momentum score driven by short- to medium-term price performance and MACD."]
    return _score_to_card("momentum", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 2. Trend
# ---------------------------------------------------------------------------

def score_trend(ti: TechnicalIndicators, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on trend structure: SMA stack, slopes, ADX."""
    cfg = algo_config or get_algo_config()
    tc = cfg.signal_cards["trend"]

    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Price vs SMAs (20, 50, 200)
    for attr, label, weight in [
        ("sma20_relative", "SMA20", tc["sma20_above_pts"]),
        ("sma50_relative", "SMA50", tc["sma50_above_pts"]),
        ("sma200_relative", "SMA200", tc["sma200_above_pts"]),
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
        ("sma20_slope", "SMA20 slope", tc["sma20_slope_pts"]),
        ("sma50_slope", "SMA50 slope", tc["sma50_slope_pts"]),
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
        total += tc["adx_pts"]
        if adx >= tc["adx_strong_threshold"]:
            raw += tc["adx_strong_pts"]
            pos.append(f"ADX {adx:.0f} — strong trend")
        elif adx >= tc["adx_moderate_threshold"]:
            raw += tc["adx_moderate_pts"]
        else:
            raw += tc["adx_weak_pts"]
            neg.append(f"ADX {adx:.0f} — weak trend")
    else:
        warn.append("ADX unavailable")

    # 6M and 1Y performance (trend confirmation)
    for attr, label, weight in [
        ("perf_6m", "6-month", tc["perf_6m_pts"]),
        ("perf_1y", "1-year", tc["perf_1y_pts"]),
    ]:
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

    # Extension penalty — overextended uptrends have poor forward returns (doubled)
    sma50_rel = getattr(ti, "sma50_relative", None)
    sma20_rel = getattr(ti, "sma200_relative", None)
    sma50_sl = getattr(ti, "sma50_slope", None)
    sma200_sl = getattr(ti, "sma200_slope", None)
    sma50_rel_val = getattr(ti, "sma50_relative", None)
    sma20_rel_val = getattr(ti, "sma20_relative", None)
    if sma50_rel_val is not None and sma50_rel_val > tc.get("extension_penalty_sma50_threshold", 15.0):
        raw = max(0.0, raw + tc.get("extension_penalty_sma50_pts", -25))
        neg.append(f"SMA50 extension +{sma50_rel_val:.1f}% — severely overextended, mean-reversion risk")
    if sma20_rel_val is not None and sma20_rel_val > tc.get("extension_penalty_sma20_threshold", 8.0):
        raw = max(0.0, raw + tc.get("extension_penalty_sma20_pts", -12))
        neg.append(f"SMA20 extension +{sma20_rel_val:.1f}% — stretched above near-term mean")

    # Recovery bonus — early-stage recovery from downtrend has high forward alpha
    sma200_rel = getattr(ti, "sma200_relative", None)
    reclaim_zone = tc.get("sma200_reclaim_zone_pct", 5.0) / 100.0
    recovery_slope_min = tc.get("sma200_recovery_slope_min", 0.0)
    if (sma200_rel is not None and sma200_sl is not None
            and -reclaim_zone <= sma200_rel <= reclaim_zone
            and sma200_sl >= recovery_slope_min):
        raw = min(total, raw + tc.get("sma200_reclaim_pts", 20))
        pos.append(f"Price reclaiming SMA200 with rising slope — early recovery signal")
    elif (sma200_rel is not None and sma200_rel < 0
          and sma50_sl is not None and sma50_sl > 0
          and sma200_sl is not None and sma200_sl >= recovery_slope_min):
        raw = min(total, raw + tc.get("sma50_recovery_pts", 15))
        pos.append("SMA50 recovering while below SMA200 — bottoming pattern forming")

    parts = ["Trend score rewards early-stage recovery signals and penalises overextended uptrends."]
    return _score_to_card("trend", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 3. Entry Timing
# ---------------------------------------------------------------------------

def score_entry_timing(ti: TechnicalIndicators, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on entry quality: RSI, StochRSI, VWAP, Bollinger, gap."""
    cfg = algo_config or get_algo_config()
    ec = cfg.signal_cards["entry_timing"]
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    rsi = ti.rsi_14
    if rsi is not None:
        total += ec["rsi_weight"]
        deep_os_max = ec.get("rsi_deep_oversold_max", 20.0)
        if rsi < deep_os_max:
            # extreme oversold — capitulation, high recovery probability
            raw += ec.get("rsi_deep_oversold_pts", 20)
            pos.append(f"RSI {rsi:.0f} — extreme capitulation, strong mean-reversion entry")
        elif ec["rsi_ideal_min"] <= rsi <= ec["rsi_ideal_max"]:
            # primary buy zone: 20-40 (deeply oversold recovery)
            raw += ec["rsi_ideal_pts"]
            pos.append(f"RSI {rsi:.0f} — ideal oversold entry zone ({ec['rsi_ideal_min']:.0f}–{ec['rsi_ideal_max']:.0f})")
        elif ec["rsi_pullback_min"] <= rsi < ec["rsi_pullback_max"]:
            # good pullback zone: 40-50
            raw += ec["rsi_pullback_pts"]
            pos.append(f"RSI {rsi:.0f} — pullback sweet spot ({ec['rsi_pullback_min']:.0f}–{ec['rsi_pullback_max']:.0f})")
        elif ec.get("rsi_neutral_min", 50.0) <= rsi <= ec.get("rsi_neutral_max", 60.0):
            # neutral zone: 50-60
            raw += ec.get("rsi_neutral_pts", 15)
        elif ec["rsi_extended_min"] < rsi <= ec["rsi_extended_max"]:
            # extended zone: 60-72 — some pts but poor entry
            raw += ec["rsi_extended_pts"]
            neg.append(f"RSI {rsi:.0f} — extended, poor entry risk/reward")
        elif rsi > ec["rsi_overbought_threshold"]:
            raw += ec["rsi_overbought_pts"]
            neg.append(f"RSI {rsi:.0f} — overbought, avoid new entries")
        else:
            # 40-50 fallback (shouldn't normally reach here)
            raw += ec["rsi_pullback_pts"]
    else:
        warn.append("RSI unavailable")

    # Stochastic RSI
    srsi = ti.stochastic_rsi
    if srsi is not None:
        w = ec["stochrsi_weight"]
        total += w
        if ec["stochrsi_mid_min"] <= srsi <= ec["stochrsi_mid_max"]:
            raw += w
            pos.append("StochRSI in healthy range")
        elif srsi > 0.8:
            raw += round(w / 3)
            neg.append("StochRSI overbought")
        elif srsi < ec["stochrsi_mid_min"]:
            raw += round(w * 8 / 15)
        else:
            raw += round(w * 2 / 3)
    else:
        warn.append("StochRSI unavailable")

    # VWAP position — inverted: below VWAP = buying at discount = best entry
    vwap_dev = ti.vwap_deviation
    if vwap_dev is not None:
        w = ec["vwap_weight"]
        total += w
        discount_min = ec.get("vwap_dev_discount_min", -8.0)
        discount_max = ec.get("vwap_dev_discount_max", 0.0)
        if discount_min <= vwap_dev <= discount_max:
            raw += w
            pos.append(f"Price {abs(vwap_dev):.1f}% below VWAP — buying at institutional discount")
        elif vwap_dev < discount_min:
            raw += round(w * 0.6)
            pos.append("Price deeply below VWAP — extreme discount, possible support")
        elif vwap_dev <= ec["vwap_dev_good_max"]:
            raw += round(w * 0.5)
        else:
            raw += round(w * 0.2)
            neg.append(f"Price {vwap_dev:.1f}% above VWAP — extended, chasing entry")
    else:
        warn.append("VWAP deviation unavailable")

    # Bollinger Band position (0 = lower band, 1 = upper band)
    # Inverted: lower band = oversold = best entry zone
    bb_pos = ti.bollinger_band_position
    if bb_pos is not None:
        w = ec["bb_weight"]
        total += w
        if ec["bb_ideal_min"] <= bb_pos <= ec["bb_ideal_max"]:
            # lower third (0.0–0.3): near lower band = best entry
            raw += w
            pos.append("Price near lower Bollinger Band — oversold entry zone")
        elif bb_pos < ec["bb_oversold_threshold"]:
            # below lower band: extreme oversold
            raw += round(w * 0.8)
            pos.append("Price below lower Bollinger Band — capitulation entry")
        elif bb_pos <= ec["bb_extended_threshold"]:
            # middle range (0.3–0.6): neutral
            raw += round(w * 0.5)
        else:
            # upper range / overbought: poor entry
            raw += round(w * 0.2)
            neg.append("Price at upper Bollinger Band — extended, poor entry")
    else:
        warn.append("Bollinger Band position unavailable")

    # EMA8 relative (near-term support)
    ema8 = ti.ema8_relative
    if ema8 is not None:
        w = ec["ema8_weight"]
        total += w
        if 0 <= ema8 <= ec["ema8_dev_good_max"]:
            raw += w
            pos.append("Price close to EMA8 — tight entry")
        elif ema8 > ec["ema8_dev_good_max"]:
            raw += round(w * 0.5)
            neg.append("Price extended above EMA8")
        else:
            raw += round(w * 0.3)
    else:
        warn.append("EMA8 relative unavailable")

    # RSI slope
    rsi_slope = ti.rsi_slope
    if rsi_slope is not None:
        total += ec["rsi_slope_weight"]
        slope_pts = ec["rsi_slope_pts"]  # [strong_up, mild_up, mild_down, strong_down]
        if rsi_slope >= ec["rsi_slope_up_strong"]:
            raw += slope_pts[0]
            pos.append(f"RSI slope +{rsi_slope:.1f} — momentum building, good entry")
        elif rsi_slope >= ec["rsi_slope_up_mild"]:
            raw += slope_pts[1]
        elif rsi_slope >= ec["rsi_slope_down"]:
            raw += slope_pts[2]
            neg.append(f"RSI slope {rsi_slope:.1f} — momentum fading at entry")
        else:
            raw += slope_pts[3]
            neg.append(f"RSI slope {rsi_slope:.1f} — avoid entry, momentum declining")
    else:
        warn.append("RSI slope unavailable")

    # Gap %
    gap = ti.gap_percent
    if gap is not None:
        w = ec["gap_weight"]
        total += w
        if ec["gap_ideal_min"] <= gap <= ec["gap_ideal_max"]:
            raw += w
        elif gap > ec["gap_chasing_threshold"]:
            raw += round(w * 0.2)
            neg.append(f"Large gap up {gap:.1f}% — risky entry")
        else:
            raw += round(w * 0.6)
    else:
        warn.append("Gap% unavailable")

    parts = ["Entry timing measures RSI zone, RSI slope, StochRSI, VWAP support, and Bollinger Band position."]
    return _score_to_card("entry_timing", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 4. Volume / Accumulation
# ---------------------------------------------------------------------------

def score_volume_accumulation(ti: TechnicalIndicators, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on OBV, A/D, CMF, relative volume, up/down ratio."""
    cfg = algo_config or get_algo_config()
    vc = cfg.signal_cards["volume_accumulation"]
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # OBV trend
    obv = ti.obv_trend
    if obv is not None:
        w = vc["obv_weight"]
        total += w
        if obv == 1:
            raw += w
            pos.append("OBV rising — accumulation confirmed")
        elif obv == -1:
            neg.append("OBV falling — distribution signal")
        else:
            raw += round(w * 0.5)

    # A/D trend
    ad = ti.ad_trend
    if ad is not None:
        w = vc["ad_weight"]
        total += w
        if ad == 1:
            raw += w
            pos.append("A/D line rising")
        elif ad == -1:
            neg.append("A/D line falling — institutional selling")
        else:
            raw += round(w * 0.47)

    # Chaikin Money Flow
    cmf = ti.chaikin_money_flow
    if cmf is not None:
        w = vc["cmf_weight"]
        total += w
        if cmf > vc["cmf_bullish"]:
            raw += w
            pos.append(f"CMF {cmf:.2f} — strong buying pressure")
        elif cmf > vc["cmf_moderate"]:
            raw += round(w * 0.6)
            pos.append(f"CMF {cmf:.2f} — mild buying pressure")
        elif cmf < vc["cmf_bearish"]:
            neg.append(f"CMF {cmf:.2f} — distribution")
        else:
            raw += round(w * 0.25)
    else:
        warn.append("Chaikin Money Flow unavailable")

    # Breakout volume multiple
    bvol = ti.breakout_volume_multiple
    if bvol is not None:
        w = vc["breakout_vol_weight"]
        total += w
        if bvol >= vc["breakout_vol_strong"]:
            raw += w
            pos.append(f"Volume {bvol:.1f}× avg — breakout confirmation")
        elif bvol >= vc["breakout_vol_normal"]:
            raw += round(w * 0.6)
        else:
            raw += round(w * 0.25)
            neg.append(f"Volume {bvol:.1f}× avg — below average")
    else:
        warn.append("Breakout volume multiple unavailable")

    # Up/down volume ratio
    udv = ti.updown_volume_ratio
    if udv is not None:
        w = vc["updown_vol_weight"]
        total += w
        if udv >= vc["updown_vol_strong"]:
            raw += w
            pos.append(f"Up/down volume ratio {udv:.1f} — buyers in control")
        elif udv >= vc["updown_vol_normal"]:
            raw += round(w * 0.67)
        else:
            neg.append(f"Up/down volume ratio {udv:.1f} — sellers dominant")
    else:
        warn.append("Up/down volume ratio unavailable")

    # Volume dry-up (low volume on pullback = bullish)
    vdu = ti.volume_dryup_ratio
    if vdu is not None:
        w = vc["dryup_weight"]
        total += w
        if vdu < vc["dryup_low"]:
            raw += w
            pos.append("Volume dry-up on pullback — healthy consolidation")
        elif vdu > vc["dryup_high"]:
            raw += round(w * 0.3)
            neg.append("Heavy volume on pullback — distribution concern")
        else:
            raw += round(w * 0.6)
    else:
        warn.append("Volume dry-up ratio unavailable")

    parts = ["Volume/accumulation score measures institutional buying pressure via OBV, CMF, and volume ratios."]
    return _score_to_card("volume_accumulation", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 5. Volatility / Risk
# ---------------------------------------------------------------------------

def score_volatility_risk(ti: TechnicalIndicators, algo_config: Optional[AlgoConfig] = None, beta: Optional[float] = None) -> SignalCard:
    """Score based on dislocation opportunity: severe drawdown, high ATR spike, and distance from highs.

    Inverted from the old 'reward low risk' logic. In a quality-stock universe, high current
    volatility and deep drawdowns signal panic selling — exactly the buying opportunity.
    """
    cfg = algo_config or get_algo_config()
    vrc = cfg.signal_cards["volatility_risk"]
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # 3M drawdown — more severe = more opportunity (capitulation buy in quality stock)
    dd3m = ti.max_drawdown_3m
    if dd3m is not None:
        w = vrc["dd3m_weight"]
        tiers = vrc["dd3m_tiers"]   # [-5, -10, -20]
        pts = vrc["dd3m_pts"]       # [3, 10, 18, 25] — inverted: severe = high pts
        total += w
        if dd3m >= tiers[0]:        # >= -5%: tiny drawdown = priced to perfection
            raw += pts[0]
            neg.append(f"3M drawdown only {dd3m:.1f}% — limited mean-reversion upside")
        elif dd3m >= tiers[1]:      # >= -10%
            raw += pts[1]
        elif dd3m >= tiers[2]:      # >= -20%
            raw += pts[2]
            pos.append(f"3M drawdown {dd3m:.1f}% — meaningful dislocation opportunity")
        else:                        # < -20%: severe capitulation
            raw += pts[3]
            pos.append(f"3M drawdown {dd3m:.1f}% — deep capitulation, high recovery potential")
    else:
        warn.append("3M drawdown unavailable")

    # 1Y drawdown — more severe = more opportunity
    dd1y = ti.max_drawdown_1y
    if dd1y is not None:
        w = vrc["dd1y_weight"]
        tiers = vrc["dd1y_tiers"]   # [-10, -25]
        pts = vrc["dd1y_pts"]       # [2, 8, 15] — inverted
        total += w
        if dd1y >= tiers[0]:        # >= -10%: minimal 1Y drawdown
            raw += pts[0]
        elif dd1y >= tiers[1]:      # >= -25%
            raw += pts[1]
            pos.append(f"1Y drawdown {dd1y:.1f}% — significant reset from peak")
        else:                        # < -25%: deep annual drawdown
            raw += pts[2]
            pos.append(f"1Y drawdown {dd1y:.1f}% — major dislocation from year high")
    else:
        warn.append("1Y drawdown unavailable")

    # ATR% — higher = more fear = more opportunity (inverted)
    atr_pct = ti.atr_percent
    if atr_pct is not None:
        w = vrc["atr_weight"]
        tiers = vrc["atr_tiers"]    # [1.5, 3.0, 5.0]
        pts = vrc["atr_pts"]        # [2, 7, 13, 20] — inverted: high ATR = high pts
        total += w
        if atr_pct <= tiers[0]:     # <= 1.5%: dead calm = fully priced
            raw += pts[0]
            neg.append(f"ATR {atr_pct:.1f}% — very low, stock priced to perfection")
        elif atr_pct <= tiers[1]:   # <= 3.0%: normal vol
            raw += pts[1]
        elif atr_pct <= tiers[2]:   # <= 5.0%: elevated fear
            raw += pts[2]
            pos.append(f"ATR {atr_pct:.1f}% — elevated fear, potential opportunity")
        else:                        # > 5.0%: high fear spike
            raw += pts[3]
            pos.append(f"ATR {atr_pct:.1f}% — fear spike, strong mean-reversion candidate")
    else:
        warn.append("ATR% unavailable")

    # Weekly volatility (annualised %) — higher = more fear = more opportunity (inverted)
    wvol = ti.volatility_weekly
    if wvol is not None:
        w = vrc["vol_weekly_weight"]
        tiers = vrc["vol_weekly_tiers"]  # [20, 40]
        pts = vrc["vol_weekly_pts"]      # [2, 8, 15] — inverted
        total += w
        wvol_pct = wvol * 100 if wvol < 5 else wvol
        if wvol_pct <= tiers[0]:    # <= 20%: very stable = no dislocation
            raw += pts[0]
            neg.append(f"Weekly vol {wvol_pct:.0f}% ann — low, likely fully valued")
        elif wvol_pct <= tiers[1]:  # <= 40%: moderate vol
            raw += pts[1]
        else:                        # > 40%: high vol = panic selling
            raw += pts[2]
            pos.append(f"Weekly vol {wvol_pct:.0f}% ann — elevated, mean-reversion opportunity")
    else:
        warn.append("Weekly volatility unavailable")

    # Beta — higher beta = amplified recovery in quality stock (inverted).
    # Passed in from FundamentalData.beta (yfinance info); None in backtest (not time-varying there).
    beta = beta
    if beta is not None:
        w = vrc["beta_weight"]
        pts = vrc["beta_pts"]       # [15, 10, 5, 3]
        total += w
        high_t = vrc.get("beta_high_threshold", 1.5)
        mid_t = vrc.get("beta_mid_threshold", 1.0)
        low_t = vrc.get("beta_low_threshold", 0.5)
        if beta >= high_t:          # >= 1.5: high beta = amplified recovery
            raw += pts[0]
            pos.append(f"Beta {beta:.1f} — high-beta recovery candidate")
        elif beta >= mid_t:         # >= 1.0: market-plus beta
            raw += pts[1]
        elif beta >= low_t:         # >= 0.5: moderate
            raw += pts[2]
        else:                        # < 0.5: defensive, limited upside in recovery
            raw += pts[3]
            neg.append(f"Beta {beta:.1f} — very defensive, limited recovery leverage")
    else:
        warn.append("Beta unavailable")

    # Distance from 52W high — farther = more dislocation = more opportunity (inverted)
    d52h = ti.dist_from_52w_high
    if d52h is not None:
        w = vrc["dist_52w_weight"]
        pts = vrc["dist52_pts"]     # [10, 6, 2]
        total += w
        deep_t = vrc.get("dist52_deep", -30.0)   # very far from high
        mid_t = vrc.get("dist52_mid", -15.0)     # moderate correction
        if d52h <= deep_t:          # <= -30%: deep dislocation
            raw += pts[0]
            pos.append(f"{abs(d52h):.0f}% below 52W high — deep dislocation, high recovery potential")
        elif d52h <= mid_t:         # <= -15%: meaningful correction
            raw += pts[1]
            pos.append(f"{abs(d52h):.0f}% below 52W high — meaningful pullback from peak")
        else:                        # > -15%: near high = already recovered / priced in
            raw += pts[2]
            neg.append(f"Only {abs(d52h):.0f}% below 52W high — limited mean-reversion upside")
    else:
        warn.append("52W high distance unavailable")

    parts = ["Dislocation score: high ATR, deep drawdown, and distance from highs signal panic selling in quality stocks — the primary alpha source."]
    return _score_to_card("volatility_risk", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 6. Relative Strength
# ---------------------------------------------------------------------------

def score_relative_strength(ti: TechnicalIndicators, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on RS vs QQQ, return percentile ranks."""
    cfg = algo_config or get_algo_config()
    rc = cfg.signal_cards["relative_strength"]
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # RS vs QQQ
    rs_qqq = ti.rs_vs_qqq
    if rs_qqq is not None:
        w = rc["rs_qqq_weight"]
        pts = rc["rs_qqq_pts"]   # e.g. [30, 18, 10, 0]
        total += w
        if rs_qqq >= rc["rs_qqq_strong"]:
            raw += pts[0]
            pos.append(f"RS vs QQQ +{rs_qqq:.1f}% — strong outperformance")
        elif rs_qqq >= rc["rs_qqq_neutral"]:
            raw += pts[1]
            pos.append(f"RS vs QQQ +{rs_qqq:.1f}%")
        elif rs_qqq >= rc["rs_qqq_weak"]:
            raw += pts[2]
            neg.append(f"RS vs QQQ {rs_qqq:.1f}%")
        else:
            raw += pts[3]
            neg.append(f"RS vs QQQ {rs_qqq:.1f}% — underperforming badly")
    else:
        warn.append("RS vs QQQ unavailable (QQQ benchmark data not fetched)")

    # Return percentile ranks — weights and tier points from config
    rank_cfg = [
        ("return_pct_rank_20d",  "20D",  rc["rank_20d_weight"],  rc["rank_pts_high"][0],  rc["rank_pts_mid"][0],  rc["rank_pts_low"][0],  rc["rank_pts_bottom"][0]),
        ("return_pct_rank_63d",  "63D",  rc["rank_63d_weight"],  rc["rank_pts_high"][1],  rc["rank_pts_mid"][1],  rc["rank_pts_low"][1],  rc["rank_pts_bottom"][1]),
        ("return_pct_rank_126d", "126D", rc["rank_126d_weight"], rc["rank_pts_high"][2],  rc["rank_pts_mid"][2],  rc["rank_pts_low"][2],  rc["rank_pts_bottom"][2]),
        ("return_pct_rank_252d", "252D", rc["rank_252d_weight"], rc["rank_pts_high"][3],  rc["rank_pts_mid"][3],  rc["rank_pts_low"][3],  rc["rank_pts_bottom"][3]),
    ]
    for attr, label, weight, p_high, p_mid, p_low, p_bottom in rank_cfg:
        val = getattr(ti, attr, None)
        if val is not None:
            total += weight
            if val >= rc["rank_pct_high"]:
                raw += p_high
                pos.append(f"{label} return rank {val:.0f}th percentile — top quartile")
            elif val >= rc["rank_pct_mid"]:
                raw += p_mid
            elif val >= rc["rank_pct_low"]:
                raw += p_low
                neg.append(f"{label} return rank {val:.0f}th percentile")
            else:
                raw += p_bottom
                neg.append(f"{label} return rank {val:.0f}th percentile — bottom quartile")
        else:
            warn.append(f"{label} return percentile rank unavailable")

    parts = ["Relative strength score compares returns vs QQQ and measures return percentile ranks."]
    return _score_to_card("relative_strength", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 7. Growth
# ---------------------------------------------------------------------------

def score_growth(fd: FundamentalData, earnings: EarningsData, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on EPS/revenue growth rates and earnings surprise history."""
    cfg = algo_config or get_algo_config()
    gc = cfg.signal_cards["growth"]
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Revenue growth YoY
    rev_yoy = fd.revenue_growth_yoy
    if rev_yoy is not None:
        w = gc["rev_yoy_weight"]
        total += w
        if rev_yoy >= gc["rev_yoy_strong"]:
            raw += w
            pos.append(f"Revenue growth {rev_yoy*100:.0f}% YoY — strong")
        elif rev_yoy >= gc["rev_yoy_moderate"]:
            raw += round(w * 0.7)
            pos.append(f"Revenue growth {rev_yoy*100:.0f}% YoY")
        elif rev_yoy >= gc["rev_yoy_slow"]:
            raw += round(w * 0.4)
        else:
            neg.append(f"Revenue declining {rev_yoy*100:.0f}% YoY")
    else:
        warn.append("Revenue growth YoY unavailable")

    # QoQ revenue growth (acceleration signal)
    rev_qoq = fd.revenue_growth_qoq
    if rev_qoq is not None:
        w = gc["rev_qoq_weight"]
        total += w
        if rev_qoq >= gc["rev_qoq_strong"]:
            raw += w
            pos.append(f"Revenue accelerating QoQ +{rev_qoq*100:.1f}%")
        elif rev_qoq >= 0:
            raw += round(w * 0.7)
        else:
            neg.append(f"Revenue decelerating QoQ {rev_qoq*100:.1f}%")
    else:
        warn.append("QoQ revenue growth unavailable")

    # EPS growth YoY
    eps_yoy = fd.eps_growth_yoy
    if eps_yoy is not None:
        w = gc["eps_yoy_weight"]
        total += w
        if eps_yoy >= gc["eps_yoy_strong"]:
            raw += w
            pos.append(f"EPS growth {eps_yoy*100:.0f}% YoY")
        elif eps_yoy >= gc["eps_yoy_moderate"]:
            raw += round(w * 0.65)
        elif eps_yoy >= 0:
            raw += round(w * 0.4)
        else:
            neg.append(f"EPS declining {eps_yoy*100:.0f}% YoY")
    else:
        warn.append("EPS growth YoY unavailable")

    # EPS next year estimate
    eps_ny = fd.eps_growth_next_year
    if eps_ny is not None:
        w = gc["eps_next_yr_weight"]
        total += w
        if eps_ny >= gc["eps_next_yr_strong"]:
            raw += w
            pos.append(f"EPS next year est. +{eps_ny*100:.0f}%")
        elif eps_ny >= 0:
            raw += round(w * 0.6)
        else:
            neg.append(f"EPS next year est. {eps_ny*100:.0f}%")
    else:
        warn.append("EPS next-year estimate unavailable")

    # Sales growth TTM
    sg_ttm = fd.sales_growth_ttm
    if sg_ttm is not None:
        w = gc["sales_ttm_weight"]
        total += w
        if sg_ttm >= gc["sales_ttm_strong"]:
            raw += w
            pos.append(f"Sales TTM growth {sg_ttm*100:.0f}%")
        elif sg_ttm >= 0:
            raw += round(w * 0.6)
        else:
            neg.append(f"Sales TTM {sg_ttm*100:.0f}%")
    else:
        warn.append("Sales growth TTM unavailable")

    # Multi-year EPS durability (3Y EPS growth)
    eps_3y = fd.eps_growth_3y
    if eps_3y is not None:
        w = gc["eps_3y_weight"]
        total += w
        if eps_3y >= gc["eps_3y_strong"]:
            raw += w
            pos.append(f"EPS 3Y CAGR {eps_3y*100:.0f}% — durable growth")
        elif eps_3y >= gc["eps_3y_moderate"]:
            raw += round(w * 0.6)
        elif eps_3y >= 0:
            raw += round(w * 0.3)
        else:
            neg.append(f"EPS 3Y CAGR {eps_3y*100:.0f}% — declining trend")
    else:
        warn.append("EPS 3-year growth unavailable")

    # Multi-year sales durability (3Y sales growth)
    sg_3y = fd.sales_growth_3y
    if sg_3y is not None:
        w = gc["sales_3y_weight"]
        total += w
        if sg_3y >= gc["sales_3y_strong"]:
            raw += w
            pos.append(f"Sales 3Y CAGR {sg_3y*100:.0f}% — durable revenue")
        elif sg_3y >= gc["sales_3y_moderate"]:
            raw += round(w * 0.625)
        elif sg_3y >= 0:
            raw += round(w * 0.25)
        else:
            neg.append(f"Sales 3Y CAGR {sg_3y*100:.0f}%")
    else:
        warn.append("Sales 3-year growth unavailable")

    # Forward EPS durability (next 5Y)
    eps_next5y = fd.eps_growth_next_5y
    if eps_next5y is not None:
        w = gc["eps_5y_weight"]
        total += w
        if eps_next5y >= gc["eps_5y_strong"]:
            raw += w
            pos.append(f"EPS next 5Y est. {eps_next5y*100:.0f}% — strong forward growth")
        elif eps_next5y >= gc["eps_5y_moderate"]:
            raw += round(w * 0.57)
        else:
            raw += round(w * 0.14)
            neg.append(f"EPS next 5Y est. {eps_next5y*100:.0f}% — weak outlook")
    else:
        warn.append("EPS next-5-year estimate unavailable")

    # Earnings beat rate
    beat_rate = earnings.beat_rate
    if beat_rate is not None:
        w = gc["beat_rate_weight"]
        total += w
        if beat_rate >= gc["beat_rate_high"] / 100:
            raw += w
            pos.append(f"Earnings beat rate {beat_rate*100:.0f}% — consistent")
        elif beat_rate >= gc["beat_rate_moderate"] / 100:
            raw += round(w * 0.6)
        else:
            neg.append(f"Beat rate {beat_rate*100:.0f}% — misses common")
    else:
        warn.append("Earnings beat rate unavailable")

    # Avg earnings surprise
    surprise = earnings.avg_eps_surprise_pct
    if surprise is not None:
        w = gc["eps_surprise_weight"]
        total += w
        if surprise >= gc["eps_surprise_strong"]:
            raw += w
            pos.append(f"Avg earnings surprise +{surprise:.1f}%")
        elif surprise >= gc["eps_surprise_moderate"]:
            raw += round(w * 0.7)
        elif surprise >= 0:
            raw += round(w * 0.4)
        else:
            neg.append(f"Avg earnings surprise {surprise:.1f}% — misses")
    else:
        warn.append("Avg earnings surprise unavailable")

    parts = ["Growth card assesses EPS/revenue growth rates and earnings beat consistency."]
    return _score_to_card("growth", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 8. Valuation
# ---------------------------------------------------------------------------

def score_valuation(vd: ValuationData, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on P/E, PEG, P/S, EV/EBITDA, P/FCF, EV/Sales."""
    cfg = algo_config or get_algo_config()
    vc = cfg.signal_cards["valuation"]
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Forward P/E (lower is better)
    fpe = vd.forward_pe
    if fpe is not None:
        w = vc["fpe_weight"]
        tiers = vc["fpe_tiers"]   # e.g. [15, 25, 40]
        pts = vc["fpe_pts"]       # e.g. [20, 13, 7, 2]
        total += w
        if fpe <= tiers[0]:
            raw += pts[0]
            pos.append(f"Forward P/E {fpe:.1f} — attractive")
        elif fpe <= tiers[1]:
            raw += pts[1]
        elif fpe <= tiers[2]:
            raw += pts[2]
            neg.append(f"Forward P/E {fpe:.1f} — elevated")
        else:
            raw += pts[3]
            neg.append(f"Forward P/E {fpe:.1f} — expensive")
    else:
        warn.append("Forward P/E unavailable")

    # PEG ratio (lower is better)
    peg = vd.peg_ratio
    if peg is not None:
        w = vc["peg_weight"]
        tiers = vc["peg_tiers"]   # e.g. [1.0, 1.5, 2.5]
        pts = vc["peg_pts"]       # e.g. [20, 14, 8, 2]
        total += w
        if peg <= tiers[0]:
            raw += pts[0]
            pos.append(f"PEG {peg:.2f} — undervalued vs growth")
        elif peg <= tiers[1]:
            raw += pts[1]
            pos.append(f"PEG {peg:.2f} — reasonable")
        elif peg <= tiers[2]:
            raw += pts[2]
            neg.append(f"PEG {peg:.2f} — slightly rich")
        else:
            raw += pts[3]
            neg.append(f"PEG {peg:.2f} — overvalued vs growth")
    else:
        warn.append("PEG ratio unavailable")

    # P/S ratio (lower is better)
    ps = vd.price_to_sales
    if ps is not None:
        w = vc["ps_weight"]
        tiers = vc["ps_tiers"]   # e.g. [3, 8, 15]
        pts = vc["ps_pts"]       # e.g. [15, 9, 5, 1]
        total += w
        if ps <= tiers[0]:
            raw += pts[0]
            pos.append(f"P/S {ps:.1f} — value territory")
        elif ps <= tiers[1]:
            raw += pts[1]
        elif ps <= tiers[2]:
            raw += pts[2]
            neg.append(f"P/S {ps:.1f} — premium")
        else:
            raw += pts[3]
            neg.append(f"P/S {ps:.1f} — very expensive")
    else:
        warn.append("Price/Sales unavailable")

    # EV/EBITDA (lower is better)
    ev_ebitda = vd.ev_to_ebitda
    if ev_ebitda is not None:
        w = vc["ev_ebitda_weight"]
        tiers = vc["ev_ebitda_tiers"]   # e.g. [12, 20, 35]
        pts = vc["ev_ebitda_pts"]       # e.g. [15, 9, 4, 1]
        total += w
        if ev_ebitda <= tiers[0]:
            raw += pts[0]
            pos.append(f"EV/EBITDA {ev_ebitda:.1f} — attractive")
        elif ev_ebitda <= tiers[1]:
            raw += pts[1]
        elif ev_ebitda <= tiers[2]:
            raw += pts[2]
            neg.append(f"EV/EBITDA {ev_ebitda:.1f} — elevated")
        else:
            raw += pts[3]
            neg.append(f"EV/EBITDA {ev_ebitda:.1f} — expensive")
    else:
        warn.append("EV/EBITDA unavailable")

    # FCF yield (higher is better)
    fcfy = vd.fcf_yield
    if fcfy is not None:
        w = vc["fcf_yield_weight"]
        tiers = vc["fcf_yield_tiers"]   # e.g. [5, 2, 0]
        pts = vc["fcf_yield_pts"]       # e.g. [15, 9, 4, 0]
        total += w
        if fcfy >= tiers[0]:
            raw += pts[0]
            pos.append(f"FCF yield {fcfy:.1f}% — strong cash return")
        elif fcfy >= tiers[1]:
            raw += pts[1]
        elif fcfy >= tiers[2]:
            raw += pts[2]
        else:
            raw += pts[3]
            neg.append("Negative FCF yield")
    else:
        warn.append("FCF yield unavailable")

    # EV/Sales (lower is better)
    evs = vd.ev_sales
    if evs is not None:
        w = vc["ev_sales_weight"]
        tiers = vc["ev_sales_tiers"]   # e.g. [3, 8, 15]
        pts = vc["ev_sales_pts"]       # e.g. [15, 9, 4, 1]
        total += w
        if evs <= tiers[0]:
            raw += pts[0]
            pos.append(f"EV/Sales {evs:.1f} — low multiple")
        elif evs <= tiers[1]:
            raw += pts[1]
        elif evs <= tiers[2]:
            raw += pts[2]
            neg.append(f"EV/Sales {evs:.1f} — premium multiple")
        else:
            raw += pts[3]
            neg.append(f"EV/Sales {evs:.1f} — very expensive")
    else:
        warn.append("EV/Sales unavailable")

    parts = ["Valuation card scores multiple metrics: P/E, PEG, P/S, EV/EBITDA, FCF yield, EV/Sales."]
    return _score_to_card("valuation", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 9. Quality
# ---------------------------------------------------------------------------

def score_quality(fd: FundamentalData, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on margins, ROE, ROIC, ROA, balance sheet health."""
    cfg = algo_config or get_algo_config()
    qc = cfg.signal_cards["quality"]
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Gross margin (stored as fraction e.g. 0.50 = 50%)
    gm = fd.gross_margin
    if gm is not None:
        w = qc["gross_margin_weight"]
        total += w
        if gm >= qc["gross_margin_high"]:
            raw += w
            pos.append(f"Gross margin {gm*100:.0f}% — excellent")
        elif gm >= qc["gross_margin_moderate"]:
            raw += round(w * 0.6)
        else:
            raw += round(w * 0.2)
            neg.append(f"Gross margin {gm*100:.0f}% — thin")
    else:
        warn.append("Gross margin unavailable")

    # Operating margin
    om = fd.operating_margin
    if om is not None:
        w = qc["op_margin_weight"]
        total += w
        if om >= qc["op_margin_high"]:
            raw += w
            pos.append(f"Operating margin {om*100:.0f}%")
        elif om >= qc["op_margin_moderate"]:
            raw += round(w * 0.6)
        elif om >= 0:
            raw += round(w * 0.27)
        else:
            neg.append(f"Operating margin {om*100:.0f}% — loss-making")
    else:
        warn.append("Operating margin unavailable")

    # ROE (stored as fraction)
    roe = fd.roe
    if roe is not None:
        w = qc["roe_weight"]
        total += w
        if roe >= qc["roe_high"] / 100:
            raw += w
            pos.append(f"ROE {roe*100:.0f}% — high return")
        elif roe >= qc["roe_moderate"] / 100:
            raw += round(w * 0.6)
        elif roe >= 0:
            raw += round(w * 0.27)
        else:
            neg.append(f"ROE {roe*100:.0f}% — negative")
    else:
        warn.append("ROE unavailable")

    # ROIC (stored as fraction)
    roic = fd.roic
    if roic is not None:
        w = qc["roic_weight"]
        total += w
        if roic >= qc["roic_high"] / 100:
            raw += w
            pos.append(f"ROIC {roic*100:.0f}% — above cost of capital")
        elif roic >= qc["roic_moderate"] / 100:
            raw += round(w * 0.6)
        elif roic >= 0:
            raw += round(w * 0.27)
        else:
            neg.append(f"ROIC {roic*100:.0f}% — destroying value")
    else:
        warn.append("ROIC unavailable")

    # ROA (stored as fraction)
    roa = fd.roa
    if roa is not None:
        w = qc["roa_weight"]
        total += w
        if roa >= qc["roa_high"] / 100:
            raw += w
            pos.append(f"ROA {roa*100:.0f}% — efficient assets")
        elif roa >= qc["roa_moderate"] / 100:
            raw += round(w * 0.6)
        elif roa >= 0:
            raw += round(w * 0.3)
        else:
            neg.append(f"ROA {roa*100:.0f}% — negative")
    else:
        warn.append("ROA unavailable")

    # Current ratio
    cr = fd.current_ratio
    if cr is not None:
        w = qc["current_ratio_weight"]
        total += w
        if cr >= qc["current_ratio_good"]:
            raw += w
            pos.append(f"Current ratio {cr:.1f} — strong liquidity")
        elif cr >= qc["current_ratio_ok"]:
            raw += round(w * 0.7)
        else:
            raw += round(w * 0.2)
            neg.append(f"Current ratio {cr:.1f} — liquidity risk")
    else:
        warn.append("Current ratio unavailable")

    # Quick ratio
    qr = fd.quick_ratio
    if qr is not None:
        w = qc["quick_ratio_weight"]
        total += w
        if qr >= qc["quick_ratio_high"]:
            raw += w
            pos.append(f"Quick ratio {qr:.1f} — excellent liquidity")
        elif qr >= qc["quick_ratio_moderate"]:
            raw += round(w * 0.7)
        else:
            raw += round(w * 0.2)
            neg.append(f"Quick ratio {qr:.1f} — tight")
    else:
        warn.append("Quick ratio unavailable")

    # Debt/equity (data comes as percentage e.g. 50 = 50%; config stores as ratio 0.5)
    de = fd.debt_to_equity
    if de is not None:
        w = qc["debt_equity_weight"]
        total += w
        de_low = qc["debt_equity_low"] * 100
        de_mid = qc["debt_equity_mid"] * 100
        de_high = qc["debt_equity_high"] * 100
        if de <= de_low:
            raw += w
            pos.append(f"D/E {de:.0f}% — low leverage")
        elif de <= de_mid:
            raw += round(w * 0.57)
        elif de <= de_high:
            raw += round(w * 0.29)
            neg.append(f"D/E {de:.0f}% — high leverage")
        else:
            neg.append(f"D/E {de:.0f}% — very high leverage")
    else:
        warn.append("Debt/equity unavailable")

    # Long-term debt/equity (data as percentage; config stores as ratio)
    ltde = fd.long_term_debt_equity
    if ltde is not None:
        w = qc["lt_debt_equity_weight"]
        total += w
        ltde_low = qc["lt_debt_equity_low"] * 100
        ltde_mod = qc["lt_debt_equity_moderate"] * 100
        ltde_high = qc["lt_debt_equity_high"] * 100
        if ltde <= ltde_low:
            raw += w
            pos.append(f"LT Debt/Equity {ltde:.0f}% — conservative long-term leverage")
        elif ltde <= ltde_mod:
            raw += round(w * 0.625)
        elif ltde <= ltde_high:
            raw += round(w * 0.25)
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

def score_ownership(fd: FundamentalData, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on insider/institutional ownership, short float."""
    cfg = algo_config or get_algo_config()
    oc = cfg.signal_cards["ownership"]
    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Insider ownership (data as fraction; config in whole-number %)
    ins_own = fd.insider_ownership
    if ins_own is not None:
        w = oc["insider_own_weight"]
        total += w
        if ins_own >= oc["insider_own_high"] / 100:
            raw += w
            pos.append(f"Insider ownership {ins_own*100:.0f}% — strong alignment")
        elif ins_own >= oc["insider_own_mid"] / 100:
            raw += round(w * 0.67)
            pos.append(f"Insider ownership {ins_own*100:.0f}%")
        else:
            raw += round(w * 0.33)
            neg.append(f"Low insider ownership {ins_own*100:.1f}%")
    else:
        warn.append("Insider ownership unavailable")

    # Insider transactions (net buying)
    ins_tx = fd.insider_transactions
    if ins_tx is not None:
        w = oc["insider_txn_weight"]
        total += w
        if ins_tx > 0:
            raw += w
            pos.append("Insiders net buying — bullish signal")
        elif ins_tx < 0:
            neg.append("Insiders net selling")
        else:
            raw += round(w * 0.5)
    else:
        warn.append("Insider transactions unavailable")

    # Institutional ownership (data as fraction; config in whole-number %)
    inst_own = fd.institutional_ownership
    if inst_own is not None:
        w = oc["inst_own_weight"]
        total += w
        inst_low = oc["inst_own_low"] / 100
        inst_hi_min = oc["inst_own_high_min"] / 100
        inst_hi_max = oc["inst_own_high_max"] / 100
        if inst_hi_min <= inst_own <= inst_hi_max:
            raw += w
            pos.append(f"Institutional ownership {inst_own*100:.0f}% — well-sponsored")
        elif inst_own < inst_low:
            raw += round(w * 0.33)
            neg.append(f"Low institutional ownership {inst_own*100:.0f}%")
        else:
            raw += round(w * 0.6)
    else:
        warn.append("Institutional ownership unavailable")

    # Institutional transactions (net buying)
    inst_tx = fd.institutional_transactions
    if inst_tx is not None:
        w = oc["inst_txn_weight"]
        total += w
        if inst_tx > 0:
            raw += w
            pos.append("Institutions net accumulating")
        elif inst_tx < 0:
            neg.append("Institutions net distributing")
        else:
            raw += round(w * 0.5)
    else:
        warn.append("Institutional transactions unavailable")

    # Short float (data as fraction; config in whole-number %)
    sf = fd.short_float
    if sf is not None:
        w = oc["short_float_weight"]
        total += w
        sf_low = oc["short_float_low"] / 100
        sf_mid = oc["short_float_mid"] / 100
        sf_high = oc["short_float_high"] / 100
        if sf <= sf_low:
            raw += w
            pos.append(f"Short float {sf*100:.1f}% — low short interest")
        elif sf <= sf_mid:
            raw += round(w * 0.6)
        elif sf <= sf_high:
            raw += round(w * 0.3)
            neg.append(f"Short float {sf*100:.0f}% — elevated")
        else:
            raw += round(w * 0.4)
            pos.append(f"Short float {sf*100:.0f}% — squeeze potential")
            neg.append(f"Short float {sf*100:.0f}% — high risk signal")
    else:
        warn.append("Short float unavailable")

    # Short ratio (days to cover; config already in days)
    sr = fd.short_ratio
    if sr is not None:
        w = oc["short_ratio_weight"]
        total += w
        if sr <= oc["short_ratio_low"]:
            raw += w
        elif sr <= oc["short_ratio_mid"]:
            raw += round(w * 0.6)
        else:
            raw += round(w * 0.2)
            neg.append(f"Short ratio {sr:.1f} days — crowded short")
    else:
        warn.append("Short ratio unavailable")

    parts = ["Ownership card measures insider/institutional positioning and short interest dynamics."]
    return _score_to_card("ownership", raw, total, pos, neg, warn, parts)


# ---------------------------------------------------------------------------
# 11. Catalyst
# ---------------------------------------------------------------------------

def score_catalyst(fd: FundamentalData, earnings: EarningsData, news: NewsSummary, algo_config: Optional[AlgoConfig] = None) -> SignalCard:
    """Score based on analyst recommendations, news sentiment, earnings proximity, target price."""
    cfg = algo_config or get_algo_config()
    cc = cfg.signal_cards["catalyst"]

    raw = 0.0
    total = 0.0
    pos, neg, warn = [], [], []

    # Analyst recommendation (1=Strong Buy, 5=Strong Sell)
    rec = fd.analyst_recommendation
    if rec is not None:
        w = cc["analyst_rec_weight"]
        tiers = cc["analyst_rec_tiers"]   # e.g. [1.5, 2.5, 3.5, 4.0]
        pts = cc["analyst_rec_pts"]       # e.g. [25, 18, 10, 4, 0]
        total += w
        if rec <= tiers[0]:
            raw += pts[0]
            pos.append(f"Analyst consensus {rec:.1f} — Strong Buy")
        elif rec <= tiers[1]:
            raw += pts[1]
            pos.append(f"Analyst consensus {rec:.1f} — Buy")
        elif rec <= tiers[2]:
            raw += pts[2]
        elif rec <= tiers[3]:
            raw += pts[3]
            neg.append(f"Analyst consensus {rec:.1f} — Underperform")
        else:
            raw += pts[4]
            neg.append(f"Analyst consensus {rec:.1f} — Sell")
    else:
        warn.append("Analyst recommendation unavailable")

    # Target price distance
    tpd = fd.target_price_distance
    if tpd is not None:
        w = cc["target_dist_weight"]
        tiers = cc["target_dist_tiers"]   # e.g. [20, 10, 0]
        pts = cc["target_dist_pts"]       # e.g. [20, 14, 8, 0]
        total += w
        if tpd >= tiers[0]:
            raw += pts[0]
            pos.append(f"Analyst target +{tpd:.0f}% upside")
        elif tpd >= tiers[1]:
            raw += pts[1]
            pos.append(f"Analyst target +{tpd:.0f}% upside")
        elif tpd >= tiers[2]:
            raw += pts[2]
        else:
            raw += pts[3]
            neg.append(f"Analyst target {tpd:.0f}% — stock above consensus")
    else:
        warn.append("Analyst target price unavailable")

    # News score (0–100 from NewsSummary)
    ns = news.news_score
    if ns is not None:
        total += cc["news_weight"]
        news_tiers = cc["news_tiers"]  # descending thresholds e.g. [70, 55, 45, 30]
        news_pts = cc["news_pts"]      # points per tier  e.g. [25, 18, 12, 5, 0]
        if ns >= news_tiers[0]:
            raw += news_pts[0]
            pos.append(f"News score {ns:.0f}/100 — positive coverage")
        elif ns >= news_tiers[1]:
            raw += news_pts[1]
            pos.append(f"News score {ns:.0f}/100 — mildly positive")
        elif ns >= news_tiers[2]:
            raw += news_pts[2]
        elif ns >= news_tiers[3]:
            raw += news_pts[3]
            neg.append(f"News score {ns:.0f}/100 — negative sentiment")
        else:
            raw += news_pts[4]
            neg.append(f"News score {ns:.0f}/100 — very negative")
    else:
        warn.append("News score unavailable")

    # Earnings beat rate (recent catalyst quality)
    beat_rate = earnings.beat_rate
    if beat_rate is not None:
        w = cc["beat_rate_weight"]
        tiers = cc["beat_rate_tiers"]   # e.g. [75, 50] (whole-number %)
        pts = cc["beat_rate_pts"]       # e.g. [15, 9, 0]
        total += w
        if beat_rate * 100 >= tiers[0]:
            raw += pts[0]
            pos.append(f"Beat rate {beat_rate*100:.0f}% — reliable catalyst")
        elif beat_rate * 100 >= tiers[1]:
            raw += pts[1]
        else:
            raw += pts[2]
            neg.append(f"Beat rate {beat_rate*100:.0f}% — inconsistent")
    else:
        warn.append("Earnings beat rate unavailable")

    # Earnings proximity: within 30 days = upcoming catalyst
    within_30 = earnings.within_30_days
    if within_30 is True:
        total += cc["earnings_timing_weight"]
        raw += cc["within_30_days_pts"]
        pos.append("Earnings within 30 days — upcoming catalyst")
    elif within_30 is False:
        total += cc["earnings_timing_weight"]
        raw += cc["beyond_30_days_pts"]
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
    algo_config: Optional[AlgoConfig] = None,
    archetype: Optional[str] = None,
) -> SignalCards:
    """Compute all 11 signal cards and return a SignalCards container.

    Pass ``archetype`` (e.g. "HYPER_GROWTH") to enable archetype-aware valuation
    scoring instead of the absolute-multiple default.
    """
    # Valuation card: use archetype-aware scoring when archetype is known
    if archetype:
        from app.services.valuation_analysis_service import score_valuation_with_archetype as _arch_val
        arch_score = _arch_val(
            valuation,
            archetype,
            revenue_growth_yoy=fundamentals.revenue_growth_yoy,
            operating_margin=fundamentals.operating_margin,
            gross_margin=fundamentals.gross_margin,
            algo_config=algo_config,
        )
        base_val_card = score_valuation(valuation, algo_config=algo_config)
        val_card = base_val_card.model_copy(update={
            "score": round(float(arch_score), 1),
            "label": SignalCardLabel.from_score(float(arch_score)),
        })
    else:
        val_card = score_valuation(valuation, algo_config=algo_config)

    return SignalCards(
        momentum=score_momentum(technicals, algo_config=algo_config),
        trend=score_trend(technicals, algo_config=algo_config),
        entry_timing=score_entry_timing(technicals, algo_config=algo_config),
        volume_accumulation=score_volume_accumulation(technicals, algo_config=algo_config),
        volatility_risk=score_volatility_risk(technicals, algo_config=algo_config, beta=fundamentals.beta),
        relative_strength=score_relative_strength(technicals, algo_config=algo_config),
        growth=score_growth(fundamentals, earnings, algo_config=algo_config),
        valuation=val_card,
        quality=score_quality(fundamentals, algo_config=algo_config),
        ownership=score_ownership(fundamentals, algo_config=algo_config),
        catalyst=score_catalyst(fundamentals, earnings, news, algo_config=algo_config),
    )
