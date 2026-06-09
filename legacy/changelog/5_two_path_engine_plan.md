# Two-Path Decision Engine — Clean-Break Plan

## Context

The current engine produces a single composite score from 11 signal cards and routes everything through the same decision gates. This is architecturally wrong: the signals that tell you *when to buy* (dislocation, RSI recovery, vol spike) are the opposite of the signals that tell you *what to avoid* (revenue decel, margin compression, debt rising). Mixing them dilutes both.

The fix is a quality gate as the first split:

```
Quality gate (fundamentally sound business?)
         │
  ┌──────┴──────┐
  ▼             ▼
YES: intact    NO: deteriorating
  │             │
  ▼             ▼
Buy-side      Avoid-side
timing model  deterioration model
  │             │
  ▼             ▼
BUY / WAIT   AVOID / WATCHLIST
```

This replaces all old engine code entirely. Frontend is deleted. Access is CLI-only.

---

## New Project Directory

All new work lives in `claude-backend/` — a sibling directory to the existing `backend/` and `frontend/`. This isolation allows the old code to be deleted cleanly without risk.

```
usingGptStrategy/
  backend/           ← existing (will be deleted after migration)
  frontend/          ← existing (will be deleted)
  claude-backend/    ← NEW PROJECT (all new work goes here)
    two_path_engine/
      __init__.py
      engine.py          ← TwoPathEngine: main orchestrator
      quality_gate.py    ← multi-factor AND-logic gate
      buy_side.py        ← dislocation-timing scorer
      avoid_side.py      ← deterioration scorer
      cli.py             ← CLI entry point
    app/
      providers/         ← copied/adapted from backend/app/providers/
      services/          ← copied/adapted: technical, fundamental, valuation, regime, archetype, news, risk
      features/          ← copied/adapted: feature_snapshot.py, feature_builder.py
      engine/
        rule_engine.py   ← copied from backend/app/engine/rule_engine.py
      cache/             ← copied from backend/app/cache/
      data/              ← copied from backend/app/data/
      algo_config.py     ← copied/adapted (strips old signal_card sections)
    config/
      buy_side_timing_config.json           ← NEW
      avoid_side_deterioration_config.json  ← NEW
    backtest/            ← copied/adapted from backend/backtest/ + --two-path flag
      loser_universe.json  ← NEW
    tests/
      test_two_path_engine.py  ← NEW
    algo_config.json     ← cleaned-up (quality_gate section, no signal_card weights)
    requirements.txt
```

**CLI usage** (from `claude-backend/`):
```bash
source .venv/bin/activate
python -m two_path_engine.cli NVDA
python -m two_path_engine.cli INTC --verbose
python -m two_path_engine.cli AAPL,MSFT,NVDA  # batch
```

---

## Scope Note: No Deletions

The existing `backend/` and `frontend/` directories are left untouched. All new work goes exclusively into `claude-backend/`. Once the new engine is validated, removing the old directories is a separate decision.

---

## What Gets Kept

**Data providers (raw data fetching):**
- `app/providers/market_data_provider.py`
- `app/providers/fundamental_provider.py`
- `app/providers/earnings_provider.py`
- `app/providers/news_provider.py`
- `app/providers/options_provider.py`

**Analysis services (computation only, no decision logic):**
- `app/services/technical_analysis_service.py`
- `app/services/fundamental_analysis_service.py`
- `app/services/valuation_analysis_service.py`
- `app/services/market_regime_service.py`
- `app/services/stock_archetype_service.py`
- `app/services/news_sentiment_service.py`
- `app/services/risk_management_service.py`
- `app/services/markdown_report_service.py`

**Feature layer (reusable adapters):**
- `app/features/feature_snapshot.py` — flat normalized feature dict (pure data model)
- `app/features/feature_builder.py` — flattens service outputs into FeatureSnapshot (pure adapter, zero business logic)

**Infrastructure:**
- `app/algo_config.py` (singleton config loader)
- `app/engine/rule_engine.py` (JSON logic evaluator, reused)
- `app/cache/`
- `app/data/`
- `algo_config.json` (modified — strip old engine params, add quality_gate section)
- `backtest/` (kept, modified to add `--two-path` flag and loser universe)

---

## New Config Files

### `algo_config.json` — additions
```json
"quality_gate": {
  "gross_margin_min": 0.30,
  "op_margin_min": -0.05,
  "roe_min": 5.0,
  "fcf_substitutes_roe": true,
  "debt_equity_max": 2.0,
  "current_ratio_min": 1.0
}
```
Removed sections: all `signal_cards.*`, `signal_card_short_weights`, `signal_card_medium_weights`, `signal_card_long_weights`, `scoring`, `decision_logic` (old gate params).
Kept sections: `technical_indicators`, `extension_detection`, `market_regime`, `stock_archetype`.

### `config/buy_side_timing_config.json`
Scoring rules for quality stocks. Each rule: `{logic, points, reason}`.

