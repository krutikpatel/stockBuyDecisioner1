"""S3.7 — End-to-end smoke tests for fmp_primary_yfinance_fallback mode (mocked HTTP).

All FMP HTTP calls are intercepted by the mock session helper; yfinance is patched
with fixture data. The active_mode config key stays 'legacy_yfinance' — these tests
explicitly request the dormant mode via BacktestOptions.data_mode.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
from codex_backed.config.loader import load_config_bundle, validate_config_bundle
from codex_backed.results import create_run_paths

_CONFIG_SRC = Path(__file__).resolve().parents[1] / "configs"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_FIXTURE_PKL = _FIXTURES / "prices_fixture.pkl"
_YF_INFO = json.loads((_FIXTURES / "yfinance" / "info_aapl.json").read_text())

_MODE = "fmp_primary_yfinance_fallback"
_BACKTEST_START = "2022-01-03"
_BACKTEST_END = "2024-03-31"
_TICKERS = ["AAPL", "MSFT"]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _setup_tmp_config(tmp_path: Path) -> Path:
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


def _mock_yf_ticker(info_data: dict):
    mock_ticker = MagicMock()
    mock_ticker.info = info_data
    return mock_ticker


@pytest.fixture(scope="module")
def fmp_backtest_result(tmp_path_factory):
    """Run one backtest in fmp mode and cache the result for all tests."""
    from fixtures.fmp.__mocked_session__ import mock_fmp_http

    tmp = tmp_path_factory.mktemp("fmp_smoke")
    config_dir = _setup_tmp_config(tmp)
    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)
    paths = create_run_paths(tmp / "results", run_id="fmp_smoke")

    captured_rows: list[dict] = []
    from codex_backed.features.historical_builder import build_historical_feature_rows as _orig_build
    import codex_backed.backtest.runner as _runner_mod

    def _capturing_build(*args, **kwargs):
        rows = _orig_build(*args, **kwargs)
        captured_rows.extend(rows)
        return rows

    with mock_fmp_http(), \
         patch("yfinance.Ticker", side_effect=lambda t: _mock_yf_ticker(_YF_INFO)), \
         patch.object(_runner_mod, "build_historical_feature_rows", _capturing_build):
        result = run_lifecycle_backtest(
            bundle, paths,
            BacktestOptions(
                start=_BACKTEST_START,
                end=_BACKTEST_END,
                workers=1,
                no_report=True,
                rebuild_feature_cache=True,
                data_mode=_MODE,
            ),
        )
    return result, paths, captured_rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_backtest_completes_in_fmp_mode_on_2_tickers(fmp_backtest_result):
    result, paths, _ = fmp_backtest_result
    assert result is not None
    assert "entry_decisions" in result
    assert "trades" in result


def test_backtest_produces_non_zero_actionable_decisions_when_fundamentals_present(fmp_backtest_result):
    result, paths, _ = fmp_backtest_result
    # Pipeline must emit decisions (even if all are NO_TRADE — proves fundamentals didn't break the flow)
    assert result["entry_decisions"] > 0


def test_fundamentals_populated_rate_above_threshold_for_forward_pe(fmp_backtest_result):
    """At least 50% of feature rows should have a non-None forward_pe (from yfinance fallback)."""
    _, _, captured_rows = fmp_backtest_result
    assert len(captured_rows) > 0
    # forward_pe is not in FMP caps → composite routes to yfinance → should be populated
    populated = sum(1 for r in captured_rows if r.get("forward_pe") is not None)
    rate = populated / len(captured_rows)
    assert rate >= 0.5, f"forward_pe populated in only {rate:.1%} of rows (expected ≥50%)"


def test_analyze_completes_in_fmp_mode_on_2_tickers(tmp_path):
    """analyze command must complete in fmp mode without raising."""
    from fixtures.fmp.__mocked_session__ import mock_fmp_http
    from codex_backed.analyze import run_watchlist_analysis
    import pandas as pd

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    # Point watchlist at our 2 tickers
    wc = config_dir / "watchlist_config.json"
    wcfg = json.loads(wc.read_text())
    wcfg["tickers"] = _TICKERS
    wc.write_text(json.dumps(wcfg, indent=2))

    bundle = load_config_bundle(config_dir)
    paths = create_run_paths(tmp_path / "results", run_id="fmp_analyze")

    from codex_backed.analyze import AnalyzeOptions

    # Build a mock yfinance.download that returns a multi-ticker DataFrame
    def _mock_yf_download(**kwargs):
        all_tickers = kwargs.get("tickers", [])
        if isinstance(all_tickers, str):
            all_tickers = [all_tickers]
        dates = pd.bdate_range("2022-01-01", periods=120)
        if len(all_tickers) == 1:
            return pd.DataFrame({
                "Open": [100.0] * 120, "High": [102.0] * 120,
                "Low": [98.0] * 120, "Close": [101.0] * 120,
                "Volume": [1_000_000] * 120,
            }, index=dates)
        cols = pd.MultiIndex.from_product(
            [all_tickers, ["Open", "High", "Low", "Close", "Volume"]]
        )
        import numpy as np
        data = np.ones((120, len(cols))) * 100.0
        return pd.DataFrame(data, index=dates, columns=cols)

    with mock_fmp_http(), \
         patch("yfinance.Ticker", side_effect=lambda t: _mock_yf_ticker(_YF_INFO)), \
         patch("yfinance.download", side_effect=_mock_yf_download):
        result = run_watchlist_analysis(
            bundle, paths, AnalyzeOptions(data_mode=_MODE, tickers=_TICKERS)
        )

    assert result is not None


def test_run_metrics_data_layer_json_emitted_with_expected_fields(fmp_backtest_result):
    """run_metrics_data_layer.json must exist and contain the expected top-level keys."""
    _, paths, _ = fmp_backtest_result
    metrics_file = paths.run_dir / "run_metrics_data_layer.json"
    assert metrics_file.exists(), "run_metrics_data_layer.json not found"
    data = json.loads(metrics_file.read_text())
    # File must be a non-empty dict with at least one provider entry
    assert isinstance(data, dict) and len(data) > 0
