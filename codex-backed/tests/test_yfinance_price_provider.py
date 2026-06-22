"""S1.3 — YFinancePriceProvider tests (prices only; fundamentals in S3.3)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.yfinance_provider import YFinancePriceProvider

# ---------------------------------------------------------------------------
# Helpers — build fake yfinance DataFrames
# ---------------------------------------------------------------------------

_DATES = pd.bdate_range("2022-01-03", periods=10)


def _flat_df(base: float = 100.0) -> pd.DataFrame:
    """Single-ticker flat DataFrame (no MultiIndex)."""
    n = len(_DATES)
    return pd.DataFrame(
        {
            "Open": [base] * n,
            "High": [base + 5] * n,
            "Low": [base - 3] * n,
            "Close": [base + 2] * n,
            "Volume": [1_000_000] * n,
        },
        index=_DATES,
    )


def _multi_ticker_df(*tickers: str) -> pd.DataFrame:
    """Multi-ticker DataFrame with ticker MultiIndex (as yfinance returns)."""
    frames = {t: _flat_df(100.0 + i * 10) for i, t in enumerate(tickers)}
    combined = pd.concat(
        {t: df for t, df in frames.items()}, axis=1
    )
    # yfinance puts tickers at the top level: df["AAPL"] -> OHLCV sub-frame
    combined.columns = combined.columns.swaplevel(0, 1)
    combined.sort_index(axis=1, level=0, inplace=True)
    return combined


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fetch_history_batch_calls_yf_download_with_correct_args():
    provider = YFinancePriceProvider()
    mock_df = _flat_df()

    with patch("yfinance.download", return_value=mock_df) as mock_dl:
        provider.fetch_history_batch(
            ["AAPL"],
            start=date(2022, 1, 3),
            end=date(2022, 1, 14),
        )

    mock_dl.assert_called_once()
    kwargs = mock_dl.call_args.kwargs
    assert kwargs.get("tickers") == ["AAPL"]
    assert kwargs.get("start") == "2022-01-03"
    assert kwargs.get("end") == "2022-01-14"
    assert kwargs.get("group_by") == "ticker"


def test_fetch_history_batch_normalizes_dataframe_to_bar_dicts():
    provider = YFinancePriceProvider()
    mock_df = _flat_df(150.0)

    with patch("yfinance.download", return_value=mock_df):
        result = provider.fetch_history_batch(
            ["AAPL"],
            start=date(2022, 1, 1),
            end=date(2022, 12, 31),
        )

    assert "AAPL" in result
    bar = result["AAPL"][0]
    assert all(k in bar for k in ("date", "open", "high", "low", "close", "volume"))
    assert isinstance(bar["close"], float)
    assert isinstance(bar["date"], str)


def test_fetch_live_batch_uses_period_and_interval():
    provider = YFinancePriceProvider()
    mock_df = _flat_df()

    with patch("yfinance.download", return_value=mock_df) as mock_dl:
        provider.fetch_live_batch(["AAPL"], period="6mo", interval="1d")

    kwargs = mock_dl.call_args.kwargs
    assert kwargs.get("period") == "6mo"
    assert kwargs.get("interval") == "1d"
    assert "start" not in kwargs
    assert "end" not in kwargs


def test_capabilities_declares_prices_only():
    provider = YFinancePriceProvider()
    assert provider.capabilities.supports_prices is True
    assert provider.capabilities.supports_fundamentals is False
    assert len(provider.capabilities.fundamentals_fields) == 0


def test_empty_response_raises_provider_error():
    provider = YFinancePriceProvider()
    empty_df = pd.DataFrame()

    with patch("yfinance.download", return_value=empty_df):
        with pytest.raises(ProviderError):
            provider.fetch_history_batch(
                ["AAPL"],
                start=date(2022, 1, 1),
                end=date(2022, 12, 31),
            )


def test_single_ticker_response_handled():
    """Single-ticker download returns flat DataFrame — parsed without KeyError."""
    provider = YFinancePriceProvider()
    single_df = _flat_df(200.0)

    with patch("yfinance.download", return_value=single_df):
        result = provider.fetch_history_batch(
            ["MSFT"],
            start=date(2022, 1, 1),
            end=date(2022, 12, 31),
        )

    assert "MSFT" in result
    assert len(result["MSFT"]) == len(_DATES)
