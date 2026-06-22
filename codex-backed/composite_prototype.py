#!/usr/bin/env python3
"""
composite_prototype.py — Does a QUALITY-VALUE COMPOSITE separate forward returns
better than any single feature, and how many INDEPENDENT bets do you really have?

This is the engine prototype for the quality-first strategy, evaluated on unbiased
universe data BEFORE writing any config rule. It does three things:

1. CLUSTER: correlation-cluster the candidate features so you see how many
   independent axes exist (ROIC/ROA/margins are probably ONE quality factor, not
   four). You pick one representative per cluster -> that's your real bet count.

2. COMPOSITE (honest): build a cross-sectional z-score composite from the chosen
   representatives. Weights/normalization are FIT ON TRAIN ONLY, then applied
   unchanged to RECENT. Test whether the composite's top-decile beats bottom-decile
   forward return — in TRAIN and (the real test) in RECENT.

3. FILTER: re-test the composite with an earnings-proximity exclusion to confirm
   avoiding pre-earnings entries helps.

Forward returns computed within-ticker, non-overlapping (same as universe_separation).

CANDIDATES default to the durable quality/growth survivors. Edit --candidates to taste.
By default we LEAN ON QUALITY (roic/roa/margins/growth), treat valuation as optional,
because "expensive wins" is regime-dependent.

USAGE:
  python3 composite_prototype.py --features cache/features.pkl \
      --fwd-days 60 --horizon short_term --split-date 2021-12-31 \
      --candidates roic roa gross_margin net_margin sales_growth_yoy eps_growth_yoy \
      --earnings-flag earnings_within_30_days --out composite_report.csv
"""
import argparse, sys
import numpy as np
import pandas as pd

DEFAULT_CANDIDATES = ["roic","roa","gross_margin","operating_margin","net_margin",
                      "sales_growth_yoy","eps_growth_yoy","roe"]

def fwd_returns(df, fwd_days):
    df = df.sort_values(["ticker","date"]).copy()
    out=[]
    for tk,g in df.groupby("ticker", sort=False):
        g=g.reset_index(drop=True)
        if len(g)<=fwd_days: continue
        g["fwd_return"]=(g["price"].shift(-fwd_days)/g["price"]-1)*100
        out.append(g.iloc[::fwd_days])
    return pd.concat(out, ignore_index=True).dropna(subset=["fwd_return"])

def xs_zscore(df, col):
    """cross-sectional z-score by date (rank within each day's universe)."""
    def z(s):
        sd=s.std()
        return (s-s.mean())/sd if sd>1e-9 else s*0.0
    return df.groupby("date")[col].transform(z)

def decile_spread(sub, score_col):
    s=sub[[score_col,"fwd_return"]].dropna()
    if len(s)<100: return None
    try: s["d"]=pd.qcut(s[score_col],10,labels=False,duplicates="drop")
    except ValueError: return None
    g=s.groupby("d")["fwd_return"].median()
    if len(g)<2: return None
    return {"top_decile_med": round(g.iloc[-1],2),
            "bottom_decile_med": round(g.iloc[0],2),
            "spread_pts": round(g.iloc[-1]-g.iloc[0],2),
            "monotonic": bool(np.all(np.diff(g.values)>=-1e-9) or
                              np.all(np.diff(g.values)<=1e-9)),
            "n": len(s)}

