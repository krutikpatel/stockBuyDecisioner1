"""
Main backtest loop.

For each (ticker, weekly_date) pair:
  1. Slice price data to test_date (no look-ahead bias)
  2. Compute technical indicators
  3. Build fundamentals snapshot (Phase 3) or neutral placeholders (Phase 1-2)
  4. Classify archetype + compute growth-adjusted valuation (Phase 3)
  5. Classify market regime from historical SPY/QQQ
  6. Score all 11 signal cards
  7. Compute horizon composite scores from signal cards
  8. Build per-horizon recommendations
  9. Emit one SignalRecord dict per horizon

The output is a flat list of dicts that outcome.py and metrics.py consume.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

import pandas as pd

from app.services.technical_analysis_service import compute_technicals, compute_relative_strength
from app.services.fundamental_analysis_service import score_fundamentals
from app.services.valuation_analysis_service import (
    score_valuation as score_valuation_legacy,
    score_valuation_with_archetype,
)
from app.services.scoring_service import compute_scores_from_signal_cards
from app.services.recommendation_service import build_recommendations
from app.services.stock_archetype_service import classify_and_attach
from app.services.market_regime_service import classify_regime
from app.services.signal_card_service import score_all_cards

from backtest.config import (
    BACKTEST_TICKERS,
    SECTOR_ETF_MAP,
    BACKTEST_START,
    BACKTEST_END,
    HORIZONS,
    MIN_ROWS_FOR_ANALYSIS,
    DEFAULT_RISK_PROFILE,
    DEFAULT_PHASE,
)
from backtest.snapshot import (
    get_price_slice,
    build_historical_fundamentals,
    neutral_news,
    neutral_fundamentals,
    neutral_valuation,
    neutral_earnings,
    _normalize_ts,
)

logger = logging.getLogger(__name__)

SIGNAL_CARD_NAMES = [
    "momentum", "trend", "entry_timing", "volume_accumulation",
    "volatility_risk", "relative_strength", "growth", "valuation",
    "quality", "ownership", "catalyst",
]


def _generate_weekly_dates(start: str, end: str) -> list[pd.Timestamp]:
    """Every Monday between *start* and *end* (inclusive), adjusted to Monday."""
    dates: list[pd.Timestamp] = []
    current = pd.Timestamp(start)
    while current.weekday() != 0:       # advance to Monday
        current += timedelta(days=1)
    end_ts = pd.Timestamp(end)
    while current <= end_ts:
        dates.append(current)
        current += timedelta(weeks=1)
    return dates


def run_backtest(
    data: dict,
    tickers: Optional[list[str]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    risk_profile: str = DEFAULT_RISK_PROFILE,
    phase: int = DEFAULT_PHASE,
) -> list[dict]:
    """Run the backtest and return a list of signal records.

    Args:
        data:         Output of data_loader.load_all_data().
        tickers:      Override list of stock tickers (default = BACKTEST_TICKERS).
        start:        Override backtest start date (ISO string).
        end:          Override backtest end date (ISO string).
        risk_profile: Risk profile passed to build_recommendations().
        phase:        1 = technical-only, 2 = + regime labels, 3 = + fundamentals.

    Returns:
        List of dicts, one per (ticker, date, horizon).  Outcome fields are None
        and are filled in later by outcome.attach_outcomes().
    """
    tickers = tickers or BACKTEST_TICKERS
    start   = start   or BACKTEST_START
    end     = end     or BACKTEST_END

    prices:   dict[str, pd.DataFrame] = data["prices"]
    quarterly: dict[str, dict]        = data["quarterly"]

    test_dates   = _generate_weekly_dates(start, end)
    spy_full     = prices.get("SPY", pd.DataFrame())
    qqq_full     = prices.get("QQQ", pd.DataFrame())

    # ── Pre-compute per-date shared state (SPY/QQQ slices, VIX, regime) ───
    # These depend only on the date, not the ticker, so compute once per date.
    _date_state: dict[pd.Timestamp, tuple] = {}
    for td in test_dates:
        spy_sl  = get_price_slice(spy_full, td)
        qqq_sl  = get_price_slice(qqq_full, td)

        vix: Optional[float] = None
        if not spy_sl.empty and len(spy_sl) >= 21:
            spy_close = spy_sl["Close"].squeeze()
            daily_ret = spy_close.pct_change().dropna()
            rolling_vol = daily_ret.rolling(20).std().iloc[-1]
            if pd.notna(rolling_vol):
                vix = round(float(rolling_vol) * (252 ** 0.5) * 100, 2)

        regime = None
        if not spy_sl.empty and not qqq_sl.empty:
            try:
                regime = classify_regime(spy_sl, qqq_sl, vix_level=vix)
            except Exception as exc:
                logger.debug("classify_regime pre-compute failed for %s: %s", td.date(), exc)

        _date_state[td] = (spy_sl, qqq_sl, vix, regime)

    signals: list[dict] = []
    total  = len(tickers) * len(test_dates)
    done   = 0

    print(
        f"\nRunning backtest (phase={phase}): "
        f"{len(tickers)} tickers × {len(test_dates)} dates = {total} snapshots"
    )
    print(f"Date range: {start} → {end} | Risk profile: {risk_profile}\n")

    for ticker in tickers:
        price_full = prices.get(ticker, pd.DataFrame())
        q_data     = quarterly.get(ticker, {})
        sector_etf = SECTOR_ETF_MAP.get(ticker, "XLK")
        sector_full = prices.get(sector_etf, pd.DataFrame()) if sector_etf else pd.DataFrame()

        if price_full.empty:
            logger.warning("No price data for %s — skipping", ticker)
            done += len(test_dates)
            continue

        for test_date in test_dates:
            done += 1
            if done % 100 == 0 or done == total:
                pct = done / total * 100
                print(
                    f"  Progress: {done}/{total} ({pct:.0f}%) "
                    f"— {ticker} {test_date.date()}          ",
                    end="\r", flush=True,
                )

            try:
                # ── Price slices (no look-ahead) ───────────────────────────
                price_slice  = get_price_slice(price_full, test_date)
                if len(price_slice) < MIN_ROWS_FOR_ANALYSIS:
                    continue

                # Shared per-date state (pre-computed above)
                spy_slice, qqq_slice, vix_proxy, regime_assessment = _date_state[test_date]

                sector_slice = (
                    get_price_slice(sector_full, test_date)
                    if not sector_full.empty else pd.DataFrame()
                )

                current_price = float(price_slice["Close"].iloc[-1])

                # ── Technical indicators ───────────────────────────────────
                technicals = compute_technicals(
                    price_slice,
                    spy_df=spy_slice    if not spy_slice.empty    else None,
                    qqq_df=qqq_slice    if not qqq_slice.empty    else None,
                    sector_df=sector_slice if not sector_slice.empty else None,
                )

                # ── Fundamentals (phase-gated) ─────────────────────────────
                if phase >= 3 and q_data:
                    fundamentals, valuation, earnings = build_historical_fundamentals(
                        ticker=ticker,
                        test_date=test_date,
                        quarterly_data=q_data,
                        price_at_date=current_price,
                    )
                    # Fundamental score + archetype-adjusted valuation
                    fundamentals.fundamental_score = score_fundamentals(fundamentals)
                    valuation.valuation_score       = score_valuation_legacy(valuation)
                    fundamentals = classify_and_attach(fundamentals, valuation)
                    valuation.archetype_adjusted_score = score_valuation_with_archetype(
                        valuation,
                        fundamentals.archetype,
                        revenue_growth_yoy=fundamentals.revenue_growth_yoy,
                        operating_margin=fundamentals.operating_margin,
                        gross_margin=fundamentals.gross_margin,
                    )
                else:
                    fundamentals = neutral_fundamentals()
                    valuation    = neutral_valuation()
                    earnings     = neutral_earnings()

                news = neutral_news()  # historical news is unavailable

                # ── Sector macro score from real RS ────────────────────────
                sector_macro_score = 50.0
                if (
                    not sector_slice.empty
                    and len(sector_slice) >= 63
                    and len(spy_slice) >= 63
                ):
                    rs = compute_relative_strength(
                        sector_slice["Close"], spy_slice["Close"], period=63
                    )
                    if rs is not None:
                        sector_macro_score = 65.0 if rs > 1.05 else (35.0 if rs < 0.95 else 50.0)

                # regime_assessment and vix_proxy come from _date_state (pre-computed)

                # ── Signal cards ───────────────────────────────────────────
                signal_cards = score_all_cards(
                    technicals=technicals,
                    fundamentals=fundamentals,
                    valuation=valuation,
                    earnings=earnings,
                    news=news,
                )

                # ── Horizon scores from signal cards ───────────────────────
                scores = compute_scores_from_signal_cards(signal_cards, regime_assessment)

                # ── Recommendations ────────────────────────────────────────
                recommendations = build_recommendations(
                    technicals=technicals,
                    fundamentals=fundamentals,
                    valuation=valuation,
                    earnings=earnings,
                    news=news,
                    scores=scores,
                    horizons=HORIZONS,
                    risk_profile=risk_profile,
                    current_price=current_price,
                    regime_assessment=regime_assessment,
                    signal_cards=signal_cards,
                )

                # ── Flatten signal card scores into a dict ─────────────────
                card_scores: dict[str, Optional[float]] = {}
                for name in SIGNAL_CARD_NAMES:
                    card = getattr(signal_cards, name, None)
                    card_scores[f"sc_{name}"] = card.score if card else None

                # ── Emit one record per horizon ────────────────────────────
                regime_str = (
                    str(regime_assessment.regime)
                    if regime_assessment else "SIDEWAYS_CHOPPY"
                )
                archetype_str = str(fundamentals.archetype) if fundamentals.archetype else "UNKNOWN"

                for rec in recommendations:
                    record = {
                        # Identity
                        "ticker":   ticker,
                        "date":     test_date.date().isoformat(),
                        "horizon":  rec.horizon,
                        # Decision
                        "decision":   rec.decision,
                        "score":      rec.score,
                        "confidence": rec.confidence,
                        # Context
                        "market_regime": regime_str,
                        "archetype":     archetype_str,
                        "phase":         phase,
                        "price":         current_price,
                        # Diagnostics
                        "technical_score":   technicals.technical_score,
                        "fundamental_score": fundamentals.fundamental_score,
                        "valuation_score":   valuation.valuation_score,
                        "earnings_score":    earnings.earnings_score,
                        "trend":             technicals.trend.label,
                        "rsi":               technicals.rsi_14,
                        "is_extended":       technicals.is_extended,
                        "entry_preferred":   rec.entry_plan.preferred_entry if rec.entry_plan else None,
                        "stop_loss":         rec.exit_plan.stop_loss if rec.exit_plan else None,
                        "first_target":      rec.exit_plan.first_target if rec.exit_plan else None,
                        # Signal card scores
                        **card_scores,
                        # Outcomes (filled by outcome.py)
                        "forward_return":      None,
                        "spy_return":          None,
                        "qqq_return":          None,
                        "excess_return":       None,
                        "excess_return_vs_qqq": None,
                        "max_drawdown_period": None,
                    }
                    signals.append(record)

            except Exception as exc:
                logger.debug("Error at %s %s: %s", ticker, test_date.date(), exc)
                continue

    print(f"\n\nDone. Generated {len(signals)} signal records.")
    return signals
