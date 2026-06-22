from __future__ import annotations

from typing import Any, Mapping


def apply_aliases(
    payload: dict[str, Any],
    aliases: Mapping[str, list[str]],
) -> dict[str, Any | None]:
    """Map vendor-specific JSON keys to canonical FundamentalsSnapshot fields.

    For each canonical field, tries alias keys in order and returns the first
    value found in payload.  Returns None for a field when no alias key matches.
    Skips alias keys that start with '_computed_' (those are filled in by
    provider-specific post-processing logic, not read from a raw payload).

    Returns a dict keyed by canonical field name.
    """
    result: dict[str, Any | None] = {}
    for canonical, vendor_keys in aliases.items():
        value: Any | None = None
        for key in vendor_keys:
            if key.startswith("_computed_"):
                continue
            if key in payload:
                value = payload[key]
                break
        result[canonical] = value
    return result
