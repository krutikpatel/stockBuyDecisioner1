# Backtesting Strategy to Test the Stock Buy Decision Plan

Your backtest should test the tool as a **decision engine**, not just a score predictor.

The expanded plan already separates short-term, medium-term, and long-term logic, with short-term focused on momentum, relative volume, entry quality, relative strength, risk/reward, and catalysts; medium-term focused on trend, earnings/sales acceleration, relative strength, volume/institutional accumulation, valuation, margins, and catalysts; and long-term focused on durability, profitability, balance sheet, valuation, trend, sector/theme, ownership, and drawdown risk. 

So the backtest must test each horizon separately.

---

# 1. Core Backtesting Goal

Do **not** ask only:

```md
Did BUY signals go up?
```

Ask:

```md
Did BUY_NOW outperform WAIT?
Did BUY_STARTER outperform WATCHLIST?
Did AVOID_BAD_CHART reduce drawdowns?
Did WAIT_FOR_PULLBACK improve entry price?
Did the model outperform SPY, QQQ, and sector ETF?
Did the model work across bull, bear, and sideways regimes?
```

Your new backtest should measure:

```md
1. Absolute return
2. Benchmark-relative return
3. Max drawdown after signal
4. Hit rate
5. Average win / average loss
6. Risk-adjusted return
7. Signal frequency
8. False positive rate
9. False negative rate
10. Regime-specific performance
```

---

# 2. Backtest the Three Horizons Separately

## A. Short-Term Backtest

Target horizon:

```md
5 trading days
10 trading days
20 trading days
30 trading days
```

This tests:

```md
- Momentum
- Relative volume
- Entry quality
- Breakout/pullback setup
- RSI/extension
- ATR-based risk
- Relative strength
- News/catalyst proximity if available
```

Short-term labels:

```md
BUY_NOW_MOMENTUM
BUY_STARTER_STRONG_BUT_EXTENDED
WAIT_FOR_PULLBACK
BUY_ON_BREAKOUT_CONFIRMATION
AVOID_BAD_CHART
AVOID_LOW_CONFIDENCE
```

Primary question:

```md
Does the short-term signal predict favorable 1–4 week risk/reward?
```

Important metrics:

```md
- 5D, 10D, 20D forward return
- 5D, 10D, 20D return vs SPY/QQQ/sector ETF
- Max adverse excursion within 20 trading days
- Max favorable excursion within 20 trading days
- Probability of hitting stop before target
- Probability of hitting target before stop
- Gap-down risk
- Average return after BUY_NOW_MOMENTUM
- Average return after WAIT_FOR_PULLBACK
```

---

## B. Medium-Term Backtest

Target horizon:

```md
1 month
3 months
6 months
```

This tests:

```md
- Trend strength
- Earnings momentum
- Sales/EPS acceleration
- Sector strength
- Relative strength
- Institutional accumulation
- Growth-adjusted valuation
```

Medium-term labels:

```md
BUY_NOW
BUY_STARTER
BUY_ON_PULLBACK
WATCHLIST_NEEDS_CONFIRMATION
AVOID_BAD_BUSINESS
AVOID_BAD_CHART
```

Primary question:

```md
Does the model identify stocks that outperform over 1–6 months?
```

Important metrics:

```md
- 21D, 63D, 126D forward return
- Excess return vs SPY
- Excess return vs QQQ
- Excess return vs sector ETF
- Max drawdown during holding period
- Return/drawdown ratio
- Win rate vs benchmark
- Earnings-event performance
- Post-earnings drift
```

---

## C. Long-Term Backtest

Target horizon:

```md
6 months
12 months
24 months
```

This tests:

```md
- Business quality
- Revenue/EPS durability
- Margins
- ROIC/ROE/ROA
- Balance sheet
- Long-term trend
- Growth-adjusted valuation
- Ownership/sponsorship
```

Long-term labels:

```md
BUY_NOW_LONG_TERM
ACCUMULATE_ON_WEAKNESS
WATCHLIST_VALUATION_TOO_RICH
AVOID_LONG_TERM
AVOID_BAD_BUSINESS
```

Primary question:

