from __future__ import annotations

from typing import Optional

from app.algo_config import AlgoConfig, get_algo_config
from app.models.earnings import EarningsData
from app.models.fundamentals import ValuationData
from app.models.news import NewsSummary


def compute_completeness(
    news: NewsSummary,
    earnings: EarningsData,
    valuation: ValuationData,
    has_options_data: bool = False,
    has_sufficient_price_history: bool = True,
    algo_config: Optional[AlgoConfig] = None,
) -> tuple[float, float, list[str]]:
    """Return (data_completeness_score, confidence_score, warnings).

    data_completeness_score: 0–100, deducted for each missing category.
    confidence_score:        0–100, capped at 60 when completeness < 60.
    warnings:                human-readable messages for each gap.
    """
    cfg = algo_config or get_algo_config()
    dc = cfg.data_completeness
    deductions = dc["deductions"]
    confidence_cap_threshold = dc["confidence_cap_threshold"]
    confidence_cap_value = dc["confidence_cap_value"]

    completeness = 100.0
    warnings: list[str] = []

    if news.positive_count + news.negative_count == 0:
        completeness -= deductions["no_news"]
        warnings.append("No recent news found — sentiment signal unavailable.")

    if earnings.next_earnings_date is None:
        completeness -= deductions["no_next_earnings_date"]
        warnings.append("Next earnings date could not be determined.")

    if valuation.peer_comparison_available is False:
        completeness -= deductions["no_peer_comparison"]
        warnings.append("Peer valuation comparison unavailable.")

    if not has_options_data:
        completeness -= deductions["no_options_data"]
        warnings.append("Options flow data unavailable — catalyst signal is estimated.")

    if not has_sufficient_price_history:
        completeness -= deductions["insufficient_price_history"]
        warnings.append("Less than 6 months of price history available.")

    completeness = round(max(0.0, completeness), 2)

    confidence_score = 100.0
    if completeness < confidence_cap_threshold:
        confidence_score = confidence_cap_value

    return completeness, confidence_score, warnings


# ---------------------------------------------------------------------------
# Backward-compatible module-level aliases (read from default config at import)
# ---------------------------------------------------------------------------

def _get_default_dc() -> dict:
    return get_algo_config().data_completeness


_DEDUCTIONS = _get_default_dc()["deductions"]
_CONFIDENCE_CAP_THRESHOLD = _get_default_dc()["confidence_cap_threshold"]
_CONFIDENCE_CAP_VALUE = _get_default_dc()["confidence_cap_value"]
AVOID_LOW_CONFIDENCE_THRESHOLD = _get_default_dc()["avoid_low_confidence_threshold"]
