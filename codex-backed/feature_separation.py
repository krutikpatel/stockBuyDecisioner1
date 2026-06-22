#!/usr/bin/env python3
"""
feature_separation.py — Which of your 75 features actually separate WINNERS from
LOSERS? Evidence before knobs.

You have 75 features in cache/features.pkl but your entry configs score on ~14,
all trend/momentum/RS. This tool measures, on your REAL historical trades, which
features predict outcome — so you add params based on evidence, not intuition,
and discover which currently-used features are dead weight.

METHOD (deliberately simple, robust, non-overfitting):
For each numeric feature, split trades into the feature's quintiles and measure
win rate + median return per quintile. A feature SEPARATES if outcome rises (or
falls) monotonically across quintiles and the top-vs-bottom gap is meaningful.
We rank features by:
  - AUC-style rank correlation between feature value and a binary win flag
    (Mann-Whitney; 0.5 = no separation, >0.5 feature high => win, <0.5 => lose)
  - top-minus-bottom-quintile win-rate spread
  - monotonicity across quintiles
Categorical features (sector, trend_label, market_regime) get a group win-rate
breakdown instead.

It also reports each feature's CORRELATION to the features you ALREADY use, so
you can tell "new orthogonal signal" from "another trend proxy".

INPUTS:
  --decisions entry_decisions.csv   (ticker,date,horizon,...,setup,label,regime)
  --features   features.pkl          (75-col snapshot, keyed ticker,date,horizon)
  --trades     trades.csv            (the realized outcomes: realized_return_pct)
Join keys: (ticker, date/signal_date, horizon).

USAGE:
  python3 feature_separation.py --trades results/<run>/trades.csv \
      --features cache/features.pkl [--decisions results/<run>/entry_decisions.csv] \
      --win-threshold 0 --exclude-crash 2020-03-01:2020-05-31 --out feature_report.csv
"""
import argparse, sys
import numpy as np
import pandas as pd

# features your entry configs ALREADY score on — used to flag redundancy
USED = {"rsi14","rsi_slope","sma50_relative","sma50_slope","sma20_relative",
        "rs_vs_spy_20d","trend_label","market_regime","dist_from_52w_high",
        "dist_from_20d_high","breakout_volume_multiple","volume_dryup_ratio",
        "updown_volume_ratio","perf_1w"}

NON_FEATURE = {"ticker","date","signal_date","horizon","price","entry_date",
               "exit_date","exit_reason","realized_return_pct","__win__",
               "primary_category","archetype","entry_index","exit_index"}

def parse_date(s): return pd.to_datetime(s).dt.date

def load_any(path):
    if path.endswith(".pkl"):
        obj = pd.read_pickle(path)
        if isinstance(obj, dict) and "rows" in obj:
            return pd.DataFrame(obj["rows"])
        return obj
    return pd.read_csv(path)

def mann_whitney_auc(values, wins):
    """AUC = P(feature higher for a win than for a loss). 0.5 = no signal."""
    v = np.asarray(values, float); w = np.asarray(wins, bool)
    pos, neg = v[w], v[~w]
    if len(pos) == 0 or len(neg) == 0: return np.nan
    # rank-based AUC (handles ties)
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order), float); ranks[order] = np.arange(1, len(order)+1)
    r_pos = ranks[:len(pos)].sum()
    auc = (r_pos - len(pos)*(len(pos)+1)/2) / (len(pos)*len(neg))
    return auc

def quintile_table(df, feat, ret="realized_return_pct"):
    s = df[[feat, ret, "__win__"]].dropna()
    if s[feat].nunique() < 5 or len(s) < 25: return None
    try:
        s["q"] = pd.qcut(s[feat], 5, labels=False, duplicates="drop")
    except ValueError:
        return None
    g = s.groupby("q").agg(n=("__win__","size"),
                           win=("__win__","mean"),
                           med=(ret,"median"),
                           favg=(feat,"mean"))
    return g

