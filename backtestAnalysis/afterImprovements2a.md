# Backtest Analysis: What’s Working, What’s Broken, and What to Improve

You did the right broader test. This new report is much more useful than the earlier 20-stock test because it covers **198 tickers**, **244,683 total signals**, **230,835 resolved outcomes**, and **418 test dates** from **2018-01-01 to 2025-12-29**. The model is still Phase 3: **Technical + Regime + Fundamentals**. 

## Bottom Line

```md
The algorithm is not useless.
But the recommendation labels and scoring logic are still badly calibrated.
```

Across the full 198-stock universe:

| Horizon     | Avg Return | Win Rate | Avg Excess vs SPY | Verdict                      |
| ----------- | ---------: | -------: | ----------------: | ---------------------------- |
| Short-term  |       1.3% |    56.9% |              0.1% | Barely useful                |
| Medium-term |       4.1% |    60.3% |              0.4% | Some signal, weak alpha      |
| Long-term   |      17.6% |    68.1% |              2.4% | Useful, but labels are wrong |

The biggest issue: the model makes positive absolute returns, but **barely beats SPY** in the broader universe. That means it is mostly capturing market beta, growth bias, and rebound effects, not strong standalone alpha. 

---

# 1. What Is Working

## 1. Medium-term `BUY_ON_PULLBACK` is the best real signal

This is the strongest actionable result in the report.

Medium-term `BUY_ON_PULLBACK`:

| Metric            | Result |
| ----------------- | -----: |
| Count             |  2,078 |
| Avg return        |   6.4% |
| Avg excess vs SPY |   2.4% |
| Win rate          |  61.8% |
| Profit factor     |   2.45 |

This is much better than normal `BUY_NOW` and `BUY_STARTER`. It also performs well across regimes: **+2.4% excess in BEAR_RISK_OFF**, **+4.3% in BULL_NARROW_LEADERSHIP**, **+1.5% in BULL_RISK_ON**, **+5.3% in LIQUIDITY_RALLY**, and **+3.4% in SIDEWAYS_CHOPPY**. 

### Algorithm change

Make this your main medium-term engine:

```md
Strong stock + pullback + growth support + acceptable regime = BUY_ON_PULLBACK
```

Not:

```md
Strong stock + high score = BUY_NOW
```

---

## 2. Growth signal card is actually useful

In medium-term results, the `growth` card has positive correlation with returns: **0.0637**. Its quartile behavior is good: low growth score returned **3.0%**, while high growth score returned **7.1%**. 

Short-term growth was also the only clearly positive card in that horizon, with correlation **0.0350** and Q4 return **2.2%** versus Q1 return **1.0%**. 

### Algorithm change

Promote growth acceleration:

```md
Increase weight of:
- revenue acceleration
- EPS acceleration
- gross margin expansion
- EPS/revenue surprise
- forward growth estimate trend
```

Especially for:

```md
- HYPER_GROWTH
- PROFITABLE_GROWTH
- SPECULATIVE_STORY
```

---

## 3. Hyper-growth archetype is working

For medium-term, `HYPER_GROWTH` produced:

| Metric            |      Result |
| ----------------- | ----------: |
| Signals           |       6,060 |
| Avg return        |        7.0% |
| Win rate          |       61.0% |
| Avg excess vs SPY |        3.4% |
| Best decision     | BUY_STARTER |

That is one of the best validated areas of your model. 

### Algorithm change

For hyper-growth stocks, your engine should prefer:

```md
BUY_STARTER
BUY_ON_PULLBACK
QUALITY_GROWTH_EXPENSIVE_BUT_WORKING
```

And avoid overusing:

```md
WATCHLIST_VALUATION_TOO_RICH
AVOID_BAD_BUSINESS
```

---

## 4. Long-term model has some value

Long-term overall result is good: **17.6% average return**, **68.1% win rate**, and **2.4% average excess vs SPY**. 

But the label quality is mixed. More on that below.

---

# 2. What Is Not Working

## 1. Composite score is still broken

This is the biggest problem.

Short-term score-return correlation is **-0.0827**. Medium-term score-return correlation is **-0.0609**. Long-term score-return correlation is **-0.0447**.

That means:

```md
Higher score does not mean better future return.
```

