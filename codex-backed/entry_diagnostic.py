#!/usr/bin/env python3
"""
entry_diagnostic.py — Does the ENTRY thesis have any edge OUTSIDE crash-recovery
windows, with exits NEUTRALIZED?

The optimization found a config whose performance was ~98% driven by the
Mar-May 2020 crash recovery, with 90% of big winners exiting on the sim clock
(MAX_SIM_WINDOW_EXIT), not on a strategy exit. So we cannot trust realized_return
to tell us about ENTRY quality — it's contaminated by exit timing and one regime.

This script isolates ENTRY quality four ways:
  1. Regime partition: raw entry performance per market_regime.
  2. Period partition: crash-recovery vs normal/grinding periods.
  3. Exit-reason decomposition: how much of the edge rides the sim clock.
  4. Forward-return proxy (optional, if mfe/mae present): does the entry put you
     in a position that goes your way EARLY, independent of how the trade exited?

It deliberately does NOT optimize anything. It answers one question: is there a
signal in the entries themselves, or only in 2020?

USAGE:
  python3 entry_diagnostic.py results/<run>/trades.csv
  python3 entry_diagnostic.py results/<run>/trades.csv --crash 2020-03-01:2020-05-31
  python3 entry_diagnostic.py results/<run>/trades.csv \
      --crash 2020-03-01:2020-05-31 --crash 2018-12-01:2019-01-31
"""
import argparse, csv, statistics, sys
from datetime import datetime
from collections import Counter, defaultdict

REQ = ["entry_date", "exit_date", "realized_return_pct", "market_regime", "exit_reason"]
OPT = ["mfe_pct", "mae_pct", "days_held", "horizon", "selected_setup", "ticker"]

def d(s): return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()

def f(x, default=None):
    try: return float(x)
    except (TypeError, ValueError): return default

def load(path):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit("empty file")
    miss = [c for c in REQ if c not in rows[0]]
    if miss:
        sys.exit(f"missing required columns: {miss}\npresent: {list(rows[0])}")
    out = []
    for r in rows:
        rr = f(r["realized_return_pct"])
        if rr is None: continue
        try:
            ed, xd = d(r["entry_date"]), d(r["exit_date"])
        except Exception:
            continue
        out.append({
            "entry": ed, "exit": xd, "ret": rr,
            "regime": (r.get("market_regime") or "ALL").strip() or "ALL",
            "exit_reason": (r.get("exit_reason") or "").strip(),
            "mfe": f(r.get("mfe_pct")), "mae": f(r.get("mae_pct")),
            "setup": (r.get("selected_setup") or "").strip(),
            "ticker": (r.get("ticker") or "").strip(),
        })
    return out

def stats(rows):
    if not rows: return None
    rets = [r["ret"] for r in rows]
    wins = [x for x in rets if x > 0]
    pos = sum(x for x in rets if x > 0)
    neg = -sum(x for x in rets if x < 0)
    pf = (pos/neg) if neg > 0 else float("inf")
    return {
        "n": len(rets),
        "mean": round(statistics.fmean(rets), 2),
        "median": round(statistics.median(rets), 3),
        "win%": round(len(wins)/len(rets)*100, 1),
        "pf": (round(pf, 2) if pf != float("inf") else "inf"),
    }

def line(label, s):
    if s is None:
        print(f"  {label:<26} (no trades)")
    else:
        print(f"  {label:<26} n={s['n']:>4}  mean={s['mean']:>7}%  "
              f"median={s['median']:>7}%  win={s['win%']:>5}%  PF={s['pf']}")

