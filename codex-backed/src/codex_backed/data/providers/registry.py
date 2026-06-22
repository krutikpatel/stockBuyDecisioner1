from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codex_backed.config.loader import ConfigError
from codex_backed.data.providers.capabilities import ProviderCapabilities

_VALID_PRICE_TYPES = {"pickle", "yfinance", "fmp", "composite"}
_VALID_FUNDAMENTALS_TYPES = {"null", "yfinance", "fmp", "composite"}


@dataclass
class ProviderSet:
    """Concrete provider instances for a single mode."""

    price_backtest: Any   # satisfies PriceProvider protocol
    price_live: Any       # satisfies PriceProvider protocol
    fundamentals: Any     # satisfies FundamentalsProvider protocol


def build_providers(
    config: dict[str, Any],
    mode: str | None = None,
    pickle_path_override: str | None = None,
) -> ProviderSet:
    """Instantiate concrete providers from a data_provider_config dict.

    Args:
        config: Parsed data_provider_config.json contents.
        mode:   Override active_mode.  Defaults to config["active_mode"].

    Raises:
        ConfigError: Unknown mode, missing provider block, or structural issues.
    """
    active_mode = mode or config.get("active_mode")
    modes = config.get("modes", {})
    if not isinstance(modes, dict) or active_mode not in modes:
        raise ConfigError(
            f"Unknown data provider mode '{active_mode}'. "
            f"Available modes: {sorted(modes.keys())}"
        )

    providers_cfg = config.get("providers", {})
    mode_cfg = modes[active_mode]

    price_backtest = _build_price_provider(
        mode_cfg.get("price_provider_backtest", {}),
        providers_cfg,
        pickle_path_override=pickle_path_override,
    )
    price_live = _build_price_provider(
        mode_cfg.get("price_provider_live", {}), providers_cfg
    )
    fundamentals = _build_fundamentals_provider(
        mode_cfg.get("fundamentals_provider", {}), providers_cfg
    )
    return ProviderSet(
        price_backtest=price_backtest,
        price_live=price_live,
        fundamentals=fundamentals,
    )


# ---------------------------------------------------------------------------
# Internal builder helpers
# ---------------------------------------------------------------------------


def _build_price_provider(
    spec: dict[str, Any],
    providers_cfg: dict[str, Any],
    pickle_path_override: str | None = None,
):
    ptype = spec.get("type")
    caps = _resolve_capabilities(spec, providers_cfg)

    if ptype == "pickle":
        from codex_backed.data.providers.pickle_provider import PickleProvider

        pconfig = _resolve_provider_config(spec, providers_cfg)
        path = (
            pickle_path_override
            or pconfig.get("prices_cache_path", "codex-backed/cache/prices.pkl")
        )
        return PickleProvider(pickle_path=path, capabilities=caps)

    if ptype == "yfinance":
        from codex_backed.data.providers.yfinance_provider import YFinancePriceProvider

        pconfig = _resolve_provider_config(spec, providers_cfg)
        auto_adjust = pconfig.get("auto_adjust", False)
        return YFinancePriceProvider(capabilities=caps, auto_adjust=auto_adjust)

    if ptype == "fmp":
        from codex_backed.data.providers.fmp_provider import FMPPriceProvider
        from codex_backed.data.providers.cache import DiskCache
        from codex_backed.data.providers.budget import DailyBudget

        pconfig = _resolve_provider_config(spec, providers_cfg)
        api_key = os.environ.get(pconfig.get("api_key_env", "FMP_API_KEY"), "")
        cache_dir = Path(pconfig.get("cache_dir", "codex-backed/cache/fmp"))
        schema_v = int(pconfig.get("cache_schema_version", 1))
        ttl_days = float(pconfig.get("cache_ttl_days", 1))
        budget_path = Path(pconfig.get("budget_path", "codex-backed/cache/fmp_budget.json"))
        budget_limit = pconfig.get("budget_limit")
        if budget_limit is not None:
            budget_limit = int(budget_limit)
        budget_on_exceed = pconfig.get("budget_on_exceed", "warn")
        cache = DiskCache(cache_dir, schema_version=schema_v, ttl_seconds=ttl_days * 86_400)
        budget = DailyBudget(budget_path, limit=budget_limit, on_exceed=budget_on_exceed)
        return FMPPriceProvider(api_key=api_key, capabilities=caps, cache=cache, budget=budget)

    if ptype == "composite":
        from codex_backed.data.providers.composite import CompositePriceProvider

        primary = _build_price_provider(spec.get("primary", {}), providers_cfg, pickle_path_override=pickle_path_override)
        fallback = _build_price_provider(spec.get("fallback", {}), providers_cfg, pickle_path_override=pickle_path_override)
        return CompositePriceProvider(primary=primary, fallback=fallback)

    raise ConfigError(
        f"Unknown price provider type '{ptype}'. "
        f"Supported: {sorted(_VALID_PRICE_TYPES)}"
    )


