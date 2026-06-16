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


def test_active_mode_unchanged_after_this_story():
    """Guard: active_mode must stay legacy_yfinance until S4.3."""
    cfg = _load_config()
    assert cfg["active_mode"] == "legacy_yfinance", (
        f"active_mode changed to {cfg['active_mode']!r} — this must not happen before S4.3"
    )
