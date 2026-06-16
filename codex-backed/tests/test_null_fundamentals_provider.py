"""S1.4 — NullFundamentalsProvider tests."""

from __future__ import annotations

import dataclasses
from datetime import date
from unittest.mock import patch

from codex_backed.data.providers.null_fundamentals import NullFundamentalsProvider


def test_prefetch_batch_is_noop():
    provider = NullFundamentalsProvider()
    # Must not raise and must not have side effects
    result = provider.prefetch_batch(["AAPL", "MSFT"], (date(2022, 1, 1), date(2023, 1, 1)))
    assert result is None


def test_get_snapshot_returns_all_none():
    provider = NullFundamentalsProvider()
    provider.prefetch_batch(["AAPL"], (date(2022, 1, 1), date(2023, 1, 1)))
    snap = provider.get_snapshot("AAPL", date(2022, 6, 1))

    assert snap.ticker == "AAPL"
    assert snap.earnings_within_30_days is False

    for f in dataclasses.fields(snap):
        if f.name in ("ticker", "as_of_date", "earnings_within_30_days"):
            continue
        assert getattr(snap, f.name) is None, (
            f"Expected None for {f.name}, got {getattr(snap, f.name)!r}"
        )


def test_get_snapshot_has_no_io():
    """get_snapshot must not touch the filesystem or network."""
    provider = NullFundamentalsProvider()
    # No prefetch — get_snapshot still works
    with (
        patch("builtins.open", side_effect=AssertionError("filesystem access")),
        patch("urllib.request.urlopen", side_effect=AssertionError("network access")),
    ):
        snap = provider.get_snapshot("TSLA", date(2023, 3, 15))

    assert snap.ticker == "TSLA"


def test_capabilities_declares_no_fundamentals():
    provider = NullFundamentalsProvider()
    assert provider.capabilities.supports_fundamentals is False
    assert len(provider.capabilities.fundamentals_fields) == 0
    assert provider.capabilities.supports_prices is False
