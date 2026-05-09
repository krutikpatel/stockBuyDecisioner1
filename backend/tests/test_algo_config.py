"""Tests for the AlgoConfig loader infrastructure (Step 1)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.algo_config import AlgoConfig, get_algo_config, reset_algo_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure singleton is reset before and after each test."""
    reset_algo_config()
    yield
    reset_algo_config()


# ---------------------------------------------------------------------------
# Loading tests
# ---------------------------------------------------------------------------

def test_loads_default_json():
    cfg = get_algo_config()
    assert isinstance(cfg, AlgoConfig)


def test_all_sections_present():
    cfg = get_algo_config()
    expected_sections = [
        "technical_indicators",
        "technical_scoring",
        "extension_detection",
        "stock_archetype",
        "market_regime",
        "regime_scoring",
        "scoring",
        "signal_cards",
        "decision_logic",
        "data_completeness",
        "risk_management",
        "valuation",
    ]
    for section in expected_sections:
        assert section in cfg._data, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# Default value spot-checks
# ---------------------------------------------------------------------------

def test_default_rsi_period():
    cfg = get_algo_config()
    assert cfg.technical_indicators["rsi_period"] == 14


def test_default_macd_params():
    cfg = get_algo_config()
    ti = cfg.technical_indicators
    assert ti["macd_fast"] == 12
    assert ti["macd_slow"] == 26
    assert ti["macd_signal"] == 9


def test_default_extension_thresholds():
    cfg = get_algo_config()
    ext = cfg.extension_detection
    assert ext["ext_above_20ma_threshold"] == 8.0
    assert ext["ext_above_50ma_threshold"] == 15.0
    assert ext["ext_rsi_overbought"] == 75.0


def test_default_momentum_card_weight():
    cfg = get_algo_config()
    assert cfg.scoring["signal_card_short_weights"]["momentum"] == 25


def test_default_data_completeness_deductions():
    cfg = get_algo_config()
    ded = cfg.data_completeness["deductions"]
    assert ded["no_news"] == 15
    assert ded["no_next_earnings_date"] == 10
    assert ded["no_peer_comparison"] == 5
    assert ded["no_options_data"] == 15
    assert ded["insufficient_price_history"] == 5


def test_default_risk_management_position_sizing():
    cfg = get_algo_config()
    ps = cfg.risk_management["position_sizing"]
    assert ps["conservative"]["starter_pct"] == 15
    assert ps["moderate"]["max_allocation"] == 5.0
    assert ps["aggressive"]["starter_pct"] == 40


def test_default_regime_weight_bull():
    cfg = get_algo_config()
    adj = cfg.market_regime["regime_weight_adjustments"]["BULL_RISK_ON"]
    assert adj["technical_momentum"] == 1.20
    assert adj["valuation_relative_growth"] == 0.70


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------

def test_signal_card_short_weights_sum_to_100():
    cfg = get_algo_config()
    weights = cfg.scoring["signal_card_short_weights"]
    assert sum(weights.values()) == 100, f"Short weights sum to {sum(weights.values())}"


def test_signal_card_medium_weights_sum_to_100():
    cfg = get_algo_config()
    weights = cfg.scoring["signal_card_medium_weights"]
    assert sum(weights.values()) == 100, f"Medium weights sum to {sum(weights.values())}"


def test_signal_card_long_weights_sum_to_100():
    cfg = get_algo_config()
    weights = cfg.scoring["signal_card_long_weights"]
    assert sum(weights.values()) == 100, f"Long weights sum to {sum(weights.values())}"


def test_legacy_short_weights_sum_to_100():
    cfg = get_algo_config()
    weights = cfg.scoring["legacy_short_term_weights"]
    assert sum(weights.values()) == 100


def test_legacy_medium_weights_sum_to_100():
    cfg = get_algo_config()
    weights = cfg.scoring["legacy_medium_term_weights"]
    assert sum(weights.values()) == 100


def test_legacy_long_weights_sum_to_100():
    cfg = get_algo_config()
    weights = cfg.scoring["legacy_long_term_weights"]
    assert sum(weights.values()) == 100


# ---------------------------------------------------------------------------
# from_dict injection
# ---------------------------------------------------------------------------

def test_from_dict_injection():
    custom = {
        "technical_indicators": {"rsi_period": 9},
        "technical_scoring": {},
        "extension_detection": {},
        "stock_archetype": {},
        "market_regime": {},
        "regime_scoring": {},
        "scoring": {},
        "signal_cards": {},
        "decision_logic": {},
        "data_completeness": {},
        "risk_management": {},
        "valuation": {},
    }
    cfg = AlgoConfig.from_dict(custom)
    assert cfg.technical_indicators["rsi_period"] == 9


def test_from_dict_does_not_affect_singleton():
    singleton = get_algo_config()
    assert singleton.technical_indicators["rsi_period"] == 14

    custom = AlgoConfig.from_dict({"technical_indicators": {"rsi_period": 9}})
    assert custom.technical_indicators["rsi_period"] == 9

    # Singleton unchanged
    assert get_algo_config().technical_indicators["rsi_period"] == 14


# ---------------------------------------------------------------------------
# Environment variable override
# ---------------------------------------------------------------------------

def test_env_var_override():
    minimal_config = {
        "technical_indicators": {"rsi_period": 7},
        "technical_scoring": {},
        "extension_detection": {},
        "stock_archetype": {},
        "market_regime": {},
        "regime_scoring": {},
        "scoring": {},
        "signal_cards": {},
        "decision_logic": {},
        "data_completeness": {},
        "risk_management": {},
        "valuation": {},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(minimal_config, f)
        tmp_path = f.name

    try:
        old_env = os.environ.get("ALGO_CONFIG_PATH")
        os.environ["ALGO_CONFIG_PATH"] = tmp_path
        reset_algo_config()

        cfg = get_algo_config()
        assert cfg.technical_indicators["rsi_period"] == 7
    finally:
        if old_env is not None:
            os.environ["ALGO_CONFIG_PATH"] = old_env
        elif "ALGO_CONFIG_PATH" in os.environ:
            del os.environ["ALGO_CONFIG_PATH"]
        os.unlink(tmp_path)
        reset_algo_config()


# ---------------------------------------------------------------------------
# from_file with explicit path
# ---------------------------------------------------------------------------

def test_from_file_explicit_path():
    default_path = Path(__file__).parent.parent / "algo_config.json"
    cfg = AlgoConfig.from_file(default_path)
    assert cfg.technical_indicators["rsi_period"] == 14


# ---------------------------------------------------------------------------
# Missing section raises KeyError
# ---------------------------------------------------------------------------

def test_missing_section_raises_key_error():
    cfg = AlgoConfig.from_dict({"technical_indicators": {"rsi_period": 14}})
    with pytest.raises(KeyError):
        _ = cfg.technical_scoring
