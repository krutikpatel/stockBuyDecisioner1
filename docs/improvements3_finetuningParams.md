Saved `improvements2.md` as the current algorithm reference. Based on that file, your current technical logic uses these key short-term rules: `BUY_NOW_MOMENTUM` requires price above SMA20/SMA50/SMA200, relative volume `> 1.5`, positive 1-week and 1-month performance, RSI between `50–70`, price no more than `10%` above SMA20, and breakout/continuation confirmation. 

# Main Diagnosis

Your broader backtest says the current values are too broad and not profit-selective enough. Short-term `BUY_NOW_MOMENTUM` had only **0.6% avg return**, **-0.2% excess vs SPY**, and **1.23 profit factor**, while `AVOID_BAD_CHART` returned **2.4% avg return**, **0.5% excess vs SPY**, and **1.87 profit factor**. That means your “bad chart” rules are accidentally catching rebound winners, and your “momentum buy now” rules are not selective enough. 

Your best technical-style signal is medium-term `BUY_ON_PULLBACK`, with **6.4% avg return**, **2.4% excess vs SPY**, and **2.45 profit factor**. So the goal should be:

```md
Less immediate chasing.
More controlled pullback entries.
Separate momentum continuation from oversold rebound.
```

---

# 1. Tune RSI Rules

## Current

```md
BUY_NOW_MOMENTUM:
RSI between 50 and 70
```

This range is too wide. RSI 50 and RSI 69 are very different setups.

## Recommended Tuning

### For continuation buys

Test:

```md
RSI 55–68
RSI 58–70
RSI 60–72 only in LIQUIDITY_RALLY
```

My preferred first version:

```md
BUY_NOW_CONTINUATION:
RSI 55–68
RSI slope positive
RSI not lower than previous week
```

### For extended starter buys

```md
BUY_STARTER_EXTENDED:
RSI 68–76
only if growth score strong
only if relative strength vs sector is positive
position size reduced
```

### For rebound candidates

Add a new label:

```md
OVERSOLD_REBOUND_CANDIDATE:
RSI 25–42
RSI slope turning up
price below SMA20 or SMA50
selling volume fading
market regime stabilizing
```

This is important because your `AVOID_BAD_CHART` results suggest many “bad chart” stocks were actually rebound opportunities.

---

# 2. Tune Price Distance From SMA20

## Current

```md
BUY_NOW_MOMENTUM:
price not more than 10% above SMA20
```

This is probably too loose for short-term buy-now entries.

## Recommended Tuning

Test these buckets:

```md
-5% to 0% below SMA20
0% to +3% above SMA20
+3% to +6% above SMA20
+6% to +10% above SMA20
+10% to +15% above SMA20
> +15% above SMA20
```

Suggested rule:

```md
BUY_NOW_CONTINUATION:
price between 0% and +5% above SMA20

BUY_STARTER_EXTENDED:
price between +5% and +10% above SMA20

WAIT_FOR_PULLBACK:
price > +10% above SMA20
```

For volatile hyper-growth names, allow slightly wider:

```md
HYPER_GROWTH:
BUY_NOW allowed up to +7% above SMA20

MATURE_VALUE:
BUY_NOW allowed only up to +4% above SMA20
```

---

# 3. Tune Price Distance From SMA50

Your current logic requires price above SMA50, but does not clearly control how extended price is from SMA50.

Add this.

## Recommended Buckets

```md
below SMA50
0% to +5% above SMA50
+5% to +10% above SMA50
+10% to +20% above SMA50
> +20% above SMA50
```

Suggested rules:

```md
Medium-term BUY_ON_PULLBACK:
price within -3% to +5% of SMA50
```

```md
BUY_STARTER:
price +5% to +12% above SMA50
```

```md
WAIT_FOR_PULLBACK:
price > +12% above SMA50
```

```md
AVOID_CHASING:
price > +20% above SMA50 unless liquidity rally + hyper-growth
```

Given your backtest, I would make **SMA50 pullback** the central medium-term trigger.

---

# 4. Tune Relative Volume

## Current

```md
Relative volume > 1.5
```

This is not enough by itself. High relative volume can mean buying pressure or panic selling.

## Recommended Tuning

Split by context.

### Breakout continuation

