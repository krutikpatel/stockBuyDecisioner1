# Low-Level Design

## 1. Package Layout

```text
codex-backed/
  configs/
    technical_setup_config.json
    entry_signal_config.json
    risk_config.json
    exit_policy_config.json
    backtest_config.json
    data_provider_config.json
    backtest_ticker_universe_config.json
    watchlist_config.json
  scripts/
    fmp_access_audit.py         probe FMP plan coverage across the ticker universe
  src/codex_backed/
    cli.py
    analyze.py
    results.py
    config/
      loader.py
    rules/
      rule_engine.py
    features/
      snapshot.py
      historical_builder.py     native OHLCV → feature row pipeline
    entry/
      labels.py
      setup_detector.py
      engine.py
    risk/
      sizing.py
      stops.py
    simulation/
      entry_simulator.py
      trade.py
      trade_simulator.py
    data/
      bars.py
      loader.py
      fundamentals_snapshot.py
      providers/
        base.py                 ProviderError
        capabilities.py         ProviderCapabilities dataclass
        cache.py                DiskCache (JSON, TTL, schema version)
        budget.py               DailyBudget (soft daily call limit)
        rate_limiter.py         TokenBucket (token-bucket rate limiter)
        http_client.py          HttpClient (requests wrapper, retry, redaction)
        fmp_provider.py         FMPPriceProvider, FMPFundamentalsProvider
        yfinance_provider.py    YFinancePriceProvider, YFinanceFundamentalsProvider
        pickle_provider.py      PickleProvider (prices.pkl)
        null_fundamentals.py    NullFundamentalsProvider (legacy_yfinance mode)
        composite.py            CompositePriceProvider, CompositeFundamentalsProvider
        alias_apply.py          FMP JSON key → FeatureSnapshot field mapping
        field_aliases.py        FMP_ALIASES dict
        observability.py        StatsCollector, run_metrics_data_layer.json
        registry.py             build_providers() factory
    backtest/
      metrics.py
      runner.py
      worker.py
      writer.py
  tests/
    fixtures/
      fmp/
        __mocked_session__.py   mock_fmp_http() context manager
        historical_aapl.json
        key_metrics_aapl.json
        profile_aapl.json
        earning_calendar.json
      prices_fixture.pkl
      legacy_baseline_metrics.json
    test_fmp_price_provider.py
    test_fmp_fundamentals_provider.py
    test_fmp_free_key_smoke.py   real-key smoke (skipped without FMP_API_KEY)
    test_activation_gates.py     S4.3 gates (skipped without FMP_API_KEY)
    test_fmp_baseline_capture.py S4.2 baseline (skipped without FMP_API_KEY)
    test_http_client.py
    test_e2e_fmp_mode_smoke.py   mocked end-to-end FMP backtest
    ... (30+ other test files)
```

## 2. CLI Layer

File: `src/codex_backed/cli.py`

Implemented commands:
```text
validate-config
analyze
backtest
```

Backtest options:
```text
--config-dir
--output-dir
--run-id
--tickers
--start
--end
--workers
--feature-source
--force-refresh
--rebuild-feature-cache
--no-report
--data-mode        override active_mode from data_provider_config.json
```

`analyze` has no `--date` option. It uses today's local date as the requested analysis date and the latest bar as the actual signal date.

## 3. Config Layer

File: `src/codex_backed/config/loader.py`

Key types: `ConfigBundle`, `ConfigError`

Required config files:
```text
entry_signal_config.json
exit_policy_config.json
risk_config.json
backtest_config.json
technical_setup_config.json
data_provider_config.json
backtest_ticker_universe_config.json
watchlist_config.json
```

Validation checks include: required files exist, JSON is valid, rule operators are valid, entry labels are valid, horizons are `short_term` / `medium_term`, exit percentages are 0–100, stop/target/ATR/risk numbers have valid bounds, data provider mode exists in `modes` block.

## 4. Rule Engine

File: `src/codex_backed/rules/rule_engine.py`

Class: `RuleEngine`

Supported composition: `all`, `any`, `not`

Supported operators:
```text
>=  <=  >  <  ==  !=  in  not_in  between  exists  missing  contains
```

