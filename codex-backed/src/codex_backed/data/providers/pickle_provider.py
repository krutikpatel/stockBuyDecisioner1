from __future__ import annotations

from datetime import date
from pathlib import Path

from codex_backed.data.loader import load_price_bars
from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.capabilities import ProviderCapabilities

_DEFAULT_CAPABILITIES = ProviderCapabilities(
    supports_prices=True,
    supports_fundamentals=False,
    fundamentals_fields=frozenset(),
    history_start_date=None,
    price_realtime=False,
    rate_limit_per_minute=0,
)


class PickleProvider:
    """PriceProvider backed by the local prices.pkl cache.

    Wraps loader.load_price_bars.  SPY and QQQ are always included when any
    ticker filter is active (preserved from the legacy loader behaviour).
    fetch_live_batch is not supported; it raises ProviderError.
    """

    name = "pickle"

    def __init__(
        self,
        pickle_path: str | Path,
        capabilities: ProviderCapabilities = _DEFAULT_CAPABILITIES,
    ) -> None:
        self._path = Path(pickle_path)
        self.capabilities = capabilities
        self._cache: dict[str, list[dict]] | None = None

    def _load_all(self) -> dict[str, list[dict]]:
        """Load all tickers from the pickle, caching after first load."""
        if self._cache is None:
            # load_price_bars raises DataLoadError on missing / malformed file
            self._cache = load_price_bars(self._path)
        return self._cache

    def fetch_history_batch(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[dict]]:
        """Return date-filtered OHLCV bars for requested tickers.

        SPY and QQQ pass through unconditionally when present in the pickle
        (required for relative-strength calculations).
        """
        all_bars = self._load_all()
        start_iso = start.isoformat()
        end_iso = end.isoformat()
        wanted = {t.upper() for t in tickers}

        result: dict[str, list[dict]] = {}
        for ticker, bars in all_bars.items():
            if ticker not in wanted and ticker not in {"SPY", "QQQ"}:
                continue
            filtered = [b for b in bars if start_iso <= b["date"] <= end_iso]
            if filtered:
                result[ticker] = filtered
        return result

    def fetch_live_batch(
        self,
        tickers: list[str],
        period: str = "2y",
        interval: str = "1d",
    ) -> dict[str, list[dict]]:
        raise ProviderError(
            "PickleProvider is historical-only; use a live provider for fetch_live_batch"
        )