In short-term score buckets, the weakest bucket did best:

| Short-Term Score Bucket | Avg Return |
| ----------------------- | ---------: |
| 12–25 Weak              |       4.0% |
| 25–37 Below Avg         |       2.1% |
| 62–75 Good              |       0.8% |
| 75–87 Strong            |       0.6% |
| 87–100 Excellent        |      -0.2% |

This is inverted. Your score is rewarding the wrong properties for short-term return. 

### Algorithm change

Stop using composite score to decide buy/wait/avoid.

Use:

```md
archetype + regime + label-specific rules + signal cards
```

Not:

```md
score > threshold
```

---

## 2. Short-term `BUY_NOW_MOMENTUM` is weak

Short-term `BUY_NOW_MOMENTUM` had:

| Metric            | Result |
| ----------------- | -----: |
| Count             | 19,021 |
| Avg return        |   0.6% |
| Beats SPY         |  47.6% |
| Avg excess vs SPY |  -0.2% |
| Profit factor     |   1.23 |

That is not a good buy signal. It underperforms SPY on average. 

Even worse, short-term portfolio simulation for buy signals shows:

| Metric            | Model |   SPY |
| ----------------- | ----: | ----: |
| Annualized return |  9.0% | 10.0% |
| Alpha             | -1.1% |     — |

So the short-term buy engine is not worth using as-is. 

### Algorithm change

Short-term should become more selective:

```md
BUY_NOW_MOMENTUM only if:
- relative strength is positive vs SPY and sector
- price is not extended above SMA20/SMA50
- volume expansion is real
- regime is liquidity rally or confirmed risk-on
- stop distance is acceptable
- catalyst risk is not immediately negative
```

---

## 3. `AVOID_BAD_CHART` is not an avoid signal

Short-term `AVOID_BAD_CHART` is outperforming the buy labels:

| Decision          | Avg Return | Avg Excess vs SPY | Profit Factor |
| ----------------- | ---------: | ----------------: | ------------: |
| BUY_NOW_MOMENTUM  |       0.6% |             -0.2% |          1.23 |
| WAIT_FOR_PULLBACK |       0.9% |              0.0% |          1.32 |
| AVOID_BAD_CHART   |       2.4% |              0.5% |          1.87 |

That means your `AVOID_BAD_CHART` label is probably catching **oversold rebound candidates**, not truly broken charts. 

### Algorithm change

Split `AVOID_BAD_CHART` into at least four labels:

```md
1. OVERSOLD_REBOUND_CANDIDATE
2. TRUE_DOWNTREND_AVOID
3. BROKEN_SUPPORT_HIGH_RISK
4. WEAK_CHART_BUT_REVERSING
```

New logic:

```md
If price below SMA50/SMA200 but RSI is washed out and market is rebounding:
    OVERSOLD_REBOUND_CANDIDATE

If price below SMA50/SMA200, relative strength falling, no rebound volume:
    TRUE_DOWNTREND_AVOID

If support breaks on high volume:
    BROKEN_SUPPORT_HIGH_RISK
```

Do **not** treat all weak charts as avoid.

---

## 4. `AVOID_BAD_BUSINESS` is badly mislabeled

Medium-term `AVOID_BAD_BUSINESS` returned:

| Metric            | Result |
| ----------------- | -----: |
| Count             | 18,995 |
| Avg return        |   6.0% |
| Win rate          |  64.0% |
| Avg excess vs SPY |   1.1% |
| Profit factor     |   2.66 |

That is better than `BUY_NOW`, `BUY_STARTER`, and `WATCHLIST_NEEDS_CONFIRMATION`. 

This is a major bug in label logic.

### Algorithm change

Make `AVOID_BAD_BUSINESS` much stricter. It should require multiple confirming negatives:

```md
AVOID_BAD_BUSINESS only if at least 3–4 are true:
- revenue growth decelerating
- EPS growth negative or decelerating
- margins compressing
- guidance cut
- earnings miss
- debt/FCF risk rising
- relative strength below sector
- price below 200DMA
- sector also weakening
```

Otherwise use softer labels:

```md
BUSINESS_MIXED_BUT_STOCK_WORKING
CYCLICAL_WEAKNESS_BUT_REBOUNDING
VALUATION_RISK_NOT_BUSINESS_AVOID
```

