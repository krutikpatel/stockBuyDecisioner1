from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields as dc_fields
from datetime import date
from typing import Any

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.capabilities import ProviderCapabilities

logger = logging.getLogger(__name__)


@dataclass
class CompositePriceStats:
    primary_failures: int = 0
    fallback_serves: int = 0


class CompositePriceProvider:
    """PriceProvider that tries primary first, falls back per-ticker.

    Bars for a given ticker come entirely from one source — never a splice
    of primary + fallback bars.  Provenance is recorded in `last_provenance`
    after each fetch call.
    """

    name = "composite"

    def __init__(self, primary: Any, fallback: Any) -> None:
        self._primary = primary
        self._fallback = fallback
        self.stats = CompositePriceStats()
        self.last_provenance: dict[str, str] = {}

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._primary.capabilities

    def fetch_history_batch(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[dict[str, Any]]]:
        provenance: dict[str, str] = {}
        try:
            primary_result = self._primary.fetch_history_batch(tickers, start, end)
        except Exception as exc:
            logger.warning("Primary fetch_history_batch failed: %s — falling back", exc)
            self.stats.primary_failures += 1
            primary_result = {}

        served: dict[str, list[dict[str, Any]]] = {}
        missing: list[str] = []

        for ticker in tickers:
            bars = primary_result.get(ticker.upper())
            if bars:
                served[ticker.upper()] = bars
                provenance[ticker.upper()] = self._primary.name
            else:
                missing.append(ticker)

        if missing:
            self.stats.primary_failures += len(missing)
            try:
                fallback_result = self._fallback.fetch_history_batch(missing, start, end)
            except Exception as exc:
                logger.warning("Fallback fetch_history_batch failed: %s", exc)
                fallback_result = {}
            for ticker in missing:
                bars = fallback_result.get(ticker.upper())
                if bars:
                    served[ticker.upper()] = bars
                    provenance[ticker.upper()] = self._fallback.name
                    self.stats.fallback_serves += 1

        self.last_provenance = provenance
        return served

    def fetch_live_batch(
        self,
        tickers: list[str],
        period: str = "2y",
        interval: str = "1d",
    ) -> dict[str, list[dict[str, Any]]]:
        provenance: dict[str, str] = {}
        try:
            primary_result = self._primary.fetch_live_batch(tickers, period=period, interval=interval)
        except Exception as exc:
            logger.warning("Primary fetch_live_batch failed: %s — falling back", exc)
            self.stats.primary_failures += 1
            primary_result = {}

        served: dict[str, list[dict[str, Any]]] = {}
        missing: list[str] = []

        for ticker in tickers:
            bars = primary_result.get(ticker.upper())
            if bars:
                served[ticker.upper()] = bars
                provenance[ticker.upper()] = self._primary.name
            else:
                missing.append(ticker)

        if missing:
            self.stats.primary_failures += len(missing)
            try:
                fallback_result = self._fallback.fetch_live_batch(missing, period=period, interval=interval)
            except Exception as exc:
                logger.warning("Fallback fetch_live_batch failed: %s", exc)
                fallback_result = {}
            for ticker in missing:
                bars = fallback_result.get(ticker.upper())
                if bars:
                    served[ticker.upper()] = bars
                    provenance[ticker.upper()] = self._fallback.name
                    self.stats.fallback_serves += 1

        self.last_provenance = provenance
        return served


class CompositeFundamentalsProvider:
    """FundamentalsProvider combining primary (FMP) and fallback (yfinance).

    Rules per field:
    1. If field is in field_overrides → always use fallback value.
    2. If field not in primary.capabilities.fundamentals_fields → use fallback.
    3. If as_of_date before primary.capabilities.history_start_date → use fallback.
    4. If primary value is None → use fallback.
    5. Otherwise use primary value.

    Fallback prefetch is lazy: only called when field_overrides is non-empty or
    a primary value is None at get_snapshot time.
    """

    name = "composite_fundamentals"

    def __init__(
        self,
        primary: Any,
        fallback: Any,
        field_overrides: frozenset[str] = frozenset(),
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._field_overrides = field_overrides
        self._fallback_prefetched: set[str] = set()

    @property
    def capabilities(self) -> ProviderCapabilities:
        p = self._primary.capabilities
        f = self._fallback.capabilities
        return ProviderCapabilities(
            supports_prices=False,
            supports_fundamentals=True,
            fundamentals_fields=p.fundamentals_fields | f.fundamentals_fields,
            history_start_date=f.history_start_date,
            price_realtime=False,
            rate_limit_per_minute=min(p.rate_limit_per_minute or 0, f.rate_limit_per_minute or 0),
        )

    def prefetch_batch(
        self,
        tickers: list[str],
        date_range: tuple[date, date],
    ) -> None:
        self._primary.prefetch_batch(tickers, date_range)
        if self._field_overrides:
            needed = [t for t in tickers if t.upper() not in self._fallback_prefetched]
            if needed:
                self._fallback.prefetch_batch(needed, date_range)
                self._fallback_prefetched.update(t.upper() for t in needed)

    def get_snapshot(
        self, ticker: str, as_of_date: date
    ) -> FundamentalsSnapshot:
        primary_snap = self._primary.get_snapshot(ticker, as_of_date)
        fallback_snap: FundamentalsSnapshot | None = None

        primary_caps = self._primary.capabilities
        primary_history_start = primary_caps.history_start_date
        use_primary_date = (
            primary_history_start is None
            or as_of_date.isoformat() >= primary_history_start
        )

        def _get_field(field_name: str) -> Any:
            nonlocal fallback_snap
            if field_name in self._field_overrides:
                fallback_snap = fallback_snap or self._ensure_fallback(ticker, as_of_date)
                return getattr(fallback_snap, field_name, None)
            if field_name not in primary_caps.fundamentals_fields:
                fallback_snap = fallback_snap or self._ensure_fallback(ticker, as_of_date)
                return getattr(fallback_snap, field_name, None)
            if not use_primary_date:
                fallback_snap = fallback_snap or self._ensure_fallback(ticker, as_of_date)
                return getattr(fallback_snap, field_name, None)
            primary_val = getattr(primary_snap, field_name, None)
            if primary_val is None:
                fallback_snap = fallback_snap or self._ensure_fallback(ticker, as_of_date)
                return getattr(fallback_snap, field_name, None)
            return primary_val

        kwargs: dict[str, Any] = {"ticker": ticker, "as_of_date": as_of_date.isoformat()}
        for f in dc_fields(FundamentalsSnapshot):
            if f.name in ("ticker", "as_of_date"):
                continue
            kwargs[f.name] = _get_field(f.name)
        return FundamentalsSnapshot(**kwargs)

    def signature(self) -> str:
        return f"composite({self._primary.signature()},{self._fallback.signature()})"

    def _ensure_fallback(self, ticker: str, as_of_date: date) -> FundamentalsSnapshot:
        t = ticker.upper()
        if t not in self._fallback_prefetched:
            self._fallback.prefetch_batch([ticker], (as_of_date, as_of_date))
            self._fallback_prefetched.add(t)
        return self._fallback.get_snapshot(ticker, as_of_date)
