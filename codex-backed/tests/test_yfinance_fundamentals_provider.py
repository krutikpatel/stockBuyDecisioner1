"""S3.3 — YFinance fundamentals provider tests."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.cache import DiskCache
from codex_backed.data.providers.yfinance_provider import YFinanceFundamentalsProvider

_FIXTURES = Path(__file__).parent / "fixtures" / "yfinance"
_INFO_AAPL = json.loads((_FIXTURES / "info_aapl.json").read_text())


def _provider(cache=None) -> YFinanceFundamentalsProvider:
    return YFinanceFundamentalsProvider(cache=cache)


def _patch_ticker(info_data: dict):
    mock_ticker = MagicMock()
    mock_ticker.info = info_data
    return patch("yfinance.Ticker", return_value=mock_ticker)


def test_prefetch_batch_calls_ticker_info_once_per_ticker():
    provider = _provider()
    with _patch_ticker(_INFO_AAPL) as mock_yf:
        provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    mock_yf.assert_called_once_with("AAPL")


def test_get_snapshot_returns_short_float_from_info():
    provider = _provider()
    with _patch_ticker(_INFO_AAPL):
        provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert snap.short_float == pytest.approx(0.0081)


def test_get_snapshot_returns_institutional_ownership_from_info():
    provider = _provider()
    with _patch_ticker(_INFO_AAPL):
        provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert snap.institutional_ownership == pytest.approx(0.6142)


def test_get_snapshot_returns_insider_ownership_from_info():
    provider = _provider()
    with _patch_ticker(_INFO_AAPL):
        provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert snap.insider_ownership == pytest.approx(0.0007)


def test_missing_info_field_yields_none_not_exception():
    partial_info = {"heldPercentInsiders": 0.001}  # missing most fields
    provider = _provider()
    with _patch_ticker(partial_info):
        provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert snap.institutional_ownership is None
    assert snap.short_float is None
    assert snap.insider_ownership == pytest.approx(0.001)


def test_unexpected_info_shape_logged_but_does_not_crash(caplog):
    import logging
    provider = _provider()
    with patch("yfinance.Ticker") as mock_yf:
        mock_yf.return_value.info = "not-a-dict"
        with caplog.at_level(logging.WARNING, logger="codex_backed.data.providers.yfinance_provider"):
            provider.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    snap = provider.get_snapshot("AAPL", date(2023, 10, 1))
    assert isinstance(snap, FundamentalsSnapshot)
    assert snap.short_float is None


def test_cache_ttl_respected(tmp_path):
    cache = DiskCache(tmp_path / "cache", schema_version=1, ttl_seconds=0.1)
    provider1 = _provider(cache=cache)
    with _patch_ticker(_INFO_AAPL) as mock_yf:
        provider1.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    assert mock_yf.call_count == 1

    time.sleep(0.15)  # let cache expire

    provider2 = _provider(cache=cache)
    with _patch_ticker(_INFO_AAPL) as mock_yf2:
        provider2.prefetch_batch(["AAPL"], (date(2023, 1, 1), date(2023, 12, 31)))
    # Cache expired → yfinance should be called again
    assert mock_yf2.call_count == 1
