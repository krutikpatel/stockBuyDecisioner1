"""CLI entry point for the two-path decision engine.

Usage:
    python -m two_path_engine.cli NVDA
    python -m two_path_engine.cli INTC --verbose
    python -m two_path_engine.cli AAPL,MSFT,NVDA
"""
from __future__ import annotations

import sys
import textwrap
from typing import Sequence

from two_path_engine.engine import TwoPathDecision, TwoPathEngine


def _format_decision(d: TwoPathDecision, verbose: bool = False) -> str:
    path_label = (
        "QUALITY INTACT" if d.path_taken == "quality_intact" else "DETERIORATING BUSINESS"
    )
    lines = [
        f"{'=' * 60}",
        f"  {d.ticker}",
        f"  Path    : {path_label}",
        f"  Decision: {d.decision}",
        f"  Score   : {d.score:.0f}/100",
        f"{'=' * 60}",
    ]

    if d.gate_reasons:
        lines.append("Gate:")
        for r in d.gate_reasons:
            lines.append(f"  {r}")

    if d.reasons:
        lines.append("Signals:")
        for r in d.reasons:
            lines.append(f"  {r}")

    if d.missing_fields:
        lines.append(f"Missing data: {', '.join(d.missing_fields)}")

    if d.risk_plan and verbose:
        lines.append("Risk plan:")
        for k, v in d.risk_plan.items():
            lines.append(f"  {k}: {v}")

    return "\n".join(lines)


def run(args: Sequence[str] | None = None) -> None:
    argv = list(args or sys.argv[1:])
    if not argv:
        print("Usage: python -m two_path_engine.cli TICKER[,TICKER,...] [--verbose]")
        sys.exit(1)

    verbose = "--verbose" in argv or "-v" in argv
    argv = [a for a in argv if a not in ("--verbose", "-v")]

    tickers = [t.strip().upper() for t in argv[0].split(",") if t.strip()]
    if not tickers:
        print("No tickers provided.")
        sys.exit(1)

    engine = TwoPathEngine()
    for ticker in tickers:
        try:
            decision = engine.analyze(ticker)
            print(_format_decision(decision, verbose=verbose))
        except Exception as exc:
            print(f"ERROR analyzing {ticker}: {exc}")


if __name__ == "__main__":
    run()
