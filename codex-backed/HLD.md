# High-Level Design

## 1. Overview

`codex-backed` is a CLI-only trade lifecycle engine for short-term and medium-term stock decisions.

The system separates four concerns:

- Entry: should a new trade be opened?
- Exit: how should a trade be sold after entry?
- Risk: how large should the position be, and where are stop/target levels?
- Backtest: how would historical entry signals perform under the configured exit policy?
- Analyze: what does the tuned entry engine say about today's watchlist using fresh market data?

This is intentionally different from the older one-score model where buy and avoid decisions came from the same composite score. The new architecture avoids mixing entry signals and sell signals.

## 2. Design Goals

- Keep all strategy rules in pure JSON config.
- Optimize entry and exit rules separately.
- Use lifecycle trade simulation instead of fixed day-N exits.
- Support partial profit-taking and trailing stops.
- Run as a CLI tool only.
- Use Financial Modeling Prep (FMP) as the primary price and fundamentals source, with yfinance and local pickle as fallbacks.
- Keep outputs easy to inspect in CSV, JSON, and HTML.

## 3. Non-Goals

- No frontend.
- No live brokerage execution.
- No live position tracking.
- No forced sell exactly on the 20th or 63rd trading day.
- No compatibility requirement with old labels.

## 4. System Context

```text
FMP REST API (/stable/)          prices.pkl (pickle fallback)
  historical prices                cached OHLCV bars
  key-metrics, ratios              |
  financial-growth, profile        |
  earnings calendar                |
        |                          |
        v                          v
  CompositePriceProvider  --------+
  CompositeFundamentalsProvider
        |
        v
codex-backed CLI
  config validation
  native feature builder (OHLCV → SMA/RSI/ATR/regime)
  entry engine
  risk engine
  trade simulator
  lifecycle backtest runner
        |
        v
codex-backed/results/<run_id>/
  entry_decisions.csv
  trades.csv
  metrics.json
  sliced metric CSVs
  report.html

Fresh FMP + yfinance data
  watchlist_config.json
        |
        v
codex-backed analyze
  live OHLCV fetch (FMP → yfinance fallback)
  live fundamentals prefetch (FMP → yfinance fallback)
  latest native feature snapshots
  entry engine
  risk/stop preview
        |
        v
codex-backed/results/<run_id>/
  entry_decisions.csv
  actionable_watchlist.csv
  metrics.json
```

## 5. Main Runtime Flow

```text
codex-backed backtest
  -> load JSON configs
  -> validate configs
  -> create run directory
  -> build providers (composite FMP + pickle/yfinance)
  -> fetch historical price bars for all tickers + SPY/QQQ benchmarks
  -> prefetch fundamentals for all tickers
  -> build native feature rows (OHLCV → SMA, RSI, ATR, regime, etc.)
  -> cache feature rows (invalidated by config hash + provider signature)
  -> group work by ticker
  -> process tickers (serial or parallel workers)
  -> run entry decision engine
  -> simulate trades for actionable entries
  -> write artifacts
  -> write report
```

```text
codex-backed analyze
  -> load JSON configs
  -> validate configs
  -> read default watchlist unless --tickers is supplied
  -> build providers (composite FMP → yfinance fallback)
  -> fetch fresh OHLCV bars from FMP/yfinance for watchlist + benchmarks
  -> prefetch fundamentals from FMP, yfinance fallback for override fields
  -> build daily native features through the latest available bar
  -> select the latest row per ticker/horizon
  -> run entry decision engine
  -> compute position size and stop/target preview
  -> write entry_decisions.csv, actionable_watchlist.csv, metrics.json
```

## 6. Entry Engine

The entry engine answers: *Should I open a new trade today?*

Inputs:
- `FeatureSnapshot` (technical + fundamentals fields)
- selected technical setup
- market regime (derived from SPY SMA50/SMA200)
- stock archetype
- signal-card values

