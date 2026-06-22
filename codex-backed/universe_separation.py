#!/usr/bin/env python3
"""
universe_separation.py — UNBIASED feature edge test across the WHOLE universe.

The trade-level feature_separation.py only saw stocks your entries already picked
(a biased sample). This asks the prior question: across ALL 306k (ticker,date)
snapshots, does a feature predict FORWARD return — independent of your strategy?

This decides Path A (salvage technical thesis) vs Path B (quality-first rethink):
if quality/ownership/analyst features separate forward returns ACROSS THE UNIVERSE
while your technical stack does not, the edge lives in fundamentals, not technicals.

WHAT IT DOES
------------
1. Computes forward return per snapshot, WITHIN ticker, by looking ahead `--fwd-days`
   trading rows in that ticker's own date-sorted series. (No cross-ticker leakage.)
2. To kill overlapping-window autocorrelation, it SUBSAMPLES to non-overlapping
   snapshots per ticker (one every `--fwd-days` rows) before scoring.
3. For each numeric feature: AUC vs "forward return > median" (universe-relative,
   so we measure RELATIVE edge, not just market beta), top-vs-bottom decile spread,
   and a monotonic decile table.
4. Splits the test TRAIN (<= --split-date) vs RECENT (> --split-date) so you can
   see whether a feature's edge SURVIVED into recent regimes — the thing that
   killed your strategy.

CRITICAL: only features known AT snapshot time are valid. We hard-exclude any
outcome-derived columns. 'price' is used only to compute forward return, never scored.

USAGE
-----
  python3 universe_separation.py --features cache/features.pkl \
      --fwd-days 60 --horizon short_term \
      --split-date 2021-12-31 --out universe_report.csv
"""
import argparse, sys
import numpy as np
import pandas as pd

# never valid as predictors (identity, outcome-derived, or the price used for label)
EXCLUDE = {
    "ticker","date","horizon","price","primary_category","archetype",
    # outcome / trade-derived if they ever appear in a snapshot export:
    "realized_return_pct","mfe_pct","mae_pct","mfe_capture_pct","days_held",
    "target_1_hit","partial_exit_pct","position_size_multiplier","entry_wait_days",
    "fwd_return","fwd_return_rel","__win__","is_extended",
}
# the technical cluster you currently lean on (to contrast vs fundamentals)
TECH = {"rsi14","rsi_slope","sma20_relative","sma50_relative","sma200_relative",
        "sma20_slope","sma50_slope","sma200_slope","rs_vs_spy","rs_vs_spy_20d",
        "rs_vs_spy_63d","dist_from_20d_high","dist_from_52w_high","perf_1w",
        "perf_1m","perf_3m","perf_6m","perf_1y","extension_pct_above_20ma",
        "extension_pct_above_50ma","max_drawdown_3m","max_drawdown_1y"}
FUND = {"sales_growth_yoy","sales_growth_qoq","eps_growth_yoy","eps_growth_next_year",
        "eps_growth_3y","eps_growth_5y","gross_margin","operating_margin","net_margin",
        "free_cash_flow","roic","roe","roa","debt_to_equity","current_ratio",
        "forward_pe","trailing_pe","peg_ratio","price_to_sales","ev_to_ebitda",
        "price_to_fcf","fcf_yield","ev_sales","beat_rate","avg_eps_surprise_pct",
        "insider_ownership","institutional_ownership","short_float",
        "analyst_recommendation","analyst_target_price"}

def auc(values, wins):
    v = np.asarray(values, float); w = np.asarray(wins, bool)
    pos, neg = v[w], v[~w]
    if len(pos) < 10 or len(neg) < 10: return np.nan
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order), float); ranks[order] = np.arange(1, len(order)+1)
    return (ranks[:len(pos)].sum() - len(pos)*(len(pos)+1)/2)/(len(pos)*len(neg))

def fwd_returns(df, fwd_days):
    """Within-ticker forward return over fwd_days rows; subsample non-overlapping."""
    df = df.sort_values(["ticker","date"]).copy()
    out = []
    for tk, g in df.groupby("ticker", sort=False):
        g = g.reset_index(drop=True)
        if len(g) <= fwd_days: continue
        fut = g["price"].shift(-fwd_days)
        g["fwd_return"] = (fut / g["price"] - 1.0) * 100.0
        g = g.iloc[::fwd_days]            # non-overlapping windows only
        out.append(g)
    if not out: sys.exit("no ticker had enough history for fwd-days")
    return pd.concat(out, ignore_index=True).dropna(subset=["fwd_return"])

