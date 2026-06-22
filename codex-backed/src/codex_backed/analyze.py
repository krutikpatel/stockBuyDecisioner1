from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from codex_backed.backtest.writer import write_csv, write_json
from codex_backed.config.loader import ConfigBundle
from codex_backed.data.providers import registry as _provider_registry
from codex_backed.data.providers.observability import StatsCollector
from codex_backed.entry.engine import EntryDecisionEngine
from codex_backed.features.builder import build_feature_snapshot_from_mapping
from codex_backed.features.historical_builder import HistoricalFeatureOptions, build_historical_feature_rows
from codex_backed.results import RunPaths
from codex_backed.risk.sizing import compute_position_size
from codex_backed.risk.stops import compute_stop_target
from codex_backed.data.bars import find_index_on_or_before


FetchBars = Callable[..., dict[str, list[dict[str, Any]]]]


@dataclass(frozen=True)
class AnalyzeOptions:
    tickers: list[str] | None = None
    horizons: list[str] | None = None
    period: str | None = None
    interval: str | None = None
    auto_adjust: bool | None = None
    data_mode: str | None = None


def run_watchlist_analysis(
    bundle: ConfigBundle,
    paths: RunPaths,
    options: AnalyzeOptions,
    *,
    fetch_bars: FetchBars | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    watchlist_cfg = bundle.get("watchlist")
    analysis_date = (today or date.today()).isoformat()
    tickers = _normalize_tickers(options.tickers or watchlist_cfg["tickers"])
    horizons = options.horizons or watchlist_cfg.get("horizons", ["short_term"])
    benchmarks = _normalize_tickers(watchlist_cfg.get("benchmark_tickers", ["SPY"]))
    yfinance_cfg = watchlist_cfg.get("yfinance", {})
    period = options.period or yfinance_cfg.get("period", "2y")
    interval = options.interval or yfinance_cfg.get("interval", "1d")
    auto_adjust = yfinance_cfg.get("auto_adjust", False) if options.auto_adjust is None else options.auto_adjust

    requested_data_tickers = list(dict.fromkeys([*tickers, *benchmarks]))

    if fetch_bars is not None:
        # Test-injection or legacy-explicit path
        _effective_fetch = fetch_bars
        _provider_name = "yfinance"
    else:
        # Registry path: build provider from config
        provider_cfg = bundle.data.get("data_provider", {})
        active_mode = options.data_mode or provider_cfg.get("active_mode", "legacy_yfinance")
        provider_set = _provider_registry.build_providers(provider_cfg, mode=active_mode)
        _price_provider = provider_set.price_live
        _provider_name = _price_provider.name

        def _effective_fetch(t, *, period, interval, auto_adjust=False):
            return _price_provider.fetch_live_batch(t, period=period, interval=interval)

    bars_by_ticker = _effective_fetch(
        requested_data_tickers,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
    )
    missing_data_tickers = [ticker for ticker in requested_data_tickers if ticker not in bars_by_ticker]
    if "SPY" not in bars_by_ticker:
        raise RuntimeError("Analyze requires SPY bars for market regime and relative strength")

    feature_rows = build_historical_feature_rows(
        bars_by_ticker,
        tickers=tickers,
        options=HistoricalFeatureOptions(
            start="1900-01-01",
            end=analysis_date,
            horizons=set(horizons),
            signal_frequency="daily",
        ),
    )
    latest_rows = _latest_rows_by_ticker_horizon(feature_rows)
    if not latest_rows:
        raise RuntimeError("No latest feature rows found for requested watchlist")

    engine = EntryDecisionEngine(bundle.get("entry"), bundle.get("technical_setup"))
    decision_rows: list[dict[str, Any]] = []
    for row in latest_rows:
        snapshot = build_feature_snapshot_from_mapping(row)
        decision = engine.decide(snapshot, horizon=str(row["horizon"]))
        decision_rows.append(_decision_record(decision, row, bars_by_ticker.get(decision.ticker, []), bundle.get("risk"), bundle.get("exit")))

    actionable_rows = sorted(
        [row for row in decision_rows if row["is_actionable"]],
        key=lambda row: (
            0 if row["horizon"] == "short_term" else 1,
            _label_rank(row["entry_label"]),
            -float(row["entry_score"]),
            row["ticker"],
        ),
    )
    decision_rows.sort(key=lambda row: (row["ticker"], row["horizon"]))

    stats = StatsCollector()
    stats.record_cache_miss("analyze")  # live data is always fresh
    stats.write_summary(paths.run_dir)

    write_csv(paths.entry_decisions_path, decision_rows)
    write_csv(paths.run_dir / "actionable_watchlist.csv", actionable_rows)
    write_json(
        paths.metrics_path,
        {
            "analysis_date": analysis_date,
            "requested_tickers": tickers,
            "requested_data_tickers": requested_data_tickers,
            "missing_data_tickers": missing_data_tickers,
            "latest_signal_date": max(row["date"] for row in decision_rows),
            "entry_decisions": {
                "count": len(decision_rows),
                "actionable_count": len(actionable_rows),
            },
            "by_horizon": _count_by(decision_rows, "horizon"),
            "by_entry_label": _count_by(decision_rows, "entry_label"),
            "by_entry_strategy": _count_by(decision_rows, "entry_strategy"),
            "data_source": {
                "provider": _provider_name,
                "period": period,
                "interval": interval,
                "auto_adjust": auto_adjust,
                "cache_used": False,
            },
        },
    )

    return {
        "run_id": paths.run_id,
        "analysis_date": analysis_date,
        "latest_signal_date": max(row["date"] for row in decision_rows),
        "tickers": len(tickers),
        "horizons": horizons,
        "data_source": _provider_name,
        "cache_used": False,
        "entry_decisions": len(decision_rows),
        "actionable": len(actionable_rows),
        "missing_data_tickers": missing_data_tickers,
        "run_dir": str(paths.run_dir),
    }


def _latest_rows_by_ticker_horizon(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["ticker"]), str(row["horizon"]))
        if key not in latest or str(row["date"]) > str(latest[key]["date"]):
            latest[key] = row
    return list(latest.values())


