from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from codex_backed.data.providers.base import ProviderError

logger = logging.getLogger(__name__)

_UTC_MIDNIGHT_TOLERANCE = 1.0  # seconds


def _utc_day_start() -> float:
    """Return the Unix timestamp for the start of the current UTC day."""
    now = time.time()
    return now - (now % 86_400)


class DailyBudget:
    """Persistent daily request budget for a data provider.

    Counter is stored on disk and resets at UTC midnight.
    On_exceed action: "fail" raises ProviderError; "warn" logs and continues.
    When limit is None the budget is disabled (unlimited).
    """

    def __init__(
        self,
        budget_path: str | Path,
        limit: int | None,
        on_exceed: str = "fail",
    ) -> None:
        self._path = Path(budget_path)
        self._limit = limit
        if on_exceed not in ("fail", "warn"):
            raise ValueError(f"on_exceed must be 'fail' or 'warn', got {on_exceed!r}")
        self._on_exceed = on_exceed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def disabled(self) -> bool:
        return self._limit is None

    def current_count(self) -> int:
        return self._read_state()["count"]

    def increment(self) -> None:
        """Increment the daily counter by one and persist to disk."""
        state = self._read_state()
        state["count"] += 1
        self._write_state(state)

    def check(self) -> None:
        """Check whether the budget is exhausted.

        Raises ProviderError if on_exceed='fail' and limit is reached.
        Logs a warning if on_exceed='warn'.
        Does nothing when limit is None (disabled).
        """
        if self.disabled:
            return
        count = self._read_state()["count"]
        assert self._limit is not None
        if count >= self._limit:
            msg = (
                f"Daily budget exhausted ({count}/{self._limit} requests). "
                f"Resets at next UTC midnight."
            )
            if self._on_exceed == "fail":
                raise ProviderError(msg)
            logger.warning(msg)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _read_state(self) -> dict:
        day_start = _utc_day_start()
        if self._path.exists():
            try:
                state = json.loads(self._path.read_text())
                if isinstance(state, dict) and state.get("day_start", 0) >= day_start:
                    return state
            except (OSError, json.JSONDecodeError):
                pass
        return {"day_start": day_start, "count": 0}

    def _write_state(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        os.rename(tmp, self._path)