```md
Relative volume > 1.8
close near top 30% of daily range
price up on the day
breaks 20D or 50D high
```

### Pullback buy

```md
Relative volume < 1.0 on pullback
or
volume dry-up ratio < 0.8
```

### Reversal/rebound

```md
Relative volume > 1.5
but only if price closes above open
and RSI is turning up
```

So do not use relative volume as one generic bullish feature.

Use it like this:

```md
High relative volume + breakout = bullish
Low relative volume + pullback = bullish
High relative volume + selloff = bearish unless reversal confirmed
```

---

# 5. Tune 1-Week and 1-Month Performance

## Current

```md
1-week performance positive
1-month performance positive
```

This is too simple. A stock up 0.2% and a stock up 18% both pass.

## Recommended Buckets

For short-term:

```md
1W return:
< -5%
-5% to 0%
0% to +3%
+3% to +8%
> +8%
```

For 1M return:

```md
1M return:
< -10%
-10% to 0%
0% to +8%
+8% to +20%
> +20%
```

Suggested continuation rule:

```md
BUY_NOW_CONTINUATION:
1W return between 0% and +6%
1M return between +3% and +15%
```

Avoid chasing:

```md
If 1W return > +10%
or 1M return > +25%:
    WAIT_FOR_PULLBACK unless breakout + earnings catalyst
```

Rebound rule:

```md
OVERSOLD_REBOUND_CANDIDATE:
1M return < -10%
but 3D or 5D return improving
RSI turning up
volume selling pressure fading
```

---

# 6. Tune 52-Week High Distance

Current logic says “price near 52-week high” for `WAIT_FOR_PULLBACK`, but this should be quantified.

## Suggested Buckets

```md
Within 0–3% of 52W high
3–7% below 52W high
7–15% below 52W high
15–30% below 52W high
>30% below 52W high
```

Suggested rules:

```md
Breakout candidate:
within 0–3% of 52W high
relative strength strong
volume expanding
not extended above SMA20
```

```md
Healthy pullback:
3–10% below 52W high
price near SMA20/SMA50
growth score still strong
```

```md
Rebound candidate:
15–35% below 52W high
RSI recovering
price reclaiming SMA20
```

```md
Avoid:
>35% below 52W high
and below SMA200
and weak growth / weak relative strength
```

---

# 7. Tune AVOID_BAD_CHART

This is the biggest technical bug.

## Current

```md
AVOID_BAD_CHART if:
- Price below SMA50 and SMA200
- Relative strength deteriorating
- Down days have higher volume than up days
- RSI weak and not recovering
```

But your backtest shows this label made money. So split it.

## New Technical Rules

### TRUE_DOWNTREND_AVOID

```md
price below SMA50
price below SMA200
SMA50 below SMA200
SMA200 slope negative
RSI < 45
RSI slope flat/down
relative strength vs SPY < -5% over 3M
relative strength vs sector < -3% over 3M
down-volume/up-volume ratio > 1.3
```

### OVERSOLD_REBOUND_CANDIDATE

```md
price below SMA50
price below or near SMA200
RSI 25–42
RSI slope positive
5D return positive or improving
price closes above previous day high
relative volume > 1.2
market regime not in active crash
```

### BROKEN_SUPPORT_AVOID

```md
price breaks 50D low
volume > 1.5x average
close near bottom 30% of daily range
RSI < 40 and falling
```

This change alone should improve your short-term model because `AVOID_BAD_CHART` is currently hiding a profitable rebound setup.

---

# 8. Tune BUY_NOW_MOMENTUM

Current `BUY_NOW_MOMENTUM` is too permissive and underperformed SPY.

## Replace with stricter continuation rule

```md
BUY_NOW_CONTINUATION if:
- price > SMA20 > SMA50 > SMA200
- SMA20 slope positive
- SMA50 slope positive
- price 0% to +5% above SMA20
- price 0% to +12% above SMA50
- RSI 55–68
- RSI slope positive
- 1W return 0% to +6%
- 1M return +3% to +15%
- relative volume > 1.3
- if breakout: relative volume > 1.8
- relative strength vs SPY positive over 20D and 63D
- relative strength vs sector positive over 20D
```

## Avoid buy-now if