def monotonic(winrates):
    d = np.diff(winrates)
    return bool(np.all(d >= -1e-9) or np.all(d <= 1e-9))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", required=True)
    ap.add_argument("--features", required=True)
    ap.add_argument("--decisions")
    ap.add_argument("--win-threshold", type=float, default=0.0,
                    help="return%% above this = win (default 0)")
    ap.add_argument("--exclude-crash", action="append", default=[])
    ap.add_argument("--out", default="feature_report.csv")
    a = ap.parse_args()

    trades = load_any(a.trades)
    feats = load_any(a.features)

    # normalize join keys
    for df in (trades, feats):
        if "signal_date" in df and "date" not in df: df["date"] = df["signal_date"]
    # trades use entry_date as the snapshot date if no signal_date
    if "signal_date" in trades:
        trades["join_date"] = pd.to_datetime(trades["signal_date"])
    else:
        trades["join_date"] = pd.to_datetime(trades["entry_date"])
    feats["join_date"] = pd.to_datetime(feats["date"])

    keys = ["ticker","join_date"] + (["horizon"] if "horizon" in trades and "horizon" in feats else [])
    df = trades.merge(feats, on=keys, how="left", suffixes=("","_feat"))

    matched = df["sma50_relative"].notna().mean() if "sma50_relative" in df else 0
    print(f"Joined {len(trades)} trades to features; "
          f"{matched*100:.0f}% matched a snapshot.")
    if matched < 0.5:
        print("WARNING: <50% of trades matched a feature snapshot — check join keys "
              "(ticker/date/horizon formats).")

    # crash exclusion by entry date
    for w in a.exclude_crash:
        lo, hi = pd.to_datetime(w.split(":")[0]), pd.to_datetime(w.split(":")[1])
        ed = pd.to_datetime(df["entry_date"])
        df = df[~((ed >= lo) & (ed <= hi))]
    df["__win__"] = df["realized_return_pct"] > a.win_threshold
    base_wr = df["__win__"].mean()
    print(f"Analyzing {len(df)} trades (crash-excluded). "
          f"Base win rate: {base_wr*100:.1f}%\n")

    # numeric feature columns
    num = [c for c in df.columns
           if c not in NON_FEATURE and pd.api.types.is_numeric_dtype(df[c])
           and df[c].notna().sum() >= 25]

    rows = []
    used_vecs = {u: df[u] for u in USED if u in df and
                 pd.api.types.is_numeric_dtype(df[u])}
    for feat in num:
        sub = df[[feat,"realized_return_pct","__win__"]].dropna()
        if len(sub) < 25: continue
        auc = mann_whitney_auc(sub[feat], sub["__win__"])
        if np.isnan(auc): continue
        qt = quintile_table(df, feat)
        if qt is None or len(qt) < 3: 
            top_bot = np.nan; mono = False
        else:
            top_bot = (qt["win"].iloc[-1] - qt["win"].iloc[0]) * 100
            mono = monotonic(qt["win"].values)
        # max correlation to an already-used feature (redundancy)
        maxcorr, corr_with = 0.0, ""
        for u, uv in used_vecs.items():
            if u == feat: continue
            c = df[[feat]].join(uv.rename("u")).dropna()
            if len(c) > 25:
                r = abs(c[feat].corr(c["u"]))
                if r > maxcorr: maxcorr, corr_with = r, u
        rows.append({
            "feature": feat,
            "auc": round(auc,3),
            "separation": round(abs(auc-0.5)*2,3),   # 0=none,1=perfect
            "top_minus_bottom_winrate_pts": (round(top_bot,1)
                                             if not np.isnan(top_bot) else None),
            "monotonic": mono,
            "n": len(sub),
            "already_used": feat in USED,
            "max_corr_to_used": round(maxcorr,2),
            "most_corr_with": corr_with,
            "orthogonal": maxcorr < 0.5,
        })

    rep = pd.DataFrame(rows).sort_values("separation", ascending=False)
    rep.to_csv(a.out, index=False)

    def show(title, sub):
        print(title)
        if sub.empty: print("  (none)\n"); return
        for _, r in sub.iterrows():
            tag = []
            if r["already_used"]: tag.append("USED")
            if r["orthogonal"]: tag.append("ORTHOGONAL")
            dirn = "high→win" if r["auc"]>0.5 else "low→win"
            print(f"  {r['feature']:<26} sep={r['separation']:.2f} "
                  f"AUC={r['auc']:.2f} ({dirn})  "
                  f"top-bot={r['top_minus_bottom_winrate_pts']}pts  "
                  f"corr2used={r['max_corr_to_used']:.2f}"
                  f"{'('+r['most_corr_with']+')' if r['most_corr_with'] else ''}  "
                  f"{' '.join(tag)}")
        print()

    strong = rep[rep["separation"] >= 0.15]
    print("=== TOP SEPARATORS (sep >= 0.15) ===")
    show("", strong.head(20))

    print("=== HIGH-VALUE UNUSED + ORTHOGONAL (add these first) ===")
    cand = rep[(~rep["already_used"]) & (rep["orthogonal"]) &
               (rep["separation"] >= 0.12)]
    show("", cand.head(15))

    print("=== ALREADY-USED FEATURES THAT DON'T SEPARATE (candidates to drop) ===")
    dead = rep[(rep["already_used"]) & (rep["separation"] < 0.08)]
    show("", dead)

    # categorical breakdowns
    print("=== CATEGORICAL WIN-RATE BREAKDOWN ===")
    for cat in ("sector","trend_label","market_regime","selected_setup"):
        if cat in df and df[cat].notna().any():
            g = df.groupby(cat)["__win__"].agg(["mean","size"])
            g = g[g["size"] >= 10].sort_values("mean", ascending=False)
            if len(g):
                print(f"  [{cat}]")
                for idx, r in g.iterrows():
                    print(f"     {str(idx):<22} win={r['mean']*100:>5.1f}%  n={int(r['size'])}")
        print()

    print(f"Full ranked table written to {a.out}")
    print("\nREAD: features with high 'separation' AND orthogonal=True AND not "
          "already used are your highest-value additions. 'sep' near 0 means the "
          "feature is noise for outcome — including ones you already score on.")

if __name__ == "__main__":
    main()