def score_block(df, feats, min_n=200):
    # universe-relative win = beat the cross-sectional median forward return
    df = df.copy()
    df["__win__"] = df["fwd_return"] > df["fwd_return"].median()
    rows = []
    for f in feats:
        s = df[[f,"fwd_return","__win__"]].dropna()
        if len(s) < min_n: continue
        a = auc(s[f], s["__win__"])
        if np.isnan(a): continue
        try:
            s["d"] = pd.qcut(s[f], 10, labels=False, duplicates="drop")
            dec = s.groupby("d")["__win__"].mean()
            spread = (dec.iloc[-1]-dec.iloc[0])*100 if len(dec)>=2 else np.nan
            mono = bool(np.all(np.diff(dec.values)>=-1e-9) or
                        np.all(np.diff(dec.values)<=1e-9))
        except ValueError:
            spread, mono = np.nan, False
        grp = "TECH" if f in TECH else ("FUND" if f in FUND else "OTHER")
        rows.append({"feature":f,"group":grp,"auc":round(a,3),
                     "separation":round(abs(a-0.5)*2,3),
                     "top_bot_decile_pts":(round(spread,1) if not np.isnan(spread) else None),
                     "monotonic":mono,"n":len(s)})
    return pd.DataFrame(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--fwd-days", type=int, default=60)
    ap.add_argument("--horizon", default=None, help="filter to one horizon if present")
    ap.add_argument("--split-date", default="2021-12-31")
    ap.add_argument("--out", default="universe_report.csv")
    a = ap.parse_args()

    raw = pd.read_pickle(a.features)
    df = pd.DataFrame(raw["rows"]) if isinstance(raw, dict) and "rows" in raw else raw
    df["date"] = pd.to_datetime(df["date"])
    if a.horizon and "horizon" in df:
        df = df[df["horizon"] == a.horizon]
    print(f"Loaded {len(df):,} snapshots"
          + (f" (horizon={a.horizon})" if a.horizon else "")
          + f"; tickers={df['ticker'].nunique()}, "
          f"dates {df['date'].min().date()}..{df['date'].max().date()}")

    fr = fwd_returns(df, a.fwd_days)
    print(f"Non-overlapping forward-return samples ({a.fwd_days}d): {len(fr):,}")

    feats = [c for c in fr.columns if c not in EXCLUDE
             and pd.api.types.is_numeric_dtype(fr[c]) and fr[c].notna().sum() >= 200]

    split = pd.to_datetime(a.split_date)
    recent_n = len(fr[fr["date"]>split])
    recent_min_n = max(30, recent_n // 6)
    full = score_block(fr, feats); full["window"]="ALL"
    early = score_block(fr[fr["date"]<=split], feats); early["window"]="TRAIN"
    recent = score_block(fr[fr["date"]>split], feats, min_n=recent_min_n); recent["window"]="RECENT"

    rep = full.merge(early[["feature","auc","separation"]], on="feature",
                     how="left", suffixes=("","_train"))
    if not recent.empty:
        rep = rep.merge(recent[["feature","auc","separation"]], on="feature",
                        how="left", suffixes=("","_recent"))
    else:
        rep["auc_recent"] = float("nan")
        rep["separation_recent"] = float("nan")
        print(f"WARNING: recent window only {recent_n} samples — RECENT_AUC not computed.")
    rep = rep.sort_values("separation", ascending=False)
    rep.to_csv(a.out, index=False)

    def show(title, sub):
        print(title)
        if sub.empty: print("  (none)\n"); return
        for _,r in sub.iterrows():
            dirn = "high→win" if r["auc"]>0.5 else "low→win"
            auc_r = r.get("auc_recent", float("nan"))
            if pd.isna(auc_r):
                recent_str = "RECENT_AUC=n/a  N/A"
            else:
                survived = abs(auc_r-0.5)>=0.04 and ((auc_r-0.5)*(r["auc"]-0.5)>0)
                recent_str = f"RECENT_AUC={auc_r:.2f} {'SURVIVED' if survived else 'DECAYED'}"
            train_auc = r.get("auc_train", float("nan"))
            train_str = f"TRAIN_AUC={train_auc:.2f}" if not pd.isna(train_auc) else "TRAIN_AUC=n/a"
            print(f"  {r['feature']:<24} [{r['group']:<5}] "
                  f"AUC={r['auc']:.2f}({dirn}) sep={r['separation']:.2f} "
                  f"decile_spread={r['top_bot_decile_pts']}pts | "
                  f"{train_str} {recent_str}")
        print()

    print(f"\nUniverse base: forward-return > universe median = ~50% by construction.\n")
    print("=== TOP UNIVERSE SEPARATORS (any group) ===")
    show("", rep.head(20))
    print("=== FUNDAMENTAL/QUALITY FEATURES (Path B evidence) ===")
    show("", rep[rep["group"]=="FUND"].head(20))
    print("=== TECHNICAL FEATURES (Path A evidence) ===")
    show("", rep[rep["group"]=="TECH"].head(20))

    print("READ: a feature with sep>=0.10 AND 'SURVIVED' (edge present in RECENT "
          "window, same direction) is a real, durable, universe-wide signal. If the "
          "FUND block has survivors and the TECH block does not, the edge is "
          "fundamental — Path B. Full table -> " + a.out)

if __name__ == "__main__":
    main()