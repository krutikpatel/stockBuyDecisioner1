# Low-Level Design — Two-Path Decision Engine

## 1. Project Layout

```
claude-backend/
├── algo_config.json                    # All tunable parameters
├── app/
│   ├── algo_config.py                  # AlgoConfig singleton loader
│   ├── config.py                       # Settings (TTLs, API keys)
│   ├── cache/
│   │   └── cache_manager.py            # TTLCache wrappers (15min price, 24h fundamentals)
│   ├── engine/
│   │   └── rule_engine.py              # JSON logic evaluator
│   ├── features/
│   │   ├── feature_snapshot.py         # FeatureSnapshot Pydantic model (~90 fields)
│   │   └── feature_builder.py          # build_feature_snapshot() — pure adapter
│   ├── models/
│   │   ├── market.py                   # MarketData, TechnicalIndicators, MarketRegimeAssessment
│   │   ├── fundamentals.py             # FundamentalData, ValuationData, StockArchetype
│   │   ├── earnings.py                 # EarningsData
│   │   └── news.py                     # NewsItem, NewsSummary
│   ├── providers/
│   │   ├── market_data_provider.py     # get_history(), get_market_data()
│   │   ├── fundamental_provider.py     # get_fundamental_data(), get_valuation_data()
│   │   ├── earnings_provider.py        # get_earnings_data()
│   │   ├── news_provider.py            # get_news_items()
│   │   └── options_provider.py         # get_options_snapshot()
│   └── services/
│       ├── technical_analysis_service.py   # compute_technicals() → TechnicalIndicators
│       ├── fundamental_analysis_service.py # score_fundamentals() → float
│       ├── valuation_analysis_service.py   # score_valuation() → float
│       ├── market_regime_service.py        # classify_regime() → MarketRegimeAssessment
│       ├── stock_archetype_service.py      # classify_archetype(), classify_and_attach()
│       ├── news_sentiment_service.py       # classify_news() → NewsSummary
│       └── risk_management_service.py      # compute_risk_management()
├── config/
│   ├── buy_side_timing_config.json     # 13 buy-side scoring rules
│   └── avoid_side_deterioration_config.json  # 12 avoid-side scoring rules
├── two_path_engine/
│   ├── __init__.py
│   ├── quality_gate.py                 # QualityGate — AND-logic filter
│   ├── buy_side.py                     # BuySideScorer — dislocation-timing
│   ├── avoid_side.py                   # AvoidSideScorer — deterioration depth
│   ├── engine.py                       # TwoPathEngine, TwoPathDecision
│   └── cli.py                          # CLI entry point
├── backtest/
│   ├── run_backtest.py                 # --two-path backtest runner
│   └── loser_universe.json             # 13 known deteriorating tickers
└── tests/
    ├── test_stage1_data_layer.py
    ├── test_stage2_feature_snapshot.py
    ├── test_stage3_quality_gate.py
    ├── test_stage4_buy_side.py
    ├── test_stage5_avoid_side.py
    └── test_stage6_engine.py
```

---

## 2. `app/algo_config.py` — Config Singleton

```python
class AlgoConfig:
    def __init__(self, data: dict)
    @classmethod def from_file(cls, path=None) -> AlgoConfig   # reads ALGO_CONFIG_PATH env var
    @classmethod def from_dict(cls, data: dict) -> AlgoConfig  # for tests
    def get(self, section: str) -> dict
    # Properties: technical_indicators, technical_scoring, extension_detection,
    #             stock_archetype, market_regime, regime_scoring,
    #             risk_management, valuation, quality_gate

def get_algo_config() -> AlgoConfig    # module-level singleton
def reset_algo_config() -> None        # clears singleton (required in tests)
```

**`algo_config.json` sections used by the engine:**

| Section | Used by |
|---------|---------|
| `technical_indicators` | `compute_technicals()` |
| `technical_scoring` | `score_technicals()` |
| `extension_detection` | `detect_extension()` |
| `stock_archetype` | `classify_archetype()` |
| `market_regime` | `classify_regime()` |
| `risk_management` | `_build_risk_plan()` |
| `valuation` | `score_valuation()` |
| `quality_gate` | `QualityGate.evaluate()` |

**`quality_gate` section:**
```json
{
  "gross_margin_min": 0.30,
  "op_margin_min": -0.05,
  "roe_min": 5.0,
  "fcf_substitutes_roe": true,
  "debt_equity_max": 2.0,
  "current_ratio_min": 1.0
}
```

---

## 3. `app/engine/rule_engine.py` — RuleEngine

Evaluates JSON logic trees against a flat dict (the FeatureSnapshot).

**Supported composite nodes:**
- `{"all": [...]}` — AND (short-circuits on first failure)
- `{"any": [...]}` — OR (short-circuits on first match)
- `{"not": {...}}` — negation

