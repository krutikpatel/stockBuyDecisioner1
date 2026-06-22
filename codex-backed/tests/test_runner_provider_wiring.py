"""S1.6 — Registry wiring tests for runner.py and analyze.py."""

from __future__ import annotations

import json
import os
import pickle
import shutil
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from codex_backed.analyze import AnalyzeOptions, run_watchlist_analysis
from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
from codex_backed.backtest.worker import worker_init
from codex_backed.config.loader import load_config_bundle, validate_config_bundle
from codex_backed.data.providers.pickle_provider import PickleProvider
from codex_backed.data.providers.yfinance_provider import YFinancePriceProvider
from codex_backed.data.providers.null_fundamentals import NullFundamentalsProvider
from codex_backed.data.providers.registry import ProviderSet
from codex_backed.results import create_run_paths

_CONFIG_SRC = Path(__file__).resolve().parents[1] / "configs"


# ---------------------------------------------------------------------------
# Fixture helpers shared with backtest runner tests
# ---------------------------------------------------------------------------


def _write_price_cache(path: Path) -> None:
    dates = pd.bdate_range("2023-01-02", periods=200)

    def _frame(start, step, vol):
        rows = [
            {"Open": s - 0.2, "High": s + 1.5, "Low": s - 1.0, "Close": s, "Volume": vol}
            for i, s in enumerate(start + i * step for i in range(len(dates)))
        ]
        return pd.DataFrame(rows, index=dates)

    with path.open("wb") as fh:
        pickle.dump({"TST": _frame(100.0, 0.35, 1_200_000), "SPY": _frame(380.0, 0.08, 5_000_000)}, fh)


def _setup_backtest_bundle(tmp_path: Path):
    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    prices_path = tmp_path / "prices.pkl"
    _write_price_cache(prices_path)

    bc = config_dir / "backtest_config.json"
    cfg = json.loads(bc.read_text())
    cfg["data_sources"]["prices_cache_path"] = str(prices_path)
    cfg["data_sources"]["feature_csv_path"] = str(tmp_path / "features.csv")
    cfg["feature_generation"]["cache_path"] = str(tmp_path / "feature_cache.pkl")
    bc.write_text(json.dumps(cfg, indent=2) + "\n")

    uc = config_dir / "backtest_ticker_universe_config.json"
    ucfg = json.loads(uc.read_text())
    ucfg["tickers"] = ["TST"]
    uc.write_text(json.dumps(ucfg, indent=2) + "\n")

    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    paths = create_run_paths(tmp_path / "results", run_id="wiring_test")
    return bundle, paths, prices_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_runner_uses_pickle_provider_in_legacy_mode(tmp_path):
    """Runner routes through the registry; the mock provider's fetch_history_batch is called."""
    bundle, paths, prices_path = _setup_backtest_bundle(tmp_path)

    mock_pickle = MagicMock(spec=PickleProvider)
    mock_pickle.name = "pickle"
    mock_pickle.fetch_history_batch.return_value = {}  # empty → runtime error is expected

    mock_null = MagicMock(spec=NullFundamentalsProvider)
    mock_null.name = "null"

    mock_set = ProviderSet(
        price_backtest=mock_pickle,
        price_live=MagicMock(),
        fundamentals=mock_null,
    )

    with patch("codex_backed.backtest.runner.registry.build_providers", return_value=mock_set) as mock_build:
        with pytest.raises((RuntimeError, Exception)):
            run_lifecycle_backtest(
                bundle, paths,
                BacktestOptions(start="2023-01-02", end="2023-12-29", workers=1, no_report=True),
            )

    mock_build.assert_called_once()
    mock_pickle.fetch_history_batch.assert_called_once()


def test_runner_does_not_construct_providers_in_workers(tmp_path):
    """config_data passed to worker_init never contains a provider runtime key."""
    bundle, paths, _ = _setup_backtest_bundle(tmp_path)

    captured_config: list[dict] = []

    original_worker_init = worker_init

    def capturing_worker_init(config_data):
        captured_config.append(dict(config_data))
        return original_worker_init(config_data)

    with patch("codex_backed.backtest.runner.worker_init", side_effect=capturing_worker_init):
        try:
            run_lifecycle_backtest(
                bundle, paths,
                BacktestOptions(start="2023-01-02", end="2023-12-29", workers=1, no_report=True),
            )
        except Exception:
            pass

    # At least one call should have been captured
    assert len(captured_config) >= 1
    for config_data in captured_config:
        assert "data_provider_runtime" not in config_data


