from __future__ import annotations

from typing import Optional

import pandas as pd

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
) -> MarketRegimeAssessment:
    """Classify market regime from SPY/QQQ price DataFrames and VIX.

    Args:
        spy_df: Daily OHLCV DataFrame for SPY (must have 'Close' column).
        qqq_df: Daily OHLCV DataFrame for QQQ (must have 'Close' column).
        vix_level: Current VIX reading (optional).

    Returns:
        MarketRegimeAssessment with regime, confidence, and diagnostics.
    """
    if spy_df is None or spy_df.empty or len(spy_df) < 50:
        return MarketRegimeAssessment(
            regime=MarketRegime.SIDEWAYS_CHOPPY,
            confidence=20.0,
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
        spy_above_50, spy_above_200, qqq_above_200, vix
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
) -> tuple[str, float]:
    """Return (regime, confidence) from boolean indicators."""
    # BEAR: clear downtrend signals
    if spy_above_200 is False and (vix is None or vix > 20):
        if vix is not None and vix > 25:
            return MarketRegime.BEAR_RISK_OFF, 82.0
        if qqq_above_200 is False:
            return MarketRegime.BEAR_RISK_OFF, 70.0
        # SPY below 200DMA but QQQ still above → narrow market divergence
        return MarketRegime.SIDEWAYS_CHOPPY, 55.0

    # BULL signals present
    if spy_above_200 is True and spy_above_50 is True:
        if vix is not None and vix < 20:
            if qqq_above_200 is True:
                return MarketRegime.BULL_RISK_ON, 85.0
            return MarketRegime.BULL_NARROW_LEADERSHIP, 68.0
        if vix is not None and vix < 25:
            # VIX elevated but still below 200DMA → recovering rally
            return MarketRegime.LIQUIDITY_RALLY, 62.0
        # No VIX data but both MAs bullish
        if qqq_above_200 is True:
            return MarketRegime.BULL_RISK_ON, 70.0
        return MarketRegime.BULL_NARROW_LEADERSHIP, 58.0

    # SPY above 200DMA but below 50DMA → choppy/sector rotation
    if spy_above_200 is True and spy_above_50 is False:
        return MarketRegime.SIDEWAYS_CHOPPY, 60.0

    # SPY within 2% of 200DMA (near threshold) → sideways
    if spy_above_200 is None:
        return MarketRegime.SIDEWAYS_CHOPPY, 40.0

    # VIX falling from high (>20 → dropping) suggests liquidity rally
    if vix is not None and 20 < vix < 30 and spy_above_200 is True:
        return MarketRegime.LIQUIDITY_RALLY, 55.0

    return MarketRegime.SIDEWAYS_CHOPPY, 45.0


# Weight multiplier maps for each regime (applied in scoring service)
REGIME_WEIGHT_ADJUSTMENTS: dict[str, dict[str, float]] = {
    MarketRegime.BULL_RISK_ON: {
        "technical_momentum": 1.20,
        "relative_strength": 1.15,
        "growth_acceleration": 1.15,
        "valuation_relative_growth": 0.70,
        "fcf_quality": 0.90,
    },
    MarketRegime.BEAR_RISK_OFF: {
        "valuation_relative_growth": 1.30,
        "balance_sheet_strength": 1.25,
        "fcf_quality": 1.20,
        "technical_momentum": 0.90,
        "catalyst_news": 0.90,
    },
    MarketRegime.SIDEWAYS_CHOPPY: {
        "risk_reward": 1.25,
        "relative_strength": 1.10,
        "technical_momentum": 0.85,
    },
    MarketRegime.BULL_NARROW_LEADERSHIP: {
        "technical_momentum": 1.15,
        "relative_strength": 1.20,
        "sector_strength": 1.15,
    },
    MarketRegime.LIQUIDITY_RALLY: {
        "technical_momentum": 1.10,
        "catalyst_news": 1.10,
        "valuation_relative_growth": 0.80,
    },
    MarketRegime.SECTOR_ROTATION: {
        "sector_strength": 1.30,
        "relative_strength": 1.15,
    },
}
