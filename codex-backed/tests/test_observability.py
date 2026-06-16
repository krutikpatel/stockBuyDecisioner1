"""S2.6 — StatsCollector + observability tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from codex_backed.data.providers.observability import StatsCollector


def test_cache_hit_miss_accumulate():
    stats = StatsCollector()
    stats.record_cache_hit("fmp")
    stats.record_cache_hit("fmp")
    stats.record_cache_miss("fmp")
    summary = stats.build_summary()
    assert summary["fmp"]["cache_hits"] == 2
    assert summary["fmp"]["cache_misses"] == 1
    assert summary["fmp"]["cache_hit_rate"] == round(2 / 3, 4)


def test_latency_percentiles_computed_correctly():
    stats = StatsCollector()
    # 10 samples: 0.01s … 0.10s
    for i in range(1, 11):
        stats.record_latency("fmp", i * 0.01)
    summary = stats.build_summary()
    # p50 should be around 50ms (50th percentile of 10ms..100ms)
    assert summary["fmp"]["latency_p50_ms"] is not None
    assert summary["fmp"]["latency_p99_ms"] is not None
    # p99 should be ≥ p50
    assert summary["fmp"]["latency_p99_ms"] >= summary["fmp"]["latency_p50_ms"]


def test_api_error_counted_by_status():
    stats = StatsCollector()
    stats.record_api_error("fmp", 429)
    stats.record_api_error("fmp", 429)
    stats.record_api_error("fmp", 500)
    summary = stats.build_summary()
    assert summary["fmp"]["api_errors_by_status"][429] == 2
    assert summary["fmp"]["api_errors_by_status"][500] == 1


def test_summary_json_redacts_credentials():
    stats = StatsCollector()
    # Simulate a provider name that accidentally contains a key fragment
    stats.record_cache_hit("fmp?apikey=SECRET_VALUE")
    summary = stats.build_summary()
    raw = json.dumps(summary)
    assert "SECRET_VALUE" not in raw
    assert "***" in raw


def test_summary_written_to_run_dir(tmp_path):
    """End-to-end: run a backtest and verify run_metrics_data_layer.json exists."""
    from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
    from codex_backed.config.loader import load_config_bundle, validate_config_bundle
    from codex_backed.results import create_run_paths

    _CONFIG_SRC = Path(__file__).resolve().parents[1] / "configs"
    _FIXTURE_PKL = Path(__file__).resolve().parent / "fixtures" / "prices_fixture.pkl"

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    bc = config_dir / "backtest_config.json"
    import json as _json
    cfg = _json.loads(bc.read_text())
    cfg["data_sources"]["prices_cache_path"] = str(_FIXTURE_PKL)
    cfg["feature_generation"]["cache_path"] = str(tmp_path / "feat_cache.pkl")
    bc.write_text(_json.dumps(cfg, indent=2))

    uc = config_dir / "backtest_ticker_universe_config.json"
    ucfg = _json.loads(uc.read_text())
    ucfg["tickers"] = ["AAPL"]
    uc.write_text(_json.dumps(ucfg, indent=2))

    bundle = load_config_bundle(config_dir)
    paths = create_run_paths(tmp_path / "results", run_id="obs_test")

    run_lifecycle_backtest(
        bundle, paths,
        BacktestOptions(start="2022-01-03", end="2023-01-31", workers=1, no_report=True, rebuild_feature_cache=True),
    )

    summary_path = paths.run_dir / "run_metrics_data_layer.json"
    assert summary_path.exists(), "run_metrics_data_layer.json was not written"
    data = _json.loads(summary_path.read_text())
    assert "backtest" in data


def test_stats_reset_between_runs():
    stats1 = StatsCollector()
    stats1.record_cache_hit("fmp")
    stats1.record_api_error("fmp", 500)

    # New instance must start empty
    stats2 = StatsCollector()
    summary2 = stats2.build_summary()
    assert summary2 == {}
