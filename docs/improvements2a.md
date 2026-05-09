Step 1 — Make “safe” code changes now

These are not aggressive strategy changes. They improve diagnosis.

1. Add more detailed label breakdowns.
2. Split confusing labels in shadow mode.
3. Add benchmark-relative reports.
4. Add archetype reports.
5. Add score bucket reports.
6. Add entry-method comparison.
7. Add drawdown/stop-hit reporting.

Do this before broader backtest because your current labels are too broad.

For example, split:

AVOID_BAD_CHART

into shadow labels:

TRUE_BAD_CHART
OVERSOLD_REBOUND_CANDIDATE
BROKEN_BUT_RECOVERING
DOWNTREND_CONTINUATION

And split:

WATCHLIST_VALUATION_TOO_RICH

into:

QUALITY_GROWTH_EXPENSIVE_BUT_WINNING
EXPENSIVE_AND_GROWTH_SLOWING
SPECULATIVE_OVERVALUED_NO_SUPPORT

Do not yet change final buy/sell behavior aggressively. Just generate these labels in the report.