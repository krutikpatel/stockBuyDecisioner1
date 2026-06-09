from __future__ import annotations

import csv
import pickle
from pathlib import Path
from typing import Any

from codex_backed.data.bars import normalize_price_frame


class DataLoadError(RuntimeError):
    """Raised when historical backtest data cannot be loaded."""


def load_price_bars(prices_cache_path: Path, tickers: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    if not prices_cache_path.exists():
        raise DataLoadError(f"Price cache not found: {prices_cache_path}")
    with prices_cache_path.open("rb") as fh:
        prices = pickle.load(fh)
    if not isinstance(prices, dict):
        raise DataLoadError(f"Price cache must contain a dict: {prices_cache_path}")

    wanted = {ticker.upper() for ticker in tickers} if tickers else None
    bars_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for ticker, df in prices.items():
        ticker_upper = str(ticker).upper()
        if wanted is not None and ticker_upper not in wanted and ticker_upper not in {"SPY", "QQQ"}:
            continue
        bars = normalize_price_frame(df)
        if bars:
            bars_by_ticker[ticker_upper] = bars
    return bars_by_ticker


def load_feature_rows(
    feature_csv_path: Path,
    *,
    tickers: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    horizons: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not feature_csv_path.exists():
        raise DataLoadError(f"Feature CSV not found: {feature_csv_path}")

    wanted = {ticker.upper() for ticker in tickers} if tickers else None
    rows: list[dict[str, Any]] = []
    with feature_csv_path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            ticker = raw.get("ticker", "").upper()
            date = str(raw.get("date", ""))[:10]
            horizon = raw.get("horizon")
            if wanted is not None and ticker not in wanted:
                continue
            if start is not None and date < start:
                continue
            if end is not None and date > end:
                continue
            if horizons is not None and horizon not in horizons:
                continue
            rows.append(_normalize_feature_row(raw))
    return rows


def group_feature_rows_by_ticker(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["ticker"], []).append(row)
    for ticker_rows in grouped.values():
        ticker_rows.sort(key=lambda item: (item["date"], item["horizon"]))
    return grouped


def _normalize_feature_row(raw: dict[str, str]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None or value == "":
            row[key] = None
            continue
        if key in {"ticker", "date", "horizon", "decision", "market_regime", "archetype", "trend", "engine", "setup", "strategy_name"}:
            row[key] = value
            continue
        row[key] = _coerce_number(value)

    row["ticker"] = str(row.get("ticker", "")).upper()
    row["date"] = str(row.get("date", ""))[:10]
    row["price"] = row.get("price")
    row["market_regime"] = row.get("market_regime") or "SIDEWAYS_CHOPPY"
    row["selected_setup"] = row.get("setup")
    row["trend_label"] = row.get("trend") or "sideways"
    row["rsi14"] = row.get("rsi")

    row.setdefault("sma20_relative", 0.0)
    row.setdefault("perf_1w", None)
    row.setdefault("volume_dryup_ratio", None)
    row.setdefault("updown_volume_ratio", None)
    row.setdefault("dist_from_20d_high", None)
    row.setdefault("breakout_volume_multiple", None)
    return row


def _coerce_number(value: str) -> Any:
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number
