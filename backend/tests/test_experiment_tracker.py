"""Tests for backtest.experiment_tracker."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backtest.experiment_tracker import ExperimentTracker, ExperimentManifest


@pytest.fixture
def tracker(tmp_path):
    return ExperimentTracker(experiments_dir=str(tmp_path / "experiments"))


class TestStartExperiment:
    def test_creates_manifest_file(self, tracker, tmp_path):
        manifest = tracker.start_experiment("exp001", description="test run")
        manifest_path = tmp_path / "experiments" / "exp001_manifest.json"
        assert manifest_path.exists()

    def test_manifest_fields_populated(self, tracker):
        manifest = tracker.start_experiment(
            "exp002",
            description="test",
            changed_params={"rsi_period": 14},
            tags=["baseline"],
        )
        assert manifest.experiment_id == "exp002"
        assert manifest.description == "test"
        assert manifest.changed_params == {"rsi_period": 14}
        assert "baseline" in manifest.tags
        assert manifest.primary_metric_value is None

    def test_manifest_json_valid(self, tracker, tmp_path):
        tracker.start_experiment("exp003")
        raw = (tmp_path / "experiments" / "exp003_manifest.json").read_text()
        data = json.loads(raw)
        assert data["experiment_id"] == "exp003"


class TestSaveResults:
    def _make_metrics(self, avg_return=3.5) -> dict:
        return {
            "short_term": {
                "total_signals": 100,
                "resolved_signals": 90,
                "overall_stats": {
                    "avg_return_pct": avg_return,
                    "overall_win_rate_pct": 60.0,
                },
            }
        }

    def test_updates_primary_metric_value(self, tracker):
        tracker.start_experiment("exp004", primary_metric="avg_return_pct|short_term")
        tracker.save_results("exp004", self._make_metrics(4.2))
        experiments = tracker.list_experiments()
        exp = next(e for e in experiments if e["experiment_id"] == "exp004")
        assert exp["primary_metric_value"] == 4.2

    def test_writes_summary_file(self, tracker, tmp_path):
        tracker.start_experiment("exp005")
        tracker.save_results("exp005", self._make_metrics())
        summary_path = tmp_path / "experiments" / "exp005_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert data["experiment_id"] == "exp005"

    def test_no_op_when_manifest_missing(self, tracker):
        # Should not raise even if manifest doesn't exist
        tracker.save_results("nonexistent", {})


class TestCompareToBaseline:
    def _setup_pair(self, tracker):
        tracker.start_experiment("baseline", primary_metric="avg_return_pct|short_term")
        metrics_b = {"short_term": {"overall_stats": {"avg_return_pct": 2.0}, "total_signals": 50, "resolved_signals": 50}}
        tracker.save_results("baseline", metrics_b)

        tracker.start_experiment("improved", baseline_id="baseline", primary_metric="avg_return_pct|short_term")
        metrics_i = {"short_term": {"overall_stats": {"avg_return_pct": 3.5}, "total_signals": 50, "resolved_signals": 50}}
        tracker.save_results("improved", metrics_i)

    def test_delta_computed_correctly(self, tracker):
        self._setup_pair(tracker)
        comp = tracker.compare_to_baseline("improved")
        assert comp["delta"] == pytest.approx(1.5, abs=0.01)
        assert comp["baseline"] == "baseline"

    def test_error_when_experiment_missing(self, tracker):
        result = tracker.compare_to_baseline("ghost")
        assert "error" in result

    def test_error_when_no_baseline_id(self, tracker):
        tracker.start_experiment("solo")
        result = tracker.compare_to_baseline("solo")
        assert "error" in result


class TestListExperiments:
    def test_returns_all_experiments(self, tracker):
        tracker.start_experiment("a")
        tracker.start_experiment("b")
        tracker.start_experiment("c")
        lst = tracker.list_experiments()
        ids = {e["experiment_id"] for e in lst}
        assert {"a", "b", "c"} == ids

    def test_empty_when_no_experiments(self, tracker):
        assert tracker.list_experiments() == []
