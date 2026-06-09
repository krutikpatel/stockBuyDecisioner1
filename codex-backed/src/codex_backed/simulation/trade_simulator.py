from __future__ import annotations

from typing import Any

from codex_backed.risk.stops import compute_atr, compute_stop_target
from codex_backed.simulation.trade import ExitEvent, SimulatedTrade


class TradeSimulator:
    """Bar-by-bar long trade simulator with partial profits and trailing stops."""

    def simulate(
        self,
        bars: list[dict[str, Any]],
        *,
        ticker: str,
        signal_index: int,
        entry_index: int,
        entry_price: float,
        exit_policy: dict[str, Any],
    ) -> SimulatedTrade:
        stop_target = compute_stop_target(
            bars,
            entry_index=entry_index,
            entry_price=entry_price,
            stop_config=exit_policy["initial_stop"],
            partial_profit_config=exit_policy["partial_profit"],
        )
        stop = stop_target.initial_stop
        target_1 = stop_target.target_1
        max_days = int(exit_policy["max_simulation_days"])
        partial_cfg = exit_policy["partial_profit"]
        trailing_cfg = exit_policy["trailing_stop"]
        time_cfg = exit_policy["time_stop"]
        partial_sell_pct = float(partial_cfg["sell_pct"])
        risk_per_share = max(entry_price - stop, 0.0)
        breakeven_r_multiple = partial_cfg.get("breakeven_after_r_multiple")
        breakeven_trigger = (
            entry_price + float(breakeven_r_multiple) * risk_per_share
            if breakeven_r_multiple is not None and risk_per_share > 0
            else None
        )

        position_pct = 100.0
        realized = 0.0
        events: list[ExitEvent] = []
        target_1_hit = False
        breakeven_moved = False
        trailing_active = False
        trailing_stop = stop
        max_high = entry_price
        min_low = entry_price
        exit_index = min(entry_index + max_days, len(bars) - 1)
        exit_date = bars[exit_index].get("date")
        exit_price = float(bars[exit_index]["close"])
        exit_reason = "MAX_SIM_WINDOW_EXIT"

        for day_offset in range(1, max_days + 1):
            idx = entry_index + day_offset
            if idx >= len(bars):
                exit_index = len(bars) - 1
                exit_date = bars[exit_index].get("date")
                exit_price = float(bars[exit_index]["close"])
                exit_reason = "MAX_SIM_WINDOW_EXIT"
                break

            bar = bars[idx]
            high = float(bar.get("high", bar["close"]))
            low = float(bar.get("low", bar["close"]))
            close = float(bar["close"])
            max_high = max(max_high, high)
            min_low = min(min_low, low)

            active_stop = trailing_stop if trailing_active else stop
            if low <= active_stop:
                realized += _leg_return(entry_price, active_stop, position_pct)
                events.append(_event(idx, bar, "TRAILING_STOP_EXIT" if trailing_active else "STOP_LOSS_EXIT", active_stop, position_pct, 0.0, entry_price))
                exit_index = idx
                exit_date = bar.get("date")
                exit_price = active_stop
                exit_reason = "TRAILING_STOP_EXIT" if trailing_active else "STOP_LOSS_EXIT"
                position_pct = 0.0
                break

            if (
                not breakeven_moved
                and not target_1_hit
                and breakeven_trigger is not None
                and high >= breakeven_trigger
                and bool(partial_cfg.get("move_stop_to_breakeven", False))
            ):
                stop = max(stop, entry_price)
                breakeven_moved = True
                events.append(_event(idx, bar, "STOP_MOVED_TO_BREAKEVEN", stop, position_pct, position_pct, entry_price))

            if not target_1_hit and bool(partial_cfg["enabled"]) and high >= target_1:
                sell_pct = min(partial_sell_pct, position_pct)
                realized += _leg_return(entry_price, target_1, sell_pct)
                events.append(_event(idx, bar, "PARTIAL_PROFIT_TAKEN", target_1, position_pct, position_pct - sell_pct, entry_price))
                position_pct -= sell_pct
                target_1_hit = True
                if bool(partial_cfg.get("move_stop_to_breakeven", False)) and not breakeven_moved:
                    stop = max(stop, entry_price)
                    breakeven_moved = True
                    events.append(_event(idx, bar, "STOP_MOVED_TO_BREAKEVEN", stop, position_pct, position_pct, entry_price))
                if bool(trailing_cfg.get("enabled", False)) and bool(trailing_cfg.get("activate_after_target_1", True)):
                    trailing_active = True
                    trailing_stop = max(stop, _trailing_stop_level(bars, idx, high, trailing_cfg))

            if trailing_active:
                trailing_stop = max(trailing_stop, _trailing_stop_level(bars, idx, max_high, trailing_cfg))

            if (
                bool(time_cfg.get("enabled", False))
                and day_offset >= int(time_cfg["days_without_progress"])
                and (max_high - entry_price) / entry_price * 100.0 < float(time_cfg["min_open_return_pct"])
            ):
                realized += _leg_return(entry_price, close, position_pct)
                events.append(_event(idx, bar, "TIME_STOP_EXIT", close, position_pct, 0.0, entry_price))
                exit_index = idx
                exit_date = bar.get("date")
                exit_price = close
                exit_reason = "TIME_STOP_EXIT"
                position_pct = 0.0
                break
        else:
            final_idx = min(entry_index + max_days, len(bars) - 1)
            final_bar = bars[final_idx]
            final_close = float(final_bar["close"])
            realized += _leg_return(entry_price, final_close, position_pct)
            events.append(_event(final_idx, final_bar, "MAX_SIM_WINDOW_EXIT", final_close, position_pct, 0.0, entry_price))
            exit_index = final_idx
            exit_date = final_bar.get("date")
            exit_price = final_close
            exit_reason = "MAX_SIM_WINDOW_EXIT"

        mae_pct = round((min_low - entry_price) / entry_price * 100.0, 4)
        mfe_pct = round((max_high - entry_price) / entry_price * 100.0, 4)
        mfe_capture = round(realized / mfe_pct * 100.0, 4) if mfe_pct > 0 else None

        return SimulatedTrade(
            ticker=ticker,
            signal_index=signal_index,
            entry_index=entry_index,
            entry_price=round(entry_price, 4),
            initial_stop=stop_target.initial_stop,
            target_1=target_1,
            target_1_hit=target_1_hit,
            partial_exit_pct=partial_sell_pct if target_1_hit else 0.0,
            exit_index=exit_index,
            exit_date=exit_date,
            exit_price=round(exit_price, 4),
            exit_reason=exit_reason,
            days_held=max(0, exit_index - entry_index),
            realized_return_pct=round(realized, 4),
            mae_pct=mae_pct,
            mfe_pct=mfe_pct,
            mfe_capture_pct=mfe_capture,
            events=events,
        )


def _trailing_stop_level(bars: list[dict[str, Any]], idx: int, reference_high: float, trailing_cfg: dict[str, Any]) -> float:
    if trailing_cfg.get("method") == "percent":
        pct = float(trailing_cfg.get("trailing_pct", 10.0))
        return reference_high * (1.0 - pct / 100.0)
    atr = compute_atr(bars, idx) or reference_high * 0.03
    return reference_high - float(trailing_cfg.get("atr_multiplier", 2.5)) * atr


def _leg_return(entry_price: float, exit_price: float, position_pct: float) -> float:
    return ((exit_price - entry_price) / entry_price * 100.0) * (position_pct / 100.0)


def _event(
    idx: int,
    bar: dict[str, Any],
    event_type: str,
    price: float,
    before: float,
    after: float,
    entry_price: float,
) -> ExitEvent:
    return ExitEvent(
        event_index=idx,
        event_date=bar.get("date"),
        event_type=event_type,
        event_price=round(price, 4),
        position_pct_before=round(before, 4),
        position_pct_after=round(after, 4),
        realized_return_pct=round(_leg_return(entry_price, price, before - after), 4),
        reason=event_type,
    )