```md
Does the model find long-term outperformers, not just stocks that go up in a bull market?
```

Important metrics:

```md
- 126D, 252D, 504D forward return
- Return vs SPY
- Return vs QQQ
- Return vs sector ETF
- Max drawdown
- Sharpe ratio
- Sortino ratio
- Calmar ratio
- Alpha over benchmark
- Outperformance hit rate
```

---

# 3. Use Benchmark-Relative Returns

This is critical.

Your previous 52-week win rate was inflated by the 2024–2025 AI/tech bull market. So every signal should be judged against:

```md
- SPY for broad market
- QQQ for growth/tech-heavy names
- Sector ETF for sector-specific comparison
```

Example:

```md
Stock return after signal: +18%
QQQ return same period: +22%

Result:
Absolute return positive.
Benchmark-relative return negative.
Signal did not create alpha.
```

For semiconductor stocks, compare against:

```md
SOXX or SMH
```

For software:

```md
IGV or sector proxy
```

For financials:

```md
XLF
```

For healthcare:

```md
XLV
```

For energy:

```md
XLE
```

---

# 4. Backtest Signal Labels, Not Just Scores

Do not only run:

```md
score vs future return correlation
```

That is too crude.

Instead test each final recommendation label:

```md
BUY_NOW_MOMENTUM
BUY_STARTER_STRONG_BUT_EXTENDED
WAIT_FOR_PULLBACK
BUY_ON_PULLBACK
BUY_ON_BREAKOUT_CONFIRMATION
WATCHLIST_NEEDS_CONFIRMATION
WATCHLIST_VALUATION_TOO_RICH
AVOID_BAD_CHART
AVOID_BAD_BUSINESS
AVOID_LOW_CONFIDENCE
```

For each label, calculate:

```md
Signal count:
Average forward return:
Median forward return:
Win rate:
Benchmark-relative win rate:
Average max drawdown:
Average max favorable move:
Profit factor:
Worst 5 signals:
Best 5 signals:
Regime where it works:
Regime where it fails:
```

This will tell you whether the labels are meaningful.

---

# 5. Create Daily or Weekly Historical Snapshots

For each ticker and date, create a snapshot:

```json
{
  "ticker": "MU",
  "asOfDate": "2024-03-15",
  "price": 93.25,
  "features": {
    "rsi14": 62,
    "relativeVolume": 1.7,
    "priceVsSma20": 4.2,
    "priceVsSma50": 8.5,
    "priceVsSma200": 31.4,
    "relativeStrengthVsQQQ": 6.1,
    "atrPercent": 3.4,
    "salesGrowthQoQ": 22.5,
    "epsGrowthYoY": 35.2
  },
  "signalCards": {
    "momentum": "VERY_BULLISH",
    "entryTiming": "BULLISH",
    "valuation": "RISKY",
    "growth": "BULLISH"
  },
  "recommendations": {
    "shortTerm": "BUY_NOW_MOMENTUM",
    "mediumTerm": "BUY_STARTER",
    "longTerm": "ACCUMULATE_ON_WEAKNESS"
  }
}
```

Then attach forward outcomes:

```json
{
  "return5D": 2.1,
  "return20D": 8.4,
  "return63D": 18.7,
  "return126D": 31.2,
  "maxDrawdown20D": -4.6,
  "maxDrawdown63D": -9.8,
  "excessReturnVsQQQ63D": 7.4,
  "hitStopBeforeTarget": false
}
```

---

# 6. Avoid Look-Ahead Bias

This is one of the most important parts.

At each historical date, the model can only use data available **before or on that date**.

Rules:

```md
Use only trailing OHLCV data.
Use only fundamentals already reported by that date.
Use only earnings data known by that date.
Use only news published before that date.
Do not use future revised estimates unless you have point-in-time estimate history.
Do not use today’s Finviz values for historical dates.
```

Common mistake:

```md
Using today’s P/E, EPS growth, analyst rating, or target price for a 2024 signal.
```

That makes the backtest invalid.

For the first version, if point-in-time fundamentals are hard, do this:

