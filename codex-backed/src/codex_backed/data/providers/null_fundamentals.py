from __future__ import annotations

from datetime import date

from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.capabilities import ProviderCapabilities

_NULL_CAPABILITIES = ProviderCapabilities(
    supports_prices=False,
    supports_fundamentals=False,
    fundamentals_fields=frozenset(),
    history_start_date=None,
    price_realtime=False,
    rate_limit_per_minute=0,
)


class NullFundamentalsProvider:
    """FundamentalsProvider that returns all-None snapshots.

    Used in legacy_yfinance mode so the pipeline runs unchanged while
    preserving today's behaviour of every fundamental field being None.
    prefetch_batch is a deliberate no-op; get_snapshot never performs I/O.
    """

    name = "null"
    capabilities: ProviderCapabilities = _NULL_CAPABILITIES

    def prefetch_batch(
        self,
        tickers: list[str],
        date_range: tuple[date, date],
    ) -> None:
        """No-op — nothing to prefetch for the null provider."""

    def get_snapshot(
        self,
        ticker: str,
        as_of_date: date,
    ) -> FundamentalsSnapshot:
        """Return an all-None snapshot without performing any I/O."""
        return FundamentalsSnapshot(ticker=ticker, as_of_date=as_of_date.isoformat())

    def signature(self) -> str:
        """Stable cache-key component identifying this provider's identity and config."""
        return "null"
