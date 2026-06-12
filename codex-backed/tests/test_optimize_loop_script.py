import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "optimize_loop.py"
    spec = importlib.util.spec_from_file_location("optimize_loop", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_summary_includes_horizon_deltas():
    module = _load_module()
    metrics = {
        "overall": {"count": 10, "avg_return_pct": 5.0, "median_return_pct": 4.0, "win_rate_pct": 60.0, "profit_factor": 2.0},
        "by_horizon": [
            {"horizon": "short_term", "count": 5, "avg_return_pct": 3.0, "median_return_pct": 2.0, "win_rate_pct": 70.0, "profit_factor": 1.8},
            {"horizon": "medium_term", "count": 5, "avg_return_pct": 7.0, "median_return_pct": 6.0, "win_rate_pct": 50.0, "profit_factor": 2.2},
        ],
    }
    baseline = {
        "overall": {"count": 10, "avg_return_pct": 4.0, "median_return_pct": 4.0, "win_rate_pct": 55.0, "profit_factor": 1.9},
        "by_horizon": [
            {"horizon": "short_term", "count": 5, "avg_return_pct": 2.5, "median_return_pct": 2.0, "win_rate_pct": 68.0, "profit_factor": 1.7},
            {"horizon": "medium_term", "count": 5, "avg_return_pct": 6.5, "median_return_pct": 6.0, "win_rate_pct": 48.0, "profit_factor": 2.1},
        ],
    }

    summary = module.build_summary(
        run_id="test_run",
        metrics=metrics,
        baseline_run_id="base_run",
        baseline_metrics=baseline,
        change="short.foo 1 -> 2",
        decision="accept",
        next_step="continue",
    )

    assert summary["short_term"]["win"] == 70.0
    assert summary["delta"]["short_term"]["win"] == 2.0
    assert summary["delta"]["overall"]["avg"] == 1.0


def test_append_audit_and_update_state(tmp_path):
    module = _load_module()
    log_path = tmp_path / "audit.md"
    state_path = tmp_path / "state.json"
    summary = {
        "run": "test_run",
        "change": "x 1 -> 2",
        "decision": "accept",
        "next": "done",
        "overall": {"count": 1, "avg": 1.0, "median": 1.0, "win": 100.0, "pf": None},
        "short_term": {"count": 1, "avg": 1.0, "median": 1.0, "win": 100.0, "pf": None},
        "medium_term": {"count": 0, "avg": None, "median": None, "win": None, "pf": None},
        "delta": {
            "overall": {"avg": 1.0, "median": 1.0, "win": 10.0, "pf": None},
            "short_term": {"avg": 1.0, "median": 1.0, "win": 10.0, "pf": None},
            "medium_term": {"avg": None, "median": None, "win": None, "pf": None},
        },
    }

    module.append_audit_entry(log_path=log_path, iteration=1, summary=summary)
    module.update_state(state_path=state_path, iteration=1, summary=summary)

    assert "## Iteration 1" in log_path.read_text()
    state = json.loads(state_path.read_text())
    assert state["accepted_best_run_id"] == "test_run"
    assert state["last_completed_iteration"] == 1
