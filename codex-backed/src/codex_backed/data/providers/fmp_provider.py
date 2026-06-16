from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.alias_apply import apply_aliases
from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.budget import DailyBudget
from codex_backed.data.providers.cache import DiskCache
from codex_backed.data.providers.capabilities import ProviderCapabilities
from codex_backed.data.providers.field_aliases import FMP_ALIASES
from codex_backed.data.providers.http_client import HttpClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://financialmodelingprep.com/api/v3"
_PERIOD_TO_DAYS = {"1y": 365, "2y": 730, "3y": 1095, "5y": 1825}


def _period_days(period: str) -> int:
    return _PERIOD_TO_DAYS.get(period, 730)


class FMPPriceProvider:
    """PriceProvider backed by the Financial Modeling Prep REST API (prices only).

    fetch_history_batch: uses /historical-price-full/{ticker}?from=&to=
    fetch_live_batch:    uses /historical-price-full/{ticker,ticker,...}?from=&to=
                         computing the date range from the period string.

    Results are cached per (ticker, date-range) key.  A 4xx error never
    overwrites a valid cache entry.  Each successful network call is counted
    against the daily budget.
    """

    name = "fmp"

    def __init__(
        self,
        api_key: str,
        capabilities: ProviderCapabilities,
        cache: DiskCache,
        budget: DailyBudget,
        http_client: HttpClient | None = None,
    ) -> None:
        self._api_key = api_key
        self.capabilities = capabilities
        self._cache = cache
        self._budget = budget
        self._http = http_client or HttpClient()

    # ------------------------------------------------------------------
    # PriceProvider interface
    # ------------------------------------------------------------------

    def fetch_history_batch(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for ticker in tickers:
            bars = self._fetch_history(ticker.upper(), start.isoformat(), end.isoformat())
            if bars:
                result[ticker.upper()] = bars
        return result

    def fetch_live_batch(
        self,
        tickers: list[str],
        period: str = "2y",
        interval: str = "1d",
    ) -> dict[str, list[dict[str, Any]]]:
        end_date = date.today()
        start_date = end_date - timedelta(days=_period_days(period))
        # Use the batch historical endpoint (comma-separated tickers)
        batch_key = f"live/{','.join(sorted(t.upper() for t in tickers))}/{start_date}/{end_date}"
        cached = self._cache.get(batch_key)
        if cached is not None:
            return cached

        ticker_str = ",".join(t.upper() for t in tickers)
        url = f"{_BASE_URL}/historical-price-full/{ticker_str}"
        self._budget.check()
        try:
            data = self._http.get(url, params={
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "apikey": self._api_key,
            })
        except ProviderError:
            logger.warning("FMP live batch failed for %s", ticker_str)
            return {}
        self._budget.increment()

        result = _parse_batch_response(data)
        self._cache.set(batch_key, result)
        return result

    def signature(self) -> str:
        return f"fmp:{self.capabilities.history_start_date or 'unknown'}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_history(
        self, ticker: str, start: str, end: str
    ) -> list[dict[str, Any]]:
        cache_key = f"history/{ticker}/{start}/{end}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{_BASE_URL}/historical-price-full/{ticker}"
        self._budget.check()
        try:
            data = self._http.get(url, params={"from": start, "to": end, "apikey": self._api_key})
        except ProviderError as exc:
            logger.warning("FMP history failed for %s: %s", ticker, exc)
            return []
        self._budget.increment()

        bars = _parse_single_response(data, start, end)
        self._cache.set(cache_key, bars)
        return bars


