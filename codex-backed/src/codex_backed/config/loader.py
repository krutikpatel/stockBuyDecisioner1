from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_CONFIG_FILES = {
    "entry": "entry_signal_config.json",
    "exit": "exit_policy_config.json",
    "risk": "risk_config.json",
    "backtest": "backtest_config.json",
    "backtest_universe": "backtest_ticker_universe_config.json",
    "optimization": "optimization_config.json",
    "technical_setup": "technical_setup_config.json",
    "market_universe": "market_and_universe_config.json",
    "stock_classification": "stock_classification_config.json",
    "watchlist": "watchlist_config.json",
}

VALID_OPERATORS = {
    ">=",
    "<=",
    ">",
    "<",
    "==",
    "!=",
    "in",
    "not_in",
    "between",
    "exists",
    "missing",
    "contains",
}

VALID_HORIZONS = {"short_term", "medium_term"}
VALID_ENTRY_LABELS = {"NO_TRADE", "WATCHLIST", "BUY_STARTER", "BUY_FULL", "BUY_AGGRESSIVE"}


class ConfigError(ValueError):
    """Raised when config loading or validation fails."""


@dataclass(frozen=True)
class ConfigBundle:
    config_dir: Path
    files: dict[str, Path]
    data: dict[str, dict[str, Any]]

    def get(self, name: str) -> dict[str, Any]:
        return self.data[name]


def load_config_bundle(config_dir: Path) -> ConfigBundle:
    if not config_dir.exists():
        raise ConfigError(f"Config directory does not exist: {config_dir}")
    if not config_dir.is_dir():
        raise ConfigError(f"Config path is not a directory: {config_dir}")

    loaded: dict[str, dict[str, Any]] = {}
    files: dict[str, Path] = {}
    for key, filename in REQUIRED_CONFIG_FILES.items():
        path = config_dir / filename
        if not path.exists():
            raise ConfigError(f"Missing required config file: {path}")
        try:
            value = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ConfigError(f"Config file must contain a JSON object: {path}")
        loaded[key] = value
        files[key] = path

    return ConfigBundle(config_dir=config_dir, files=files, data=loaded)


def validate_config_bundle(bundle: ConfigBundle) -> None:
    _validate_entry_config(bundle.get("entry"))
    _validate_exit_config(bundle.get("exit"))
    _validate_risk_config(bundle.get("risk"))
    _validate_backtest_config(bundle.get("backtest"))
    _validate_backtest_universe_config(bundle.get("backtest_universe"))
    _validate_watchlist_config(bundle.get("watchlist"))
    _validate_optimization_config(bundle.get("optimization"))
    _validate_technical_setup_config(bundle.get("technical_setup"))


def _validate_entry_config(config: dict[str, Any]) -> None:
    labels = config.get("entry_labels")
    if not isinstance(labels, list) or set(labels) != VALID_ENTRY_LABELS:
        raise ConfigError(f"entry_labels must equal {sorted(VALID_ENTRY_LABELS)}")

    router = _require_dict(config, "entry_router")
    if router.get("method") != "priority_first_match":
        raise ConfigError("entry_router.method must be 'priority_first_match'")

    rules = _require_list(router, "rules")
    engines = _require_dict(config, "entry_engines")
    fallback = router.get("fallback_entry_engine")
    if fallback not in engines:
        raise ConfigError(f"fallback_entry_engine '{fallback}' is not defined")

    for idx, rule in enumerate(rules):
        _require_keys(rule, ["id", "priority", "logic", "entry_engine"], f"entry_router.rules[{idx}]")
        if rule["entry_engine"] not in engines:
            raise ConfigError(f"Route '{rule['id']}' references unknown entry engine '{rule['entry_engine']}'")
        _validate_logic(rule["logic"], f"entry_router.rules[{idx}].logic")

    for name, engine in engines.items():
        if not isinstance(engine, dict):
            raise ConfigError(f"entry_engines.{name} must be an object")
        for rule_group in ("score_rules", "penalty_rules"):
            for idx, rule in enumerate(engine.get(rule_group, [])):
                _require_keys(rule, ["id", "logic"], f"entry_engines.{name}.{rule_group}[{idx}]")
                _validate_logic(rule["logic"], f"entry_engines.{name}.{rule_group}[{idx}].logic")
                if rule_group == "score_rules":
                    _validate_number(rule.get("points"), f"entry_engines.{name}.{rule_group}[{idx}].points")
        for idx, threshold in enumerate(engine.get("decision_thresholds", [])):
            label = threshold.get("label")
            if label not in VALID_ENTRY_LABELS:
                raise ConfigError(f"entry_engines.{name}.decision_thresholds[{idx}] has invalid label '{label}'")
            _require_keys(threshold, ["logic"], f"entry_engines.{name}.decision_thresholds[{idx}]")
            _validate_logic(threshold["logic"], f"entry_engines.{name}.decision_thresholds[{idx}].logic")
        fallback_label = engine.get("fallback_label")
        if fallback_label not in VALID_ENTRY_LABELS:
            raise ConfigError(f"entry_engines.{name}.fallback_label has invalid label '{fallback_label}'")


