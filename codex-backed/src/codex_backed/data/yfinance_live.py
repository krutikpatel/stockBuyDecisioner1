from __future__ import annotations

from typing import Any

from codex_backed.data.bars import normalize_price_frame


class LiveDataError(RuntimeError):
    """Raised when fresh market data cannot be loaded for analysis."""


def fetch_yfinance_bars(
    tickers: list[str],
    *,
    period: str = "2y",
    interval: str = "1d",
    auto_adjust: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch fresh OHLCV bars from yfinance and normalize them for codex-backed.

    This intentionally does not read or write codex-backed price/feature caches.
    """

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - exercised only in missing dependency environments
        raise LiveDataError("yfinance is required for codex-backed analyze") from exc

    unique_tickers = list(dict.fromkeys(ticker.upper() for ticker in tickers))
    if not unique_tickers:
        raise LiveDataError("No tickers requested")

    data = yf.download(
        tickers=unique_tickers,
        period=period,
        interval=interval,
        group_by="ticker",
        auto_adjust=auto_adjust,
        progress=False,
        threads=True,
    )
    if data is None or getattr(data, "empty", True):
        raise LiveDataError("yfinance returned no bars")

    bars_by_ticker: dict[str, list[dict[str, Any]]] = {}
    if len(unique_tickers) == 1:
        bars = normalize_price_frame(data)
        if bars:
            bars_by_ticker[unique_tickers[0]] = bars
        return bars_by_ticker

    for ticker in unique_tickers:
        try:
            frame = data[ticker]
        except KeyError:
            continue
        bars = normalize_price_frame(frame)
        if bars:
            bars_by_ticker[ticker] = bars
    return bars_by_ticker
