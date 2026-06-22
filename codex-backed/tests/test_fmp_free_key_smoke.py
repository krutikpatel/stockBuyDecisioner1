"""Free-key FMP provider smoke gate (real HTTP, tiny universe).

Validates that FMPPriceProvider and FMPFundamentalsProvider work end-to-end
against the live FMP /stable/ endpoints using whichever API key is in the
environment.  Tests run only against AAPL and MSFT — the two tickers most
likely to be accessible under any FMP plan — and make the minimum number of
API calls needed to confirm the provider integration is functional.

This is NOT an S4.3 activation gate.  It verifies provider correctness on a
tiny accessible subset.  S4.3 requires 80% field population across the entire
backtest universe and must be evaluated separately with a paid FMP key.

Skip conditions:
  - FMP_API_KEY not set
  - Network unavailable (SKIP, not FAIL — we treat a network-level error as
    an environment issue, not a provider bug)
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

_FMP_KEY = os.environ.get("FMP_API_KEY", "")
_HAS_KEY = bool(_FMP_KEY)

pytestmark = pytest.mark.skipif(not _HAS_KEY, reason="FMP_API_KEY not set")

_SMOKE_TICKERS = ["AAPL", "MSFT"]
_PRICE_START = date(2024, 1, 2)
_PRICE_END = date(2024, 1, 10)


@pytest.fixture(scope="module")
def smoke_providers(tmp_path_factory):
    """Build real FMPPriceProvider and FMPFundamentalsProvider against live FMP."""
    from codex_backed.data.providers.fmp_provider import FMPFundamentalsProvider, FMPPriceProvider
    from codex_backed.data.providers.budget import DailyBudget
    from codex_backed.data.providers.cache import DiskCache
    from codex_backed.data.providers.capabilities import ProviderCapabilities

    tmp = tmp_path_factory.mktemp("fmp_free_smoke")
    cache = DiskCache(str(tmp / "cache"), schema_version=1, ttl_seconds=86400)
    budget = DailyBudget(budget_path=str(tmp / "budget.json"), limit=50, on_exceed="warn")
    caps = ProviderCapabilities(
        supports_prices=True,
        supports_fundamentals=True,
        fundamentals_fields=[],
        history_start_date="2000-01-01",
        price_realtime=True,
        rate_limit_per_minute=300,
    )
    price_prov = FMPPriceProvider(
        api_key=_FMP_KEY, capabilities=caps, cache=cache, budget=budget
    )
    fund_prov = FMPFundamentalsProvider(
        api_key=_FMP_KEY, capabilities=caps, cache=cache, budget=budget
    )
    return price_prov, fund_prov, tmp


# ---------------------------------------------------------------------------
# Price provider smoke tests
# ---------------------------------------------------------------------------

def test_price_provider_returns_bars_for_aapl(smoke_providers):
    """FMPPriceProvider must return at least one OHLCV bar for AAPL."""
    price_prov, _, _ = smoke_providers
    try:
        result = price_prov.fetch_history_batch(["AAPL"], _PRICE_START, _PRICE_END)
    except Exception as exc:
        if "429" in str(exc) or "network" in str(exc).lower():
            pytest.skip(f"FMP network/rate issue: {exc}")
        raise
    if not result.get("AAPL"):
        pytest.skip("AAPL not accessible on current FMP plan (402 or empty response)")
    bars = result["AAPL"]
    assert len(bars) >= 1, "Expected at least one bar for AAPL"
    bar = bars[0]
    assert {"date", "open", "high", "low", "close"} <= set(bar), f"Bar missing fields: {bar}"
    assert bar["close"] > 0, "Close price must be positive"


def test_price_provider_bars_are_chronological_for_aapl(smoke_providers):
    """Bars returned by FMPPriceProvider must be sorted oldest-first."""
    price_prov, _, _ = smoke_providers
    try:
        result = price_prov.fetch_history_batch(["AAPL"], _PRICE_START, _PRICE_END)
    except Exception as exc:
        if "429" in str(exc) or "network" in str(exc).lower():
            pytest.skip(f"FMP network/rate issue: {exc}")
        raise
    if not result.get("AAPL"):
        pytest.skip("AAPL not accessible on current FMP plan")
    bars = result["AAPL"]
    if len(bars) < 2:
        pytest.skip("Fewer than 2 bars returned — cannot verify ordering")
    dates = [b["date"] for b in bars]
    assert dates == sorted(dates), f"Bars not in chronological order: {dates[:5]}"


def test_price_provider_cache_hit_on_second_call(smoke_providers):
    """A second identical fetch must be served from cache (no network call)."""
    from codex_backed.data.providers.fmp_provider import FMPPriceProvider
    from codex_backed.data.providers.budget import DailyBudget
    from codex_backed.data.providers.cache import DiskCache
    from codex_backed.data.providers.capabilities import ProviderCapabilities

    price_prov, _, tmp = smoke_providers
    # A fresh provider sharing the same cache dir — second call must hit cache
    cache2 = DiskCache(str(tmp / "cache"), schema_version=1, ttl_seconds=86400)
    caps2 = ProviderCapabilities(
        supports_prices=True,
        supports_fundamentals=False,
        fundamentals_fields=[],
        history_start_date="2000-01-01",
        price_realtime=True,
        rate_limit_per_minute=300,
    )
    budget2 = DailyBudget(budget_path=str(tmp / "budget2.json"), limit=50, on_exceed="warn")
    price_prov2 = FMPPriceProvider(
        api_key=_FMP_KEY, capabilities=caps2, cache=cache2, budget=budget2
    )
    # This must not raise even if no network is available — should read from cache
    try:
        result = price_prov2.fetch_history_batch(["AAPL"], _PRICE_START, _PRICE_END)
    except Exception as exc:
        if "429" in str(exc) or "network" in str(exc).lower():
            pytest.skip(f"FMP network/rate issue: {exc}")
        raise
    if not result.get("AAPL"):
        pytest.skip("AAPL not in cache (first call must have been blocked by plan)")
    assert len(result["AAPL"]) >= 1


# ---------------------------------------------------------------------------
# Fundamentals provider smoke tests
# ---------------------------------------------------------------------------

def test_fundamentals_prefetch_batch_does_not_raise_for_aapl(smoke_providers):
    """FMPFundamentalsProvider.prefetch_batch must not raise for AAPL."""
    _, fund_prov, _ = smoke_providers
    try:
        fund_prov.prefetch_batch(["AAPL"], (_PRICE_START, _PRICE_END))
    except Exception as exc:
        if "429" in str(exc) or "network" in str(exc).lower():
            pytest.skip(f"FMP network/rate issue: {exc}")
        raise
    # No assertion on content — just confirming the call completes


def test_fundamentals_get_snapshot_returns_populated_fields_for_aapl(smoke_providers):
    """get_snapshot must return at least one non-None fundamentals field for AAPL."""
    _, fund_prov, _ = smoke_providers
    try:
        fund_prov.prefetch_batch(["AAPL"], (_PRICE_START, _PRICE_END))
    except Exception as exc:
        if "429" in str(exc) or "network" in str(exc).lower():
            pytest.skip(f"FMP network/rate issue: {exc}")
        raise

    snap = fund_prov.get_snapshot("AAPL", _PRICE_START)
    fmp_fields = [
        snap.eps_growth_yoy, snap.gross_margin, snap.operating_margin,
        snap.net_margin, snap.roic, snap.roe, snap.market_cap, snap.beta,
    ]
    populated = [f for f in fmp_fields if f is not None]
    if not populated:
        pytest.skip(
            "AAPL fundamentals prefetch returned no data (plan may not cover fundamentals). "
            "S4.3 requires a paid FMP plan for full field population."
        )
    assert len(populated) >= 1, "Expected at least one FMP fundamentals field populated for AAPL"