Outputs:
- `NO_TRADE`
- `WATCHLIST`
- `BUY_STARTER`
- `BUY_FULL`
- `BUY_AGGRESSIVE`

Entry strategies currently configured:
- `quality_dislocation` — broken-chart recovery in BEAR_RISK_OFF (only active strategy in current baseline)
- `bull_leadership` — trend-following in BULL_RISK_ON
- `oversold_rebound` — RSI reversal
- `pullback_entry` — pullback to moving average in uptrend
- `breakout_entry` — volume breakout
- `no_trade` — catch-all exclusion route

## 7. Exit Engine

The exit engine answers: *If this entry was taken, how would the configured sell policy exit it?*

Exit lifecycle:
1. Enter using configured entry method.
2. Compute initial stop.
3. Compute target 1 from R multiple.
4. Walk forward bar by bar.
5. Exit if stop is hit.
6. Take partial profit if target 1 is hit.
7. Move stop to breakeven if configured.
8. Trail the remaining position.
9. Exit on trailing stop, time stop, or max simulation window.

Current best exit params (from 50-iteration loop):
- Short-term: 2.375R target, 0% partial, breakeven after target, 2.5 ATR trail, 60-day max
- Medium-term: 2.0R target, 40% partial, 1.25R breakeven, 3.0 ATR trail, 90-day max

## 8. Risk Engine

The risk engine applies:
- label-based position size
- high-ATR position cap
- earnings proximity cap
- ATR/support stop logic
- R-multiple target logic

Risk is applied after an entry decision and before trade simulation.

## 9. Backtest Architecture

The backtest runner follows a per-ticker parallel model:

```text
main process
  -> load configs
  -> build providers (FMP + fallbacks)
  -> fetch price bars + fundamentals (API calls happen here; results cached to disk)
  -> build feature rows
  -> create one work item per ticker
  -> start ProcessPoolExecutor (or serial loop if workers=1)

worker process
  -> process all dates/horizons for one ticker
  -> return entry decisions and simulated trades

main process
  -> merge results
  -> write artifacts
```

## 10. Data Sources

### Active configuration (`fmp_primary_yfinance_fallback`)

| Data type | Primary | Fallback |
|-----------|---------|---------|
| Backtest prices | FMP `/stable/historical-price-eod/full` | `prices.pkl` |
| Live prices | FMP `/stable/historical-price-eod/full` | yfinance |
| Fundamentals | FMP `/stable/key-metrics`, `/stable/ratios`, `/stable/financial-growth`, `/stable/profile`, `/stable/earnings` | yfinance |
| Market regime | SPY bars (from price provider above) | — |

FMP data is disk-cached at `codex-backed/cache/fmp/` (24h TTL). Cold-start fetches ~600 API calls for 200 tickers; subsequent runs are served from cache.

FMP history depth confirmed: EOD prices from **2000-01-03** on the $30 Starter plan.

### Legacy configuration (`legacy_yfinance`)

Prices from `prices.pkl` only. No fundamentals. Used for offline tests and as `--data-mode` override when FMP key is unavailable.

### Benchmark tickers

SPY and QQQ are always fetched alongside the trading universe, even if not in `backtest_ticker_universe_config.json`. They are used exclusively for SPY-relative strength and market regime detection and are excluded from the trading universe.

## 11. Output Artifacts

Each backtest run writes:

```text
manifest.json          run metadata and config snapshot
entry_decisions.csv    every decision (NO_TRADE through BUY_AGGRESSIVE)
trades.csv             simulated trades with full lifecycle detail
metrics.json           overall + sliced performance metrics
by_entry_label.csv
by_entry_strategy.csv
by_entry_setup.csv
by_horizon.csv
by_market_regime.csv
by_exit_reason.csv
by_ticker.csv
report.html
run_metrics_data_layer.json   provider-level stats (cache hits, latency, errors)
```