```md
price > +10% above SMA20
or RSI > 72
or 1W return > +10%
or 1M return > +25%
```

Those should become:

```md
BUY_STARTER_EXTENDED
or
WAIT_FOR_PULLBACK
```

---

# 9. Tune BUY_ON_PULLBACK

This is the most important profitable setup.

## Current

```md
BUY_ON_PULLBACK if:
- strong medium-term trend
- price pulls back toward SMA50
- volume dries up
- no fundamental deterioration
```

Good, but too vague.

## Make it precise

```md
BUY_ON_PULLBACK if:
- price above SMA200
- SMA50 above SMA200
- SMA50 slope positive or flat
- price within -3% to +5% of SMA50
- price not more than +8% above SMA20
- RSI between 40 and 58
- RSI slope stabilizing or rising
- 1M return not worse than -12%
- 3M return positive
- volume dry-up ratio < 0.85
- relative strength vs sector not worse than -3% over 20D
- growth score >= 60 for growth stocks
```

For hyper-growth stocks:

```md
Allow price within -5% to +8% of SMA50
Allow RSI 38–62
Require smaller position size
```

For mature value:

```md
Require price within -2% to +3% of SMA50
Require RSI 42–55
Require stronger fundamental support
```

---

# 10. Tune Volume Dry-Up

You need this because `BUY_ON_PULLBACK` is working.

## Add explicit volume dry-up ratio

```md
volumeDryUpRatio = avg volume during pullback / 20D avg volume
```

Suggested thresholds:

```md
Strong dry-up:
< 0.70

Good dry-up:
0.70–0.85

Neutral:
0.85–1.10

Bad pullback:
> 1.10

Distribution:
> 1.30 and price down
```

Use:

```md
BUY_ON_PULLBACK:
volumeDryUpRatio < 0.85
```

Avoid:

```md
price near SMA50 but volumeDryUpRatio > 1.20
```

That is not a healthy pullback; that is distribution.

---

# 11. Tune ATR / Stop Rules

Your current framework includes ATR but does not seem to use it strongly enough for entry quality.

## Add ATR percent buckets

```md
ATR% = ATR / price * 100
```

Suggested buckets:

```md
Low volatility: < 2%
Normal: 2–4%
High: 4–7%
Extreme: > 7%
```

Position sizing:

```md
ATR% < 2:
normal position

ATR% 2–4:
normal or starter

ATR% 4–7:
starter only

ATR% > 7:
rebound/speculative only, small size
```

Stop placement:

```md
Short-term continuation:
stop = entry - 1.5 * ATR

Medium-term pullback:
stop = entry - 2.0 to 2.5 * ATR

High-vol growth:
stop = entry - 2.5 * ATR, smaller position
```

Important: volatility should not automatically reduce “return score.” Your backtest showed volatility/risk score was negatively correlated with return. Use ATR for **position sizing**, not rejecting winners.

---

# 12. Tune Regime-Specific Thresholds

The same RSI/volume/SMA values should not apply in all regimes.

Your short-term `BUY_NOW_MOMENTUM` only looked good in `LIQUIDITY_RALLY`, while it underperformed in bear, narrow leadership, risk-on, and sideways regimes. 

## Suggested regime-specific tuning

### LIQUIDITY_RALLY

Allow more aggressive settings:

```md
RSI 55–74
price up to +8% above SMA20
relative volume > 1.2
BUY_STARTER allowed for extended leaders
```

### BULL_RISK_ON

Use normal settings:

```md
RSI 55–68
price up to +5% above SMA20
relative volume > 1.3
```

### SIDEWAYS_CHOPPY

Prefer pullbacks:

```md
BUY_NOW rare
BUY_ON_PULLBACK preferred
price near SMA50
RSI 40–58
volume dry-up required
```

### BEAR_RISK_OFF

Do not use normal momentum continuation.

```md
Only allow:
OVERSOLD_REBOUND_CANDIDATE
or BUY_ON_PULLBACK after market stabilizes

Require:
RSI turning up
SPY/QQQ above 10D or 20D
no fresh support break
```

### BULL_NARROW_LEADERSHIP

Only buy leaders:

```md
Require:
relative strength vs SPY > +3% over 20D
relative strength vs sector > 0
price above SMA50
```

---

