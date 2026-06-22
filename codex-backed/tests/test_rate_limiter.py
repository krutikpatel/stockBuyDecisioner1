"""S2.3 — Token-bucket rate limiter tests."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from codex_backed.data.providers.rate_limiter import TokenBucket


def test_bucket_allows_burst_up_to_capacity():
    bucket = TokenBucket(capacity=5, rate_per_second=1)
    # Five tokens available immediately; all should return without sleeping
    start = time.monotonic()
    for _ in range(5):
        bucket.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"Burst took too long: {elapsed:.2f}s"


def test_bucket_blocks_when_empty():
    bucket = TokenBucket(capacity=1, rate_per_second=100)
    bucket.acquire()  # drain the single token
    start = time.monotonic()
    bucket.acquire()  # must wait for refill
    elapsed = time.monotonic() - start
    # At 100 tokens/s a refill takes ~10ms; anything > 1ms is proof of blocking
    assert elapsed > 0.001


def test_bucket_refills_over_time():
    # 10 tokens/s: after 0.15s we should have at least 1 new token
    bucket = TokenBucket(capacity=2, rate_per_second=10)
    bucket.acquire()
    bucket.acquire()  # fully drained
    time.sleep(0.15)
    # Should not block (token has refilled)
    start = time.monotonic()
    bucket.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


def test_throttle_event_counted_in_stats():
    bucket = TokenBucket(capacity=1, rate_per_second=200)
    bucket.acquire()  # drain
    # next acquire must block → throttle_events should increment
    bucket.acquire()
    assert bucket.stats.throttle_events >= 1
