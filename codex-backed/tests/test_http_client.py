"""S2.1 — HTTP client tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.http_client import HttpClient, _redact


def _mock_response(status_code: int, json_data=None, text: str = "") -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("no body")
    return resp


def test_get_returns_parsed_json_on_200():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _mock_response(200, json_data={"result": 42})
    client = HttpClient(session=session, max_retries=0)
    result = client.get("https://api.example.com/data?apikey=SECRET")
    assert result == {"result": 42}


def test_get_retries_on_500_up_to_max_retries():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _mock_response(500, text="server error")
    client = HttpClient(session=session, max_retries=2, backoff_seconds=0)
    with pytest.raises(ProviderError, match="Max retries"):
        client.get("https://api.example.com/data")
    # 1 initial + 2 retries = 3 calls
    assert session.get.call_count == 3


def test_get_does_not_retry_on_4xx():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _mock_response(403, text="forbidden")
    client = HttpClient(session=session, max_retries=3, backoff_seconds=0)
    with pytest.raises(ProviderError, match="403"):
        client.get("https://api.example.com/data")
    # must NOT retry
    assert session.get.call_count == 1


def test_get_raises_after_max_retries():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _mock_response(503)
    client = HttpClient(session=session, max_retries=1, backoff_seconds=0)
    with pytest.raises(ProviderError, match="Max retries \\(1\\)"):
        client.get("https://api.example.com/endpoint")
    assert session.get.call_count == 2


def test_timeout_enforced():
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.Timeout("timed out")
    client = HttpClient(session=session, timeout=0.001, max_retries=0)
    with pytest.raises(ProviderError, match="timed out"):
        client.get("https://api.example.com/slow")


def test_api_key_redacted_in_log_output(caplog):
    import logging
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _mock_response(500, text="err")
    client = HttpClient(session=session, max_retries=1, backoff_seconds=0)
    with caplog.at_level(logging.WARNING, logger="codex_backed.data.providers.http_client"):
        with pytest.raises(ProviderError):
            client.get("https://api.example.com/data?apikey=MY_SECRET_KEY")
    for record in caplog.records:
        assert "MY_SECRET_KEY" not in record.getMessage()
        assert "***" in record.getMessage()


def test_api_key_redacted_in_exception_message():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _mock_response(404, text="apikey=TOP_SECRET_TOKEN here")
    client = HttpClient(session=session, max_retries=0)
    with pytest.raises(ProviderError) as exc_info:
        client.get("https://api.example.com/data?apikey=TOP_SECRET_TOKEN")
    assert "TOP_SECRET_TOKEN" not in str(exc_info.value)
    assert "***" in str(exc_info.value)