```md
Phase 1:
Backtest technical-only and price/volume signals.

Phase 2:
Add quarterly fundamentals using reporting-date lag.

Phase 3:
Add point-in-time analyst/news/estimate data.
```

---

# 7. Test Regime Awareness

Classify every backtest date into a market regime.

Suggested regimes:

```md
BULL_RISK_ON
BULL_NARROW_LEADERSHIP
SIDEWAYS_CHOPPY
BEAR_RISK_OFF
SECTOR_ROTATION
LIQUIDITY_RALLY
```

Simple regime rules:

```md
BULL_RISK_ON:
- SPY above 200DMA
- QQQ above 200DMA
- VIX stable or falling
- Market breadth improving

BEAR_RISK_OFF:
- SPY below 200DMA
- QQQ below 200DMA
- VIX rising
- Breadth weak

SIDEWAYS_CHOPPY:
- SPY/QQQ near 50DMA or 200DMA
- Mixed breadth
- Frequent failed breakouts
```

Then report:

```md
BUY_NOW_MOMENTUM performance in bull markets:
BUY_NOW_MOMENTUM performance in bear markets:
WAIT_FOR_PULLBACK performance in choppy markets:
AVOID_BAD_CHART performance in risk-off markets:
```

This matters because the same signal can work in one regime and fail in another.

---

# 8. Test by Stock Archetype

Classify each stock before testing.

Archetypes:

```md
HYPER_GROWTH
PROFITABLE_GROWTH
CYCLICAL_GROWTH
MATURE_VALUE
TURNAROUND
SPECULATIVE_STORY
DEFENSIVE
COMMODITY_CYCLICAL
```

Then evaluate:

```md
Does valuation work better for mature value stocks?
Does momentum work better for hyper-growth stocks?
Does earnings acceleration work better for cyclical growth stocks?
Does AVOID_BAD_BUSINESS work across all archetypes?
```

Example output:

```md
BUY_STARTER on HYPER_GROWTH stocks:
- 63D average excess return: +6.8%
- Max drawdown: -11.2%
- Win rate vs QQQ: 61%

BUY_STARTER on MATURE_VALUE stocks:
- 63D average excess return: +1.2%
- Max drawdown: -5.4%
- Win rate vs SPY: 54%
```

---

# 9. Test Entry Timing Separately

You need to know whether the tool improves entry price.

For each BUY or WATCHLIST signal, simulate multiple entry methods:

## Entry Method A: Buy Next Open

```md
Enter next trading day open after signal.
```

## Entry Method B: Buy Next Close

```md
Enter next trading day close after signal.
```

## Entry Method C: Buy Pullback to SMA20

```md
Enter only if price touches or comes within 1–2% of SMA20 within next 20 trading days.
```

## Entry Method D: Buy Pullback to SMA50

```md
Enter only if price touches or comes within 1–3% of SMA50 within next 40 trading days.
```

## Entry Method E: Buy Breakout Confirmation

```md
Enter only if price closes above resistance with volume > 1.5x average volume.
```

This is how you validate labels like:

```md
WAIT_FOR_PULLBACK
BUY_ON_BREAKOUT_CONFIRMATION
BUY_STARTER_STRONG_BUT_EXTENDED
```

You may discover:

```md
BUY_NOW works best only when not extended.
WAIT_FOR_PULLBACK improves drawdown but misses some winners.
BUY_STARTER works better than full entry for volatile growth stocks.
```

---

# 10. Test Exit Rules, Not Just Entry Signals

For every signal, simulate exits.

## Exit Strategy 1: Fixed Horizon

```md
Short-term: exit after 20 trading days
Medium-term: exit after 63 or 126 trading days
Long-term: exit after 252 trading days
```

## Exit Strategy 2: Stop + Target

```md
Stop-loss:
- 1.5x ATR below entry for short-term
- 2.5x ATR below entry for medium-term
- Below 200DMA or thesis break for long-term

Target:
- 2:1 or 3:1 reward/risk
```

## Exit Strategy 3: Trailing Stop

```md
Short-term:
- Exit on close below SMA20 or 1.5x ATR trailing stop

Medium-term:
- Exit on close below SMA50 or 2.5x ATR trailing stop

Long-term:
- Exit on close below SMA200 only if fundamentals also weaken
```

