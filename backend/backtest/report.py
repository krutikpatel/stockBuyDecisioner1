"""
Generates backtest output: CSV files + self-contained HTML report with embedded charts.
"""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from backtest.config import RESULTS_DIR, HORIZONS
from backtest.metrics import build_metrics, DECISION_ORDER

# Try matplotlib import
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

DECISION_COLORS = {
    "BUY_NOW": "#22c55e",
    "BUY_STARTER": "#10b981",
    "BUY_ON_BREAKOUT": "#3b82f6",
    "WAIT_FOR_PULLBACK": "#eab308",
    "WATCHLIST": "#94a3b8",
    "AVOID": "#ef4444",
}


def save_csvs(signals: list[dict], metrics_by_horizon: dict) -> None:
    """Save raw signals and summary CSVs to RESULTS_DIR."""
    out = Path(RESULTS_DIR)
    out.mkdir(parents=True, exist_ok=True)

    # Raw signals
    df = pd.DataFrame(signals)
    df.to_csv(out / "raw_signals.csv", index=False)
    print(f"  Saved: {out / 'raw_signals.csv'} ({len(df)} rows)")

    # Summary by decision (short-term horizon)
    st = metrics_by_horizon.get("short_term", {})
    if st.get("by_decision"):
        pd.DataFrame(st["by_decision"]).to_csv(out / "summary_by_decision.csv", index=False)
        print(f"  Saved: {out / 'summary_by_decision.csv'}")

    # Summary by ticker (short-term)
    if st.get("by_ticker"):
        pd.DataFrame(st["by_ticker"]).to_csv(out / "summary_by_ticker.csv", index=False)
        print(f"  Saved: {out / 'summary_by_ticker.csv'}")


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return encoded


def _chart_win_rate_by_decision(by_decision: list[dict]) -> Optional[str]:
    if not HAS_MPL or not by_decision:
        return None
    decisions = [r["decision"] for r in by_decision]
    win_rates = [r["win_rate_pct"] for r in by_decision]
    avg_returns = [r["avg_return_pct"] for r in by_decision]
    colors = [DECISION_COLORS.get(d, "#94a3b8") for d in decisions]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("#1e293b")
    for ax in (ax1, ax2):
        ax.set_facecolor("#0f172a")
        ax.tick_params(colors="white")
        ax.spines["bottom"].set_color("#475569")
        ax.spines["left"].set_color("#475569")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    bars1 = ax1.bar(range(len(decisions)), win_rates, color=colors, edgecolor="#1e293b", linewidth=0.5)
    ax1.set_xticks(range(len(decisions)))
    ax1.set_xticklabels([d.replace("_", "\n") for d in decisions], color="white", fontsize=9)
    ax1.set_ylabel("Win Rate (%)", color="white")
    ax1.set_title("Win Rate by Decision Type", color="white", fontsize=12, pad=10)
    ax1.set_ylim(0, 100)
    ax1.axhline(50, color="#64748b", linestyle="--", linewidth=0.8, label="50% baseline")
    ax1.legend(fontsize=8, labelcolor="white", framealpha=0.2)
    for bar, val in zip(bars1, win_rates):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f"{val:.0f}%", ha="center", va="bottom", color="white", fontsize=9)

    c2 = ["#22c55e" if v >= 0 else "#ef4444" for v in avg_returns]
    bars2 = ax2.bar(range(len(decisions)), avg_returns, color=c2, edgecolor="#1e293b", linewidth=0.5)
    ax2.set_xticks(range(len(decisions)))
    ax2.set_xticklabels([d.replace("_", "\n") for d in decisions], color="white", fontsize=9)
    ax2.set_ylabel("Avg Return (%)", color="white")
    ax2.set_title("Avg Forward Return by Decision Type", color="white", fontsize=12, pad=10)
    ax2.axhline(0, color="#64748b", linestyle="--", linewidth=0.8)
    for bar, val in zip(bars2, avg_returns):
        ypos = bar.get_height() + 0.1 if val >= 0 else bar.get_height() - 0.5
        ax2.text(bar.get_x() + bar.get_width() / 2, ypos,
                 f"{val:+.1f}%", ha="center", va="bottom", color="white", fontsize=9)

    fig.tight_layout(pad=2)
    return _fig_to_base64(fig)


