from __future__ import annotations

from typing import Any

from codex_backed.data.bars import find_index_on_or_before
from codex_backed.entry.engine import EntryDecisionEngine
from codex_backed.entry.labels import ACTIONABLE_ENTRY_LABELS
from codex_backed.features.builder import build_feature_snapshot_from_mapping
from codex_backed.risk.sizing import compute_position_size
from codex_backed.simulation.entry_simulator import EntryExecutionSimulator
from codex_backed.simulation.trade_simulator import TradeSimulator


_ENTRY_ENGINE: EntryDecisionEngine | None = None
_ENTRY_CONFIG: dict[str, Any] | None = None
_TECHNICAL_CONFIG: dict[str, Any] | None = None
_RISK_CONFIG: dict[str, Any] | None = None
_EXIT_CONFIG: dict[str, Any] | None = None
_BACKTEST_CONFIG: dict[str, Any] | None = None


def worker_init(config_data: dict[str, dict[str, Any]]) -> None:
    global _ENTRY_ENGINE, _ENTRY_CONFIG, _TECHNICAL_CONFIG, _RISK_CONFIG, _EXIT_CONFIG, _BACKTEST_CONFIG
    _ENTRY_CONFIG = config_data["entry"]
    _TECHNICAL_CONFIG = config_data["technical_setup"]
    _RISK_CONFIG = config_data["risk"]
    _EXIT_CONFIG = config_data["exit"]
    _BACKTEST_CONFIG = config_data["backtest"]
    _ENTRY_ENGINE = EntryDecisionEngine(_ENTRY_CONFIG, _TECHNICAL_CONFIG)


def process_ticker(work: dict[str, Any]) -> dict[str, Any]:
    if _ENTRY_ENGINE is None:
        worker_init(work["config_data"])
    assert _ENTRY_ENGINE is not None
    assert _RISK_CONFIG is not None
    assert _EXIT_CONFIG is not None
    assert _BACKTEST_CONFIG is not None

    ticker = work["ticker"]
    rows = work["feature_rows"]
    bars = work["bars"]
    enabled_horizons = work["enabled_horizons"]
    entry_method = work["entry_method"]
    max_wait_days = work["max_wait_days"]
    entry_simulator = EntryExecutionSimulator()
    trade_simulator = TradeSimulator()

    entry_records: list[dict[str, Any]] = []
    trade_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for row in rows:
        horizon = row.get("horizon")
        if horizon not in enabled_horizons:
            continue
        try:
            snapshot = build_feature_snapshot_from_mapping(row)
            decision = _ENTRY_ENGINE.decide(snapshot, horizon=horizon)
            decision_record = _decision_to_record(decision, row)
            entry_records.append(decision_record)

            if decision.entry_label not in ACTIONABLE_ENTRY_LABELS:
                continue
            signal_index = find_index_on_or_before(bars, snapshot.date)
            if signal_index is None:
                continue
            entry = entry_simulator.simulate(
                bars,
                signal_index=signal_index,
                method=entry_method,
                max_wait_days=max_wait_days,
            )
            if not entry.triggered or entry.entry_index is None or entry.entry_price is None:
                continue
            size = compute_position_size(
                entry_label=decision.entry_label,
                atr_percent=snapshot.atr_percent,
                earnings_days_away=snapshot.earnings_days_away,
                risk_config=_RISK_CONFIG,
            )
            if size.final_size_multiplier <= 0:
                continue
            exit_policy = _EXIT_CONFIG["default_exit_policy"][horizon]
            trade = trade_simulator.simulate(
                bars,
                ticker=ticker,
                signal_index=signal_index,
                entry_index=entry.entry_index,
                entry_price=entry.entry_price,
                exit_policy=exit_policy,
            )
            trade_records.append(_trade_to_record(trade, decision_record, entry, size))
        except Exception as exc:  # keep one bad row from killing a worker
            errors.append({"ticker": ticker, "date": row.get("date"), "horizon": row.get("horizon"), "error": str(exc)})

    return {
        "ticker": ticker,
        "entry_decisions": entry_records,
        "trades": trade_records,
        "errors": errors,
    }


def _decision_to_record(decision, source_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": decision.ticker,
        "date": decision.date,
        "horizon": decision.horizon,
        "entry_label": decision.entry_label,
        "entry_score": round(decision.entry_score, 4),
        "confidence": round(decision.confidence, 4),
        "selected_setup": decision.selected_setup,
        "entry_strategy": decision.entry_strategy,
        "is_actionable": decision.is_actionable,
        "reasons": "|".join(decision.reasons),
        "missing_data": "|".join(decision.missing_data),
        "matched_signals": "|".join(decision.matched_signals),
        "optional_signals": "|".join(decision.optional_signals),
        "market_regime": source_row.get("market_regime"),
        "archetype": source_row.get("archetype"),
        "price": source_row.get("price"),
        "source_decision": source_row.get("decision"),
        "source_strategy": source_row.get("strategy_name"),
        "source_setup": source_row.get("setup"),
    }


def _trade_to_record(trade, decision_record: dict[str, Any], entry, size) -> dict[str, Any]:
    return {
        "ticker": decision_record["ticker"],
        "signal_date": decision_record["date"],
        "horizon": decision_record["horizon"],
        "entry_label": decision_record["entry_label"],
        "entry_strategy": decision_record["entry_strategy"],
        "selected_setup": decision_record["selected_setup"],
        "entry_date": entry.entry_date,
        "entry_index": entry.entry_index,
        "entry_price": trade.entry_price,
        "entry_method": entry.method_used,
        "entry_wait_days": entry.wait_days,
        "position_size_multiplier": size.final_size_multiplier,
        "applied_size_caps": "|".join(size.applied_caps),
        "initial_stop": trade.initial_stop,
        "target_1": trade.target_1,
        "target_1_hit": trade.target_1_hit,
        "partial_exit_pct": trade.partial_exit_pct,
        "exit_date": trade.exit_date,
        "exit_index": trade.exit_index,
        "exit_price": trade.exit_price,
        "exit_reason": trade.exit_reason,
        "days_held": trade.days_held,
        "realized_return_pct": trade.realized_return_pct,
        "mae_pct": trade.mae_pct,
        "mfe_pct": trade.mfe_pct,
        "mfe_capture_pct": trade.mfe_capture_pct,
        "event_count": len(trade.events),
        "market_regime": decision_record["market_regime"],
        "archetype": decision_record["archetype"],
        "source_decision": decision_record["source_decision"],
    }