# 13. Tune Relative Strength

Current file includes relative strength vs SPY/QQQ/sector as a feature, but the rules do not define exact thresholds.

Add thresholds.

## Suggested relative strength thresholds

```md
RS20_SPY = stock 20D return - SPY 20D return
RS63_SPY = stock 63D return - SPY 63D return
RS20_SECTOR = stock 20D return - sector ETF 20D return
```

### Continuation buy

```md
RS20_SPY > 0
RS63_SPY > 0
RS20_SECTOR > 0
```

### Leader buy

```md
RS20_SPY > +3%
RS63_SPY > +5%
RS20_SECTOR > +2%
```

### Avoid / weak

```md
RS20_SPY < -5%
RS63_SPY < -10%
RS20_SECTOR < -5%
```

### Rebound candidate

```md
RS20_SPY may be negative
but 5D relative strength must improve
```

---

# 14. Suggested First Tuning Grid

Do not tune everything at once. Start with the variables most likely to improve profit.

## Grid 1: BUY_NOW_CONTINUATION

```md
RSI low: 50, 55, 58, 60
RSI high: 68, 70, 72, 74
Max price above SMA20: 4%, 6%, 8%, 10%
Max price above SMA50: 10%, 15%, 20%
Relative volume: 1.2, 1.5, 1.8, 2.0
Minimum RS20_SPY: 0%, +2%, +4%
```

Optimize for:

```md
20D excess return
profit factor
max drawdown
beats SPY %
```

---

## Grid 2: BUY_ON_PULLBACK

```md
Price vs SMA50 lower bound: -5%, -3%, -2%, 0%
Price vs SMA50 upper bound: +3%, +5%, +8%
RSI low: 35, 38, 40, 42
RSI high: 55, 58, 62
Volume dry-up max: 0.70, 0.85, 1.00
RS20_SECTOR minimum: -5%, -3%, 0%
```

Optimize for:

```md
63D excess return
profit factor
drawdown
stop-hit rate
```

---

## Grid 3: Oversold Rebound

```md
RSI low: 20, 25, 30
RSI high: 38, 42, 45
Distance below SMA20: -3%, -5%, -8%, -10%
Distance below SMA50: -5%, -10%, -15%
Relative volume: 1.0, 1.2, 1.5
5D return minimum: -2%, 0%, +2%
```

Optimize for:

```md
10D and 20D return
max adverse excursion
hit target before stop
```

---

# 15. Immediate Code Changes I Would Make

## Change 1

Replace:

```md
RSI between 50 and 70
```

With:

```md
Continuation RSI: 55–68
Extended RSI: 68–76
Rebound RSI: 25–42 and rising
```

## Change 2

Replace:

```md
price not more than 10% above SMA20
```

With:

```md
BUY_NOW: 0% to +5% above SMA20
BUY_STARTER: +5% to +10% above SMA20
WAIT: > +10% above SMA20
```

## Change 3

Add SMA50 distance:

```md
BUY_ON_PULLBACK: -3% to +5% from SMA50
WAIT_FOR_PULLBACK: > +12% above SMA50
AVOID_CHASING: > +20% above SMA50
```

## Change 4

Replace generic relative volume:

```md
relative volume > 1.5
```

With context-specific volume:

```md
Breakout: relative volume > 1.8
Continuation: relative volume > 1.3
Pullback: volume dry-up ratio < 0.85
Reversal: relative volume > 1.2 + green close
```

## Change 5

Split `AVOID_BAD_CHART`:

```md
TRUE_DOWNTREND_AVOID
OVERSOLD_REBOUND_CANDIDATE
BROKEN_SUPPORT_AVOID
WEAK_CHART_BUT_REVERSING
```

---

# 16. Highest-ROI Tuning Order

Do this in order:

```md
1. Tune BUY_ON_PULLBACK around SMA50 distance, RSI 40–58, and volume dry-up.
2. Split AVOID_BAD_CHART into true avoid vs rebound.
3. Tighten BUY_NOW_MOMENTUM using RSI 55–68 and SMA20 distance max +5%.
4. Add relative strength thresholds vs SPY and sector ETF.
5. Make regime-specific thresholds.
6. Use ATR only for stop and position sizing, not signal rejection.
```

