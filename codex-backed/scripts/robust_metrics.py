#!/usr/bin/env python3
"""
robust_metrics.py - walk-forward, recency-weighted robustness metrics + a literal
accept/reject verdict for the overfitting-resistant backtest optimization loop.

WHY WALK-FORWARD (read once)
----------------------------
A single fixed train/validate/holdout split lets one regime (e.g. the 2020 COVID
crash, or the 2023-24 megacap rally) dominate the verdict. Walk-forward rolls a
window through history: each FOLD is SCORED on a test year it never tuned on. We
judge a parameter set by behavior ACROSS folds - median fold, worst fold, and a
recency-WEIGHTED blend - not by one number. COVID becomes one fold among many.

A strategy whose return lived in a few tail winners (the old iter-103 failure)
shows up as "great in 1-2 folds, flat/negative elsewhere" and is caught by the
worst-fold and profitable-fold-fraction gates.

INPUT: per-trade ledger for ONE run. CSV or JSON list, one row per closed trade.
  REQUIRED: ticker, entry_date(YYYY-MM-DD), exit_date(YYYY-MM-DD), return_pct(float, post-cost)
  OPTIONAL: market_regime (default "ALL")
A trade belongs to the fold whose TEST year its EXIT date falls in.

OUTPUT: metrics JSON + verdict + exit code:
  0 = ACCEPT or BASELINE | 2 = REJECT | 3 = HARD-CONSTRAINT fail | 4 = OVERFIT(final)

Single source of truth for metrics + verdict. Never appends to history.jsonl
except via the explicit, separate `log` subcommand.

COMMANDS: score | promote | log   (see argparse help)
"""

import argparse
import csv
import json
import math
import statistics
import sys
from datetime import datetime

TRADING_DAYS = 252

# Walk-forward layout: each fold TESTS one calendar year it never tuned on.
WF = {
    "first_test_year": 2015,
    "last_test_year": 2022,
    "train_years": 4,
    "test_years": 1,
}
HOLDOUT_YEARS = (2023, 2025)          # sealed final exam
RECENCY_HALF_LIFE_YEARS = 3.0         # fold weight = 0.5 ** (age / half_life)

HARD = {
    "min_trades_full": 300,
    "min_trades_oos": 100,
    "max_mean_median_ratio": 500.0,   # crash-recovery strategy is legitimately tail-dependent
    "min_profitable_fold_frac": 0.50,
    "min_folds": 4,
}
ACCEPT = {
    "primary_degrade_max_pct": 10.0,
    "worstfold_drop_max_pct": 15.0,
    "regime_pf_drop_max_pct": 15.0,
    "trades_floor_full": 300,
    "trades_floor_oos": 100,
    "maxdd_worsen_max_pct": 10.0,
    "shrink_trade_drop_pct": 20.0,
    "shrink_min_gain_pct": 5.0,
    "overfit_wr_jump_pts": 5.0,
}


def _parse_date(s):
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


# Column aliases: maps the script's required field -> list of accepted source
# column names, in priority order. This lets the native backtester ledger be read
# directly with NO separate adapter / no intermediate file. The first alias that
# is present (and non-empty) wins. Add names here if your schema changes.
COLUMN_ALIASES = {
    "ticker":        ["ticker", "symbol"],
    "entry_date":    ["entry_date", "entry_dt", "open_date"],
    "exit_date":     ["exit_date", "exit_dt", "close_date"],
    "return_pct":    ["return_pct", "realized_return_pct", "pnl_pct", "ret_pct"],
    "market_regime": ["market_regime", "regime"],
}


def _resolve_columns(header):
    """Pick the actual source column for each required field. Returns a
    {field: source_col} map, or raises SystemExit listing what's missing."""
    header_set = set(header)
    resolved, missing = {}, []
    for field, aliases in COLUMN_ALIASES.items():
        hit = next((a for a in aliases if a in header_set), None)
        if hit is None and field != "market_regime":   # regime is optional
            missing.append(f"{field} (looked for any of: {', '.join(aliases)})")
        elif hit is not None:
            resolved[field] = hit
    if missing:
        raise SystemExit(
            "trades file is missing required column(s):\n  - "
            + "\n  - ".join(missing)
            + f"\nColumns present: {', '.join(sorted(header_set))}\n"
            "Fix: add the column, or add its name to COLUMN_ALIASES at the top "
            "of robust_metrics.py.")
    return resolved


