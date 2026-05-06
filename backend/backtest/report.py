"""
Generates a self-contained HTML backtest report and companion CSV files.

Public entry point:  generate_report(all_metrics, signals, output_dir)

The HTML uses only inline CSS and vanilla JS — no external dependencies,
so the file opens correctly offline.

Sections (phase-gated):
  1. Executive Summary
  2. Signal Performance by Decision Label  (all phases)
  3. Score Bucket Analysis                 (all phases)
  4. Per-Ticker Performance                (all phases)
  5. Monthly Breakdown                     (all phases)
  6. Portfolio Simulation                  (all phases)
  7. Regime Performance Heatmap            (Phase 2+)
  8. Archetype Performance                 (Phase 3)
  9. Signal Card Effectiveness             (Phase 3)
 10. Cross-Horizon Summary                 (all phases)
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(val, suffix: str = "", decimals: int = 1, default: str = "—") -> str:
    if val is None or (isinstance(val, float) and val != val):
        return default
    return f"{val:.{decimals}f}{suffix}"


def _color_return(val: Optional[float], neutral_zero: bool = False) -> str:
    if val is None:
        return ""
    if val > 3:
        return "color:#16a34a;font-weight:600"     # green
    if val > 0:
        return "color:#4ade80"                      # light green
    if val < -3:
        return "color:#dc2626;font-weight:600"      # red
    if val < 0:
        return "color:#f87171"                      # light red
    return "color:#94a3b8"                          # neutral grey


def _table(headers: list[str], rows: list[list], col_styles: list[str] | None = None) -> str:
    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = []
    for row in rows:
        tds = []
        for i, cell in enumerate(row):
            style = ""
            if col_styles and i < len(col_styles):
                style = col_styles[i]
            tds.append(f"<td style='{style}'>{cell}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return (
        "<table><thead><tr>" + ths + "</tr></thead><tbody>"
        + "".join(trs) + "</tbody></table>"
    )


def _section(title: str, content: str, anchor: str = "") -> str:
    aid = f'id="{anchor}"' if anchor else ""
    return f"""
<section {aid} class="section">
  <h2>{title}</h2>
  {content}
</section>
"""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _exec_summary(all_metrics: dict, signals: list[dict], phase: int) -> str:
    if not signals:
        return "<p>No signals generated.</p>"

    df = pd.DataFrame(signals)
    total  = len(df)
    resolved = df["forward_return"].notna().sum()
    tickers  = df["ticker"].nunique()
    dates    = df["date"].nunique()
    date_min = df["date"].min()
    date_max = df["date"].max()

    # Cross-horizon win rates
    horizon_lines = []
    for h in ["short_term", "medium_term", "long_term"]:
        m = all_metrics.get(h, {})
        ov = m.get("overall_stats", {})
        wr = ov.get("overall_win_rate_pct")
        ar = ov.get("avg_return_pct")
        xs = ov.get("avg_excess_spy_pct")
        horizon_lines.append(
            f"<li><strong>{h.replace('_',' ').title()}:</strong> "
            f"Win rate {_fmt(wr, '%')} | Avg return {_fmt(ar, '%')} | "
            f"Avg excess vs SPY {_fmt(xs, '%')}</li>"
        )

    phase_label = {1: "Technical-only (Phase 1)", 2: "Technical + Regime (Phase 2)",
                   3: "Technical + Regime + Fundamentals (Phase 3)"}.get(phase, f"Phase {phase}")

    return f"""
<div class="summary-grid">
  <div class="summary-card"><div class="kv-label">Total Signals</div><div class="kv-val">{total:,}</div></div>
  <div class="summary-card"><div class="kv-label">Resolved Outcomes</div><div class="kv-val">{resolved:,}</div></div>
  <div class="summary-card"><div class="kv-label">Tickers</div><div class="kv-val">{tickers}</div></div>
  <div class="summary-card"><div class="kv-label">Test Dates</div><div class="kv-val">{dates:,}</div></div>
  <div class="summary-card"><div class="kv-label">Date Range</div><div class="kv-val">{date_min} → {date_max}</div></div>
  <div class="summary-card"><div class="kv-label">Phase</div><div class="kv-val">{phase_label}</div></div>
