"""
Aggregates backtest signal records into structured performance metrics.

Public entry point:  build_metrics(signals, horizon) -> dict

Sections produced:
  overall_stats          — aggregate numbers across all decisions
  by_decision            — per decision-label performance
  by_score_bucket        — performance by score range
  by_ticker              — per-stock performance
  by_horizon             — across all 3 horizons (summary)
  monthly_breakdown      — time-series of monthly performance
  portfolio_simulation   — equal-weight buy-signal portfolio vs SPY
  by_regime              — performance per market regime  (Phase 2+)
  by_regime_decision     — regime × decision heatmap     (Phase 2+)
  by_archetype           — performance per stock archetype (Phase 3)
  by_archetype_decision  — archetype × decision table     (Phase 3)
  by_signal_card         — per-card score correlation with returns (Phase 3)
"""
from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd

# Decision label ordering for consistent table display
DECISION_ORDER = [
    # New short-term labels (Story 7)
    "BUY_NOW_MOMENTUM", "BUY_STARTER_STRONG_BUT_EXTENDED",
    "WAIT_FOR_PULLBACK",
    # New medium-term labels
    "BUY_NOW", "BUY_STARTER", "BUY_ON_PULLBACK",
    "WATCHLIST_NEEDS_CONFIRMATION",
    # New long-term labels
    "BUY_NOW_LONG_TERM", "ACCUMULATE_ON_WEAKNESS",
    "WATCHLIST_VALUATION_TOO_RICH",
    # Shared / legacy labels
    "BUY_STARTER_EXTENDED", "BUY_ON_BREAKOUT", "BUY_AFTER_EARNINGS",
    "WATCHLIST", "WATCHLIST_NEEDS_CATALYST", "HOLD_EXISTING_DO_NOT_ADD",
    "AVOID_BAD_BUSINESS", "AVOID_BAD_CHART", "AVOID_LONG_TERM",
    "AVOID_BAD_RISK_REWARD", "AVOID_LOW_CONFIDENCE", "AVOID",
]

SCORE_BUCKETS = [
    (0,   12.5, "0–12 (Very Weak)"),
    (12.5, 25,  "12–25 (Weak)"),
    (25,   37.5, "25–37 (Below Avg)"),
    (37.5, 50,  "37–50 (Below Avg)"),
    (50,   62.5, "50–62 (Average)"),
    (62.5, 75,  "62–75 (Good)"),
    (75,   87.5, "75–87 (Strong)"),
    (87.5, 100.001, "87–100 (Excellent)"),
]

