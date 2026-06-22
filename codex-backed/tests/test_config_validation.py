"""Config validation tests — extended for S1.5 (data_provider_config)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from codex_backed.config.loader import ConfigError, load_config_bundle, validate_config_bundle

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


# ---------------------------------------------------------------------------
# Helper — load configs and patch a copy for negative tests
# ---------------------------------------------------------------------------


def _bundle_with_data_provider_override(overrides: dict):
    """Load the real bundle then replace 'data_provider' with overrides dict."""
    bundle = load_config_bundle(_CONFIG_DIR)
    # Reach into the frozen dataclass via object.__setattr__ for test purposes
    patched_data = dict(bundle.data)
    patched_data["data_provider"] = overrides
    from codex_backed.config.loader import ConfigBundle

    return ConfigBundle(
        config_dir=bundle.config_dir,
        files=bundle.files,
        data=patched_data,
    )


# ---------------------------------------------------------------------------
# S1.5 data_provider_config validation tests
# ---------------------------------------------------------------------------


def test_data_provider_config_valid_legacy_passes():
    bundle = load_config_bundle(_CONFIG_DIR)
    # Must not raise
    validate_config_bundle(bundle)


def test_data_provider_config_invalid_mode_rejected():
    bad_cfg = {
        "active_mode": "does_not_exist",
        "modes": {
            "legacy_yfinance": {
                "price_provider_backtest": {"type": "pickle", "config_ref": "pickle"},
                "price_provider_live": {"type": "yfinance", "config_ref": "yfinance"},
                "fundamentals_provider": {"type": "null"},
            }
        },
        "providers": {
            "pickle": {
                "prices_cache_path": "some/path.pkl",
                "tier_capabilities": {
                    "supports_prices": True,
                    "supports_fundamentals": False,
                    "fundamentals_fields": [],
                    "history_start_date": None,
                    "price_realtime": False,
                    "rate_limit_per_minute": 0,
                },
            },
            "yfinance": {
                "auto_adjust": False,
                "tier_capabilities": {
                    "supports_prices": True,
                    "supports_fundamentals": False,
                    "fundamentals_fields": [],
                    "history_start_date": None,
                    "price_realtime": False,
                    "rate_limit_per_minute": 60,
                },
            },
        },
    }
    bundle = _bundle_with_data_provider_override(bad_cfg)
    with pytest.raises(ConfigError, match="does_not_exist"):
        validate_config_bundle(bundle)


def test_data_provider_config_missing_tier_capabilities_rejected():
    bad_cfg = {
        "active_mode": "legacy_yfinance",
        "modes": {
            "legacy_yfinance": {
                "price_provider_backtest": {"type": "pickle", "config_ref": "pickle"},
                "price_provider_live": {"type": "yfinance", "config_ref": "yfinance"},
                "fundamentals_provider": {"type": "null"},
            }
        },
        "providers": {
            "pickle": {
                "prices_cache_path": "some/path.pkl",
                # tier_capabilities intentionally omitted
            },
            "yfinance": {
                "auto_adjust": False,
                "tier_capabilities": {
                    "supports_prices": True,
                    "supports_fundamentals": False,
                    "fundamentals_fields": [],
                    "history_start_date": None,
                    "price_realtime": False,
                    "rate_limit_per_minute": 60,
                },
            },
        },
    }
    bundle = _bundle_with_data_provider_override(bad_cfg)
    with pytest.raises(ConfigError, match="tier_capabilities"):
        validate_config_bundle(bundle)
