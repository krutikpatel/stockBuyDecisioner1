"""
Backtest CLI entry point.

Usage (from backend/ directory):

  # Full run, all 20 tickers, Phase 3 (default)
  python -m backtest.run_backtest

  # Quick smoke test — 2 tickers, 1 year, Phase 1
  python -m backtest.run_backtest --tickers AAPL,MSFT --start 2022-01-01 --end 2023-01-01 --phase 1

  # Force re-download of all cached data
  python -m backtest.run_backtest --force-refresh

  # Track as a named experiment
  python -m backtest.run_backtest --experiment-id my_experiment_01

  # Run walk-forward validation instead of a standard backtest
  python -m backtest.run_backtest --walk-forward --tickers AAPL,MSFT --start 2019-01-01 --end 2024-01-01

Options:
  --tickers        Comma-separated ticker list (default: all 20 in config)
  --start          Backtest start date  YYYY-MM-DD (default: config.BACKTEST_START)
  --end            Backtest end date    YYYY-MM-DD (default: config.BACKTEST_END)
  --phase          1, 2, or 3 (default: 3)
  --risk-profile   conservative | moderate | aggressive (default: moderate)
  --force-refresh  Re-download all data even if cache exists
  --output-dir     Directory for results (default: backtest/results/)
  --no-report      Skip HTML report generation (still writes CSVs)
  --algo-config    Path to a custom algo_config.json (default: backend/algo_config.json)
  --experiment-id  Name this run for experiment tracking (writes manifest + summary)
  --walk-forward   Run walk-forward validation instead of a standard backtest
  --train-weeks    Walk-forward training window in weeks (default: 104)
  --test-weeks     Walk-forward test window in weeks (default: 26)
  --step-weeks     Walk-forward fold step in weeks (default: 13)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the backend/ package root is on sys.path when running as a module
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.algo_config import AlgoConfig, reset_algo_config
from backtest.config import (
    BACKTEST_START, BACKTEST_END, DEFAULT_RISK_PROFILE,
    DEFAULT_PHASE, RESULTS_DIR,
)
from backtest.data_loader import load_all_data
from backtest.runner import run_backtest
from backtest.outcome import attach_outcomes
from backtest.metrics import build_all_horizons_metrics
from backtest.report import generate_report
from backtest.experiment_tracker import ExperimentTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_backtest")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the stock-decision-tool backtesting framework.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--tickers",       default=None,
                   help="Comma-separated list of tickers (overrides config)")
    p.add_argument("--start",         default=BACKTEST_START,
                   help=f"Backtest start date (default: {BACKTEST_START})")
    p.add_argument("--end",           default=BACKTEST_END,
                   help=f"Backtest end date (default: {BACKTEST_END})")
    p.add_argument("--phase",         default=DEFAULT_PHASE, type=int, choices=[1, 2, 3],
                   help="Phase 1=technical-only, 2=+regime, 3=+fundamentals (default: 3)")
    p.add_argument("--risk-profile",  default=DEFAULT_RISK_PROFILE,
                   choices=["conservative", "moderate", "aggressive"],
                   help=f"Risk profile (default: {DEFAULT_RISK_PROFILE})")
    p.add_argument("--force-refresh", action="store_true",
                   help="Re-download all data even if cache exists")
    p.add_argument("--output-dir",    default=RESULTS_DIR,
                   help=f"Output directory (default: {RESULTS_DIR})")
    p.add_argument("--no-report",     action="store_true",
                   help="Skip HTML report generation")
    p.add_argument("--algo-config",   default=None,
                   help="Path to a custom algo_config.json (default: backend/algo_config.json)")
    p.add_argument("--experiment-id", default=None,
                   help="Tag this run with an experiment ID for tracking")
    p.add_argument("--walk-forward",  action="store_true",
                   help="Run walk-forward validation instead of a standard backtest")
    p.add_argument("--train-weeks",   default=104, type=int,
                   help="Walk-forward training window in weeks (default: 104)")
    p.add_argument("--test-weeks",    default=26,  type=int,
                   help="Walk-forward test window in weeks (default: 26)")
    p.add_argument("--step-weeks",    default=13,  type=int,
                   help="Walk-forward fold step in weeks (default: 13)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None

    # ── Load custom algo config if provided ───────────────────────────────
    algo_cfg: AlgoConfig | None = None
    if args.algo_config:
        config_path = Path(args.algo_config).resolve()
        logger.info("Loading custom algo config from: %s", config_path)
        reset_algo_config()
        algo_cfg = AlgoConfig.from_file(str(config_path))

    logger.info("=== Stock Decision Tool Backtest ===")
    logger.info("Phase: %d | Start: %s | End: %s", args.phase, args.start, args.end)
    if tickers:
        logger.info("Tickers: %s", ", ".join(tickers))
    if algo_cfg:
        logger.info("Custom algo config: %s", args.algo_config)

    # ── Step 1: Load / download data ──────────────────────────────────────
    logger.info("Step 1: Loading data…")
    data = load_all_data(force_refresh=args.force_refresh, extra_tickers=tickers)

    # ── Walk-forward shortcut ──────────────────────────────────────────────
    if args.walk_forward:
        from backtest.walk_forward import WalkForwardValidator
        import json

        logger.info("Walk-forward mode: train=%dwk, test=%dwk, step=%dwk",
                    args.train_weeks, args.test_weeks, args.step_weeks)
        validator = WalkForwardValidator(
            train_window_weeks=args.train_weeks,
            test_window_weeks=args.test_weeks,
            step_weeks=args.step_weeks,
            phase=args.phase,
            risk_profile=args.risk_profile,
            algo_config=algo_cfg,
        )
        result = validator.run(
            data=data, tickers=tickers,
            start=args.start, end=args.end,
        )
        logger.info(
            "Walk-forward complete: %d folds, consistency=%.3f",
            len(result.folds), result.oos_vs_is_consistency,
        )
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output = {
            "summary":               result.summary,
            "oos_vs_is_consistency": result.oos_vs_is_consistency,
            "folds": [
                {
                    "fold_index":     f.fold_index,
                    "train_start":    f.train_start,  "train_end":    f.train_end,
                    "test_start":     f.test_start,   "test_end":     f.test_end,
                    "is_win_rate":    f.is_win_rate,  "oos_win_rate": f.oos_win_rate,
                    "is_avg_return":  f.is_avg_return, "oos_avg_return": f.oos_avg_return,
                }
                for f in result.folds
            ],
        }
        wf_path = out_dir / "walk_forward_results.json"
        wf_path.write_text(json.dumps(output, indent=2))
        logger.info("Walk-forward results written to %s", wf_path)
        return

    # ── Step 2: Run backtest ──────────────────────────────────────────────
    logger.info("Step 2/5: Running backtest loop…")

    # Start experiment tracking if requested
    tracker: ExperimentTracker | None = None
    if args.experiment_id:
        tracker = ExperimentTracker()
        tracker.start_experiment(
            experiment_id=args.experiment_id,
            cli_args=vars(args),
            algo_config_path=args.algo_config,
        )
        logger.info("Experiment tracking started: %s", args.experiment_id)

    signals = run_backtest(
        data=data,
        tickers=tickers,
        start=args.start,
        end=args.end,
        risk_profile=args.risk_profile,
        phase=args.phase,
        force_refresh=args.force_refresh,
        algo_config=algo_cfg,
    )

    if not signals:
        logger.error("No signals generated — check data or date range.")
        sys.exit(1)

    # ── Step 3: Attach outcomes ───────────────────────────────────────────
    logger.info("Step 3/5: Attaching forward returns…")
    signals = attach_outcomes(signals, data["prices"])

    resolved = sum(1 for s in signals if s.get("forward_return") is not None)
    logger.info("Outcomes resolved: %d / %d signals", resolved, len(signals))

    # ── Step 4: Compute metrics ───────────────────────────────────────────
    logger.info("Step 4/5: Computing metrics…")
    all_metrics = build_all_horizons_metrics(signals)

    # Save experiment results if tracking
    if tracker and args.experiment_id:
        tracker.save_results(args.experiment_id, all_metrics)

    # ── Step 5: Generate report ───────────────────────────────────────────
    if not args.no_report:
        logger.info("Step 5/5: Generating report → %s/", args.output_dir)
        generate_report(
            all_metrics=all_metrics,
            signals=signals,
            output_dir=args.output_dir,
            phase=args.phase,
        )
    else:
        import pandas as pd
        from pathlib import Path as _Path
        out = _Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(signals).to_csv(out / "signals_with_outcomes.csv", index=False)
        logger.info("Signals CSV written to %s/signals_with_outcomes.csv", args.output_dir)

    logger.info("=== Backtest complete ===")


if __name__ == "__main__":
    main()