def _validate_exit_config(config: dict[str, Any]) -> None:
    policy = _require_dict(config, "default_exit_policy")
    if set(policy) != VALID_HORIZONS:
        raise ConfigError(f"default_exit_policy horizons must be {sorted(VALID_HORIZONS)}")

    for horizon, horizon_policy in policy.items():
        path = f"default_exit_policy.{horizon}"
        max_days = horizon_policy.get("max_simulation_days")
        if not isinstance(max_days, int) or max_days <= 0:
            raise ConfigError(f"{path}.max_simulation_days must be a positive integer")

        initial_stop = _require_dict(horizon_policy, "initial_stop")
        if initial_stop.get("method") not in {"atr", "support", "atr_or_support"}:
            raise ConfigError(f"{path}.initial_stop.method is invalid")
        _validate_positive_number(initial_stop.get("atr_multiplier"), f"{path}.initial_stop.atr_multiplier")
        _validate_non_negative_number(initial_stop.get("support_buffer_pct"), f"{path}.initial_stop.support_buffer_pct")

        partial = _require_dict(horizon_policy, "partial_profit")
        _validate_bool(partial.get("enabled"), f"{path}.partial_profit.enabled")
        _validate_positive_number(partial.get("target_r_multiple"), f"{path}.partial_profit.target_r_multiple")
        _validate_percent(partial.get("sell_pct"), f"{path}.partial_profit.sell_pct")
        _validate_bool(partial.get("move_stop_to_breakeven"), f"{path}.partial_profit.move_stop_to_breakeven")
        if "breakeven_after_r_multiple" in partial:
            _validate_positive_number(partial.get("breakeven_after_r_multiple"), f"{path}.partial_profit.breakeven_after_r_multiple")

        trailing = _require_dict(horizon_policy, "trailing_stop")
        _validate_bool(trailing.get("enabled"), f"{path}.trailing_stop.enabled")
        if trailing.get("method") not in {"atr", "percent"}:
            raise ConfigError(f"{path}.trailing_stop.method is invalid")
        _validate_positive_number(trailing.get("atr_multiplier"), f"{path}.trailing_stop.atr_multiplier")
        _validate_bool(trailing.get("activate_after_target_1"), f"{path}.trailing_stop.activate_after_target_1")

        time_stop = _require_dict(horizon_policy, "time_stop")
        _validate_bool(time_stop.get("enabled"), f"{path}.time_stop.enabled")
        days = time_stop.get("days_without_progress")
        if not isinstance(days, int) or days <= 0:
            raise ConfigError(f"{path}.time_stop.days_without_progress must be a positive integer")
        _validate_number(time_stop.get("min_open_return_pct"), f"{path}.time_stop.min_open_return_pct")


def _validate_risk_config(config: dict[str, Any]) -> None:
    sizing = _require_dict(config, "position_sizing")
    missing = VALID_ENTRY_LABELS.difference(sizing)
    if missing:
        raise ConfigError(f"position_sizing missing labels: {sorted(missing)}")
    for label, size in sizing.items():
        if label not in VALID_ENTRY_LABELS:
            raise ConfigError(f"position_sizing has unknown label '{label}'")
        _validate_non_negative_number(size, f"position_sizing.{label}")

    caps = _require_dict(config, "risk_caps")
    for key in ("max_risk_per_trade_pct", "max_position_size_pct", "high_atr_threshold_pct", "high_atr_position_cap_pct"):
        _validate_positive_number(caps.get(key), f"risk_caps.{key}")

    earnings = _require_dict(config, "earnings_risk")
    for key in ("avoid_new_entries_within_days", "starter_only_within_days"):
        value = earnings.get(key)
        if not isinstance(value, int) or value < 0:
            raise ConfigError(f"earnings_risk.{key} must be a non-negative integer")


