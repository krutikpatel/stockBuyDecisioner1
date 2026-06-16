"""S3.1 — Field-alias registry tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_backed.data.providers.alias_apply import apply_aliases
from codex_backed.data.providers.field_aliases import (
    FMP_ALIASES,
    FMP_SUPPORTED_FIELDS,
    YFINANCE_ALIASES,
    YFINANCE_SUPPORTED_FIELDS,
)

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "data_provider_config.json"


def _fmp_config_fields() -> frozenset[str]:
    cfg = json.loads(_CONFIG_PATH.read_text())
    fmp_tier = cfg["providers"]["fmp"]["tier_capabilities"]
    return frozenset(fmp_tier.get("fundamentals_fields", []))


def _yfinance_config_fields() -> frozenset[str]:
    cfg = json.loads(_CONFIG_PATH.read_text())
    yf_tier = cfg["providers"]["yfinance"]["tier_capabilities"]
    return frozenset(yf_tier.get("fundamentals_fields", []))


def test_fmp_aliases_cover_all_supported_fields():
    config_fields = _fmp_config_fields()
    for field in config_fields:
        assert field in FMP_ALIASES, (
            f"FMP config lists '{field}' in fundamentals_fields but FMP_ALIASES has no entry for it"
        )


def test_yfinance_aliases_cover_all_supported_fields():
    config_fields = _yfinance_config_fields()
    for field in config_fields:
        assert field in YFINANCE_ALIASES, (
            f"YFinance config lists '{field}' in fundamentals_fields but YFINANCE_ALIASES has no entry for it"
        )


def test_apply_aliases_picks_first_present_key():
    aliases = {"sales_growth_yoy": ["revenueGrowth", "revenue_growth"]}
    payload = {"revenue_growth": 0.15, "revenueGrowth": 0.12}
    result = apply_aliases(payload, aliases)
    # first matching key in the payload should win
    assert result["sales_growth_yoy"] == 0.12


def test_apply_aliases_returns_none_when_no_alias_matches():
    aliases = {"roe": ["returnOnEquity", "roe"]}
    payload = {"someOtherField": 99}
    result = apply_aliases(payload, aliases)
    assert result["roe"] is None


def test_aliases_are_immutable():
    import types
    assert isinstance(FMP_ALIASES, types.MappingProxyType)
    assert isinstance(YFINANCE_ALIASES, types.MappingProxyType)
    with pytest.raises((TypeError, AttributeError)):
        FMP_ALIASES["new_field"] = []  # type: ignore[index]
