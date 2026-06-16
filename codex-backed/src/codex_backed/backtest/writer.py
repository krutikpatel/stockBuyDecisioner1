from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, median
from typing import Any

ENTRY_DECISIONS_COLUMNS: tuple[str, ...] = (
    "ticker", "date", "horizon", "entry_label", "entry_score", "confidence",
    "selected_setup", "entry_strategy", "is_actionable", "reasons", "missing_data",
    "matched_signals", "optional_signals", "market_regime", "archetype", "price",
    "source_decision", "source_strategy", "source_setup",
)

TRADES_COLUMNS: tuple[str, ...] = (
    "ticker", "signal_date", "horizon", "entry_label", "entry_strategy",
    "selected_setup", "entry_date", "entry_index", "entry_price", "entry_method",
    "entry_wait_days", "position_size_multiplier", "applied_size_caps",
    "initial_stop", "target_1", "target_1_hit", "partial_exit_pct",
    "exit_date", "exit_index", "exit_price", "exit_reason", "days_held",
    "realized_return_pct", "mae_pct", "mfe_pct", "mfe_capture_pct",
    "event_count", "market_regime", "archetype", "source_decision",
)


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    columns: tuple[str, ...] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    if columns is not None:
        fieldnames = list(columns)
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore", restval="")
            writer.writeheader()
            writer.writerows(rows)
    else:
        fieldnames = sorted({key for row in rows for key in row})
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


def build_record_metrics(records: list[dict[str, Any]], return_field: str = "realized_return_pct") -> dict[str, Any]:
    if not records:
        return {
            "count": 0,
            "avg_return_pct": None,
            "median_return_pct": None,
            "win_rate_pct": None,
            "profit_factor": None,
        }
    returns = [float(row[return_field]) for row in records if row.get(return_field) is not None]
    if not returns:
        return {
            "count": len(records),
            "avg_return_pct": None,
            "median_return_pct": None,
            "win_rate_pct": None,
            "profit_factor": None,
        }
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "count": len(records),
        "avg_return_pct": round(mean(returns), 4),
        "median_return_pct": round(median(returns), 4),
        "win_rate_pct": round(len(wins) / len(returns) * 100.0, 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
    }


def build_sliced_metrics(records: list[dict[str, Any]], group_field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get(group_field, "UNKNOWN")), []).append(record)
    output: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items()):
        metrics = build_record_metrics(group)
        output.append({group_field: key, **metrics})
    return output


def build_input_quality_metrics(entry_decisions: list[dict[str, Any]], trades: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "missing_field_counts": _count_pipe_values(entry_decisions, "missing_data"),
        "decision_setup_distribution": _count_values(entry_decisions, "selected_setup"),
        "trade_setup_distribution": _count_values(trades, "selected_setup"),
        "actionable_by_setup": _actionable_by_field(entry_decisions, "selected_setup"),
        "entry_label_distribution": _count_values(entry_decisions, "entry_label"),
        "skipped_entry_reasons": _skipped_entry_reasons(entry_decisions),
    }


def write_lifecycle_report(path: Path, *, metrics: dict[str, Any], trade_count: int, decision_count: int) -> None:
    input_quality = metrics.get("input_quality", {})
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Codex-Backed Lifecycle Backtest</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; border-radius: 4px; }}
    pre {{ background: #111827; color: #f9fafb; padding: 1rem; overflow: auto; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; min-width: 520px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.35rem 0.55rem; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>Codex-Backed Lifecycle Backtest</h1>
  <p>Entry decisions: <strong>{decision_count}</strong></p>
  <p>Simulated trades: <strong>{trade_count}</strong></p>
  <p>Feature source: <strong>{input_quality.get("feature_source", "unknown")}</strong>; cache: <strong>{input_quality.get("feature_cache_status", "unknown")}</strong></p>
  <p>This report uses lifecycle exits. Fixed 20D/63D returns are not the primary result.</p>
  <h2>Overall Metrics</h2>
  {_table_from_dict(metrics.get("overall", {}))}
  <h2>Input Quality</h2>
  <h3>Missing Fields</h3>
  {_table_from_counts(input_quality.get("missing_field_counts", {}), "Field")}
  <h3>Decision Setup Distribution</h3>
  {_table_from_counts(input_quality.get("decision_setup_distribution", {}), "Setup")}
  <h3>Actionable By Setup</h3>
  {_table_from_rows(input_quality.get("actionable_by_setup", []))}
  <h2>Entry Quality</h2>
  <h3>By Entry Label</h3>
  {_table_from_rows(metrics.get("by_entry_label", []))}
  <h3>By Entry Setup</h3>
  {_table_from_rows(metrics.get("by_entry_setup", []))}
  <h3>By Horizon</h3>
  {_table_from_rows(metrics.get("by_horizon", []))}
  <h2>Exit Reasons</h2>
  {_table_from_rows(metrics.get("by_exit_reason", []))}
</body>
</html>
"""
    path.write_text(html)


def _count_pipe_values(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        raw = row.get(field)
        if not raw:
            continue
        for value in str(raw).split("|"):
            if value:
                counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _count_values(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field) or "None")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _actionable_by_field(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        value = str(row.get(field) or "None")
        group = grouped.setdefault(value, {"total": 0, "actionable": 0})
        group["total"] += 1
        if row.get("is_actionable"):
            group["actionable"] += 1
    output = []
    for value, group in grouped.items():
        total = group["total"]
        actionable = group["actionable"]
        output.append(
            {
                field: value,
                "total": total,
                "actionable": actionable,
                "actionable_rate_pct": round(actionable / total * 100.0, 4) if total else 0.0,
            }
        )
    return sorted(output, key=lambda row: (-row["actionable"], row[field]))


def _skipped_entry_reasons(rows: list[dict[str, Any]]) -> dict[str, int]:
    skipped = [row for row in rows if not row.get("is_actionable")]
    return _count_values(skipped, "entry_label")


def _table_from_dict(values: dict[str, Any]) -> str:
    rows = [{"metric": key, "value": value} for key, value in values.items()]
    return _table_from_rows(rows)


def _table_from_counts(values: dict[str, int], first_header: str) -> str:
    rows = [{first_header: key, "count": value} for key, value in values.items()]
    return _table_from_rows(rows)


def _table_from_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No data.</p>"
    fieldnames = list(rows[0].keys())
    head = "".join(f"<th>{_escape(name)}</th>" for name in fieldnames)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{_escape(row.get(name))}</td>" for name in fieldnames) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
