"""
CLI entry point for the backtest engine.

Usage:
    cd backend
    source .venv/bin/activate

    # Quick smoke test (2 tickers, 1 year)
    python -m backtest.run_backtest --tickers AAPL SPY --start 2025-05-01

    # Full 2-year backtest (all 20 tickers, ~15–30 min)
    python -m backtest.run_backtest

    # Custom config
    python -m backtest.run_backtest --tickers AAPL MSFT NVDA --start 2024-05-01 --refresh-cache
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure backend/ is on the path when run as `python -m backtest.run_backtest`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backtest")

from backtest.config import (
    BACKTEST_TICKERS, BACKTEST_START, BACKTEST_END,
    DEFAULT_RISK_PROFILE, HORIZONS, RESULTS_DIR,
)
from backtest.data_loader import load_all_data
from backtest.runner import run_backtest
from backtest.outcome import attach_outcomes
from backtest.metrics import build_metrics
from backtest.report import save_csvs, save_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stock Decision Tool — Backtest Engine")
    p.add_argument("--tickers", nargs="+", default=None,
                   help="Ticker symbols to test (default: all 20 configured tickers)")
    p.add_argument("--start", default=None,
                   help="Backtest start date YYYY-MM-DD (default: 2024-05-06)")
    p.add_argument("--end", default=None,
                   help="Backtest end date YYYY-MM-DD (default: 2026-05-04)")
    p.add_argument("--risk-profile", default=DEFAULT_RISK_PROFILE,
                   choices=["conservative", "moderate", "aggressive"],
                   help="Risk profile for recommendations (default: moderate)")
    p.add_argument("--refresh-cache", action="store_true",
                   help="Force re-fetch of all data from yfinance (ignores cache)")
    p.add_argument("--no-report", action="store_true",
                   help="Skip HTML/JSON report generation")
    return p.parse_args()


def print_summary(metrics_by_horizon: dict) -> None:
    """Print a concise summary table to stdout."""
    print("\n" + "=" * 72)
    print("BACKTEST SUMMARY")
    print("=" * 72)

    for horizon in HORIZONS:
        m = metrics_by_horizon.get(horizon, {})
        overall = m.get("overall_stats", {})
        sim = m.get("portfolio_simulation", {})
        by_decision = m.get("by_decision", [])

        label = horizon.replace("_", "-").upper()
        print(f"\n{'─' * 72}")
        print(f"  {label} HORIZON")
        print(f"  Total signals: {m.get('total_signals', 0)} | Resolved: {m.get('resolved_signals', 0)}")

        wr = overall.get("overall_win_rate_pct")
        ar = overall.get("avg_return_pct")
        ae = overall.get("avg_excess_vs_spy_pct")
        corr = overall.get("score_return_correlation")

        print(f"  Overall win rate: {wr:.1f}%  |  Avg return: {ar:+.2f}%  |  Avg vs SPY: {ae:+.2f}%"
              if (wr and ar is not None and ae is not None) else "  No resolved signals.")
        if corr is not None:
            print(f"  Score↔Return correlation: {corr:.3f}")

        if by_decision:
            print(f"\n  {'Decision':<22} {'Count':>6} {'Avg Return':>12} {'Win Rate':>10} {'vs SPY':>10}")
            print(f"  {'-'*22} {'-'*6} {'-'*12} {'-'*10} {'-'*10}")
            for row in by_decision:
                exc = row.get("avg_excess_vs_spy_pct")
                exc_str = f"{exc:+.2f}%" if exc is not None else "N/A"
                print(
                    f"  {row['decision']:<22} {row['count']:>6} "
                    f"  {row['avg_return_pct']:>+8.2f}%  {row['win_rate_pct']:>7.1f}%  {exc_str:>10}"
                )

        sim_trades = sim.get("total_trades", 0)
        if sim_trades > 0:
            alpha = sim.get("alpha_pct")
            alpha_str = f"{alpha:+.2f}%" if alpha is not None else "N/A"
            print(f"\n  Buy signals simulated: {sim_trades} trades | Alpha vs SPY: {alpha_str}")

    print("\n" + "=" * 72)
    print(f"Results saved to: {Path(RESULTS_DIR).resolve()}/")
    print("=" * 72 + "\n")


def main() -> None:
    args = parse_args()

    tickers = args.tickers or BACKTEST_TICKERS
    print(f"\nStock Decision Tool — Backtest Engine")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Date range: {args.start or BACKTEST_START} → {args.end or BACKTEST_END}")
    print(f"Risk profile: {args.risk_profile}")

    # Step 1: Load / fetch data (pass user tickers so extras get fetched)
    data = load_all_data(force_refresh=args.refresh_cache, extra_tickers=tickers)

    # Step 2: Run backtest
    signals = run_backtest(
        data=data,
        tickers=tickers,
        start=args.start,
        end=args.end,
        risk_profile=args.risk_profile,
    )

    if not signals:
        print("No signals generated. Check that tickers have sufficient price history.")
        sys.exit(1)

    # Step 3: Attach outcomes
    print("\nComputing forward returns...")
    signals = attach_outcomes(signals, data["prices"])

    # Step 4: Build metrics
    print("Aggregating metrics...")
    metrics_by_horizon = {
        h: build_metrics(signals, h) for h in HORIZONS
    }

    # Step 5: Save CSV files
    save_csvs(signals, metrics_by_horizon)

    # Step 6: Generate HTML + JSON report
    if not args.no_report:
        save_report(signals, metrics_by_horizon)

    # Step 7: Print summary
    print_summary(metrics_by_horizon)


if __name__ == "__main__":
    main()