def in_any(date_, windows):
    return any(lo <= date_ <= hi for lo, hi in windows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trades")
    ap.add_argument("--crash", action="append", default=[],
                    help="entry-date window LO:HI to treat as crash-recovery; repeatable")
    a = ap.parse_args()

    windows = []
    for w in (a.crash or ["2020-03-01:2020-05-31"]):
        lo, hi = w.split(":"); windows.append((d(lo), d(hi)))

    rows = load(a.trades)
    print(f"\nLoaded {len(rows)} trades from {a.trades}")
    print(f"Crash-recovery windows (by ENTRY date): "
          f"{', '.join(f'{lo}..{hi}' for lo,hi in windows)}")
    print(f"Date span: {min(r['entry'] for r in rows)} .. "
          f"{max(r['exit'] for r in rows)}")

    # ---- 1. OVERALL vs EX-CRASH ----
    print("\n=== 1. OVERALL vs CRASH-EXCLUDED (the headline test) ===")
    line("ALL trades", stats(rows))
    ex = [r for r in rows if not in_any(r["entry"], windows)]
    cr = [r for r in rows if in_any(r["entry"], windows)]
    line("CRASH-window entries", stats(cr))
    line("EX-CRASH entries", stats(ex))
    if cr and ex:
        share = len(cr)/len(rows)*100
        print(f"  -> crash-window trades are {share:.1f}% of all trades")

    # ---- 2. PER REGIME (ex-crash, so 2020 V doesn't pollute) ----
    print("\n=== 2. PER-REGIME, CRASH EXCLUDED (does any regime show edge?) ===")
    byreg = defaultdict(list)
    for r in ex: byreg[r["regime"]].append(r)
    for reg in sorted(byreg, key=lambda k: -len(byreg[k])):
        line(reg, stats(byreg[reg]))

    # ---- 3. PER YEAR (ex-crash) ----
    print("\n=== 3. PER-YEAR, CRASH EXCLUDED (is any year self-supporting?) ===")
    byyr = defaultdict(list)
    for r in ex: byyr[r["exit"].year].append(r)
    for yr in sorted(byyr):
        line(str(yr), stats(byyr[yr]))

    # ---- 4. EXIT-REASON decomposition ----
    print("\n=== 4. EXIT-REASON MIX (is the edge real exits or the sim clock?) ===")
    allbig = [r for r in rows if r["ret"] > 20]
    print(f"  Winners >20% by exit_reason: "
          f"{dict(Counter(r['exit_reason'] for r in allbig))}")
    print(f"  ALL trades by exit_reason:   "
          f"{dict(Counter(r['exit_reason'] for r in rows))}")
    msw = [r for r in rows if r["exit_reason"] == "MAX_SIM_WINDOW_EXIT"]
    if msw:
        print(f"  MAX_SIM_WINDOW_EXIT share of all trades: "
              f"{len(msw)/len(rows)*100:.1f}%  | of >20% winners: "
              f"{sum(r['ret']>20 for r in msw)}/{len(allbig)}")

    # ---- 5. ENTRY-QUALITY PROXY via MFE (exit-independent) ----
    # MFE = max favorable excursion: how far the trade went your way at best,
    # regardless of how it exited. If entries are good, MFE should be meaningfully
    # positive even ex-crash. This isolates ENTRY from EXIT.
    have_mfe = any(r["mfe"] is not None for r in ex)
    if have_mfe:
        print("\n=== 5. ENTRY-QUALITY PROXY: MFE (exit-independent), CRASH EXCLUDED ===")
        mfe = [r["mfe"] for r in ex if r["mfe"] is not None]
        mae = [r["mae"] for r in ex if r["mae"] is not None]
        print(f"  median MFE (best move in your favor): "
              f"{round(statistics.median(mfe),2)}%")
        if mae:
            print(f"  median MAE (worst move against you): "
                  f"{round(statistics.median(mae),2)}%")
            # edge ratio: do entries get more upside excursion than downside?
            mm = statistics.median(mfe); ma = abs(statistics.median(mae))
            print(f"  MFE:MAE median ratio: {round(mm/ma,2) if ma>0 else 'inf'}  "
                  f"(>1.0 suggests entries find favorable positions)")
    else:
        print("\n=== 5. MFE proxy skipped (mfe_pct empty) ===")

    # ---- VERDICT ----
    print("\n=== READ-THIS ===")
    se = stats(ex)
    if se is None or se["n"] == 0:
        print("  Almost all trades are in crash windows. No ex-crash sample — the")
        print("  strategy has essentially never been tested outside the recovery.")
    else:
        good = se["median"] > 0 and se["win%"] >= 45
        print(f"  Ex-crash median trade: {se['median']}% | win rate: {se['win%']}%")
        if good:
            print("  -> Entries show SOME edge outside crashes. Worth rebuilding exits around.")
        else:
            print("  -> Ex-crash median is ~flat/negative. The entry thesis does NOT")
            print("     generalize beyond crash recovery. Tuning will not fix this;")
            print("     the entry signal itself needs to change.")
    print()

if __name__ == "__main__":
    main()