def _build_fundamentals_provider(spec: dict[str, Any], providers_cfg: dict[str, Any]):
    ptype = spec.get("type")

    if ptype == "null":
        from codex_backed.data.providers.null_fundamentals import NullFundamentalsProvider

        return NullFundamentalsProvider()

    if ptype == "yfinance":
        from codex_backed.data.providers.yfinance_provider import YFinanceFundamentalsProvider

        caps = _resolve_capabilities(spec, providers_cfg)
        return YFinanceFundamentalsProvider(capabilities=caps)

    if ptype == "fmp":
        from codex_backed.data.providers.fmp_provider import FMPFundamentalsProvider
        from codex_backed.data.providers.cache import DiskCache
        from codex_backed.data.providers.budget import DailyBudget

        pconfig = _resolve_provider_config(spec, providers_cfg)
        caps = _resolve_capabilities(spec, providers_cfg)
        api_key = os.environ.get(pconfig.get("api_key_env", "FMP_API_KEY"), "")
        cache_dir = Path(pconfig.get("cache_dir", "codex-backed/cache/fmp"))
        schema_v = int(pconfig.get("cache_schema_version", 1))
        ttl_days = float(pconfig.get("cache_ttl_days", 1))
        budget_path = Path(pconfig.get("budget_path", "codex-backed/cache/fmp_budget.json"))
        budget_limit = pconfig.get("budget_limit")
        if budget_limit is not None:
            budget_limit = int(budget_limit)
        budget_on_exceed = pconfig.get("budget_on_exceed", "warn")
        cache = DiskCache(cache_dir, schema_version=schema_v, ttl_seconds=ttl_days * 86_400)
        budget = DailyBudget(budget_path, limit=budget_limit, on_exceed=budget_on_exceed)
        return FMPFundamentalsProvider(api_key=api_key, capabilities=caps, cache=cache, budget=budget)

    if ptype == "composite":
        from codex_backed.data.providers.composite import CompositeFundamentalsProvider

        primary = _build_fundamentals_provider(spec.get("primary", {}), providers_cfg)
        fallback = _build_fundamentals_provider(spec.get("fallback", {}), providers_cfg)
        field_overrides = frozenset(spec.get("field_overrides", []))
        return CompositeFundamentalsProvider(primary=primary, fallback=fallback, field_overrides=field_overrides)

    raise ConfigError(
        f"Unknown fundamentals provider type '{ptype}'. "
        f"Supported: {sorted(_VALID_FUNDAMENTALS_TYPES)}"
    )


def _resolve_provider_config(
    spec: dict[str, Any], providers_cfg: dict[str, Any]
) -> dict[str, Any]:
    """Return the provider config block referenced by spec['config_ref']."""
    config_ref = spec.get("config_ref")
    if config_ref is None:
        return {}
    if config_ref not in providers_cfg:
        raise ConfigError(
            f"Provider config_ref '{config_ref}' not found in providers block. "
            f"Available: {sorted(providers_cfg.keys())}"
        )
    return providers_cfg[config_ref]


def _resolve_capabilities(
    spec: dict[str, Any], providers_cfg: dict[str, Any]
) -> ProviderCapabilities:
    """Build ProviderCapabilities from the tier_capabilities block in the provider config.

    Composite specs have no config_ref; return empty capabilities (each sub-provider
    carries its own capabilities).
    """
    if spec.get("type") == "composite":
        return _build_capabilities({})
    pconfig = _resolve_provider_config(spec, providers_cfg)
    tier = pconfig.get("tier_capabilities", {})
    return _build_capabilities(tier)


def _build_capabilities(tier: dict[str, Any]) -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_prices=bool(tier.get("supports_prices", False)),
        supports_fundamentals=bool(tier.get("supports_fundamentals", False)),
        fundamentals_fields=frozenset(tier.get("fundamentals_fields", [])),
        history_start_date=tier.get("history_start_date"),
        price_realtime=bool(tier.get("price_realtime", False)),
        rate_limit_per_minute=int(tier.get("rate_limit_per_minute", 0)),
    )
