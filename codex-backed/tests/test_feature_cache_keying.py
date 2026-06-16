"""S1.7 — Feature cache key extension tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from codex_backed.features.feature_cache import load_or_build_feature_rows


def _base_metadata() -> dict:
    return {
        "source": "native",
        "tickers": ["AAPL"],
        "start": "2023-01-01",
        "end": "2023-12-31",
        "horizons": ["short_term"],
        "signal_frequency": "weekly",
        "data_mode": "legacy_yfinance",
        "fundamentals_provider_signature": "null",
        "fundamentals_snapshot_schema_version": 1,
    }


def _build_rows():
    return [{"ticker": "AAPL", "date": "2023-06-01", "horizon": "short_term"}]


def test_cache_key_changes_when_data_mode_changes(tmp_path):
    cache_path = tmp_path / "features.pkl"
    meta1 = {**_base_metadata(), "data_mode": "legacy_yfinance"}
    meta2 = {**_base_metadata(), "data_mode": "fmp_premium"}

    result1 = load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta1, rebuild=True, builder=_build_rows
    )
    result2 = load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta2, rebuild=True, builder=_build_rows
    )

    assert result1.cache_key != result2.cache_key


def test_cache_key_changes_when_provider_signature_changes(tmp_path):
    cache_path = tmp_path / "features.pkl"
    meta1 = {**_base_metadata(), "fundamentals_provider_signature": "null"}
    meta2 = {**_base_metadata(), "fundamentals_provider_signature": "fmp:v2"}

    result1 = load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta1, rebuild=True, builder=_build_rows
    )
    result2 = load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta2, rebuild=True, builder=_build_rows
    )

    assert result1.cache_key != result2.cache_key


def test_cache_key_changes_when_schema_version_bumps(tmp_path):
    cache_path = tmp_path / "features.pkl"
    meta1 = {**_base_metadata(), "fundamentals_snapshot_schema_version": 1}
    meta2 = {**_base_metadata(), "fundamentals_snapshot_schema_version": 2}

    result1 = load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta1, rebuild=True, builder=_build_rows
    )
    result2 = load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta2, rebuild=True, builder=_build_rows
    )

    assert result1.cache_key != result2.cache_key


def test_cache_hit_returns_stored_rows_when_keys_match(tmp_path):
    cache_path = tmp_path / "features.pkl"
    meta = _base_metadata()

    build_count = 0

    def counting_builder():
        nonlocal build_count
        build_count += 1
        return _build_rows()

    load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta, rebuild=False, builder=counting_builder
    )
    result = load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta, rebuild=False, builder=counting_builder
    )

    assert result.status == "hit"
    assert build_count == 1  # second call hit the cache


def test_cache_miss_rebuilds_when_any_metadata_key_changes(tmp_path):
    cache_path = tmp_path / "features.pkl"
    meta1 = _base_metadata()
    meta2 = {**_base_metadata(), "data_mode": "fmp_premium"}

    build_count = 0

    def counting_builder():
        nonlocal build_count
        build_count += 1
        return _build_rows()

    load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta1, rebuild=False, builder=counting_builder
    )
    result = load_or_build_feature_rows(
        cache_path=cache_path, metadata=meta2, rebuild=False, builder=counting_builder
    )

    assert result.status == "rebuilt"
    assert build_count == 2
