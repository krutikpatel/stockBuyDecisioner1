from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_backed.analyze import AnalyzeOptions, run_watchlist_analysis
from codex_backed.backtest.runner import BacktestOptions, run_lifecycle_backtest
from codex_backed.config.loader import ConfigError, load_config_bundle, validate_config_bundle
from codex_backed.results import create_run_paths, write_manifest


DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "results"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-backed",
        description="CLI trade lifecycle engine with separate entry and exit optimization.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in [
        ("validate-config", "Validate JSON config files."),
        ("analyze", "Analyze today's watchlist using fresh yfinance data."),
        ("backtest", "Run lifecycle backtest and write result artifacts."),
        ("optimize-entry", "Optimize entry rules with a fixed exit policy."),
        ("optimize-exit", "Optimize exit rules with fixed entry signals."),
        ("report", "Generate or inspect a run report."),
        ("compare", "Compare two result runs."),
    ]:
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument(
            "--config-dir",
            default=str(DEFAULT_CONFIG_DIR),
            help=f"Directory containing JSON configs (default: {DEFAULT_CONFIG_DIR})",
        )
        if command in {"analyze", "backtest", "optimize-entry", "optimize-exit"}:
            sub.add_argument(
                "--output-dir",
                default=str(DEFAULT_OUTPUT_DIR),
                help=f"Directory for run results (default: {DEFAULT_OUTPUT_DIR})",
            )
            sub.add_argument("--run-id", default=None, help="Optional explicit run id.")
        if command == "analyze":
            sub.add_argument("--tickers", default=None, help="Comma-separated ticker list. Defaults to watchlist_config.json.")
            sub.add_argument("--horizons", default=None, help="Comma-separated horizons. Defaults to watchlist_config.json.")
            sub.add_argument("--period", default=None, help="yfinance lookback period. Defaults to watchlist_config.json.")
            sub.add_argument("--interval", default=None, help="yfinance interval. Defaults to watchlist_config.json.")
        if command == "backtest":
            sub.add_argument("--tickers", default=None, help="Comma-separated ticker list.")
            sub.add_argument("--start", default=None, help="Backtest start date YYYY-MM-DD.")
            sub.add_argument("--end", default=None, help="Backtest end date YYYY-MM-DD.")
            sub.add_argument("--workers", default=None, type=int, help="Worker process count. Use 1 for debug.")
            sub.add_argument(
                "--feature-source",
                choices=["native", "parent_csv"],
                default=None,
                help="Feature source override. Defaults to backtest_config.json.",
            )
            sub.add_argument("--force-refresh", action="store_true", help="Rebuild native feature cache for this run.")
            sub.add_argument("--rebuild-feature-cache", action="store_true", help="Rebuild native feature cache for this run.")
            sub.add_argument("--no-report", action="store_true", help="Skip HTML report generation.")
        if command in {"report", "compare"}:
            sub.add_argument("--run-id", default=None, help="Result run id to inspect.")
        if command == "compare":
            sub.add_argument("--baseline-run-id", default=None, help="Baseline run id.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_dir = Path(args.config_dir).resolve()

    try:
        bundle = load_config_bundle(config_dir)
        validate_config_bundle(bundle)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate-config":
        print(json.dumps({"status": "ok", "config_dir": str(config_dir)}, indent=2))
        return 0

    if args.command == "analyze":
        output_dir = Path(args.output_dir).resolve()
        paths = create_run_paths(output_dir, run_id=args.run_id)
        write_manifest(
            paths,
            command=args.command,
            cli_args=vars(args),
            config_dir=config_dir,
        )
        tickers = [ticker.strip().upper() for ticker in args.tickers.split(",")] if args.tickers else None
        horizons = [horizon.strip() for horizon in args.horizons.split(",")] if args.horizons else None
        try:
            result = run_watchlist_analysis(
                bundle,
                paths,
                AnalyzeOptions(
                    tickers=tickers,
                    horizons=horizons,
                    period=args.period,
                    interval=args.interval,
                ),
            )
        except Exception as exc:
            print(f"Analyze error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps({"status": "ok", **result}, indent=2))
        return 0

    if args.command == "backtest":
        output_dir = Path(args.output_dir).resolve()
        paths = create_run_paths(output_dir, run_id=args.run_id)
        write_manifest(
            paths,
            command=args.command,
            cli_args=vars(args),
            config_dir=config_dir,
        )
        tickers = [ticker.strip().upper() for ticker in args.tickers.split(",")] if args.tickers else None
        try:
            result = run_lifecycle_backtest(
                bundle,
                paths,
                BacktestOptions(
                    tickers=tickers,
                    start=args.start,
                    end=args.end,
                    workers=args.workers,
                    feature_source=args.feature_source,
                    force_refresh=args.force_refresh,
                    rebuild_feature_cache=args.rebuild_feature_cache,
                    no_report=args.no_report,
                ),
            )
        except Exception as exc:
            print(f"Backtest error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps({"status": "ok", **result}, indent=2))
        return 0

    if args.command in {"optimize-entry", "optimize-exit"}:
        output_dir = Path(args.output_dir).resolve()
        paths = create_run_paths(output_dir, run_id=args.run_id)
        write_manifest(
            paths,
            command=args.command,
            cli_args=vars(args),
            config_dir=config_dir,
        )
        print(
            json.dumps(
                {
                    "status": "created_run",
                    "command": args.command,
                    "run_id": paths.run_id,
                    "run_dir": str(paths.run_dir),
                    "note": "Optimization command is scaffolded but not implemented yet.",
                },
                indent=2,
            )
        )
        return 0

    print(
        json.dumps(
            {
                "status": "not_implemented",
                "command": args.command,
                "note": "This command is scaffolded but not implemented yet.",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
