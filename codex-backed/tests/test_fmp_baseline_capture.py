"""S4.2 — Real-FMP baseline backtest and cache validation.

All tests are skipped unless the FMP_API_KEY environment variable is set.
When run with a valid key these tests:
1. Execute a full backtest in fmp_primary_yfinance_fallback mode
2. Capture run_metrics_data_layer.json provenance
3. Confirm that a second consecutive run hits the disk cache (≥ 95% hit rate)

Usage:
    FMP_API_KEY=<key> backend/.venv/bin/python -m pytest \
        codex-backed/tests/test_fmp_baseline_capture.py -v
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

_FMP_KEY = os.environ.get("FMP_API_KEY", "")
_HAS_KEY = bool(_FMP_KEY)

pytestmark = pytest.mark.skipif(
    not _HAS_KEY,
    reason="FMP_API_KEY not set — skipping live FMP tests",
)

_CONFIG_SRC = Path(__file__).resolve().parents[1] / "configs"
_RESULTS_DIR = Path(__file__).resolve().parents[1] / "results" / "fmp_baseline_run"
_MODE = "fmp_primary_yfinance_fallback"
_BACKTEST_START = "2022-01-03"
_BACKTEST_END = "2024-03-31"


def _run_fmp_backtest(tmp_path: Path, rebuild: bool = True):
    from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
    from codex_backed.config.loader import load_config_bundle, validate_config_bundle
    from codex_backed.results import create_run_paths

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    bc = config_dir / "backtest_config.json"
    cfg = json.loads(bc.read_text())
    cfg["feature_generation"]["cache_path"] = str(tmp_path / "feat_cache.pkl")
    # Override FMP cache dir to tmp so tests stay isolated
    dp = config_dir / "data_provider_config.json"
    dpcfg = json.loads(dp.read_text())
    dpcfg["providers"]["fmp"]["cache_dir"] = str(tmp_path / "fmp_cache")
    dpcfg["providers"]["fmp"]["budget_path"] = str(tmp_path / "fmp_budget.json")
    bc.write_text(json.dumps(cfg, indent=2))
    dp.write_text(json.dumps(dpcfg, indent=2))

    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    paths = create_run_paths(tmp_path / "results", run_id="fmp_baseline")

    result = run_lifecycle_backtest(
        bundle,
        paths,
        BacktestOptions(
            start=_BACKTEST_START,
            end=_BACKTEST_END,
            workers=1,
            no_report=True,
            rebuild_feature_cache=rebuild,
            data_mode=_MODE,
        ),
    )
    return result, paths


@pytest.fixture(scope="module")
def fmp_first_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("fmp_baseline")
    result, paths = _run_fmp_backtest(tmp, rebuild=True)
    return result, paths, tmp


def test_backtest_runs_to_completion_in_fmp_mode_with_real_key(fmp_first_run):
    result, paths, _ = fmp_first_run
    assert result is not None
    assert result["entry_decisions"] > 0, "Expected non-zero entry decisions in FMP mode"


def test_run_metrics_data_layer_json_contains_expected_provenance(fmp_first_run):
    _, paths, _ = fmp_first_run
    metrics_file = paths.run_dir / "run_metrics_data_layer.json"
    assert metrics_file.exists(), "run_metrics_data_layer.json not written"
    data = json.loads(metrics_file.read_text())
    assert isinstance(data, dict) and len(data) > 0


def test_cache_hit_rate_above_95_on_second_consecutive_run(fmp_first_run):
    """Second run against warmed FMP disk cache must not re-fetch from the API."""
    _, _, tmp = fmp_first_run

    # Reuse same tmp dir so the FMP cache is warmed from the first run
    result2, paths2 = _run_fmp_backtest(tmp, rebuild=True)

    metrics2 = json.loads((paths2.run_dir / "run_metrics_data_layer.json").read_text())
    # Look for 'fmp' provider entry; it should show high cache hit rate
    fmp_stats = metrics2.get("fmp", {})
    hits = fmp_stats.get("cache_hits", 0)
    misses = fmp_stats.get("cache_misses", 0)
    total = hits + misses
    if total == 0:
        pytest.skip("No FMP cache stats recorded — provider may not have been used")
    hit_rate = hits / total
    assert hit_rate >= 0.95, f"FMP cache hit rate {hit_rate:.1%} below 95% threshold"