def _validate_backtest_config(config: dict[str, Any]) -> None:
    ticker_universe = config.get("ticker_universe", {})
    if not isinstance(ticker_universe, dict):
        raise ConfigError("ticker_universe must be an object")
    if "default_config" in ticker_universe and ticker_universe["default_config"] != REQUIRED_CONFIG_FILES["backtest_universe"]:
        raise ConfigError(f"ticker_universe.default_config must be '{REQUIRED_CONFIG_FILES['backtest_universe']}'")
    if "cli_override" in ticker_universe and ticker_universe["cli_override"] != "--tickers":
        raise ConfigError("ticker_universe.cli_override must be '--tickers'")

    horizons = _require_dict(config, "horizons")
    if set(horizons) != VALID_HORIZONS:
        raise ConfigError(f"backtest horizons must be {sorted(VALID_HORIZONS)}")
    for horizon, value in horizons.items():
        if not isinstance(value.get("enabled"), bool):
            raise ConfigError(f"horizons.{horizon}.enabled must be boolean")
        max_days = value.get("max_simulation_days")
        if not isinstance(max_days, int) or max_days <= 0:
            raise ConfigError(f"horizons.{horizon}.max_simulation_days must be a positive integer")

    entry_execution = _require_dict(config, "entry_execution")
    if entry_execution.get("default_method") not in {
        "NEXT_OPEN",
        "NEXT_CLOSE",
        "PULLBACK_TO_SMA20",
        "PULLBACK_TO_SMA50",
        "BREAKOUT_CONFIRMATION",
    }:
        raise ConfigError("entry_execution.default_method is invalid")
    wait_days = entry_execution.get("max_wait_days")
    if not isinstance(wait_days, int) or wait_days < 0:
        raise ConfigError("entry_execution.max_wait_days must be a non-negative integer")

    data_sources = _require_dict(config, "data_sources")
    for key in ("prices_cache_path", "feature_csv_path"):
        value = data_sources.get(key)
        if not isinstance(value, str) or not value:
            raise ConfigError(f"data_sources.{key} must be a non-empty string")
    if "feature_source" in data_sources and data_sources["feature_source"] not in {"native", "parent_csv"}:
        raise ConfigError("data_sources.feature_source must be 'native' or 'parent_csv'")

    feature_generation = config.get("feature_generation", {})
    if not isinstance(feature_generation, dict):
        raise ConfigError("feature_generation must be an object")
    if "source" in feature_generation and feature_generation["source"] not in {"native", "parent_csv"}:
        raise ConfigError("feature_generation.source must be 'native' or 'parent_csv'")
    if "cache_path" in feature_generation:
        value = feature_generation["cache_path"]
        if not isinstance(value, str) or not value:
            raise ConfigError("feature_generation.cache_path must be a non-empty string")
    if "signal_frequency" in feature_generation and feature_generation["signal_frequency"] not in {"weekly", "daily"}:
        raise ConfigError("feature_generation.signal_frequency must be 'weekly' or 'daily'")


def _validate_backtest_universe_config(config: dict[str, Any]) -> None:
    tickers = config.get("tickers")
    if not isinstance(tickers, list) or not tickers:
        raise ConfigError("backtest ticker universe must define a non-empty tickers list")

    seen: set[str] = set()
    duplicates: list[str] = []
    for idx, ticker in enumerate(tickers):
        if not isinstance(ticker, str) or not ticker.strip():
            raise ConfigError(f"backtest ticker universe tickers[{idx}] must be a non-empty string")
        normalized = ticker.strip().upper()
        if normalized != ticker:
            raise ConfigError(f"backtest ticker universe tickers[{idx}] must be uppercase without surrounding whitespace")
        if normalized in seen:
            duplicates.append(normalized)
        seen.add(normalized)
    if duplicates:
        raise ConfigError(f"backtest ticker universe contains duplicate tickers: {sorted(set(duplicates))}")


def _validate_watchlist_config(config: dict[str, Any]) -> None:
    tickers = config.get("tickers")
    if not isinstance(tickers, list) or not tickers:
        raise ConfigError("watchlist config must define a non-empty tickers list")
    _validate_ticker_list(tickers, "watchlist tickers")

    horizons = config.get("horizons", ["short_term"])
    if not isinstance(horizons, list) or not horizons:
        raise ConfigError("watchlist horizons must be a non-empty list")
    invalid_horizons = sorted(set(horizons).difference(VALID_HORIZONS))
    if invalid_horizons:
        raise ConfigError(f"watchlist horizons are invalid: {invalid_horizons}")

    benchmarks = config.get("benchmark_tickers", ["SPY"])
    if not isinstance(benchmarks, list) or not benchmarks:
        raise ConfigError("watchlist benchmark_tickers must be a non-empty list")
    _validate_ticker_list(benchmarks, "watchlist benchmark_tickers")

    yfinance_config = _require_dict(config, "yfinance")
    for key in ("period", "interval"):
        value = yfinance_config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"watchlist yfinance.{key} must be a non-empty string")
    auto_adjust = yfinance_config.get("auto_adjust", False)
    if not isinstance(auto_adjust, bool):
        raise ConfigError("watchlist yfinance.auto_adjust must be boolean")


