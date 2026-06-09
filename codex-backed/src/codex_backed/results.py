from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path
    manifest_path: Path
    trades_path: Path
    entry_decisions_path: Path
    metrics_path: Path
    report_path: Path


def make_run_id(prefix: str = "run") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}"


def create_run_paths(output_dir: Path, run_id: str | None = None) -> RunPaths:
    resolved_run_id = run_id or make_run_id()
    run_dir = output_dir / resolved_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return RunPaths(
        run_id=resolved_run_id,
        run_dir=run_dir,
        manifest_path=run_dir / "manifest.json",
        trades_path=run_dir / "trades.csv",
        entry_decisions_path=run_dir / "entry_decisions.csv",
        metrics_path=run_dir / "metrics.json",
        report_path=run_dir / "report.html",
    )


def write_manifest(
    paths: RunPaths,
    *,
    command: str,
    cli_args: dict[str, Any],
    config_dir: Path,
) -> None:
    manifest = {
        "run_id": paths.run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "cli_args": cli_args,
        "config_dir": str(config_dir),
        "git_commit": _git_commit(),
        "paths": {k: str(v) for k, v in asdict(paths).items()},
    }
    paths.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None

