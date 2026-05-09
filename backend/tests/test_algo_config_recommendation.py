"""Tests for Step 9: recommendation_service config migration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.algo_config import AlgoConfig, reset_algo_config
from app.models.market import MarketRegime, MarketRegimeAssessment, TechnicalIndicators
from app.models.fundamentals import FundamentalData, ValuationData
from app.models.earnings import EarningsData
from app.models.news import NewsSummary
from app.models.response import SignalCards, SignalCard, SignalCardLabel
from app.services.recommendation_service import (
    _get_regime_thresholds,
    _decide_medium_term_v2,
    _decide_long_term_v2,
    build_recommendations,
)


def _base_cfg() -> dict:
    path = Path(__file__).parent.parent / "algo_config.json"
    return json.loads(path.read_text())


def _ti(**kwargs) -> TechnicalIndicators:
    defaults = dict(
        rsi_14=62.0,
        rsi_slope=2.0,
        sma20_relative=3.0,
        sma50_relative=5.0,
        sma200_relative=10.0,
        sma20_slope=0.1,
        sma50_slope=0.05,
        breakout_volume_multiple=1.4,
        is_extended=False,
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
        fundamental_score=65.0,
    )
    defaults.update(kwargs)
    return FundamentalData(**defaults)


def _earnings(**kwargs) -> EarningsData:
    defaults = dict(earnings_score=60.0, beat_rate=0.75, within_30_days=False)
    defaults.update(kwargs)
    return EarningsData(**defaults)


def _news(score: float = 65.0) -> NewsSummary:
    return NewsSummary(news_score=score, news_summary="test")


def _vd(**kwargs) -> ValuationData:
    defaults = dict(valuation_score=50.0, archetype_adjusted_score=0.0)
    defaults.update(kwargs)
    return ValuationData(**defaults)


def _card(score: float = 60.0) -> SignalCard:
    return SignalCard(
        name="test", score=score, label=SignalCardLabel.NEUTRAL,
        explanation="", top_positives=[], top_negatives=[], missing_data_warnings=[],
    )


def _signal_cards(score: float = 65.0) -> SignalCards:
    c = _card(score)
    return SignalCards(
        momentum=c, trend=c, entry_timing=c, volume_accumulation=c,
        volatility_risk=c, relative_strength=c, growth=c, valuation=c,
        quality=c, ownership=c, catalyst=c,
    )


@pytest.fixture(autouse=True)
def _reset():
    reset_algo_config()
    yield
    reset_algo_config()


# ---------------------------------------------------------------------------
# _get_regime_thresholds reads from config
# ---------------------------------------------------------------------------

def test_regime_thresholds_default_bull():
    t = _get_regime_thresholds(MarketRegime.BULL_RISK_ON)
    assert t.rsi_min == 55.0
    assert t.rsi_max == 68.0
    assert t.sma20_max == 5.0
    assert t.rel_vol_min == 1.3


def test_regime_thresholds_default_sideways():
    t = _get_regime_thresholds(MarketRegime.SIDEWAYS_CHOPPY)
    assert t.rsi_min == 40.0
    assert t.rsi_max == 58.0


def test_custom_regime_thresholds_change_classification():
    """Custom BULL_RISK_ON rsi_max=80 changes threshold used in _get_regime_thresholds."""
    data = _base_cfg()
    data["decision_logic"]["regime_thresholds"]["BULL_RISK_ON"]["rsi_max"] = 80.0
    cfg = AlgoConfig.from_dict(data)

    t = _get_regime_thresholds(MarketRegime.BULL_RISK_ON, algo_config=cfg)
    assert t.rsi_max == 80.0


# ---------------------------------------------------------------------------
# _decide_medium_term_v2 uses config thresholds
# ---------------------------------------------------------------------------

def test_medium_term_buy_now_at_default_threshold():
    ti = _ti()
    decision = _decide_medium_term_v2(72.0, ti, None, _earnings())
    assert decision == "BUY_NOW"


def test_medium_term_watchlist_at_default_threshold():
    ti = _ti()
    decision = _decide_medium_term_v2(50.0, ti, None, _earnings())
    assert decision == "WATCHLIST_NEEDS_CONFIRMATION"


def test_custom_medium_term_buy_now_threshold():
    """Raising buy_now_min to 80 means score=72 no longer qualifies as BUY_NOW."""
    ti = _ti(is_extended=False)
    data = _base_cfg()
    data["decision_logic"]["medium_term_buy_now_min"] = 80
    cfg = AlgoConfig.from_dict(data)

    decision = _decide_medium_term_v2(72.0, ti, None, _earnings(), algo_config=cfg)
    # score=72 < 80 → falls to buy_starter_min check (score=72 >= 60) → BUY_STARTER
    assert decision == "BUY_STARTER"


def test_custom_medium_term_watchlist_threshold():
    """Raising watchlist_min to 55 means score=50 no longer qualifies for WATCHLIST."""
    ti = _ti()
    data = _base_cfg()
    data["decision_logic"]["medium_term_watchlist_min"] = 55
    cfg = AlgoConfig.from_dict(data)

    decision = _decide_medium_term_v2(50.0, ti, None, _earnings(), algo_config=cfg)
    # score=50 < 55 → AVOID_BAD_BUSINESS
    assert decision == "AVOID_BAD_BUSINESS"


# ---------------------------------------------------------------------------
# _decide_long_term_v2 uses config thresholds
# ---------------------------------------------------------------------------

def test_long_term_buy_now_at_default():
    decision = _decide_long_term_v2(75.0, None, None, None)
    assert decision == "BUY_NOW_LONG_TERM"


def test_custom_long_term_buy_now_threshold():
    """Raising long_term_buy_now_min to 85 means score=75 falls to ACCUMULATE."""
    data = _base_cfg()
    data["decision_logic"]["long_term_buy_now_min"] = 85
    cfg = AlgoConfig.from_dict(data)

    decision = _decide_long_term_v2(75.0, None, None, None, algo_config=cfg)
    assert decision == "ACCUMULATE_ON_WEAKNESS"


# ---------------------------------------------------------------------------
# build_recommendations accepts algo_config
# ---------------------------------------------------------------------------

def test_build_recommendations_accepts_algo_config():
    cfg = AlgoConfig.from_dict(_base_cfg())
    scores = {
        "short_term": {"composite": 65.0},
        "medium_term": {"composite": 65.0},
        "long_term": {"composite": 65.0},
    }
    recs = build_recommendations(
        technicals=_ti(),
        fundamentals=_fd(),
        valuation=_vd(),
        earnings=_earnings(),
        news=_news(),
        scores=scores,
        horizons=["short_term", "medium_term", "long_term"],
        risk_profile="moderate",
        current_price=100.0,
        signal_cards=_signal_cards(65.0),
        algo_config=cfg,
    )
    assert len(recs) == 3


def test_custom_medium_term_threshold_changes_build_decision():
    """Custom buy_now_min=80 changes medium-term decision in build_recommendations."""
    data = _base_cfg()
    data["decision_logic"]["medium_term_buy_now_min"] = 80
    cfg = AlgoConfig.from_dict(data)

    scores = {"medium_term": {"composite": 75.0}}
    # With default config: score=75 >= 72 → BUY_NOW
    default_recs = build_recommendations(
        technicals=_ti(is_extended=False),
        fundamentals=_fd(),
        valuation=_vd(),
        earnings=_earnings(),
        news=_news(),
        scores=scores,
        horizons=["medium_term"],
        risk_profile="moderate",
        current_price=100.0,
        signal_cards=_signal_cards(75.0),
    )
    # With custom config: score=75 < 80 → BUY_STARTER
    custom_recs = build_recommendations(
        technicals=_ti(is_extended=False),
        fundamentals=_fd(),
        valuation=_vd(),
        earnings=_earnings(),
        news=_news(),
        scores=scores,
        horizons=["medium_term"],
        risk_profile="moderate",
        current_price=100.0,
        signal_cards=_signal_cards(75.0),
        algo_config=cfg,
    )

    assert default_recs[0].decision == "BUY_NOW"
    assert custom_recs[0].decision == "BUY_STARTER"