**Supported leaf operators:**
`>=`, `<=`, `>`, `<`, `==`, `!=`, `in`, `not_in`, `between`, `exists`, `missing`, `contains`

**Missing field handling:** if a field is `None`, the condition evaluates to `False` and the field is recorded in `missing_fields`. A configurable penalty (default 10 points per missing field, capped at 100) is available in `RuleEvaluationResult.confidence_penalty` — currently unused by the two-path scorers.

**Return type:**
```python
@dataclass
class RuleEvaluationResult:
    matched: bool
    reasons: list[str]
    missing_fields: list[str]
    confidence_penalty: float
```

---

## 4. `app/features/feature_snapshot.py` — FeatureSnapshot

Pydantic model (~90 optional fields). All fields default to `None` so the rule engine can detect and handle missing data without crashing.

**Field groups:**

| Group | Fields |
|-------|--------|
| Identity | ticker, as_of_date, price, sector, market_cap, avg_volume, beta |
| MA relatives | sma20/50/200_relative, ema8/21_relative |
| MA slopes | sma20/50/200_slope |
| Momentum | rsi14, rsi_slope, macd_histogram, adx, stochastic_rsi |
| Volatility | atr_percent, bollinger_band_position/width, volatility_weekly |
| Performance | perf_1w/1m/3m/6m/1y, gap_percent, change_from_open_percent |
| Volume/accumulation | obv_trend, ad_trend, chaikin_money_flow, vwap_deviation, volume_dryup_ratio, breakout_volume_multiple, updown_volume_ratio |
| Range distances | dist_from_52w_high/low, dist_from_20d_high |
| Drawdown | max_drawdown_3m/1y |
| Relative strength | rs_vs_spy, rs_vs_spy_20d/63d, rs_vs_sector_20d/63d, return_pct_rank_20d/63d |
| Trend | trend_label, is_extended, extension_pct_above_20ma/50ma |
| Fundamental | sales_growth_yoy/qoq, eps_growth_yoy/next_year/3y/5y, gross_margin, operating_margin, net_margin, free_cash_flow, roic, roe, roa, debt_to_equity, current_ratio, insider/institutional_ownership, short_float, analyst_recommendation, target_price_distance, dividend_yield |
| Valuation | forward_pe, trailing_pe, peg_ratio, price_to_sales, ev_to_ebitda, price_to_fcf, fcf_yield, ev_sales |
| Earnings | beat_rate, avg_eps_surprise_pct, earnings_days_away, earnings_within_30_days |
| Classification | primary_category, secondary_tags, market_regime, regime_confidence, selected_setup |
| Engine state | strategy_score, confidence |

`to_dict()` returns `model_dump()` — the full flat dict fed to `RuleEngine.evaluate()`.

---

## 5. `app/features/feature_builder.py` — build_feature_snapshot

Pure adapter function. Takes all service outputs and maps them into a `FeatureSnapshot`. Contains no scoring or business logic.

```python
def build_feature_snapshot(
    ticker: str,
    price: float,
    technicals: TechnicalIndicators,
    fundamentals: FundamentalData,
    valuation: ValuationData,
    earnings: EarningsData,
    market_data: Optional[MarketData] = None,
    regime_assessment: Optional[MarketRegimeAssessment] = None,
    as_of_date: Optional[str] = None,
) -> FeatureSnapshot
```

Notable mappings:
- `technicals.rsi_14` → `snapshot.rsi14`
- `fundamentals.revenue_growth_yoy` → `snapshot.sales_growth_yoy`
- `fundamentals.archetype` → mapped via `_ARCHETYPE_TO_CATEGORY` dict → `snapshot.primary_category`
- `earnings_days_away` computed from `earnings.next_earnings_date` and `as_of_date`

---

## 6. `two_path_engine/quality_gate.py` — QualityGate

```python
@dataclass
class QualityGateResult:
    passes: bool
    reasons: list[str]      # failure messages if passes=False, "All conditions met" if passes=True

class QualityGate:
    def __init__(self, algo_config: AlgoConfig | None = None)
    def evaluate(self, snapshot: FeatureSnapshot) -> QualityGateResult
```

**Evaluation order and failure semantics:**

