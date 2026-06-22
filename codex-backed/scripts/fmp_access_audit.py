"""FMP free-key access audit.

Probes the FMP /stable/ endpoints for each ticker in the backtest universe and
reports which tickers are accessible, which are blocked by plan limits (402),
and at what point the rate limit is hit (429).  Stops immediately on 429 to
avoid burning quota on an exhausted key.

Usage (run from repo root):
    set -a; source .env; set +a
    python codex-backed/scripts/fmp_access_audit.py

Optional flags:
    --max N       Probe at most N tickers (default: all)
    --delay S     Sleep S seconds between requests (default: 0.25)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

_BASE = "https://financialmodelingprep.com/stable"
_UNIVERSE_CFG = Path(__file__).resolve().parents[1] / "configs" / "backtest_ticker_universe_config.json"


def _probe_ticker(ticker: str, api_key: str) -> dict[str, int]:
    """Returns {endpoint_name: status_code} for price and two fundamentals calls."""
    results: dict[str, int] = {}
    probes = [
        ("price", f"{_BASE}/historical-price-eod/full", {"symbol": ticker, "from": "2024-01-01", "to": "2024-01-05", "apikey": api_key}),
        ("key_metrics", f"{_BASE}/key-metrics", {"symbol": ticker, "apikey": api_key}),
        ("ratios", f"{_BASE}/ratios", {"symbol": ticker, "apikey": api_key}),
    ]
    for name, url, params in probes:
        try:
            resp = requests.get(url, params=params, timeout=10.0)
            results[name] = resp.status_code
        except requests.RequestException as exc:
            results[name] = -1
            print(f"  [{ticker}] {name}: network error — {exc}", file=sys.stderr)
        if results[name] == 429:
            break  # stop probing this ticker; outer loop will also stop
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="FMP free-key access audit")
    parser.add_argument("--max", type=int, default=None, metavar="N", help="Probe at most N tickers")
    parser.add_argument("--delay", type=float, default=0.25, metavar="S", help="Seconds between requests")
    args = parser.parse_args()

    api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        print("ERROR: FMP_API_KEY not set. Run: set -a; source .env; set +a", file=sys.stderr)
        sys.exit(1)

    universe_raw = json.loads(_UNIVERSE_CFG.read_text())
    tickers: list[str] = universe_raw if isinstance(universe_raw, list) else universe_raw.get("tickers", list(universe_raw.keys()))
    if args.max:
        tickers = tickers[: args.max]

    print(f"Probing {len(tickers)} tickers against FMP /stable/ endpoints …\n")

    accessible: list[str] = []
    blocked_402: list[str] = []
    blocked_429_at: str | None = None
    errors: dict[str, dict[str, int]] = {}

    for i, ticker in enumerate(tickers, 1):
        results = _probe_ticker(ticker, api_key)
        price_status = results.get("price", -1)
        km_status = results.get("key_metrics", -1)
        ratios_status = results.get("ratios", -1)
        tag = f"{i:3d}/{len(tickers)}  {ticker:<8}"

        if 429 in results.values():
            blocked_429_at = ticker
            print(f"{tag} RATE-LIMITED (429) — stopping probe")
            break

        if price_status == 200 and km_status == 200:
            accessible.append(ticker)
            print(f"{tag} OK (price={price_status} key_metrics={km_status} ratios={ratios_status})")
        elif price_status == 402 or km_status == 402:
            blocked_402.append(ticker)
            print(f"{tag} PLAN-LIMIT (price={price_status} key_metrics={km_status} ratios={ratios_status})")
        else:
            errors[ticker] = results
            print(f"{tag} OTHER (price={price_status} key_metrics={km_status} ratios={ratios_status})")

        if i < len(tickers):
            time.sleep(args.delay)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Accessible (200 on price + key_metrics): {len(accessible)}")
    if accessible:
        print("  " + ", ".join(accessible))

    print(f"\nBlocked by plan limit (402): {len(blocked_402)}")
    if blocked_402:
        print("  " + ", ".join(blocked_402))

    if blocked_429_at:
        probed = len(accessible) + len(blocked_402) + len(errors) + 1
        print(f"\nRate limit (429) hit at ticker {blocked_429_at} (probe #{probed})")
        print("  Remaining tickers were not probed.")

    if errors:
        print(f"\nOther errors: {len(errors)}")
        for t, r in errors.items():
            print(f"  {t}: {r}")

    print("\nConclusion:")
    if not accessible:
        print("  No tickers accessible under the current FMP key/plan.")
        print("  S4.3 cannot pass on this key. Options:")
        print("  1. Upgrade to an FMP plan with broader symbol coverage.")
        print("  2. Keep active_mode=legacy_yfinance and document the limitation.")
    elif len(accessible) < 5:
        print(f"  Only {len(accessible)} ticker(s) accessible. The full activation universe")
        print("  cannot be covered; S4.3 requires 80% field population across all rows.")
        print("  A free-key smoke test on these tickers can validate provider integration,")
        print("  but S4.3 activation requires a paid/higher-tier FMP plan.")
    else:
        print(f"  {len(accessible)} tickers accessible. Consider checking if this subset")
        print("  can cover enough rows to pass the 80% fundamentals threshold.")


if __name__ == "__main__":
    main()
