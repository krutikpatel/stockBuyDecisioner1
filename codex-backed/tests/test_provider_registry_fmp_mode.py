"""S2.7 — Registry wiring for fmp_primary_yfinance_fallback mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_backed.data.providers.composite import CompositePriceProvider
from codex_backed.data.providers.fmp_provider import FMPPriceProvider
from codex_backed.data.providers.yfinance_provider import YFinancePriceProvider
from codex_backed.data.providers.registry import build_providers

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "data_provider_config.json"


def _load_config() -> dict:
    return json.loads(_CONFIG_PATH.read_text())


def test_fmp_mode_returns_composite_price_provider(tmp_path):
    cfg = _load_config()
    provider_set = build_providers(cfg, mode="fmp_primary_yfinance_fallback")
    assert isinstance(provider_set.price_live, CompositePriceProvider)


def test_fmp_mode_composite_uses_fmp_primary(tmp_path):
    cfg = _load_config()
    provider_set = build_providers(cfg, mode="fmp_primary_yfinance_fallback")
    composite = provider_set.price_live
    assert isinstance(composite, CompositePriceProvider)
    assert isinstance(composite._primary, FMPPriceProvider)


def test_fmp_mode_composite_uses_yfinance_fallback(tmp_path):
    cfg = _load_config()
    provider_set = build_providers(cfg, mode="fmp_primary_yfinance_fallback")
    composite = provider_set.price_live
    assert isinstance(composite, CompositePriceProvider)
    assert isinstance(composite._fallback, YFinancePriceProvider)


def test_active_mode_is_fmp_primary_after_s4_3():
    """S4.3 complete: active_mode must be fmp_primary_yfinance_fallback."""
    cfg = _load_config()
    assert cfg["active_mode"] == "fmp_primary_yfinance_fallback", (
        f"active_mode is {cfg['active_mode']!r} — expected fmp_primary_yfinance_fallback after S4.3"
    )