class FMPFundamentalsProvider:
    """FundamentalsProvider backed by FMP REST API.

    prefetch_batch: fetches key-metrics, profile, and earning_calendar for each
    ticker and stores results in an in-memory dict.  get_snapshot reads
    exclusively from that dict — performs no I/O.
    """

    name = "fmp"

    def __init__(
        self,
        api_key: str,
        capabilities: ProviderCapabilities,
        cache: DiskCache,
        budget: DailyBudget,
        http_client: HttpClient | None = None,
    ) -> None:
        self._api_key = api_key
        self.capabilities = capabilities
        self._cache = cache
        self._budget = budget
        self._http = http_client or HttpClient()
        self._prefetch_store: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # FundamentalsProvider interface
    # ------------------------------------------------------------------

    def prefetch_batch(
        self,
        tickers: list[str],
        date_range: tuple[date, date],
    ) -> None:
        for ticker in tickers:
            t = ticker.upper()
            payload = self._prefetch_store.get(t)
            if payload is not None:
                continue  # already fetched this session

            cache_key = f"fundamentals/{t}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._prefetch_store[t] = cached
                continue

            merged: dict[str, Any] = {}
            merged.update(self._fetch_endpoint(f"/key-metrics/{t}", ticker_param=t) or {})
            merged.update(self._fetch_endpoint(f"/profile/{t}", ticker_param=t) or {})
            calendar = self._fetch_earnings_calendar(t)
            merged["_earnings_calendar"] = calendar

            self._prefetch_store[t] = merged
            self._cache.set(cache_key, merged)

    def get_snapshot(
        self,
        ticker: str,
        as_of_date: date,
    ) -> FundamentalsSnapshot:
        t = ticker.upper()
        history_start = self.capabilities.history_start_date
        if history_start and as_of_date.isoformat() < history_start:
            return FundamentalsSnapshot(ticker=ticker, as_of_date=as_of_date.isoformat())

        payload = self._prefetch_store.get(t, {})
        mapped = apply_aliases(payload, FMP_ALIASES)

        # Compute earnings calendar fields
        calendar: list[dict[str, Any]] = payload.get("_earnings_calendar", [])
        earnings_days_away = _compute_earnings_days_away(calendar, as_of_date)
        earnings_within_30 = earnings_days_away is not None and 0 <= earnings_days_away <= 30

        return FundamentalsSnapshot(
            ticker=ticker,
            as_of_date=as_of_date.isoformat(),
            sales_growth_yoy=_float_or_none(mapped.get("sales_growth_yoy")),
            eps_growth_yoy=_float_or_none(mapped.get("eps_growth_yoy")),
            eps_growth_next_year=_float_or_none(mapped.get("eps_growth_next_year")),
            eps_growth_3y=_float_or_none(mapped.get("eps_growth_3y")),
            eps_growth_5y=_float_or_none(mapped.get("eps_growth_5y")),
            gross_margin=_float_or_none(mapped.get("gross_margin")),
            operating_margin=_float_or_none(mapped.get("operating_margin")),
            net_margin=_float_or_none(mapped.get("net_margin")),
            free_cash_flow=_float_or_none(mapped.get("free_cash_flow")),
            roic=_float_or_none(mapped.get("roic")),
            roe=_float_or_none(mapped.get("roe")),
            roa=_float_or_none(mapped.get("roa")),
            debt_to_equity=_float_or_none(mapped.get("debt_to_equity")),
            current_ratio=_float_or_none(mapped.get("current_ratio")),
            trailing_pe=_float_or_none(mapped.get("trailing_pe")),
            peg_ratio=_float_or_none(mapped.get("peg_ratio")),
            price_to_sales=_float_or_none(mapped.get("price_to_sales")),
            ev_to_ebitda=_float_or_none(mapped.get("ev_to_ebitda")),
            price_to_fcf=_float_or_none(mapped.get("price_to_fcf")),
            market_cap=_float_or_none(mapped.get("market_cap")),
            beta=_float_or_none(mapped.get("beta")),
            sector=mapped.get("sector"),
            industry=mapped.get("industry"),
            analyst_recommendation=_float_or_none(mapped.get("analyst_recommendation")),
            analyst_target_price=_float_or_none(mapped.get("analyst_target_price")),
            earnings_days_away=earnings_days_away,
            earnings_within_30_days=earnings_within_30,
        )

    def signature(self) -> str:
        return f"fmp:{self.capabilities.history_start_date or 'unknown'}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_endpoint(self, path: str, ticker_param: str) -> dict[str, Any] | None:
        url = f"{_BASE_URL}{path}"
        self._budget.check()
        try:
            data = self._http.get(url, params={"apikey": self._api_key})
        except ProviderError as exc:
            logger.warning("FMP fundamentals fetch failed for %s: %s", path, exc)
            return None
        self._budget.increment()
        # FMP returns a list; take the most recent entry
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        if isinstance(data, dict):
            return data
        return None

    def _fetch_earnings_calendar(self, ticker: str) -> list[dict[str, Any]]:
        url = f"{_BASE_URL}/historical/earning_calendar/{ticker}"
        self._budget.check()
        try:
            data = self._http.get(url, params={"apikey": self._api_key})
        except ProviderError as exc:
            logger.warning("FMP earnings calendar failed for %s: %s", ticker, exc)
            return []
        self._budget.increment()
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_earnings_days_away(
    calendar: list[dict[str, Any]], as_of: date
) -> int | None:
    """Return days until the next earnings date on or after as_of."""
    future_dates = []
    for entry in calendar:
        d_str = entry.get("date", "")
        if not d_str:
            continue
        try:
            d = date.fromisoformat(d_str[:10])
        except ValueError:
            continue
        if d >= as_of:
            future_dates.append(d)
    if not future_dates:
        return None
    next_date = min(future_dates)
    return (next_date - as_of).days


# ------------------------------------------------------------------
# Response parsers
# ------------------------------------------------------------------

def _parse_single_response(
    data: Any, start: str | None = None, end: str | None = None
) -> list[dict[str, Any]]:
    """Parse /historical-price-full/{ticker} response."""
    if not isinstance(data, dict):
        return []
    historical = data.get("historical")
    if not isinstance(historical, list):
        return []
    return _filter_and_normalize(historical, start, end)


def _parse_batch_response(
    data: Any, start: str | None = None, end: str | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Parse /historical-price-full/{ticker1,ticker2} response.

    FMP returns either a single dict (1 ticker) or a list of dicts (multi-ticker).
    """
    result: dict[str, list[dict[str, Any]]] = {}
    if isinstance(data, dict):
        symbol = data.get("symbol", "")
        bars = _parse_single_response(data, start, end)
        if symbol and bars:
            result[symbol.upper()] = bars
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol", "")
            bars = _parse_single_response(item, start, end)
            if symbol and bars:
                result[symbol.upper()] = bars
    return result


def _filter_and_normalize(
    historical: list[dict[str, Any]],
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    bars = []
    for raw in historical:
        d = raw.get("date", "")
        if not d:
            continue
        d10 = d[:10]
        if start and d10 < start:
            continue
        if end and d10 > end:
            continue
        try:
            bars.append({
                "date": d[:10],
                "open": float(raw["open"]),
                "high": float(raw["high"]),
                "low": float(raw["low"]),
                "close": float(raw["close"]),
                "volume": float(raw.get("volume", 0)),
            })
        except (KeyError, TypeError, ValueError):
            continue
    # FMP returns newest-first; reverse to chronological order
    bars.sort(key=lambda b: b["date"])
    return bars
