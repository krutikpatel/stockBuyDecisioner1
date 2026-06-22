"""S3.4 — CompositeFundamentalsProvider tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, call

import pytest

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.capabilities import ProviderCapabilities
from codex_backed.data.providers.composite import CompositeFundamentalsProvider


def _snap(ticker="AAPL", as_of="2023-10-01", **kwargs) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(ticker=ticker, as_of_date=as_of, **kwargs)


def _caps(fields: frozenset[str], history_start: str | None = None) -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_prices=False,
        supports_fundamentals=True,
        fundamentals_fields=fields,
        history_start_date=history_start,
        price_realtime=False,
        rate_limit_per_minute=60,
    )


def _mock_provider(snap: FundamentalsSnapshot, caps: ProviderCapabilities):
    m = MagicMock()
    m.capabilities = caps
    m.get_snapshot.return_value = snap
    m.signature.return_value = "mock"
    return m


def test_field_override_forces_fallback_even_when_primary_has_value():
    primary_snap = _snap(short_float=0.05, insider_ownership=0.10)
    fallback_snap = _snap(short_float=0.02, insider_ownership=0.20)

    primary = _mock_provider(primary_snap, _caps(frozenset(["short_float", "insider_ownership"])))
    fallback = _mock_provider(fallback_snap, _caps(frozenset(["short_float", "insider_ownership"])))

    provider = CompositeFundamentalsProvider(
        primary, fallback, field_overrides=frozenset(["short_float"])
    )
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))

    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert snap.short_float == pytest.approx(0.02)   # overridden → fallback
    assert snap.insider_ownership == pytest.approx(0.10)  # not overridden → primary


def test_primary_value_used_when_present_and_not_overridden():
    primary_snap = _snap(trailing_pe=25.0, sector="Technology")
    fallback_snap = _snap(trailing_pe=30.0, sector="Tech")

    primary = _mock_provider(primary_snap, _caps(frozenset(["trailing_pe", "sector"])))
    fallback = _mock_provider(fallback_snap, _caps(frozenset(["trailing_pe", "sector"])))

    provider = CompositeFundamentalsProvider(primary, fallback)
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))

    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert snap.trailing_pe == pytest.approx(25.0)
    assert snap.sector == "Technology"


def test_fallback_value_used_when_primary_returns_none():
    primary_snap = _snap(beta=None)
    fallback_snap = _snap(beta=1.25)

    primary = _mock_provider(primary_snap, _caps(frozenset(["beta"])))
    fallback = _mock_provider(fallback_snap, _caps(frozenset(["beta"])))

    provider = CompositeFundamentalsProvider(primary, fallback)
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))

    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert snap.beta == pytest.approx(1.25)


def test_fallback_value_used_when_primary_field_not_in_capabilities():
    primary_snap = _snap()  # short_float not in primary caps
    fallback_snap = _snap(short_float=0.08)

    primary = _mock_provider(primary_snap, _caps(frozenset(["trailing_pe"])))  # no short_float
    fallback = _mock_provider(fallback_snap, _caps(frozenset(["short_float"])))

    provider = CompositeFundamentalsProvider(primary, fallback)
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))

    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert snap.short_float == pytest.approx(0.08)


def test_fallback_value_used_when_date_before_primary_history_start():
    primary_snap = _snap(trailing_pe=20.0)
    fallback_snap = _snap(trailing_pe=18.0)

    # primary only has history from 2020 onward
    primary = _mock_provider(primary_snap, _caps(frozenset(["trailing_pe"]), history_start="2020-01-01"))
    fallback = _mock_provider(fallback_snap, _caps(frozenset(["trailing_pe"])))

    provider = CompositeFundamentalsProvider(primary, fallback)
    provider.prefetch_batch(["AAPL"], (date(2019, 1, 1), date(2019, 12, 31)))

    # as_of_date 2019-06-01 is before primary history_start 2020-01-01
    snap = provider.get_snapshot("AAPL", date(2019, 6, 1))
    assert snap.trailing_pe == pytest.approx(18.0)


def test_fallback_prefetch_only_called_for_needed_tickers_and_fields():
    primary_snap = _snap(trailing_pe=25.0)
    fallback_snap = _snap(short_float=0.05)

    primary = _mock_provider(primary_snap, _caps(frozenset(["trailing_pe"])))
    fallback = _mock_provider(fallback_snap, _caps(frozenset(["short_float"])))

    # No field_overrides → fallback.prefetch_batch should NOT be called during prefetch_batch
    provider = CompositeFundamentalsProvider(primary, fallback)
    provider.prefetch_batch(["AAPL", "MSFT"], (date(2023, 1, 1), date(2023, 12, 31)))

    fallback.prefetch_batch.assert_not_called()

    # But get_snapshot will trigger lazy fallback prefetch because short_float not in primary caps
    provider.get_snapshot("AAPL", date(2023, 10, 1))
    fallback.prefetch_batch.assert_called_once_with(["AAPL"], (date(2023, 10, 1), date(2023, 10, 1)))


def test_get_snapshot_performs_no_io_after_prefetch():
    """Second get_snapshot for same ticker must NOT call prefetch again."""
    primary_snap = _snap(beta=1.0)
    fallback_snap = _snap(short_float=0.03)

    primary = _mock_provider(primary_snap, _caps(frozenset(["beta"])))
    fallback = _mock_provider(fallback_snap, _caps(frozenset(["short_float"])))

    provider = CompositeFundamentalsProvider(primary, fallback)
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))

    provider.get_snapshot("AAPL", date(2023, 10, 1))  # first call triggers lazy fallback
    provider.get_snapshot("AAPL", date(2023, 10, 1))  # second call must NOT re-prefetch

    # fallback.prefetch_batch called exactly once (lazy on first get_snapshot, not again)
    assert fallback.prefetch_batch.call_count == 1


def test_capabilities_is_union_of_primary_and_fallback():
    primary = _mock_provider(_snap(), _caps(frozenset(["trailing_pe", "beta", "sector"])))
    fallback = _mock_provider(_snap(), _caps(frozenset(["short_float", "insider_ownership", "sector"])))

    provider = CompositeFundamentalsProvider(primary, fallback)
    caps = provider.capabilities

    assert caps.supports_fundamentals is True
    assert "trailing_pe" in caps.fundamentals_fields
    assert "beta" in caps.fundamentals_fields
    assert "short_float" in caps.fundamentals_fields
    assert "insider_ownership" in caps.fundamentals_fields
    assert "sector" in caps.fundamentals_fields
    assert len(caps.fundamentals_fields) == 5  # union, no duplicates
