#!/usr/bin/env python3
"""
composite_robustness.py — Is the composite edge REAL or small-sample noise?

Your 2-factor composite (roic + sales_growth_yoy) showed RECENT decile spreads of
~29pts, but TRAIN was ~17pts — a factor that nearly doubles between windows is a
sign the point estimate is noisy. This script reports the HONEST size of the edge:

1. FULL DECILE CURVE: median fwd return for all 10 deciles (TRAIN and RECENT).
   A real factor rises fairly smoothly bottom->top. A spike only in the extreme
   decile = fragile / a few names.

2. BOOTSTRAP CI: resample the RECENT set 1000x, recompute top-bottom decile spread
   each time, report median + 90% CI. Converts "29pts" into "11pts [4,19]" honesty.

3. SUB-PERIOD STABILITY: spread per calendar year (is the edge every year, or one?).

4. RANK-IC: Spearman corr between composite and fwd return per date, averaged
   (a standard, sample-size-robust factor-strength metric). |IC|>0.03 is useful,
   >0.05 is strong, in equity cross-sections.

Builds the 2-factor composite exactly as composite_prototype did (z-score per date,
orientation fit on TRAIN, equal weight), so numbers are comparable.

USAGE:
  python3 composite_robustness.py --features cache/features.pkl \
      --fwd-days 60 --horizon short_term --split-date 2021-12-31 \
      --candidates roic sales_growth_yoy --earnings-flag earnings_within_30_days
"""
import argparse, sys
import numpy as np
import pandas as pd

def fwd_returns(df, fwd_days):
    df=df.sort_values(["ticker","date"]).copy(); out=[]
    for tk,g in df.groupby("ticker",sort=False):
        g=g.reset_index(drop=True)
        if len(g)<=fwd_days: continue
        g["fwd_return"]=(g["price"].shift(-fwd_days)/g["price"]-1)*100
        out.append(g.iloc[::fwd_days])
    return pd.concat(out,ignore_index=True).dropna(subset=["fwd_return"])

def xs_z(df,col):
    return df.groupby("date")[col].transform(
        lambda s:(s-s.mean())/s.std() if s.std()>1e-9 else s*0.0)

def decile_curve(sub, col):
    s=sub[[col,"fwd_return"]].dropna()
    if len(s)<100: return None
    try: s["d"]=pd.qcut(s[col],10,labels=False,duplicates="drop")
    except ValueError: return None
    return s.groupby("d")["fwd_return"].median()

def boot_spread(sub, col, n=1000, seed=0):
    s=sub[[col,"fwd_return"]].dropna().reset_index(drop=True)
    if len(s)<100: return None
    rng=np.random.default_rng(seed); spreads=[]
    for _ in range(n):
        bs=s.iloc[rng.integers(0,len(s),len(s))]
        try: bs=bs.assign(d=pd.qcut(bs[col],10,labels=False,duplicates="drop"))
        except ValueError: continue
        g=bs.groupby("d")["fwd_return"].median()
        if len(g)>=2: spreads.append(g.iloc[-1]-g.iloc[0])
    if not spreads: return None
    a=np.array(spreads)
    return {"median":round(float(np.median(a)),1),
            "lo5":round(float(np.percentile(a,5)),1),
            "hi95":round(float(np.percentile(a,95)),1),
            "frac_positive":round(float((a>0).mean()),3)}

