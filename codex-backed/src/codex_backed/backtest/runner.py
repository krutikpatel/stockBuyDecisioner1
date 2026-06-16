from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codex_backed.backtest.worker import process_ticker, worker_init
from codex_backed.backtest.writer import (
    ENTRY_DECISIONS_COLUMNS,
    TRADES_COLUMNS,
    build_input_quality_metrics,
    build_record_metrics,
    build_sliced_metrics,
    write_csv,
    write_json,
    write_lifecycle_report,
)
from codex_backed.config.loader import ConfigBundle
from codex_backed.data.fundamentals_snapshot import FUNDAMENTALS_SNAPSHOT_SCHEMA_VERSION
from codex_backed.data.loader import group_feature_rows_by_ticker, load_feature_rows
from codex_backed.data.providers import registry
from codex_backed.data.providers.observability import StatsCollector
from codex_backed.features.feature_cache import load_or_build_feature_rows
from codex_backed.features.historical_builder import HistoricalFeatureOptions, build_historical_feature_rows
from codex_backed.results import RunPaths


@dataclass(frozen=True)
class BacktestOptions:
    tickers: list[str] | None = None
    start: str | None = None
    end: str | None = None
    workers: int | None = None
    feature_source: str | None = None
    force_refresh: bool = False
    rebuild_feature_cache: bool = False
    no_report: bool = False
    data_mode: str | None = None


def run_lifecycle_backtest(bundle: ConfigBundle, paths: RunPaths, options: BacktestOptions) -> dict[str, Any]:
    backtest_cfg = bundle.get("backtest")
    horizons = {
        name
        for name, cfg in backtest_cfg["horizons"].items()
        if cfg.get("enabled", False)
    }
    start = options.start or backtest_cfg["date_range"]["start"]
    end = options.end or backtest_cfg["date_range"]["end"]
    tickers = [ticker.upper() for ticker in options.tickers] if options.tickers else _default_backtest_tickers(bundle)
    data_sources = backtest_cfg["data_sources"]
    prices_path = _resolve_path(data_sources["prices_cache_path"])
    source_config = backtest_cfg.get("feature_generation", {})
    feature_source = options.feature_source or source_config.get("source") or data_sources.get("feature_source") or "native"

    provider_cfg = bundle.data.get("data_provider", {})
    active_mode = options.data_mode or provider_cfg.get("active_mode", "legacy_yfinance")
    provider_set = registry.build_providers(
        provider_cfg,
        mode=active_mode,
        pickle_path_override=str(prices_path),
    )
    from datetime import date as _date
    bars_by_ticker = provider_set.price_backtest.fetch_history_batch(
        tickers,
        start=_date.fromisoformat(start),
        end=_date.fromisoformat(end),
    )
    provider_set.fundamentals.prefetch_batch(
        tickers,
        (_date.fromisoformat(start), _date.fromisoformat(end)),
    )
    feature_rows, feature_diagnostics = _load_or_build_features(
        bundle=bundle,
        backtest_cfg=backtest_cfg,
        bars_by_ticker=bars_by_ticker,
        tickers=tickers,
        start=start,
        end=end,
        horizons=horizons,
        feature_source=feature_source,
        rebuild_feature_cache=options.rebuild_feature_cache or options.force_refresh,
        data_mode=active_mode,
        fundamentals_provider=provider_set.fundamentals,
    )
    grouped_rows = group_feature_rows_by_ticker(feature_rows)
    if not grouped_rows:
        raise RuntimeError("No feature rows found for requested backtest scope")

    effective_tickers = sorted(grouped_rows)
    work_items = []
    for ticker in effective_tickers:
        bars = bars_by_ticker.get(ticker)
        if not bars:
            continue
        work_items.append(
            {
                "ticker": ticker,
                "feature_rows": grouped_rows[ticker],
                "bars": bars,
                "enabled_horizons": horizons,
                "entry_method": backtest_cfg["entry_execution"]["default_method"],
                "max_wait_days": int(backtest_cfg["entry_execution"]["max_wait_days"]),
                "config_data": bundle.data,
            }
        )
    if not work_items:
        raise RuntimeError("No tickers had usable price bars")

    workers = options.workers or min(os.cpu_count() or 4, len(work_items))
    workers = max(1, min(workers, len(work_items)))

    entry_decisions: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if workers == 1:
        worker_init(bundle.data)
        for work in work_items:
            result = process_ticker(work)
            entry_decisions.extend(result["entry_decisions"])
            trades.extend(result["trades"])
            errors.extend(result["errors"])
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=worker_init,
            initargs=(bundle.data,),
        ) as executor:
            futures = {executor.submit(process_ticker, work): work["ticker"] for work in work_items}
            for future in as_completed(futures):
                result = future.result()
                entry_decisions.extend(result["entry_decisions"])
                trades.extend(result["trades"])
                errors.extend(result["errors"])

    _write_outputs(
        paths,
        entry_decisions,
        trades,
        errors,
        no_report=options.no_report,
        diagnostics={
            "feature_source": feature_source,
            **feature_diagnostics,
        },
    )

    stats = StatsCollector()
    stats.record_cache_hit("backtest") if feature_diagnostics.get("feature_cache_status") == "hit" else stats.record_cache_miss("backtest")
    stats.write_summary(paths.run_dir)

    return {
        "run_id": paths.run_id,
        "tickers": len(work_items),
        "workers": workers,
        "feature_source": feature_source,
        **feature_diagnostics,
        "entry_decisions": len(entry_decisions),
        "trades": len(trades),
        "errors": len(errors),
        "run_dir": str(paths.run_dir),
    }


