from __future__ import annotations

from typing import Optional

import pandas as pd

from app.algo_config import AlgoConfig, get_algo_config
from app.models.market import MarketRegime, MarketRegimeAssessment

_REGIME_IMPLICATIONS = {
    MarketRegime.BULL_RISK_ON: (
        "Growth and momentum signals receive higher weight. "
        "Valuation penalty reduced. Strong stocks can extend further."
    ),
    MarketRegime.BULL_NARROW_LEADERSHIP: (
        "Only select growth leaders are rewarded. "
        "Broad market participation is weak — favor sector leaders."
    ),
    MarketRegime.SIDEWAYS_CHOPPY: (
        "Entry timing and risk/reward matter most. "
        "Avoid chasing breakouts. Prefer pullback entries."
    ),
    MarketRegime.BEAR_RISK_OFF: (
        "Valuation, balance sheet, and cash flow quality dominate. "
        "Momentum signals unreliable. AVOID signals more meaningful."
    ),
    MarketRegime.SECTOR_ROTATION: (
        "Sector selection is critical. "
        "Leading sectors may continue; lagging sectors face headwinds."
    ),
    MarketRegime.LIQUIDITY_RALLY: (
        "Risk-on but driven by liquidity, not fundamentals. "
        "Momentum is strong but breadth may be narrow."
    ),
}


def classify_regime(
    spy_df: Optional[pd.DataFrame],
    qqq_df: Optional[pd.DataFrame],
    vix_level: Optional[float] = None,
    algo_config: Optional[AlgoConfig] = None,
) -> MarketRegimeAssessment:
    """Classify market regime from SPY/QQQ price DataFrames and VIX.

    Args:
        spy_df: Daily OHLCV DataFrame for SPY (must have 'Close' column).
        qqq_df: Daily OHLCV DataFrame for QQQ (must have 'Close' column).
        vix_level: Current VIX reading (optional).
        algo_config: Optional AlgoConfig override; uses singleton if None.

    Returns:
        MarketRegimeAssessment with regime, confidence, and diagnostics.
    """
    cfg = algo_config or get_algo_config()
    mr = cfg.market_regime
    spy_min_bars = mr["spy_min_bars"]
    insufficient_confidence = mr["insufficient_data_confidence"]
    confidences = mr["regime_confidences"]

    if spy_df is None or spy_df.empty or len(spy_df) < spy_min_bars:
        return MarketRegimeAssessment(
            regime=MarketRegime.SIDEWAYS_CHOPPY,
            confidence=insufficient_confidence,
            implication=_REGIME_IMPLICATIONS[MarketRegime.SIDEWAYS_CHOPPY],
        )

    spy_close = spy_df["Close"] if "Close" in spy_df.columns else spy_df.iloc[:, 3]

    spy_50dma = spy_close.rolling(50).mean().iloc[-1] if len(spy_close) >= 50 else None
    spy_200dma = spy_close.rolling(200).mean().iloc[-1] if len(spy_close) >= 200 else None
    spy_price = float(spy_close.iloc[-1])

    spy_above_50 = (spy_price > float(spy_50dma)) if spy_50dma is not None else None
    spy_above_200 = (spy_price > float(spy_200dma)) if spy_200dma is not None else None

    qqq_above_200: Optional[bool] = None
    if qqq_df is not None and not qqq_df.empty and len(qqq_df) >= 200:
        qqq_close = qqq_df["Close"] if "Close" in qqq_df.columns else qqq_df.iloc[:, 3]
        qqq_200dma = qqq_close.rolling(200).mean().iloc[-1]
        qqq_price = float(qqq_close.iloc[-1])
        qqq_above_200 = qqq_price > float(qqq_200dma)

    vix = vix_level

    regime, confidence = _determine_regime(
        spy_above_50, spy_above_200, qqq_above_200, vix, mr
    )

    return MarketRegimeAssessment(
        regime=regime,
        confidence=confidence,
        implication=_REGIME_IMPLICATIONS.get(regime, ""),
        spy_above_50dma=spy_above_50,
        spy_above_200dma=spy_above_200,
        qqq_above_200dma=qqq_above_200,
        vix_level=vix,
    )