def _chart_score_bucket(by_score_bucket: list[dict]) -> Optional[str]:
    if not HAS_MPL or not by_score_bucket:
        return None
    labels = [r["bucket"] for r in by_score_bucket]
    returns = [r["avg_return_pct"] for r in by_score_bucket]
    win_rates = [r["win_rate_pct"] for r in by_score_bucket]
    counts = [r["count"] for r in by_score_bucket]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1e293b")
    ax.set_facecolor("#0f172a")
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("#475569")
    ax.spines["left"].set_color("#475569")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    x = range(len(labels))
    colors = ["#22c55e" if r >= 0 else "#ef4444" for r in returns]
    bars = ax.bar(x, returns, color=colors, edgecolor="#1e293b", linewidth=0.5, alpha=0.85, label="Avg Return")
    ax.axhline(0, color="#64748b", linestyle="--", linewidth=0.8)

    ax2 = ax.twinx()
    ax2.set_facecolor("#0f172a")
    ax2.plot(x, win_rates, color="#60a5fa", marker="o", linewidth=1.5, label="Win Rate %", zorder=5)
    ax2.set_ylabel("Win Rate (%)", color="#60a5fa")
    ax2.tick_params(colors="#60a5fa")
    ax2.spines["right"].set_color("#60a5fa")
    ax2.spines["top"].set_visible(False)
    ax2.spines["bottom"].set_visible(False)
    ax2.spines["left"].set_visible(False)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, color="white", fontsize=9)
    ax.set_ylabel("Avg Forward Return (%)", color="white")
    ax.set_title("Score Bucket → Forward Return Correlation", color="white", fontsize=12, pad=10)

    for bar, count, ret in zip(bars, counts, returns):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"n={count}", ha="center", va="bottom", color="white", fontsize=8)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, labelcolor="white", framealpha=0.2)

    fig.tight_layout(pad=2)
    return _fig_to_base64(fig)


def _chart_monthly(monthly: list[dict]) -> Optional[str]:
    if not HAS_MPL or not monthly:
        return None
    months = [r["month"] for r in monthly]
    returns = [r["avg_return_pct"] for r in monthly]
    win_rates = [r["win_rate_pct"] or 0 for r in monthly]

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#1e293b")
    ax.set_facecolor("#0f172a")
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("#475569")
    ax.spines["left"].set_color("#475569")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    x = range(len(months))
    colors = ["#22c55e" if r >= 0 else "#ef4444" for r in returns]
    ax.bar(x, returns, color=colors, edgecolor="#1e293b", linewidth=0.4, alpha=0.7, label="Avg Return")
    ax.axhline(0, color="#64748b", linestyle="--", linewidth=0.8)

    ax2 = ax.twinx()
    ax2.plot(x, win_rates, color="#60a5fa", linewidth=1.5, marker=".", label="Win Rate %")
    ax2.axhline(50, color="#94a3b8", linestyle=":", linewidth=0.8)
    ax2.set_ylabel("Win Rate (%)", color="#60a5fa")
    ax2.tick_params(colors="#60a5fa")
    ax2.spines["right"].set_color("#60a5fa")
    ax2.spines["top"].set_visible(False)
    ax2.spines["bottom"].set_visible(False)
    ax2.spines["left"].set_visible(False)

    ax.set_xticks(x)
    ax.set_xticklabels(months, color="white", fontsize=8, rotation=45, ha="right")
    ax.set_ylabel("Avg Forward Return (%)", color="white")
    ax.set_title("Monthly Signal Performance", color="white", fontsize=12, pad=10)

    fig.tight_layout(pad=2)
    return _fig_to_base64(fig)


def _render_table(rows: list[dict], title: str) -> str:
    if not rows:
        return f"<p class='empty'>No data for {title}</p>"
    headers = list(rows[0].keys())
    html = f"<h3>{title}</h3><div class='table-wrap'><table><thead><tr>"
    for h in headers:
        html += f"<th>{h.replace('_', ' ').title()}</th>"
    html += "</tr></thead><tbody>"
    for row in rows:
        html += "<tr>"
        for h in headers:
            val = row.get(h)
            cls = ""
            if isinstance(val, float):
                if "return" in h or "excess" in h or "alpha" in h:
                    cls = ' class="pos"' if val >= 0 else ' class="neg"'
                display = f"{val:+.2f}%" if ("return" in h or "excess" in h or "alpha" in h or "rate" in h) else f"{val:.2f}"
            elif val is None:
                display = "—"
            else:
                display = str(val)
            html += f"<td{cls}>{display}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html


