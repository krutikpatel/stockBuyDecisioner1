"""S2.2 — DiskCache tests."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from codex_backed.data.providers.cache import DiskCache


def test_set_then_get_roundtrip(tmp_path):
    cache = DiskCache(tmp_path / "cache", schema_version=1)
    cache.set("ticker/AAPL", {"close": 170.5})
    result = cache.get("ticker/AAPL")
    assert result == {"close": 170.5}


def test_get_returns_none_when_missing(tmp_path):
    cache = DiskCache(tmp_path / "cache", schema_version=1)
    assert cache.get("nonexistent_key") is None


def test_get_returns_none_when_ttl_expired(tmp_path):
    cache = DiskCache(tmp_path / "cache", schema_version=1, ttl_seconds=1.0)
    cache.set("k", {"v": 1})
    # backdate stored_at to simulate expiry
    path = list((tmp_path / "cache").glob("*.json"))[0]
    envelope = json.loads(path.read_text())
    envelope["stored_at"] = time.time() - 10.0
    path.write_text(json.dumps(envelope))
    assert cache.get("k") is None


def test_get_returns_none_when_schema_version_mismatch(tmp_path):
    writer = DiskCache(tmp_path / "cache", schema_version=1)
    writer.set("k", {"v": 1})
    reader = DiskCache(tmp_path / "cache", schema_version=2)
    assert reader.get("k") is None


def test_atomic_write_uses_rename(tmp_path):
    cache = DiskCache(tmp_path / "cache", schema_version=1)
    rename_calls: list[tuple] = []
    original_rename = __import__("os").rename

    def capturing_rename(src, dst):
        rename_calls.append((str(src), str(dst)))
        return original_rename(src, dst)

    with patch("codex_backed.data.providers.cache.os.rename", side_effect=capturing_rename):
        cache.set("k", 42)

    assert len(rename_calls) == 1
    src, dst = rename_calls[0]
    assert src.endswith(".tmp")
    assert not dst.endswith(".tmp")


def test_concurrent_reads_during_write_never_see_partial_data(tmp_path):
    """Atomic rename: readers should always see a complete envelope or nothing."""
    cache = DiskCache(tmp_path / "cache", schema_version=1)
    cache.set("k", list(range(100)))

    errors: list[str] = []

    def reader():
        for _ in range(50):
            val = cache.get("k")
            if val is not None and not isinstance(val, list):
                errors.append(f"unexpected type: {type(val)}")

    def writer():
        for i in range(10):
            cache.set("k", list(range(100 + i)))

    threads = [threading.Thread(target=reader) for _ in range(4)]
    threads.append(threading.Thread(target=writer))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Partial-data reads observed: {errors}"


def test_set_writes_payload_with_schema_version_envelope(tmp_path):
    cache = DiskCache(tmp_path / "cache", schema_version=7)
    cache.set("k", "hello")
    path = list((tmp_path / "cache").glob("*.json"))[0]
    envelope = json.loads(path.read_text())
    assert envelope["schema_version"] == 7
    assert envelope["payload"] == "hello"
    assert "stored_at" in envelope
