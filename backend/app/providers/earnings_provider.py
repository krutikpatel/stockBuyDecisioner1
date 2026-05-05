from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from app.models.earnings import EarningsData, EarningsRecord

logger = logging.getLogger(__name__)


def _to_str(dt) -> Optional[str]:
    try:
        if hasattr(dt, "isoformat"):
            return dt.isoformat()
        return str(dt)
    except Exception:
        return None


def get_earnings_data(ticker: str) -> EarningsData:
    t = yf.Ticker(ticker)

    history: list[EarningsRecord] = []
    beat_count = 0
    miss_count = 0
    surprise_pcts: list[float] = []

    # Earnings history
    try:
        eh = t.earnings_history
        if eh is not None and not eh.empty:
            for _, row in eh.head(8).iterrows():
                try:
                    eps_est = float(row.get("epsEstimate", None) or float("nan"))
                except (TypeError, ValueError):
                    eps_est = None
                try:
                    eps_act = float(row.get("epsActual", None) or float("nan"))
                except (TypeError, ValueError):
                    eps_act = None
                try:
                    surp = float(row.get("surprisePercent", None) or float("nan"))
                    if surp == surp:  # NaN check
                        surprise_pcts.append(surp)
                        if surp >= 0:
                            beat_count += 1
                        else:
                            miss_count += 1
                except (TypeError, ValueError):
                    surp = None

                date_val = row.name if hasattr(row, "name") else None
                history.append(
                    EarningsRecord(
                        date=_to_str(date_val),
                        eps_estimate=eps_est if (eps_est is not None and eps_est == eps_est) else None,
                        eps_actual=eps_act if (eps_act is not None and eps_act == eps_act) else None,
                        eps_surprise_pct=surp if (surp is not None and surp == surp) else None,
                    )
                )
    except Exception as e:
        logger.warning("Failed to fetch earnings_history for %s: %s", ticker, e)

    avg_surprise = round(sum(surprise_pcts) / len(surprise_pcts), 2) if surprise_pcts else None
    beat_rate = round(beat_count / (beat_count + miss_count), 4) if (beat_count + miss_count) > 0 else None

    # Last and next earnings dates
    last_date: Optional[str] = None
    next_date: Optional[str] = None
    within_30 = False

    try:
        ed = t.earnings_dates
        if ed is not None and not ed.empty:
            now = datetime.now(timezone.utc)
            past = ed[ed.index <= now]
            future = ed[ed.index > now]
            if not past.empty:
                last_date = _to_str(past.index[0])
            if not future.empty:
                next_dt = future.index[-1]
                next_date = _to_str(next_dt)
                days_until = (next_dt.to_pydatetime().replace(tzinfo=timezone.utc) - now).days
                within_30 = 0 <= days_until <= 30
    except Exception as e:
        logger.warning("earnings_dates unavailable for %s: %s", ticker, e)

    return EarningsData(
        last_earnings_date=last_date,
        next_earnings_date=next_date,
        history=history,
        avg_eps_surprise_pct=avg_surprise,
        beat_count=beat_count,
        miss_count=miss_count,
        beat_rate=beat_rate,
        within_30_days=within_30,
    )


def score_earnings(data: EarningsData) -> float:
    """Score 0–100 for earnings quality and momentum."""
    score = 50.0

    # Beat rate (±20)
    if data.beat_rate is not None:
        if data.beat_rate >= 0.80:
            score += 20
        elif data.beat_rate >= 0.60:
            score += 10
        elif data.beat_rate < 0.40:
            score -= 15

    # Average EPS surprise (±15)
    avg_surp = data.avg_eps_surprise_pct
    if avg_surp is not None:
        if avg_surp >= 5:
            score += 15
        elif avg_surp >= 2:
            score += 8
        elif avg_surp < 0:
            score -= 15

    # Earnings approaching within 30 days → add uncertainty penalty (−10)
    if data.within_30_days:
        score -= 10

    return round(max(0.0, min(100.0, score)), 2)
