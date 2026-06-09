from __future__ import annotations

from enum import StrEnum


class EntryLabel(StrEnum):
    NO_TRADE = "NO_TRADE"
    WATCHLIST = "WATCHLIST"
    BUY_STARTER = "BUY_STARTER"
    BUY_FULL = "BUY_FULL"
    BUY_AGGRESSIVE = "BUY_AGGRESSIVE"


ACTIONABLE_ENTRY_LABELS = {
    EntryLabel.BUY_STARTER.value,
    EntryLabel.BUY_FULL.value,
    EntryLabel.BUY_AGGRESSIVE.value,
}