def cluster(df, feats, thresh=0.6):
    """greedy correlation clustering; returns list of clusters (lists of feats)."""
    present=[f for f in feats if f in df and df[f].notna().sum()>200]
    if not present: sys.exit("no candidate features present in file")
    corr=df[present].corr().abs()
    clusters=[]; assigned=set()
    # seed by overall separation proxy = variance of xs-zscore (just need grouping)
    for f in present:
        if f in assigned: continue
        grp=[f]; assigned.add(f)
        for g in present:
            if g in assigned: continue
            if corr.loc[f,g]>=thresh:
                grp.append(g); assigned.add(g)
        clusters.append(grp)
    return clusters, corr

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--fwd-days", type=int, default=60)
    ap.add_argument("--horizon", default=None)
    ap.add_argument("--split-date", default="2021-12-31")
    ap.add_argument("--candidates", nargs="+", default=DEFAULT_CANDIDATES)
    ap.add_argument("--earnings-flag", default="earnings_within_30_days")
    ap.add_argument("--cluster-thresh", type=float, default=0.6)
    ap.add_argument("--out", default="composite_report.csv")
    a=ap.parse_args()

    raw=pd.read_pickle(a.features)
    df=pd.DataFrame(raw["rows"]) if isinstance(raw,dict) and "rows" in raw else raw
    df["date"]=pd.to_datetime(df["date"])
    if a.horizon and "horizon" in df: df=df[df["horizon"]==a.horizon]
    fr=fwd_returns(df, a.fwd_days)
    split=pd.to_datetime(a.split_date)
    print(f"Universe forward-return samples: {len(fr):,} "
          f"(TRAIN<= {split.date()}, RECENT after)\n")

    cands=[f for f in a.candidates if f in fr.columns]
    missing=[f for f in a.candidates if f not in fr.columns]
    if missing: print(f"NOTE: candidates not in file (skipped): {missing}\n")

    # ---- 1. CLUSTER ----
    clusters, corr = cluster(fr, cands, a.cluster_thresh)
    print(f"=== 1. CORRELATION CLUSTERS (|r|>={a.cluster_thresh}) — your real bet count ===")
    reps=[]
    for i,grp in enumerate(clusters,1):
        # representative = the candidate with most non-null coverage
        rep=max(grp, key=lambda f: fr[f].notna().sum())
        reps.append(rep)
        print(f"  cluster {i}: {grp}   -> representative: {rep}")
    print(f"\n  => {len(clusters)} independent axes from {len(cands)} candidates. "
          f"Using representatives: {reps}\n")

    # ---- 2. COMPOSITE: z-score reps, weights fit on TRAIN, applied to RECENT ----
    # normalize each rep cross-sectionally per date, then equal-weight average.
    for rep in reps:
        fr["z_"+rep]=xs_zscore(fr, rep)
    zcols=["z_"+r for r in reps]
    # orient each z so higher = better, using TRAIN sign of correlation w/ fwd_return
    train=fr[fr["date"]<=split]
    signs={}
    for r in reps:
        c=train[["z_"+r,"fwd_return"]].dropna()
        s=np.sign(c["z_"+r].corr(c["fwd_return"])) or 1.0
        signs[r]=s
        fr["z_"+r]=fr["z_"+r]*s
    fr["composite"]=fr[zcols].mean(axis=1, skipna=True)

    print("=== 2. COMPOSITE vs BEST SINGLE FEATURE (decile spread of fwd return) ===")
    print("  (composite weights/orientation FIT ON TRAIN, applied unchanged to RECENT)\n")
    rows=[]
    def report(name, sub_all, score_col=None):
        sc=score_col or name
        tr=decile_spread(sub_all[sub_all["date"]<=split], sc)
        re=decile_spread(sub_all[sub_all["date"]>split], sc)
        rows.append({"score":name,
                     "train_spread": tr["spread_pts"] if tr else None,
                     "train_mono": tr["monotonic"] if tr else None,
                     "recent_spread": re["spread_pts"] if re else None,
                     "recent_mono": re["monotonic"] if re else None,
                     "recent_n": re["n"] if re else 0})
        def fmt(d): return (f"top={d['top_decile_med']}% bot={d['bottom_decile_med']}% "
                            f"spread={d['spread_pts']}pts mono={d['monotonic']}") if d else "n/a"
        print(f"  {name:<28} TRAIN[{fmt(tr)}]")
        print(f"  {'':<28} RECENT[{fmt(re)}]")
    report("composite", fr)
    for r in reps:
        report(r, fr)  # single-feature decile on raw rep values

    # ---- 3. EARNINGS FILTER ----
    if a.earnings_flag in fr.columns:
        print(f"\n=== 3. COMPOSITE with {a.earnings_flag}==0 filter (avoid pre-earnings) ===\n")
        filt=fr[fr[a.earnings_flag].fillna(0)==0]
        report("composite_ex_earnings", filt, score_col="composite")
    else:
        print(f"\n=== 3. earnings filter skipped ({a.earnings_flag} not in file) ===")

    pd.DataFrame(rows).to_csv(a.out, index=False)
    print(f"\nWritten -> {a.out}")
    print("\nREAD:")
    print(" - cluster count = how many INDEPENDENT bets you have (likely 1-3).")
    print(" - If composite RECENT spread > best single rep's RECENT spread AND is")
    print("   monotonic, the blend adds durable edge -> build Path B on it.")
    print(" - If composite ~= best single feature, edges are redundant -> keep it")
    print("   simple: one quality score is your strategy core.")
    print(" - If RECENT spread collapses vs TRAIN, the edge did NOT survive -> stop.")

if __name__=="__main__":
    main()