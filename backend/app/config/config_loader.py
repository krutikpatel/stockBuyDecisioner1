from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
_instance: Optional["MultiSourceConfig"] = None


class MultiSourceConfig:
    """Loads and exposes all 5 new strategy config files.

    Independent of the existing AlgoConfig singleton — they coexist.
    Use get_multi_config() for the default singleton instance, or
    instantiate directly with a custom config_dir for tests.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        d = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
        self._market = self._load(d / "market_and_universe_config.json")
        self._classification = self._load(d / "stock_classification_config.json")
        self._setup = self._load(d / "technical_setup_config.json")
        self._strategy = self._load(d / "strategy_logic_config.json")
        self._governance = self._load(d / "parameter_governance_config.json")

    @staticmethod
    def _load(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        return json.loads(path.read_text())

    # ------------------------------------------------------------------
    # market_and_universe_config.json
    # ------------------------------------------------------------------

    @property
    def universe_filters(self) -> dict:
        return self._market.get("universe_filters", {})

    @property
    def sector_benchmarks(self) -> dict[str, str]:
        return self._market.get("sector_benchmarks", {})

    @property
    def market_regime_rules(self) -> dict:
        return self._market.get("market_regime_rules", {})

    @property
    def regime_weight_adjustments(self) -> dict:
        return self._market.get("market_regime_rules", {}).get("regime_weight_adjustments", {})

    @property
    def data_sources(self) -> dict:
        return self._market.get("data_sources", {})

    @property
    def active_provider(self) -> str:
        return self.data_sources.get("active_provider", "yfinance")

    # ------------------------------------------------------------------
    # stock_classification_config.json
    # ------------------------------------------------------------------

    @property
    def primary_categories(self) -> list[str]:
        return self._classification.get("primary_categories", [])

    @property
    def archetype_rules(self) -> dict:
        return self._classification.get("archetype_rules", {})

    @property
    def secondary_tag_rules(self) -> dict[str, dict]:
        return self._classification.get("secondary_tag_rules", {})

    # ------------------------------------------------------------------
    # technical_setup_config.json
    # ------------------------------------------------------------------

    @property
    def signal_definitions(self) -> dict[str, dict]:
        return self._setup.get("signal_definitions", {})

    @property
    def setup_definitions(self) -> dict[str, dict]:
        return self._setup.get("technical_setups", {})

    # ------------------------------------------------------------------
    # strategy_logic_config.json
    # ------------------------------------------------------------------

    @property
    def strategy_router_rules(self) -> list[dict]:
        return self._strategy.get("strategy_router", {}).get("rules", [])

    @property
    def strategy_router_fallback(self) -> str:
        return self._strategy.get("strategy_router", {}).get("fallback_strategy", "watchlist_low_confidence")

    @property
    def strategy_engines(self) -> dict[str, dict]:
        return self._strategy.get("strategy_engines", {})

    # ------------------------------------------------------------------
    # parameter_governance_config.json
    # ------------------------------------------------------------------

    @property
    def tuning_policy(self) -> dict:
        return self._governance.get("tuning_policy", {})

    @property
    def frozen_params(self) -> list[str]:
        return self._governance.get("tiers", {}).get("frozen", [])

    @property
    def active_params(self) -> list[str]:
        return self._governance.get("tiers", {}).get("active", [])


def get_multi_config() -> MultiSourceConfig:
    """Return the module-level MultiSourceConfig singleton.

    Respects the MULTI_CONFIG_DIR environment variable for overriding
    the config directory (useful in tests and CI).
    """
    global _instance
    if _instance is None:
        env_dir = os.environ.get("MULTI_CONFIG_DIR")
        _instance = MultiSourceConfig(Path(env_dir) if env_dir else None)
    return _instance


def reset_multi_config() -> None:
    """Reset the singleton (for tests that need a clean state)."""
    global _instance
    _instance = None
