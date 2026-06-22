"""S1.7 — Writer column pinning tests."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from codex_backed.backtest.writer import (
    ENTRY_DECISIONS_COLUMNS,
    TRADES_COLUMNS,
    write_csv,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def test_entry_decisions_csv_columns_in_pinned_order(tmp_path):
    out = tmp_path / "decisions.csv"
    row = {col: f"v_{col}" for col in ENTRY_DECISIONS_COLUMNS}
    write_csv(out, [row], columns=ENTRY_DECISIONS_COLUMNS)

    with out.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)

    assert header == list(ENTRY_DECISIONS_COLUMNS)


def test_trades_csv_columns_in_pinned_order(tmp_path):
    out = tmp_path / "trades.csv"
    row = {col: f"v_{col}" for col in TRADES_COLUMNS}
    write_csv(out, [row], columns=TRADES_COLUMNS)

    with out.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)

    assert header == list(TRADES_COLUMNS)


def test_extra_dict_keys_dropped_silently(tmp_path):
    out = tmp_path / "decisions.csv"
    row = {col: f"v_{col}" for col in ENTRY_DECISIONS_COLUMNS}
    row["unexpected_extra_field"] = "should_not_appear"
    write_csv(out, [row], columns=ENTRY_DECISIONS_COLUMNS)

    rows = _read_csv(out)
    assert len(rows) == 1
    assert "unexpected_extra_field" not in rows[0]
    assert set(rows[0].keys()) == set(ENTRY_DECISIONS_COLUMNS)


def test_missing_dict_keys_emit_empty_string(tmp_path):
    out = tmp_path / "decisions.csv"
    row = {"ticker": "AAPL", "date": "2023-01-01"}  # all other cols absent
    write_csv(out, [row], columns=ENTRY_DECISIONS_COLUMNS)

    rows = _read_csv(out)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["entry_label"] == ""
