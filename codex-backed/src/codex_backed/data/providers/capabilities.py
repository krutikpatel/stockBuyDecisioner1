from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declarative description of what a provider sells at its configured tier.

    Loaded from configs/data_provider_config.json -> providers.<name>.tier_capabilities.
    Composite logic reads this to decide whether to fall through to a fallback.
    """

    supports_prices: bool
    supports_fundamentals: bool
    fundamentals_fields: frozenset[str]
    history_start_date: str | None  # ISO date e.g. "2020-01-01"; None = unbounded
    price_realtime: bool
    rate_limit_per_minute: int


def supports_field(caps: ProviderCapabilities, field_name: str) -> bool:
    """Return True if the provider declares support for the given fundamentals field."""
    return field_name in caps.fundamentals_fields
