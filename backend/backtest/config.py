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
    "AAPL", "MSFT", "NVDA", "AVGO", "AMD", "INTC", "QCOM", "TXN", "MU", "ADI",
    "AMAT", "LRCX", "KLAC", "ASML", "TSM", "ORCL", "CRM", "ADBE", "NOW", "SNOW",
    "PANW", "CRWD", "FTNT", "ANET", "CDNS", "GOOGL", "GOOG", "META", "NFLX",
    "DIS", "CMCSA", "TMUS", "T", "VZ", "CHTR", "EA", "TTWO", "SPOT", "PINS",
    "SNAP", "RDDT", "ROKU", "LYV", "AMZN", "TSLA", "HD", "LOW", "MCD", "SBUX",
    "NKE", "LULU", "BKNG", "MAR", "HLT", "RCL", "CCL", "GM", "F", "ORLY", "AZO",
    "CMG", "YUM", "TJX", "ROST", "ETS", "WMT", "COST", "PG", "KO", "PEP",
    "MDLZ", "PM", "MO", "CL", "KMB", "GIS", "KHC", "KR", "TGT", "DG", "DLTR",
    "EL", "HSY", "LLY", "UNH", "JNJ", "ABBV", "MRK", "PFE", "AMGN", "GILD",
    "BMY", "REGN", "VRTX", "BIIB", "MRNA", "ISRG", "SYK", "MDT", "BSX", "ABT",
    "TMO", "DHR", "IQV", "HCA", "CI", "JPM", "BAC", "WFC", "C", "GS", "MS",
    "BLK", "SCHW", "AXP", "V", "MA", "PYPL", "COF", "DFS", "USB", "PNC", "BK",
    "AIG", "TRV", "CB", "PGR", "MET", "PRU", "CME", "ICE", "GE", "CAT", "DE",
    "HON", "RTX", "LMT", "NOC", "GD", "BA", "UPS", "FDX", "UNP", "CSX", "NSC",
    "ETN", "EMR", "PH", "ROK", "MMM", "ITW", "WM", "RSG", "XOM", "CVX", "COP",
    "EOG", "SLB", "HAL", "BKR", "PSX", "VLO", "MPC", "OXY", "DVN", "FANG", "LIN",
    "APD", "SHW", "ECL", "DD", "DOW", "NEM", "FCX", "NUE", "STLD", "VMC", "MLM",
    "PLD", "AMT", "EQIX", "CCI", "SPG", "O", "PSA", "WELL", "DLR", "VICI",
    "CBRE", "AVB", "NEE", "SO", "DUK", "AEP", "EXC", "SRE", "D", "XEL", "PEG",
    "ED",
]

BACKTEST_TICKERS_20: list[str] = [
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
