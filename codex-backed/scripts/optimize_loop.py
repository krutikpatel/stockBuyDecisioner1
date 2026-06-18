#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_DIR = Path(__file__).resolve().parents[1]
LOOP_DIR = REPO_DIR / "iterative_improvements_using_backtests"
DEFAULT_RESULTS_DIR = REPO_DIR / "results"
DEFAULT_HISTORY_PATH = LOOP_DIR / "history.jsonl"
DEFAULT_STATE_PATH = LOOP_DIR / "optimization_state.json"


def load_metrics(results_dir: Path, run_id: str) -> dict[str, Any]:
    path = results_dir / run_id / "metrics.json"
    if not path.exists():
        raise FileNotFoundError(f"metrics not found: {path}")
    return json.loads(path.read_text())


def build_summary(
    *,
    run_id: str,
    metrics: dict[str, Any],
    baseline_run_id: str | None = None,
    baseline_metrics: dict[str, Any] | None = None,
    change: str | None = None,
    decision: str | None = None,
    next_step: str | None = None,
) -> dict[str, Any]:
    summary = {
        "run": run_id,
        "change": change,
        "decision": decision,
        "next": next_step,
        "overall": _metric_block(metrics.get("overall", {})),
        "short_term": _horizon_block(metrics, "short_term"),
        "medium_term": _horizon_block(metrics, "medium_term"),
    }
    if baseline_run_id and baseline_metrics:
        summary["baseline_run"] = baseline_run_id
        summary["delta"] = {
            "overall": _delta_block(metrics.get("overall", {}), baseline_metrics.get("overall", {})),
            "short_term": _delta_block(_horizon_raw(metrics, "short_term"), _horizon_raw(baseline_metrics, "short_term")),
            "medium_term": _delta_block(_horizon_raw(metrics, "medium_term"), _horizon_raw(baseline_metrics, "medium_term")),
        }
    return summary


def append_history_entry(
    *,
    history_path: Path,
    iteration: int,
    summary: dict[str, Any],
    raw_metrics: dict[str, Any],
    raw_baseline_metrics: dict[str, Any] | None = None,
) -> None:
    entry = {
        "i": iteration,
        "run_id": summary["run"],
        "overall": _full_metric_block(raw_metrics.get("overall", {})),
        "short_term": _full_metric_block(_horizon_raw(raw_metrics, "short_term")),
        "medium_term": _full_metric_block(_horizon_raw(raw_metrics, "medium_term")),
        "delta": _full_delta_block(
            raw_metrics.get("overall", {}),
            raw_baseline_metrics.get("overall", {}),
        ) if raw_baseline_metrics else None,
        "decision": summary.get("decision"),
        "note": summary.get("change"),
        "next": summary.get("next"),
    }
    with history_path.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def update_state(
    *,
    state_path: Path,
    iteration: int | None,
    summary: dict[str, Any],
    raw_metrics: dict[str, Any],
    raw_baseline_metrics: dict[str, Any] | None = None,
) -> None:
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        state = {"schema_version": 1}
    state["status"] = "active" if summary.get("decision") == "pending" else "paused"
    state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    if iteration is not None:
        state["last_completed_iteration"] = iteration
    state["last_completed_run_id"] = summary["run"]

    tried_entry: dict[str, Any] = {
        "iter": iteration,
        "run_id": summary["run"],
        "change": summary.get("change"),
        "delta_pf": _delta(
            raw_metrics.get("overall", {}).get("profit_factor"),
            raw_baseline_metrics.get("overall", {}).get("profit_factor") if raw_baseline_metrics else None,
        ),
        "decision": summary.get("decision"),
    }
    tried: list = state.get("tried", [])
    tried.append(tried_entry)
    state["tried"] = tried

    if str(summary.get("decision", "")).lower() in {"accept", "accepted"}:
        state["accepted_best_run_id"] = summary["run"]
        state["accepted_best_metrics"] = {
            "overall": _full_metric_block(raw_metrics.get("overall", {})),
            "short_term": _full_metric_block(_horizon_raw(raw_metrics, "short_term")),
            "medium_term": _full_metric_block(_horizon_raw(raw_metrics, "medium_term")),
        }
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact helpers for token-efficient codex-backed optimization loops.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summarize-run", help="Print compact JSON metrics for a run.")
    _add_common_args(summary_parser)

    audit_parser = subparsers.add_parser("append-audit", help="Append JSONL entry to history.jsonl and update optimization state.")
    _add_common_args(audit_parser)
    audit_parser.add_argument("--iteration", type=int, required=True)
    audit_parser.add_argument("--history-path", type=Path, default=DEFAULT_HISTORY_PATH)
    audit_parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)

    args = parser.parse_args()
    metrics = load_metrics(args.results_dir, args.run_id)
    baseline_metrics = load_metrics(args.results_dir, args.baseline_run_id) if args.baseline_run_id else None
    summary = build_summary(
        run_id=args.run_id,
        metrics=metrics,
        baseline_run_id=args.baseline_run_id,
        baseline_metrics=baseline_metrics,
        change=args.change,
        decision=args.decision,
        next_step=args.next,
    )

    if args.command == "summarize-run":
        print(json.dumps(summary, indent=2))
        return 0

    append_history_entry(
        history_path=args.history_path,
        iteration=args.iteration,
        summary=summary,
        raw_metrics=metrics,
        raw_baseline_metrics=baseline_metrics,
    )
    update_state(
        state_path=args.state_path,
        iteration=args.iteration,
        summary=summary,
        raw_metrics=metrics,
        raw_baseline_metrics=baseline_metrics,
    )
    print(json.dumps({"status": "ok", "summary": summary}, indent=2))
    return 0


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--baseline-run-id", default=None)
    parser.add_argument("--change", default=None)
    parser.add_argument("--decision", default=None)
    parser.add_argument("--next", default=None)


