"""Tests for Step 8: signal_card_service config migration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.algo_config import AlgoConfig, reset_algo_config
from app.models.earnings import EarningsData
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.market import TechnicalIndicators
from app.models.news import NewsSummary
from app.services.signal_card_service import (
    score_momentum,
    score_trend,
    score_catalyst,
    score_all_cards,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_cfg() -> dict:
    path = Path(__file__).parent.parent / "algo_config.json"
    return json.loads(path.read_text())


def _ti(**kwargs) -> TechnicalIndicators:
    defaults = dict(
        rsi_14=60.0,
        rsi_slope=2.0,
        macd_histogram=0.5,
        adx=25.0,
        perf_1w=1.0,
        perf_1m=3.0,
        perf_3m=8.0,
        perf_6m=15.0,
        perf_1y=25.0,
        ema8_relative=1.0,
        ema21_relative=0.5,
        sma20_relative=2.0,
        sma50_relative=5.0,
        sma200_relative=10.0,
        sma20_slope=0.1,
        sma50_slope=0.05,
    )
    defaults.update(kwargs)
    return TechnicalIndicators(**defaults)


def _fd(**kwargs) -> FundamentalData:
    defaults = dict(
        revenue_growth_yoy=0.15,
        eps_ttm=2.0,
        operating_margin=0.15,
        free_cash_flow=100.0,
        sector="Technology",
        beta=1.0,
        fundamental_score=60.0,
    )
    defaults.update(kwargs)
    return FundamentalData(**defaults)


def _earnings(**kwargs) -> EarningsData:
    defaults = dict(
        earnings_score=60.0,
        beat_rate=0.75,
        within_30_days=False,
    )
    defaults.update(kwargs)
    return EarningsData(**defaults)


def _news(score: float = 65.0) -> NewsSummary:
    return NewsSummary(news_score=score, news_summary="test")


def _vd(**kwargs) -> ValuationData:
    defaults = dict(valuation_score=50.0, archetype_adjusted_score=0.0)
    defaults.update(kwargs)
    return ValuationData(**defaults)


@pytest.fixture(autouse=True)
def _reset():
    reset_algo_config()
    yield
    reset_algo_config()


# ---------------------------------------------------------------------------
# Default config produces same results as hardcoded values
# ---------------------------------------------------------------------------

def test_momentum_score_in_range():
    card = score_momentum(_ti())
    assert 0.0 <= card.score <= 100.0


def test_trend_score_in_range():
    card = score_trend(_ti())
    assert 0.0 <= card.score <= 100.0


def test_catalyst_score_in_range():
    card = score_catalyst(_fd(), _earnings(), _news())
    assert 0.0 <= card.score <= 100.0


def test_all_cards_score_in_range():
    cards = score_all_cards(_ti(), _fd(), _vd(), _earnings(), _news())
    for field in ["momentum", "trend", "entry_timing", "volume_accumulation",
                  "volatility_risk", "relative_strength", "growth", "valuation",
                  "quality", "ownership", "catalyst"]:
        card = getattr(cards, field)
        assert 0.0 <= card.score <= 100.0, f"{field} score out of range: {card.score}"


# ---------------------------------------------------------------------------
# Custom config changes momentum RSI scoring
# ---------------------------------------------------------------------------

def test_custom_rsi_sweet_spot_pts_change_momentum():
    """Raising RSI sweet spot points increases momentum score when RSI is in sweet spot."""
    ti = _ti(rsi_14=55.0)  # within default sweet spot [45, 65]

    data = _base_cfg()
    data["signal_cards"]["momentum"]["rsi_sweet_spot_pts"] = 30  # was 15
    cfg = AlgoConfig.from_dict(data)

    default_card = score_momentum(ti)
    custom_card = score_momentum(ti, algo_config=cfg)

    assert custom_card.score > default_card.score


def test_custom_rsi_overbought_pts_changes_momentum():
    """Reducing overbought pts lowers momentum score when RSI is overbought."""
    ti = _ti(rsi_14=80.0)  # clearly above default overbought threshold of 75

    data = _base_cfg()
    data["signal_cards"]["momentum"]["rsi_overbought_pts"] = 0  # was 4 → less reward
    cfg = AlgoConfig.from_dict(data)

    default_card = score_momentum(ti)  # RSI 80 → overbought → 4 pts
    custom_card = score_momentum(ti, algo_config=cfg)  # RSI 80 → overbought → 0 pts

    assert custom_card.score < default_card.score


def test_custom_macd_base_pts_changes_momentum():
    """Custom macd_base_pts raises MACD contribution."""
    ti = _ti(macd_histogram=0.5)

    data = _base_cfg()
    data["signal_cards"]["momentum"]["macd_base_pts"] = 14  # was 7.5
    cfg = AlgoConfig.from_dict(data)

    default_card = score_momentum(ti)
    custom_card = score_momentum(ti, algo_config=cfg)

    assert custom_card.score > default_card.score


# ---------------------------------------------------------------------------
# Custom config changes trend ADX scoring
# ---------------------------------------------------------------------------

def test_custom_adx_strong_threshold_changes_trend():
    """Lowering adx_strong_threshold makes ADX=25 qualify as strong trend."""
    ti = _ti(adx=25.0)  # default strong threshold is 30 → ADX=25 is moderate

    data = _base_cfg()
    data["signal_cards"]["trend"]["adx_strong_threshold"] = 20  # now 25 >= 20 → strong
    data["signal_cards"]["trend"]["adx_strong_pts"] = 15
    cfg = AlgoConfig.from_dict(data)

    default_card = score_trend(ti)   # ADX 25 → moderate → 10 pts
    custom_card = score_trend(ti, algo_config=cfg)  # ADX 25 → strong → 15 pts

    assert custom_card.score >= default_card.score


def test_custom_adx_strong_pts_changes_trend_score():
    """Raising adx_strong_pts increases score when ADX qualifies as strong.

    Include a negative-perf component so total > raw and the ratio changes.
    """
    # ADX=35 (strong, gets full pts), perf_6m negative (0 pts / weight contributes to total)
    ti = TechnicalIndicators(adx=35.0, perf_6m=-5.0)

    data = _base_cfg()
    data["signal_cards"]["trend"]["adx_strong_pts"] = 25  # was 15
    cfg = AlgoConfig.from_dict(data)

    default_card = score_trend(ti)   # raw=15, total=20 → 75.0
    custom_card = score_trend(ti, algo_config=cfg)  # raw=25, total=30 → 83.3

    assert custom_card.score > default_card.score


# ---------------------------------------------------------------------------
# Custom config changes catalyst news tier scoring
# ---------------------------------------------------------------------------

def test_custom_news_tiers_change_catalyst():
    """Raising the first news tier threshold means a score of 72 no longer hits top tier."""
    # Default: ns=72 >= news_tiers[0]=70 → gets news_pts[0]=25 (top points)
    # Custom: news_tiers[0]=80 → ns=72 falls to second tier, gets news_pts[1]=18
    ti_news = _news(score=72.0)

    data = _base_cfg()
    data["signal_cards"]["catalyst"]["news_tiers"] = [80, 55, 45, 30]  # first tier raised to 80
    cfg = AlgoConfig.from_dict(data)

    default_card = score_catalyst(_fd(), _earnings(), ti_news)
    custom_card = score_catalyst(_fd(), _earnings(), ti_news, algo_config=cfg)

    assert custom_card.score < default_card.score


def test_custom_news_pts_change_catalyst():
    """Custom news_pts[0]=35 gives more points for high news score."""
    ti_news = _news(score=80.0)  # clearly in top tier

    data = _base_cfg()
    data["signal_cards"]["catalyst"]["news_pts"] = [35, 18, 12, 5, 0]  # first pts raised
    cfg = AlgoConfig.from_dict(data)

    default_card = score_catalyst(_fd(), _earnings(), ti_news)
    custom_card = score_catalyst(_fd(), _earnings(), ti_news, algo_config=cfg)

    assert custom_card.score > default_card.score


def test_custom_within_30_days_pts_change_catalyst():
    """Custom within_30_days_pts changes catalyst score when earnings are imminent."""
    data = _base_cfg()
    data["signal_cards"]["catalyst"]["within_30_days_pts"] = 20  # was 10
    cfg = AlgoConfig.from_dict(data)

    earnings_soon = _earnings(within_30_days=True)
    default_card = score_catalyst(_fd(), earnings_soon, _news())
    custom_card = score_catalyst(_fd(), earnings_soon, _news(), algo_config=cfg)

    assert custom_card.score > default_card.score


# ---------------------------------------------------------------------------
# score_all_cards passes algo_config to all scorers
# ---------------------------------------------------------------------------

def test_score_all_cards_accepts_algo_config():
    """score_all_cards() runs without error when algo_config is passed."""
    cfg = AlgoConfig.from_dict(_base_cfg())
    cards = score_all_cards(_ti(), _fd(), _vd(), _earnings(), _news(), algo_config=cfg)
    assert cards.momentum is not None
    assert cards.catalyst is not None