Output: `RuleEvaluationResult` — `matched`, `reasons`, `missing_fields`, `confidence_penalty`

## 5. Feature Layer

File: `src/codex_backed/features/snapshot.py`

Class: `FeatureSnapshot`

Key field groups:
- identity: `ticker`, `date`, `price`, `horizon`
- technical: `sma50_relative`, `sma200_relative`, `rsi14`, `rsi_slope`, `atr_pct`, `dist_from_52w_high`, `volume_dryup_ratio`, `breakout_volume_multiple`, `trend_label`
- market: `market_regime`, `rs_vs_spy_20d`, `rs_vs_spy_63d`
- fundamentals (FMP): `eps_growth_yoy`, `gross_margin`, `operating_margin`, `net_margin`, `roic`, `roe`, `roa`, `free_cash_flow`, `debt_to_equity`, `current_ratio`, `earnings_days_away`, `earnings_within_30_days`, `ev_to_ebitda`
- fundamentals (yfinance): `forward_pe`, `short_float`, `institutional_ownership`, `analyst_recommendation`, `analyst_target_price`, `market_cap`, `beta`, `sector`, `industry`
- signal-card: `sc_momentum`, `sc_trend`, `sc_entry_timing`, `sc_volume_accumulation`, `sc_volatility_risk`, `sc_relative_strength`, `sc_growth`, `sc_valuation`, `sc_quality`, `sc_ownership`, `sc_catalyst`

File: `src/codex_backed/features/historical_builder.py`

Function: `build_historical_feature_rows`

Builds feature rows directly from OHLCV bar dicts. Computes: SMA20/50/200 and their relatives/slopes, RSI14 and its slope, ATR%, weekly/monthly/quarterly performance, distance from 52-week high/low, volume dry-up ratio, breakout volume multiple, up/down volume ratio, trend label, SPY-relative strength, SPY-derived market regime (from SPY SMA50/SMA200 relationship).

Output cached to `features.pkl` keyed by config hash + provider signature. Invalidated automatically when configs or the data provider change.

## 6. Entry Layer

### Labels

File: `src/codex_backed/entry/labels.py`

```text
NO_TRADE  WATCHLIST  BUY_STARTER  BUY_FULL  BUY_AGGRESSIVE
Actionable: BUY_STARTER  BUY_FULL  BUY_AGGRESSIVE
```

### Setup Detector

File: `src/codex_backed/entry/setup_detector.py`

Class: `EntrySetupDetector`

Detection logic:
1. Evaluate all named signal definitions.
2. Sort setups by priority.
3. Require all required signals.
4. Reject if any blocking signal matches.
5. Require minimum optional signals.
6. Return first matching setup.

Output: `SetupDetectionResult` — `selected_setup`, `matched_signals`, `blocked_signals`, `optional_signals`, `missing_fields`

### Entry Decision Engine

File: `src/codex_backed/entry/engine.py`

Class: `EntryDecisionEngine`

Flow:
```text
FeatureSnapshot
  -> setup detector
  -> enrich snapshot with selected_setup
  -> entry router (priority_first_match rules)
  -> selected entry strategy (quality_dislocation / bull_leadership / etc.)
  -> score rules
  -> penalty rules
  -> decision thresholds
  -> EntryDecision
```

Output: `EntryDecision` — `ticker`, `date`, `horizon`, `entry_label`, `entry_score`, `confidence`, `selected_setup`, `entry_strategy`, `reasons`, `missing_data`, `matched_signals`, `optional_signals`

## 7. Risk Layer

### Position Sizing

File: `src/codex_backed/risk/sizing.py`

Function: `compute_position_size`

Caps applied:
- high ATR cap
- earnings avoid (skip if earnings within N days)
- earnings starter-only (downsize if earnings within M days)

### Stops and Targets

File: `src/codex_backed/risk/stops.py`

Supported initial stop methods: `atr`, `support`, `atr_or_support`

Output: `StopTarget` — `initial_stop`, `target_1`, `risk_per_share`, `initial_risk_pct`

## 8. Simulation Layer

### Entry Execution

File: `src/codex_backed/simulation/entry_simulator.py`

