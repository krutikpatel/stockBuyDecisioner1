from __future__ import annotations

from app.models.response import StockAnalysisResult


def generate_markdown(result: StockAnalysisResult) -> str:
    md = result.market_data
    ti = result.technicals
    fu = result.fundamentals
    va = result.valuation
    ea = result.earnings
    ne = result.news

    def _pct(v) -> str:
        return f"{v*100:.1f}%" if v is not None else "N/A"

    def _val(v, fmt=".2f") -> str:
        return f"{v:{fmt}}" if v is not None else "N/A"

    def _mil(v) -> str:
        if v is None:
            return "N/A"
        b = v / 1_000_000_000
        if abs(b) >= 1:
            return f"${b:.2f}B"
        return f"${v/1_000_000:.0f}M"

    lines = [
        f"# Stock Decision Report: {result.ticker}",
        "",
        f"> Generated at: {result.generated_at}  ",
        f"> Current Price: **${md.current_price:.2f}**",
        "",
        "---",
        "",
        "## Final Summary",
        "",
    ]

    for rec in result.recommendations:
        lines.append(f"- **{rec.horizon.replace('_', '-').title()}**: {rec.decision} (Score: {rec.score:.0f}/100, Confidence: {rec.confidence})")

    lines += [
        "",
        "---",
        "",
        "## Current Market Data",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Current Price | ${md.current_price:.2f} |",
        f"| Previous Close | ${md.previous_close:.2f} |",
        f"| 52-Week High | ${_val(md.week_52_high)} |",
        f"| 52-Week Low | ${_val(md.week_52_low)} |",
        f"| Market Cap | {_mil(md.market_cap)} |",
        f"| Beta | {_val(md.beta)} |",
        f"| 1-Month Return | {_val(md.return_1m)}% |",
        f"| 3-Month Return | {_val(md.return_3m)}% |",
        f"| 6-Month Return | {_val(md.return_6m)}% |",
        f"| 1-Year Return | {_val(md.return_1y)}% |",
        f"| YTD Return | {_val(md.return_ytd)}% |",
        "",
        "---",
        "",
        "## Technical Setup",
        "",
        f"| Indicator | Value |",
        f"|-----------|-------|",
        f"| Trend | {ti.trend.label.replace('_', ' ').title()} |",
        f"| MA(20) | ${_val(ti.ma_20)} |",
        f"| MA(50) | ${_val(ti.ma_50)} |",
        f"| MA(200) | ${_val(ti.ma_200)} |",
        f"| RSI(14) | {_val(ti.rsi_14)} |",
        f"| MACD Histogram | {_val(ti.macd_histogram)} |",
        f"| Volume Trend | {ti.volume_trend.replace('_', ' ').title()} |",
        f"| Extended? | {'Yes' if ti.is_extended else 'No'} |",
        f"| Extension above 20MA | {_val(ti.extension_pct_above_20ma)}% |",
        f"| Nearest Support | ${_val(ti.support_resistance.nearest_support)} |",
        f"| Nearest Resistance | ${_val(ti.support_resistance.nearest_resistance)} |",
        f"| RS vs SPY | {_val(ti.rs_vs_spy)} |",
        "",
        "---",
        "",
        "## Fundamental Quality",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Revenue TTM | {_mil(fu.revenue_ttm)} |",
        f"| Revenue Growth YoY | {_pct(fu.revenue_growth_yoy)} |",
        f"| EPS TTM | {_val(fu.eps_ttm)} |",
        f"| Gross Margin | {_pct(fu.gross_margin)} |",
        f"| Operating Margin | {_pct(fu.operating_margin)} |",
        f"| Net Margin | {_pct(fu.net_margin)} |",
        f"| Free Cash Flow | {_mil(fu.free_cash_flow)} |",
        f"| Cash | {_mil(fu.cash)} |",
        f"| Total Debt | {_mil(fu.total_debt)} |",
        f"| Net Debt | {_mil(fu.net_debt)} |",
        f"| D/E Ratio | {_val(fu.debt_to_equity)} |",
        f"| ROE | {_pct(fu.roe)} |",
        f"| **Fundamental Score** | **{fu.fundamental_score:.0f}/100** |",
        "",
        "---",
        "",
        "## Valuation",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Trailing P/E | {_val(va.trailing_pe)} |",
        f"| Forward P/E | {_val(va.forward_pe)} |",
        f"| PEG Ratio | {_val(va.peg_ratio)} |",
        f"| Price/Sales | {_val(va.price_to_sales)} |",
        f"| EV/EBITDA | {_val(va.ev_to_ebitda)} |",
        f"| P/FCF | {_val(va.price_to_fcf)} |",
        f"| FCF Yield | {_val(va.fcf_yield)}% |",
        f"| Peer Comparison | {'Available' if va.peer_comparison_available else 'Not Available'} |",
        f"| **Valuation Score** | **{va.valuation_score:.0f}/100** |",
        "",
        "---",
        "",
        "## Earnings & Catalysts",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Last Earnings Date | {ea.last_earnings_date or 'N/A'} |",
        f"| Next Earnings Date | {ea.next_earnings_date or 'N/A'} |",
        f"| Avg EPS Surprise | {_val(ea.avg_eps_surprise_pct)}% |",
        f"| Beat Rate (last 8Q) | {_val(ea.beat_rate)} |",
        f"| Earnings < 30 days? | {'Yes — binary event risk' if ea.within_30_days else 'No'} |",
        f"| **Earnings Score** | **{ea.earnings_score:.0f}/100** |",
        "",
        "---",
        "",
        "## News & Sentiment",
        "",
        f"Positive: {ne.positive_count} | Neutral: {ne.neutral_count} | Negative: {ne.negative_count}  ",
        f"**News Score: {ne.news_score:.0f}/100**",
        "",
    ]

    pos_items = [i for i in ne.items if i.sentiment == "positive"]
    neg_items = [i for i in ne.items if i.sentiment == "negative"]

    if pos_items:
        lines.append("### Positive News")
        for item in pos_items[:5]:
            lines.append(f"- {item.title} *(importance: {item.importance})*")
        lines.append("")

    if neg_items:
        lines.append("### Negative News")
        for item in neg_items[:5]:
            lines.append(f"- {item.title} *(importance: {item.importance})*")
        lines.append("")

    lines += ["---", ""]

    for rec in result.recommendations:
        ep = rec.entry_plan
        xp = rec.exit_plan
        rr = rec.risk_reward
        hz = rec.horizon.replace("_", "-").title()

        lines += [
            f"## {hz} Recommendation",
            "",
            f"**Decision: {rec.decision}** | Score: {rec.score:.0f}/100 | Confidence: {rec.confidence}",
            "",
            f"> {rec.summary}",
            "",
            "**Bullish factors:**",
        ]
        for f in rec.bullish_factors:
            lines.append(f"- {f}")
        lines += ["", "**Bearish factors:**"]
        for f in rec.bearish_factors:
            lines.append(f"- {f}")

        lines += [
            "",
            f"| Plan | Value |",
            f"|------|-------|",
            f"| Preferred Entry | ${_val(ep.preferred_entry)} |",
            f"| Starter Entry | ${_val(ep.starter_entry)} |",
            f"| Stop-Loss | ${_val(xp.stop_loss)} |",
            f"| Invalidation Level | ${_val(xp.invalidation_level)} |",
            f"| First Target | ${_val(xp.first_target)} |",
            f"| Second Target | ${_val(xp.second_target)} |",
            f"| Downside Risk | {_val(rr.downside_percent)}% |",
            f"| Upside Potential | {_val(rr.upside_percent)}% |",
            f"| Risk/Reward Ratio | {_val(rr.ratio)} |",
            f"| Starter Size | {rec.position_sizing.suggested_starter_pct_of_full}% of full position |",
            f"| Max Allocation | {rec.position_sizing.max_portfolio_allocation_pct}% of portfolio |",
            "",
            "---",
            "",
        ]

    if result.data_quality.warnings:
        lines += ["## Data Quality Warnings", ""]
        for w in result.data_quality.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Signal Cards section (Story 8) — only if signal_cards present
    if result.signal_cards is not None:
        sc = result.signal_cards
        lines += [
            "---",
            "",
            "## Signal Cards",
            "",
            "| Card | Score | Label |",
            "|------|-------|-------|",
        ]
        for card_name, display_name in [
            ("momentum", "Momentum"),
            ("trend", "Trend"),
            ("entry_timing", "Entry Timing"),
            ("volume_accumulation", "Volume/Accumulation"),
            ("volatility_risk", "Volatility/Risk"),
            ("relative_strength", "Relative Strength"),
            ("growth", "Growth"),
            ("valuation", "Valuation"),
            ("quality", "Quality"),
            ("ownership", "Ownership"),
            ("catalyst", "Catalyst"),
        ]:
            card = getattr(sc, card_name)
            lines.append(f"| {display_name} | {card.score:.0f}/100 | {card.label} |")
        lines.append("")

    lines += [
        "---",
        "",
        f"*{result.disclaimer}*",
    ]

    return "\n".join(lines)
