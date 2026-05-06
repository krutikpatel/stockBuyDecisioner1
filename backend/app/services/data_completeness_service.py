from __future__ import annotations

from app.models.earnings import EarningsData
from app.models.fundamentals import ValuationData
from app.models.news import NewsSummary

# Score deductions for each missing data category
_DEDUCTIONS = {
    "no_news": 15,
    "no_next_earnings_date": 10,
    "no_peer_comparison": 5,
    "no_options_data": 15,
    "insufficient_price_history": 5,
}

# If completeness drops below this threshold, confidence is capped here
_CONFIDENCE_CAP_THRESHOLD = 60.0
_CONFIDENCE_CAP_VALUE = 60.0

# If completeness drops below this threshold, decision is forced.
# Minimum achievable completeness is 50 (all 5 deductions apply), so 55 is the
# lowest reachable trigger — fires when 3+ major data categories are missing.
AVOID_LOW_CONFIDENCE_THRESHOLD = 55.0


def compute_completeness(
    news: NewsSummary,
    earnings: EarningsData,
    valuation: ValuationData,
    has_options_data: bool = False,
    has_sufficient_price_history: bool = True,
) -> tuple[float, float, list[str]]:
    """Return (data_completeness_score, confidence_score, warnings).

    data_completeness_score: 0–100, deducted for each missing category.
    confidence_score:        0–100, capped at 60 when completeness < 60.
    warnings:                human-readable messages for each gap.
    """
    completeness = 100.0
    warnings: list[str] = []

    if news.positive_count + news.negative_count == 0:
        completeness -= _DEDUCTIONS["no_news"]
        warnings.append("No recent news found — sentiment signal unavailable.")

    if earnings.next_earnings_date is None:
        completeness -= _DEDUCTIONS["no_next_earnings_date"]
        warnings.append("Next earnings date could not be determined.")

    if valuation.peer_comparison_available is False:
        completeness -= _DEDUCTIONS["no_peer_comparison"]
        warnings.append("Peer valuation comparison unavailable.")

    if not has_options_data:
        completeness -= _DEDUCTIONS["no_options_data"]
        warnings.append("Options flow data unavailable — catalyst signal is estimated.")

    if not has_sufficient_price_history:
        completeness -= _DEDUCTIONS["insufficient_price_history"]
        warnings.append("Less than 6 months of price history available.")

    completeness = round(max(0.0, completeness), 2)

    confidence_score = 100.0
    if completeness < _CONFIDENCE_CAP_THRESHOLD:
        confidence_score = _CONFIDENCE_CAP_VALUE

    return completeness, confidence_score, warnings
