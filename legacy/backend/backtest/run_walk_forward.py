"""
Walk-forward validation CLI entry point.

Usage (from backend/ directory):

  # 2-year train / 6-month test / 3-month step on 3 tickers
  python -m backtest.run_walk_forward --tickers AAPL,MSFT,NVDA \\
      --start 2019-01-01 --end 2024-01-01

  # Custom windows
  python -m backtest.run_walk_forward --train-weeks 52 --test-weeks 13 --step-weeks 13

Options:
  --tickers       Comma-separated ticker list (default: full BACKTEST_TICKERS)
  --start         Overall start date YYYY-MM-DD
  --end           Overall end date YYYY-MM-DD
  --train-weeks   Training window in weeks (default: 104)
  --test-weeks    Test window in weeks (default: 26)
  --step-weeks    Fold step in weeks (default: 13)
  --horizon       short_term | medium_term | long_term (default: short_term)
  --phase         1 / 2 / 3 (default: 3)
  --risk-profile  conservative | moderate | aggressive (default: moderate)
  --output-dir    Directory to write walk_forward_results.json
  --algo-config   Path to a custom algo_config.json
  --force-refresh Re-download all cached data
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.algo_config import AlgoConfig, reset_algo_config
from backtest.config import BACKTEST_START, BACKTEST_END, DEFAULT_RISK_PROFILE, DEFAULT_PHASE, RESULTS_DIR
from backtest.data_loader import load_all_data
from backtest.walk_forward import WalkForwardValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_walk_forward")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Walk-forward validation for the stock decision tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--tickers",       default=None,
                   help="Comma-separated tickers (overrides config)")
    p.add_argument("--start",         default=BACKTEST_START,
                   help=f"Overall start date (default: {BACKTEST_START})")
    p.add_argument("--end",           default=BACKTEST_END,
                   help=f"Overall end date (default: {BACKTEST_END})")
    p.add_argument("--train-weeks",   default=104, type=int,
                   help="Training window in weeks (default: 104)")
    p.add_argument("--test-weeks",    default=26,  type=int,
                   help="Test window in weeks (default: 26)")
    p.add_argument("--step-weeks",    default=13,  type=int,
                   help="Step between folds in weeks (default: 13)")
    p.add_argument("--horizon",       default="short_term",
                   choices=["short_term", "medium_term", "long_term"],
                   help="Horizon for IS/OOS metric comparison (default: short_term)")
    p.add_argument("--phase",         default=DEFAULT_PHASE, type=int, choices=[1, 2, 3])
    p.add_argument("--risk-profile",  default=DEFAULT_RISK_PROFILE,
                   choices=["conservative", "moderate", "aggressive"])
    p.add_argument("--output-dir",    default=RESULTS_DIR,
                   help=f"Output directory (default: {RESULTS_DIR})")
    p.add_argument("--algo-config",   default=None,
                   help="Path to a custom algo_config.json")
    p.add_argument("--force-refresh", action="store_true",
                   help="Re-download all data even if cache exists")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None

    algo_cfg: AlgoConfig | None = None
    if args.algo_config:
        reset_algo_config()
        algo_cfg = AlgoConfig.from_file(str(Path(args.algo_config).resolve()))
        logger.info("Custom algo config: %s", args.algo_config)

    logger.info("=== Walk-Forward Validation ===")
    logger.info(
        "Windows — train: %d wk, test: %d wk, step: %d wk | Phase: %d | Horizon: %s",
        args.train_weeks, args.test_weeks, args.step_weeks,
        args.phase, args.horizon,
    )
    if tickers:
        logger.info("Tickers: %s", ", ".join(tickers))

    logger.info("Loading data…")
    data = load_all_data(force_refresh=args.force_refresh, extra_tickers=tickers)

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
        horizon=args.horizon,
    )

    logger.info("=== Walk-Forward Complete ===")
    logger.info(
        "Folds: %d | OOS consistency: %.3f",
        len(result.folds), result.oos_vs_is_consistency,
    )
    if result.summary:
        for k, v in result.summary.items():
            if not isinstance(v, list):
                logger.info("  %-30s %s", k, v)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "summary":                 result.summary,
        "oos_vs_is_consistency":   result.oos_vs_is_consistency,
        "folds": [
            {
                "fold_index":    f.fold_index,
                "train_start":   f.train_start,
                "train_end":     f.train_end,
                "test_start":    f.test_start,
                "test_end":      f.test_end,
                "is_win_rate":   f.is_win_rate,
                "oos_win_rate":  f.oos_win_rate,
                "is_avg_return": f.is_avg_return,
                "oos_avg_return": f.oos_avg_return,
            }
            for f in result.folds
        ],
    }
    out_path = output_dir / "walk_forward_results.json"
    out_path.write_text(json.dumps(output, indent=2))
    logger.info("Results written to %s", out_path)


if __name__ == "__main__":
    main()