## Exit Strategy 4: Signal-Based Exit

```md
Exit when recommendation changes from:
BUY_NOW → AVOID_BAD_CHART
BUY_STARTER → AVOID_BAD_BUSINESS
ACCUMULATE → WATCHLIST_VALUATION_TOO_RICH
```

You should compare all four.

---

# 11. Include Transaction Costs and Slippage

Use realistic assumptions.

Suggested defaults:

```md
Commission: 0
Slippage for large/liquid stocks: 0.05% to 0.10%
Slippage for smaller/volatile stocks: 0.20% to 0.50%
Entry delay: next open or next close
```

Also test:

```md
No slippage
Normal slippage
Stress slippage
```

If a strategy only works with zero slippage, it is probably too fragile.

---

# 12. Use Walk-Forward Testing

Do not tune on the full dataset and then claim success.

Use walk-forward testing.

Example:

```md
Train/calibrate:
2018–2021

Validate:
2022

Test:
2023

Walk forward:
Train 2019–2022 → Test 2023
Train 2020–2023 → Test 2024
Train 2021–2024 → Test 2025
```

Since your previous test covered mostly 2024–2025, add older periods if possible:

```md
2018 bull/choppy
2020 crash/recovery
2021 growth mania
2022 bear/rate shock
2023 recovery
2024–2025 AI bull market
```

That will reveal whether the strategy is robust or just optimized for AI bull markets.

---

# 13. Run Ablation Tests

Ablation means removing one component at a time.

Test these versions:

```md
Model A: Technical only
Model B: Technical + volume
Model C: Technical + volume + relative strength
Model D: Technical + volume + relative strength + earnings
Model E: Full model except valuation
Model F: Full model with valuation
Model G: Full model without news/options
Model H: Full model with regime overlay
Model I: Full model without regime overlay
```

You want to know:

```md
Which signal actually adds value?
Which signal reduces performance?
Does valuation help or hurt by archetype?
Does news/options improve short-term signals?
Does regime overlay reduce false positives?
```

This is where you will discover whether extra indicators help or just create noise.

---

# 14. Test Score Thresholds

Do not assume thresholds like 70 or 80 are correct.

Bucket scores:

```md
0–20
20–40
40–50
50–60
60–70
70–80
80–90
90–100
```

For each bucket, measure:

```md
Forward return
Excess return
Max drawdown
Win rate
Signal count
```

Good model behavior looks like:

```md
Higher score bucket → better forward excess return
Higher score bucket → lower drawdown
Higher score bucket → better hit rate
```

Bad model behavior looks like:

```md
70–80 performs same as 50–60
90–100 has too few signals
High scores work only in bull markets
Low scores still perform well in bull markets
```

---

# 15. Backtest Signal Cards

Your new plan says not to collapse everything into one score. That means backtest each signal card.

Signal cards:

```md
Momentum
Trend
Entry timing
Volume/accumulation
Volatility/risk
Relative strength
Growth
Valuation
Quality
Ownership
Catalyst
```

For each card, test:

```md
Card score vs future return
Card score vs future excess return
Card score vs future drawdown
Card score vs hit rate
```

Example insights you want:

```md
Momentum predicts 20D return.
Growth predicts 63D and 126D return.
Valuation predicts drawdown risk, not short-term return.
Quality predicts 252D risk-adjusted return.
Entry timing predicts max adverse excursion.
Volume predicts breakout follow-through.
```

This helps you avoid forcing every signal to predict the same thing.

---

# 16. Evaluate “Wait” Signals Properly

A `WAIT_FOR_PULLBACK` signal should not be judged as a failure just because the stock went up.

It should be judged by:

```md
Did a better entry appear within 5, 10, 20, or 40 trading days?
Did waiting reduce max drawdown?
Did waiting improve risk/reward?
How often did waiting miss a big move?
```

For every WAIT signal, calculate:

```md
Future max pullback from signal price
Future max upside without pullback
Whether SMA20/SMA50 entry triggered
Return if bought immediately
Return if waited for planned entry
Opportunity cost of waiting
```

This is extremely important.