def load_trades(path):
    if path.lower().endswith(".json"):
        with open(path) as f:
            rows = list(json.load(f))
        header = list(rows[0].keys()) if rows else []
    else:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            rows = list(reader)
    if not rows:
        raise SystemExit(f"No trades found in {path}")

    col = _resolve_columns(header)
    trades, skipped = [], 0
    for r in rows:
        try:
            t = {
                "ticker": str(r.get(col["ticker"], "")).strip(),
                "entry_date": _parse_date(r[col["entry_date"]]),
                "exit_date": _parse_date(r[col["exit_date"]]),
                "return_pct": float(r[col["return_pct"]]),
                "market_regime": (str(r.get(col.get("market_regime", ""), "ALL")).strip()
                                  or "ALL"),
            }
        except (KeyError, ValueError, TypeError):
            # a single unparyseable row (blank return, bad date) is skipped, not fatal
            skipped += 1
            continue
        if t["exit_date"] < t["entry_date"]:
            skipped += 1
            continue
        t["hold_days"] = max((t["exit_date"] - t["entry_date"]).days, 0)
        trades.append(t)
    if not trades:
        raise SystemExit(f"No valid trades parsed from {path} "
                         f"({skipped} rows skipped)")
    if skipped:
        sys.stderr.write(f"[load_trades] note: skipped {skipped} unparseable/"
                         f"invalid rows out of {len(rows)}\n")
    return trades


def _emit(obj, out):
    s = json.dumps(obj, indent=2)
    if out:
        with open(out, "w") as f:
            f.write(s)
    else:
        print(s)


def equity_curve(ts):
    eq, curve = 1.0, [1.0]
    for t in ts:
        eq *= (1.0 + t["return_pct"] / 100.0)
        curve.append(eq)
    return curve


def max_drawdown(curve):
    peak, mdd = curve[0], 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd * 100.0


def cagr(curve, first_d, last_d):
    years = max((last_d - first_d).days / 365.25, 1e-9)
    final = curve[-1]
    if final <= 0:
        return -100.0
    return ((final ** (1.0 / years)) - 1.0) * 100.0


