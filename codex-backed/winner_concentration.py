#!/usr/bin/env python3
"""
winner_concentration.py — Is the tail-dependence in your baseline a LEGITIMATE
trend/quality skew, or a DANGEROUS in-sample concentration?

The mean/median ratio (161.6) is a blunt proxy: it trips on ANY scratch-heavy
strategy, including legitimate trend books where most trades break even by design
and edge lives in the tail. This measures the ACTUAL pathology instead:

  1. PROFIT CONCENTRATION: what % of total gross profit comes from the top 5% /
     top 10% of trades? High median-ratio is fine if the top-5% is, say, <60% of
     profit (healthy skew). Dangerous if top-5% is >80% (a handful of trades ARE
     the strategy — won't generalize).
  2. FOLD SPREAD OF WINNERS: are the big winners spread across years/folds, or
     concentrated in one (the iter-103 / 2020-fold failure)? A strategy whose
     winners cluster in one fold is curve-fit; one whose winners appear every
     year is real.
  3. DROP-TOP-FOLD TEST: recompute profit factor with each fold removed — if
     removing ONE fold collapses PF, the edge is that fold.

USAGE:
  python3 winner_concentration.py results/<run>/trades.csv
"""
import csv, sys, statistics
from collections import defaultdict

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def load(path):
    rows=[]
    for r in csv.DictReader(open(path)):
        rr=f(r.get("realized_return_pct"))
        if rr is None: continue
        yr=str(r.get("exit_date",""))[:4]
        rows.append({"ret":rr,"year":yr})
    if not rows: sys.exit("no trades")
    return rows

def pf(rets):
    g=sum(x for x in rets if x>0); l=-sum(x for x in rets if x<0)
    return (g/l) if l>0 else float("inf")

def main():
    if len(sys.argv)<2: sys.exit("usage: winner_concentration.py trades.csv")
    rows=load(sys.argv[1])
    rets=sorted((r["ret"] for r in rows), reverse=True)
    n=len(rets)
    total_profit=sum(x for x in rets if x>0)
    print(f"\n{n} trades | total gross profit (sum of positive returns) = {total_profit:.1f}%")
    print(f"median return = {statistics.median(rets):.4f}%  mean = {statistics.fmean(rets):.4f}%")
    print(f"mean/median ratio = {abs(statistics.fmean(rets)/statistics.median(rets)):.1f}"
          if statistics.median(rets)!=0 else "median is 0")

    # 1. profit concentration
    print("\n=== 1. PROFIT CONCENTRATION (what carries the strategy) ===")
    for pctl in (1,5,10,20):
        k=max(1,int(n*pctl/100))
        top_profit=sum(x for x in rets[:k] if x>0)
        share=top_profit/total_profit*100 if total_profit>0 else 0
        print(f"  top {pctl:>2}% of trades ({k:>4} trades): {share:5.1f}% of all profit")
    k5=max(1,int(n*0.05))
    top5_share=sum(x for x in rets[:k5] if x>0)/total_profit*100 if total_profit>0 else 0
    verdict = ("HEALTHY skew" if top5_share<60 else
               "ELEVATED — watch" if top5_share<80 else
               "DANGEROUS concentration — a few trades ARE the strategy")
    print(f"  -> top-5% carries {top5_share:.1f}% of profit: {verdict}")

    # 2. winners by fold
    print("\n=== 2. ARE BIG WINNERS SPREAD ACROSS YEARS? ===")
    thresh=sorted((r["ret"] for r in rows),reverse=True)[max(1,int(n*0.05))]
    byyr=defaultdict(int); cntyr=defaultdict(int)
    for r in rows:
        cntyr[r["year"]]+=1
        if r["ret"]>=thresh: byyr[r["year"]]+=1
    print(f"  (big winner = top-5% trade, return >= {thresh:.1f}%)")
    yrs=sorted(cntyr)
    for y in yrs:
        bar="#"*byyr[y]
        print(f"  {y}: {byyr[y]:>3} big winners / {cntyr[y]:>4} trades  {bar}")
    nz=sum(1 for y in yrs if byyr[y]>0)
    print(f"  -> big winners appear in {nz}/{len(yrs)} years: "
          + ("SPREAD (real)" if nz>=len(yrs)*0.6 else "CONCENTRATED (curve-fit risk)"))

    # 3. drop-one-fold PF
    print("\n=== 3. DROP-ONE-YEAR PROFIT FACTOR (does one fold carry it?) ===")
    allret=[r["ret"] for r in rows]
    base_pf=pf(allret)
    print(f"  full PF = {base_pf:.2f}")
    for y in yrs:
        rest=[r["ret"] for r in rows if r["year"]!=y]
        if len(rest)<20: continue
        p=pf(rest)
        drop=(base_pf-p)/base_pf*100 if base_pf not in (0,float('inf')) else 0
        flag=" <-- removing this year collapses PF" if (base_pf!=float('inf') and p<base_pf*0.6) else ""
        print(f"  without {y}: PF = {p:.2f} ({drop:+.0f}% vs full){flag}")

    print("\nREAD: high mean/median is SAFE if top-5% carries <60-70% of profit AND")
    print("winners are spread across years AND no single year's removal collapses PF.")
    print("If all three are clean, the ratio is a trend-style artifact — recalibrate")
    print("the gate. If any fail, it's real tail-dependence — do NOT promote.")

if __name__=="__main__":
    main()