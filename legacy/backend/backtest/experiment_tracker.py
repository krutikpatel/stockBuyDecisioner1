"""
Experiment tracking for backtest runs.

Saves ExperimentManifest files to disk so parameter changes can be
compared against a baseline run.
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_EXPERIMENTS_DIR_DEFAULT = Path(__file__).parent / "experiments"


@dataclass
class ExperimentManifest:
    experiment_id: str
    description: str
    created_at: str                        # ISO 8601 UTC timestamp
    code_version: str                      # git short-hash or "unknown"
    config_hash: str                       # first 16 chars of SHA-256 of algo_config.json
    changed_params: dict[str, Any]         # human-readable diff vs. baseline
    cli_args: dict[str, Any]               # CLI arguments used for this run
    primary_metric: str                    # e.g. "avg_return_pct|short_term"
    primary_metric_value: Optional[float] = None
    baseline_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)


class ExperimentTracker:
    """Creates, updates, and compares backtest experiment manifests."""

    def __init__(self, experiments_dir: Optional[str] = None) -> None:
        self._dir = Path(experiments_dir or _EXPERIMENTS_DIR_DEFAULT)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ public

    def start_experiment(
        self,
        experiment_id: str,
        description: str = "",
        changed_params: Optional[dict] = None,
        cli_args: Optional[dict] = None,
        primary_metric: str = "avg_return_pct|short_term",
        baseline_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        algo_config_path: Optional[str] = None,
    ) -> ExperimentManifest:
        """Create and persist a new ExperimentManifest.

        Returns the manifest object so callers can attach it to run metadata.
        """
        manifest = ExperimentManifest(
            experiment_id=experiment_id,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat(),
            code_version=self._git_version(),
            config_hash=self._hash_config(algo_config_path),
            changed_params=changed_params or {},
            cli_args=cli_args or {},
            primary_metric=primary_metric,
            baseline_id=baseline_id,
            tags=tags or [],
        )
        self._save(manifest)
        logger.info("Experiment started: %s", experiment_id)
        return manifest

    def save_results(
        self,
        experiment_id: str,
        all_metrics: dict,
    ) -> None:
        """Extract the primary metric value from all_metrics and update the manifest."""
        manifest = self._load(experiment_id)
        if manifest is None:
            logger.warning(
                "No manifest found for '%s' — skipping save_results", experiment_id
            )
            return

        parts   = (manifest.primary_metric + "|short_term").split("|")
        metric_key, horizon = parts[0], parts[1]
        overall = all_metrics.get(horizon, {}).get("overall_stats", {})
        manifest.primary_metric_value = overall.get(metric_key)
        self._save(manifest)

        summary = {
            "experiment_id":         experiment_id,
            "primary_metric":        manifest.primary_metric,
            "primary_metric_value":  manifest.primary_metric_value,
            "total_signals": sum(
                all_metrics.get(h, {}).get("total_signals", 0)
                for h in ("short_term", "medium_term", "long_term")
            ),
        }
        (self._dir / f"{experiment_id}_summary.json").write_text(
            json.dumps(summary, indent=2)
        )
        logger.info("Results saved for '%s': primary=%s", experiment_id, manifest.primary_metric_value)

    def compare_to_baseline(
        self,
        experiment_id: str,
        baseline_id: Optional[str] = None,
    ) -> dict:
        """Return a comparison dict between two experiments."""
        manifest = self._load(experiment_id)
        if manifest is None:
            return {"error": f"Experiment '{experiment_id}' not found"}

        bid = baseline_id or manifest.baseline_id
        if bid is None:
            return {"error": "No baseline_id specified"}

        baseline = self._load(bid)
        if baseline is None:
            return {"error": f"Baseline experiment '{bid}' not found"}

        delta: Optional[float] = None
        if (
            manifest.primary_metric_value is not None
            and baseline.primary_metric_value is not None
        ):
            delta = round(manifest.primary_metric_value - baseline.primary_metric_value, 4)

        return {
            "experiment":       experiment_id,
            "baseline":         bid,
            "primary_metric":   manifest.primary_metric,
            "experiment_value": manifest.primary_metric_value,
            "baseline_value":   baseline.primary_metric_value,
            "delta":            delta,
            "changed_params":   manifest.changed_params,
        }

    def list_experiments(self) -> list[dict]:
        """Return all saved experiments sorted newest-first."""
        results = []
        for f in sorted(self._dir.glob("*_manifest.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                results.append({
                    k: data.get(k)
                    for k in (
                        "experiment_id", "description", "created_at",
                        "primary_metric", "primary_metric_value", "baseline_id",
                    )
                })
            except Exception:
                pass
        return results

    # ----------------------------------------------------------------- private

    def _save(self, manifest: ExperimentManifest) -> None:
        path = self._dir / f"{manifest.experiment_id}_manifest.json"
        path.write_text(json.dumps(asdict(manifest), indent=2))

    def _load(self, experiment_id: str) -> Optional[ExperimentManifest]:
        path = self._dir / f"{experiment_id}_manifest.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return ExperimentManifest(**data)

    @staticmethod
    def _hash_config(config_path: Optional[str]) -> str:
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "algo_config.json")
        try:
            content = Path(config_path).read_bytes()
            return hashlib.sha256(content).hexdigest()[:16]
        except Exception:
            return "unknown"

    @staticmethod
    def _git_version() -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"
