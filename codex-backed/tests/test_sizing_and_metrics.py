from pathlib import Path

from codex_backed.backtest.metrics import build_trade_metrics
from codex_backed.config.loader import load_config_bundle
from codex_backed.risk.sizing import compute_position_size
from codex_backed.simulation.trade import SimulatedTrade


def _risk_config():
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    return load_config_bundle(config_dir).get("risk")


def _trade(return_pct, reason="MAX_SIM_WINDOW_EXIT", target_1_hit=False):
    return SimulatedTrade(
        ticker="AAPL",
        signal_index=0,
        entry_index=1,
        entry_price=100,
        initial_stop=95,
        target_1=110,
        target_1_hit=target_1_hit,
        partial_exit_pct=50 if target_1_hit else 0,
        exit_index=5,
        exit_date="2024-01-06",
        exit_price=100 + return_pct,
        exit_reason=reason,
        days_held=4,
        realized_return_pct=return_pct,
        mae_pct=-3,
        mfe_pct=10,
        mfe_capture_pct=return_pct / 10 * 100 if return_pct > 0 else None,
        events=[],
    )


def test_position_size_applies_high_atr_cap():
    result = compute_position_size(
        entry_label="BUY_FULL",
        atr_percent=6.0,
        earnings_days_away=None,
        risk_config=_risk_config(),
    )

    assert result.base_size_multiplier == 1.0
    assert result.final_size_multiplier == 0.5
    assert result.applied_caps == ["HIGH_ATR_CAP"]


def test_position_size_avoids_entries_too_close_to_earnings():
    result = compute_position_size(
        entry_label="BUY_AGGRESSIVE",
        atr_percent=2.0,
        earnings_days_away=2,
        risk_config=_risk_config(),
    )

    assert result.final_size_multiplier == 0.0
    assert "EARNINGS_AVOID" in result.applied_caps


def test_build_trade_metrics_aggregates_lifecycle_results():
    trades = [
        _trade(10, reason="TRAILING_STOP_EXIT", target_1_hit=True),
        _trade(-5, reason="STOP_LOSS_EXIT", target_1_hit=False),
        _trade(4, reason="MAX_SIM_WINDOW_EXIT", target_1_hit=True),
    ]

    metrics = build_trade_metrics(trades)

    assert metrics.count == 3
    assert metrics.avg_realized_return_pct == 3
    assert metrics.median_realized_return_pct == 4
    assert metrics.win_rate_pct == 66.6667
    assert metrics.profit_factor == 2.8
    assert metrics.partial_profit_hit_rate_pct == 66.6667
    assert metrics.exit_reason_counts["TRAILING_STOP_EXIT"] == 1
    assert metrics.exit_reason_counts["STOP_LOSS_EXIT"] == 1
