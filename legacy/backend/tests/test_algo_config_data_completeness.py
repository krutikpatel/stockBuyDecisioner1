"""Tests for Step 2: data_completeness_service config migration."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.algo_config import AlgoConfig, reset_algo_config
from app.services.data_completeness_service import (
    AVOID_LOW_CONFIDENCE_THRESHOLD,
    _CONFIDENCE_CAP_THRESHOLD,
    _CONFIDENCE_CAP_VALUE,
    _DEDUCTIONS,
    compute_completeness,
)
from app.models.news import NewsSummary
from app.models.earnings import EarningsData
from app.models.fundamentals import ValuationData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_cfg() -> dict:
    path = Path(__file__).parent.parent / "algo_config.json"
    return json.loads(path.read_text())


def _news(positive=1, negative=1) -> NewsSummary:
    return NewsSummary(positive_count=positive, negative_count=negative, news_score=50.0)


def _no_news() -> NewsSummary:
    return NewsSummary(positive_count=0, negative_count=0, news_score=50.0)


def _earnings(has_date=True) -> EarningsData:
    return EarningsData(
        next_earnings_date="2025-06-01" if has_date else None,
        earnings_score=50.0,
    )


def _valuation(peer=True) -> ValuationData:
    return ValuationData(peer_comparison_available=peer)


@pytest.fixture(autouse=True)
def _reset():
    reset_algo_config()
    yield
    reset_algo_config()


# ---------------------------------------------------------------------------
# Module-level aliases match default config
# ---------------------------------------------------------------------------

def test_deductions_match_default_config():
    assert _DEDUCTIONS["no_news"] == 15
    assert _DEDUCTIONS["no_next_earnings_date"] == 10
    assert _DEDUCTIONS["no_peer_comparison"] == 5
    assert _DEDUCTIONS["no_options_data"] == 15
    assert _DEDUCTIONS["insufficient_price_history"] == 5


def test_avoid_threshold_default():
    assert AVOID_LOW_CONFIDENCE_THRESHOLD == 55.0


def test_confidence_cap_defaults():
    assert _CONFIDENCE_CAP_THRESHOLD == 60.0
    assert _CONFIDENCE_CAP_VALUE == 60.0


# ---------------------------------------------------------------------------
# Default config produces same results as original hardcoded values
# ---------------------------------------------------------------------------

def test_all_data_present_returns_100():
    score, conf, warns = compute_completeness(
        _news(), _earnings(), _valuation(),
        has_options_data=True,
        has_sufficient_price_history=True,
    )
    assert score == 100.0
    assert conf == 100.0
    assert warns == []


def test_no_news_deducts_15():
    score, _, _ = compute_completeness(
        _no_news(), _earnings(), _valuation(),
        has_options_data=True,
        has_sufficient_price_history=True,
    )
    assert score == 85.0


def test_no_options_deducts_15():
    score, _, _ = compute_completeness(
        _news(), _earnings(), _valuation(),
        has_options_data=False,
        has_sufficient_price_history=True,
    )
    assert score == 85.0


# ---------------------------------------------------------------------------
# Custom deductions change scores
# ---------------------------------------------------------------------------

def test_custom_no_news_deduction():
    data = _base_cfg()
    data["data_completeness"]["deductions"]["no_news"] = 20
    cfg = AlgoConfig.from_dict(data)

    score, _, warns = compute_completeness(
        _no_news(), _earnings(), _valuation(),
        has_options_data=True,
        has_sufficient_price_history=True,
        algo_config=cfg,
    )
    assert score == 80.0  # 100 - 20


def test_custom_no_earnings_deduction():
    data = _base_cfg()
    data["data_completeness"]["deductions"]["no_next_earnings_date"] = 20
    cfg = AlgoConfig.from_dict(data)

    score, _, _ = compute_completeness(
        _news(), _earnings(has_date=False), _valuation(),
        has_options_data=True,
        has_sufficient_price_history=True,
        algo_config=cfg,
    )
    assert score == 80.0  # 100 - 20


# ---------------------------------------------------------------------------
# Custom confidence cap threshold
# ---------------------------------------------------------------------------

def test_custom_confidence_cap_threshold():
    """Raise cap threshold to 80: completeness=85 should NOT cap confidence."""
    data = _base_cfg()
    data["data_completeness"]["confidence_cap_threshold"] = 80.0
    data["data_completeness"]["confidence_cap_value"] = 70.0
    cfg = AlgoConfig.from_dict(data)

    # No news → completeness = 85 (still above 80 threshold)
    # But with default threshold 60, 85 would NOT cap; with 80 it caps at 70
    # no_news deduction = 15 → completeness = 85, which is > 80 → no cap still
    # Let's use no_news + no_options → 100 - 15 - 15 = 70, which is < 80 → cap fires
    score, conf, _ = compute_completeness(
        _no_news(), _earnings(), _valuation(),
        has_options_data=False,
        has_sufficient_price_history=True,
        algo_config=cfg,
    )
    assert score == 70.0
    assert conf == 70.0  # capped because 70 < new threshold of 80


def test_default_confidence_cap_does_not_fire_at_85():
    """With default threshold=60, completeness=85 → confidence NOT capped."""
    score, conf, _ = compute_completeness(
        _no_news(), _earnings(), _valuation(),
        has_options_data=True,
        has_sufficient_price_history=True,
    )
    assert score == 85.0
    assert conf == 100.0  # not capped
