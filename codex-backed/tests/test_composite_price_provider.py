"""S2.5 — CompositePriceProvider tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.composite import CompositePriceProvider


def _bars(ticker: str, source: str = "p") -> list[dict]:
    return [{"date": "2024-01-05", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1e6, "_src": source}]


def _mock_provider(name: str, history_result: dict | Exception, live_result: dict | Exception | None = None) -> MagicMock:
    p = MagicMock()
    p.name = name
    if isinstance(history_result, Exception):
        p.fetch_history_batch.side_effect = history_result
    else:
        p.fetch_history_batch.return_value = history_result
    if live_result is None:
        p.fetch_live_batch.return_value = history_result if not isinstance(history_result, Exception) else {}
    elif isinstance(live_result, Exception):
        p.fetch_live_batch.side_effect = live_result
    else:
        p.fetch_live_batch.return_value = live_result
    return p


_START = date(2024, 1, 1)
_END = date(2024, 1, 31)


def test_primary_success_serves_all_tickers():
    primary = _mock_provider("fmp", {"AAPL": _bars("AAPL"), "MSFT": _bars("MSFT")})
    fallback = _mock_provider("yfinance", {})
    composite = CompositePriceProvider(primary, fallback)
    result = composite.fetch_history_batch(["AAPL", "MSFT"], _START, _END)
    assert "AAPL" in result and "MSFT" in result
    fallback.fetch_history_batch.assert_not_called()


def test_primary_failure_falls_back_for_all_tickers():
    primary = _mock_provider("fmp", ProviderError("down"))
    fallback = _mock_provider("yfinance", {"AAPL": _bars("AAPL"), "MSFT": _bars("MSFT")})
    composite = CompositePriceProvider(primary, fallback)
    result = composite.fetch_history_batch(["AAPL", "MSFT"], _START, _END)
    assert "AAPL" in result and "MSFT" in result


def test_primary_partial_coverage_falls_back_only_for_missing():
    primary = _mock_provider("fmp", {"AAPL": _bars("AAPL")})  # MSFT missing
    fallback = _mock_provider("yfinance", {"MSFT": _bars("MSFT")})
    composite = CompositePriceProvider(primary, fallback)
    result = composite.fetch_history_batch(["AAPL", "MSFT"], _START, _END)
    assert "AAPL" in result and "MSFT" in result
    # fallback called only for MSFT
    call_tickers = fallback.fetch_history_batch.call_args[0][0]
    assert "MSFT" in call_tickers
    assert "AAPL" not in call_tickers


def test_never_splices_bars_within_single_ticker():
    """Bars for one ticker must all come from the same source."""
    primary_bars = [{"date": "2024-01-05", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1e6}]
    fallback_bars = [{"date": "2024-01-04", "open": 99.0, "high": 100.0, "low": 98.0, "close": 99.5, "volume": 9e5}]
    primary = _mock_provider("fmp", {"AAPL": primary_bars})
    fallback = _mock_provider("yfinance", {"AAPL": fallback_bars})
    composite = CompositePriceProvider(primary, fallback)
    result = composite.fetch_history_batch(["AAPL"], _START, _END)
    # Must be exactly primary_bars — no splice with fallback_bars
    assert result["AAPL"] == primary_bars


def test_provenance_records_source_per_ticker():
    primary = _mock_provider("fmp", {"AAPL": _bars("AAPL")})
    fallback = _mock_provider("yfinance", {"MSFT": _bars("MSFT")})
    composite = CompositePriceProvider(primary, fallback)
    composite.fetch_history_batch(["AAPL", "MSFT"], _START, _END)
    assert composite.last_provenance["AAPL"] == "fmp"
    assert composite.last_provenance["MSFT"] == "yfinance"


def test_stats_increment_on_primary_failure():
    primary = _mock_provider("fmp", ProviderError("down"))
    fallback = _mock_provider("yfinance", {})
    composite = CompositePriceProvider(primary, fallback)
    composite.fetch_history_batch(["AAPL", "MSFT"], _START, _END)
    assert composite.stats.primary_failures >= 1


def test_stats_increment_on_fallback_serve():
    primary = _mock_provider("fmp", {})  # returns nothing for all tickers
    fallback = _mock_provider("yfinance", {"AAPL": _bars("AAPL"), "MSFT": _bars("MSFT")})
    composite = CompositePriceProvider(primary, fallback)
    composite.fetch_history_batch(["AAPL", "MSFT"], _START, _END)
    assert composite.stats.fallback_serves == 2
