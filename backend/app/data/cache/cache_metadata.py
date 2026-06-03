"""
Provenance metadata written alongside each parquet cache file.

One JSON file per parquet shard: ``{parquet_path}.meta.json``.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class CacheMetadata:
    ticker: str
    provider: str
    data_type: str               # "price" | "fundamentals" | "earnings" | ...
    interval: str                # "1d", "1h", etc.
    start: str                   # ISO date string
    end: str                     # ISO date string
    fetched_at: str              # ISO 8601 UTC timestamp
    schema_version: int          # bump when parquet schema changes
    adjusted_prices: bool        # True if prices are split/dividend adjusted
    row_count: int
    columns: list[str]
    notes: Optional[str] = None


def save_metadata(parquet_path: Path, metadata: CacheMetadata) -> None:
    """Write metadata JSON alongside *parquet_path*."""
    meta_path = parquet_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(asdict(metadata), indent=2))


def load_metadata(parquet_path: Path) -> Optional[CacheMetadata]:
    """Load metadata for *parquet_path*. Returns None if file is missing."""
    meta_path = parquet_path.with_suffix(".meta.json")
    if not meta_path.exists():
        return None
    data = json.loads(meta_path.read_text())
    return CacheMetadata(**data)


def make_metadata(
    ticker: str,
    provider: str,
    data_type: str,
    interval: str,
    start: str,
    end: str,
    row_count: int,
    columns: list[str],
    adjusted_prices: bool = True,
    schema_version: int = 1,
    notes: Optional[str] = None,
) -> CacheMetadata:
    return CacheMetadata(
        ticker=ticker,
        provider=provider,
        data_type=data_type,
        interval=interval,
        start=start,
        end=end,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        schema_version=schema_version,
        adjusted_prices=adjusted_prices,
        row_count=row_count,
        columns=columns,
        notes=notes,
    )
