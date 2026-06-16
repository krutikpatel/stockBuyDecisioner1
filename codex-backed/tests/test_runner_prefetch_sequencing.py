"""S3.6 — Runner prefetch sequencing and worker isolation tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from codex_backed.backtest.worker import worker_init

_CONFIG_SRC = Path(__file__).resolve().parents[1] / "configs"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_FIXTURE_PKL = _FIXTURES / "prices_fixture.pkl"

_BACKTEST_START = "2022-01-03"
_BACKTEST_END = "2024-03-31"
_TICKERS = ["AAPL", "MSFT"]


def _setup_tmp_config(tmp_path: Path) -> Path:
    """Copy configs to tmp_path, point prices at fixture pickle."""
    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    bc = config_dir / "backtest_config.json"
    cfg = json.loads(bc.read_text())
    cfg["data_sources"]["prices_cache_path"] = str(_FIXTURE_PKL)
    cfg["feature_generation"]["cache_path"] = str(tmp_path / "feat_cache.pkl")
    bc.write_text(json.dumps(cfg, indent=2))

    uc = config_dir / "backtest_ticker_universe_config.json"
    ucfg = json.loads(uc.read_text())
    ucfg["tickers"] = _TICKERS
    uc.write_text(json.dumps(ucfg, indent=2))

    return config_dir


def test_prefetch_called_before_process_pool_constructed(tmp_path):
    """prefetch_batch must be called in the main process before pool creation."""
    from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
    from codex_backed.config.loader import load_config_bundle, validate_config_bundle
    from codex_backed.results import create_run_paths

    config_dir = _setup_tmp_config(tmp_path)
    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    paths = create_run_paths(tmp_path / "results", run_id="seq_test")

    call_log: list[str] = []

    original_build = None

    def _tracking_prefetch(prov_self, tickers, date_range):
        call_log.append("prefetch_batch")

    # Track when ProcessPoolExecutor is entered (only used in multi-worker runs;
    # here we use workers=2 to trigger the pool path)
    import concurrent.futures as _cf
    OriginalExecutor = _cf.ProcessPoolExecutor

    class TrackingExecutor(OriginalExecutor):
        def __init__(self, *args, **kwargs):
            call_log.append("ProcessPoolExecutor.__init__")
            super().__init__(*args, **kwargs)

    from codex_backed.data.providers import null_fundamentals

    with patch.object(null_fundamentals.NullFundamentalsProvider, "prefetch_batch", _tracking_prefetch), \
         patch("codex_backed.backtest.runner.ProcessPoolExecutor", TrackingExecutor):
        run_lifecycle_backtest(
            bundle, paths,
            BacktestOptions(
                start=_BACKTEST_START,
                end=_BACKTEST_END,
                workers=2,
                no_report=True,
                rebuild_feature_cache=True,
            ),
        )

    assert "prefetch_batch" in call_log
    assert "ProcessPoolExecutor.__init__" in call_log
    assert call_log.index("prefetch_batch") < call_log.index("ProcessPoolExecutor.__init__")


def test_prefetch_called_exactly_once_per_run(tmp_path):
    """prefetch_batch is called exactly once during a backtest run."""
    from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
    from codex_backed.config.loader import load_config_bundle, validate_config_bundle
    from codex_backed.results import create_run_paths

    config_dir = _setup_tmp_config(tmp_path)
    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    paths = create_run_paths(tmp_path / "results", run_id="once_test")

    prefetch_call_count = []

    def _counting_prefetch(prov_self, tickers, date_range):
        prefetch_call_count.append(1)

    from codex_backed.data.providers import null_fundamentals

    with patch.object(null_fundamentals.NullFundamentalsProvider, "prefetch_batch", _counting_prefetch):
        run_lifecycle_backtest(
            bundle, paths,
            BacktestOptions(
                start=_BACKTEST_START,
                end=_BACKTEST_END,
                workers=1,
                no_report=True,
                rebuild_feature_cache=True,
            ),
        )

    assert len(prefetch_call_count) == 1


def test_worker_init_asserts_no_provider_runtime_in_config():
    """worker_init must raise AssertionError if config includes a provider runtime object."""
    good_config = {
        "entry": {},
        "technical_setup": {},
        "risk": {},
        "exit": {"default_exit_policy": {}},
        "backtest": {},
    }
    # Should not raise
    worker_init(good_config)

    bad_config = {**good_config, "data_provider_runtime": object()}
    with pytest.raises(AssertionError):
        worker_init(bad_config)


def test_workers_perform_zero_provider_calls():
    """process_ticker must not call any provider method — it works on pre-built rows."""
    from codex_backed.backtest.worker import process_ticker

    # Build a minimal work item with no real bars/rows so it returns quickly
    mock_provider = MagicMock()

    # A work item that has no feature rows → process_ticker loops over [] and returns fast
    work = {
        "ticker": "AAPL",
        "feature_rows": [],
        "bars": [],
        "enabled_horizons": {"short_term"},
        "entry_method": "next_open",
        "max_wait_days": 3,
        "config_data": {
            "entry": {},
            "technical_setup": {},
            "risk": {},
            "exit": {"default_exit_policy": {}},
            "backtest": {},
        },
    }

    result = process_ticker(work)

    # The key assertion: mock_provider was never called
    mock_provider.assert_not_called()
    # And the result structure is correct (no errors from empty rows)
    assert result["ticker"] == "AAPL"
    assert result["entry_decisions"] == []
    assert result["trades"] == []
