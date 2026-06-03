from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.features.feature_snapshot import FeatureSnapshot


@dataclass
class UniverseFilterResult:
    tradable: bool
    reason: str
    warnings: list[str] = field(default_factory=list)


class UniverseFilter:
    """Checks whether a stock passes basic tradability criteria.

    Config keys (from market_and_universe_config.json universe_filters):
      min_price, min_market_cap, min_avg_volume, min_dollar_volume,
      avoid_earnings_within_days
    """

    def __init__(self, config: dict):
        uf = config.get("universe_filters", {})
        self._min_price: float = uf.get("min_price", 5.0)
        self._min_market_cap: float = uf.get("min_market_cap", 1_000_000_000)
        self._min_avg_volume: float = uf.get("min_avg_volume", 500_000)
        self._min_dollar_volume: float = uf.get("min_dollar_volume", 25_000_000)
        self._earnings_warn_days: int = uf.get("avoid_earnings_within_days", 3)

    def check(self, snapshot: FeatureSnapshot) -> UniverseFilterResult:
        warnings: list[str] = []

        if snapshot.price < self._min_price:
            return UniverseFilterResult(
                tradable=False,
                reason=f"Price ${snapshot.price:.2f} below minimum ${self._min_price}",
            )

        if snapshot.market_cap is not None and snapshot.market_cap < self._min_market_cap:
            return UniverseFilterResult(
                tradable=False,
                reason=f"Market cap ${snapshot.market_cap/1e9:.1f}B below minimum ${self._min_market_cap/1e9:.1f}B",
            )

        if snapshot.avg_volume is not None and snapshot.avg_volume < self._min_avg_volume:
            return UniverseFilterResult(
                tradable=False,
                reason=f"Avg volume {snapshot.avg_volume:,.0f} below minimum {self._min_avg_volume:,.0f}",
            )

        if snapshot.dollar_volume is not None and snapshot.dollar_volume < self._min_dollar_volume:
            return UniverseFilterResult(
                tradable=False,
                reason=f"Dollar volume below minimum ${self._min_dollar_volume/1e6:.0f}M",
            )

        if (
            snapshot.earnings_days_away is not None
            and snapshot.earnings_days_away <= self._earnings_warn_days
        ):
            warnings.append(
                f"Earnings in {snapshot.earnings_days_away} days — "
                "consider waiting for post-earnings clarity"
            )

        return UniverseFilterResult(tradable=True, reason="Passes all filters", warnings=warnings)
