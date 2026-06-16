"""S1.1 — Provider protocols + capabilities + snapshot dataclass."""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.base import FundamentalsProvider, PriceProvider
from codex_backed.data.providers.capabilities import ProviderCapabilities, supports_field
from codex_backed.features.snapshot import FeatureSnapshot

# ---------------------------------------------------------------------------
# Helpers — minimal concrete classes that satisfy each protocol
# ---------------------------------------------------------------------------

_CAPS = ProviderCapabilities(
    supports_prices=True,
    supports_fundamentals=False,
    fundamentals_fields=frozenset(),
    history_start_date=None,
    price_realtime=False,
    rate_limit_per_minute=60,
)

_FUND_CAPS = ProviderCapabilities(
    supports_prices=False,
    supports_fundamentals=True,
    fundamentals_fields=frozenset({"forward_pe", "eps_growth_yoy"}),
    history_start_date="2020-01-01",
    price_realtime=False,
    rate_limit_per_minute=300,
)


class _MinimalPriceProvider:
    name = "test_price"
    capabilities = _CAPS

    def fetch_history_batch(self, tickers, start, end):
        return {}

    def fetch_live_batch(self, tickers, period="2y", interval="1d"):
        return {}


class _MinimalFundamentalsProvider:
    name = "test_fund"
    capabilities = _FUND_CAPS

    def prefetch_batch(self, tickers, date_range):
        return None

    def get_snapshot(self, ticker, as_of_date):
        return FundamentalsSnapshot(ticker=ticker, as_of_date=as_of_date.isoformat())


# ---------------------------------------------------------------------------
# Protocol structure tests
# ---------------------------------------------------------------------------


def test_price_provider_protocol_has_required_methods():
    attrs = PriceProvider.__protocol_attrs__
    assert "fetch_history_batch" in attrs
    assert "fetch_live_batch" in attrs
    assert "name" in attrs
    assert "capabilities" in attrs


def test_fundamentals_provider_protocol_has_required_methods():
    attrs = FundamentalsProvider.__protocol_attrs__
    assert "prefetch_batch" in attrs
    assert "get_snapshot" in attrs
    assert "name" in attrs
    assert "capabilities" in attrs


def test_price_provider_concrete_satisfies_protocol():
    provider = _MinimalPriceProvider()
    assert isinstance(provider, PriceProvider)


def test_fundamentals_provider_concrete_satisfies_protocol():
    provider = _MinimalFundamentalsProvider()
    assert isinstance(provider, FundamentalsProvider)


# ---------------------------------------------------------------------------
# ProviderCapabilities tests
# ---------------------------------------------------------------------------


def test_capabilities_dataclass_is_frozen():
    caps = ProviderCapabilities(
        supports_prices=True,
        supports_fundamentals=True,
        fundamentals_fields=frozenset({"forward_pe"}),
        history_start_date=None,
        price_realtime=False,
        rate_limit_per_minute=60,
    )
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        caps.supports_prices = False  # type: ignore[misc]


def test_capabilities_supports_field_lookup():
    caps = ProviderCapabilities(
        supports_prices=True,
        supports_fundamentals=True,
        fundamentals_fields=frozenset({"forward_pe", "eps_growth_yoy", "gross_margin"}),
        history_start_date=None,
        price_realtime=False,
        rate_limit_per_minute=300,
    )
    assert supports_field(caps, "forward_pe") is True
    assert supports_field(caps, "eps_growth_yoy") is True
    assert supports_field(caps, "gross_margin") is True
    assert supports_field(caps, "short_float") is False
    assert supports_field(caps, "nonexistent_field") is False


# ---------------------------------------------------------------------------
# FundamentalsSnapshot tests
# ---------------------------------------------------------------------------


def test_fundamentals_snapshot_defaults_are_none():
    snap = FundamentalsSnapshot(ticker="AAPL", as_of_date="2024-01-15")

    # earnings_within_30_days defaults to False, not None
    assert snap.earnings_within_30_days is False

    # Every other optional field should default to None
    for f in dataclasses.fields(snap):
        if f.name in ("ticker", "as_of_date", "earnings_within_30_days"):
            continue
        assert getattr(snap, f.name) is None, (
            f"Expected None for {f.name}, got {getattr(snap, f.name)!r}"
        )


def test_fundamentals_snapshot_field_names_match_feature_snapshot_subset():
    """Every fundamentals field must also exist on FeatureSnapshot."""
    feature_fields = {f.name for f in dataclasses.fields(FeatureSnapshot)}
    for name in FundamentalsSnapshot.field_names():
        assert name in feature_fields, (
            f"FundamentalsSnapshot.{name} has no matching field on FeatureSnapshot"
        )


def test_fundamentals_snapshot_field_names_excludes_identity_fields():
    names = FundamentalsSnapshot.field_names()
    assert "ticker" not in names
    assert "as_of_date" not in names
    assert len(names) > 0
