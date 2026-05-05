"""
Aggregates backtest signals into human-readable metrics.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd

DECISION_ORDER = [
    "BUY_NOW", "BUY_STARTER", "BUY_ON_BREAKOUT",
    "WAIT_FOR_PULLBACK", "WATCHLIST", "AVOID",
]

SCORE_BUCKETS = [
    (0, 40, "0–40 (Weak)"),
    (40, 55, "40–55 (Below avg)"),
    (55, 70, "55–70 (Average)"),
    (70, 85, "70–85 (Good)"),
    (85, 100, "85–100 (Strong)"),
]


def _fmt(val, suffix="", decimals=1) -> str:
    if val is None or (isinstance(val, float) and val != val):
        return "N/A"
    return f"{val:.{decimals}f}{suffix}"


def build_metrics(signals: list[dict], horizon: str = "short_term") -> dict:
    """
    Compute all summary metrics for a given horizon.
    Returns a dict with keys: by_decision, by_score_bucket, by_ticker,
    monthly_breakdown, portfolio_simulation, overall_stats.
    """
    df = pd.DataFrame(signals)
    df = df[df["horizon"] == horizon].copy()
    df_resolved = df[df["forward_return"].notna()].copy()

    result = {
        "horizon": horizon,
        "total_signals": len(df),
        "resolved_signals": len(df_resolved),
        "by_decision": _by_decision(df_resolved),
        "by_score_bucket": _by_score_bucket(df_resolved),
        "by_ticker": _by_ticker(df_resolved),
        "monthly_breakdown": _monthly_breakdown(df_resolved),
        "portfolio_simulation": _portfolio_simulation(df_resolved),
        "overall_stats": _overall_stats(df_resolved),
    }
    return result


def _by_decision(df: pd.DataFrame) -> list[dict]:
    rows = []
    for decision in DECISION_ORDER:
        sub = df[df["decision"] == decision]
        if len(sub) == 0:
            continue
        wins = (sub["forward_return"] > 0).sum()
        rows.append({
            "decision": decision,
            "count": len(sub),
            "avg_return_pct": round(sub["forward_return"].mean(), 2),
            "median_return_pct": round(sub["forward_return"].median(), 2),
            "win_rate_pct": round(wins / len(sub) * 100, 1),
            "avg_excess_vs_spy_pct": round(sub["excess_return"].mean(), 2) if sub["excess_return"].notna().any() else None,
            "best_return_pct": round(sub["forward_return"].max(), 2),
            "worst_return_pct": round(sub["forward_return"].min(), 2),
        })
    return rows


def _by_score_bucket(df: pd.DataFrame) -> list[dict]:
    rows = []
    for lo, hi, label in SCORE_BUCKETS:
        sub = df[(df["score"] >= lo) & (df["score"] < hi)]
        if len(sub) == 0:
            continue
        wins = (sub["forward_return"] > 0).sum()
        rows.append({
            "bucket": label,
            "score_range": f"{lo}–{hi}",
            "count": len(sub),
            "avg_return_pct": round(sub["forward_return"].mean(), 2),
            "win_rate_pct": round(wins / len(sub) * 100, 1),
            "avg_excess_vs_spy_pct": round(sub["excess_return"].mean(), 2) if sub["excess_return"].notna().any() else None,
        })
    return rows


def _by_ticker(df: pd.DataFrame) -> list[dict]:
    rows = []
    for ticker in sorted(df["ticker"].unique()):
        sub = df[df["ticker"] == ticker]
        wins = (sub["forward_return"] > 0).sum()
        rows.append({
            "ticker": ticker,
            "signals": len(sub),
            "avg_score": round(sub["score"].mean(), 1),
            "avg_return_pct": round(sub["forward_return"].mean(), 2),
            "win_rate_pct": round(wins / len(sub) * 100, 1) if len(sub) > 0 else None,
            "avg_excess_vs_spy_pct": round(sub["excess_return"].mean(), 2) if sub["excess_return"].notna().any() else None,
            "best_decision": sub["decision"].mode().iloc[0] if len(sub) > 0 else None,
        })
    rows.sort(key=lambda r: r["avg_return_pct"] or 0, reverse=True)
    return rows


def _monthly_breakdown(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    df = df.copy()
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    rows = []
    for period, group in df.groupby("month"):
        wins = (group["forward_return"] > 0).sum()
        rows.append({
            "month": str(period),
            "signals": len(group),
            "avg_return_pct": round(group["forward_return"].mean(), 2),
            "win_rate_pct": round(wins / len(group) * 100, 1) if len(group) > 0 else None,
            "buy_signals": int((group["decision"].isin(["BUY_NOW", "BUY_STARTER"])).sum()),
            "avoid_signals": int((group["decision"] == "AVOID").sum()),
        })
    return rows


def _portfolio_simulation(df: pd.DataFrame) -> dict:
    """
    Simulate equal-weight $1 invested at each BUY_NOW / BUY_STARTER signal.
    Compare final value vs. avg SPY return over the same signals.
    """
    buy_signals = df[df["decision"].isin(["BUY_NOW", "BUY_STARTER"])].copy()

    if buy_signals.empty:
        return {"total_trades": 0, "model_cagr_pct": None, "spy_cagr_pct": None, "hit_rate_pct": None}

    # Simple arithmetic: mean of individual trade returns
    avg_trade_return = buy_signals["forward_return"].mean()
    avg_spy_return = buy_signals["spy_return"].mean() if buy_signals["spy_return"].notna().any() else None
    wins = (buy_signals["forward_return"] > 0).sum()

    # Approximate CAGR from mean return per period
    # Short-term: ~13 periods per year, medium-term: ~4, long-term: ~1
    periods_per_year = {"short_term": 13, "medium_term": 4, "long_term": 1}
    horizon = df["horizon"].iloc[0] if not df.empty else "short_term"
    n_per_year = periods_per_year.get(horizon, 13)

    model_cagr = None
    spy_cagr = None
    if avg_trade_return is not None:
        model_cagr = round(avg_trade_return * n_per_year, 2)
    if avg_spy_return is not None:
        spy_cagr = round(avg_spy_return * n_per_year, 2)

    return {
        "total_trades": len(buy_signals),
        "avg_trade_return_pct": round(avg_trade_return, 2) if avg_trade_return == avg_trade_return else None,
        "avg_spy_return_pct": round(avg_spy_return, 2) if avg_spy_return and avg_spy_return == avg_spy_return else None,
        "hit_rate_pct": round(wins / len(buy_signals) * 100, 1),
        "model_annualized_return_pct": model_cagr,
        "spy_annualized_return_pct": spy_cagr,
        "alpha_pct": round(model_cagr - spy_cagr, 2) if (model_cagr and spy_cagr) else None,
    }


def _overall_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    wins = (df["forward_return"] > 0).sum()
    return {
        "total_resolved_signals": len(df),
        "overall_win_rate_pct": round(wins / len(df) * 100, 1),
        "avg_return_pct": round(df["forward_return"].mean(), 2),
        "avg_excess_vs_spy_pct": round(df["excess_return"].mean(), 2) if df["excess_return"].notna().any() else None,
        "score_return_correlation": round(df["score"].corr(df["forward_return"]), 4) if len(df) > 1 else None,
        "best_signal": {
            "ticker": df.loc[df["forward_return"].idxmax(), "ticker"],
            "date": df.loc[df["forward_return"].idxmax(), "date"],
            "decision": df.loc[df["forward_return"].idxmax(), "decision"],
            "return_pct": round(df["forward_return"].max(), 2),
        } if len(df) > 0 else None,
        "worst_signal": {
            "ticker": df.loc[df["forward_return"].idxmin(), "ticker"],
            "date": df.loc[df["forward_return"].idxmin(), "date"],
            "decision": df.loc[df["forward_return"].idxmin(), "decision"],
            "return_pct": round(df["forward_return"].min(), 2),
        } if len(df) > 0 else None,
    }