def generate_html_report(signals: list[dict], metrics_by_horizon: dict) -> str:
    """Generate a self-contained HTML report with embedded charts."""
    st = metrics_by_horizon.get("short_term", {})
    mt = metrics_by_horizon.get("medium_term", {})
    lt = metrics_by_horizon.get("long_term", {})

    overall = st.get("overall_stats", {})
    sim = st.get("portfolio_simulation", {})

    # Charts
    chart_decision = _chart_win_rate_by_decision(st.get("by_decision", []))
    chart_score = _chart_score_bucket(st.get("by_score_bucket", []))
    chart_monthly = _chart_monthly(st.get("monthly_breakdown", []))

    def img_tag(b64: Optional[str]) -> str:
        if not b64:
            return "<p class='empty'>Chart unavailable (matplotlib not installed)</p>"
        return f'<img src="data:image/png;base64,{b64}" style="max-width:100%;border-radius:8px">'

    def stat(label, val, suffix="", color=""):
        c = f' style="color:{color}"' if color else ""
        return f'<div class="stat-card"><div class="stat-label">{label}</div><div class="stat-value"{c}>{val}{suffix}</div></div>'

    def fmt(v, d=2):
        if v is None:
            return "N/A"
        return f"{v:.{d}f}"

    # Overall stats bar
    win_rate = overall.get("overall_win_rate_pct")
    avg_ret = overall.get("avg_return_pct")
    avg_exc = overall.get("avg_excess_vs_spy_pct")
    corr = overall.get("score_return_correlation")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Decision Tool — Backtest Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #0f172a; color: #e2e8f0; line-height: 1.6; }}
  .header {{ background: #1e293b; border-bottom: 1px solid #334155;
             padding: 24px 32px; }}
  .header h1 {{ font-size: 1.8rem; color: #f1f5f9; font-weight: 700; }}
  .header p {{ color: #94a3b8; font-size: 0.9rem; margin-top: 4px; }}
  .container {{ max-width: 1300px; margin: 0 auto; padding: 24px 32px; }}
  .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px;
              padding: 24px; margin-bottom: 24px; }}
  .section h2 {{ font-size: 1.2rem; color: #f1f5f9; margin-bottom: 16px;
                 border-bottom: 1px solid #334155; padding-bottom: 8px; }}
  .section h3 {{ font-size: 1rem; color: #cbd5e1; margin: 16px 0 10px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
  .stat-card {{ background: #0f172a; border-radius: 8px; padding: 14px 16px;
                text-align: center; border: 1px solid #334155; }}
  .stat-label {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase;
                 letter-spacing: 0.05em; margin-bottom: 4px; }}
  .stat-value {{ font-size: 1.4rem; font-weight: 700; color: #f1f5f9;
                 font-family: monospace; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; min-width: 600px; }}
  th {{ background: #0f172a; color: #94a3b8; text-align: left;
        padding: 8px 12px; font-weight: 600; font-size: 0.75rem;
        text-transform: uppercase; letter-spacing: 0.04em; border-bottom: 1px solid #334155; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:hover td {{ background: #0f172a; }}
  td.pos {{ color: #4ade80; font-weight: 600; }}
  td.neg {{ color: #f87171; font-weight: 600; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .tab {{ padding: 6px 14px; border-radius: 6px; border: 1px solid #334155;
          background: #0f172a; color: #94a3b8; cursor: pointer; font-size: 0.85rem; }}
  .tab.active {{ background: #2563eb; border-color: #2563eb; color: white; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 0.75rem; font-weight: 600; }}
  .empty {{ color: #64748b; font-size: 0.9rem; padding: 12px 0; }}
  .disclaimer {{ color: #475569; font-size: 0.75rem; margin-top: 32px;
                 padding: 12px; border: 1px solid #334155; border-radius: 8px; }}
  @media (max-width: 768px) {{ .container {{ padding: 16px; }} }}
</style>
</head>
<body>
<div class="header">
  <h1>Stock Decision Tool — Backtest Report</h1>
  <p>2-year weekly backtest | {st.get('resolved_signals', 0)} resolved signals | Short-term horizon shown by default</p>
</div>
<div class="container">

  <!-- Overall Stats -->
  <div class="section">
    <h2>Overall Performance (Short-Term Horizon)</h2>
    <div class="stats-grid">
      {stat("Total Signals", st.get("total_signals", "N/A"))}
      {stat("Resolved", st.get("resolved_signals", "N/A"))}
      {stat("Win Rate", fmt(win_rate), "%", "#4ade80" if win_rate and win_rate > 50 else "#f87171")}
      {stat("Avg Return", (f"+{avg_ret:.2f}" if avg_ret and avg_ret >= 0 else fmt(avg_ret)), "%",
             "#4ade80" if avg_ret and avg_ret >= 0 else "#f87171")}
      {stat("Avg vs SPY", (f"+{avg_exc:.2f}" if avg_exc and avg_exc >= 0 else fmt(avg_exc)), "%",
             "#4ade80" if avg_exc and avg_exc >= 0 else "#f87171")}
      {stat("Score Correlation", fmt(corr, 3))}
      {stat("Model Annualized", fmt(sim.get("model_annualized_return_pct")), "%")}
      {stat("SPY Annualized", fmt(sim.get("spy_annualized_return_pct")), "%")}
      {stat("Alpha", (f"+{sim.get('alpha_pct'):.2f}" if sim.get('alpha_pct') and sim.get('alpha_pct', 0) >= 0
             else fmt(sim.get('alpha_pct'))), "%",
             "#4ade80" if sim.get("alpha_pct") and sim.get("alpha_pct", 0) >= 0 else "#f87171")}
    </div>
  </div>

  <!-- Horizon Tabs -->
  <div class="section">
    <h2>Win Rate &amp; Return by Decision Type</h2>
    <div class="tabs" id="horizonTabs">
      <div class="tab active" onclick="switchTab('short_term')">Short-Term</div>
      <div class="tab" onclick="switchTab('medium_term')">Medium-Term</div>
      <div class="tab" onclick="switchTab('long_term')">Long-Term</div>
    </div>
    <div id="tab_short_term" class="tab-content active">
      {_render_table(st.get("by_decision", []), "Short-Term Decisions")}
    </div>
    <div id="tab_medium_term" class="tab-content">
      {_render_table(mt.get("by_decision", []), "Medium-Term Decisions")}
    </div>
    <div id="tab_long_term" class="tab-content">
      {_render_table(lt.get("by_decision", []), "Long-Term Decisions")}
    </div>
  </div>

  <!-- Charts -->
  <div class="section">
    <h2>Decision Performance Charts</h2>
    {img_tag(chart_decision)}
  </div>

  <div class="section">
    <h2>Score → Return Correlation</h2>
    {img_tag(chart_score)}
    {_render_table(st.get("by_score_bucket", []), "Score Bucket Analysis")}
  </div>

  <div class="section">
    <h2>Monthly Breakdown</h2>
    {img_tag(chart_monthly)}
  </div>

  <!-- Per-Ticker -->
  <div class="section">
    <h2>Per-Ticker Summary (Short-Term)</h2>
    {_render_table(st.get("by_ticker", []), "Ticker Performance")}
  </div>

  <!-- Portfolio Simulation -->
  <div class="section">
    <h2>Portfolio Simulation (BUY_NOW + BUY_STARTER signals)</h2>
    <div class="stats-grid">
      {stat("Total Trades", sim.get("total_trades", "N/A"))}
      {stat("Avg Trade Return", fmt(sim.get("avg_trade_return_pct")), "%")}
      {stat("Hit Rate", fmt(sim.get("hit_rate_pct")), "%")}
      {stat("Model Ann. Return", fmt(sim.get("model_annualized_return_pct")), "%")}
      {stat("SPY Ann. Return", fmt(sim.get("spy_annualized_return_pct")), "%")}
      {stat("Alpha", fmt(sim.get("alpha_pct")), "%")}
    </div>
    <p style="color:#64748b;font-size:0.8rem;margin-top:12px">
      Annualized return = avg trade return × periods/year (short-term: 13, medium-term: 4, long-term: 1).
      This is an approximation, not a compounded CAGR.
    </p>
  </div>

  <div class="disclaimer">
    <strong>Disclaimer:</strong> This backtest uses yfinance historical price data for returns but approximates
    fundamental data from quarterly financial statements. News sentiment and options catalyst scores are set to
    neutral (50) for all historical dates, which means short-term signal quality may be understated.
    Past backtest performance does not guarantee future results. This is a decision-support tool, not financial advice.
  </div>
</div>

<script>
function switchTab(horizon) {{
  document.querySelectorAll('.tab').forEach((t, i) => {{
    const ids = ['short_term', 'medium_term', 'long_term'];
    t.classList.toggle('active', ids[i] === horizon);
  }});
  document.querySelectorAll('.tab-content').forEach(c => {{
    c.classList.toggle('active', c.id === 'tab_' + horizon);
  }});
}}
</script>
</body>
</html>"""
    return html


def save_report(signals: list[dict], metrics_by_horizon: dict) -> None:
    """Write all output files to RESULTS_DIR."""
    out = Path(RESULTS_DIR)
    out.mkdir(parents=True, exist_ok=True)

    print("\nGenerating reports...")

    # HTML
    html = generate_html_report(signals, metrics_by_horizon)
    html_path = out / "report.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  Saved: {html_path}")

    # JSON
    json_path = out / "report.json"
    with open(json_path, "w") as f:
        json.dump(metrics_by_horizon, f, indent=2, default=str)
    print(f"  Saved: {json_path}")