Each analyze run writes:

```text
manifest.json
entry_decisions.csv
actionable_watchlist.csv
metrics.json
run_metrics_data_layer.json
```

## 12. Quality Attributes

**Performance:**
- Ticker-level multiprocessing.
- FMP disk cache eliminates repeated API calls.
- Native feature cache keyed by config hash + provider signature.

**Maintainability:**
- Strategy logic lives in JSON.
- Python handles plumbing, simulation, validation, and reporting.
- Entry and exit concerns are separated.
- Data provider protocol layer isolates API specifics from the backtest runner.

**Testability:**
- Mocked FMP HTTP fixture for all offline tests.
- Real-key smoke tests (`test_fmp_free_key_smoke.py`) gated on `FMP_API_KEY`.
- Full S4.3 activation gates validate end-to-end with real data.
- 183 offline tests pass without any network access.

## 13. Data Provider Protocol Layer

Price and fundamentals data flow through a typed protocol layer:

- `PriceProvider` protocol: `fetch_history_batch`, `fetch_live_batch`, `name`, `capabilities`
- `FundamentalsProvider` protocol: `prefetch_batch`, `get_snapshot`, `name`, `capabilities`
- `ProviderCapabilities` declares what each tier supports: `fundamentals_fields`, `history_start_date`, `rate_limit_per_minute`
- `CompositePriceProvider` tries primary per-ticker, falls back to secondary for misses
- `CompositeFundamentalsProvider` routes each snapshot field individually (primary → fallback → field_overrides)
- `HttpClient` handles retries: 5xx retried with linear backoff; 429 retried with 60-second backoff; other 4xx fail immediately
- `DiskCache` persists API responses to JSON files with schema version and TTL guards
- `DailyBudget` tracks daily API call count (soft limit — logs warning on exceed, does not stop the run)
- Active mode is set in `configs/data_provider_config.json` via `active_mode`; the registry builds concrete providers at runtime

### Fundamentals field routing

| Field | Source |
|-------|--------|
| `eps_growth_yoy`, `gross_margin`, `operating_margin`, `net_margin`, `roic`, `roe`, `roa`, `earnings_days_away`, `earnings_within_30_days`, `free_cash_flow`, `debt_to_equity`, `current_ratio` | FMP primary |
| `forward_pe`, `short_float`, `institutional_ownership`, `analyst_recommendation`, `analyst_target_price` | yfinance (field_overrides — FMP Starter does not carry these) |
| `market_cap`, `beta`, `sector`, `industry`, `trailing_pe`, `peg_ratio`, `price_to_sales`, `ev_to_ebitda` | FMP primary, yfinance fallback if None |

## 14. Current Production Baseline

`fmp_baseline_02` — 200 tickers, 2018-01-02 → 2025-12-31, `fmp_primary_yfinance_fallback`:

| Metric | Value |
|--------|-------|
| Trades | 104 |
| Avg return | 15.67% |
| Median return | 2.98% |
| Win rate | 98.1% |
| Profit factor | 160.6 |

All trades use `quality_dislocation` in `BEAR_RISK_OFF`. Bull market strategies (`bull_leadership`, `oversold_rebound`, `breakout_entry`) produce WATCHLIST detections but no trades — their score thresholds are the primary tuning target.

## 15. Known Limitations and Open Work

- Bull market strategies have 0 trades — entry score thresholds are too strict for non-crash periods.
- Medium-term horizon underperforms short-term (PF 111 vs 226) — trailing stop or max-days needs tightening.
- Fundamentals fields now populated but not yet used in any entry score rule.
- FMP `DiskCache` hits/misses are not wired to `StatsCollector` — `run_metrics_data_layer.json` shows `total=0` for FMP.
- Backtest history starts 2018 — FMP has data to 2000; extending to 2010 would cover 2008 crash.
- HTML report is basic.
- Optimizer commands are scaffolded but not implemented.