---

## 5. Long-term valuation label is still wrong

Long-term `WATCHLIST_VALUATION_TOO_RICH` is the best major long-term label:

| Label                        | Avg Return | Avg Excess vs SPY | Profit Factor |
| ---------------------------- | ---------: | ----------------: | ------------: |
| BUY_NOW_LONG_TERM            |      19.4% |              6.4% |          3.20 |
| ACCUMULATE_ON_WEAKNESS       |      13.1% |             -0.8% |          3.05 |
| WATCHLIST_VALUATION_TOO_RICH |      20.3% |              4.2% |          5.02 |
| AVOID_LONG_TERM              |      14.2% |             -5.9% |           3.x |

`WATCHLIST_VALUATION_TOO_RICH` beating `ACCUMULATE_ON_WEAKNESS` means the model still treats expensive winners too cautiously. 

### Algorithm change

Replace `WATCHLIST_VALUATION_TOO_RICH` with more precise labels:

```md
QUALITY_GROWTH_EXPENSIVE_BUT_WORKING
QUALITY_GROWTH_EXTENDED_WAIT_FOR_PULLBACK
EXPENSIVE_AND_GROWTH_SLOWING
SPECULATIVE_OVERVALUED_NO_SUPPORT
```

For hyper-growth and profitable-growth stocks:

```md
High valuation + high growth + strong relative strength
= BUY_STARTER or ACCUMULATE_ON_PULLBACK

High valuation + slowing growth + weak chart
= AVOID_LONG_TERM
```

---

## 6. Volatility/risk card is being used incorrectly

In medium-term, `volatility_risk` has strong negative correlation with return: **-0.1865**. Q1 low volatility/risk score returned **7.6%**, while Q4 high score returned only **0.7%**. 

In short-term, the same issue exists: `volatility_risk` correlation is **-0.1332**, and high-score quartile returned about **0%**, while low-score quartile returned **2.8%**. 

This means either:

```md
1. The score direction is inverted, or
2. The market rewards high-volatility rebound/growth stocks, or
3. You are using volatility as a return predictor when it should be a risk/position-sizing tool.
```

### Algorithm change

Do not use volatility to reduce signal quality directly.

Use it for:

```md
- position size
- stop width
- expected drawdown
- whether to buy starter instead of full position
```

Example:

```md
High volatility + strong growth + strong setup
= BUY_STARTER, not AVOID

High volatility + weak growth + weak chart
= AVOID_HIGH_RISK
```

---

# 3. Most Important Algorithm Improvements

## Improvement 1: Replace score-based engine with rule-based decision matrix

Current bad pattern:

```md
score high = buy
score low = avoid
```

New pattern:

```md
decision = archetype + regime + growth + trend + entry + valuation-risk + volatility-risk
```

Example:

```md
HYPER_GROWTH
+ strong growth score
+ high valuation risk
+ strong relative strength
+ extended entry
= BUY_STARTER_OR_WAIT_FOR_PULLBACK
```

Not:

```md
valuation expensive => WATCHLIST or AVOID
```

---

## Improvement 2: Make medium-term the primary usable horizon

Based on the report, your short-term model is weak and your long-term model is label-confused. Medium-term has the most practical signal.

Prioritize:

```md
1–6 month swing/investment decision engine
```

Core rule:

```md
BUY_ON_PULLBACK if:
- growth score strong
- price above or near SMA50/SMA200
- pullback is controlled
- relative strength is not collapsing
- regime is not hostile
```

This should become your highest-confidence recommendation.

---

## Improvement 3: Create two separate engines: continuation vs rebound

Your backtest shows low scores and bad-chart labels often perform well. That means you are mixing two strategies:

```md
1. Momentum continuation
2. Mean-reversion rebound
```

Separate them.

### Continuation engine

```md
Good for:
- BUY_NOW_MOMENTUM
- BUY_STARTER
- BUY_ON_BREAKOUT

Needs:
- positive relative strength
- volume confirmation
- trend alignment
- not too extended
```

### Rebound engine

