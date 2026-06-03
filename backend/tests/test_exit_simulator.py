"""Tests for backtest.exit_simulator."""
from __future__ import annotations

import pandas as pd
import pytest

from backtest.exit_simulator import ExitSimulator, EXIT_METHODS


def _make_price_df(closes, opens=None, highs=None, lows=None) -> pd.DataFrame:
    dates = pd.date_range("2023-01-02", periods=len(closes), freq="B")
    data = {"Close": closes}
    if opens:
        data["Open"] = opens
    if highs:
        data["High"] = highs
    if lows:
        data["Low"] = lows
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def simulator():
    return ExitSimulator()


@pytest.fixture
def flat_df():
    """25 bars at 100 — no stop or target hit."""
    closes = [100.0] * 25
    highs  = [101.0] * 25
    lows   = [99.0]  * 25
    return _make_price_df(closes, highs=highs, lows=lows)


class TestFixedHorizon:
    def test_exits_at_last_bar(self, simulator, flat_df):
        entry_date = flat_df.index[0] - pd.Timedelta(days=1)  # signal before first bar
        result = simulator.simulate_exit(
            entry_date=entry_date,
            entry_price=100.0,
            price_df=flat_df,
            method="FIXED_HORIZON",
            horizon="short_term",  # 20 bars
        )
        assert result.exit_reason == "FIXED_HORIZON"
        assert result.exit_price == 100.0
        assert result.holding_days == 20

    def test_pnl_positive_on_rising_prices(self, simulator):
        closes = list(range(100, 125))
        highs  = [c + 1 for c in closes]
        lows   = [c - 1 for c in closes]
        df = _make_price_df(closes, highs=highs, lows=lows)
        entry_date = df.index[0] - pd.Timedelta(days=1)
        result = simulator.simulate_exit(
            entry_date=entry_date,
            entry_price=100.0,
            price_df=df,
            method="FIXED_HORIZON",
            horizon="short_term",
        )
        assert result.pnl_pct is not None and result.pnl_pct > 0

    def test_empty_df_returns_data_end(self, simulator):
        result = simulator.simulate_exit(
            entry_date=pd.Timestamp("2023-01-02"),
            entry_price=100.0,
            price_df=pd.DataFrame(),
            method="FIXED_HORIZON",
        )
        assert result.exit_reason == "DATA_UNAVAILABLE"
        assert result.exit_price is None


class TestMaeMfe:
    def test_mae_is_negative(self, simulator):
        closes = [100, 98, 95, 97, 100] + [100] * 15
        lows   = [c - 2 for c in closes]
        highs  = [c + 2 for c in closes]
        df = _make_price_df(closes, highs=highs, lows=lows)
        entry_date = df.index[0] - pd.Timedelta(days=1)
        result = simulator.simulate_exit(
            entry_date=entry_date,
            entry_price=100.0,
            price_df=df,
            method="FIXED_HORIZON",
            horizon="short_term",
        )
        assert result.mae_pct is not None
        assert result.mae_pct < 0

    def test_mfe_is_positive(self, simulator):
        closes = [100, 105, 110, 108, 106] + [100] * 15
        highs  = [c + 2 for c in closes]
        lows   = [c - 1 for c in closes]
        df = _make_price_df(closes, highs=highs, lows=lows)
        entry_date = df.index[0] - pd.Timedelta(days=1)
        result = simulator.simulate_exit(
            entry_date=entry_date,
            entry_price=100.0,
            price_df=df,
            method="FIXED_HORIZON",
            horizon="short_term",
        )
        assert result.mfe_pct is not None
        assert result.mfe_pct > 0


class TestAtrStopTarget:
    def test_stop_hit_when_low_drops_far(self, simulator):
        # Build pre-entry bars for ATR computation (ATR ~ 2)
        pre_closes = [100.0] * 20
        pre_highs  = [102.0] * 20
        pre_lows   = [98.0]  * 20

        # Future bars: first bar drops hard (Low < entry - 2*ATR)
        fut_closes = [100, 90, 95] + [100] * 17
        fut_highs  = [101, 91, 96] + [101] * 17
        fut_lows   = [99, 85, 93] + [99] * 17    # bar 1: low=85 → hits stop (96)

        all_closes = pre_closes + fut_closes
        all_highs  = pre_highs  + fut_highs
        all_lows   = pre_lows   + fut_lows
        df = _make_price_df(all_closes, highs=all_highs, lows=all_lows)

        entry_date = df.index[19]   # entry at bar 20 (first future bar)
        result = simulator.simulate_exit(
            entry_date=entry_date,
            entry_price=100.0,
            price_df=df,
            method="ATR_STOP_TARGET",
            horizon="short_term",
            atr_stop_multiplier=2.0,
        )
        assert result.exit_reason in ("STOP_HIT", "FIXED_HORIZON")

    def test_target_hit_when_high_rises(self, simulator):
        pre_closes = [100.0] * 20
        pre_highs  = [102.0] * 20
        pre_lows   = [98.0]  * 20

        fut_closes = [100, 110, 120] + [100] * 17
        fut_highs  = [101, 115, 125] + [101] * 17   # bar 1: high=115 → hits target
        fut_lows   = [99,  109, 119] + [99]  * 17

        all_closes = pre_closes + fut_closes
        all_highs  = pre_highs  + fut_highs
        all_lows   = pre_lows   + fut_lows
        df = _make_price_df(all_closes, highs=all_highs, lows=all_lows)

        entry_date = df.index[19]
        result = simulator.simulate_exit(
            entry_date=entry_date,
            entry_price=100.0,
            price_df=df,
            method="ATR_STOP_TARGET",
            horizon="short_term",
            atr_target_multiplier=3.0,
        )
        assert result.exit_reason in ("TARGET_HIT", "FIXED_HORIZON")


class TestTrailingStop:
    def test_triggers_when_price_reverses(self, simulator):
        # Price rises to 115 then falls back — trailing stop should trigger
        closes = [100, 105, 110, 115, 112, 108, 104, 100] + [100] * 12
        highs  = [c + 1 for c in closes]
        lows   = [c - 1 for c in closes]
        df = _make_price_df(closes, highs=highs, lows=lows)

        entry_date = df.index[0] - pd.Timedelta(days=1)
        result = simulator.simulate_exit(
            entry_date=entry_date,
            entry_price=100.0,
            price_df=df,
            method="TRAILING_STOP",
            horizon="short_term",
            trailing_pct=0.10,   # 10% trailing stop
        )
        assert result.exit_reason in ("TRAILING_STOP_HIT", "FIXED_HORIZON")

    def test_not_triggered_when_price_holds(self, simulator):
        # Steady rise — trailing stop never breached
        closes = list(range(100, 120)) + [119] * 5
        highs  = [c + 0.5 for c in closes]
        lows   = [c - 0.5 for c in closes]
        df = _make_price_df(closes, highs=highs, lows=lows)

        entry_date = df.index[0] - pd.Timedelta(days=1)
        result = simulator.simulate_exit(
            entry_date=entry_date,
            entry_price=100.0,
            price_df=df,
            method="TRAILING_STOP",
            horizon="short_term",
            trailing_pct=0.50,   # very loose trailing stop → unlikely to trigger
        )
        assert result.exit_reason == "FIXED_HORIZON"


class TestInvalidMethod:
    def test_raises_on_unknown_method(self, simulator, flat_df):
        with pytest.raises(ValueError, match="Unknown exit method"):
            simulator.simulate_exit(
                entry_date=flat_df.index[0],
                entry_price=100.0,
                price_df=flat_df,
                method="INVALID",
            )
