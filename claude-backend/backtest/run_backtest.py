"""Backtest runner with --two-path flag support.

Design:
  All price data is sliced to the sampled date before computing technicals and
  regime — no lookahead bias in technical signals.

  Known limitation: fundamental/valuation data is fetched as-of today (yfinance
  doesn't expose point-in-time fundamentals). Quality-gate and avoid-side signals
  driven by fundamentals therefore carry look-ahead. Technical signals on the
  buy-side path are clean.

Usage:
    python -m backtest.run_backtest --two-path --tickers NVDA,AAPL,MSFT \\
        --start 2022-01-01 --end 2024-01-01
    python -m backtest.run_backtest --two-path --tickers loser \\
        --start 2022-01-01 --end 2024-01-01
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_RESULTS_DIR = Path(__file__).parent / "results"
_LOSER_UNIVERSE = Path(__file__).parent / "loser_universe.json"

# Forward-return horizons in trading bars (index steps in a daily OHLCV frame)
_HORIZONS: dict[str, int] = {
    "20d": 20,   # ~1 calendar month
    "60d": 60,   # ~3 calendar months
}


def _load_loser_universe() -> list[str]:
    with open(_LOSER_UNIVERSE) as f:
        return json.load(f)


def _forward_return(df: pd.DataFrame, entry_date: pd.Timestamp, bars: int) -> float | None:
    """Return % return over `bars` trading days starting at entry_date.

    Uses the full (unsliced) price DataFrame so future prices are available.
    entry_date itself is the entry bar — exit is entry_idx + bars.
    """
    try:
        entry_idx = df.index.searchsorted(entry_date, side="left")
        if entry_idx >= len(df):
            return None
        exit_idx = entry_idx + bars
        if exit_idx >= len(df):
            return None                          # not enough future data
        entry_price = float(df["Close"].iloc[entry_idx])
        exit_price = float(df["Close"].iloc[exit_idx])
        if entry_price == 0:
            return None
        return (exit_price - entry_price) / entry_price
    except Exception:
        return None


def _sampled_trading_dates(
    df: pd.DataFrame,
    start: str,
    end: str,
    freq_bars: int,
) -> list[pd.Timestamp]:
    """Return every freq_bars-th trading day within [start, end]."""
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    window = df.index[(df.index >= start_ts) & (df.index <= end_ts)]
    return list(window[::freq_bars])


def run_two_path_backtest(
    tickers: list[str],
    start: str,
    end: str,
    freq_bars: int = 20,
) -> list[dict]:
    """Run two-path backtest with date-sliced data (no technical lookahead).

    Args:
        tickers:   List of tickers to backtest.
        start:     First sample date (ISO string).
        end:       Last sample date (ISO string).
        freq_bars: Sampling interval in trading bars (default 20 ≈ monthly).

    Returns:
        List of result dicts, one per (ticker, date).
    """
    from app.features.feature_builder import build_feature_snapshot
    from app.providers.earnings_provider import get_earnings_data
    from app.providers.fundamental_provider import get_fundamental_data, get_valuation_data
    from app.providers.market_data_provider import get_history, get_market_data
    from app.services.market_regime_service import classify_regime
    from app.services.stock_archetype_service import classify_and_attach
    from app.services.technical_analysis_service import compute_technicals
    from two_path_engine.engine import TwoPathEngine

    engine = TwoPathEngine()
    rows: list[dict] = []

    # Shared market benchmarks — fetched once, sliced per date
    logger.info("Fetching SPY and QQQ history …")
    spy_full = get_history("SPY", period="max", interval="1d")
    qqq_full = get_history("QQQ", period="max", interval="1d")

    for ticker in tickers:
        logger.info("Processing %s", ticker)

        # --- Fetch all ticker data once ---
        try:
            df_full = get_history(ticker, period="max", interval="1d")
        except Exception as exc:
            logger.warning("Price fetch failed for %s: %s", ticker, exc)
            continue

        if df_full.empty or len(df_full) < 100:
            logger.warning("Insufficient price data for %s", ticker)
            continue

        try:
            mkt = get_market_data(ticker)
            fund = get_fundamental_data(ticker)
            val = get_valuation_data(ticker, market_cap=mkt.market_cap)
            earn = get_earnings_data(ticker)
        except Exception as exc:
            logger.warning("Fundamental fetch failed for %s: %s", ticker, exc)
            continue

        # Archetype classification — uses current fundamentals (known limitation)
        classify_and_attach(fund, val)

        # --- Sample dates within the backtest window ---
        dates = _sampled_trading_dates(df_full, start, end, freq_bars)
        if not dates:
            logger.warning("No trading dates found for %s in [%s, %s]", ticker, start, end)
            continue

        for actual_date in dates:
            # Slice to actual_date — no lookahead in price-derived signals
            df_slice = df_full.loc[df_full.index <= actual_date]
            spy_slice = spy_full.loc[spy_full.index <= actual_date]
            qqq_slice = qqq_full.loc[qqq_full.index <= actual_date]

            if len(df_slice) < 100:
                continue

            try:
                technicals = compute_technicals(df_slice, spy_df=spy_slice)
                regime = classify_regime(spy_slice, qqq_slice)

                price = float(df_slice["Close"].iloc[-1])
                snapshot = build_feature_snapshot(
                    ticker=ticker,
                    price=price,
                    technicals=technicals,
                    fundamentals=fund,
                    valuation=val,
                    earnings=earn,
                    market_data=mkt,
                    regime_assessment=regime,
                    as_of_date=actual_date.strftime("%Y-%m-%d"),
                )

                decision = engine.analyze_snapshot(snapshot)

                # Forward returns from FULL df (future prices available here)
                row: dict = {
                    "ticker": ticker,
                    "date": actual_date.strftime("%Y-%m-%d"),
                    "path_taken": decision.path_taken,
                    "decision": decision.decision,
                    "score": round(decision.score, 1),
                }
                for label, bars in _HORIZONS.items():
                    fwd = _forward_return(df_full, actual_date, bars)
                    row[f"fwd_return_{label}"] = (
                        round(fwd * 100, 2) if fwd is not None else None
                    )
                row["reasons"] = "; ".join(decision.reasons[:5])  # top 5 for CSV readability
                rows.append(row)

            except Exception as exc:
                logger.debug("Error on %s @ %s: %s", ticker, actual_date, exc)

    return rows


def _save_results(rows: list[dict], output_path: Path) -> None:
    if not rows:
        logger.warning("No results to save.")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Saved %d rows to %s", len(rows), output_path)


def _print_summary(rows: list[dict]) -> None:
    if not rows:
        return

    by_decision: dict[str, list[dict]] = {}
    for r in rows:
        by_decision.setdefault(r["decision"], []).append(r)

    print("\n=== Two-Path Backtest Summary ===")
    print(f"  Total observations: {len(rows)}")
    print()
    header = f"  {'Decision':<12}  {'n':>5}  {'avg 20d':>8}  {'avg 60d':>8}  {'win% 20d':>9}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for decision in ("BUY", "WAIT", "AVOID", "WATCHLIST"):
        group = by_decision.get(decision, [])
        if not group:
            continue
        fwd_20 = [r["fwd_return_20d"] for r in group if r.get("fwd_return_20d") is not None]
        fwd_60 = [r["fwd_return_60d"] for r in group if r.get("fwd_return_60d") is not None]
        avg_20 = sum(fwd_20) / len(fwd_20) if fwd_20 else float("nan")
        avg_60 = sum(fwd_60) / len(fwd_60) if fwd_60 else float("nan")
        win_20 = (sum(1 for x in fwd_20 if x > 0) / len(fwd_20) * 100) if fwd_20 else float("nan")
        print(
            f"  {decision:<12}  {len(group):>5}  {avg_20:>+7.2f}%  {avg_60:>+7.2f}%  {win_20:>8.1f}%"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-path backtest runner")
    parser.add_argument("--two-path", action="store_true", required=True,
                        help="Use the two-path engine (required)")
    parser.add_argument("--tickers", type=str, default=None,
                        help="Comma-separated tickers, or 'loser' for loser_universe.json")
    parser.add_argument("--start", type=str, default="2022-01-01",
                        help="Backtest start date (ISO, default: 2022-01-01)")
    parser.add_argument("--end", type=str, default="2024-01-01",
                        help="Backtest end date (ISO, default: 2024-01-01)")
    parser.add_argument("--freq", type=int, default=20,
                        help="Sampling frequency in trading bars (default: 20 ≈ monthly)")
    args = parser.parse_args()

    if args.tickers and args.tickers.lower() == "loser":
        tickers = _load_loser_universe()
    elif args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        parser.error("--tickers is required")

    logger.info(
        "Two-path backtest: %s tickers, %s–%s, freq=%d bars",
        len(tickers), args.start, args.end, args.freq,
    )
    rows = run_two_path_backtest(tickers, args.start, args.end, freq_bars=args.freq)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = _RESULTS_DIR / f"two_path_{ts}.csv"
    _save_results(rows, out)
    _print_summary(rows)


if __name__ == "__main__":
    main()
