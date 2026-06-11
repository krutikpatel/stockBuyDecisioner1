import json
from pathlib import Path

import pytest

from codex_backed.config.loader import ConfigError, load_config_bundle, validate_config_bundle


def test_default_configs_validate():
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    bundle = load_config_bundle(config_dir)
    validate_config_bundle(bundle)


def test_invalid_operator_fails_validation(tmp_path):
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    target = tmp_path / "configs"
    target.mkdir()
    for path in config_dir.glob("*.json"):
        (target / path.name).write_text(path.read_text())

    entry_path = target / "entry_signal_config.json"
    text = entry_path.read_text()
    entry_path.write_text(text.replace('"operator": ">="', '"operator": "BAD_OP"', 1))

    bundle = load_config_bundle(target)
    with pytest.raises(ConfigError, match="BAD_OP"):
        validate_config_bundle(bundle)


def test_invalid_partial_sell_percentage_fails_validation(tmp_path):
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    target = tmp_path / "configs"
    target.mkdir()
    for path in config_dir.glob("*.json"):
        (target / path.name).write_text(path.read_text())

    exit_path = target / "exit_policy_config.json"
    exit_config = json.loads(exit_path.read_text())
    exit_config["default_exit_policy"]["short_term"]["partial_profit"]["sell_pct"] = 150
    exit_path.write_text(json.dumps(exit_config))

    bundle = load_config_bundle(target)
    with pytest.raises(ConfigError, match="sell_pct"):
        validate_config_bundle(bundle)


def test_invalid_backtest_universe_duplicate_fails_validation(tmp_path):
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    target = tmp_path / "configs"
    target.mkdir()
    for path in config_dir.glob("*.json"):
        (target / path.name).write_text(path.read_text())

    universe_path = target / "backtest_ticker_universe_config.json"
    universe_config = json.loads(universe_path.read_text())
    universe_config["tickers"] = ["AAPL", "AAPL"]
    universe_path.write_text(json.dumps(universe_config))

    bundle = load_config_bundle(target)
    with pytest.raises(ConfigError, match="duplicate"):
        validate_config_bundle(bundle)


def test_invalid_backtest_universe_reference_fails_validation(tmp_path):
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    target = tmp_path / "configs"
    target.mkdir()
    for path in config_dir.glob("*.json"):
        (target / path.name).write_text(path.read_text())

    backtest_path = target / "backtest_config.json"
    backtest_config = json.loads(backtest_path.read_text())
    backtest_config["ticker_universe"]["default_config"] = "wrong.json"
    backtest_path.write_text(json.dumps(backtest_config))

    bundle = load_config_bundle(target)
    with pytest.raises(ConfigError, match="ticker_universe.default_config"):
        validate_config_bundle(bundle)


def test_invalid_watchlist_duplicate_fails_validation(tmp_path):
    config_dir = Path(__file__).resolve().parents[1] / "configs"
    target = tmp_path / "configs"
    target.mkdir()
    for path in config_dir.glob("*.json"):
        (target / path.name).write_text(path.read_text())

    watchlist_path = target / "watchlist_config.json"
    watchlist_config = json.loads(watchlist_path.read_text())
    watchlist_config["tickers"] = ["AAPL", "AAPL"]
    watchlist_path.write_text(json.dumps(watchlist_config))

    bundle = load_config_bundle(target)
    with pytest.raises(ConfigError, match="watchlist tickers contains duplicate"):
        validate_config_bundle(bundle)
