"""Tests for Step 3: risk_management_service config migration."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Optional

import pytest

from app.algo_config import AlgoConfig, reset_algo_config
from app.services.risk_management_service import (
    _POSITION_SIZING,
    _atr_size_multiplier,
    _compute_stop_atr,
    compute_risk_management,
)
from app.models.market import SupportResistanceLevels, TechnicalIndicators


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_cfg() -> dict:
    path = Path(__file__).parent.parent / "algo_config.json"
    return json.loads(path.read_text())


def _ti(atr: float = 5.0, atr_pct: float = 2.0) -> TechnicalIndicators:
    """Minimal TechnicalIndicators with support/resistance."""
    sr = SupportResistanceLevels(
        supports=[95.0, 90.0],
        resistances=[110.0, 120.0],
        nearest_support=95.0,
        nearest_resistance=110.0,
    )
    return TechnicalIndicators(
        atr=atr,
        atr_percent=atr_pct,
        support_resistance=sr,
        technical_score=60.0,
    )


@pytest.fixture(autouse=True)
def _reset():
    reset_algo_config()
    yield
    reset_algo_config()


# ---------------------------------------------------------------------------
# Module-level alias matches default config
# ---------------------------------------------------------------------------

def test_position_sizing_alias_conservative():
    assert _POSITION_SIZING["conservative"]["starter_pct"] == 15
    assert _POSITION_SIZING["conservative"]["max_allocation"] == 3.0


def test_position_sizing_alias_moderate():
    assert _POSITION_SIZING["moderate"]["starter_pct"] == 25
    assert _POSITION_SIZING["moderate"]["max_allocation"] == 5.0


def test_position_sizing_alias_aggressive():
    assert _POSITION_SIZING["aggressive"]["starter_pct"] == 40
    assert _POSITION_SIZING["aggressive"]["max_allocation"] == 8.0


# ---------------------------------------------------------------------------
# ATR size multiplier
# ---------------------------------------------------------------------------

def test_atr_multiplier_low_volatility():
    # atr_pct < 4.0 → 1.0
    result = _atr_size_multiplier(3.0, [4.0, 7.0], [1.0, 0.55, 0.30])
    assert result == 1.0


def test_atr_multiplier_high_volatility():
    # 4.0 <= atr_pct <= 7.0 → 0.55
    result = _atr_size_multiplier(5.5, [4.0, 7.0], [1.0, 0.55, 0.30])
    assert result == 0.55


def test_atr_multiplier_extreme_volatility():
    # atr_pct > 7.0 → 0.30
    result = _atr_size_multiplier(9.0, [4.0, 7.0], [1.0, 0.55, 0.30])
    assert result == 0.30


def test_custom_atr_multiplier_thresholds():
    # Custom: < 3.0 → 1.0, <= 6.0 → 0.60, else → 0.25
    assert _atr_size_multiplier(2.0, [3.0, 6.0], [1.0, 0.60, 0.25]) == 1.0
    assert _atr_size_multiplier(5.0, [3.0, 6.0], [1.0, 0.60, 0.25]) == 0.60
    assert _atr_size_multiplier(8.0, [3.0, 6.0], [1.0, 0.60, 0.25]) == 0.25


# ---------------------------------------------------------------------------
# ATR stop computation
# ---------------------------------------------------------------------------

def test_atr_stop_short_term_default():
    stop = _compute_stop_atr(100.0, 5.0, "short_term", {"short_term": 1.5, "medium_term": 2.0, "long_term": 2.5})
    assert stop == 92.5  # 100 - 1.5 * 5


def test_atr_stop_long_term_default():
    stop = _compute_stop_atr(100.0, 5.0, "long_term", {"short_term": 1.5, "medium_term": 2.0, "long_term": 2.5})
    assert stop == 87.5  # 100 - 2.5 * 5


def test_custom_atr_stop_multiplier():
    stop = _compute_stop_atr(100.0, 5.0, "short_term", {"short_term": 2.0}, default_mult=2.0)
    assert stop == 90.0  # 100 - 2.0 * 5


# ---------------------------------------------------------------------------
# compute_risk_management — default config
# ---------------------------------------------------------------------------

def test_buy_now_entry_default():
    entry, exit_, rr, sizing = compute_risk_management(
        price=100.0, technicals=_ti(), decision="BUY_NOW", risk_profile="moderate"
    )
    assert entry.preferred_entry == 100.0
    assert entry.starter_entry == 100.5   # price * 1.005
    assert entry.avoid_above == 108.0     # price * 1.08


def test_wait_for_pullback_entry_default():
    entry, _, _, _ = compute_risk_management(
        price=100.0, technicals=_ti(), decision="WAIT_FOR_PULLBACK", risk_profile="moderate"
    )
    assert entry.preferred_entry == 95.0  # nearest_support
    assert entry.starter_entry == 98.0    # price * 0.98
    assert entry.avoid_above == 105.0     # price * 1.05


def test_position_sizing_moderate_default():
    _, _, _, sizing = compute_risk_management(
        price=100.0, technicals=_ti(atr_pct=2.0), decision="BUY_NOW", risk_profile="moderate"
    )
    assert sizing.suggested_starter_pct_of_full == 25
    assert sizing.max_portfolio_allocation_pct == 5.0


def test_pre_earnings_reduces_position():
    _, _, _, sizing = compute_risk_management(
        price=100.0, technicals=_ti(atr_pct=2.0), decision="BUY_NOW",
        risk_profile="moderate", within_30_days_earnings=True
    )
    # moderate: starter=25, max=5.0 → pre-earnings: 25*0.5=12, 5.0*0.7=3.5
    assert sizing.suggested_starter_pct_of_full == 12
    assert sizing.max_portfolio_allocation_pct == 3.5


def test_first_target_uses_resistance():
    _, exit_, _, _ = compute_risk_management(
        price=100.0, technicals=_ti(), decision="BUY_NOW"
    )
    assert exit_.first_target == 110.0   # nearest resistance
    assert exit_.second_target == 120.0  # second resistance


def test_first_target_fallback_no_resistance():
    sr = SupportResistanceLevels(supports=[], resistances=[], nearest_support=None, nearest_resistance=None)
    ti = TechnicalIndicators(atr=None, atr_percent=None, support_resistance=sr, technical_score=50.0)
    _, exit_, _, _ = compute_risk_management(price=100.0, technicals=ti, decision="BUY_NOW")
    assert exit_.first_target == 110.0   # price * 1.10
    assert exit_.second_target == 120.0  # price * 1.20


# ---------------------------------------------------------------------------
# compute_risk_management — custom config
# ---------------------------------------------------------------------------

def test_custom_position_sizing_aggressive():
    data = _base_cfg()
    data["risk_management"]["position_sizing"]["aggressive"]["max_allocation"] = 10.0
    cfg = AlgoConfig.from_dict(data)

    _, _, _, sizing = compute_risk_management(
        price=100.0, technicals=_ti(atr_pct=2.0), decision="BUY_NOW",
        risk_profile="aggressive", algo_config=cfg
    )
    assert sizing.max_portfolio_allocation_pct == 10.0


def test_custom_atr_stop_multiplier_in_compute():
    data = _base_cfg()
    data["risk_management"]["atr_stop_multipliers"]["short_term"] = 2.0
    cfg = AlgoConfig.from_dict(data)

    # price=100, atr=5, short_term stop = 100 - 2.0*5 = 90
    _, exit_, _, _ = compute_risk_management(
        price=100.0, technicals=_ti(atr=5.0, atr_pct=2.0), decision="BUY_NOW",
        algo_config=cfg
    )
    assert exit_.stop_loss == 90.0


def test_custom_pre_earnings_cut():
    data = _base_cfg()
    data["risk_management"]["pre_earnings_starter_cut"] = 0.25  # 75% cut instead of 50%
    cfg = AlgoConfig.from_dict(data)

    _, _, _, sizing = compute_risk_management(
        price=100.0, technicals=_ti(atr_pct=2.0), decision="BUY_NOW",
        risk_profile="moderate", within_30_days_earnings=True, algo_config=cfg
    )
    # moderate: starter=25 → 25 * 0.25 = 6
    assert sizing.suggested_starter_pct_of_full == 6


def test_custom_buy_now_avoid_factor():
    data = _base_cfg()
    data["risk_management"]["entry_buy_now_avoid_factor"] = 1.05
    cfg = AlgoConfig.from_dict(data)

    entry, _, _, _ = compute_risk_management(
        price=100.0, technicals=_ti(), decision="BUY_NOW", algo_config=cfg
    )
    assert entry.avoid_above == 105.0  # price * 1.05
