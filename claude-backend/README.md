# This directory is not in use right now - IGNORE- Two-Path Decision Engine

A CLI stock decision tool that answers two separate questions before giving you a verdict:

1. **Is this a good business?** — quality gate (margins, ROE/FCF, leverage, liquidity)
2. **Is now a good time to buy it?** — dislocation-timing score (RSI, volume, drawdown, momentum)

A stock that fails the first question goes to the **avoid/watchlist** path. Only stocks that pass get scored for entry timing. This prevents the engine from recommending entry into a structurally broken company just because it's "oversold."

---

## Quick Start

```bash
cd claude-backend
source .venv/bin/activate

# Analyze a single stock
python -m two_path_engine.cli NVDA

# Verbose output (includes risk plan)
python -m two_path_engine.cli NVDA --verbose

# Batch — analyze several at once
python -m two_path_engine.cli AAPL,MSFT,NVDA,INTC
```

---

## Reading the Output

```
============================================================
  NVDA
  Path    : QUALITY INTACT
  Decision: BUY
  Score   : 72/100
============================================================
Gate:
  All quality gate conditions met
Signals:
  [+25] RSI deeply oversold (20-40): dislocation entry zone
  [+10] RSI slope positive: momentum recovering
  [+15] Price ≥ 20% below 52-week high: meaningful pullback from peak
  [+10] Volume spike ≥ 1.3×: institutional accumulation signal
  [+7]  OBV trend positive: underlying accumulation intact
  [+5]  Price above VWAP: intraday demand active
```

| Field | What it means |
|-------|--------------|
| **Path** | `QUALITY INTACT` — passed quality gate; `DETERIORATING BUSINESS` — failed |
| **Decision** | `BUY`, `WAIT`, `AVOID`, or `WATCHLIST` (see table below) |
| **Score** | 0–100 points accumulated from fired signals |
| **Gate** | Why the stock passed or failed the quality gate |
| **Signals** | Each rule that fired with its point contribution |

### Decision Reference

| Decision | Path | Meaning |
|----------|------|---------|
| **BUY** | quality_intact | Good business, good entry timing right now |
| **WAIT** | quality_intact | Good business, but not a good entry yet (extended or no dislocation) |
| **AVOID** | deteriorating_business | Multiple confirmed deterioration signals — do not hold |
| **WATCHLIST** | deteriorating_business | Early warning only, not yet confirmed — monitor |

### Verbose Risk Plan (`--verbose`)

```
Risk plan:
  decision: BUY
  entry_price: 487.23
  stop_loss: 467.82
  target_1: 535.95
  target_2: 584.68
  atr_pct: 1.99
  risk_per_share: 19.41
```

Stop is placed at 2× ATR below entry. Targets are +10% and +20% from entry.

---

## Daily Workflow

### Morning scan (5–10 minutes)

Run your watchlist in a batch. Focus only on **BUY** decisions — everything else is informational.

```bash
python -m two_path_engine.cli NVDA,AAPL,MSFT,GOOGL,META,AMZN,TSM,ASML
```

A **BUY** means: quality business currently in measurable dislocation with recovery signals firing. Score ≥ 60 required.

### Checking a deteriorating stock you own

```bash
python -m two_path_engine.cli INTC --verbose
```

If the output is `AVOID`, the engine has confirmed multiple deterioration signals (revenue contracting, margins collapsing, high debt, missing earnings estimates). That is a signal to reduce or exit.

If `WATCHLIST`, only one or two warning signs are present — worth monitoring but not confirmed deterioration yet.

### Evaluating an unfamiliar name

```bash
python -m two_path_engine.cli TICKER --verbose
```

Read the **Gate** section first. If it failed, look at *why* — a stock failing on gross margin alone is a different risk profile than one failing on debt/equity and current ratio both. The avoid-side score tells you how severe the deterioration is (50 is early warning; 85 is multi-factor confirmed).

### Checking missing data warnings

If `Missing data:` appears in the output, those fields were `None` from the data provider. The engine still runs but the rules that depend on those fields couldn't fire. A BUY with many missing fields is less reliable than a BUY with all fields populated.

---

## What to Do With Each Decision

**BUY**
- Check the `--verbose` risk plan for stop and targets
- Confirm the reasons make sense for the specific stock (some signals matter more for tech than for utilities)
- Consider position sizing proportional to score (72/100 → larger than 62/100)

**WAIT**
- Check which penalty rules fired (`PENALTY:` prefix in signals)
- Common reason: RSI > 70 (overbought) or price extended >8% above SMA20
- Re-check in 1–2 weeks; quality stocks that pulled back often become BUY

**AVOID**
- Do not add to position
- Review the gate failures and avoid-side signals — they explain *what* is breaking
- AVOID with score 80+ means multiple independent signals confirmed

**WATCHLIST**
- No action needed immediately
- One or two warning signs present; business not yet confirmed broken
- Re-run weekly; if score climbs above 60 it becomes AVOID

---

## Configuration

All thresholds live in `algo_config.json`. You can tighten or relax the quality gate without changing any Python:

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

Scoring rules (which signals fire, how many points) live in:
- `config/buy_side_timing_config.json` — buy-side timing rules
- `config/avoid_side_deterioration_config.json` — deterioration rules

The `decision_thresholds.buy_min_score` and `avoid_min_score` keys (both default 60) control where BUY/WAIT and AVOID/WATCHLIST split.

---

## Running Tests

```bash
cd claude-backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
# Expected: 89 passed
```

Tests are fully offline — no network calls. All tests use synthetic `FeatureSnapshot` objects.

---

## Project Structure

```
claude-backend/
├── two_path_engine/     # Core engine (quality_gate, buy_side, avoid_side, engine, cli)
├── app/                 # Data providers, analysis services, feature builder
├── config/              # Scoring rule JSON files
├── backtest/            # Historical validation runner
├── tests/               # 89 unit tests (6 test files)
├── algo_config.json     # All tunable parameters
├── HLD.md               # System architecture
└── LLD.md               # Implementation detail (classes, APIs, data flow)
```

See `HLD.md` for the full architecture diagram and design rationale.  
See `LLD.md` for class APIs, rule tables, and data flow step-by-step.  
See `BACKTEST_README.md` for how to validate decisions against historical forward returns.

---

## Data Source & Caching

Data is fetched from **yfinance** (free, no API key required for price/fundamental data). Results are cached in memory:
- Price history: 15-minute TTL
- Fundamental data: 24-hour TTL

If you run the CLI twice in quick succession on the same ticker, the second call uses the cache. To force a fresh fetch, restart the Python process.

**Optional:** set `OPENAI_API_KEY` in a `.env` file to enable GPT-4o-mini news sentiment classification. Without it, keyword-based classification is used as a fallback (sentiment is not currently used in scoring decisions).