def _full_metric_block(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "count": row.get("count"),
        "avg_return_pct": row.get("avg_return_pct"),
        "median_return_pct": row.get("median_return_pct"),
        "win_rate_pct": row.get("win_rate_pct"),
        "profit_factor": row.get("profit_factor"),
    }


def _full_delta_block(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "avg_return_pct": _delta(row.get("avg_return_pct"), baseline.get("avg_return_pct")),
        "median_return_pct": _delta(row.get("median_return_pct"), baseline.get("median_return_pct")),
        "win_rate_pct": _delta(row.get("win_rate_pct"), baseline.get("win_rate_pct")),
        "profit_factor": _delta(row.get("profit_factor"), baseline.get("profit_factor")),
    }


def _metric_block(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "count": row.get("count"),
        "avg": row.get("avg_return_pct"),
        "median": row.get("median_return_pct"),
        "win": row.get("win_rate_pct"),
        "pf": row.get("profit_factor"),
    }


def _horizon_raw(metrics: dict[str, Any], horizon: str) -> dict[str, Any]:
    for row in metrics.get("by_horizon", []):
        if row.get("horizon") == horizon:
            return row
    return {}


def _horizon_block(metrics: dict[str, Any], horizon: str) -> dict[str, Any]:
    return _metric_block(_horizon_raw(metrics, horizon))


def _delta_block(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "avg": _delta(row.get("avg_return_pct"), baseline.get("avg_return_pct")),
        "median": _delta(row.get("median_return_pct"), baseline.get("median_return_pct")),
        "win": _delta(row.get("win_rate_pct"), baseline.get("win_rate_pct")),
        "pf": _delta(row.get("profit_factor"), baseline.get("profit_factor")),
    }


def _delta(value: Any, baseline: Any) -> float | None:
    if value is None or baseline is None:
        return None
    return round(float(value) - float(baseline), 4)


if __name__ == "__main__":
    raise SystemExit(main())
