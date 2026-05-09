"""Tests for Step 9: valuation_analysis_service config migration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.algo_config import AlgoConfig, reset_algo_config
from app.models.fundamentals import StockArchetype, ValuationData
from app.services.valuation_analysis_service import (
    score_valuation,
    score_valuation_with_archetype,
)


def _base_cfg() -> dict:
    path = Path(__file__).parent.parent / "algo_config.json"
    return json.loads(path.read_text())


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
# score_valuation accepts algo_config without error
# ---------------------------------------------------------------------------

def test_score_valuation_accepts_algo_config():
    cfg = AlgoConfig.from_dict(_base_cfg())
    result = score_valuation(_vd(forward_pe=15.0), algo_config=cfg)
    assert 0.0 <= result <= 100.0


def test_score_valuation_with_default_config_matches_no_config():
    vd = _vd(forward_pe=15.0, peg_ratio=1.0, price_to_sales=2.0)
    default_score = score_valuation(vd)
    cfg = AlgoConfig.from_dict(_base_cfg())
    config_score = score_valuation(vd, algo_config=cfg)
    assert default_score == config_score


# ---------------------------------------------------------------------------
# score_valuation_with_archetype accepts algo_config without error
# ---------------------------------------------------------------------------

def test_score_valuation_with_archetype_accepts_algo_config():
    cfg = AlgoConfig.from_dict(_base_cfg())
    vd = _vd(forward_pe=25.0, peg_ratio=1.5)
    result = score_valuation_with_archetype(
        vd, StockArchetype.HYPER_GROWTH, algo_config=cfg
    )
    assert 0.0 <= result <= 100.0


def test_score_valuation_archetype_consistent_with_default():
    vd = _vd(forward_pe=20.0, peg_ratio=1.2, price_to_sales=5.0)
    default = score_valuation_with_archetype(vd, StockArchetype.MATURE_VALUE)
    cfg = AlgoConfig.from_dict(_base_cfg())
    with_cfg = score_valuation_with_archetype(vd, StockArchetype.MATURE_VALUE, algo_config=cfg)
    assert default == with_cfg


def test_score_valuation_output_in_range_for_all_archetypes():
    vd = _vd(forward_pe=25.0, peg_ratio=2.0, fcf_yield=3.0)
    cfg = AlgoConfig.from_dict(_base_cfg())
    for archetype in [
        StockArchetype.HYPER_GROWTH,
        StockArchetype.SPECULATIVE_STORY,
        StockArchetype.MATURE_VALUE,
        StockArchetype.CYCLICAL_GROWTH,
        StockArchetype.DEFENSIVE,
        StockArchetype.PROFITABLE_GROWTH,
    ]:
        result = score_valuation_with_archetype(vd, archetype, algo_config=cfg)
        assert 0.0 <= result <= 100.0, f"{archetype}: score {result} out of range"