Supported methods: `NEXT_OPEN`, `NEXT_CLOSE`, `PULLBACK_TO_SMA20`, `PULLBACK_TO_SMA50`, `BREAKOUT_CONFIRMATION`

### Trade Simulator

File: `src/codex_backed/simulation/trade_simulator.py`

Bar-by-bar lifecycle:
1. Compute initial stop and target 1.
2. Track MAE and MFE.
3. Stop out if active stop is hit.
4. Take partial profit if target 1 is hit.
5. Move stop to breakeven if configured.
6. Activate/update trailing stop.
7. Exit on time stop if no progress.
8. Exit at max simulation window if no earlier exit fires.

## 9. Data Provider Layer

### HttpClient

File: `src/codex_backed/data/providers/http_client.py`

Thin wrapper around `requests.get`:
- **5xx:** retried with linear backoff (`backoff_seconds * attempt`), up to `max_retries` (default 3)
- **429:** retried with `rate_limit_backoff_seconds` sleep (default 60s) before each retry — handles FMP's 300 req/min limit
- **Other 4xx:** fail immediately, no retry
- API key redacted from all log output and exception messages

### DiskCache

File: `src/codex_backed/data/providers/cache.py`

Per-key JSON cache. Each entry is an envelope: `{schema_version, stored_at, payload}`. Invalidated on schema version mismatch or TTL expiry (default 24h). Atomic writes via tmp-file + rename.

### DailyBudget

File: `src/codex_backed/data/providers/budget.py`

Soft daily call counter, resets at UTC midnight. `on_exceed=warn` logs a warning but does not stop the run. Used to prevent accidental quota exhaustion — does not replace FMP's own server-side rate limiting.

### FMPPriceProvider

File: `src/codex_backed/data/providers/fmp_provider.py`

Calls `/stable/historical-price-eod/full?symbol=&from=&to=&apikey=`. Returns bars in chronological order (FMP delivers newest-first; reversed on parse). Results cached per `(ticker, from, to)` key. 4xx errors never overwrite valid cache entries.

### FMPFundamentalsProvider

File: `src/codex_backed/data/providers/fmp_provider.py`

`prefetch_batch` fetches 5 endpoints per ticker: `/stable/key-metrics`, `/stable/ratios`, `/stable/financial-growth`, `/stable/profile`, `/stable/earnings`. Merges into a single dict and caches per ticker. `get_snapshot` reads exclusively from the in-memory prefetch store — performs no I/O at query time.

`_compute_earnings_days_away` scans the earnings calendar for the next date on or after `as_of_date` and returns the number of days away.

### PickleProvider

File: `src/codex_backed/data/providers/pickle_provider.py`

Loads `prices.pkl` and filters to the requested tickers. Always passes through SPY and QQQ unconditionally (required for regime detection even when they are not in the trading universe).

### CompositePriceProvider

File: `src/codex_backed/data/providers/composite.py`

Tries primary (`FMPPriceProvider`) per-ticker. Falls back to secondary (`PickleProvider`) for tickers that returned no bars. Provenance is tracked per ticker in `last_provenance`. **Important:** only tickers explicitly in the requested list are returned — the pickle's unconditional SPY/QQQ passthrough is not propagated. The runner compensates by always appending SPY and QQQ to the fetch ticker list.

### CompositeFundamentalsProvider

File: `src/codex_backed/data/providers/composite.py`

Routes each `FundamentalsSnapshot` field individually:
1. If field is in `field_overrides` → always use fallback (yfinance)
2. If field not in `primary.capabilities.fundamentals_fields` → use fallback
3. If `as_of_date` before `primary.capabilities.history_start_date` → use fallback
4. If primary value is `None` → use fallback
5. Otherwise use primary value

`field_overrides` for the FMP/yfinance composite: `["insider_ownership", "institutional_ownership", "short_float"]` — FMP Starter does not carry these fields.

### Provider Registry

File: `src/codex_backed/data/providers/registry.py`

`build_providers(config, mode)` constructs the full `ProviderSet` (price_backtest, price_live, fundamentals) from JSON config. Adding a new provider requires one new file in `data/providers/` and one `providers` block entry in `data_provider_config.json`.

