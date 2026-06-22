"""S1.2 — PickleProvider tests."""

from __future__ import annotations

import pickle
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from codex_backed.data.loader import DataLoadError
from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.capabilities import ProviderCapabilities
from codex_backed.data.providers.pickle_provider import PickleProvider

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

# Business-day dates covering 2022-01-03 to 2022-06-30 (approx 125 rows)
_DATES = pd.bdate_range("2022-01-03", "2022-06-30")


def _make_df(base_price: float = 100.0) -> pd.DataFrame:
    n = len(_DATES)
    return pd.DataFrame(
        {
            "Open": [base_price + i * 0.1 for i in range(n)],
            "High": [base_price + 5 + i * 0.1 for i in range(n)],
            "Low": [base_price - 3 + i * 0.1 for i in range(n)],
            "Close": [base_price + 2 + i * 0.1 for i in range(n)],
            "Volume": [1_000_000] * n,
        },
        index=_DATES,
    )


@pytest.fixture
def prices_pkl(tmp_path: Path) -> Path:
    """Small deterministic pickle with AAPL, MSFT, SPY, QQQ."""
    data = {
        "AAPL": _make_df(150.0),
        "MSFT": _make_df(250.0),
        "SPY": _make_df(450.0),
        "QQQ": _make_df(350.0),
    }
    pkl_path = tmp_path / "prices.pkl"
    with pkl_path.open("wb") as fh:
        pickle.dump(data, fh)
    return pkl_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fetch_history_batch_returns_bars_for_known_tickers(prices_pkl):
    provider = PickleProvider(prices_pkl)
    result = provider.fetch_history_batch(
        ["AAPL", "MSFT"],
        start=date(2022, 1, 1),
        end=date(2022, 12, 31),
    )
    assert "AAPL" in result
    assert "MSFT" in result
    assert len(result["AAPL"]) > 0
    assert len(result["MSFT"]) > 0
    # Each bar has the expected OHLCV keys
    bar = result["AAPL"][0]
    assert all(k in bar for k in ("date", "open", "high", "low", "close", "volume"))


def test_fetch_history_batch_filters_by_ticker(prices_pkl):
    """Only requested tickers returned; SPY and QQQ always pass through."""
    provider = PickleProvider(prices_pkl)
    result = provider.fetch_history_batch(
        ["AAPL"],
        start=date(2022, 1, 1),
        end=date(2022, 12, 31),
    )
    assert "AAPL" in result
    # SPY and QQQ always included
    assert "SPY" in result
    assert "QQQ" in result
    # MSFT was not requested and is not a passthrough ticker
    assert "MSFT" not in result


def test_fetch_history_batch_filters_by_date_range(prices_pkl):
    provider = PickleProvider(prices_pkl)
    start = date(2022, 3, 1)
    end = date(2022, 3, 31)
    result = provider.fetch_history_batch(["AAPL"], start=start, end=end)

    assert "AAPL" in result
    for bar in result["AAPL"]:
        assert start.isoformat() <= bar["date"] <= end.isoformat(), (
            f"Bar date {bar['date']} outside [{start}, {end}]"
        )


def test_fetch_live_batch_raises(prices_pkl):
    provider = PickleProvider(prices_pkl)
    with pytest.raises(ProviderError, match="historical-only"):
        provider.fetch_live_batch(["AAPL"])


def test_capabilities_declares_no_fundamentals(prices_pkl):
    provider = PickleProvider(prices_pkl)
    assert provider.capabilities.supports_fundamentals is False
    assert len(provider.capabilities.fundamentals_fields) == 0
    assert provider.capabilities.supports_prices is True


def test_missing_pickle_raises_data_load_error(tmp_path):
    provider = PickleProvider(tmp_path / "nonexistent.pkl")
    with pytest.raises(DataLoadError):
        provider.fetch_history_batch(
            ["AAPL"],
            start=date(2022, 1, 1),
            end=date(2022, 12, 31),
        )
