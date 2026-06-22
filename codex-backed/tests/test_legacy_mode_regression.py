"""S1.8 — Phase 1 regression baseline: legacy_yfinance mode must stay bit-for-bit identical.

Runs the full pipeline against a committed deterministic fixture and compares
every output metric to a committed baseline. Any deviation is a regression.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
from codex_backed.config.loader import load_config_bundle, validate_config_bundle
from codex_backed.results import create_run_paths

_CONFIG_SRC = Path(__file__).resolve().parents[1] / "configs"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_BASELINE_PATH = _FIXTURES / "legacy_baseline_metrics.json"
_FIXTURE_PKL = _FIXTURES / "prices_fixture.pkl"

_BACKTEST_START = "2022-01-03"
_BACKTEST_END = "2024-03-31"
_TICKERS = ["AAPL", "MSFT"]

_TOLERANCE = 0.0001


def _run_backtest(tmp_path: Path) -> tuple[dict, dict]:
    """Return (run_result, full_metrics) from a backtest against the fixture."""
    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    bc = config_dir / "backtest_config.json"
    cfg = json.loads(bc.read_text())
    cfg["data_sources"]["prices_cache_path"] = str(_FIXTURE_PKL)
    cfg["data_sources"]["feature_csv_path"] = str(tmp_path / "feat.csv")
    cfg["feature_generation"]["cache_path"] = str(tmp_path / "feat_cache.pkl")
    bc.write_text(json.dumps(cfg, indent=2))

    uc = config_dir / "backtest_ticker_universe_config.json"
    ucfg = json.loads(uc.read_text())
    ucfg["tickers"] = _TICKERS
    uc.write_text(json.dumps(ucfg, indent=2))

    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    paths = create_run_paths(tmp_path / "results", run_id="regression")

    result = run_lifecycle_backtest(
        bundle, paths,
        BacktestOptions(
            start=_BACKTEST_START,
            end=_BACKTEST_END,
            workers=1,
            no_report=True,
            rebuild_feature_cache=True,
            data_mode="legacy_yfinance",
        ),
    )
    metrics = json.loads(paths.metrics_path.read_text())
    return result, metrics


@pytest.fixture(scope="module")
def baseline():
    return json.loads(_BASELINE_PATH.read_text())


@pytest.fixture(scope="module")
def backtest_result(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("regression")
    result, metrics = _run_backtest(tmp)
    return result, metrics


def test_entry_decisions_count_matches_baseline_exactly(baseline, backtest_result):
    result, _ = backtest_result
    assert result["entry_decisions"] == baseline["entry_decisions_count"]


def test_trades_count_matches_baseline_exactly(baseline, backtest_result):
    result, _ = backtest_result
    assert result["trades"] == baseline["trades_count"]


def test_feature_row_count_matches_baseline_exactly(baseline, backtest_result):
    result, _ = backtest_result
    assert result.get("feature_rows") == baseline["feature_rows_count"]


def test_win_rate_pct_matches_baseline_exactly(baseline, backtest_result):
    _, metrics = backtest_result
    actual = metrics["overall"]["win_rate_pct"]
    expected = baseline["overall"]["win_rate_pct"]
    assert actual == expected


def test_avg_return_pct_matches_baseline_within_0_0001(baseline, backtest_result):
    _, metrics = backtest_result
    actual = metrics["overall"]["avg_return_pct"]
    expected = baseline["overall"]["avg_return_pct"]
    if expected is None:
        assert actual is None
    else:
        assert actual is not None
        assert abs(actual - expected) < _TOLERANCE


def test_median_return_pct_matches_baseline_within_0_0001(baseline, backtest_result):
    _, metrics = backtest_result
    actual = metrics["overall"]["median_return_pct"]
    expected = baseline["overall"]["median_return_pct"]
    if expected is None:
        assert actual is None
    else:
        assert actual is not None
        assert abs(actual - expected) < _TOLERANCE


def test_profit_factor_matches_baseline_within_0_0001(baseline, backtest_result):
    _, metrics = backtest_result
    actual = metrics["overall"]["profit_factor"]
    expected = baseline["overall"]["profit_factor"]
    if expected is None:
        assert actual is None
    else:
        assert actual is not None
        assert abs(actual - expected) < _TOLERANCE


def test_per_horizon_slice_matches_baseline_within_tolerance(baseline, backtest_result):
    _, metrics = backtest_result
    actual_slices = {row["horizon"]: row for row in metrics["by_horizon"]}
    expected_slices = {row["horizon"]: row for row in baseline["by_horizon"]}
    assert set(actual_slices) == set(expected_slices)
    for horizon, expected_row in expected_slices.items():
        actual_row = actual_slices[horizon]
        for field in ("avg_return_pct", "median_return_pct", "win_rate_pct", "profit_factor"):
            exp_val = expected_row.get(field)
            act_val = actual_row.get(field)
            if exp_val is None:
                assert act_val is None, f"{horizon}.{field}: expected None, got {act_val}"
            else:
                assert act_val is not None, f"{horizon}.{field}: expected {exp_val}, got None"
                assert abs(act_val - exp_val) < _TOLERANCE, (
                    f"{horizon}.{field}: {act_val} not within {_TOLERANCE} of {exp_val}"
                )
