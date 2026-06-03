"""Tests for backtest.entry_simulator."""
from __future__ import annotations

import pandas as pd
import pytest

from backtest.entry_simulator import EntrySimulator, ENTRY_METHODS


def _make_price_df(closes, opens=None, lows=None, volumes=None) -> pd.DataFrame:
    """Build a minimal price DataFrame for testing."""
    dates = pd.date_range("2023-01-02", periods=len(closes), freq="B")
    data = {"Close": closes}
    if opens:
        data["Open"] = opens
    if lows:
        data["Low"] = lows
    if volumes:
        data["Volume"] = volumes
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def simulator():
    return EntrySimulator()


@pytest.fixture
def simple_df():
    closes = [100, 101, 99, 98, 102, 105, 103, 104, 106, 108]
    return _make_price_df(closes)


class TestNextClose:
    def test_returns_next_bar_close(self, simulator, simple_df):
        signal_date = simple_df.index[0]
        result = simulator.simulate_entry(signal_date, simple_df, method="NEXT_CLOSE")
        assert result.entry_price == 101.0
        assert result.wait_days == 0
        assert result.not_triggered is False

    def test_last_bar_returns_none(self, simulator, simple_df):
        signal_date = simple_df.index[-1]
        result = simulator.simulate_entry(signal_date, simple_df, method="NEXT_CLOSE")
        assert result.entry_price is None
        assert result.not_triggered is True

    def test_empty_df_returns_not_triggered(self, simulator):
        result = simulator.simulate_entry(
            pd.Timestamp("2023-01-02"), pd.DataFrame(), method="NEXT_CLOSE"
        )
        assert result.entry_price is None
        assert result.not_triggered is True


class TestNextOpen:
    def test_uses_open_when_available(self, simulator):
        df = _make_price_df(closes=[100, 101], opens=[99, 100])
        signal_date = df.index[0]
        result = simulator.simulate_entry(signal_date, df, method="NEXT_OPEN")
        assert result.entry_price == 100.0   # next bar's Open
        assert result.wait_days == 0

    def test_falls_back_to_close_when_no_open(self, simulator, simple_df):
        signal_date = simple_df.index[0]
        result = simulator.simulate_entry(signal_date, simple_df, method="NEXT_OPEN")
        assert result.entry_price == simple_df["Close"].iloc[1]


class TestPullbackToSMA20:
    def test_triggers_when_low_touches_sma(self, simulator):
        # 30 bars of uptrend then a dip below SMA20
        closes = list(range(80, 110))   # 30 bars: 80..109 (SMA20 at bar 30 ~ 100)
        df = _make_price_df(closes, lows=[c - 3 for c in closes])
        signal_date = df.index[29]  # last bar of history
        # Add 5 future bars where low touches SMA
        future_closes = [108, 107, 106, 105, 104]
        future_lows   = [99,  98,  97,  96,  95]   # below SMA20 (~100)
        all_closes = closes + future_closes
        all_lows   = [c - 3 for c in closes] + future_lows
        full_df = _make_price_df(all_closes, lows=all_lows)
        result = simulator.simulate_entry(
            signal_date, full_df, method="PULLBACK_TO_SMA20", max_wait_days=10
        )
        assert result.not_triggered is False
        assert result.entry_price is not None
        assert result.wait_days >= 1

    def test_not_triggered_when_no_pullback(self, simulator):
        # Steadily rising prices — never touches SMA
        closes = list(range(100, 150))
        df = _make_price_df(closes, lows=[c - 1 for c in closes])
        signal_date = df.index[30]
        result = simulator.simulate_entry(
            signal_date, df, method="PULLBACK_TO_SMA20", max_wait_days=5
        )
        assert result.not_triggered is True


class TestPullbackToSMA50:
    def test_triggers_on_deeper_pullback(self, simulator):
        # Build price series with enough history for SMA50 and then a big dip
        closes = list(range(60, 120))  # 60 bars
        lows   = [c - 2 for c in closes]
        # Future bars that dip to SMA50 level
        future_closes = [118, 116, 114, 112, 110]
        future_lows   = [85, 84, 83, 82, 81]  # well below SMA50 (~90)
        all_closes = closes + future_closes
        all_lows   = lows + future_lows
        df = _make_price_df(all_closes, lows=all_lows)
        signal_date = df.index[59]
        result = simulator.simulate_entry(
            signal_date, df, method="PULLBACK_TO_SMA50", max_wait_days=10
        )
        assert result.not_triggered is False


class TestBreakoutConfirmation:
    def test_triggers_on_breakout_with_volume(self, simulator):
        closes  = [100] * 20 + [100]  # 20-bar base at 100, then signal bar
        volumes = [1_000_000] * 21
        df = _make_price_df(closes, volumes=volumes)
        signal_date = df.index[-1]

        # Add future bar that breaks out
        future_closes  = [105, 103]
        future_volumes = [2_000_000, 500_000]
        all_closes  = closes + future_closes
        all_volumes = volumes + future_volumes
        full_df = _make_price_df(all_closes, volumes=all_volumes)
        result = simulator.simulate_entry(
            signal_date, full_df, method="BREAKOUT_CONFIRMATION", max_wait_days=5
        )
        assert result.not_triggered is False
        assert result.entry_price == 105.0

    def test_not_triggered_if_no_volume_expansion(self, simulator):
        closes  = [100] * 21
        volumes = [1_000_000] * 21
        # Future bars that go above resistance but low volume
        future_closes  = [101, 102]
        future_volumes = [500_000, 600_000]  # below avg
        df = _make_price_df(closes + future_closes, volumes=volumes + future_volumes)
        signal_date = df.index[20]
        result = simulator.simulate_entry(
            signal_date, df, method="BREAKOUT_CONFIRMATION", max_wait_days=2
        )
        assert result.not_triggered is True


class TestInvalidMethod:
    def test_raises_on_unknown_method(self, simulator, simple_df):
        with pytest.raises(ValueError, match="Unknown entry method"):
            simulator.simulate_entry(simple_df.index[0], simple_df, method="INVALID")
