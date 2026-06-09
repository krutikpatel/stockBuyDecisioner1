# High-Level Design — Two-Path Decision Engine

## 1. Purpose

The two-path engine is a CLI-first stock decision system that separates two fundamentally different questions:

- **Is this a good business?** (quality gate — fundamental health)
- **Is now a good time to buy it?** (buy-side timing — dislocation signals)

Mixing these questions — as a single composite score does — dilutes both. A company can be excellent but fully priced, or deeply discounted but structurally broken. The engine forces a hard split before scoring begins.

---

## 2. Architecture Overview

```
                         User / Backtest
                               │
                   python -m two_path_engine.cli NVDA
                               │
                       TwoPathEngine.analyze()
                               │
              ┌────────────────┴────────────────┐
              │         Data Providers          │
              │  yfinance (price, fundamental,  │
              │  earnings, options, news)       │
              └────────────────┬────────────────┘
                               │
                     compute_technicals()
                     classify_regime()
                     classify_archetype()
                               │
                      FeatureSnapshot
                  (flat dict of ~90 fields)
                               │
                        Quality Gate
                     (AND-logic, 5 checks)
                               │
               ┌───────────────┴───────────────┐
               │                               │
          PASSES                            FAILS
               │                               │
        Buy-Side Scorer               Avoid-Side Scorer
     (dislocation timing)          (deterioration depth)
     10 signals + 3 penalties       12 deterioration signals
               │                               │
          BUY / WAIT                   AVOID / WATCHLIST
               │                               │
               └───────────────┬───────────────┘
                               │
                       TwoPathDecision
                  {ticker, path_taken, decision,
                   score, reasons, gate_reasons,
                   missing_fields, risk_plan}
```

---

## 3. Decision Outputs

| Path | Score ≥ threshold | Score < threshold |
|------|-------------------|-------------------|
| quality_intact | **BUY** | **WAIT** |
| deteriorating_business | **AVOID** | **WATCHLIST** |

- **BUY** — quality business in measurable dislocation; timing signals support entry
- **WAIT** — quality business but no timing edge yet (overbought or not enough signals)
- **AVOID** — multi-factor deterioration confirmed; do not hold
- **WATCHLIST** — early warning of deterioration; monitor, not yet confirmed

---

## 4. Quality Gate Logic

The gate is AND-logic: every condition must pass. One failure routes to avoid-side.

| Check | Threshold | On Missing Data |
|-------|-----------|-----------------|
| Gross margin | ≥ 30% | FAILS (required) |
| Operating margin | ≥ −5% | FAILS (required) |
| ROE OR positive FCF | ROE ≥ 5.0 or FCF > 0 | FAILS if both absent |
| Debt/equity | ≤ 2.0 | PASSES (not checked) |
| Current ratio | ≥ 1.0 | PASSES (not checked) |

All thresholds are configurable in `algo_config.json → quality_gate`.

---

## 5. Scoring Logic (Both Paths)

Both scorers use the same point-accumulation mechanism:

1. Load rules from a JSON config file
2. Evaluate each rule's `logic` field against the FeatureSnapshot using `RuleEngine`
3. If the rule fires, add `points` (positive or negative) to the running total
4. Clamp total to [0, 100]
5. Apply decision threshold

**Buy-side:** score ≥ 60 → BUY, else WAIT  
**Avoid-side:** score ≥ 60 → AVOID, else WATCHLIST

Rules are purely additive/subtractive — there are no weights, no multiplicative factors.

---

## 6. Data Flow

### Live Analysis (`TwoPathEngine.analyze`)

```
yfinance APIs
    ├── price history (2y daily) ─→ compute_technicals()
    ├── SPY history (2y daily)   ─→ classify_regime()
    ├── QQQ history (2y daily)   ─┘
    ├── fundamental data         ─→ classify_archetype()
    ├── valuation data           ─┐
    ├── earnings data            ─┤ build_feature_snapshot()
    └── market data              ─┘
                                      │
                                 FeatureSnapshot
                                      │
                                 analyze_snapshot()
                                      │
                                TwoPathDecision
                                      │
                                _build_risk_plan()
```

### Backtest Analysis (`backtest/run_backtest.py`)

