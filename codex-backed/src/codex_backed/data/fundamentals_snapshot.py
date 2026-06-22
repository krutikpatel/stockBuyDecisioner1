from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields

FUNDAMENTALS_SNAPSHOT_SCHEMA_VERSION = 1


@dataclass
class FundamentalsSnapshot:
    """Fundamentals data for a single (ticker, as_of_date) point.

    Mirrors the fundamentals subset of FeatureSnapshot.  Every field here
    must also exist on FeatureSnapshot so the builder can merge snapshots
    directly into feature rows without a translation step.
    """

    ticker: str
    as_of_date: str  # ISO date string

    # Statements / ratios
    sales_growth_yoy: float | None = None
    sales_growth_qoq: float | None = None
    eps_growth_yoy: float | None = None
    eps_growth_next_year: float | None = None
    eps_growth_3y: float | None = None
    eps_growth_5y: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    free_cash_flow: float | None = None
    roic: float | None = None
    roe: float | None = None
    roa: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None

    # Valuation
    forward_pe: float | None = None
    trailing_pe: float | None = None
    peg_ratio: float | None = None
    price_to_sales: float | None = None
    ev_to_ebitda: float | None = None
    price_to_fcf: float | None = None
    fcf_yield: float | None = None
    ev_sales: float | None = None

    # Earnings calendar / surprise
    beat_rate: float | None = None
    avg_eps_surprise_pct: float | None = None
    earnings_days_away: int | None = None
    earnings_within_30_days: bool = False

    # Ownership / float (served primarily by yfinance fallback)
    insider_ownership: float | None = None
    institutional_ownership: float | None = None
    short_float: float | None = None

    # Misc
    dividend_yield: float | None = None
    market_cap: float | None = None
    beta: float | None = None
    sector: str | None = None
    industry: str | None = None
    analyst_recommendation: float | None = None
    analyst_target_price: float | None = None

    @classmethod
    def field_names(cls) -> list[str]:
        """Return all field names except the identity fields (ticker, as_of_date)."""
        return [
            f.name
            for f in dataclass_fields(cls)
            if f.name not in ("ticker", "as_of_date")
        ]