def _load_or_build_features(
    *,
    bundle: ConfigBundle,
    backtest_cfg: dict[str, Any],
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    tickers: list[str] | None,
    start: str,
    end: str,
    horizons: set[str],
    feature_source: str,
    rebuild_feature_cache: bool,
    data_mode: str = "legacy_yfinance",
    fundamentals_provider: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if feature_source == "parent_csv":
        features_path = _resolve_path(backtest_cfg["data_sources"]["feature_csv_path"])
        rows = load_feature_rows(
            features_path,
            tickers=tickers,
            start=start,
            end=end,
            horizons=horizons,
        )
        return rows, {
            "feature_cache_status": "not_used",
            "feature_rows": len(rows),
            "feature_path": str(features_path),
        }
    if feature_source != "native":
        raise RuntimeError(f"Unsupported feature source: {feature_source}")

    source_config = backtest_cfg.get("feature_generation", {})
    cache_path = _resolve_path(source_config.get("cache_path", "codex-backed/cache/features.pkl"))
    signal_frequency = source_config.get("signal_frequency", "weekly")
    requested_tickers = tickers or sorted(ticker for ticker in bars_by_ticker if ticker not in {"SPY", "QQQ"})
    provider_sig = getattr(fundamentals_provider, "signature", lambda: "null")()
    metadata = {
        "source": "native",
        "tickers": requested_tickers,
        "start": start,
        "end": end,
        "horizons": sorted(horizons),
        "signal_frequency": signal_frequency,
        "technical_setup_config": bundle.get("technical_setup"),
        "entry_config": bundle.get("entry"),
        "data_mode": data_mode,
        "fundamentals_provider_signature": provider_sig,
        "fundamentals_snapshot_schema_version": FUNDAMENTALS_SNAPSHOT_SCHEMA_VERSION,
    }

    cache_result = load_or_build_feature_rows(
        cache_path=cache_path,
        metadata=metadata,
        rebuild=rebuild_feature_cache,
        builder=lambda: build_historical_feature_rows(
            bars_by_ticker,
            tickers=requested_tickers,
            options=HistoricalFeatureOptions(
                start=start,
                end=end,
                horizons=horizons,
                signal_frequency=signal_frequency,
            ),
            fundamentals=fundamentals_provider,
        ),
    )
    return cache_result.rows, {
        "feature_cache_status": cache_result.status,
        "feature_cache_path": str(cache_result.path),
        "feature_cache_key": cache_result.cache_key,
        "feature_rows": len(cache_result.rows),
    }


def _default_backtest_tickers(bundle: ConfigBundle) -> list[str] | None:
    universe = bundle.data.get("backtest_universe")
    if not universe:
        return None
    tickers = universe.get("tickers")
    if not isinstance(tickers, list):
        return None
    return [str(ticker).upper() for ticker in tickers]


def _write_outputs(
    paths: RunPaths,
    entry_decisions: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    *,
    no_report: bool,
    diagnostics: dict[str, Any],
) -> None:
    write_csv(paths.entry_decisions_path, entry_decisions, columns=ENTRY_DECISIONS_COLUMNS)
    write_csv(paths.trades_path, trades, columns=TRADES_COLUMNS)
    if errors:
        write_csv(paths.run_dir / "errors.csv", errors)

    metrics = {
        "overall": build_record_metrics(trades),
        "entry_decisions": {
            "count": len(entry_decisions),
            "actionable_count": sum(1 for row in entry_decisions if row.get("is_actionable")),
        },
        "by_entry_label": build_sliced_metrics(trades, "entry_label"),
        "by_entry_strategy": build_sliced_metrics(trades, "entry_strategy"),
        "by_entry_setup": build_sliced_metrics(trades, "selected_setup"),
        "by_horizon": build_sliced_metrics(trades, "horizon"),
        "by_market_regime": build_sliced_metrics(trades, "market_regime"),
        "by_exit_reason": build_sliced_metrics(trades, "exit_reason"),
        "by_ticker": build_sliced_metrics(trades, "ticker"),
        "input_quality": diagnostics,
    }
    metrics["input_quality"].update(build_input_quality_metrics(entry_decisions, trades))
    write_json(paths.metrics_path, metrics)
    for key in ["by_entry_label", "by_entry_strategy", "by_entry_setup", "by_horizon", "by_market_regime", "by_exit_reason", "by_ticker"]:
        write_csv(paths.run_dir / f"{key}.csv", metrics[key])
    if not no_report:
        write_lifecycle_report(
            paths.report_path,
            metrics=metrics,
            trade_count=len(trades),
            decision_count=len(entry_decisions),
        )


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()