def _decision_record(
    decision,
    source_row: dict[str, Any],
    bars: list[dict[str, Any]],
    risk_config: dict[str, Any],
    exit_config: dict[str, Any],
) -> dict[str, Any]:
    snapshot = build_feature_snapshot_from_mapping(source_row)
    size = compute_position_size(
        entry_label=decision.entry_label,
        atr_percent=snapshot.atr_percent,
        earnings_days_away=snapshot.earnings_days_away,
        risk_config=risk_config,
    )
    exit_policy = exit_config["default_exit_policy"][decision.horizon]
    stop_target = None
    signal_index = find_index_on_or_before(bars, str(source_row["date"]))
    if signal_index is not None and source_row.get("price") is not None:
        stop_target = compute_stop_target(
            bars,
            entry_index=signal_index,
            entry_price=float(source_row["price"]),
            stop_config=exit_policy["initial_stop"],
            partial_profit_config=exit_policy["partial_profit"],
        )
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
        "price": source_row.get("price"),
        "market_regime": source_row.get("market_regime"),
        "archetype": source_row.get("archetype"),
        "position_size_multiplier": size.final_size_multiplier,
        "applied_size_caps": "|".join(size.applied_caps),
        "initial_stop": stop_target.initial_stop if stop_target else None,
        "target_1": stop_target.target_1 if stop_target else None,
        "reasons": "|".join(decision.reasons),
        "missing_data": "|".join(decision.missing_data),
        "matched_signals": "|".join(decision.matched_signals),
        "optional_signals": "|".join(decision.optional_signals),
    }

def _label_rank(label: str) -> int:
    return {
        "BUY_AGGRESSIVE": 0,
        "BUY_FULL": 1,
        "BUY_STARTER": 2,
        "WATCHLIST": 3,
        "NO_TRADE": 4,
    }.get(label, 99)


def _count_by(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field, "UNKNOWN"))
        counts[key] = counts.get(key, 0) + 1
    return [{field: key, "count": value} for key, value in sorted(counts.items())]


def _normalize_tickers(tickers: list[str]) -> list[str]:
    return list(dict.fromkeys(ticker.strip().upper() for ticker in tickers if ticker.strip()))
