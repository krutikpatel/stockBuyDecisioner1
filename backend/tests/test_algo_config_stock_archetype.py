"""Tests for Step 7: stock_archetype_service config migration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.algo_config import AlgoConfig, reset_algo_config
from app.models.fundamentals import FundamentalData, StockArchetype, ValuationData
from app.services.stock_archetype_service import classify_archetype


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_cfg() -> dict:
    path = Path(__file__).parent.parent / "algo_config.json"
    return json.loads(path.read_text())


def _fund(**kwargs) -> FundamentalData:
    defaults = dict(
        revenue_growth_yoy=0.10,
        eps_ttm=1.0,
        operating_margin=0.10,
        free_cash_flow=100.0,
        sector="Technology",
        beta=1.0,
        eps_growth_yoy=None,
        revenue_growth_qoq=None,
        gross_margin=None,
        fundamental_score=60.0,
    )
    defaults.update(kwargs)
    return FundamentalData(**defaults)


def _val(**kwargs) -> ValuationData:
    defaults = dict(valuation_score=50.0, archetype_adjusted_score=0.0)
    defaults.update(kwargs)
    return ValuationData(**defaults)


@pytest.fixture(autouse=True)
def _reset():
    reset_algo_config()
    yield
    reset_algo_config()


# ---------------------------------------------------------------------------
# Default config produces correct archetypes
# ---------------------------------------------------------------------------

def test_hyper_growth_high_rev():
    archetype, conf = classify_archetype(_fund(revenue_growth_yoy=0.35), _val())
    assert archetype == StockArchetype.HYPER_GROWTH
    assert conf > 70.0


def test_speculative_high_ps_unprofitable():
    archetype, conf = classify_archetype(
        _fund(revenue_growth_yoy=0.25, eps_ttm=-1.0),
        _val(price_to_sales=25.0),
    )
    assert archetype == StockArchetype.SPECULATIVE_STORY
    assert conf == 80.0


def test_speculative_very_high_ps():
    archetype, conf = classify_archetype(_fund(), _val(price_to_sales=45.0))
    assert archetype == StockArchetype.SPECULATIVE_STORY
    assert conf == 70.0


def test_defensive_low_beta():
    archetype, conf = classify_archetype(_fund(sector="Healthcare", beta=0.5), _val())
    assert archetype == StockArchetype.DEFENSIVE
    assert conf == 80.0


def test_mature_value_slow_growth():
    archetype, conf = classify_archetype(
        _fund(revenue_growth_yoy=0.05, free_cash_flow=100.0),
        _val(),
    )
    assert archetype == StockArchetype.MATURE_VALUE
    assert conf == 68.0


# ---------------------------------------------------------------------------
# Custom config changes classifications
# ---------------------------------------------------------------------------

def test_custom_hyper_growth_threshold_higher():
    """Raise hyper_growth_rev_yoy_min to 0.40 — rev_yoy=0.35 no longer qualifies."""
    data = _base_cfg()
    data["stock_archetype"]["hyper_growth_rev_yoy_min"] = 0.40
    cfg = AlgoConfig.from_dict(data)

    archetype, _ = classify_archetype(_fund(revenue_growth_yoy=0.35), _val(), algo_config=cfg)
    # Should fall through to PROFITABLE_GROWTH (>0.15 with positive ops)
    assert archetype == StockArchetype.PROFITABLE_GROWTH


def test_custom_speculative_ps_threshold():
    """Lower speculative_ps_high_growth_min to 15 — ps=18 now triggers speculative."""
    data = _base_cfg()
    data["stock_archetype"]["speculative_ps_high_growth_min"] = 15.0
    cfg = AlgoConfig.from_dict(data)

    # ps=18, unprofitable, rev_yoy=25% → now triggers (18 > 15)
    archetype, conf = classify_archetype(
        _fund(revenue_growth_yoy=0.25, eps_ttm=-1.0),
        _val(price_to_sales=18.0),
        algo_config=cfg,
    )
    assert archetype == StockArchetype.SPECULATIVE_STORY


def test_custom_defensive_sectors():
    """Remove Utilities from defensive sectors — utilities stock no longer defensive."""
    data = _base_cfg()
    data["stock_archetype"]["defensive_sectors"] = ["Healthcare", "Consumer Defensive"]
    cfg = AlgoConfig.from_dict(data)

    archetype, _ = classify_archetype(_fund(sector="Utilities", beta=0.5), _val(), algo_config=cfg)
    # Utilities not in custom defensive sectors → falls through
    assert archetype != StockArchetype.DEFENSIVE


def test_custom_cyclical_beta_threshold():
    """Lower cyclical beta threshold to 1.1 — beta=1.2 now qualifies as cyclical."""
    data = _base_cfg()
    data["stock_archetype"]["cyclical_beta_min"] = 1.1
    data["stock_archetype"]["cyclical_sectors"] = ["Industrials"]
    cfg = AlgoConfig.from_dict(data)

    archetype, _ = classify_archetype(
        _fund(sector="Industrials", beta=1.2, revenue_growth_yoy=0.05),
        _val(),
        algo_config=cfg,
    )
    assert archetype == StockArchetype.CYCLICAL_GROWTH


def test_custom_mature_value_confidence():
    data = _base_cfg()
    data["stock_archetype"]["mature_value_confidence"] = 75.0
    cfg = AlgoConfig.from_dict(data)

    _, conf = classify_archetype(
        _fund(revenue_growth_yoy=0.05, free_cash_flow=100.0),
        _val(),
        algo_config=cfg,
    )
    assert conf == 75.0
