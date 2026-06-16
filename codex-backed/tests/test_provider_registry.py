"""S1.5 — Provider registry tests."""

from __future__ import annotations

import pytest

from codex_backed.config.loader import ConfigError
from codex_backed.data.providers.null_fundamentals import NullFundamentalsProvider
from codex_backed.data.providers.pickle_provider import PickleProvider
from codex_backed.data.providers.registry import ProviderSet, build_providers
from codex_backed.data.providers.yfinance_provider import YFinancePriceProvider

# ---------------------------------------------------------------------------
# Minimal config fixtures
# ---------------------------------------------------------------------------

_LEGACY_CONFIG = {
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
            "prices_cache_path": "/tmp/test_prices.pkl",
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_legacy_yfinance_mode_returns_pickle_for_backtest_prices():
    ps = build_providers(_LEGACY_CONFIG)
    assert isinstance(ps, ProviderSet)
    assert isinstance(ps.price_backtest, PickleProvider)


def test_legacy_yfinance_mode_returns_yfinance_for_live_prices():
    ps = build_providers(_LEGACY_CONFIG)
    assert isinstance(ps.price_live, YFinancePriceProvider)


def test_legacy_yfinance_mode_returns_null_for_fundamentals():
    ps = build_providers(_LEGACY_CONFIG)
    assert isinstance(ps.fundamentals, NullFundamentalsProvider)


def test_unknown_mode_raises_config_error():
    with pytest.raises(ConfigError, match="Unknown data provider mode"):
        build_providers(_LEGACY_CONFIG, mode="nonexistent_mode")


def test_missing_provider_block_raises_config_error():
    bad_config = {
        "active_mode": "legacy_yfinance",
        "modes": {
            "legacy_yfinance": {
                "price_provider_backtest": {"type": "pickle", "config_ref": "missing_ref"},
                "price_provider_live": {"type": "yfinance", "config_ref": "yfinance"},
                "fundamentals_provider": {"type": "null"},
            }
        },
        "providers": {
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
            }
        },
    }
    with pytest.raises(ConfigError, match="missing_ref"):
        build_providers(bad_config)


def test_capabilities_loaded_from_config_not_class():
    """Changing tier_capabilities in config changes the provider's capabilities — not class defaults."""
    custom_config = {
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
                "prices_cache_path": "/tmp/test.pkl",
                "tier_capabilities": {
                    "supports_prices": True,
                    "supports_fundamentals": False,
                    "fundamentals_fields": ["custom_field"],
                    "history_start_date": "2021-01-01",
                    "price_realtime": True,
                    "rate_limit_per_minute": 99,
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
    ps = build_providers(custom_config)
    caps = ps.price_backtest.capabilities
    assert "custom_field" in caps.fundamentals_fields
    assert caps.history_start_date == "2021-01-01"
    assert caps.price_realtime is True
    assert caps.rate_limit_per_minute == 99