1. `gross_margin` — required field; `None` → FAIL
2. `operating_margin` — required field; `None` → FAIL
3. ROE OR FCF check — `None` for both → FAIL; either passing → PASS
4. `debt_to_equity` — optional; `None` → skip (don't fail)
5. `current_ratio` — optional; `None` → skip (don't fail)

All failures are collected; evaluation does not short-circuit. This gives the caller a full list of reasons (useful for CLI output and debugging).

**Configurability:** `QualityGate(algo_config=custom_cfg)` for tests or experiments.

---

## 7. `two_path_engine/buy_side.py` — BuySideScorer

```python
@dataclass
class BuySideResult:
    score: float            # [0, 100]
    decision: str           # "BUY" | "WAIT"
    reasons: list[str]      # "[+25] RSI deeply oversold ..." for each fired rule
    missing_fields: list[str]

class BuySideScorer:
    def __init__(self, config_path: Path | None = None)
    def score(self, snapshot: FeatureSnapshot) -> BuySideResult
```

**Config: `config/buy_side_timing_config.json`**

| Rule id | Field | Operator | Points | Rationale |
|---------|-------|----------|--------|-----------|
| rsi_deep_oversold | rsi14 | between [20, 40] | +25 | Deep dislocation zone |
| rsi_turning_up | rsi_slope | > 0 | +10 | Momentum recovering |
| dist_from_52w_high_deep | dist_from_52w_high | ≤ −0.20 | +15 | Meaningful pullback from peak |
| volume_spike | breakout_volume_multiple | ≥ 1.3 | +10 | Institutional accumulation |
| atr_elevated | atr_percent | ≥ 2.0 | +8 | Volatility creates entry opportunity |
| obv_positive | obv_trend | > 0 | +7 | Underlying accumulation intact |
| price_above_vwap | vwap_deviation | > 0 | +5 | Intraday demand active |
| stochrsi_oversold | stochastic_rsi | ≤ 20 | +8 | Short-term deeply oversold |
| cmf_positive | chaikin_money_flow | > 0 | +5 | Buying pressure confirmed |
| drawdown_significant | max_drawdown_3m | ≤ −0.15 | +7 | 3-month correction meaningful |
| penalty_rsi_overbought | rsi14 | > 70 | −20 | Overbought, poor entry timing |
| penalty_extended_above_sma20 | sma20_relative | > 8.0 | −15 | Extended above MA |
| penalty_downtrend | sma200_relative | < −15.0 | −10 | Structural downtrend |

Max achievable score (all positives fire, no penalties): 90  
Decision threshold: **60**

---

## 8. `two_path_engine/avoid_side.py` — AvoidSideScorer

```python
@dataclass
class AvoidSideResult:
    score: float            # [0, 100]
    decision: str           # "AVOID" | "WATCHLIST"
    reasons: list[str]      # "[+20] Revenue YoY ≤ 0% ..."
    missing_fields: list[str]

class AvoidSideScorer:
    def __init__(self, config_path: Path | None = None)
    def score(self, snapshot: FeatureSnapshot) -> AvoidSideResult
```

**Config: `config/avoid_side_deterioration_config.json`**

| Rule id | Field | Operator | Points | Rationale |
|---------|-------|----------|--------|-----------|
| revenue_declining_yoy | sales_growth_yoy | ≤ 0.0 | +20 | Top-line contraction |
| revenue_declining_qoq | sales_growth_qoq | < 0.0 | +10 | Sequential deceleration |
| op_margin_negative | operating_margin | < −0.05 | +20 | Burning cash operationally |
| op_margin_negative_mild | operating_margin | between [−0.05, 0.0] | +10 | Margins deteriorating |
| eps_beat_rate_low | beat_rate | < 0.40 | +15 | Management missing estimates |
| debt_equity_high | debt_to_equity | > 2.0 | +15 | Elevated leverage risk |
| fcf_negative | free_cash_flow | < 0 | +10 | Cash burn |
| price_far_below_sma200 | sma200_relative | < −15.0 | +8 | Structural breakdown |
| eps_growth_negative | eps_growth_yoy | < 0.0 | +10 | Earnings deterioration |
| gross_margin_compressed | gross_margin | < 0.20 | +12 | Severe margin compression |
| current_ratio_low | current_ratio | < 0.8 | +8 | Near-term liquidity stress |
| roe_negative | roe | < 0.0 | +7 | Destroying shareholder value |

Max achievable score (all rules fire): 125 → clamped to 100  
Decision threshold: **60**

---

## 9. `two_path_engine/engine.py` — TwoPathEngine

```python
@dataclass
class TwoPathDecision:
    ticker: str
    path_taken: str         # "quality_intact" | "deteriorating_business"
    decision: str           # "BUY" | "WAIT" | "AVOID" | "WATCHLIST"
    score: float            # [0, 100]
    reasons: list[str]      # fired scoring rules
    gate_reasons: list[str] # quality gate pass/fail messages
    missing_fields: list[str]
    risk_plan: dict         # entry_price, stop_loss, target_1, target_2, atr_pct
    snapshot: FeatureSnapshot | None

class TwoPathEngine:
    def __init__(self)
        # Instantiates: QualityGate, BuySideScorer, AvoidSideScorer

    def analyze(self, ticker: str) -> TwoPathDecision
        # Full live pipeline: fetch → compute → build_snapshot → analyze_snapshot → risk_plan

    def analyze_snapshot(self, snapshot: FeatureSnapshot) -> TwoPathDecision
        # Scoring only: gate → route → score (no I/O)
```

**`analyze()` call sequence:**

```
get_history(ticker, "2y")           ← yfinance, TTL-cached 15min
get_history("SPY", "2y")
get_history("QQQ", "2y")
get_market_data(ticker)             ← yfinance info, TTL-cached 24h
get_fundamental_data(ticker)
get_valuation_data(ticker)
get_earnings_data(ticker)
classify_and_attach(fundamental_data)   ← sets .archetype in-place
compute_technicals(df, spy_df=spy_df)   → TechnicalIndicators
classify_regime(spy_df, qqq_df)         → MarketRegimeAssessment
build_feature_snapshot(...)             → FeatureSnapshot
analyze_snapshot(snapshot)              → TwoPathDecision (no risk_plan yet)
_build_risk_plan(snapshot, decision)    → dict
decision.risk_plan = risk_plan
return decision
```

**`_build_risk_plan` (module-level helper):**

```
stop_loss = price − 2 × (atr_pct% × price)
target_1  = price × 1.10
target_2  = price × 1.20
```

---

## 10. `two_path_engine/cli.py` — CLI

```python
def run(args: Sequence[str] | None = None) -> None

# Entry: python -m two_path_engine.cli
```

**Output format (default):**
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
  ...
```

**With `--verbose`:** appends the risk plan (entry, stop, targets, ATR%).

**Batch:** comma-separated tickers processed sequentially; errors per ticker are printed and skipped without aborting the batch.

---

## 11. `backtest/run_backtest.py` — Backtest Runner

**No-lookahead protocol:**

```
Pre-fetch (once per ticker):
  df_full   = get_history(ticker, period="max")
  spy_full  = get_history("SPY",  period="max")
  qqq_full  = get_history("QQQ",  period="max")
  fund      = get_fundamental_data(ticker)      ← current only
  val       = get_valuation_data(ticker)
  earn      = get_earnings_data(ticker)
  classify_and_attach(fund)

For each sampled date (every freq_bars trading bars within [start, end]):
  df_slice  = df_full.loc[:actual_date]         ← no future prices
  spy_slice = spy_full.loc[:actual_date]
  qqq_slice = qqq_full.loc[:actual_date]
  technicals = compute_technicals(df_slice, spy_df=spy_slice)
  regime     = classify_regime(spy_slice, qqq_slice)
  snapshot   = build_feature_snapshot(price=df_slice["Close"].iloc[-1], ...)
  decision   = engine.analyze_snapshot(snapshot)   ← no I/O

  fwd_20d = _forward_return(df_full, actual_date, bars=20)  ← uses full df
  fwd_60d = _forward_return(df_full, actual_date, bars=60)
```

**`_forward_return(df, entry_date, bars)`:**
- Finds `entry_idx` via `searchsorted`
- Returns `None` if `entry_idx + bars >= len(df)` (insufficient future data)
- Returns `(close[entry_idx + bars] − close[entry_idx]) / close[entry_idx]`
- `bars` is trading bars, not calendar days (20 bars ≈ 1 month, 60 bars ≈ 3 months)

**Summary output:**
```
  Decision      n      avg 20d   avg 60d   win% 20d
  -------------------------------------------------------
  BUY          42      +3.21%    +6.87%      64.3%
  WAIT         18      +0.41%    +0.93%      55.6%
  AVOID        31      -2.15%    -4.02%      35.5%
  WATCHLIST    12      -0.88%    -1.44%      41.7%
```

**CSV output:** saved to `backtest/results/two_path_YYYYMMDD_HHMMSS.csv` with columns: `ticker`, `date`, `path_taken`, `decision`, `score`, `fwd_return_20d`, `fwd_return_60d`, `reasons`.

---

## 12. `app/cache/cache_manager.py` — Caching

Two `TTLCache` instances (from `cachetools`), protected by a `threading.Lock`:

| Cache | TTL | Key format |
|-------|-----|------------|
| `_price_cache` | 900s (15 min) | `"{ticker}:{period}:{interval}"` |
| `_fundamental_cache` | 86400s (24 h) | `"fundamental:{ticker}"` |

All providers call `get_cached()` first; on miss, fetch from yfinance and `set_cached()`.

---

## 13. Testing Conventions

- All tests in `tests/` operate on synthetic `FeatureSnapshot` objects — no network calls
- `QualityGate`, `BuySideScorer`, `AvoidSideScorer` all accept `FeatureSnapshot` directly
- `TwoPathEngine.analyze_snapshot()` is the testable path; `analyze()` is the I/O path
- Tests that inject custom `AlgoConfig` use `AlgoConfig.from_dict({...})` — no file I/O
- No pytest fixtures with scope > function; each test constructs its own data

**Run all tests:**
```bash
cd claude-backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
# Expected: 89 passed
```