SIGNAL_CARD_NAMES = [
    "momentum", "trend", "entry_timing", "volume_accumulation",
    "volatility_risk", "relative_strength", "growth", "valuation",
    "quality", "ownership", "catalyst",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _perf_row(sub: pd.DataFrame) -> dict:
    """Compute standard performance metrics from a sub-DataFrame."""
    if sub.empty:
        return {}
    n = len(sub)
    resolved = sub[sub["forward_return"].notna()]
    if resolved.empty:
        return {"count": n, "resolved": 0}

    wins      = (resolved["forward_return"] > 0).sum()
    spy_wins  = (
        (resolved["excess_return"] > 0).sum()
        if "excess_return" in resolved.columns and resolved["excess_return"].notna().any()
        else None
    )
    avg_excess = (
        round(resolved["excess_return"].mean(), 2)
        if "excess_return" in resolved.columns and resolved["excess_return"].notna().any()
        else None
    )
    avg_excess_qqq = (
        round(resolved["excess_return_vs_qqq"].mean(), 2)
        if "excess_return_vs_qqq" in resolved.columns and resolved["excess_return_vs_qqq"].notna().any()
        else None
    )
    avg_dd = (
        round(resolved["max_drawdown_period"].mean(), 2)
        if "max_drawdown_period" in resolved.columns and resolved["max_drawdown_period"].notna().any()
        else None
    )

    # Profit factor = sum of gains / |sum of losses|
    gains  = resolved.loc[resolved["forward_return"] > 0, "forward_return"].sum()
    losses = abs(resolved.loc[resolved["forward_return"] < 0, "forward_return"].sum())
    profit_factor = round(gains / losses, 2) if losses > 0 else None

    row: dict = {
        "count":                 n,
        "resolved":              len(resolved),
        "avg_return_pct":        round(resolved["forward_return"].mean(), 2),
        "median_return_pct":     round(resolved["forward_return"].median(), 2),
        "win_rate_pct":          round(wins / len(resolved) * 100, 1),
        "benchmark_win_rate_pct": round(spy_wins / len(resolved) * 100, 1) if spy_wins is not None else None,
        "avg_excess_spy_pct":    avg_excess,
        "avg_excess_qqq_pct":    avg_excess_qqq,
        "avg_max_drawdown_pct":  avg_dd,
        "profit_factor":         profit_factor,
        "best_return_pct":       round(resolved["forward_return"].max(), 2),
        "worst_return_pct":      round(resolved["forward_return"].min(), 2),
    }
    return row


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_metrics(signals: list[dict], horizon: str) -> dict:
    """Build all performance metrics for a single horizon.

    Args:
        signals: List of signal dicts (with outcomes attached).
        horizon: One of "short_term", "medium_term", "long_term".

    Returns:
        Nested dict with all metric sections.
    """
    df_all  = pd.DataFrame(signals)
    df      = df_all[df_all["horizon"] == horizon].copy() if not df_all.empty else pd.DataFrame()
    df_res  = df[df["forward_return"].notna()].copy() if not df.empty else pd.DataFrame()

    # Determine which phases of data are present
    has_regime    = "market_regime" in df_res.columns and df_res["market_regime"].notna().any()
    has_archetype = (
        "archetype" in df_res.columns
        and df_res["archetype"].notna().any()
        and (df_res["archetype"] != "UNKNOWN").any()
    )
    sc_cols = [f"sc_{n}" for n in SIGNAL_CARD_NAMES if f"sc_{n}" in df_res.columns]
    has_signal_cards = len(sc_cols) > 0

    result: dict = {
        "horizon":          horizon,
        "total_signals":    len(df),
        "resolved_signals": len(df_res),
        "overall_stats":    _overall_stats(df_res),
        "by_decision":      _by_decision(df_res),
        "by_score_bucket":  _by_score_bucket(df_res),
        "by_ticker":        _by_ticker(df_res),
        "monthly_breakdown": _monthly_breakdown(df_res),
        "portfolio_simulation": _portfolio_simulation(df_res, horizon),
    }

    # Phase 2+: regime
    if has_regime:
        result["by_regime"]          = _by_regime(df_res)
        result["by_regime_decision"] = _by_regime_decision(df_res)

    # Phase 3: archetype + signal card correlation
    if has_archetype:
        result["by_archetype"]          = _by_archetype(df_res)
        result["by_archetype_decision"] = _by_archetype_decision(df_res)

    if has_signal_cards:
        result["by_signal_card"] = _by_signal_card(df_res, sc_cols)

    return result


def build_all_horizons_metrics(signals: list[dict]) -> dict:
    """Build metrics for all three horizons plus a cross-horizon summary."""
    result = {}
    for horizon in ["short_term", "medium_term", "long_term"]:
        result[horizon] = build_metrics(signals, horizon)
    result["cross_horizon"] = _cross_horizon_summary(signals)
    return result


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _overall_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    wins = (df["forward_return"] > 0).sum()
    row: dict = {
        "total_resolved_signals": len(df),
        "overall_win_rate_pct":   round(wins / len(df) * 100, 1),
        "avg_return_pct":         round(df["forward_return"].mean(), 2),
        "avg_excess_spy_pct":     (
            round(df["excess_return"].mean(), 2)
            if "excess_return" in df.columns and df["excess_return"].notna().any() else None
        ),
        "score_return_correlation": (
            round(float(df["score"].corr(df["forward_return"])), 4)
            if len(df) > 1 else None
        ),
    }
    if len(df) > 0:
        best_idx  = df["forward_return"].idxmax()
        worst_idx = df["forward_return"].idxmin()
        row["best_signal"] = {
            "ticker":     df.loc[best_idx, "ticker"],
            "date":       df.loc[best_idx, "date"],
            "decision":   df.loc[best_idx, "decision"],
            "return_pct": round(df.loc[best_idx, "forward_return"], 2),
        }
        row["worst_signal"] = {
            "ticker":     df.loc[worst_idx, "ticker"],
            "date":       df.loc[worst_idx, "date"],
            "decision":   df.loc[worst_idx, "decision"],
            "return_pct": round(df.loc[worst_idx, "forward_return"], 2),
        }
    return row


def _by_decision(df: pd.DataFrame) -> list[dict]:
    rows = []
    # Include any decisions actually present even if not in the canonical order
    present  = set(df["decision"].unique()) if not df.empty else set()
    ordered  = [d for d in DECISION_ORDER if d in present]
    ordered += sorted(present - set(DECISION_ORDER))  # any unlisted labels

    for decision in ordered:
        sub = df[df["decision"] == decision]
        if sub.empty:
            continue
        row = _perf_row(sub)
        row["decision"] = decision
        rows.append(row)
    return rows


def _by_score_bucket(df: pd.DataFrame) -> list[dict]:
    rows = []
    for lo, hi, label in SCORE_BUCKETS:
        sub = df[(df["score"] >= lo) & (df["score"] < hi)]
        if sub.empty:
            continue
        row = _perf_row(sub)
        row["bucket"]      = label
        row["score_range"] = f"{lo:.0f}–{hi:.0f}"
        rows.append(row)
    return rows


def _by_ticker(df: pd.DataFrame) -> list[dict]:
    rows = []
    for ticker in sorted(df["ticker"].unique()):
        sub  = df[df["ticker"] == ticker]
        row  = _perf_row(sub)
        row["ticker"] = ticker
        row["avg_score"] = round(sub["score"].mean(), 1) if not sub.empty else None
        row["best_decision"] = (
            sub["decision"].mode().iloc[0] if len(sub) > 0 else None
        )
        rows.append(row)
    rows.sort(key=lambda r: r.get("avg_return_pct") or 0, reverse=True)
    return rows


def _by_regime(df: pd.DataFrame) -> list[dict]:
    rows = []
    for regime, group in df.groupby("market_regime"):
        row = _perf_row(group)
        row["regime"] = str(regime)
        rows.append(row)
    rows.sort(key=lambda r: r.get("avg_return_pct") or 0, reverse=True)
    return rows


def _by_regime_decision(df: pd.DataFrame) -> list[dict]:
    """Heatmap data: for each (regime, decision) pair, compute avg excess return."""
    if df.empty:
        return []
    rows = []
    for (regime, decision), group in df.groupby(["market_regime", "decision"]):
        if group.empty:
            continue
        resolved = group[group["forward_return"].notna()]
        if resolved.empty:
            continue
        rows.append({
            "regime":           str(regime),
            "decision":         str(decision),
            "count":            len(resolved),
            "avg_return_pct":   round(resolved["forward_return"].mean(), 2),
            "win_rate_pct":     round((resolved["forward_return"] > 0).sum() / len(resolved) * 100, 1),
            "avg_excess_spy_pct": (
                round(resolved["excess_return"].mean(), 2)
                if "excess_return" in resolved.columns and resolved["excess_return"].notna().any()
                else None
            ),
        })
    return rows


def _by_archetype(df: pd.DataFrame) -> list[dict]:
    rows = []
    for archetype, group in df.groupby("archetype"):
        row = _perf_row(group)
        row["archetype"] = str(archetype)
        row["avg_score"] = round(group["score"].mean(), 1) if not group.empty else None
        row["best_decision"] = (
            group["decision"].mode().iloc[0] if len(group) > 0 else None
        )
        rows.append(row)
    rows.sort(key=lambda r: r.get("avg_return_pct") or 0, reverse=True)
    return rows


def _by_archetype_decision(df: pd.DataFrame) -> list[dict]:
    """For each (archetype, decision) pair, compute avg excess return."""
    if df.empty:
        return []
    rows = []
    for (archetype, decision), group in df.groupby(["archetype", "decision"]):
        resolved = group[group["forward_return"].notna()]
        if len(resolved) < 3:          # skip cells with too few samples
            continue
        rows.append({
            "archetype":      str(archetype),
            "decision":       str(decision),
            "count":          len(resolved),
            "avg_return_pct": round(resolved["forward_return"].mean(), 2),
            "win_rate_pct":   round(
                (resolved["forward_return"] > 0).sum() / len(resolved) * 100, 1
            ),
            "avg_excess_spy_pct": (
                round(resolved["excess_return"].mean(), 2)
                if "excess_return" in resolved.columns and resolved["excess_return"].notna().any()
                else None
            ),
        })
    return rows


def _by_signal_card(df: pd.DataFrame, sc_cols: list[str]) -> list[dict]:
    """For each signal card, compute correlation with forward returns and
    per-quartile average returns."""
    rows = []
    for col in sc_cols:
        card_name = col.replace("sc_", "")
        valid  = df[[col, "forward_return"]].dropna()
        if len(valid) < 10:
            continue

        with np.errstate(divide="ignore", invalid="ignore"):
            raw_corr = valid[col].corr(valid["forward_return"])
        corr_20d = round(float(raw_corr), 4) if pd.notna(raw_corr) else None

        # Per-quartile avg return
        quartile_avgs = {}
        try:
            valid = valid.copy()
            valid["quartile"] = pd.qcut(valid[col], q=4, labels=["Q1 Low", "Q2", "Q3", "Q4 High"])
            for q, g in valid.groupby("quartile", observed=True):
                quartile_avgs[str(q)] = round(g["forward_return"].mean(), 2)
        except Exception:
            pass

        rows.append({
            "card":             card_name,
            "n_signals":        len(valid),
            "corr_with_return": corr_20d,
            "quartile_returns": quartile_avgs,
            "avg_score":        round(float(df[col].mean()), 1) if df[col].notna().any() else None,
        })

    rows.sort(key=lambda r: abs(r.get("corr_with_return") or 0), reverse=True)
    return rows


def _monthly_breakdown(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    df2 = df.copy()
    df2["month"] = pd.to_datetime(df2["date"]).dt.to_period("M")
    rows = []
    buy_labels = {
        "BUY_NOW", "BUY_NOW_MOMENTUM", "BUY_NOW_LONG_TERM",
        "BUY_STARTER", "BUY_STARTER_STRONG_BUT_EXTENDED",
        "ACCUMULATE_ON_WEAKNESS",
    }
    avoid_labels = {"AVOID", "AVOID_BAD_CHART", "AVOID_BAD_BUSINESS", "AVOID_LONG_TERM"}
    for period, group in df2.groupby("month"):
        wins = (group["forward_return"] > 0).sum()
        rows.append({
            "month":          str(period),
            "signals":        len(group),
            "avg_return_pct": round(group["forward_return"].mean(), 2),
            "win_rate_pct":   round(wins / len(group) * 100, 1) if len(group) > 0 else None,
            "buy_signals":    int(group["decision"].isin(buy_labels).sum()),
            "avoid_signals":  int(group["decision"].isin(avoid_labels).sum()),
        })
    return rows


def _portfolio_simulation(df: pd.DataFrame, horizon: str) -> dict:
    """Simulate equal-weight portfolio of all BUY signals vs SPY."""
    buy_labels = {
        "BUY_NOW", "BUY_NOW_MOMENTUM", "BUY_NOW_LONG_TERM",
        "BUY_STARTER", "BUY_STARTER_STRONG_BUT_EXTENDED",
        "ACCUMULATE_ON_WEAKNESS",
    }
    buys = df[df["decision"].isin(buy_labels)].copy()
    if buys.empty:
        return {"total_trades": 0}

    avg_trade = buys["forward_return"].mean()
    avg_spy   = buys["spy_return"].mean() if "spy_return" in buys.columns and buys["spy_return"].notna().any() else None
    wins      = (buys["forward_return"] > 0).sum()

    periods_per_year = {"short_term": 13, "medium_term": 4, "long_term": 1}
    n_per_yr = periods_per_year.get(horizon, 13)

    return {
        "total_trades":            len(buys),
        "avg_trade_return_pct":    round(avg_trade, 2),
        "avg_spy_return_pct":      round(avg_spy, 2) if avg_spy is not None else None,
        "hit_rate_pct":            round(wins / len(buys) * 100, 1),
        "model_annualized_return_pct": round(avg_trade * n_per_yr, 2) if pd.notna(avg_trade) else None,
        "spy_annualized_return_pct":   round(avg_spy * n_per_yr, 2) if avg_spy is not None else None,
        "alpha_pct": (
            round(avg_trade * n_per_yr - avg_spy * n_per_yr, 2)
            if avg_spy is not None and pd.notna(avg_trade) else None
        ),
    }


def _cross_horizon_summary(signals: list[dict]) -> list[dict]:
    """Brief comparison across horizons: avg return, win rate, signal count."""
    if not signals:
        return []
    df = pd.DataFrame(signals)
    rows = []
    for horizon in ["short_term", "medium_term", "long_term"]:
        sub = df[(df["horizon"] == horizon) & (df["forward_return"].notna())]
        if sub.empty:
            continue
        wins = (sub["forward_return"] > 0).sum()
        rows.append({
            "horizon":        horizon,
            "count":          len(sub),
            "avg_return_pct": round(sub["forward_return"].mean(), 2),
            "win_rate_pct":   round(wins / len(sub) * 100, 1),
            "avg_excess_spy": (
                round(sub["excess_return"].mean(), 2)
                if "excess_return" in sub.columns and sub["excess_return"].notna().any()
                else None
            ),
        })
    return rows
