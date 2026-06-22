"""S2.4 — FMP price provider tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.budget import DailyBudget
from codex_backed.data.providers.cache import DiskCache
from codex_backed.data.providers.capabilities import ProviderCapabilities
from codex_backed.data.providers.fmp_provider import FMPPriceProvider
from codex_backed.data.providers.http_client import HttpClient

_FIXTURES = Path(__file__).parent / "fixtures" / "fmp"

_CAPABILITIES = ProviderCapabilities(
    supports_prices=True,
    supports_fundamentals=False,
    fundamentals_fields=frozenset(),
    history_start_date="2010-01-01",
    price_realtime=True,
    rate_limit_per_minute=300,
)


def _provider(tmp_path: Path, http_client: HttpClient | None = None) -> FMPPriceProvider:
    cache = DiskCache(tmp_path / "cache", schema_version=1)
    budget = DailyBudget(tmp_path / "budget.json", limit=None)
    return FMPPriceProvider(
        api_key="TEST_KEY",
        capabilities=_CAPABILITIES,
        cache=cache,
        budget=budget,
        http_client=http_client,
    )


def _mock_http(response_data) -> HttpClient:
    mock = MagicMock(spec=HttpClient)
    mock.get.return_value = response_data
    return mock


def test_fetch_history_batch_parses_recorded_response(tmp_path):
    data = json.loads((_FIXTURES / "historical_aapl.json").read_text())
    provider = _provider(tmp_path, http_client=_mock_http(data))
    result = provider.fetch_history_batch(
        ["AAPL"],
        start=date(2023, 12, 29),
        end=date(2024, 1, 5),
    )
    assert "AAPL" in result
    bars = result["AAPL"]
    assert len(bars) == 4
    assert bars[0]["date"] == "2023-12-29"
    assert bars[-1]["date"] == "2024-01-05"


def test_fetch_history_batch_normalizes_dates_to_iso(tmp_path):
    data = json.loads((_FIXTURES / "historical_aapl.json").read_text())
    provider = _provider(tmp_path, http_client=_mock_http(data))
    result = provider.fetch_history_batch(
        ["AAPL"], start=date(2023, 12, 29), end=date(2024, 1, 5)
    )
    for bar in result["AAPL"]:
        assert len(bar["date"]) == 10
        assert bar["date"].count("-") == 2


def test_fetch_history_batch_filters_by_date_range(tmp_path):
    data = json.loads((_FIXTURES / "historical_aapl.json").read_text())
    provider = _provider(tmp_path, http_client=_mock_http(data))
    result = provider.fetch_history_batch(
        ["AAPL"], start=date(2024, 1, 3), end=date(2024, 1, 5)
    )
    for bar in result["AAPL"]:
        assert "2024-01-03" <= bar["date"] <= "2024-01-05"


def test_fetch_history_batch_uses_cache_on_second_call(tmp_path):
    data = json.loads((_FIXTURES / "historical_aapl.json").read_text())
    http = _mock_http(data)
    provider = _provider(tmp_path, http_client=http)
    provider.fetch_history_batch(["AAPL"], start=date(2023, 12, 29), end=date(2024, 1, 5))
    provider.fetch_history_batch(["AAPL"], start=date(2023, 12, 29), end=date(2024, 1, 5))
    # Second call should use cache — only 1 HTTP call total
    assert http.get.call_count == 1


def test_fetch_history_batch_uses_stable_eod_endpoint(tmp_path):
    data = json.loads((_FIXTURES / "historical_aapl.json").read_text())
    http = _mock_http(data)
    provider = _provider(tmp_path, http_client=http)
    provider.fetch_history_batch(["AAPL"], start=date(2023, 12, 29), end=date(2024, 1, 5))
    url = http.get.call_args.args[0]
    params = http.get.call_args.kwargs["params"]
    assert url == "https://financialmodelingprep.com/stable/historical-price-eod/full"
    assert params["symbol"] == "AAPL"
    assert "/api/v3/" not in url


def test_fetch_history_batch_skips_tickers_returning_empty(tmp_path):
    http = _mock_http({"symbol": "UNKNOWN", "historical": []})
    provider = _provider(tmp_path, http_client=http)
    result = provider.fetch_history_batch(
        ["UNKNOWN"], start=date(2024, 1, 1), end=date(2024, 1, 5)
    )
    assert "UNKNOWN" not in result


def test_fetch_live_batch_parses_stable_history_endpoint(tmp_path):
    data = json.loads((_FIXTURES / "historical_aapl.json").read_text())
    http = MagicMock(spec=HttpClient)
    http.get.side_effect = [data, data]
    provider = _provider(tmp_path, http_client=http)
    result = provider.fetch_live_batch(["AAPL", "MSFT"], period="5y")
    assert "AAPL" in result
    assert "MSFT" in result
    assert len(result["AAPL"]) == 4
    assert result["AAPL"][0]["close"] == 181.5
    assert http.get.call_count == 2


def test_capabilities_match_config_tier_capabilities(tmp_path):
    provider = _provider(tmp_path)
    assert provider.capabilities.supports_prices is True
    assert provider.capabilities.history_start_date == "2010-01-01"
    assert provider.capabilities.rate_limit_per_minute == 300


def test_4xx_error_does_not_corrupt_cache(tmp_path):
    http = MagicMock(spec=HttpClient)
    http.get.side_effect = ProviderError("HTTP 403: forbidden")
    provider = _provider(tmp_path, http_client=http)

    # First call: fails
    result = provider.fetch_history_batch(
        ["AAPL"], start=date(2024, 1, 1), end=date(2024, 1, 5)
    )
    assert result == {}

    # Cache should be empty (error must not have been written)
    cache = DiskCache(tmp_path / "cache", schema_version=1)
    assert cache.get("history/AAPL/2024-01-01/2024-01-05") is None


def test_request_counted_against_daily_budget(tmp_path):
    data = json.loads((_FIXTURES / "historical_aapl.json").read_text())
    cache = DiskCache(tmp_path / "cache", schema_version=1)
    budget = DailyBudget(tmp_path / "budget.json", limit=100)
    provider = FMPPriceProvider(
        api_key="K",
        capabilities=_CAPABILITIES,
        cache=cache,
        budget=budget,
        http_client=_mock_http(data),
    )
    provider.fetch_history_batch(["AAPL"], start=date(2023, 12, 29), end=date(2024, 1, 5))
    assert budget.current_count() == 1