Features used: `rsi14`, `rsi_slope`, `dist_52w_high_pct`, `atr_pct`, `stoch_rsi`, `volume_ratio`, `obv_slope`, `vwap_relative`, `sma20_relative`, `drawdown_from_high`.

Decision thresholds (evaluated in order):
- `strategy_score >= 60` → **BUY** (dislocation + recovery confirmed)
- else → **WAIT**

Key scoring rules (points add to 0–100):
- RSI 20–40 (deep oversold): +25
- RSI turning up (rsi_slope > 0): +10
- Distance from 52W high ≤ -20%: +15
- Volume spike ≥ 1.3×: +10
- ATR elevated (≥ 2%): +8
- OBV slope positive: +7
- Price above VWAP: +5
- Penalties: RSI > 70: -20; price > 8% above SMA20: -15

### `config/avoid_side_deterioration_config.json`
Scoring rules for deteriorating stocks. Features used: `revenue_growth_yoy`, `op_margin`, `gross_margin`, `debt_equity`, `beat_rate`, `free_cash_flow`, `sma200_relative`, `insider_transactions`, `eps_growth_yoy`.

Decision thresholds:
- `strategy_score >= 60` → **AVOID** (confirmed multi-factor deterioration)
- else → **WATCHLIST** (early warning, not yet confirmed)

Key scoring rules:
- Revenue YoY ≤ 0%: +20
- Revenue QoQ declining: +10
- Op margin < -5%: +20
- Op margin declining YoY: +10
- Beat rate < 40%: +15
- Debt/equity > 2.0: +15
- FCF negative: +10
- Price > 15% below SMA200: +8
- Insider selling (net negative): +7

### `backtest/loser_universe.json`
```json
["INTC", "PFE", "BABA", "T", "MPW", "DLTR", "WBA", "VFC", "PARA", "BEN", "MO", "CVS", "MMM"]
```

---

## New Engine Files

### `two_path_engine/quality_gate.py`
```python
class QualityGate:
    def passes(self, snapshot: FeatureSnapshot) -> bool
    # AND-logic: gross_margin, op_margin, (roe OR fcf > 0), debt_equity, current_ratio
    # Reads thresholds from algo_config.json quality_gate section
```

### `two_path_engine/buy_side.py` and `two_path_engine/avoid_side.py`
Each wraps `RuleEngine` (reused from `app/engine/rule_engine.py`) + loads its own config JSON.
Returns: `score (0-100)`, `decision (BUY|WAIT or AVOID|WATCHLIST)`, `reasons (list[str])`.

### `two_path_engine/engine.py`
```python
@dataclass
class TwoPathDecision:
    ticker: str
    path_taken: str        # "quality_intact" | "deteriorating_business"
    decision: str          # BUY | WAIT | AVOID | WATCHLIST
    score: float
    reasons: list[str]
    risk_plan: dict        # from risk_management_service

class TwoPathEngine:
    def analyze(self, ticker: str) -> TwoPathDecision
```

### `two_path_engine/cli.py`
Thin wrapper: parses `sys.argv`, calls `TwoPathEngine.analyze()`, prints formatted output (markdown or plain text).

---

## Implementation Order

1. Create `config/buy_side_timing_config.json`
2. Create `config/avoid_side_deterioration_config.json`
3. Add `quality_gate` section to `algo_config.json` (strip old signal_card weight sections)
4. Create `two_path_engine/quality_gate.py`
5. Create `two_path_engine/buy_side.py`
6. Create `two_path_engine/avoid_side.py`
7. Create `two_path_engine/engine.py`
8. Create `two_path_engine/cli.py`
9. Create `backtest/loser_universe.json`
10. Add `--two-path` flag to `backtest/run_backtest.py`
11. Write tests: `tests/test_two_path_engine.py`
12. Delete old files (services, engine, config/, frontend/, router, main)

---

## Verification

```bash
cd usingGptStrategy/claude-backend
source .venv/bin/activate

# Unit tests
PYTHONPATH=. pytest tests/test_two_path_engine.py -v

# CLI smoke tests
python -m two_path_engine.cli NVDA    # expect: quality_intact → BUY or WAIT
python -m two_path_engine.cli INTC    # expect: deteriorating_business → AVOID or WATCHLIST
python -m two_path_engine.cli AAPL,MSFT,NVDA,INTC,PFE  # batch

# Backtest — quality universe
python -m backtest.run_backtest --two-path \
  --tickers NVDA,AAPL,MSFT,GOOGL \
  --start 2022-01-01 --end 2024-01-01

# Backtest — loser universe
python -m backtest.run_backtest --two-path \
  --tickers INTC,PFE,BABA,T,WBA \
  --start 2022-01-01 --end 2024-01-01
# Validate: BUY decisions → positive MFE; AVOID decisions → negative forward returns
```