def rank_ic(sub, col):
    ics=[]
    for dt,g in sub.groupby("date"):
        s=g[[col,"fwd_return"]].dropna()
        if len(s)<10: continue
        ics.append(s[col].rank().corr(s["fwd_return"].rank()))
    if not ics: return None
    a=np.array(ics)
    return {"mean_ic":round(float(a.mean()),4),
            "ic_std":round(float(a.std()),4),
            "ic_ir":round(float(a.mean()/a.std()),3) if a.std()>0 else None,
            "n_dates":len(a)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--features",required=True)
    ap.add_argument("--fwd-days",type=int,default=60)
    ap.add_argument("--horizon",default=None)
    ap.add_argument("--split-date",default="2021-12-31")
    ap.add_argument("--candidates",nargs="+",default=["roic","sales_growth_yoy"])
    ap.add_argument("--earnings-flag",default="earnings_within_30_days")
    a=ap.parse_args()

    raw=pd.read_pickle(a.features)
    df=pd.DataFrame(raw["rows"]) if isinstance(raw,dict) and "rows" in raw else raw
    df["date"]=pd.to_datetime(df["date"])
    if a.horizon and "horizon" in df: df=df[df["horizon"]==a.horizon]
    fr=fwd_returns(df,a.fwd_days)
    split=pd.to_datetime(a.split_date)
    cands=[c for c in a.candidates if c in fr.columns]
    print(f"Samples: {len(fr):,} | factors: {cands} | split {split.date()}\n")

    # build composite: z per date, orient on TRAIN, equal weight
    for c in cands:
        fr["z_"+c]=xs_z(fr,c)
    train_mask=fr["date"]<=split
    zc=[]
    for c in cands:
        cc=fr.loc[train_mask,["z_"+c,"fwd_return"]].dropna()
        sign=np.sign(cc["z_"+c].corr(cc["fwd_return"])) or 1.0
        fr["z_"+c]=fr["z_"+c]*sign; zc.append("z_"+c)
    fr["composite"]=fr[zc].mean(axis=1,skipna=True)
    rec=fr[fr["date"]>split]; tr=fr[fr["date"]<=split]

    # 1. decile curves
    print("=== 1. FULL DECILE CURVE (median fwd return %, bottom->top) ===")
    for label,sub in (("TRAIN",tr),("RECENT",rec)):
        c=decile_curve(sub,"composite")
        if c is None: print(f"  {label}: insufficient"); continue
        vals=" ".join(f"{v:>6.1f}" for v in c.values)
        smooth=np.all(np.diff(c.values)>=-2.0)  # near-monotone tolerance
        print(f"  {label}: [{vals}]  {'~smooth' if smooth else 'NON-monotone (fragile)'}")
    print()

    # 2. bootstrap CI on RECENT
    print("=== 2. BOOTSTRAP CI on RECENT top-bottom spread (1000x) ===")
    b=boot_spread(rec,"composite")
    if b:
        print(f"  spread median={b['median']}pts  90% CI [{b['lo5']}, {b['hi95']}]  "
              f"P(spread>0)={b['frac_positive']}")
        if b["lo5"]<=0: print("  -> CI includes 0: edge NOT reliably positive on this sample.")
        elif b["hi95"]-b["lo5"]>b["median"]*1.5:
            print("  -> very wide CI: edge real-ish but size highly uncertain (small sample).")
        else: print("  -> CI comfortably positive: edge is reliable.")
    print()

    # 3. per-year spread
    print("=== 3. PER-YEAR top-bottom spread (is it every year or one?) ===")
    fr["yr"]=fr["date"].dt.year
    for yr in sorted(fr["yr"].unique()):
        c=decile_curve(fr[fr["yr"]==yr],"composite")
        if c is not None and len(c)>=2:
            sp=c.iloc[-1]-c.iloc[0]
            n=((fr["yr"]==yr).sum())
            print(f"  {yr}: spread={sp:>6.1f}pts  (n={n})")
    print()

    # 4. rank IC (sample-robust factor strength)
    print("=== 4. RANK IC (Spearman composite vs fwd return, per date) ===")
    for label,sub in (("TRAIN",tr),("RECENT",rec)):
        ic=rank_ic(sub,"composite")
        if ic: print(f"  {label}: mean_IC={ic['mean_ic']} IC_IR={ic['ic_ir']} "
                      f"(|IC|>0.03 useful, >0.05 strong; n_dates={ic['n_dates']})")
    print()

    if a.earnings_flag in fr.columns:
        print(f"=== 5. RANK IC with {a.earnings_flag}==0 (RECENT) ===")
        sub=rec[rec[a.earnings_flag].fillna(0)==0]
        ic=rank_ic(sub,"composite")
        if ic: print(f"  RECENT ex-earnings: mean_IC={ic['mean_ic']} IC_IR={ic['ic_ir']}")
    print("\nREAD: trust the RANK IC and the bootstrap CI over the raw decile spread.")
    print("A mean_IC of 0.03-0.06 that holds in RECENT = a real, modest, buildable")
    print("edge — even if the headline decile spread looked like 29pts. The decile")
    print("curve tells you if it's a smooth gradient (robust) or one-decile spike (fragile).")

if __name__=="__main__":
    main()