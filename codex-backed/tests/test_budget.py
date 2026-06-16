"""S2.3 — DailyBudget tests."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from codex_backed.data.providers.base import ProviderError
from codex_backed.data.providers.budget import DailyBudget, _utc_day_start


def test_increment_persists_to_disk(tmp_path):
    path = tmp_path / "budget.json"
    budget = DailyBudget(budget_path=path, limit=100)
    budget.increment()
    budget.increment()
    # Fresh instance must see the persisted count
    budget2 = DailyBudget(budget_path=path, limit=100)
    assert budget2.current_count() == 2


def test_exceeds_budget_raises_when_action_is_fail(tmp_path):
    path = tmp_path / "budget.json"
    budget = DailyBudget(budget_path=path, limit=2, on_exceed="fail")
    budget.increment()
    budget.increment()
    with pytest.raises(ProviderError, match="exhausted"):
        budget.check()


def test_exceeds_budget_warns_when_action_is_warn(tmp_path, caplog):
    import logging
    path = tmp_path / "budget.json"
    budget = DailyBudget(budget_path=path, limit=1, on_exceed="warn")
    budget.increment()
    with caplog.at_level(logging.WARNING, logger="codex_backed.data.providers.budget"):
        budget.check()  # must NOT raise
    assert any("exhausted" in r.getMessage() for r in caplog.records)


def test_counter_resets_at_utc_midnight(tmp_path):
    path = tmp_path / "budget.json"
    budget = DailyBudget(budget_path=path, limit=100)
    # Write a state with yesterday's day_start
    yesterday_start = _utc_day_start() - 86_400
    path.write_text(json.dumps({"day_start": yesterday_start, "count": 99}))
    # Fresh read should see a reset counter
    assert budget.current_count() == 0


def test_disabled_budget_is_unlimited(tmp_path):
    path = tmp_path / "budget.json"
    budget = DailyBudget(budget_path=path, limit=None)
    assert budget.disabled
    for _ in range(1000):
        budget.increment()
    budget.check()  # should not raise
