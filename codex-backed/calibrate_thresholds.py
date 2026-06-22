#!/usr/bin/env python3
"""
calibrate_thresholds.py — Read your universe's ACTUAL roic / sales_growth_yoy /
gross_margin distribution and print the exact threshold values to drop into the
Path B entry config (the six constants ROIC_STRONG/_OK/_WEAK, SALES_*, etc.).

The Path B config shipped with PLACEHOLDER thresholds keyed to a generic universe.
This replaces them with percentile breakpoints from YOUR features.pkl, so the
quality gate's "strong / ok / weak" buckets land where your edge actually lives.

It also (a) confirms the four fundamental fields exist and are populated (the code
check — if roic is all-null, the engine has no data to gate on), and (b) prints
the win-rate-by-quality-bucket so you can eyeball that higher quality => better,
i.e. the thresholds point the right way.

USAGE:
  python3 calibrate_thresholds.py --features cache/features.pkl --horizon short_term
  # optional: validate buckets against outcomes by also passing a trades file
  python3 calibrate_thresholds.py --features cache/features.pkl --horizon short_term \
      --trades results/<run>/trades.csv
"""
import argparse
import numpy as np
import pandas as pd

FIELDS = ["roic", "sales_growth_yoy", "gross_margin"]

def pctl(s, p):
    return float(np.nanpercentile(s.dropna().values, p))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--horizon", default=None)
    ap.add_argument("--trades", default=None)
    a = ap.parse_args()

    raw = pd.read_pickle(a.features)
    df = pd.DataFrame(raw["rows"]) if isinstance(raw, dict) and "rows" in raw else raw
    if a.horizon and "horizon" in df:
        df = df[df["horizon"] == a.horizon]
    print(f"Universe snapshots: {len(df):,}"
          + (f" (horizon={a.horizon})" if a.horizon else ""))

    # ---- (a) FIELD AVAILABILITY = the code check ----
    print("\n=== FIELD AVAILABILITY (the 'do I need code?' check) ===")
    ok = True
    for f in FIELDS + ["earnings_within_30_days"]:
        if f not in df.columns:
            print(f"  {f:<26} MISSING — not a column. Engine cannot gate on it.")
            ok = False
        else:
            cov = df[f].notna().mean()
            print(f"  {f:<26} present, {cov*100:5.1f}% populated"
                  + ("" if cov > 0.5 else "  <-- LOW COVERAGE, gate will pass few names"))
            if cov < 0.05:
                ok = False
    if not ok:
        print("\n  -> Fundamental fields missing/empty. Before this config can work, "
              "the feature pipeline must populate them (a CODE/data change). If they "
              "exist but the rule evaluator can't see them, that's the field-whitelist "
              "one-liner.")
    else:
        print("\n  -> Fields present & populated. If the rule evaluator passes the whole "
              "row through (as it does for technical fields), this config is config-only.")

    # ---- threshold breakpoints ----
    print("\n=== CALIBRATED THRESHOLDS (drop into the config constants) ===")
    print("    Buckets: STRONG=top tercile (>=66th pctl), OK=middle (>=33rd), "
          "WEAK=bottom (<=20th pctl floor)\n")
    out = {}
    for f, names in (("roic", ("ROIC_STRONG","ROIC_OK","ROIC_WEAK")),
                     ("sales_growth_yoy", ("SALES_STRONG","SALES_OK","SALES_WEAK"))):
        if f not in df.columns:
            continue
        strong = round(pctl(df[f], 66), 1)
        okv    = round(pctl(df[f], 33), 1)
        weak   = round(pctl(df[f], 20), 1)
        out[names[0]] = strong; out[names[1]] = okv; out[names[2]] = weak
        print(f"  {f}:")
        print(f"     {names[0]:<14} = {strong:>8}   (66th pctl — top tercile)")
        print(f"     {names[1]:<14} = {okv:>8}   (33rd pctl — above this is mid+)")
        print(f"     {names[2]:<14} = {weak:>8}   (20th pctl — below this = block)")
    if "gross_margin" in df.columns:
        gm = round(pctl(df["gross_margin"], 40), 1)
        out["GROSS_MARGIN_MIN"] = gm
        print(f"  gross_margin:")
        print(f"     GROSS_MARGIN_MIN = {gm:>8}   (40th pctl — confirmation floor)")

    print("\n  Copy-paste into build_config / the config constants:")
    for k, v in out.items():
        print(f"     {k} = {v}")

    # ---- (b) sanity: do higher-quality buckets actually win? (needs trades) ----
    if a.trades:
        print("\n=== BUCKET SANITY CHECK (win rate by quality, from your trades) ===")
        tr = pd.read_csv(a.trades)
        # join trades to features at signal time
        dcol = "signal_date" if "signal_date" in tr else "entry_date"
        tr["jd"] = pd.to_datetime(tr[dcol]); df["jd"] = pd.to_datetime(df["date"])
        keys = ["ticker", "jd"] + (["horizon"] if "horizon" in tr and "horizon" in df else [])
        m = tr.merge(df[keys + FIELDS], on=keys, how="left")
        m["win"] = m["realized_return_pct"] > 0
        for f in ("roic", "sales_growth_yoy"):
            s = m[[f, "win"]].dropna()
            if len(s) < 30:
                print(f"  {f}: too few matched trades"); continue
            s["bucket"] = pd.qcut(s[f], 3, labels=["low","mid","high"], duplicates="drop")
            g = s.groupby("bucket", observed=True)["win"].agg(["mean","size"])
            print(f"  {f} (win rate by tercile):")
            for idx, r in g.iterrows():
                print(f"     {idx:<5} win={r['mean']*100:5.1f}%  n={int(r['size'])}")
            mono = g["mean"].is_monotonic_increasing
            print(f"     {'higher quality => higher win rate: YES' if mono else 'NOT monotone (check direction)'}")

    print("\nNote: these are ABSOLUTE thresholds (config-only, Option A). They will "
          "drift if the whole universe's profitability shifts. Switch to a precomputed "
          "*_percentile column later if you want them regime-adaptive (a small pipeline change).")

if __name__ == "__main__":
    main()