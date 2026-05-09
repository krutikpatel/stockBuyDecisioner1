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

from app.algo_config import AlgoConfig, get_algo_config
from app.services.technical_analysis_service import (
    compute_technicals,
    compute_relative_strength,
    compute_rs_vs_benchmark,
    score_technicals,
)
from app.models.market import TechnicalIndicators
from backtest.indicator_cache import build_indicator_cache, lookup_ticker_indicators
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


def _attach_rs_fields(
    ti: TechnicalIndicators,
    stock_close: pd.Series,
    spy_slice: pd.DataFrame,
    qqq_slice: pd.DataFrame,
    sector_slice: pd.DataFrame,
) -> None:
    """Attach benchmark-dependent RS fields to a cached TechnicalIndicators in-place.

    The cached object has RS fields = None and technical_score as a placeholder
    (computed without rs_spy).  This function sets the RS fields and recomputes
    technical_score so the result is identical to a full compute_technicals call.
    """
    if not spy_slice.empty:
        spy_close = spy_slice["Close"].squeeze()
        ti.rs_vs_spy     = compute_relative_strength(stock_close, spy_close)
        ti.rs_vs_spy_20d = compute_rs_vs_benchmark(stock_close, spy_close, period=20)
        ti.rs_vs_spy_63d = compute_rs_vs_benchmark(stock_close, spy_close, period=63)
    if not qqq_slice.empty:
        qqq_close = qqq_slice["Close"].squeeze()
        ti.rs_vs_qqq = compute_rs_vs_benchmark(stock_close, qqq_close, period=63)
    if not sector_slice.empty:
        sector_close = sector_slice["Close"].squeeze()
        ti.rs_vs_sector     = compute_relative_strength(stock_close, sector_close)
        ti.rs_vs_sector_20d = compute_rs_vs_benchmark(stock_close, sector_close, period=20)
        ti.rs_vs_sector_63d = compute_rs_vs_benchmark(stock_close, sector_close, period=63)
    # Recompute technical_score now that rs_vs_spy is correctly populated
    ti.technical_score = score_technicals(
        ti.trend,
        ti.rsi_14,
        ti.macd_histogram,
        ti.is_extended,
        ti.volume_trend,
        ti.rs_vs_spy,
        ti.support_resistance,
        float(stock_close.iloc[-1]),
    )


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
    force_refresh: bool = False,
    algo_config: Optional[AlgoConfig] = None,
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
    _cfg    = algo_config or get_algo_config()

    prices:   dict[str, pd.DataFrame] = data["prices"]
    quarterly: dict[str, dict]        = data["quarterly"]

    test_dates   = _generate_weekly_dates(start, end)
    spy_full     = prices.get("SPY", pd.DataFrame())
    qqq_full     = prices.get("QQQ", pd.DataFrame())

    # ── Pre-compute / load indicator cache (ticker-only technicals) ────────
    logger.info("Loading indicator cache…")
    _indicator_cache = build_indicator_cache(
        prices=prices,
        tickers=tickers,
        test_dates=test_dates,
        force_refresh=force_refresh,
    )

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
                regime = classify_regime(spy_sl, qqq_sl, vix_level=vix, algo_config=_cfg)
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
                technicals = lookup_ticker_indicators(_indicator_cache, ticker, test_date)
                if technicals is not None:
                    # Cache hit: attach benchmark-dependent RS fields and rescore
                    _attach_rs_fields(
                        technicals,
                        stock_close=price_slice["Close"].squeeze(),
                        spy_slice=spy_slice,
                        qqq_slice=qqq_slice,
                        sector_slice=sector_slice,
                    )
                else:
                    # Cache miss: compute everything inline (includes RS fields)
                    logger.debug(
                        "Cache miss: %s %s — computing full technicals",
                        ticker, test_date.date(),
                    )
                    technicals = compute_technicals(
                        price_slice,
                        spy_df=spy_slice    if not spy_slice.empty    else None,
                        qqq_df=qqq_slice    if not qqq_slice.empty    else None,
                        sector_df=sector_slice if not sector_slice.empty else None,
                        algo_config=_cfg,
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
                    valuation.valuation_score       = score_valuation_legacy(valuation, algo_config=_cfg)
                    fundamentals = classify_and_attach(fundamentals, valuation, algo_config=_cfg)
                    valuation.archetype_adjusted_score = score_valuation_with_archetype(
                        valuation,
                        fundamentals.archetype,
                        revenue_growth_yoy=fundamentals.revenue_growth_yoy,
                        operating_margin=fundamentals.operating_margin,
                        gross_margin=fundamentals.gross_margin,
                        algo_config=_cfg,
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
                    algo_config=_cfg,
                )

                # ── Horizon scores from signal cards ───────────────────────
                scores = compute_scores_from_signal_cards(signal_cards, regime_assessment, algo_config=_cfg)

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
                    algo_config=_cfg,
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
