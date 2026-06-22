from __future__ import annotations

import logging
from datetime import date
from typing import Any

import yfinance as yf

from codex_backed.data.bars import normalize_price_frame
from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.alias_apply import apply_aliases
from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.capabilities import ProviderCapabilities
from codex_backed.data.providers.field_aliases import YFINANCE_ALIASES

logger = logging.getLogger(__name__)

_DEFAULT_CAPABILITIES = ProviderCapabilities(
    supports_prices=True,
    supports_fundamentals=False,   # fundamentals added in S3.3
    fundamentals_fields=frozenset(),
    history_start_date=None,
    price_realtime=False,
    rate_limit_per_minute=60,
)


class YFinancePriceProvider:
    """PriceProvider backed by yfinance.download.

    Wraps the existing fetch_yfinance_bars logic; fundamentals support
    will be added in S3.3 (kept separate per story sequencing).
    """

    name = "yfinance"

    def __init__(
        self,
        capabilities: ProviderCapabilities = _DEFAULT_CAPABILITIES,
        auto_adjust: bool = False,
    ) -> None:
        self.capabilities = capabilities
        self._auto_adjust = auto_adjust

    # ------------------------------------------------------------------
    # Public protocol methods
    # ------------------------------------------------------------------

    def fetch_history_batch(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[dict]]:
        """Download OHLCV bars for a date range from yfinance."""
        unique = list(dict.fromkeys(t.upper() for t in tickers))
        if not unique:
            raise ProviderError("No tickers requested")

        data = yf.download(
            tickers=unique,
            start=start.isoformat(),
            end=end.isoformat(),
            group_by="ticker",
            auto_adjust=self._auto_adjust,
            progress=False,
            threads=True,
        )
        return self._parse_download(data, unique)

    def fetch_live_batch(
        self,
        tickers: list[str],
        period: str = "2y",
        interval: str = "1d",
    ) -> dict[str, list[dict]]:
        """Download recent bars via period/interval from yfinance."""
        unique = list(dict.fromkeys(t.upper() for t in tickers))
        if not unique:
            raise ProviderError("No tickers requested")

        data = yf.download(
            tickers=unique,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=self._auto_adjust,
            progress=False,
            threads=True,
        )
        return self._parse_download(data, unique)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_download(
        self, data, unique_tickers: list[str]
    ) -> dict[str, list[dict]]:
        if data is None or getattr(data, "empty", True):
            raise ProviderError("yfinance returned no bars")

        result: dict[str, list[dict]] = {}

        if len(unique_tickers) == 1:
            # Single-ticker download returns a flat DataFrame (no MultiIndex)
            bars = normalize_price_frame(data)
            if bars:
                result[unique_tickers[0]] = bars
            return result

        for ticker in unique_tickers:
            try:
                frame = data[ticker]
            except KeyError:
                continue
            bars = normalize_price_frame(frame)
            if bars:
                result[ticker] = bars
        return result


_YF_FUNDAMENTALS_CAPS = ProviderCapabilities(
    supports_prices=False,
    supports_fundamentals=True,
    fundamentals_fields=frozenset([
        "insider_ownership", "institutional_ownership", "short_float",
        "trailing_pe", "forward_pe", "peg_ratio", "price_to_sales",
        "dividend_yield", "market_cap", "beta", "sector", "industry",
        "analyst_recommendation", "analyst_target_price",
    ]),
    history_start_date=None,
    price_realtime=False,
    rate_limit_per_minute=60,
)


class YFinanceFundamentalsProvider:
    """FundamentalsProvider backed by yfinance.Ticker(...).info.

    Focuses on the ownership/float fields that FMP does not provide at standard
    tier.  prefetch_batch fetches .info for each ticker once; get_snapshot is
    pure in-memory lookup.  An optional DiskCache can be supplied to persist
    .info across process restarts with a TTL.
    """

    name = "yfinance"

    def __init__(
        self,
        capabilities: ProviderCapabilities = _YF_FUNDAMENTALS_CAPS,
        cache=None,  # optional DiskCache
    ) -> None:
        self.capabilities = capabilities
        self._cache = cache
        self._prefetch_store: dict[str, dict[str, Any]] = {}

    def prefetch_batch(
        self,
        tickers: list[str],
        date_range: tuple[date, date],
    ) -> None:
        for ticker in tickers:
            t = ticker.upper()
            if t in self._prefetch_store:
                continue
            if self._cache is not None:
                cached = self._cache.get(f"yf_info/{t}")
                if cached is not None:
                    self._prefetch_store[t] = cached
                    continue
            info = self._fetch_info(t)
            self._prefetch_store[t] = info
            if self._cache is not None:
                self._cache.set(f"yf_info/{t}", info)

    def get_snapshot(self, ticker: str, as_of_date: date) -> FundamentalsSnapshot:
        t = ticker.upper()
        raw = self._prefetch_store.get(t, {})
        mapped = apply_aliases(raw, YFINANCE_ALIASES)

        def _float(v: Any) -> float | None:
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        return FundamentalsSnapshot(
            ticker=ticker,
            as_of_date=as_of_date.isoformat(),
            insider_ownership=_float(mapped.get("insider_ownership")),
            institutional_ownership=_float(mapped.get("institutional_ownership")),
            short_float=_float(mapped.get("short_float")),
            trailing_pe=_float(mapped.get("trailing_pe")),
            forward_pe=_float(mapped.get("forward_pe")),
            peg_ratio=_float(mapped.get("peg_ratio")),
            price_to_sales=_float(mapped.get("price_to_sales")),
            dividend_yield=_float(mapped.get("dividend_yield")),
            market_cap=_float(mapped.get("market_cap")),
            beta=_float(mapped.get("beta")),
            sector=mapped.get("sector"),
            industry=mapped.get("industry"),
            analyst_recommendation=_float(mapped.get("analyst_recommendation")),
            analyst_target_price=_float(mapped.get("analyst_target_price")),
        )

    def signature(self) -> str:
        return "yfinance_fundamentals"

    def _fetch_info(self, ticker: str) -> dict[str, Any]:
        try:
            info = yf.Ticker(ticker).info
            if not isinstance(info, dict):
                logger.warning("yfinance .info for %s returned unexpected type: %s", ticker, type(info))
                return {}
            return info
        except Exception as exc:
            logger.warning("yfinance .info failed for %s: %s", ticker, exc)
            return {}
