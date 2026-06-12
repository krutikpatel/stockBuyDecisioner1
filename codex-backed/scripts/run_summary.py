"""Compact metrics summary for a backtest run.

Usage:
    claude-backend/.venv/bin/python codex-backed/scripts/run_summary.py codex-backed/results/<run-id>

Prints the ~10 numbers a tuning iteration actually uses, in a tight block.
Replaces full metrics.json dumps that wasted ~200 tokens per iteration.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def fmt(val: float | None, width: int = 7) -> str:
    if val is None:
        return f"{'-':>{width}}"
    return f"{val:>{width}.3f}"


def main(run_dir: str) -> int:
    path = Path(run_dir) / "metrics.json"
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    m = json.loads(path.read_text())
    o = m["overall"]
    print(
        f"overall  n={o['count']:>4}  avg={fmt(o['avg_return_pct'])}  "
        f"med={fmt(o['median_return_pct'])}  wr={fmt(o['win_rate_pct'])}  "
        f"pf={fmt(o['profit_factor'])}"
    )
    for h in m.get("by_horizon", []):
        print(
            f"  {h['horizon']:<11} n={h['count']:>4}  avg={fmt(h['avg_return_pct'])}  "
            f"med={fmt(h['median_return_pct'])}  wr={fmt(h['win_rate_pct'])}  "
            f"pf={fmt(h['profit_factor'])}"
        )
    for e in m.get("by_exit_reason", []):
        print(
            f"  {e['exit_reason']:<22} n={e['count']:>4}  "
            f"avg={fmt(e['avg_return_pct'])}  wr={fmt(e['win_rate_pct'])}"
        )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: run_summary.py <run-dir>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
