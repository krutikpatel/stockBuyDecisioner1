from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean, median

from codex_backed.simulation.trade import SimulatedTrade


@dataclass(frozen=True)
class TradeMetrics:
    count: int
    avg_realized_return_pct: float | None
    median_realized_return_pct: float | None
    win_rate_pct: float | None
    profit_factor: float | None
    avg_mae_pct: float | None
    avg_mfe_pct: float | None
    avg_mfe_capture_pct: float | None
    avg_days_held: float | None
    partial_profit_hit_rate_pct: float | None
    exit_reason_counts: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)


def build_trade_metrics(trades: list[SimulatedTrade]) -> TradeMetrics:
    if not trades:
        return TradeMetrics(
            count=0,
            avg_realized_return_pct=None,
            median_realized_return_pct=None,
            win_rate_pct=None,
            profit_factor=None,
            avg_mae_pct=None,
            avg_mfe_pct=None,
            avg_mfe_capture_pct=None,
            avg_days_held=None,
            partial_profit_hit_rate_pct=None,
            exit_reason_counts={},
        )

    returns = [trade.realized_return_pct for trade in trades]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    captures = [trade.mfe_capture_pct for trade in trades if trade.mfe_capture_pct is not None]
    exit_counts: dict[str, int] = {}
    for trade in trades:
        exit_counts[trade.exit_reason] = exit_counts.get(trade.exit_reason, 0) + 1

    return TradeMetrics(
        count=len(trades),
        avg_realized_return_pct=round(mean(returns), 4),
        median_realized_return_pct=round(median(returns), 4),
        win_rate_pct=round(len(wins) / len(trades) * 100.0, 4),
        profit_factor=round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
        avg_mae_pct=round(mean(trade.mae_pct for trade in trades), 4),
        avg_mfe_pct=round(mean(trade.mfe_pct for trade in trades), 4),
        avg_mfe_capture_pct=round(mean(captures), 4) if captures else None,
        avg_days_held=round(mean(trade.days_held for trade in trades), 4),
        partial_profit_hit_rate_pct=round(
            sum(1 for trade in trades if trade.target_1_hit) / len(trades) * 100.0,
            4,
        ),
        exit_reason_counts=exit_counts,
    )


def group_trade_metrics(
    trades: list[SimulatedTrade],
    key_fn,
) -> dict[str, TradeMetrics]:
    grouped: dict[str, list[SimulatedTrade]] = {}
    for trade in trades:
        key = str(key_fn(trade))
        grouped.setdefault(key, []).append(trade)
    return {key: build_trade_metrics(values) for key, values in grouped.items()}

