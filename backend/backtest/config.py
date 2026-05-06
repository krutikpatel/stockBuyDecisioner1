from __future__ import annotations

BACKTEST_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL",
    "JPM", "JNJ", "XOM", "WMT",
    "CRWD", "DKNG", "ENPH", "COIN",
    "MVIS", "PLUG", "ARRY", "CLOV",
    "SPY", "QQQ", "IWM", "GLD",
]

# All sector ETFs that need price data too
SECTOR_ETF_MAP: dict[str, str | None] = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "GOOGL": "XLC",
    "JPM": "XLF", "JNJ": "XLV", "XOM": "XLE", "WMT": "XLP",
    "CRWD": "XLK", "DKNG": "XLY", "ENPH": "XLK", "COIN": "XLF",
    "MVIS": "XLK", "PLUG": "XLE", "ARRY": "XLK", "CLOV": "XLV",
    "SPY": None, "QQQ": None, "IWM": None, "GLD": None,
}

BACKTEST_START = "2024-05-06"   # first Monday on/after 2024-05-01
BACKTEST_END = "2026-05-04"
HISTORY_START = "2022-05-01"   # 3 years of history so 2024 dates have ≥252 rows

# Forward windows in trading days
HOLDING_PERIODS: dict[str, int] = {
    "short_term": 20,
    "medium_term": 65,
    "long_term": 252,
}

HORIZONS = ["short_term", "medium_term", "long_term"]

# Skip a test point if price slice has fewer than this many rows
MIN_ROWS_FOR_ANALYSIS = 252

CACHE_DIR = "backtest_results/cache"
RESULTS_DIR = "backtest_results"

DEFAULT_RISK_PROFILE = "moderate"

BENCHMARK_TICKERS = {"SPY", "QQQ"}
