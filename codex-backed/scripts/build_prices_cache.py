"""One-shot script: download OHLCV for the backtest universe and write prices.pkl.

Run from repo root with the claude-backend venv:
    claude-backend/.venv/bin/python codex-backed/scripts/build_prices_cache.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_JSON = ROOT / "codex-backed/configs/backtest_ticker_universe_config.json"
OUT_PATH = ROOT / "codex-backed/cache/prices.pkl"

START = "2017-06-01"
END = "2026-01-01"
EXTRA = ["SPY", "QQQ"]
BATCH_SIZE = 40
PAUSE_BETWEEN_BATCHES_SEC = 1.5


def load_tickers() -> list[str]:
    with UNIVERSE_JSON.open() as fh:
        data = json.load(fh)
    tickers = [t.upper() for t in data["tickers"]]
    for sym in EXTRA:
        if sym not in tickers:
            tickers.append(sym)
    return tickers


def download_batch(tickers: list[str]) -> dict:
    df = yf.download(
        tickers=tickers,
        start=START,
        end=END,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    out: dict = {}
    if df is None or df.empty:
        return out
    if len(tickers) == 1:
        t = tickers[0]
        sub = df.dropna(how="all")
        if not sub.empty:
            out[t] = sub
        return out
    for t in tickers:
        try:
            sub = df[t].dropna(how="all")
        except KeyError:
            continue
        if sub.empty:
            continue
        out[t] = sub
    return out


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tickers = load_tickers()
    print(f"Universe size: {len(tickers)}")
    bars: dict = {}
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i : i + BATCH_SIZE]
        print(f"Batch {i // BATCH_SIZE + 1}: {batch[0]}..{batch[-1]} ({len(batch)} tickers)")
        retry = 0
        while retry < 3:
            try:
                batch_data = download_batch(batch)
                break
            except Exception as exc:  # broad: yfinance transient errors
                retry += 1
                print(f"  retry {retry} after error: {exc}", file=sys.stderr)
                time.sleep(5)
        else:
            print(f"  batch failed permanently, skipping", file=sys.stderr)
            continue
        bars.update(batch_data)
        print(f"  got {len(batch_data)}/{len(batch)} tickers, cumulative: {len(bars)}")
        time.sleep(PAUSE_BETWEEN_BATCHES_SEC)

    print(f"Total tickers with data: {len(bars)}")
    print(f"Writing pickle: {OUT_PATH}")
    with OUT_PATH.open("wb") as fh:
        pickle.dump(bars, fh)
    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"Wrote {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