def _validate_ticker_list(tickers: list[Any], path: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for idx, ticker in enumerate(tickers):
        if not isinstance(ticker, str) or not ticker.strip():
            raise ConfigError(f"{path}[{idx}] must be a non-empty string")
        normalized = ticker.strip().upper()
        if normalized != ticker:
            raise ConfigError(f"{path}[{idx}] must be uppercase without surrounding whitespace")
        if normalized in seen:
            duplicates.append(normalized)
        seen.add(normalized)
    if duplicates:
        raise ConfigError(f"{path} contains duplicate tickers: {sorted(set(duplicates))}")


def _validate_optimization_config(config: dict[str, Any]) -> None:
    if config.get("primary_objective") != "realized_return_pct":
        raise ConfigError("primary_objective must be 'realized_return_pct'")
    constraints = _require_dict(config, "constraints")
    min_trades = constraints.get("min_trades")
    if not isinstance(min_trades, int) or min_trades <= 0:
        raise ConfigError("constraints.min_trades must be a positive integer")
    _validate_positive_number(constraints.get("max_avg_mae_pct"), "constraints.max_avg_mae_pct")
    _validate_positive_number(constraints.get("min_profit_factor"), "constraints.min_profit_factor")


def _validate_technical_setup_config(config: dict[str, Any]) -> None:
    signal_definitions = _require_dict(config, "signal_definitions")
    for name, logic in signal_definitions.items():
        if not isinstance(logic, dict):
            raise ConfigError(f"signal_definitions.{name} must be an object")
        if "description" in logic:
            logic = {k: v for k, v in logic.items() if k != "description"}
        _validate_logic(logic, f"signal_definitions.{name}")

    setup_key = "entry_setups" if "entry_setups" in config else "technical_setups"
    _require_dict(config, setup_key)


def _validate_logic(logic: Any, path: str) -> None:
    if not isinstance(logic, dict):
        raise ConfigError(f"{path} must be an object")

    if "all" in logic:
        _validate_logic_list(logic["all"], f"{path}.all")
        return
    if "any" in logic:
        _validate_logic_list(logic["any"], f"{path}.any")
        return
    if "not" in logic:
        _validate_logic(logic["not"], f"{path}.not")
        return

    _require_keys(logic, ["field", "operator"], path)
    operator = logic["operator"]
    if operator not in VALID_OPERATORS:
        raise ConfigError(f"{path}.operator '{operator}' is invalid")
    if operator == "between":
        value = logic.get("value")
        if not isinstance(value, list) or len(value) != 2:
            raise ConfigError(f"{path}.value must be a two-item list for between")
    elif operator not in {"exists", "missing"} and "value" not in logic:
        raise ConfigError(f"{path}.value is required for operator '{operator}'")


def _validate_logic_list(value: Any, path: str) -> None:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{path} must be a non-empty list")
    for idx, child in enumerate(value):
        _validate_logic(child, f"{path}[{idx}]")


def _require_dict(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be an object")
    return value


def _require_list(config: dict[str, Any], key: str) -> list[Any]:
    value = config.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"{key} must be a list")
    return value


def _require_keys(config: dict[str, Any], keys: list[str], path: str) -> None:
    for key in keys:
        if key not in config:
            raise ConfigError(f"{path}.{key} is required")


def _validate_bool(value: Any, path: str) -> None:
    if not isinstance(value, bool):
        raise ConfigError(f"{path} must be boolean")


def _validate_number(value: Any, path: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{path} must be numeric")


def _validate_positive_number(value: Any, path: str) -> None:
    _validate_number(value, path)
    if value <= 0:
        raise ConfigError(f"{path} must be positive")


def _validate_non_negative_number(value: Any, path: str) -> None:
    _validate_number(value, path)
    if value < 0:
        raise ConfigError(f"{path} must be non-negative")


def _validate_percent(value: Any, path: str) -> None:
    _validate_number(value, path)
    if value < 0 or value > 100:
        raise ConfigError(f"{path} must be between 0 and 100")
