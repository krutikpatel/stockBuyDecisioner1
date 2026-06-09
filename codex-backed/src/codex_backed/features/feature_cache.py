from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class FeatureCacheResult:
    rows: list[dict[str, Any]]
    status: str
    path: Path
    cache_key: str


def load_or_build_feature_rows(
    *,
    cache_path: Path,
    metadata: dict[str, Any],
    rebuild: bool,
    builder: Callable[[], list[dict[str, Any]]],
) -> FeatureCacheResult:
    cache_key = _cache_key(metadata)
    if not rebuild:
        cached = _read_cache(cache_path)
        if cached and cached.get("cache_key") == cache_key:
            rows = cached.get("rows")
            if isinstance(rows, list):
                return FeatureCacheResult(rows=rows, status="hit", path=cache_path, cache_key=cache_key)

    rows = builder()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as fh:
        pickle.dump({"cache_key": cache_key, "metadata": metadata, "rows": rows}, fh)
    return FeatureCacheResult(rows=rows, status="rebuilt", path=cache_path, cache_key=cache_key)


def _read_cache(cache_path: Path) -> dict[str, Any] | None:
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("rb") as fh:
            value = pickle.load(fh)
    except (OSError, pickle.PickleError, EOFError):
        return None
    return value if isinstance(value, dict) else None


def _cache_key(metadata: dict[str, Any]) -> str:
    encoded = json.dumps(metadata, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
