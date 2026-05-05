"""
Main backtest loop.
Iterates over weekly test dates for each ticker and runs the analysis engine.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from app.services.technical_analysis_service import compute_technicals
from app.services.fundamental_analysis_service import score_fundamentals
from app.services.valuation_analysis_service import score_valuation
from app.services.scoring_service import compute_scores
from app.services.recommendation_service import build_recommendations

from backtest.config import (
    BACKTEST_TICKERS,
    SECTOR_ETF_MAP,
    BACKTEST_START,
    BACKTEST_END,
    HORIZONS,
    MIN_ROWS_FOR_ANALYSIS,
    DEFAULT_RISK_PROFILE,
)
from backtest.snapshot import (
    build_historical_fundamentals,
    get_price_slice,
    neutral_news,
    _normalize_ts,
)

logger = logging.getLogger(__name__)


def _generate_weekly_dates(start: str, end: str) -> list[pd.Timestamp]:
    """Generate every Monday in [start, end], business-day adjusted."""
    dates = []
    current = pd.Timestamp(start)
    # Advance to Monday
    while current.weekday() != 0:
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
) -> list[dict]:
    """
    Run the backtest over weekly dates for all specified tickers.

    Returns a list of signal dicts, one per (ticker, date, horizon).
    """
    tickers = tickers or BACKTEST_TICKERS
    start = start or BACKTEST_START
    end = end or BACKTEST_END

    prices: dict[str, pd.DataFrame] = data["prices"]
    quarterly: dict[str, dict] = data["quarterly"]

    test_dates = _generate_weekly_dates(start, end)
    spy_full = prices.get("SPY", pd.DataFrame())

    signals: list[dict] = []
    total = len(tickers) * len(test_dates)
    done = 0

    print(f"\nRunning backtest: {len(tickers)} tickers × {len(test_dates)} dates = {total} snapshots")
    print(f"Date range: {start} → {end} | Risk profile: {risk_profile}\n")

    for ticker in tickers:
        price_full = prices.get(ticker, pd.DataFrame())
        q_data = quarterly.get(ticker, {})
        # Map sector ETF; default to XLK for tech tickers not in the map
        sector_etf = SECTOR_ETF_MAP.get(ticker, "XLK")
        sector_full = prices.get(sector_etf, pd.DataFrame()) if sector_etf else pd.DataFrame()

        if price_full.empty:
            logger.warning("No price data for %s — skipping", ticker)
            done += len(test_dates)
            continue

        for test_date in test_dates:
            done += 1
            if done % 50 == 0 or done == total:
                pct = done / total * 100
                print(f"  Progress: {done}/{total} ({pct:.0f}%) — current: {ticker} {test_date.date()}", end="\r", flush=True)

            try:
                # Slice price data to test_date (no look-ahead bias)
                price_slice = get_price_slice(price_full, test_date)
                if len(price_slice) < MIN_ROWS_FOR_ANALYSIS:
                    continue  # not enough history yet

                spy_slice = get_price_slice(spy_full, test_date)
                sector_slice = get_price_slice(sector_full, test_date) if not sector_full.empty else pd.DataFrame()

                current_price = float(price_slice["Close"].iloc[-1])

                # Technical indicators
                technicals = compute_technicals(
                    price_slice,
                    spy_df=spy_slice if not spy_slice.empty else None,
                    sector_df=sector_slice if not sector_slice.empty else None,
                )

                # Historical fundamentals
                fundamentals, valuation, earnings = build_historical_fundamentals(
                    ticker=ticker,
                    test_date=test_date,
                    quarterly_data=q_data,
                    price_at_date=current_price,
                )

                # Compute scores
                fundamentals.fundamental_score = score_fundamentals(fundamentals)
                valuation.valuation_score = score_valuation(valuation)

                news = neutral_news()

                scores = compute_scores(
                    technicals=technicals,
                    fundamentals=fundamentals,
                    valuation=valuation,
                    earnings=earnings,
                    news=news,
                    catalyst_score=50.0,
                    sector_macro_score=50.0,
                    risk_reward_score=50.0,
                )

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
                )

                for rec in recommendations:
                    signals.append({
                        "ticker": ticker,
                        "date": test_date.date().isoformat(),
                        "horizon": rec.horizon,
                        "decision": rec.decision,
                        "score": rec.score,
                        "confidence": rec.confidence,
                        "price": current_price,
                        "technical_score": technicals.technical_score,
                        "fundamental_score": fundamentals.fundamental_score,
                        "valuation_score": valuation.valuation_score,
                        "earnings_score": earnings.earnings_score,
                        "trend": technicals.trend.label,
                        "rsi": technicals.rsi_14,
                        "is_extended": technicals.is_extended,
                        "entry_preferred": rec.entry_plan.preferred_entry if rec.entry_plan else None,
                        "stop_loss": rec.exit_plan.stop_loss if rec.exit_plan else None,
                        "first_target": rec.exit_plan.first_target if rec.exit_plan else None,
                        # forward_return and excess_return filled in by outcome.py
                        "forward_return": None,
                        "spy_return": None,
                        "excess_return": None,
                    })

            except Exception as e:
                logger.debug("Error at %s %s: %s", ticker, test_date.date(), e)
                continue

    print(f"\n\nDone. Generated {len(signals)} signals.")
    return signals
