"""
Provider factory — creates the appropriate MarketDataProvider based on config.

Reads ``active_provider`` from ``backend/config/market_and_universe_config.json``.
Defaults to ``yfinance`` when the key is absent or the config is unavailable.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.data.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[MarketDataProvider]] = {}


def _register(name: str):
    """Class decorator to register a provider under a name."""
    def decorator(cls: type[MarketDataProvider]):
        _REGISTRY[name] = cls
        return cls
    return decorator


# Register the built-in provider at import time
def _load_registry() -> None:
    from app.data.providers.yfinance_provider import YFinanceProvider
    _REGISTRY["yfinance"] = YFinanceProvider


class ProviderFactory:
    """Creates MarketDataProvider instances by name."""

    @staticmethod
    def create(
        provider_name: Optional[str] = None,
    ) -> MarketDataProvider:
        """Return the provider for *provider_name*.

        If provider_name is None, reads ``data_sources.active_provider`` from
        ``market_and_universe_config.json``.  Falls back to ``yfinance``.
        """
        if not _REGISTRY:
            _load_registry()

        name = provider_name or ProviderFactory._active_provider_from_config()

        cls = _REGISTRY.get(name)
        if cls is None:
            logger.warning(
                "Unknown provider '%s'; available: %s. Falling back to yfinance.",
                name, sorted(_REGISTRY),
            )
            cls = _REGISTRY["yfinance"]

        logger.debug("Creating provider: %s", name)
        return cls()

    @staticmethod
    def _active_provider_from_config() -> str:
        try:
            from app.config.config_loader import get_multi_config
            cfg = get_multi_config()
            return cfg.data_sources.get("active_provider", "yfinance")
        except Exception:
            return "yfinance"

    @staticmethod
    def available_providers() -> list[str]:
        if not _REGISTRY:
            _load_registry()
        return sorted(_REGISTRY)
