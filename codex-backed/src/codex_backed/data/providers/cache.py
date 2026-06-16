from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_DEFAULT_TTL_SECONDS = 86_400  # 24 hours


class DiskCache:
    """Per-key JSON cache with TTL and schema_version guard.

    Files are written atomically via a tmp sibling + os.rename so concurrent
    readers never observe a partial write.  Each stored file is a JSON envelope:
    {"schema_version": int, "stored_at": float, "payload": Any}
    """

    def __init__(
        self,
        cache_dir: str | Path,
        schema_version: int,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._dir = Path(cache_dir)
        self._schema_version = schema_version
        self._ttl = ttl_seconds

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "_")
        return self._dir / f"{safe}.json"

    def get(self, key: str) -> Any | None:
        """Return cached payload or None on miss, expiry, or schema mismatch."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        if envelope.get("schema_version") != self._schema_version:
            return None
        stored_at = envelope.get("stored_at", 0.0)
        if time.time() - stored_at > self._ttl:
            return None
        return envelope.get("payload")

    def set(self, key: str, value: Any) -> None:
        """Write value under key atomically."""
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        envelope = {
            "schema_version": self._schema_version,
            "stored_at": time.time(),
            "payload": value,
        }
        tmp.write_text(json.dumps(envelope))
        os.rename(tmp, path)