def sharpe_sortino(returns):
    if len(returns) < 2:
        return 0.0, 0.0
    mean = statistics.fmean(returns)
    sd = statistics.pstdev(returns)
    downside = [r for r in returns if r < 0]
    dsd = statistics.pstdev(downside) if len(downside) >= 2 else 0.0
    sharpe = (mean / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0
    sortino = (mean / dsd * math.sqrt(TRADING_DAYS)) if dsd > 0 else 0.0
    return sharpe, sortino


def profit_factor(returns):
    gains = sum(r for r in returns if r > 0)
    losses = -sum(r for r in returns if r < 0)
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def regime_min_pf(trades):
    by = {}
    for t in trades:
        by.setdefault(t["market_regime"], []).append(t["return_pct"])
    pfs = {k: profit_factor(v) for k, v in by.items() if len(v) >= 5}
    if not pfs:
        return None, {}
    finite = {k: (v if math.isfinite(v) else 1e9) for k, v in pfs.items()}
    return min(finite.values()), pfs


def _safe_mar(cg, mdd):
    if mdd > 1e-9:
        return cg / mdd
    return float("inf") if cg > 0 else 0.0


def metrics_for(trades):
    if not trades:
        return None
    ts = sorted(trades, key=lambda t: t["exit_date"])
    rets = [t["return_pct"] for t in ts]
    curve = equity_curve(ts)
    first, last = ts[0]["entry_date"], ts[-1]["exit_date"]
    mdd = max_drawdown(curve)
    cg = cagr(curve, first, last)
    mar = _safe_mar(cg, mdd)
    sharpe, sortino = sharpe_sortino(rets)
    mean = statistics.fmean(rets)
    median = statistics.median(rets)
    mm = (abs(mean) / abs(median)) if abs(median) > 1e-9 else float("inf")
    losses = [r for r in rets if r < 0]
    wins = [r for r in rets if r > 0]
    pf = profit_factor(rets)
    min_pf, regime_pfs = regime_min_pf(ts)
    return {
        "trade_count": len(ts),
        "cagr": round(cg, 4),
        "max_drawdown": round(mdd, 4),
        "mar_ratio": (round(mar, 4) if math.isfinite(mar) else None),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "avg_return": round(mean, 4),
        "median_return": round(median, 4),
        "mean_median_ratio": (round(mm, 2) if math.isfinite(mm) else None),
        "win_rate": round(len(wins) / len(rets) * 100.0, 4),
        "profit_factor": (round(pf, 4) if math.isfinite(pf) else None),
        "avg_loss": round(statistics.fmean(losses), 4) if losses else 0.0,
        "min_regime_pf": (round(min_pf, 4) if min_pf is not None
                          and math.isfinite(min_pf) else None),
        "regime_pf": {k: (round(v, 4) if math.isfinite(v) else None)
                      for k, v in regime_pfs.items()},
        "first_exit": str(first),
        "last_exit": str(last),
    }


def fold_windows():
    out = []
    for ty in range(WF["first_test_year"], WF["last_test_year"] + 1, WF["test_years"]):
        out.append({"test_year": ty,
                    "train_label": f"{ty - WF['train_years']}-{ty - 1}"})
    return out


def trades_in_year(trades, year):
    return [t for t in trades if t["exit_date"].year == year]


def recency_weight(test_year, newest_year):
    return 0.5 ** ((newest_year - test_year) / RECENCY_HALF_LIFE_YEARS)


def walk_forward(trades):
    folds = []
    newest = WF["last_test_year"]
    for fw in fold_windows():
        ty = fw["test_year"]
        m = metrics_for(trades_in_year(trades, ty))
        folds.append({"test_year": ty, "train_label": fw["train_label"],
                      "weight": round(recency_weight(ty, newest), 4),
                      "metrics": m, "empty": m is None})

    scored = [f for f in folds if not f["empty"]]
    mars = [f["metrics"]["mar_ratio"] for f in scored
            if f["metrics"]["mar_ratio"] is not None]
    median_fold_mar = round(statistics.median(mars), 4) if mars else None
    worst_fold_mar = round(min(mars), 4) if mars else None

    wsum, wmar = 0.0, 0.0
    for f in scored:
        mar = f["metrics"]["mar_ratio"]
        if mar is None:
            continue
        wsum += f["weight"]
        wmar += f["weight"] * mar
    weighted_fold_mar = round(wmar / wsum, 4) if wsum > 0 else None

    prof = [f for f in scored if f["metrics"]["cagr"] > 0]
    prof_frac = round(len(prof) / len(scored), 4) if scored else 0.0

    oos_union = []
    for fw in fold_windows():
        oos_union += trades_in_year(trades, fw["test_year"])
    oos = metrics_for(oos_union)

    return {
        "folds": folds,
        "n_scored_folds": len(scored),
        "median_fold_mar": median_fold_mar,
        "worst_fold_mar": worst_fold_mar,
        "weighted_fold_mar": weighted_fold_mar,
        "profitable_fold_frac": prof_frac,
        "oos_union": oos,
        "recency_half_life_years": RECENCY_HALF_LIFE_YEARS,
    }


def pct_change(new, old):
    if old in (None, 0) or new is None:
        return None
    return (new - old) / abs(old) * 100.0


def hard_constraints(new):
    fails, flags = [], []
    full = new["full"]
    wf = new["walk_forward"]
    oos = wf["oos_union"]
    if full["trade_count"] < HARD["min_trades_full"]:
        fails.append(f"full trades {full['trade_count']} < {HARD['min_trades_full']}")
    if oos is None or oos["trade_count"] < HARD["min_trades_oos"]:
        n = 0 if oos is None else oos["trade_count"]
        fails.append(f"OOS(union) trades {n} < {HARD['min_trades_oos']}")
    mm = full["mean_median_ratio"]
    if mm is None or mm > HARD["max_mean_median_ratio"]:
        fails.append(f"mean/median {mm} > {HARD['max_mean_median_ratio']}")
        flags.append("TAIL_DEPENDENT")
    if wf["n_scored_folds"] < HARD["min_folds"]:
        fails.append(f"only {wf['n_scored_folds']} scored folds < {HARD['min_folds']}")
    if wf["profitable_fold_frac"] < HARD["min_profitable_fold_frac"]:
        fails.append(f"profitable folds {wf['profitable_fold_frac']:.0%} "
                     f"< {HARD['min_profitable_fold_frac']:.0%}")
        flags.append("FOLD_FRAGILE")
    if full["max_drawdown"] is None or not math.isfinite(full["max_drawdown"]):
        fails.append("max_drawdown not finite")
    return fails, flags


def decide(new, base):
    flags = []
    hf, hflags = hard_constraints(new)
    flags += hflags
    if hf:
        return "REJECT", 3, ["HARD CONSTRAINT: " + "; ".join(hf)], flags
    if base is None:
        return ("BASELINE", 0,
                ["No baseline - recorded as honest baseline / last-accepted."], flags)

    wf, bwf = new["walk_forward"], base["walk_forward"]
    new_p, old_p = wf["weighted_fold_mar"], bwf["weighted_fold_mar"]
    p_chg = pct_change(new_p, old_p)
    if new_p is None or old_p is None or new_p <= old_p:
        return ("REJECT", 2,
                [f"clause1: weighted-fold MAR {old_p}->{new_p} did not improve"], flags)

    wf_chg = pct_change(wf["worst_fold_mar"], bwf["worst_fold_mar"])
    if wf_chg is not None and wf_chg < -ACCEPT["worstfold_drop_max_pct"]:
        return ("REJECT", 2,
                [f"clause2: worst-fold MAR worsened {wf_chg:.1f}% - gain concentrated"],
                flags)

    new_minpf = wf["oos_union"].get("min_regime_pf")
    old_minpf = bwf["oos_union"].get("min_regime_pf")
    rp_chg = pct_change(new_minpf, old_minpf)
    if rp_chg is not None and rp_chg < -ACCEPT["regime_pf_drop_max_pct"]:
        return ("REJECT", 2, [f"clause3: min-regime PF dropped {rp_chg:.1f}%"], flags)

    full = new["full"]
    oos = wf["oos_union"]
    if full["trade_count"] < ACCEPT["trades_floor_full"]:
        return ("REJECT", 2, ["clause4: full trades < floor"], flags)
    if oos["trade_count"] < ACCEPT["trades_floor_oos"]:
        return ("REJECT", 2, ["clause4: OOS trades < floor"], flags)

    dd_chg = pct_change(oos["max_drawdown"], bwf["oos_union"]["max_drawdown"])
    if dd_chg is not None and dd_chg > ACCEPT["maxdd_worsen_max_pct"]:
        return ("REJECT", 2, [f"clause5: OOS maxDD worsened {dd_chg:.1f}%"], flags)

    b_oos = bwf["oos_union"]
    trade_chg = pct_change(oos["trade_count"], b_oos["trade_count"])
    wr_jump = oos["win_rate"] - b_oos["win_rate"]
    if (wr_jump > ACCEPT["overfit_wr_jump_pts"] and trade_chg is not None
            and trade_chg < -ACCEPT["shrink_trade_drop_pct"]):
        return ("REJECT", 2,
                [f"OVERFIT-SUSPECT: WR +{wr_jump:.1f}pts while OOS trades "
                 f"{trade_chg:.1f}% - regime-carving"], flags)
    if (trade_chg is not None and trade_chg < -ACCEPT["shrink_trade_drop_pct"]
            and p_chg is not None and p_chg < ACCEPT["shrink_min_gain_pct"]):
        return ("REJECT", 2,
                [f"shrink-guard: OOS trades {trade_chg:.1f}% for only "
                 f"{p_chg:.1f}% weighted-MAR gain"], flags)

    return ("ACCEPT", 0,
            [f"ACCEPT: weighted-fold MAR {old_p}->{new_p} (+{p_chg:.1f}%), "
             f"worst-fold OK, {wf['profitable_fold_frac']:.0%} folds profitable"],
            flags)


def build_run(trades, run_id, holdout_locked, do_holdout):
    new = {"run_id": run_id, "full": metrics_for(trades),
           "walk_forward": walk_forward(trades)}
    if do_holdout:
        ho = [t for t in trades
              if HOLDOUT_YEARS[0] <= t["exit_date"].year <= HOLDOUT_YEARS[1]]
        new["holdout"] = metrics_for(ho)
    elif holdout_locked:
        new["holdout"] = {"_locked": True}
    return new


def cmd_score(args):
    trades = load_trades(args.trades)
    if args.final_holdout:
        new = build_run(trades, args.run_id, False, True)
        wf = new["walk_forward"]
        vm = wf["weighted_fold_mar"]
        hm = (new["holdout"] or {}).get("mar_ratio")
        overfit = (hm is None) or (vm and hm is not None and hm < 0.5 * vm)
        new["final_holdout_verdict"] = "OVERFIT" if overfit else "ROBUST"
        _emit(new, args.out)
        print(f"[FINAL] weighted-fold MAR={vm}  holdout MAR={hm}  -> "
              f"{new['final_holdout_verdict']}")
        sys.exit(4 if overfit else 0)

    new = build_run(trades, args.run_id, args.holdout_locked, False)
    base = None
    if args.baseline:
        try:
            with open(args.baseline) as f:
                base = json.load(f)
        except FileNotFoundError:
            base = None

    verdict, code, reasons, flags = decide(new, base)
    new["verdict"] = verdict
    new["verdict_reasons"] = reasons
    if flags:
        new["note_flags"] = sorted(set(flags))
    _emit(new, args.out)

    wf, full = new["walk_forward"], new["full"]
    print(f"[{args.run_id}] {verdict}  ("
          f"full_trades={full['trade_count']}, wMAR={wf['weighted_fold_mar']}, "
          f"medMAR={wf['median_fold_mar']}, worstMAR={wf['worst_fold_mar']}, "
          f"profFolds={wf['profitable_fold_frac']:.0%}, "
          f"mean/med={full['mean_median_ratio']}, PF_diag={full['profit_factor']}) "
          f"| {reasons[0]}")
    sys.exit(code)


def cmd_promote(args):
    with open(args.metrics) as f:
        m = json.load(f)
    if m.get("verdict") not in ("ACCEPT", "BASELINE"):
        raise SystemExit(f"Refusing to promote a {m.get('verdict')} run.")
    with open(args.baseline, "w") as f:
        json.dump(m, f, indent=2)
    print(f"Promoted {m['run_id']} -> {args.baseline}")


def cmd_log(args):
    with open(args.metrics) as f:
        m = json.load(f)
    wf, full = m["walk_forward"], m["full"]
    rec = {
        "iteration": args.iteration,
        "run_id": m["run_id"],
        "decision": args.decision,
        "change": args.change,
        "primary_weighted_fold_mar": wf["weighted_fold_mar"],
        "median_fold_mar": wf["median_fold_mar"],
        "worst_fold_mar": wf["worst_fold_mar"],
        "profitable_fold_frac": wf["profitable_fold_frac"],
        "n_scored_folds": wf["n_scored_folds"],
        "full": {k: full[k] for k in (
            "trade_count", "cagr", "max_drawdown", "mar_ratio", "sharpe",
            "sortino", "avg_return", "median_return", "mean_median_ratio",
            "win_rate", "profit_factor", "avg_loss")},
        "oos_union": ({k: wf["oos_union"][k] for k in (
            "trade_count", "cagr", "max_drawdown", "mar_ratio", "win_rate",
            "profit_factor", "min_regime_pf")} if wf["oos_union"] else None),
        "per_fold_mar": [{"test_year": f["test_year"], "weight": f["weight"],
                          "mar": (f["metrics"]["mar_ratio"] if f["metrics"] else None)}
                         for f in wf["folds"]],
        "note_flags": m.get("note_flags", []),
        "note": args.note,
        "next": args.next,
    }
    with open(args.history, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"Appended iter {args.iteration} ({args.decision}) to {args.history}")


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score")
    s.add_argument("--trades", required=True)
    s.add_argument("--run-id", required=True)
    s.add_argument("--baseline")
    s.add_argument("--out")
    s.add_argument("--holdout-locked", action="store_true")
    s.add_argument("--final-holdout", action="store_true")
    s.set_defaults(func=cmd_score)

    pr = sub.add_parser("promote")
    pr.add_argument("--metrics", required=True)
    pr.add_argument("--baseline", required=True)
    pr.set_defaults(func=cmd_promote)

    lg = sub.add_parser("log")
    lg.add_argument("--metrics", required=True)
    lg.add_argument("--history", required=True)
    lg.add_argument("--iteration", type=int, required=True)
    lg.add_argument("--change", required=True)
    lg.add_argument("--decision", required=True, choices=["accept", "reject"])
    lg.add_argument("--note", default="")
    lg.add_argument("--next", default="")
    lg.set_defaults(func=cmd_log)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()