A good WAIT signal may look like:

```md
Immediate buy return: +8%
Wait entry return: +6%
But max drawdown improved from -12% to -4%
```

Depending on your risk style, the wait signal may still be valuable.

---

# 17. Evaluate “Avoid” Signals Properly

Do not expect `AVOID` to always mean negative return.

Split avoid labels:

```md
AVOID_BAD_CHART
AVOID_BAD_BUSINESS
AVOID_BAD_RISK_REWARD
AVOID_LOW_CONFIDENCE
```

Measure each differently.

## AVOID_BAD_CHART

Should predict:

```md
Poor short/medium-term momentum
Higher drawdown
Weak relative return
```

## AVOID_BAD_BUSINESS

Should predict:

```md
Weak 6–12 month performance
Weak relative return
Fundamental deterioration
```

## AVOID_BAD_RISK_REWARD

Should predict:

```md
Poor reward per unit of drawdown
High chance of stop hit
Weak entry quality
```

## AVOID_LOW_CONFIDENCE

Should not be judged as bearish.

It means:

```md
Model should not make strong call because data is incomplete.
```

---

# 18. Recommended Backtest Reports

Generate these reports automatically.

## Report 1: Signal Performance Summary

```md
Signal label
Count
Avg return 20D
Avg return 63D
Avg return 126D
Avg excess return
Win rate
Benchmark win rate
Avg max drawdown
Worst drawdown
```

## Report 2: Regime Performance

```md
Signal
Bull regime performance
Bear regime performance
Choppy regime performance
Sector rotation performance
```

## Report 3: Archetype Performance

```md
Signal
Hyper-growth
Profitable growth
Cyclical growth
Mature value
Speculative
Defensive
```

## Report 4: Feature Importance

```md
Feature
Correlation with 20D excess return
Correlation with 63D excess return
Correlation with max drawdown
Information coefficient
Stability by year
```

## Report 5: Entry Method Comparison

```md
Signal
Buy next open
Buy next close
Buy pullback to SMA20
Buy pullback to SMA50
Buy breakout confirmation
```

## Report 6: Score Bucket Test

```md
Score bucket
Signal count
Forward return
Excess return
Drawdown
Win rate
```

---

# 19. Minimum Viable Backtest

Start simple.

## MVP Backtest v1

Use:

```md
Universe:
- 50–200 liquid US stocks
- Include tech, semis, software, financials, healthcare, energy, industrials

Dates:
- At least 2018–2025 if available

Frequency:
- Weekly snapshots every Friday close

Signals:
- Short-term recommendation
- Medium-term recommendation
- Long-term recommendation

Forward returns:
- 5D
- 20D
- 63D
- 126D
- 252D

Benchmarks:
- SPY
- QQQ
- Sector ETF

Metrics:
- Absolute return
- Excess return
- Max drawdown
- Hit rate
- Signal count
```

Why weekly snapshots?

```md
Daily snapshots create many overlapping signals and noisy duplicate trades.
Weekly snapshots are cleaner for first validation.
```

After MVP works, move to daily.

---

# 20. Best Practical Implementation Sequence

## Phase 1: Technical-Only Backtest

Use:

```md
Price
Volume
RSI
SMA20/50/200
ATR
Relative volume
1W/1M/3M/6M performance
Relative strength vs SPY/QQQ/sector
Distance from 52-week high
Support/resistance
```

Goal:

```md
Validate short-term and medium-term technical engine.
```

## Phase 2: Add Regime and Benchmarks

Add:

```md
SPY trend
QQQ trend
Sector ETF trend
VIX trend
Benchmark-relative return
```

Goal:

```md
Know when the model works.
```

## Phase 3: Add Fundamentals

Add:

```md
Sales growth
EPS growth
Margins
ROE/ROIC
Debt/equity
Forward P/E
PEG
EV/Sales
EV/EBITDA
```

Goal:

```md
Validate medium-term and long-term engine.
```

## Phase 4: Add News/Earnings

Add:

```md
Earnings dates
EPS surprise
Revenue surprise
Guidance direction
Major news flag
Analyst upgrade/downgrade flag
```

Goal:

