"""S3.5 — historical_builder accepts warmed FundamentalsProvider."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, call

import pytest

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.features.historical_builder import (
    HistoricalFeatureOptions,
    build_historical_feature_rows,
)

# ---------------------------------------------------------------------------
# Minimal bar list helpers
# ---------------------------------------------------------------------------

def _bar(date_str: str, close: float = 100.0) -> dict:
    return {
        "date": date_str,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": 1_000_000,
    }


def _bars(n: int = 120, start_year: int = 2022) -> list[dict]:
    """Build n daily bars starting 2022-01-03 with linearly increasing close."""
    from datetime import date, timedelta
    bars = []
    d = date(start_year, 1, 3)
    close = 100.0
    for _ in range(n):
        bars.append({
            "date": d.isoformat(),
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1_000_000,
        })
        close += 0.5
        d += timedelta(days=1)
        while d.weekday() >= 5:  # skip weekends
            d += timedelta(days=1)
    return bars


def _options(start: str = "2022-03-01", end: str = "2022-06-30") -> HistoricalFeatureOptions:
    return HistoricalFeatureOptions(start=start, end=end, horizons={"short_term"})


def _mock_fundamentals(snap: FundamentalsSnapshot) -> MagicMock:
    m = MagicMock()
    m.get_snapshot.return_value = snap
    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_builder_without_fundamentals_emits_none_for_fundamental_fields():
    bars = _bars()
    rows = build_historical_feature_rows(
        {"AAPL": bars, "SPY": bars},
        tickers=["AAPL"],
        options=_options(),
    )
    assert len(rows) > 0
    # All fundamental fields should be absent (None) on every row
    for row in rows:
        assert row.get("short_float") is None
        assert row.get("insider_ownership") is None
        assert row.get("trailing_pe") is None


def test_builder_with_fundamentals_merges_snapshot_into_row():
    bars = _bars()
    snap = FundamentalsSnapshot(
        ticker="AAPL",
        as_of_date="2022-04-01",
        short_float=0.05,
        trailing_pe=28.0,
        beta=1.2,
    )
    prov = _mock_fundamentals(snap)

    rows = build_historical_feature_rows(
        {"AAPL": bars, "SPY": bars},
        tickers=["AAPL"],
        options=_options(),
        fundamentals=prov,
    )
    assert len(rows) > 0
    for row in rows:
        assert row["short_float"] == pytest.approx(0.05)
        assert row["trailing_pe"] == pytest.approx(28.0)
        assert row["beta"] == pytest.approx(1.2)


def test_builder_never_calls_fundamentals_methods_other_than_get_snapshot():
    bars = _bars()
    snap = FundamentalsSnapshot(ticker="AAPL", as_of_date="2022-04-01")
    prov = _mock_fundamentals(snap)

    build_historical_feature_rows(
        {"AAPL": bars, "SPY": bars},
        tickers=["AAPL"],
        options=_options(),
        fundamentals=prov,
    )

    # Only get_snapshot should have been called — nothing else
    assert prov.get_snapshot.called
    prov.prefetch_batch.assert_not_called()


def test_builder_calls_get_snapshot_once_per_ticker_date():
    """Even with multiple horizons, get_snapshot is called once per (ticker, date)."""
    bars = _bars()
    snap = FundamentalsSnapshot(ticker="AAPL", as_of_date="2022-04-01")
    prov = _mock_fundamentals(snap)

    rows = build_historical_feature_rows(
        {"AAPL": bars, "SPY": bars},
        tickers=["AAPL"],
        options=HistoricalFeatureOptions(
            start="2022-03-01", end="2022-06-30",
            horizons={"short_term", "medium_term"},
        ),
        fundamentals=prov,
    )

    # Each (ticker, date) pair generates 2 horizon rows but 1 get_snapshot call
    assert len(rows) > 0
    unique_dates = {row["date"] for row in rows}
    assert prov.get_snapshot.call_count == len(unique_dates)


def test_unknown_snapshot_field_ignored_not_raises():
    """Snapshot getattr for a missing field returns None, never raises."""
    bars = _bars()

    # Use a real FundamentalsSnapshot — all its fields exist on FeatureSnapshot
    # per the dataclass contract, so there is no actual "unknown" field to error on.
    # This test verifies getattr(..., None) guards are in place by using a partial mock.
    mock_snap = MagicMock(spec=FundamentalsSnapshot)
    mock_snap.ticker = "AAPL"
    mock_snap.as_of_date = "2022-04-01"
    # Make every field_names() attribute return None
    for name in FundamentalsSnapshot.field_names():
        setattr(mock_snap, name, None)

    prov = _mock_fundamentals(mock_snap)

    # Must not raise even if getattr returns None for all fields
    rows = build_historical_feature_rows(
        {"AAPL": bars, "SPY": bars},
        tickers=["AAPL"],
        options=_options(),
        fundamentals=prov,
    )
    assert len(rows) > 0
    for row in rows:
        assert row["short_float"] is None
