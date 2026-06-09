import csv
import json
import pickle
import shutil
from pathlib import Path

import pandas as pd

from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
from codex_backed.config.loader import load_config_bundle, validate_config_bundle
from codex_backed.results import create_run_paths


def test_lifecycle_backtest_runner_writes_artifacts(tmp_path):
    source_config_dir = Path(__file__).resolve().parents[1] / "configs"
    config_dir = tmp_path / "configs"
    shutil.copytree(source_config_dir, config_dir)

    prices_path = tmp_path / "prices.pkl"
    _write_price_cache(prices_path)
    _patch_backtest_config(config_dir / "backtest_config.json", prices_path, tmp_path / "features.csv", tmp_path / "feature_cache.pkl")
    _patch_backtest_universe_config(config_dir / "backtest_ticker_universe_config.json", ["TST"])

    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    paths = create_run_paths(tmp_path / "results", run_id="runner_test")

    result = run_lifecycle_backtest(
        bundle,
        paths,
        BacktestOptions(start="2024-01-01", end="2024-02-28", workers=1, no_report=True),
    )

    assert result["feature_source"] == "native"
    assert result["feature_cache_status"] == "rebuilt"
    assert result["entry_decisions"] > 0
    assert paths.entry_decisions_path.exists()
    assert paths.trades_path.exists()
    assert paths.metrics_path.exists()

    trades = list(csv.DictReader(paths.trades_path.open()))
    metrics = json.loads(paths.metrics_path.read_text())
    assert metrics["input_quality"]["feature_source"] == "native"
    assert metrics["input_quality"]["decision_setup_distribution"]
    if trades:
        assert trades[0]["ticker"] == "TST"
        assert trades[0]["entry_label"] in {"BUY_STARTER", "BUY_FULL", "BUY_AGGRESSIVE"}
        assert float(trades[0]["realized_return_pct"]) != 0


def _write_price_cache(path: Path) -> None:
    dates = pd.bdate_range("2023-01-02", periods=310)
    df = _price_frame(dates, start=100.0, step=0.35, volume=1_200_000)
    spy_df = _price_frame(dates, start=380.0, step=0.08, volume=5_000_000)
    with path.open("wb") as fh:
        pickle.dump({"TST": df, "SPY": spy_df}, fh)


def _price_frame(dates, *, start: float, step: float, volume: int) -> pd.DataFrame:
    rows = []
    for idx, _dt in enumerate(dates):
        close = start + idx * step + (1.5 if idx % 13 == 0 else -0.8 if idx % 8 == 0 else 0.0)
        rows.append(
            {
                "Open": close - 0.2,
                "High": close + 1.5,
                "Low": close - 1.0,
                "Close": close,
                "Volume": volume + idx * 1000,
            }
        )
    return pd.DataFrame(rows, index=dates)


def _patch_backtest_config(path: Path, prices_path: Path, features_path: Path, cache_path: Path) -> None:
    config = json.loads(path.read_text())
    config["data_sources"]["prices_cache_path"] = str(prices_path)
    config["data_sources"]["feature_csv_path"] = str(features_path)
    config["feature_generation"]["cache_path"] = str(cache_path)
    path.write_text(json.dumps(config, indent=2) + "\n")


def _patch_backtest_universe_config(path: Path, tickers: list[str]) -> None:
    config = json.loads(path.read_text())
    config["tickers"] = tickers
    path.write_text(json.dumps(config, indent=2) + "\n")