</div>
<h3 style="margin-top:1.5rem">Performance by Horizon</h3>
<ul>{"".join(horizon_lines)}</ul>
"""


def _decision_table(by_decision: list[dict]) -> str:
    if not by_decision:
        return "<p>No data.</p>"
    headers = [
        "Decision", "Count", "Avg Return %", "Median %",
        "Win Rate %", "Beats SPY %", "Avg Excess SPY %",
        "Avg Max DD %", "Profit Factor",
    ]
    rows = []
    for r in by_decision:
        ar = r.get("avg_return_pct")
        rows.append([
            f"<code>{r.get('decision','')}</code>",
            r.get("resolved", r.get("count", "—")),
            f"<span style='{_color_return(ar)}'>{_fmt(ar, '%')}</span>",
            f"<span style='{_color_return(r.get('median_return_pct'))}'>{_fmt(r.get('median_return_pct'), '%')}</span>",
            _fmt(r.get("win_rate_pct"), "%"),
            _fmt(r.get("benchmark_win_rate_pct"), "%"),
            f"<span style='{_color_return(r.get('avg_excess_spy_pct'))}'>{_fmt(r.get('avg_excess_spy_pct'), '%')}</span>",
            _fmt(r.get("avg_max_drawdown_pct"), "%"),
            _fmt(r.get("profit_factor"), "", 2),
        ])
    return _table(headers, rows)


def _score_bucket_table(by_bucket: list[dict]) -> str:
    if not by_bucket:
        return "<p>No data.</p>"
    headers = ["Score Bucket", "Count", "Avg Return %", "Win Rate %", "Avg Excess SPY %"]
    rows = []
    for r in by_bucket:
        ar = r.get("avg_return_pct")
        rows.append([
            r.get("bucket", "—"),
            r.get("resolved", r.get("count", "—")),
            f"<span style='{_color_return(ar)}'>{_fmt(ar, '%')}</span>",
            _fmt(r.get("win_rate_pct"), "%"),
            f"<span style='{_color_return(r.get('avg_excess_spy_pct'))}'>{_fmt(r.get('avg_excess_spy_pct'), '%')}</span>",
        ])
    return _table(headers, rows)


def _ticker_table(by_ticker: list[dict]) -> str:
    if not by_ticker:
        return "<p>No data.</p>"
    headers = ["Ticker", "Signals", "Avg Score", "Avg Return %", "Win Rate %", "Avg Excess SPY %", "Best Decision"]
    rows = []
    for r in by_ticker:
        ar = r.get("avg_return_pct")
        rows.append([
            f"<strong>{r.get('ticker','')}</strong>",
            r.get("resolved", r.get("count", "—")),
            _fmt(r.get("avg_score"), ""),
            f"<span style='{_color_return(ar)}'>{_fmt(ar, '%')}</span>",
            _fmt(r.get("win_rate_pct"), "%"),
            f"<span style='{_color_return(r.get('avg_excess_spy_pct'))}'>{_fmt(r.get('avg_excess_spy_pct'), '%')}</span>",
            f"<code>{r.get('best_decision','')}</code>",
        ])
    return _table(headers, rows)


def _monthly_table(monthly: list[dict]) -> str:
    if not monthly:
        return "<p>No data.</p>"
    headers = ["Month", "Signals", "Avg Return %", "Win Rate %", "Buy Signals", "Avoid Signals"]
    rows = []
    for r in monthly:
        ar = r.get("avg_return_pct")
        rows.append([
            r.get("month", "—"),
            r.get("signals", "—"),
            f"<span style='{_color_return(ar)}'>{_fmt(ar, '%')}</span>",
            _fmt(r.get("win_rate_pct"), "%"),
            r.get("buy_signals", 0),
            r.get("avoid_signals", 0),
        ])
    return _table(headers, rows)


def _portfolio_section(sim: dict) -> str:
    if not sim or sim.get("total_trades", 0) == 0:
        return "<p>No buy signals in this horizon.</p>"
    lines = [
        f"<li>Total buy trades: <strong>{sim.get('total_trades',0)}</strong></li>",
        f"<li>Avg trade return: <strong>{_fmt(sim.get('avg_trade_return_pct'), '%')}</strong></li>",
        f"<li>Hit rate: <strong>{_fmt(sim.get('hit_rate_pct'), '%')}</strong></li>",
        f"<li>Avg SPY return (same periods): <strong>{_fmt(sim.get('avg_spy_return_pct'), '%')}</strong></li>",
        f"<li>Annualised model return: <strong>{_fmt(sim.get('model_annualized_return_pct'), '%')}</strong></li>",
        f"<li>Annualised SPY return: <strong>{_fmt(sim.get('spy_annualized_return_pct'), '%')}</strong></li>",
        f"<li>Alpha (annualised): <strong style='{_color_return(sim.get('alpha_pct'))}'>{_fmt(sim.get('alpha_pct'), '%')}</strong></li>",
    ]
    return "<ul>" + "".join(lines) + "</ul>"


def _regime_heatmap(by_regime_decision: list[dict]) -> str:
    """Build a pivot-style HTML table: rows = decisions, cols = regimes."""
    if not by_regime_decision:
        return "<p>No regime data available (Phase 2+ required).</p>"

    df = pd.DataFrame(by_regime_decision)
    if df.empty:
        return "<p>No data.</p>"

    regimes   = sorted(df["regime"].unique())
    decisions = sorted(df["decision"].unique())

    # Pivot on avg_excess_spy_pct
    headers = ["Decision"] + regimes
    rows = []
    for dec in decisions:
        row = [f"<code>{dec}</code>"]
        for reg in regimes:
            match = df[(df["decision"] == dec) & (df["regime"] == reg)]
            if match.empty:
                row.append("—")
            else:
                val = match.iloc[0].get("avg_excess_spy_pct")
                cnt = match.iloc[0].get("count", "")
                cell = f"<span style='{_color_return(val)}'>{_fmt(val, '%')}</span><br><small>n={cnt}</small>"
                row.append(cell)
        rows.append(row)

    return (
        "<p>Values show average excess return vs SPY. Rows = decision labels, columns = market regimes.</p>"
        + _table(headers, rows)
    )


def _regime_summary_table(by_regime: list[dict]) -> str:
    if not by_regime:
        return "<p>No regime data.</p>"
    headers = ["Regime", "Signals", "Avg Return %", "Win Rate %", "Avg Excess SPY %"]
    rows = []
    for r in by_regime:
        ar = r.get("avg_return_pct")
        rows.append([
            f"<strong>{r.get('regime','')}</strong>",
            r.get("resolved", r.get("count", "—")),
            f"<span style='{_color_return(ar)}'>{_fmt(ar, '%')}</span>",
            _fmt(r.get("win_rate_pct"), "%"),
            f"<span style='{_color_return(r.get('avg_excess_spy_pct'))}'>{_fmt(r.get('avg_excess_spy_pct'), '%')}</span>",
        ])
    return _table(headers, rows)


def _archetype_table(by_archetype: list[dict]) -> str:
    if not by_archetype:
        return "<p>No archetype data available (Phase 3 required).</p>"
    headers = ["Archetype", "Signals", "Avg Score", "Avg Return %", "Win Rate %", "Avg Excess SPY %", "Best Decision"]
    rows = []
    for r in by_archetype:
        ar = r.get("avg_return_pct")
        rows.append([
            f"<strong>{r.get('archetype','')}</strong>",
            r.get("resolved", r.get("count", "—")),
            _fmt(r.get("avg_score"), ""),
            f"<span style='{_color_return(ar)}'>{_fmt(ar, '%')}</span>",
            _fmt(r.get("win_rate_pct"), "%"),
            f"<span style='{_color_return(r.get('avg_excess_spy_pct'))}'>{_fmt(r.get('avg_excess_spy_pct'), '%')}</span>",
            f"<code>{r.get('best_decision','')}</code>",
        ])
    return _table(headers, rows)


def _signal_card_table(by_sc: list[dict]) -> str:
    if not by_sc:
        return "<p>No signal card data available (Phase 3 required).</p>"
    headers = [
        "Signal Card", "Signals", "Avg Score",
        "Corr with Return", "Q1 Low Avg %", "Q2 Avg %", "Q3 Avg %", "Q4 High Avg %",
    ]
    rows = []
    for r in by_sc:
        qr = r.get("quartile_returns", {})
        corr = r.get("corr_with_return")
        corr_color = _color_return(corr * 100 if corr is not None else None)  # scale for color
        q1_val = qr.get("Q1 Low")
        q2_val = qr.get("Q2")
        q3_val = qr.get("Q3")
        q4_val = qr.get("Q4 High")
        rows.append([
            f"<strong>{r.get('card','')}</strong>",
            r.get("n_signals", "—"),
            _fmt(r.get("avg_score"), ""),
            f"<span style='{corr_color}'>{_fmt(corr, '', 4)}</span>",
            f"<span style='{_color_return(q1_val)}'>{_fmt(q1_val, '%')}</span>",
            f"<span style='{_color_return(q2_val)}'>{_fmt(q2_val, '%')}</span>",
            f"<span style='{_color_return(q3_val)}'>{_fmt(q3_val, '%')}</span>",
            f"<span style='{_color_return(q4_val)}'>{_fmt(q4_val, '%')}</span>",
        ])
    return (
        "<p>Correlation of each signal card score with forward returns. "
        "Quartile returns show avg forward return for bottom-25% (Q1) to top-25% (Q4) scoring signals.</p>"
        + _table(headers, rows)
    )


def _cross_horizon_table(cross: list[dict]) -> str:
    if not cross:
        return "<p>No data.</p>"
    headers = ["Horizon", "Signals", "Avg Return %", "Win Rate %", "Avg Excess SPY %"]
    rows = []
    for r in cross:
        ar = r.get("avg_return_pct")
        rows.append([
            r.get("horizon", "—").replace("_", " ").title(),
            r.get("count", "—"),
            f"<span style='{_color_return(ar)}'>{_fmt(ar, '%')}</span>",
            _fmt(r.get("win_rate_pct"), "%"),
            f"<span style='{_color_return(r.get('avg_excess_spy'))}'>{_fmt(r.get('avg_excess_spy'), '%')}</span>",
        ])
    return _table(headers, rows)


# ---------------------------------------------------------------------------
# CSS / HTML scaffolding
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #e2e8f0;
       font-size: 14px; line-height: 1.6; }
h1 { font-size: 1.6rem; font-weight: 700; color: #f8fafc; padding: 1.5rem 2rem 0.5rem; }
h2 { font-size: 1.2rem; font-weight: 600; color: #cbd5e1; margin-bottom: 1rem; padding-bottom: 0.4rem;
     border-bottom: 1px solid #334155; }
h3 { font-size: 1rem; font-weight: 600; color: #94a3b8; margin: 1rem 0 0.5rem; }
.section { padding: 1.5rem 2rem; border-bottom: 1px solid #1e293b; }
.section:last-child { border-bottom: none; }
nav { background: #1e293b; padding: 0.75rem 2rem; display: flex; gap: 1rem; flex-wrap: wrap;
      position: sticky; top: 0; z-index: 10; border-bottom: 1px solid #334155; }
nav a { color: #94a3b8; text-decoration: none; font-size: 0.85rem; }
nav a:hover { color: #e2e8f0; }
.meta { color: #64748b; font-size: 0.8rem; padding: 0.5rem 2rem 1rem; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
.summary-card { background: #1e293b; border-radius: 8px; padding: 0.75rem 1rem; }
.kv-label { color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.kv-val { color: #f1f5f9; font-size: 1.1rem; font-weight: 600; margin-top: 0.2rem; }
table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; font-size: 0.85rem; }
th { background: #1e293b; color: #94a3b8; text-align: left; padding: 0.5rem 0.75rem;
     font-weight: 500; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
td { padding: 0.45rem 0.75rem; border-bottom: 1px solid #1e293b; }
tr:hover td { background: #1a2535; }
code { background: #1e293b; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.8rem; color: #7dd3fc; }
.tabs { display: flex; gap: 0.25rem; margin-bottom: 1rem; flex-wrap: wrap; }
.tab-btn { background: #1e293b; color: #94a3b8; border: none; padding: 0.4rem 0.9rem;
           border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
.tab-btn.active { background: #334155; color: #e2e8f0; }
.tab-pane { display: none; }
.tab-pane.active { display: block; }
small { color: #64748b; }
ul { padding-left: 1.2rem; }
li { margin: 0.2rem 0; }
"""

