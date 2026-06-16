"""Test helper: patches HttpClient.get to return fixture data instead of hitting FMP API."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from codex_backed.data.providers.http_client import HttpClient

_FIXTURES = Path(__file__).parent


def _load_json(name: str) -> Any:
    return json.loads((_FIXTURES / name).read_text())


def _route_fmp_response(url: str, params: dict | None = None) -> Any:
    """Return fixture JSON based on URL path."""
    url = str(url)
    if "/historical/earning_calendar/" in url:
        return _load_json("earning_calendar.json")
    if "/key-metrics/" in url:
        return _load_json("key_metrics_aapl.json")
    if "/profile/" in url:
        return _load_json("profile_aapl.json")
    if "/historical-price-full/" in url:
        return _load_json("historical_aapl.json")
    return {}


def _patched_get(self: HttpClient, url: str, params: dict | None = None) -> Any:
    return _route_fmp_response(url, params)


@contextmanager
def mock_fmp_http():
    """Context manager: redirects all HttpClient.get calls to fixture data."""
    with patch.object(HttpClient, "get", _patched_get):
        yield
