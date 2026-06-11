import csv
import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from codex_backed.analyze import AnalyzeOptions, run_watchlist_analysis
from codex_backed.config.loader import load_config_bundle, validate_config_bundle
from codex_backed.data.bars import normalize_price_frame
from codex_backed.results import create_run_paths


def test_watchlist_analysis_fetches_fresh_bars_and_writes_artifacts(tmp_path):
    source_config_dir = Path(__file__).resolve().parents[1] / "configs"
    config_dir = tmp_path / "configs"
    shutil.copytree(source_config_dir, config_dir)
    _patch_watchlist_config(config_dir / "watchlist_config.json", ["TST"], ["short_term"])

    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    paths = create_run_paths(tmp_path / "results", run_id="analyze_test")

    calls = []

    def fake_fetch(tickers, *, period, interval, auto_adjust):
        calls.append(
            {
                "tickers": tickers,
                "period": period,
                "interval": interval,
                "auto_adjust": auto_adjust,
            }
        )
        dates = pd.bdate_range(end="2026-06-08", periods=320)
        return {
            "TST": normalize_price_frame(_price_frame(dates, start=100.0, step=0.15, volume=1_000_000)),
            "SPY": normalize_price_frame(_price_frame(dates, start=400.0, step=0.05, volume=5_000_000)),
            "QQQ": normalize_price_frame(_price_frame(dates, start=350.0, step=0.04, volume=4_000_000)),
        }

    result = run_watchlist_analysis(
        bundle,
        paths,
        AnalyzeOptions(),
        fetch_bars=fake_fetch,
        today=date(2026, 6, 8),
    )

    assert calls == [
        {
            "tickers": ["TST", "SPY", "QQQ"],
            "period": "2y",
            "interval": "1d",
            "auto_adjust": False,
        }
    ]
    assert result["cache_used"] is False
    assert result["analysis_date"] == "2026-06-08"
    assert result["latest_signal_date"] == "2026-06-08"
    assert result["entry_decisions"] == 1
    assert paths.entry_decisions_path.exists()
    assert (paths.run_dir / "actionable_watchlist.csv").exists()
    assert paths.metrics_path.exists()

    rows = list(csv.DictReader(paths.entry_decisions_path.open()))
    metrics = json.loads(paths.metrics_path.read_text())
    assert rows[0]["ticker"] == "TST"
    assert rows[0]["horizon"] == "short_term"
    assert rows[0]["date"] == "2026-06-08"
    assert metrics["data_source"]["provider"] == "yfinance"
    assert metrics["data_source"]["cache_used"] is False


def test_watchlist_analysis_cli_tickers_override_default_watchlist(tmp_path):
    source_config_dir = Path(__file__).resolve().parents[1] / "configs"
    config_dir = tmp_path / "configs"
    shutil.copytree(source_config_dir, config_dir)
    _patch_watchlist_config(config_dir / "watchlist_config.json", ["AAA"], ["short_term", "medium_term"])

    bundle = load_config_bundle(config_dir)
    paths = create_run_paths(tmp_path / "results", run_id="override_test")
    seen_tickers = []

    def fake_fetch(tickers, *, period, interval, auto_adjust):
        seen_tickers.extend(tickers)
        dates = pd.bdate_range(end="2026-06-08", periods=320)
        frame = _price_frame(dates, start=100.0, step=0.1, volume=1_000_000)
        return {
            "BBB": normalize_price_frame(frame),
            "SPY": normalize_price_frame(_price_frame(dates, start=400.0, step=0.05, volume=5_000_000)),
            "QQQ": normalize_price_frame(_price_frame(dates, start=350.0, step=0.04, volume=4_000_000)),
        }

    result = run_watchlist_analysis(
        bundle,
        paths,
        AnalyzeOptions(tickers=["BBB"], horizons=["short_term"]),
        fetch_bars=fake_fetch,
        today=date(2026, 6, 8),
    )

    assert seen_tickers == ["BBB", "SPY", "QQQ"]
    assert result["tickers"] == 1
    assert result["horizons"] == ["short_term"]
    assert result["entry_decisions"] == 1


def _patch_watchlist_config(path: Path, tickers: list[str], horizons: list[str]) -> None:
    config = json.loads(path.read_text())
    config["tickers"] = tickers
    config["horizons"] = horizons
    path.write_text(json.dumps(config, indent=2) + "\n")


def _price_frame(dates, *, start: float, step: float, volume: int) -> pd.DataFrame:
    rows = []
    for idx, _dt in enumerate(dates):
        close = start + idx * step + (1.0 if idx % 17 == 0 else -0.6 if idx % 11 == 0 else 0.0)
        rows.append(
            {
                "Open": close - 0.2,
                "High": close + 1.2,
                "Low": close - 1.0,
                "Close": close,
                "Volume": volume + idx * 1000,
            }
        )
    return pd.DataFrame(rows, index=dates)