_JS = """
function switchTab(groupId, tabId) {
  document.querySelectorAll('#' + groupId + ' .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('#' + groupId + ' .tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById(groupId + '-btn-' + tabId).classList.add('active');
  document.getElementById(groupId + '-pane-' + tabId).classList.add('active');
}
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.tab-btn[data-group]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      switchTab(btn.dataset.group, btn.dataset.tab);
    });
  });
});
"""


def _tabs(group_id: str, tabs: list[tuple[str, str]]) -> str:
    """Render tabbed panels.  tabs = list of (label, html_content)."""
    btn_html = ""
    pane_html = ""
    for i, (label, content) in enumerate(tabs):
        tab_id = f"t{i}"
        active = " active" if i == 0 else ""
        btn_html += (
            f'<button class="tab-btn{active}" id="{group_id}-btn-{tab_id}" '
            f'data-group="{group_id}" data-tab="{tab_id}">{label}</button>'
        )
        pane_html += (
            f'<div class="tab-pane{active}" id="{group_id}-pane-{tab_id}">{content}</div>'
        )
    return (
        f'<div id="{group_id}">'
        f'<div class="tabs">{btn_html}</div>'
        f'{pane_html}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Main HTML assembly
# ---------------------------------------------------------------------------

def _build_horizon_html(m: dict, horizon: str) -> str:
    """Build the full content for one horizon tab."""
    label_map = {
        "short_term":  "Short-Term (20D)",
        "medium_term": "Medium-Term (63D)",
        "long_term":   "Long-Term (252D)",
    }
    label = label_map.get(horizon, horizon)
    ov    = m.get("overall_stats", {})
    parts = [
        f"<h3>Overall: "
        f"Win rate {_fmt(ov.get('overall_win_rate_pct'), '%')} | "
        f"Avg return {_fmt(ov.get('avg_return_pct'), '%')} | "
        f"Avg excess SPY {_fmt(ov.get('avg_excess_spy_pct'), '%')} | "
        f"Score-return corr {_fmt(ov.get('score_return_correlation'), '', 4)}</h3>",

        "<h3>Decision Label Performance</h3>",
        _decision_table(m.get("by_decision", [])),

        "<h3>Score Bucket Analysis</h3>",
        _score_bucket_table(m.get("by_score_bucket", [])),

        "<h3>Portfolio Simulation (Buy Signals)</h3>",
        _portfolio_section(m.get("portfolio_simulation", {})),
    ]

    if "by_regime" in m:
        parts += [
            "<h3>Performance by Market Regime</h3>",
            _regime_summary_table(m.get("by_regime", [])),
            "<h3>Regime × Decision Heatmap (Avg Excess Return vs SPY)</h3>",
            _regime_heatmap(m.get("by_regime_decision", [])),
        ]

    if "by_archetype" in m:
        parts += [
            "<h3>Performance by Stock Archetype</h3>",
            _archetype_table(m.get("by_archetype", [])),
        ]

    if "by_signal_card" in m:
        parts += [
            "<h3>Signal Card Effectiveness</h3>",
            _signal_card_table(m.get("by_signal_card", [])),
        ]

    parts += [
        "<h3>Per-Ticker Performance</h3>",
        _ticker_table(m.get("by_ticker", [])),

        "<h3>Monthly Breakdown</h3>",
        _monthly_table(m.get("monthly_breakdown", [])),
    ]

    return "".join(parts)


def _build_html(all_metrics: dict, signals: list[dict], phase: int) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine phase from signals if not provided
    if signals:
        phases_present = set(s.get("phase", 1) for s in signals)
        phase = max(phases_present)

    # Navigation
    nav_links = [
        '<a href="#summary">Summary</a>',
        '<a href="#horizons">Horizons</a>',
        '<a href="#cross">Cross-Horizon</a>',
    ]
    nav = "<nav>" + " | ".join(nav_links) + "</nav>"

    # Executive summary section
    exec_html = _section(
        "Executive Summary",
        _exec_summary(all_metrics, signals, phase),
        "summary",
    )

    # Tabbed horizon sections
    horizon_tabs = []
    for h in ["short_term", "medium_term", "long_term"]:
        m = all_metrics.get(h, {})
        if not m:
            continue
        label = {"short_term": "Short-Term (20D)",
                 "medium_term": "Medium-Term (63D)",
                 "long_term": "Long-Term (252D)"}[h]
        horizon_tabs.append((label, _build_horizon_html(m, h)))

    horizons_html = _section(
        "Performance by Horizon",
        _tabs("horizons", horizon_tabs) if horizon_tabs else "<p>No horizon data.</p>",
        "horizons",
    )

    # Cross-horizon summary
    cross = all_metrics.get("cross_horizon", [])
    cross_html = _section(
        "Cross-Horizon Summary",
        _cross_horizon_table(cross),
        "cross",
    )

    body = exec_html + horizons_html + cross_html

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Backtest Report</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Stock Decision Tool — Backtest Report</h1>
<div class="meta">Generated: {generated} | Phase {phase}</div>
{nav}
{body}
<script>{_JS}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------

def _export_csvs(all_metrics: dict, signals: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Raw signals with outcomes
    if signals:
        pd.DataFrame(signals).to_csv(output_dir / "signals_with_outcomes.csv", index=False)

    for horizon in ["short_term", "medium_term", "long_term"]:
        m = all_metrics.get(horizon, {})
        prefix = horizon

        def _to_csv(key: str, filename: str) -> None:
            data = m.get(key)
            if data:
                pd.DataFrame(data).to_csv(output_dir / filename, index=False)

        _to_csv("by_decision",      f"{prefix}_by_decision.csv")
        _to_csv("by_score_bucket",  f"{prefix}_by_score_bucket.csv")
        _to_csv("by_ticker",        f"{prefix}_by_ticker.csv")
        _to_csv("monthly_breakdown", f"{prefix}_monthly.csv")
        if "by_regime" in m:
            _to_csv("by_regime",          f"{prefix}_by_regime.csv")
            _to_csv("by_regime_decision",  f"{prefix}_by_regime_decision.csv")
        if "by_archetype" in m:
            _to_csv("by_archetype",         f"{prefix}_by_archetype.csv")
            _to_csv("by_archetype_decision", f"{prefix}_by_archetype_decision.csv")
        if "by_signal_card" in m:
            _to_csv("by_signal_card", f"{prefix}_by_signal_card.csv")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(
    all_metrics: dict,
    signals: list[dict],
    output_dir: str,
    phase: int = 3,
) -> None:
    """Generate HTML report + CSV exports.

    Args:
        all_metrics: Output of metrics.build_all_horizons_metrics().
        signals:     Raw signal list with outcomes attached.
        output_dir:  Directory to write report.html and CSV files.
        phase:       Backtest phase (controls which sections are included).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    html = _build_html(all_metrics, signals, phase)
    report_path = out / "report.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to {report_path}")

    _export_csvs(all_metrics, signals, out)
    print(f"CSVs written to {out}/")
