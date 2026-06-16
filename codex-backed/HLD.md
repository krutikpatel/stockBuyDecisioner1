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
- Reuse proven parent-backtest ideas such as per-ticker multiprocessing, cached data, and flat output files.
- Keep outputs easy to inspect in CSV, JSON, and HTML.

## 3. Non-Goals

- No frontend.
- No live brokerage execution.
- No live position tracking for now.
- No forced sell exactly on the 20th or 63rd trading day.
- No compatibility requirement with old labels.

## 4. System Context

```text
Existing backend/backtest artifacts
  prices.pkl
  signals_with_outcomes.csv
        |
        v
codex-backed CLI
  config validation
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

Fresh yfinance data
  watchlist_config.json
        |
        v
codex-backed analyze
  live OHLCV fetch
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
  -> load historical feature rows
  -> load historical price bars
  -> group work by ticker
  -> process tickers in parallel
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
  -> use today's local date as requested analysis date
  -> fetch fresh OHLCV bars from yfinance for watchlist + benchmarks
  -> build daily native features through the latest available bar
  -> select the latest row per ticker/horizon
  -> run entry decision engine
  -> compute position size and stop/target preview
  -> write entry_decisions.csv, actionable_watchlist.csv, metrics.json
```

## 6. Entry Engine

The entry engine answers:

```text
Should I open a new trade today?
```

Inputs:

- `FeatureSnapshot`
- selected technical setup
- market regime
- stock archetype
- signal-card values
- raw technical and fundamental fields where available

Outputs:

- `NO_TRADE`
- `WATCHLIST`
- `BUY_STARTER`
- `BUY_FULL`
- `BUY_AGGRESSIVE`

Entry strategies currently configured:

- `quality_dislocation`
- `bull_leadership`
- `oversold_rebound`
- `pullback_entry`
- `breakout_entry`
- `no_trade`

## 7. Exit Engine

The exit engine answers:

```text
If this entry was taken, how would the configured sell policy exit it?
```

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
  -> load configs/data
  -> create one work item per ticker
  -> start ProcessPoolExecutor

worker process
  -> process all dates/horizons for one ticker
  -> return entry decisions and simulated trades

main process
  -> merge results
  -> write artifacts
```

This approach is inherited from the parent `backend/backtest` runner because it is efficient and avoids excessive interprocess overhead.

## 10. Data Sources

Current version:

- Backtest price bars: `codex-backed/cache/prices.pkl`
- Backtest native features: generated locally from OHLCV bars and cached in `codex-backed/cache/features.pkl`
- Live analysis price bars: fresh yfinance daily OHLCV fetched at runtime

Planned version:

- Optional parquet-based cache if pickle becomes too large.

## 11. Output Artifacts

Each backtest run writes:

```text
manifest.json
entry_decisions.csv
trades.csv
metrics.json
by_entry_label.csv
by_entry_strategy.csv
by_entry_setup.csv
by_market_regime.csv
by_exit_reason.csv
by_ticker.csv
report.html
```

Each analyze run writes:

```text
manifest.json
entry_decisions.csv
actionable_watchlist.csv
metrics.json
```

## 12. Quality Attributes

Performance:

- Ticker-level multiprocessing.
- Cached parent price/features.
- Batch file writes.

Maintainability:

- Strategy logic lives in JSON.
- Python code handles plumbing, simulation, validation, and reporting.
- Entry and exit concerns are separated.

Testability:

- Synthetic path tests for trade simulation.
- Config validation tests.
- Rule engine tests.
- Backtest runner integration test with synthetic fixtures.
- Analyze runner tests with fake live-data fetcher fixtures.

## 13. Data Provider Protocol Layer

Price and fundamentals data are fetched through a typed protocol layer:

- `PriceProvider` protocol: `fetch_history_batch`, `fetch_live_batch`, `name`, `capabilities`
- `FundamentalsProvider` protocol: `prefetch_batch`, `get_snapshot`, `name`, `capabilities`
- `ProviderCapabilities` declares what each tier supports (`fundamentals_fields`, `history_start_date`, etc.)
- `CompositePriceProvider` and `CompositeFundamentalsProvider` implement fallback routing transparently
- Active mode is set in `configs/data_provider_config.json` via `active_mode`; the registry builds concrete providers at runtime

## 14. Known Limitations

- The HTML report is basic and should be expanded.
- Optimizer commands are scaffolded but not implemented.
- Live analysis depends on yfinance availability and data freshness.
- Live analysis does not place trades or track open positions.
