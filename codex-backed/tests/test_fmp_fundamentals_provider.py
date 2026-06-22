"""S3.2 — FMP fundamentals provider tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.budget import DailyBudget
from codex_backed.data.providers.cache import DiskCache
from codex_backed.data.providers.capabilities import ProviderCapabilities
from codex_backed.data.providers.fmp_provider import FMPFundamentalsProvider
from codex_backed.data.providers.http_client import HttpClient

_FIXTURES = Path(__file__).parent / "fixtures" / "fmp"

_CAPS = ProviderCapabilities(
    supports_prices=False,
    supports_fundamentals=True,
    fundamentals_fields=frozenset([
        "gross_margin", "net_margin", "roe", "roa", "trailing_pe",
        "market_cap", "beta", "sector", "industry",
        "earnings_days_away", "earnings_within_30_days",
    ]),
    history_start_date="2000-01-01",
    price_realtime=False,
    rate_limit_per_minute=300,
)

_KEY_METRICS = json.loads((_FIXTURES / "key_metrics_aapl.json").read_text())
_PROFILE = json.loads((_FIXTURES / "profile_aapl.json").read_text())
_CALENDAR = json.loads((_FIXTURES / "earning_calendar.json").read_text())


def _provider(tmp_path: Path, http_responses: list | None = None) -> tuple[FMPFundamentalsProvider, MagicMock]:
    cache = DiskCache(tmp_path / "cache", schema_version=1)
    budget = DailyBudget(tmp_path / "budget.json", limit=None)
    http = MagicMock(spec=HttpClient)
    if http_responses is not None:
        http.get.side_effect = http_responses
    provider = FMPFundamentalsProvider(
        api_key="TEST",
        capabilities=_CAPS,
        cache=cache,
        budget=budget,
        http_client=http,
    )
    return provider, http


def _normal_responses():
    """Five responses: key_metrics, ratios, financial_growth, profile, earnings."""
    return [_KEY_METRICS, _KEY_METRICS, _KEY_METRICS, _PROFILE, _CALENDAR]


def test_prefetch_batch_makes_no_call_for_empty_tickers(tmp_path):
    provider, http = _provider(tmp_path)
    provider.prefetch_batch([], (date(2023, 1, 1), date(2023, 12, 31)))
    http.get.assert_not_called()


def test_prefetch_batch_calls_each_endpoint_once_per_ticker(tmp_path):
    provider, http = _provider(tmp_path, http_responses=_normal_responses())
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    # 5 endpoints: key-metrics, ratios, financial-growth, profile, earnings
    assert http.get.call_count == 5


def test_prefetch_batch_uses_stable_fundamentals_endpoints(tmp_path):
    provider, http = _provider(tmp_path, http_responses=_normal_responses())
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    calls = http.get.call_args_list
    urls = [c.args[0] for c in calls]
    assert urls == [
        "https://financialmodelingprep.com/stable/key-metrics",
        "https://financialmodelingprep.com/stable/ratios",
        "https://financialmodelingprep.com/stable/financial-growth",
        "https://financialmodelingprep.com/stable/profile",
        "https://financialmodelingprep.com/stable/earnings",
    ]
    assert all(c.kwargs["params"]["symbol"] == "AAPL" for c in calls)
    assert all("/api/v3/" not in url for url in urls)


def test_get_snapshot_performs_no_io_after_prefetch(tmp_path):
    provider, http = _provider(tmp_path, http_responses=_normal_responses())
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    http.reset_mock()
    provider.get_snapshot("AAPL", date(2023, 10, 1))
    http.get.assert_not_called()


def test_get_snapshot_returns_field_values_through_aliases(tmp_path):
    provider, http = _provider(tmp_path, http_responses=_normal_responses())
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert isinstance(snap, FundamentalsSnapshot)
    assert snap.gross_margin == pytest.approx(0.4431)
    assert snap.net_margin == pytest.approx(0.2531)
    assert snap.roe == pytest.approx(1.608)
    assert snap.market_cap == pytest.approx(3_000_000_000_000)
    assert snap.sector == "Technology"


def test_get_snapshot_returns_none_for_fields_not_supported(tmp_path):
    provider, http = _provider(tmp_path, http_responses=_normal_responses())
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    # FMP does not provide these in our alias dict
    assert snap.insider_ownership is None
    assert snap.institutional_ownership is None
    assert snap.short_float is None


def test_get_snapshot_returns_none_for_dates_before_history_start_date(tmp_path):
    provider, http = _provider(tmp_path, http_responses=_normal_responses())
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    snap = provider.get_snapshot("AAPL", date(1999, 12, 31))  # before "2000-01-01"
    assert snap.gross_margin is None
    assert snap.roe is None


def test_earnings_days_away_computed_correctly_from_calendar(tmp_path):
    # as_of_date = 2024-01-15; next earnings = 2024-02-01 → 17 days
    provider, http = _provider(tmp_path, http_responses=_normal_responses())
    provider.prefetch_batch(["AAPL"], (date(2024, 1, 1), date(2024, 3, 31)))
    snap = provider.get_snapshot("AAPL", date(2024, 1, 15))
    assert snap.earnings_days_away == 17
    assert snap.earnings_within_30_days is True


def test_prefetch_uses_cache_on_second_call(tmp_path):
    provider, http = _provider(tmp_path, http_responses=_normal_responses() * 2)
    # First prefetch: 5 HTTP calls
    provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    assert http.get.call_count == 5

    # New provider instance pointing at same cache
    provider2, http2 = _provider(tmp_path)
    provider2.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    http2.get.assert_not_called()  # should hit disk cache