```
yfinance APIs (fetched once per ticker, period="max")
    ├── df_full (ticker)
    ├── spy_full
    └── qqq_full
          │
          │  for each sampled trading date:
          ├── df_full.loc[:actual_date]   ─→ compute_technicals()  ← no lookahead
          ├── spy_full.loc[:actual_date]  ─→ classify_regime()     ← no lookahead
          ├── qqq_full.loc[:actual_date]  ─┘
          └── fundamentals (current)      ─→ build_feature_snapshot()
                                                     │
                                            analyze_snapshot()
                                                     │
                                            forward_return(df_full, date, bars=20)
                                            forward_return(df_full, date, bars=60)
```

**Known limitation:** fundamental data (revenue growth, margins, ROE, FCF) is as-of today — yfinance does not expose point-in-time financials. Technical signals on the buy-side path are fully look-ahead free.

---

## 7. Config Files

| File | Purpose |
|------|---------|
| `algo_config.json` | All algorithm parameters — technical indicator periods, quality gate thresholds, risk management factors |
| `config/buy_side_timing_config.json` | 13 rules (10 positive, 3 penalty) for dislocation-timing scorer |
| `config/avoid_side_deterioration_config.json` | 12 rules for deterioration scorer |
| `backtest/loser_universe.json` | 13 known deteriorating tickers for backtest validation |

All strategy logic is in JSON — no business logic in Python beyond loading configs and evaluating rules.

---

## 8. CLI Interface

```bash
cd claude-backend
source .venv/bin/activate

# Single ticker
python -m two_path_engine.cli NVDA

# With verbose risk plan
python -m two_path_engine.cli INTC --verbose

# Batch
python -m two_path_engine.cli AAPL,MSFT,NVDA,INTC

# Backtest (quality universe)
python -m backtest.run_backtest --two-path \
    --tickers NVDA,AAPL,MSFT,GOOGL \
    --start 2022-01-01 --end 2024-01-01

# Backtest (loser universe)
python -m backtest.run_backtest --two-path \
    --tickers loser \
    --start 2022-01-01 --end 2024-01-01
```

---

## 9. Test Strategy

Tests are unit-only — no network calls. All tests operate on synthetic `FeatureSnapshot` objects constructed directly in Python.

| Stage | Test file | Tests | Scope |
|-------|-----------|-------|-------|
| 1 | `test_stage1_data_layer.py` | 11 | Config loads, service imports, technical/fundamental compute |
| 2 | `test_stage2_feature_snapshot.py` | 14 | FeatureSnapshot field mapping, missing data, to_dict() |
| 3 | `test_stage3_quality_gate.py` | 20 | AND-logic gate, threshold edges, missing data, custom config |
| 4 | `test_stage4_buy_side.py` | 14 | BUY/WAIT decisions, penalty rules, score clamping |
| 5 | `test_stage5_avoid_side.py` | 13 | AVOID/WATCHLIST decisions, individual rule firing |
| 6 | `test_stage6_engine.py` | 17 | Routing, all 4 decision outputs, TwoPathDecision structure |
| **Total** | | **89** | **100% pass rate** |

---

## 10. Key Design Decisions

**Why AND-logic for the quality gate?**  
One bad metric (negative FCF, high debt, collapsing margins) is sufficient reason to route a stock to the avoid side. OR-logic would allow a company with 4% gross margin and no FCF to pass because its current ratio is 2.0.

**Why point accumulation instead of weights?**  
Weighted scoring requires calibration data you don't have. Point accumulation is explicit — each rule's contribution is stated plainly in the config, readable by a non-engineer. It also makes audit trails trivial: the `reasons` list shows exactly which rules fired and how many points each contributed.

**Why separate scoring thresholds (not one continuous score)?**  
The buy-side and avoid-side are measuring orthogonal things. A 65/100 on the buy-side means "good entry timing." A 65/100 on the avoid-side means "confirmed deterioration." Using a single 0–100 score for both paths would conflate them.

**Why no horizon differentiation?**  
The engine produces one decision per ticker, not per horizon. Adding horizon-specific weights requires validated backtest data showing which signals predict 1-month vs 3-month returns. Until that data exists, a single decision is more honest than three false-precision outputs.

---

## 11. Known Limitations

- Fundamental data is current-as-of-today (yfinance limitation) — backtest quality gate quality is not fully point-in-time
- No sector/archetype adjustment on buy-side or avoid-side scoring (same rules apply to a semiconductor company and a utility)
- Risk plan targets (+10%, +20%) are fixed and not derived from resistance levels or ATR multiples
- No real-time news or earnings event handling — earnings proximity is noted in the snapshot but not used in scoring
