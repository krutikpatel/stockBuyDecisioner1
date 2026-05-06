"""
Backtest configuration.
Centralises all tunable parameters so runner/metrics/report stay parameter-free.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

BACKTEST_TICKERS: list[str] = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META",
    # High-growth / momentum
    "TSLA", "AMD", "SHOP", "SNOW",
    # Cybersecurity
    "CRWD", "PANW",
    # Financials
    "JPM", "GS",
    # Healthcare / biotech
    "UNH", "LLY",
    # Energy
    "XOM", "CVX",
    # Speculative
    "DKNG", "ROKU",
]

# Benchmark tickers (always fetched alongside stock universe)
BENCHMARK_TICKERS: list[str] = ["SPY", "QQQ"]

# Sector ETF mapping — used for sector-relative RS and sector_macro_score
SECTOR_ETF_MAP: dict[str, str] = {
    "AAPL":  "XLK",
    "MSFT":  "XLK",
    "NVDA":  "XLK",
    "GOOGL": "XLK",
    "AMZN":  "XLY",
    "META":  "XLK",
    "TSLA":  "XLY",
    "AMD":   "XLK",
    "SHOP":  "XLK",
    "SNOW":  "XLK",
    "CRWD":  "XLK",
    "PANW":  "XLK",
    "JPM":   "XLF",
    "GS":    "XLF",
    "UNH":   "XLV",
    "LLY":   "XLV",
    "XOM":   "XLE",
    "CVX":   "XLE",
    "DKNG":  "XLY",
    "ROKU":  "XLK",
}

# ---------------------------------------------------------------------------
# Date ranges
# ---------------------------------------------------------------------------

# Full history download start — needs enough pre-history for 200-day MA warmup
HISTORY_START: str = "2016-01-01"

# Backtest period
BACKTEST_START: str = "2018-01-01"
BACKTEST_END: str = "2025-12-31"

# ---------------------------------------------------------------------------
# Horizons
# Keys match HorizonRecommendation.horizon values used by the production code.
# Values are calendar-day offsets used when looking up exit prices.
# ---------------------------------------------------------------------------

HORIZONS: list[str] = ["short_term", "medium_term", "long_term"]

# Trading-day holding periods (used by outcome.py to find exit price)
HOLDING_PERIODS: dict[str, int] = {
    "short_term":  20,   # ~1 month
    "medium_term": 63,   # ~3 months
    "long_term":   252,  # ~1 year
}

# ---------------------------------------------------------------------------
# Snapshot / runner settings
# ---------------------------------------------------------------------------

# Minimum bars of price history required before a snapshot is generated
MIN_ROWS_FOR_ANALYSIS: int = 252

# Risk profile used by build_recommendations (affects position sizing only)
DEFAULT_RISK_PROFILE: str = "moderate"

# Slippage cost applied to forward return (as a fraction, e.g. 0.001 = 0.1%)
SLIPPAGE: float = 0.0  # Phase 1: no slippage

# Phase gate: controls which data sources are used
# 1 = technical + regime only (no fundamentals)
# 2 = same as 1 (regime metrics added in post-processing)
# 3 = add time-sliced fundamentals + archetype
DEFAULT_PHASE: int = 3

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BASE = Path(__file__).parent

CACHE_DIR: str = str(_BASE / "cache")
RESULTS_DIR: str = str(_BASE / "results")