def test_analyze_uses_yfinance_provider_in_legacy_mode(tmp_path):
    """analyze routes through the registry; the mock provider's fetch_live_batch is called."""
    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)
    wc = config_dir / "watchlist_config.json"
    wcfg = json.loads(wc.read_text())
    wcfg["tickers"] = ["TST"]
    wcfg["horizons"] = ["short_term"]
    wc.write_text(json.dumps(wcfg, indent=2) + "\n")

    bundle = load_config_bundle(config_dir)
    paths = create_run_paths(tmp_path / "results", run_id="analyze_wiring")

    dates = pd.bdate_range(end="2024-01-05", periods=300)

    def _norm(start, step, vol):
        from codex_backed.data.bars import normalize_price_frame
        rows = [
            {"Open": s - 0.2, "High": s + 1.2, "Low": s - 1.0, "Close": s, "Volume": vol}
            for i, s in enumerate(start + i * step for i in range(len(dates)))
        ]
        return normalize_price_frame(pd.DataFrame(rows, index=dates))

    mock_yf = MagicMock(spec=YFinancePriceProvider)
    mock_yf.name = "yfinance"
    mock_yf.fetch_live_batch.return_value = {
        "TST": _norm(100.0, 0.15, 1_000_000),
        "SPY": _norm(400.0, 0.05, 5_000_000),
        "QQQ": _norm(350.0, 0.04, 4_000_000),
    }

    mock_set = ProviderSet(
        price_backtest=MagicMock(),
        price_live=mock_yf,
        fundamentals=MagicMock(),
    )

    with patch("codex_backed.analyze._provider_registry.build_providers", return_value=mock_set):
        result = run_watchlist_analysis(
            bundle, paths, AnalyzeOptions(),
            today=date(2024, 1, 5),
        )

    mock_yf.fetch_live_batch.assert_called_once()
    assert result["data_source"] == "yfinance"


def test_cli_data_mode_flag_recorded_in_run_manifest(tmp_path):
    """--data-mode is written to the manifest as effective_data_mode + mode_override_origin."""
    from codex_backed.cli import main

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    prices_path = tmp_path / "prices.pkl"
    _write_price_cache(prices_path)
    bc = config_dir / "backtest_config.json"
    cfg = json.loads(bc.read_text())
    cfg["data_sources"]["prices_cache_path"] = str(prices_path)
    cfg["data_sources"]["feature_csv_path"] = str(tmp_path / "feat.csv")
    cfg["feature_generation"]["cache_path"] = str(tmp_path / "feat_cache.pkl")
    bc.write_text(json.dumps(cfg, indent=2) + "\n")

    uc = config_dir / "backtest_ticker_universe_config.json"
    ucfg = json.loads(uc.read_text())
    ucfg["tickers"] = ["TST"]
    uc.write_text(json.dumps(ucfg, indent=2) + "\n")

    output_dir = tmp_path / "results"
    output_dir.mkdir()

    ret = main([
        "backtest",
        "--config-dir", str(config_dir),
        "--output-dir", str(output_dir),
        "--run-id", "mode_test",
        "--data-mode", "legacy_yfinance",
        "--workers", "1",
        "--start", "2023-01-02",
        "--end", "2023-06-30",
        "--no-report",
    ])

    # May succeed or fail with backtest errors; we just need the manifest written
    manifest_path = output_dir / "mode_test" / "manifest.json"
    assert manifest_path.exists(), "Manifest was not written"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["cli_args"]["effective_data_mode"] == "legacy_yfinance"
    assert manifest["cli_args"]["mode_override_origin"] == "cli"


def test_codex_no_overrides_blocks_cli_flag(tmp_path):
    """When CODEX_NO_OVERRIDES=1 is set, --data-mode is rejected."""
    from codex_backed.cli import main

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)
    prices_path = tmp_path / "prices.pkl"
    _write_price_cache(prices_path)
    bc = config_dir / "backtest_config.json"
    cfg = json.loads(bc.read_text())
    cfg["data_sources"]["prices_cache_path"] = str(prices_path)
    bc.write_text(json.dumps(cfg, indent=2) + "\n")

    output_dir = tmp_path / "results"
    output_dir.mkdir()

    env = {**os.environ, "CODEX_NO_OVERRIDES": "1"}
    with patch.dict(os.environ, {"CODEX_NO_OVERRIDES": "1"}):
        ret = main([
            "backtest",
            "--config-dir", str(config_dir),
            "--output-dir", str(output_dir),
            "--run-id", "blocked_test",
            "--data-mode", "legacy_yfinance",
            "--no-report",
        ])

    assert ret == 2