def _determine_regime(
    spy_above_50: Optional[bool],
    spy_above_200: Optional[bool],
    qqq_above_200: Optional[bool],
    vix: Optional[float],
    mr: Optional[dict] = None,
) -> tuple[str, float]:
    """Return (regime, confidence) from boolean indicators."""
    if mr is None:
        mr = get_algo_config().market_regime

    confidences = mr["regime_confidences"]
    vix_bear_high = mr["vix_bear_high_threshold"]
    vix_moderate = mr["vix_moderate_threshold"]
    vix_elevated_max = mr["vix_elevated_max"]

    # BEAR: clear downtrend signals
    if spy_above_200 is False and (vix is None or vix > vix_moderate):
        if vix is not None and vix > vix_bear_high:
            return MarketRegime.BEAR_RISK_OFF, confidences["bear_high_vix"]
        if qqq_above_200 is False:
            return MarketRegime.BEAR_RISK_OFF, confidences["bear_double_below"]
        # SPY below 200DMA but QQQ still above → narrow market divergence
        return MarketRegime.SIDEWAYS_CHOPPY, confidences["sideways_divergence"]

    # BULL signals present
    if spy_above_200 is True and spy_above_50 is True:
        if vix is not None and vix < vix_moderate:
            if qqq_above_200 is True:
                return MarketRegime.BULL_RISK_ON, confidences["bull_full"]
            return MarketRegime.BULL_NARROW_LEADERSHIP, confidences["bull_narrow"]
        if vix is not None and vix < vix_bear_high:
            # VIX elevated but still below bear threshold → recovering rally
            return MarketRegime.LIQUIDITY_RALLY, confidences["liquidity_vix_recovering"]
        # No VIX data but both MAs bullish
        if qqq_above_200 is True:
            return MarketRegime.BULL_RISK_ON, confidences["bull_no_vix"]
        return MarketRegime.BULL_NARROW_LEADERSHIP, confidences["bull_narrow_no_vix"]

    # SPY above 200DMA but below 50DMA → choppy/sector rotation
    if spy_above_200 is True and spy_above_50 is False:
        return MarketRegime.SIDEWAYS_CHOPPY, confidences["sideways_above200_below50"]

    # SPY within 2% of 200DMA (near threshold) → sideways
    if spy_above_200 is None:
        return MarketRegime.SIDEWAYS_CHOPPY, confidences["sideways_no_200dma"]

    # VIX falling from high (>20 → dropping) suggests liquidity rally
    if vix is not None and vix_moderate < vix < vix_elevated_max and spy_above_200 is True:
        return MarketRegime.LIQUIDITY_RALLY, confidences["liquidity_vix_elevated"]

    return MarketRegime.SIDEWAYS_CHOPPY, confidences["sideways_fallback"]


# ---------------------------------------------------------------------------
# Backward-compatible module-level alias (imported by scoring_service)
# Keys use MarketRegime string values matching the config JSON keys
# ---------------------------------------------------------------------------

def _build_regime_weight_adjustments() -> dict[str, dict[str, float]]:
    raw = get_algo_config().market_regime["regime_weight_adjustments"]
    # Map string keys from config to MarketRegime constants (they match)
    return {
        MarketRegime.BULL_RISK_ON: raw.get("BULL_RISK_ON", {}),
        MarketRegime.BEAR_RISK_OFF: raw.get("BEAR_RISK_OFF", {}),
        MarketRegime.SIDEWAYS_CHOPPY: raw.get("SIDEWAYS_CHOPPY", {}),
        MarketRegime.BULL_NARROW_LEADERSHIP: raw.get("BULL_NARROW_LEADERSHIP", {}),
        MarketRegime.LIQUIDITY_RALLY: raw.get("LIQUIDITY_RALLY", {}),
        MarketRegime.SECTOR_ROTATION: raw.get("SECTOR_ROTATION", {}),
    }


REGIME_WEIGHT_ADJUSTMENTS: dict[str, dict[str, float]] = _build_regime_weight_adjustments()