### StatsCollector / Observability

File: `src/codex_backed/data/providers/observability.py`

Collects per-provider stats (cache hits/misses, latency, API errors, throttle events) during a single run and writes them to `run_metrics_data_layer.json` in the run directory. **Current limitation:** FMP `DiskCache` reads/writes are not yet instrumented — the FMP entry in `run_metrics_data_layer.json` shows `total=0`.

## 10. Analyze Layer

File: `src/codex_backed/analyze.py`

Class: `AnalyzeOptions`

`run_watchlist_analysis` responsibilities:
- Read `watchlist_config.json`.
- Build providers from active mode in `data_provider_config.json`.
- Fetch fresh OHLCV bars for watchlist + benchmark tickers.
- Prefetch FMP fundamentals for all watchlist tickers.
- Build native feature rows through today.
- Select the latest feature row per ticker/horizon.
- Run `EntryDecisionEngine`.
- Compute position size and stop/target preview.
- Write artifacts.

## 11. Backtest Layer

### Runner

File: `src/codex_backed/backtest/runner.py`

`run_lifecycle_backtest` responsibilities:
- Resolve data mode (CLI `--data-mode` overrides `active_mode` from config).
- Build providers via registry.
- Fetch price bars for all tickers **plus SPY and QQQ** (appended unconditionally for regime detection).
- Prefetch fundamentals for all tickers in the main process (before worker pool starts).
- Build or load cached feature rows.
- Dispatch per-ticker work to serial or parallel workers.
- Merge results and write all artifacts.

### Worker

File: `src/codex_backed/backtest/worker.py`

Per-ticker processing:
```text
for each feature row (date × horizon):
  build FeatureSnapshot (technical + fundamentals)
  run EntryDecisionEngine
  write entry decision record
  if actionable:
    find signal bar index
    simulate entry execution
    compute position size
    simulate trade lifecycle
    write trade record
```

### Metrics

File: `src/codex_backed/backtest/metrics.py`

Per-slice metrics: count, avg/median return, win rate, profit factor, avg MAE/MFE, avg MFE capture, avg days held, partial-profit hit rate, exit reason counts.

## 12. Test Coverage

183 offline tests pass without any network access.

Key test groups:
- Config loading and validation
- Rule engine operators
- Feature snapshot building and native historical builder
- Entry setup detection and entry engine routing
- Entry execution simulation
- Stop/target math and position sizing
- Trade simulator lifecycle (stop, partial profit, breakeven, trailing, time stop)
- Aggregate metrics
- FMP provider (mocked HTTP via `mock_fmp_http()`)
- Composite price and fundamentals routing
- Provider cache (DiskCache TTL, schema version)
- HttpClient retry behavior including 429 backoff
- Backtest runner artifact generation
- E2E FMP mode smoke (mocked HTTP)
- Legacy mode regression (pinned to `data_mode=legacy_yfinance`)
- Runner prefetch sequencing (pinned to `data_mode=legacy_yfinance`)
- S5 watchlist cleanup

Real-key tests (skipped without `FMP_API_KEY`):
- `test_fmp_free_key_smoke.py` — provider-level smoke on AAPL/MSFT (fast, ~5 API calls)
- `test_activation_gates.py` — full S4.3 gate suite (slow, ~15 min, full backtest + live analyze)
- `test_fmp_baseline_capture.py` — S4.2 baseline run + cache validation

Run offline tests:
```bash
codex-backed/.venv/bin/python -m pytest codex-backed/tests -q \
  --ignore=codex-backed/tests/test_activation_gates.py \
  --ignore=codex-backed/tests/test_fmp_baseline_capture.py \
  --ignore=codex-backed/tests/test_fmp_free_key_smoke.py
```

## 13. Known Technical Debt

- FMP cache stats not wired to `StatsCollector` — `run_metrics_data_layer.json` shows zero FMP cache events.
- HTML report is basic — no interactive charts.
- Optimizer commands scaffolded but not implemented.
- Backtest history starts 2018; FMP has data back to 2000 — extending start date is a one-line config change.
- `parent_csv` feature source retained as debug fallback but should eventually be removed.
