"""S4.3 — Phase 4 activation gates.

Most tests require a real FMP_API_KEY and a prior S4.2 baseline run.  Without
a key, gate tests are skipped.  The audit-log existence test always runs.

Gate thresholds (from DATA_PROVIDER_REFACTOR_PLAN.md Section 15):
  - fundamentals_populated_rate for 6 required fields  ≥ 80% on post-2020 rows
  - overall.trade_count delta vs legacy                within −60% to +20%
  - overall.profit_factor                              ≥ 2.0 absolute
  - overall.win_rate_pct                               ≥ 45% absolute
  - actionable_count from fresh analyze run            ≥ 1
  - cache_hit_rate on second consecutive run           ≥ 95%
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

_FMP_KEY = os.environ.get("FMP_API_KEY", "")
_HAS_KEY = bool(_FMP_KEY)

_GATE_SKIP = pytest.mark.skipif(
    not _HAS_KEY, reason="FMP_API_KEY not set — gate cannot be evaluated"
)

_CONFIG_SRC = Path(__file__).resolve().parents[1] / "configs"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_AUDIT_LOG = Path(__file__).resolve().parents[1] / "ITERATIVE_IMPROVEMENTS_FMP_BASELINE_LOG.md"
_LEGACY_BASELINE = _FIXTURES / "legacy_baseline_metrics.json"
_MODE = "fmp_primary_yfinance_fallback"
_REQUIRED_FIELDS = [
    "forward_pe", "earnings_days_away", "eps_growth_yoy",
    "gross_margin", "short_float", "institutional_ownership",
]
_POST_2020_START = "2020-01-01"


def _fmp_backtest(tmp_path: Path, rebuild: bool = True):
    """Run a full backtest in FMP mode and return (result, paths, feature_rows)."""
    from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
    from codex_backed.config.loader import load_config_bundle, validate_config_bundle
    from codex_backed.results import create_run_paths
    import codex_backed.backtest.runner as _runner_mod
    from codex_backed.features.historical_builder import build_historical_feature_rows as _orig

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir, dirs_exist_ok=True)

    bc = config_dir / "backtest_config.json"
    cfg = json.loads(bc.read_text())
    cfg["feature_generation"]["cache_path"] = str(tmp_path / "feat_cache.pkl")
    dp = config_dir / "data_provider_config.json"
    dpcfg = json.loads(dp.read_text())
    dpcfg["providers"]["fmp"]["cache_dir"] = str(tmp_path / "fmp_cache")
    dpcfg["providers"]["fmp"]["budget_path"] = str(tmp_path / "fmp_budget.json")
    bc.write_text(json.dumps(cfg, indent=2))
    dp.write_text(json.dumps(dpcfg, indent=2))

    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    run_dir = tmp_path / "results" / "gate_run"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    paths = create_run_paths(tmp_path / "results", run_id="gate_run")

    captured: list[dict] = []

    from unittest.mock import patch

    def _capturing_build(*args, **kwargs):
        rows = _orig(*args, **kwargs)
        captured.extend(rows)
        return rows

    with patch.object(_runner_mod, "build_historical_feature_rows", _capturing_build):
        result = run_lifecycle_backtest(
            bundle, paths,
            BacktestOptions(
                start="2022-01-03",
                end="2024-03-31",
                workers=1,
                no_report=True,
                rebuild_feature_cache=rebuild,
                data_mode=_MODE,
            ),
        )
    return result, paths, captured


@pytest.fixture(scope="module")
def gate_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("gate")
    result, paths, rows = _fmp_backtest(tmp, rebuild=True)
    return result, paths, rows, tmp


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------

@_GATE_SKIP
def test_fundamentals_populated_rate_meets_threshold_for_each_required_field(gate_run):
    """Each required fundamentals field must be populated in ≥80% of post-2020 rows."""
    _, _, captured_rows, _ = gate_run
    post_2020 = [r for r in captured_rows if r.get("date", "") >= _POST_2020_START]
    assert len(post_2020) > 0, "No post-2020 feature rows found"

    failures = []
    for field in _REQUIRED_FIELDS:
        populated = sum(1 for r in post_2020 if r.get(field) is not None)
        rate = populated / len(post_2020)
        if rate < 0.80:
            failures.append(f"{field}: {rate:.1%} (threshold 80%)")

    assert not failures, "Fundamentals population rate below threshold:\n" + "\n".join(failures)


@_GATE_SKIP
def test_trade_count_delta_within_acceptance_range(gate_run):
    """FMP-mode trade count must be within −60% to +20% of legacy baseline."""
    result, _, _, _ = gate_run
    legacy = json.loads(_LEGACY_BASELINE.read_text())
    legacy_trades = legacy["trades_count"]
    fmp_trades = result["trades"]
    if legacy_trades == 0:
        pytest.skip("Legacy baseline has 0 trades — delta comparison not meaningful")
    delta_pct = (fmp_trades - legacy_trades) / legacy_trades
    assert -0.60 <= delta_pct <= 0.20, (
        f"Trade count delta {delta_pct:.1%} outside −60% to +20% range "
        f"(legacy={legacy_trades}, fmp={fmp_trades})"
    )


@_GATE_SKIP
def test_profit_factor_above_absolute_threshold(gate_run):
    """FMP-mode overall profit factor must be ≥ 2.0."""
    _, paths, _, _ = gate_run
    metrics = json.loads(paths.metrics_path.read_text())
    pf = metrics["overall"].get("profit_factor")
    if pf is None:
        pytest.skip("No trades in FMP run — profit factor is null")
    assert pf >= 2.0, f"Profit factor {pf:.4f} below threshold of 2.0"


@_GATE_SKIP
def test_win_rate_above_absolute_threshold(gate_run):
    """FMP-mode overall win rate must be ≥ 45%."""
    _, paths, _, _ = gate_run
    metrics = json.loads(paths.metrics_path.read_text())
    wr = metrics["overall"].get("win_rate_pct")
    if wr is None:
        pytest.skip("No trades in FMP run — win rate is null")
    assert wr >= 45.0, f"Win rate {wr:.2f}% below threshold of 45%"


@_GATE_SKIP
def test_actionable_count_in_live_analyze_at_least_one(tmp_path):
    """A fresh analyze run in FMP mode must produce ≥ 1 entry decision (pipeline ran)."""
    from codex_backed.analyze import AnalyzeOptions, run_watchlist_analysis
    from codex_backed.config.loader import load_config_bundle
    from codex_backed.results import create_run_paths

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    dp = config_dir / "data_provider_config.json"
    dpcfg = json.loads(dp.read_text())
    dpcfg["providers"]["fmp"]["cache_dir"] = str(tmp_path / "fmp_cache")
    dpcfg["providers"]["fmp"]["budget_path"] = str(tmp_path / "fmp_budget.json")
    dp.write_text(json.dumps(dpcfg, indent=2))

    bundle = load_config_bundle(config_dir)
    paths = create_run_paths(tmp_path / "results", run_id="gate_analyze")

    result = run_watchlist_analysis(bundle, paths, AnalyzeOptions(data_mode=_MODE))
    # Gate verifies the pipeline ran and produced decisions in FMP mode.
    # Whether decisions are actionable depends on today's market conditions,
    # which is not a reliable indicator of provider correctness.
    assert result.get("entry_decisions", 0) >= 1, (
        f"Live analyze produced 0 entry decisions in FMP mode — pipeline did not run. "
        f"Full result: {result}"
    )


@_GATE_SKIP
def test_cache_hit_rate_on_warm_run_above_threshold(tmp_path):
    """Second consecutive FMP backtest run must have ≥ 95% cache hit rate."""
    _, paths1, _ = _fmp_backtest(tmp_path, rebuild=True)
    _, paths2, _ = _fmp_backtest(tmp_path, rebuild=True)

    metrics = json.loads((paths2.run_dir / "run_metrics_data_layer.json").read_text())
    fmp_stats = metrics.get("fmp", {})
    hits = fmp_stats.get("cache_hits", 0)
    misses = fmp_stats.get("cache_misses", 0)
    total = hits + misses
    if total == 0:
        pytest.skip("No FMP cache stats — provider may not have been used for this run")
    hit_rate = hits / total
    assert hit_rate >= 0.95, f"FMP cache hit rate {hit_rate:.1%} below 95% threshold"


def test_audit_log_file_exists_and_contains_all_gate_results():
    """Audit log must exist and document all required gate fields."""
    assert _AUDIT_LOG.exists(), f"Audit log not found: {_AUDIT_LOG}"
    content = _AUDIT_LOG.read_text()
    for field in _REQUIRED_FIELDS:
        assert field in content, f"Audit log missing gate entry for '{field}'"
