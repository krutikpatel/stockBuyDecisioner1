"""
AlgoConfig: Singleton loader for algo_config.json.

Usage in services (default singleton):
    from app.algo_config import get_algo_config
    cfg = get_algo_config()
    period = cfg.technical_indicators["rsi_period"]

Usage with injection (tests / backtest experiments):
    cfg = AlgoConfig.from_file("/path/to/custom.json")
    result = some_service_function(data, algo_config=cfg)

    cfg = AlgoConfig.from_dict({...})  # inline dict

Environment override:
    ALGO_CONFIG_PATH=/path/to/custom.json python -m backtest.run_backtest ...
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_DEFAULT_PATH = Path(__file__).parent.parent / "algo_config.json"


class AlgoConfig:
    def __init__(self, data: dict) -> None:
        self._data = data

    @classmethod
    def from_file(cls, path: Optional[str | Path] = None) -> "AlgoConfig":
        """Load config from a JSON file. Uses ALGO_CONFIG_PATH env var if path is None."""
        if path is None:
            path = os.environ.get("ALGO_CONFIG_PATH", str(_DEFAULT_PATH))
        with open(path) as f:
            raw = json.load(f)
        return cls(raw)

    @classmethod
    def from_dict(cls, data: dict) -> "AlgoConfig":
        """Construct directly from a dict — for tests and programmatic experiments."""
        return cls(data)

    def get(self, section: str) -> dict:
        return self._data[section]

    @property
    def technical_indicators(self) -> dict:
        return self._data["technical_indicators"]

    @property
    def technical_scoring(self) -> dict:
        return self._data["technical_scoring"]

    @property
    def extension_detection(self) -> dict:
        return self._data["extension_detection"]

    @property
    def stock_archetype(self) -> dict:
        return self._data["stock_archetype"]

    @property
    def market_regime(self) -> dict:
        return self._data["market_regime"]

    @property
    def regime_scoring(self) -> dict:
        return self._data["regime_scoring"]

    @property
    def scoring(self) -> dict:
        return self._data["scoring"]

    @property
    def signal_cards(self) -> dict:
        return self._data["signal_cards"]

    @property
    def decision_logic(self) -> dict:
        return self._data["decision_logic"]

    @property
    def data_completeness(self) -> dict:
        return self._data["data_completeness"]

    @property
    def risk_management(self) -> dict:
        return self._data["risk_management"]

    @property
    def valuation(self) -> dict:
        return self._data["valuation"]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_singleton: Optional[AlgoConfig] = None


def get_algo_config() -> AlgoConfig:
    """Return the module-level singleton, loading from file on first call."""
    global _singleton
    if _singleton is None:
        _singleton = AlgoConfig.from_file()
    return _singleton


def reset_algo_config() -> None:
    """Force singleton reload on next call to get_algo_config().

    Use in tests when ALGO_CONFIG_PATH changes or after a from_dict override.
    """
    global _singleton
    _singleton = None
