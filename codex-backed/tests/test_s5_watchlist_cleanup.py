"""S5.1 — Legacy yfinance block removed from watchlist_config.json."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_CONFIG_SRC = Path(__file__).resolve().parents[1] / "configs"


def test_watchlist_config_validation_passes_without_yfinance_block(tmp_path):
    from codex_backed.config.loader import load_config_bundle, validate_config_bundle

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    wc = config_dir / "watchlist_config.json"
    cfg = json.loads(wc.read_text())
    cfg.pop("yfinance", None)
    wc.write_text(json.dumps(cfg))

    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)  # must not raise


def test_analyze_runs_without_yfinance_block_in_watchlist_config(tmp_path):
    from codex_backed.analyze import AnalyzeOptions, run_watchlist_analysis
    from codex_backed.config.loader import load_config_bundle
    from codex_backed.results import create_run_paths
    import pandas as pd

    config_dir = tmp_path / "configs"
    shutil.copytree(_CONFIG_SRC, config_dir)

    wc = config_dir / "watchlist_config.json"
    cfg = json.loads(wc.read_text())
    cfg.pop("yfinance", None)
    cfg["tickers"] = ["AAPL", "MSFT"]
    wc.write_text(json.dumps(cfg))

    bundle = load_config_bundle(config_dir)
    paths = create_run_paths(tmp_path / "results", run_id="s5_analyze")

    def _mock_yf_download(**kwargs):
        tickers = kwargs.get("tickers", [])
        if isinstance(tickers, str):
            tickers = [tickers]
        dates = pd.bdate_range("2022-01-01", periods=120)
        if len(tickers) == 1:
            return pd.DataFrame({
                "Open": [100.0] * 120, "High": [102.0] * 120,
                "Low": [98.0] * 120, "Close": [101.0] * 120,
                "Volume": [1_000_000] * 120,
            }, index=dates)
        import numpy as np
        cols = pd.MultiIndex.from_product(
            [tickers, ["Open", "High", "Low", "Close", "Volume"]]
        )
        return pd.DataFrame(np.ones((120, len(cols))) * 100.0, index=dates, columns=cols)

    with patch("yfinance.download", side_effect=_mock_yf_download):
        result = run_watchlist_analysis(
            bundle, paths, AnalyzeOptions(tickers=["AAPL", "MSFT"])
        )

    assert result is not None
