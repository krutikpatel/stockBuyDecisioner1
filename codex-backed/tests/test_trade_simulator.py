from codex_backed.risk.stops import compute_stop_target
from codex_backed.simulation.entry_simulator import EntryExecutionSimulator
from codex_backed.simulation.trade_simulator import TradeSimulator


def _bar(idx, close, high=None, low=None, open_=None, volume=1000):
    return {
        "date": f"2024-01-{idx + 1:02d}",
        "open": open_ if open_ is not None else close,
        "high": high if high is not None else close + 1,
        "low": low if low is not None else close - 1,
        "close": close,
        "volume": volume,
    }


def _base_bars():
    return [_bar(idx, 100, high=101, low=99) for idx in range(20)]


def _exit_policy(**overrides):
    policy = {
        "max_simulation_days": 10,
        "initial_stop": {
            "method": "atr",
            "atr_multiplier": 2.0,
            "support_buffer_pct": 1.0,
        },
        "partial_profit": {
            "enabled": True,
            "target_r_multiple": 2.0,
            "sell_pct": 50,
            "move_stop_to_breakeven": True,
        },
        "trailing_stop": {
            "enabled": True,
            "method": "atr",
            "atr_multiplier": 2.5,
            "activate_after_target_1": True,
        },
        "time_stop": {
            "enabled": True,
            "days_without_progress": 5,
            "min_open_return_pct": 1.0,
        },
    }
    for key, value in overrides.items():
        policy[key].update(value)
    return policy


def test_entry_execution_next_open():
    bars = _base_bars()
    bars[6] = _bar(6, 103, open_=102.5)

    result = EntryExecutionSimulator().simulate(
        bars,
        signal_index=5,
        method="NEXT_OPEN",
        max_wait_days=10,
    )

    assert result.triggered
    assert result.entry_index == 6
    assert result.entry_price == 102.5


def test_compute_stop_target_uses_atr_risk_and_r_multiple():
    bars = _base_bars()

    result = compute_stop_target(
        bars,
        entry_index=15,
        entry_price=100,
        stop_config={"method": "atr", "atr_multiplier": 2.0, "support_buffer_pct": 1.0},
        partial_profit_config={"target_r_multiple": 2.0},
    )

    assert result.initial_stop == 96
    assert result.risk_per_share == 4
    assert result.target_1 == 108


def test_trade_simulator_takes_partial_profit_then_trails_remainder():
    bars = _base_bars()
    bars.extend(
        [
            _bar(20, 102, high=103, low=100),
            _bar(21, 106, high=109, low=104),
            _bar(22, 111, high=112, low=108),
            _bar(23, 105, high=108, low=104),
        ]
    )

    trade = TradeSimulator().simulate(
        bars,
        ticker="AAPL",
        signal_index=19,
        entry_index=19,
        entry_price=100,
        exit_policy=_exit_policy(),
    )

    assert trade.target_1_hit
    assert trade.exit_reason == "TRAILING_STOP_EXIT"
    assert [event.event_type for event in trade.events] == [
        "PARTIAL_PROFIT_TAKEN",
        "STOP_MOVED_TO_BREAKEVEN",
        "TRAILING_STOP_EXIT",
    ]
    assert trade.realized_return_pct > 0
    assert trade.mfe_pct == 12


def test_trade_simulator_time_stop_exits_flat_trade():
    bars = _base_bars()
    bars.extend([_bar(idx, 100, high=100.5, low=99.5) for idx in range(20, 30)])

    trade = TradeSimulator().simulate(
        bars,
        ticker="MSFT",
        signal_index=19,
        entry_index=19,
        entry_price=100,
        exit_policy=_exit_policy(),
    )

    assert trade.exit_reason == "TIME_STOP_EXIT"
    assert trade.days_held == 5
    assert trade.realized_return_pct == 0


def test_trade_simulator_can_move_stop_to_breakeven_before_partial_target():
    bars = _base_bars()
    bars.extend(
        [
            _bar(20, 103, high=104.5, low=100),
            _bar(21, 100, high=101, low=99.5),
        ]
    )
    policy = _exit_policy(
        partial_profit={
            "target_r_multiple": 2.0,
            "breakeven_after_r_multiple": 1.0,
        },
        time_stop={"days_without_progress": 10},
    )

    trade = TradeSimulator().simulate(
        bars,
        ticker="AAPL",
        signal_index=19,
        entry_index=19,
        entry_price=100,
        exit_policy=policy,
    )

    assert not trade.target_1_hit
    assert trade.exit_reason == "STOP_LOSS_EXIT"
    assert trade.exit_price == 100
    assert [event.event_type for event in trade.events] == [
        "STOP_MOVED_TO_BREAKEVEN",
        "STOP_LOSS_EXIT",
    ]