```md
Good for:
- OVERSOLD_REBOUND_CANDIDATE
- BUY_REVERSAL_STARTER
- WATCHLIST_REVERSAL

Needs:
- RSI washed out
- price stretched below SMA20/SMA50
- selling volume fading
- market regime stabilizing
- support/reversal candle
```

Right now, your model accidentally finds rebounds but labels them as avoid.

---

## Improvement 4: Rebuild labels

Use these labels instead:

```md
Short-term:
- BUY_NOW_CONTINUATION
- BUY_STARTER_EXTENDED
- WAIT_FOR_PULLBACK
- OVERSOLD_REBOUND_CANDIDATE
- TRUE_DOWNTREND_AVOID
- BROKEN_SUPPORT_AVOID

Medium-term:
- BUY_ON_PULLBACK
- BUY_STARTER_GROWTH_LEADER
- WATCHLIST_NEEDS_EARNINGS_CONFIRMATION
- BUSINESS_MIXED_BUT_STOCK_WORKING
- TRUE_BAD_BUSINESS_AVOID

Long-term:
- QUALITY_GROWTH_COMPOUNDER
- QUALITY_GROWTH_EXPENSIVE_BUT_WORKING
- ACCUMULATE_ON_WEAKNESS
- EXPENSIVE_AND_GROWTH_SLOWING
- AVOID_LONG_TERM_BROKEN_THESIS
```

---

## Improvement 5: Change valuation from decision blocker to risk modifier

Valuation should do this:

```md
- reduce position size
- require pullback
- increase required growth quality
- increase required confidence
```

Valuation should not do this:

```md
- automatically downgrade to watchlist
- automatically issue avoid
- override strong growth and strong trend
```

Especially for:

```md
- NVDA-type names
- AVGO-type names
- PLTR-type names
- CRWD-type names
- SHOP-type names
- TSLA-type names
```

---

## Improvement 6: Add sector ETF benchmark, not just SPY

The report uses SPY excess return heavily, which is good, but not enough.

A semiconductor stock should be compared against:

```md
SMH or SOXX
```

A software stock should be compared against:

```md
IGV
```

A financial stock:

```md
XLF
```

Energy:

```md
XLE
```

Healthcare:

```md
XLV
```

Your previous testing strategy explicitly called out benchmarking against SPY, QQQ, and sector ETF because absolute return alone can be misleading. 

---

# 4. Priority Code Changes

## Priority 1: Fix labels before adding indicators

Do this first:

```md
- split AVOID_BAD_CHART
- split AVOID_BAD_BUSINESS
- split WATCHLIST_VALUATION_TOO_RICH
- add OVERSOLD_REBOUND_CANDIDATE
- add QUALITY_GROWTH_EXPENSIVE_BUT_WORKING
```

## Priority 2: Stop using composite score as final decision

Keep scores, but use them as signal cards only.

```md
score cards = evidence
decision label = rules
```

## Priority 3: Promote `BUY_ON_PULLBACK`

Medium-term `BUY_ON_PULLBACK` should become your highest-confidence setup.

## Priority 4: Add separate strategy type

Every signal should include:

```json
{
  "strategyType": "CONTINUATION | PULLBACK | REBOUND | COMPOUNDER | AVOID"
}
```

This will prevent mixing rebound trades with momentum trades.

## Priority 5: Make `AVOID_BAD_BUSINESS` stricter

Current label is wrong because it is catching winners.

Require several business deterioration signals before issuing it.

---

# Final Verdict

```md
The broader backtest says:
Your tool has signal, but the current recommendation labels are misleading.
```

Most important finding:

```md
The algorithm is better at finding growth/rebound opportunities than it realizes.
```

Best next action:

```md
Do not add more indicators yet.
Fix decision labels and scoring interpretation first.
```

I would make the next version around these three engines:

```md
1. Medium-term BUY_ON_PULLBACK engine
2. Growth-leader BUY_STARTER engine
3. Oversold-rebound candidate engine
```

And I would demote these:

```md
1. Short-term BUY_NOW_MOMENTUM
2. Generic AVOID_BAD_CHART
3. Generic AVOID_BAD_BUSINESS
4. WATCHLIST_VALUATION_TOO_RICH
```

The model is not failing because it lacks data. It is failing because it is **misinterpreting the data it already has**.