```md
Improve catalyst and confidence scoring.
```

## Phase 5: Add Options Flow

Add:

```md
IV rank
Put/call ratio
Options volume
Expected move
Skew
Open interest concentration
```

Goal:

```md
Improve short-term prediction.
```

---

# 21. What Success Should Look Like

The model is improving if:

```md
1. BUY_NOW_MOMENTUM beats SPY/QQQ/sector over 5D–20D.
2. BUY_STARTER has lower drawdown than BUY_NOW but still positive excess return.
3. WAIT_FOR_PULLBACK improves entry risk/reward, even if it misses some winners.
4. AVOID_BAD_CHART has worse forward return or higher drawdown than BUY labels.
5. AVOID_BAD_BUSINESS underperforms over 3–12 months.
6. High score buckets outperform low score buckets.
7. Results hold outside 2024–2025.
8. Model works by archetype, not just on AI winners.
9. Regime overlay reduces false positives in bear/choppy periods.
10. Valuation helps long-term risk control but does not destroy short-term momentum trades.
```

---

# 22. Coding Agent Prompt

```md
# Task: Build Backtesting Framework for Stock Decision Tool

Build a backtesting framework to validate a stock buy decision engine.

The engine produces horizon-specific recommendations:
- short-term
- medium-term
- long-term

It also produces signal labels:
- BUY_NOW_MOMENTUM
- BUY_STARTER_STRONG_BUT_EXTENDED
- WAIT_FOR_PULLBACK
- BUY_ON_PULLBACK
- BUY_ON_BREAKOUT_CONFIRMATION
- WATCHLIST_NEEDS_CONFIRMATION
- WATCHLIST_VALUATION_TOO_RICH
- AVOID_BAD_CHART
- AVOID_BAD_BUSINESS
- AVOID_BAD_RISK_REWARD
- AVOID_LOW_CONFIDENCE

Backtest requirements:

1. Create historical snapshots for each ticker and date.
2. Use only point-in-time data available as of that date.
3. Generate model signals from each historical snapshot.
4. Calculate forward returns:
   - 5D
   - 10D
   - 20D
   - 63D
   - 126D
   - 252D
5. Calculate benchmark-relative returns vs:
   - SPY
   - QQQ
   - sector ETF
6. Calculate risk metrics:
   - max drawdown
   - max adverse excursion
   - max favorable excursion
   - Sharpe
   - Sortino
   - Calmar
   - hit rate
   - profit factor
7. Test performance by:
   - signal label
   - score bucket
   - market regime
   - stock archetype
   - sector
   - year
   - entry method
   - exit method
8. Entry methods to simulate:
   - next open
   - next close
   - pullback to SMA20
   - pullback to SMA50
   - breakout confirmation
9. Exit methods to simulate:
   - fixed holding period
   - ATR stop + target
   - trailing stop
   - signal-based exit
10. Generate reports:
   - signal performance summary
   - regime performance
   - archetype performance
   - benchmark-relative performance
   - entry method comparison
   - score bucket performance
   - feature importance report

Important:
- Avoid look-ahead bias.
- Do not use current fundamentals for historical dates.
- Missing data should reduce confidence.
- Do not optimize only for 2024–2025.
- Use walk-forward validation.
```

---

# 23. My Recommended First Backtest

Start with this exact setup:

```md
Universe:
- 100 liquid US stocks
- Include AI/semis/software plus non-tech sectors

Period:
- 2018–2025

Frequency:
- Weekly Friday close snapshots

Initial model:
- Technical + volume + relative strength + regime only

Signals:
- BUY_NOW_MOMENTUM
- BUY_STARTER_STRONG_BUT_EXTENDED
- WAIT_FOR_PULLBACK
- AVOID_BAD_CHART

Forward tests:
- 5D
- 20D
- 63D

Benchmarks:
- SPY
- QQQ
- sector ETF

Primary success metric:
- 20D and 63D excess return vs benchmark
- Max drawdown after signal
```

Then add fundamentals and long-term logic only after the technical/regime engine proves it has signal.

The biggest mistake would be testing everything at once. Start with the technical engine, prove it works, then add layers one by one.
