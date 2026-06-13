# Data Provider Refactor Plan

Refactor the codex-backed data layer to a plug-and-play provider abstraction with FMP as the primary source and yfinance as fallback for fields FMP does not carry. Existing yfinance-only behavior remains reachable behind a feature flag.

**Revision 2** — incorporates senior-architect critique: batch fetching, config-declared tier capabilities, explicit composite None semantics, cache schema versioning, process-pool concurrency, observability, kill switches, testable acceptance, revised timeline, CLI audit policy, and a dedicated Backtest Integration section.

---

## 1. Goals

1. **Provider abstraction** — engine code (feature builder, entry engine, risk, exits) reads from a stable interface, not from any specific vendor.
2. **FMP as primary** — paid-tier reliability and breadth for prices, statements, ratios, earnings calendar, and the slice of ownership data FMP exposes.
3. **yfinance as fallback** — fills three structural gaps FMP does not sell at any tier or sells only at Ultimate ($149): `short_float`, `institutional_ownership`, `insider_ownership`. Also covers 2017–2019 fundamentals (FMP Starter only carries 5 years).
4. **Feature flag for legacy behavior** — current yfinance-only path is preserved via a `legacy_yfinance` mode so any new behavior can be A/B-compared and rolled back without code changes.
5. **Plug-and-play** — adding a new provider (Tiingo, Polygon, EODHD later) is a single new file + a config entry, no engine changes.
6. **Separation of concerns** — `data/providers/` knows about vendors; `features/`, `entry/`, `risk/`, `simulation/` know nothing about them.

### Non-goals (explicit)

- Point-in-time historical fundamentals. FMP and yfinance both restate; backtest accepts this bias and documents it.
- Real-time SIP consolidated tape. FMP Starter's real-time is sufficient for daily decisioning.
- Intraday bars. Daily-only stays the supported resolution.
- Schema changes to `FeatureSnapshot` — every field already exists.

---

## 2. Current State Audit

### Data flow today

```
Backtest:
  codex-backed/cache/prices.pkl
    -> data/loader.load_price_bars
       -> features/historical_builder.build_historical_feature_rows  (technicals only)
          -> backtest/worker.process_ticker
             -> entry / risk / exit
             -> writer.csv + json

Analyze (live):
  yfinance.download (period=2y, interval=1d)
    -> data/yfinance_live.fetch_yfinance_bars
       -> features/historical_builder.build_historical_feature_rows  (technicals only)
          -> entry / risk -> writer
```

### Coupling problems

| Concern | Where | Impact |
|---|---|---|
| `prices.pkl` is hardcoded in `backtest_config.json: data_sources.prices_cache_path` | runner.py:48 | Backtest cannot use a non-pickle source without code change |
| `fetch_yfinance_bars` directly imported in `analyze.py:9` | analyze.py | Analyze hardcoded to yfinance |
| `watchlist_config.json` has a vendor-named `yfinance` block | watchlist_config.json | Adding FMP requires renaming or duplicating config schema |
| `historical_builder.py` only computes technicals | historical_builder.py:60–104 | Fundamentals fields on every snapshot are `None` at runtime — entire fundamental-gated logic in `stock_classification_config.json` and `risk_config.json` is dead code |
| `market_and_universe_config.json:87` explicitly declares `supports_point_in_time_fundamentals: false` | configs | Documented limitation, no current code path that would change it |

### What is already abstracted (reuse, don't replace)

- `data/bars.normalize_price_frame` already converts heterogeneous OHLCV frames to the internal `list[dict]` format. New providers should return frames it can consume, or return the normalized form directly.
- `features/feature_cache` already handles cache invalidation by metadata hash. New caches reuse this pattern.
- `ConfigBundle` loads typed configs; we will add one more config file to the bundle.

---

## 3. Target Architecture

```
configs/data_provider_config.json
   |
   v
data/providers/registry.build_providers(config)
   |
   +--> PriceProvider    (CompositePriceProvider)
   |       primary=FMPProvider, fallback=YFinanceProvider
   |       (legacy mode: PickleProvider for backtest, YFinanceProvider for live)
   |
   +--> FundamentalsProvider  (CompositeFundamentalsProvider)
           primary=FMPProvider, fallback=YFinanceProvider
           per-field overrides for short_float / institutional / insider -> always yfinance
           (legacy mode: NullFundamentalsProvider — returns all None, preserving today's behavior)

features/historical_builder.build_historical_feature_rows
   takes optional FundamentalsResolver
   merges fundamentals into each (ticker, date) row before emitting

backtest/runner.run_lifecycle_backtest
   resolves providers via registry, passes to builder

analyze.run_watchlist_analysis
   resolves providers via registry, passes to builder
```

### Module layout

```
codex-backed/src/codex_backed/data/
  bars.py                          (unchanged)
  loader.py                        (kept for backward compat; legacy PickleProvider wraps it)
  yfinance_live.py                 (kept; YFinancePriceProvider delegates to it)
  fundamentals_snapshot.py         (NEW — dataclass for fundamentals fields)
  providers/
    __init__.py
    base.py                        (NEW — Protocols: PriceProvider, FundamentalsProvider)
    yfinance_provider.py           (NEW — implements both protocols against yfinance)
    fmp_provider.py                (NEW — implements both protocols against FMP REST API)
    pickle_provider.py             (NEW — implements PriceProvider over prices.pkl)
    null_fundamentals.py           (NEW — returns all-None snapshots, used in legacy mode)
    composite.py                   (NEW — CompositePriceProvider, CompositeFundamentalsProvider)
    registry.py                    (NEW — config -> concrete provider instances)
    cache.py                       (NEW — disk-backed cache with TTL per provider/endpoint)
    http_client.py                 (NEW — thin requests wrapper with retries + rate-limit handling)
```

### Configuration files

```
codex-backed/configs/
  data_provider_config.json        (NEW — provider modes, credentials reference, cache settings)
  backtest_config.json             (CHANGE — drop prices_cache_path; reference data_provider mode)
  watchlist_config.json            (CHANGE — drop yfinance block; reference data_provider mode)
```

### Engine modules touched

| File | Change |
|---|---|
| `features/historical_builder.py` | Accept optional `FundamentalsResolver`; merge fundamentals into each row before emitting |
| `backtest/runner.py` | Build providers from config; pass resolver into builder; remove direct `prices.pkl` knowledge |
| `analyze.py` | Build providers from config; remove direct `fetch_yfinance_bars` import |
| `cli.py` | Add `--data-mode` flag to override `active_mode` at runtime |
| `config/loader.py` | Add validation for `data_provider_config.json`; relax `backtest_config.data_sources` requirements when not in legacy mode |

### Engine modules NOT touched

- `entry/`, `risk/`, `simulation/`, `backtest/worker.py`, `backtest/writer.py`, `features/snapshot.py`, `features/builder.py`, `features/feature_cache.py` — none of these reference vendors. They consume snapshot dicts and stay vendor-agnostic.

---

## 4. Protocols

Design rules:
1. **Everything is batched.** Single-ticker fetch is a special case of batch — protocols expose batch only to make N+1 patterns structurally impossible. Builder code calls `prefetch_*` once per backtest, then does in-memory lookups.
2. **Capabilities are data, not behavior.** No `supports_field` method on the class. A provider exposes a `capabilities: ProviderCapabilities` attribute that is loaded from the provider's config block at construction time. Upgrading FMP Starter → Premium is a config change.
3. **None means "not known," not "not for sale."** Missing-field distinction is encoded in `capabilities`, not in the return value.

### `data/providers/capabilities.py` (NEW)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderCapabilities:
    """Declarative description of what a provider sells at its configured tier.

    Loaded from configs/data_provider_config.json -> providers.<name>.tier_capabilities.
    Composite logic reads this to decide whether to fall through to a fallback.
    """
    supports_prices: bool
    supports_fundamentals: bool
    fundamentals_fields: frozenset[str]   # canonical FundamentalsSnapshot field names
    history_start_date: str | None        # e.g. "2020-01-01" for FMP Starter; None = unbounded
    price_realtime: bool                  # True if fetch_live returns RT not delayed
    rate_limit_per_minute: int
```

### `data/providers/base.py`

```python
from typing import Protocol, runtime_checkable
from datetime import date
from codex_backed.data.fundamentals_snapshot import FundamentalsSnapshot
from codex_backed.data.providers.capabilities import ProviderCapabilities

@runtime_checkable
class PriceProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    def fetch_history_batch(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[dict]]:
        """Return normalized OHLCV bars per ticker. May skip tickers without data."""

    def fetch_live_batch(
        self,
        tickers: list[str],
        period: str = "2y",
        interval: str = "1d",
    ) -> dict[str, list[dict]]:
        """Return latest bars (including today's partial bar if intraday) per ticker."""


@runtime_checkable
class FundamentalsProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    def prefetch_batch(
        self,
        tickers: list[str],
        date_range: tuple[date, date],
    ) -> None:
        """Warm the in-memory cache. Called ONCE per backtest, before workers fork.

        After this returns, get_snapshot must be O(1) and must not perform I/O.
        Implementations may use cache.py's disk-backed store underneath.
        """

    def get_snapshot(
        self,
        ticker: str,
        as_of_date: date,
    ) -> FundamentalsSnapshot:
        """In-memory snapshot lookup. Must not perform I/O.

        Returns an all-None snapshot if prefetch did not cover this (ticker, date).
        Never raises on missing data.
        """
```

### Why `prefetch_batch` + `get_snapshot` instead of a single fetch

- Backtest = 200 tickers × 8 yr × weekly cadence ≈ 84k (ticker, date) lookups
- Fundamentals change quarterly — there are at most 32 distinct fundamentals records per ticker over 8 yr
- One disk/API call per ticker (32 reports), then 84k in-memory dict lookups — vs. 84k per-row calls in the naive design
- Pre-fetch happens in the **main process** before `ProcessPoolExecutor` forks; workers inherit the warmed in-memory table via `worker_init`
- Eliminates rate-limit fragmentation across workers and cache write races (see Section 16)

### `data/fundamentals_snapshot.py`

Mirror the fundamentals subset of `FeatureSnapshot`:

```python
@dataclass
class FundamentalsSnapshot:
    ticker: str
    as_of_date: str

    # Statements / ratios
    sales_growth_yoy: float | None = None
    sales_growth_qoq: float | None = None
    eps_growth_yoy: float | None = None
    eps_growth_next_year: float | None = None
    eps_growth_3y: float | None = None
    eps_growth_5y: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    free_cash_flow: float | None = None
    roic: float | None = None
    roe: float | None = None
    roa: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None

    # Valuation
    forward_pe: float | None = None
    trailing_pe: float | None = None
    peg_ratio: float | None = None
    price_to_sales: float | None = None
    ev_to_ebitda: float | None = None
    price_to_fcf: float | None = None
    fcf_yield: float | None = None
    ev_sales: float | None = None

    # Earnings calendar / surprise
    beat_rate: float | None = None
    avg_eps_surprise_pct: float | None = None
    earnings_days_away: int | None = None
    earnings_within_30_days: bool = False

    # Ownership / float (likely served only by yfinance fallback)
    insider_ownership: float | None = None
    institutional_ownership: float | None = None
    short_float: float | None = None

    # Misc
    dividend_yield: float | None = None
    market_cap: float | None = None
    beta: float | None = None
    sector: str | None = None
    industry: str | None = None
    analyst_recommendation: float | None = None
    analyst_target_price: float | None = None
```

---

## 5. Composite Provider Semantics

### Decision: always fall through to fallback on None (no `supports_field` shortcut)

The earlier draft tried to distinguish "primary supports this field but data is genuinely missing" from "primary doesn't sell this field." That distinction is brittle (small-cap with no institutional data on FMP looks like "supported but None"). **We drop it.** The new rule:

```
For each field on the merged snapshot:
  1. If explicit field_override points to a named provider → use that provider's value (even if None)
  2. Else if primary returned a non-None value → use it
  3. Else → use fallback's value (even if also None)
```

Capabilities still matter — but only at **prefetch** time:
- If a field is not in `primary.capabilities.fundamentals_fields`, the primary's prefetch skips it entirely (saves API quota)
- Fallback prefetch is only invoked for tickers/fields the primary cannot or did not cover
- If a query date is earlier than `primary.capabilities.history_start_date`, the primary is bypassed for that date — fallback only

### Fundamentals composite

```python
class CompositeFundamentalsProvider:
    name = "composite"
    capabilities: ProviderCapabilities  # union of primary + fallback

    def prefetch_batch(self, tickers, date_range):
        # Phase 1: primary prefetches what it can
        primary_coverage = self._primary.prefetch_batch(tickers, date_range)

        # Phase 2: identify gaps the fallback must fill
        needed_by_fallback = (
            self._explicit_override_tickers          # always-fallback fields
            | self._missing_field_tickers(primary_coverage)
            | self._out_of_range_tickers(date_range, self._primary)
        )
        if needed_by_fallback:
            self._fallback.prefetch_batch(needed_by_fallback, date_range)

    def get_snapshot(self, ticker, as_of_date):
        primary_snap  = self._primary.get_snapshot(ticker, as_of_date)
        fallback_snap = self._fallback.get_snapshot(ticker, as_of_date)

        merged = {}
        for field in FundamentalsSnapshot.field_names():
            forced = self._field_overrides.get(field)
            if forced == self._fallback.name:
                merged[field] = getattr(fallback_snap, field, None)
                continue
            primary_value = getattr(primary_snap, field, None)
            if primary_value is not None:
                merged[field] = primary_value
                continue
            merged[field] = getattr(fallback_snap, field, None)

        return FundamentalsSnapshot(
            ticker=ticker,
            as_of_date=as_of_date.isoformat(),
            **merged,
        )
```

Trade-off accepted: when primary's data is genuinely missing for one field, we will occasionally surface a yfinance value instead of None. Given that all fundamental rules in `stock_classification_config.json` are binary thresholds, this is a smaller risk than silently emitting None when fallback had a usable value.

### Price composite

```python
class CompositePriceProvider:
    name = "composite"

    def fetch_history_batch(self, tickers, start, end):
        try:
            result = self._primary.fetch_history_batch(tickers, start, end)
        except ProviderError as exc:
            self._stats.record_primary_failure(exc)
            result = {}

        missing = [t for t in tickers if t not in result or not result[t]]
        if missing:
            self._stats.record_fallback_invoked(missing)
            fallback_result = self._fallback.fetch_history_batch(missing, start, end)
            result.update(fallback_result)

        # Provenance recorded per ticker for diagnostics (see Section 17)
        self._stats.record_source_per_ticker(result, primary_name=self._primary.name)
        return result
```

**Rule: never splice across sources within a single ticker's bar series.** Different adjustment conventions create discontinuities. A ticker is served by exactly one provider per call.

---

## 6. Config Schema

### `configs/data_provider_config.json` (NEW)

```json
{
  "active_mode": "fmp_primary_yfinance_fallback",
  "modes": {
    "legacy_yfinance": {
      "description": "Preserves current behavior: prices.pkl for backtest, yfinance for analyze, no fundamentals populated.",
      "price_provider_backtest": { "type": "pickle", "config_ref": "pickle" },
      "price_provider_live":     { "type": "yfinance", "config_ref": "yfinance" },
      "fundamentals_provider":   { "type": "null" }
    },
    "fmp_primary_yfinance_fallback": {
      "description": "FMP for prices and fundamentals; yfinance fills ownership/short-float gaps and pre-2020 fundamentals.",
      "price_provider_backtest": {
        "type": "composite",
        "primary":  { "type": "fmp",      "config_ref": "fmp" },
        "fallback": { "type": "yfinance", "config_ref": "yfinance" }
      },
      "price_provider_live": {
        "type": "composite",
        "primary":  { "type": "fmp",      "config_ref": "fmp" },
        "fallback": { "type": "yfinance", "config_ref": "yfinance" }
      },
      "fundamentals_provider": {
        "type": "composite",
        "primary":  { "type": "fmp",      "config_ref": "fmp" },
        "fallback": { "type": "yfinance", "config_ref": "yfinance" },
        "field_overrides": {
          "short_float":             "yfinance",
          "institutional_ownership": "yfinance",
          "insider_ownership":       "yfinance"
        },
        "fmp_fundamentals_min_date": "2020-01-01",
        "note_fmp_fundamentals_min_date": "FMP Starter carries 5 years; before this date, fundamentals come from yfinance fallback."
      }
    }
  },
  "providers": {
    "fmp": {
      "base_url": "https://financialmodelingprep.com/api/v3",
      "api_key_env": "FMP_API_KEY",
      "rate_limit_per_minute": 300,
      "timeout_seconds": 15,
      "max_retries": 3,
      "daily_request_budget": 50000,
      "tier_capabilities": {
        "supports_prices": true,
        "supports_fundamentals": true,
        "fundamentals_fields": [
          "forward_pe", "trailing_pe", "peg_ratio", "price_to_sales",
          "ev_to_ebitda", "ev_sales", "price_to_fcf", "fcf_yield",
          "eps_growth_yoy", "eps_growth_3y", "eps_growth_5y",
          "sales_growth_yoy", "sales_growth_qoq",
          "gross_margin", "operating_margin", "net_margin",
          "roic", "roe", "roa", "debt_to_equity", "current_ratio",
          "free_cash_flow", "dividend_yield", "market_cap", "beta",
          "sector", "industry",
          "beat_rate", "avg_eps_surprise_pct",
          "earnings_days_away", "earnings_within_30_days"
        ],
        "history_start_date": "2020-01-01",
        "price_realtime": true
      }
    },
    "yfinance": {
      "auto_adjust": false,
      "default_period": "2y",
      "default_interval": "1d",
      "daily_request_budget": null,
      "tier_capabilities": {
        "supports_prices": true,
        "supports_fundamentals": true,
        "fundamentals_fields": [
          "forward_pe", "trailing_pe", "peg_ratio",
          "eps_growth_yoy", "sales_growth_yoy",
          "gross_margin", "operating_margin", "net_margin",
          "roe", "roa", "debt_to_equity",
          "free_cash_flow", "dividend_yield", "market_cap", "beta",
          "sector", "industry",
          "short_float", "institutional_ownership", "insider_ownership",
          "earnings_days_away"
        ],
        "history_start_date": null,
        "price_realtime": false
      }
    },
    "pickle": {
      "prices_cache_path": "codex-backed/cache/prices.pkl",
      "tier_capabilities": {
        "supports_prices": true,
        "supports_fundamentals": false,
        "fundamentals_fields": [],
        "history_start_date": null,
        "price_realtime": false
      }
    }
  },
  "cache": {
    "directory": "codex-backed/cache/providers",
    "schema_version": 1,
    "ttl_seconds": {
      "fmp_history":              31536000,
      "fmp_fundamentals":         604800,
      "fmp_earnings_calendar":    86400,
      "yfinance_history":         86400,
      "yfinance_fundamentals":    604800,
      "yfinance_ownership":       604800
    }
  },
  "observability": {
    "enabled": true,
    "emit_summary_json": true,
    "summary_path": "run_metrics_data_layer.json",
    "log_level": "INFO",
    "track": [
      "cache_hit_rate",
      "api_error_rate_per_endpoint",
      "fallback_fire_rate_per_field",
      "request_latency_p50_p99",
      "daily_spend_count",
      "rate_limit_throttle_events"
    ]
  },
  "kill_switches": {
    "force_fallback_env": "CODEX_FORCE_FALLBACK",
    "disable_provider_env": "CODEX_DISABLE_PROVIDER",
    "max_daily_spend_action": "fail"
  }
}
```

### `tier_capabilities` rationale

Pulled out of provider class code. Two consequences:
1. **Upgrading FMP Starter → Premium** is a config edit: add fields to `fundamentals_fields`, push `history_start_date` to `null`. No code change, no redeploy.
2. **A new provider's capability declaration lives next to its credentials**, so the same audit that verifies the API key verifies the capability list. Prevents drift between "what we paid for" and "what the code thinks we have."

### Cache `schema_version`

Every cached payload is wrapped with `{"schema_version": N, "data": ...}`. Reader checks version on load; mismatch invalidates the entry. Bumped whenever `FundamentalsSnapshot` gains fields or the on-disk shape changes. Prevents the silent-stale-cache failure mode.

### Kill switches

- `CODEX_FORCE_FALLBACK=1` (env var) — composite providers skip primary entirely. Used in production to instantly degrade to known-good path when FMP misbehaves. No restart required for new runs.
- `CODEX_DISABLE_PROVIDER=fmp` — registry refuses to instantiate the named provider; mode auto-degrades to fallback-only.
- `daily_request_budget` per provider — counter persisted in `cache/providers/<name>/_budget.json`. Exceeding it raises `BudgetExceededError`. Setting `max_daily_spend_action: "fail"` blocks; `"warn"` continues with logged warnings.

### `configs/backtest_config.json` (CHANGE)

- Remove hardcoded `data_sources.prices_cache_path` requirement when `active_mode != legacy_yfinance`.
- Keep `feature_generation.cache_path` (that's the feature cache, not a data source).
- `data_sources` becomes optional and only consulted in legacy mode.

### `configs/watchlist_config.json` (CHANGE)

- Remove the `yfinance` block.
- New optional block `data_overrides` with `period` and `interval` (vendor-agnostic).
- Provider selection is inherited from `data_provider_config.active_mode`.

### Credentials

- `FMP_API_KEY` lives in env (or `.env` consumed by the CLI). Never written to configs.
- `config/loader.py` reads `api_key_env` from the provider block and resolves at provider construction time. If unset and the mode requires it, raise `ConfigError` with a clear message at startup, not deep in a request.

---

## 7. FMP Provider Implementation Notes

### Endpoints we will use (Starter tier)

| Need | Endpoint |
|---|---|
| EOD historical prices | `/historical-price-full/{ticker}` |
| Real-time / latest quote | `/quote/{ticker}` |
| Income statement | `/income-statement/{ticker}?limit=20` |
| Balance sheet | `/balance-sheet-statement/{ticker}` |
| Cash flow | `/cash-flow-statement/{ticker}` |
| Key metrics (PE, ROE, ROA, etc.) | `/key-metrics/{ticker}` |
| Ratios (margins, current ratio) | `/ratios/{ticker}` |
| Earnings calendar | `/earning_calendar?from=...&to=...` |
| Earnings surprises | `/earnings-surprises/{ticker}` |
| Profile (sector, industry, beta, market cap) | `/profile/{ticker}` |
| Dividend history | `/historical-price-full/stock_dividend/{ticker}` |

### Endpoints we will NOT use (not in tier or not sold)

- Short interest: not in FMP catalog at any tier -> `supports_field("short_float")` returns False.
- Institutional 13F: gated to Ultimate ($149) -> `supports_field("institutional_ownership")` returns False at Starter.
- Insider transactions: Premium-only and partial -> default False at Starter; switch to True if user upgrades.

### Pre-2020 fundamentals gap

`fmp_fundamentals_min_date` in config tells the provider to refuse fundamentals requests before the cutoff. The composite then falls through to yfinance. This is documented; users should not expect FMP-quality fundamentals on 2017–2019 backtest rows.

### Rate limiting

Token-bucket limiter in `http_client.py` honoring `rate_limit_per_minute`. Reads from cache first; only paid calls count against the bucket.

### Caching

- Prices: cache full history per ticker as a parquet/pickle file under `cache/providers/fmp_history/`. Refresh by re-fetching from `last_cached_date + 1` forward (incremental).
- Fundamentals: cache the latest `key-metrics` + `ratios` response per ticker; TTL one week. For "as-of-date" queries, we filter the cached statement list locally by report date.
- Earnings calendar: cache per-ticker upcoming dates with 1-day TTL.

---

## 8. yfinance Provider Implementation Notes

### Reused for fallback

- Wrap existing `fetch_yfinance_bars` for prices (no behavior change).
- Add a new `fetch_snapshot` that pulls `yf.Ticker(ticker).info` + `.calendar` + `.earnings_dates` and normalizes to `FundamentalsSnapshot`.

### Fields yfinance supplies that FMP does not

- `shortPercentOfFloat` -> `short_float`
- `heldPercentInstitutions` -> `institutional_ownership`
- `heldPercentInsiders` -> `insider_ownership`

### Reliability hardening

- All `.info` access wrapped in try/except per field; missing keys -> None.
- Cache per ticker with 7-day TTL (ownership data updates slowly).
- Log when `.info` dict shape changes (key missing that was present last fetch).

---

## 9. Feature Builder Changes

### Pattern: prefetch + in-memory lookup (NOT per-row resolver)

The earlier draft passed a `fundamentals_resolver` callable into the builder. That created an N+1 risk (84k calls per backtest), per-worker cache fragmentation, and rate-limit chaos. **Replaced with a prefetch + lookup pattern.**

### Caller responsibility (runner.py / analyze.py)

```python
# 1. Build providers once
price_provider, fundamentals_provider = registry.build_providers(config)

# 2. Pre-fetch prices for the universe + date range
bars_by_ticker = price_provider.fetch_history_batch(tickers, start, end)

# 3. Pre-fetch fundamentals — populates provider's in-memory table
fundamentals_provider.prefetch_batch(tickers, (start, end))

# 4. Hand the WARMED provider into the builder (no I/O happens after this point)
feature_rows = build_historical_feature_rows(
    bars_by_ticker,
    tickers=tickers,
    options=opts,
    fundamentals=fundamentals_provider,   # warm, ready for get_snapshot()
)
```

### Builder signature

Current:
```python
def build_historical_feature_rows(
    bars_by_ticker, *, tickers, options: HistoricalFeatureOptions
) -> list[dict]:
```

New:
```python
def build_historical_feature_rows(
    bars_by_ticker,
    *,
    tickers,
    options: HistoricalFeatureOptions,
    fundamentals: FundamentalsProvider | None = None,   # MUST be prefetched if non-None
) -> list[dict]:
```

Inside the builder, per (ticker, date) row:
```python
if fundamentals is not None:
    snap = fundamentals.get_snapshot(ticker, date.fromisoformat(date_iso))
    row.update(_fundamentals_snapshot_to_row(snap))
```

`get_snapshot` is a pure in-memory lookup — no I/O, no API calls. The builder's wall-clock complexity stays O(rows) and adds zero network calls relative to today.

### Field-name normalization

A central mapping module `data/providers/field_aliases.py` declares the canonical → vendor-specific aliases:

```python
FMP_ALIASES = {
    "forward_pe":        ["forwardPE", "peRatioForward"],
    "trailing_pe":       ["peRatioTTM", "peRatio"],
    "eps_growth_yoy":    ["epsgrowth"],
    # ...
}

YFINANCE_ALIASES = {
    "forward_pe":              ["forwardPE"],
    "short_float":             ["shortPercentOfFloat"],
    "institutional_ownership": ["heldPercentInstitutions"],
    "insider_ownership":       ["heldPercentInsiders"],
    # ...
}
```

Each provider runs vendor responses through the alias table to populate `FundamentalsSnapshot`. New provider authors edit this one file rather than hand-rolling mappers — keeps the field schema as the single source of truth and makes the test surface for mapping changes one file, not N.

### Legacy mode

When `active_mode == "legacy_yfinance"`, the registry returns `NullFundamentalsProvider` whose `prefetch_batch` is a no-op and `get_snapshot` returns an all-None snapshot. The builder still runs the same code path but emits None for every fundamental field — see Section 15 for the regression-tolerance acceptance criterion that pins this behavior.

---

## 10. CLI Surface

### `--data-mode` flag — kept, but with mandatory audit trail

Decision: **keep the override** for debugging and one-off comparisons, but require it to be reproducible from artifacts alone.

```
--data-mode legacy_yfinance              # force legacy
--data-mode fmp_primary_yfinance_fallback # force new mode
                                          # (omitted: uses active_mode from config)
```

Mandatory behaviors when the flag is used:
1. **The effective mode is written into the run's `metrics.json`** under `data_source.active_mode` and `data_source.mode_override_origin: "cli"`.
2. **A line is appended to `codex-backed/results/<run_id>/run_manifest.json`** recording the user-supplied flag and the resolved mode.
3. **If `CODEX_NO_OVERRIDES=1` is set in the environment, the override is rejected** with a clear error. Production environments set this to enforce config-as-source-of-truth.
4. **Any run with a CLI override is tagged in summary output** so downstream analysis can filter it out from canonical baselines.

Applies to both `backtest` and `analyze` commands.

### `validate-config` extensions

`validate-config` learns about `data_provider_config.json` and verifies:
- `active_mode` exists in `modes`
- Each provider referenced from a mode has a corresponding `providers` block
- Each provider's `tier_capabilities` block is structurally valid
- Required env vars are present (warn, don't fail, on validate; fail only on run)
- Cache `schema_version` is an integer
- Kill-switch env var names don't collide with shell built-ins

---

## 11. Migration Phases

Revised against the earlier-optimistic estimate. Each phase merges independently and leaves the system green. **Docs land with each phase**, not deferred to the end.

### Phase 1 — Abstraction without behavior change (2 days)

- Add `data/providers/base.py`, `capabilities.py`, `pickle_provider.py`, `yfinance_provider.py` (prices first), `null_fundamentals.py`, `registry.py`, `cache.py` (read-only stub).
- Add `field_aliases.py` with the canonical field list.
- Add `data_provider_config.json` with only the `legacy_yfinance` mode defined and active.
- Wire `runner.py` and `analyze.py` through the registry; they get the same `PickleProvider` / `YFinanceProvider` they functionally use today.
- Extend `features/feature_cache.py` metadata to include `data_mode` + provider signature (see Section 16.4).
- Pin CSV column schema in `backtest/writer.py` against current snapshot dataclass (see Section 16.6).
- Acceptance: tolerance-based legacy regression (see Section 15).

### Phase 2 — FMP price provider + cache + observability skeleton (3 days)

- Add `http_client.py` with retries + token-bucket rate limiter + budget guard.
- Add `cache.py` write path with schema versioning and atomic rename.
- Add `fmp_provider.py` prices: `fetch_history_batch`, `fetch_live_batch`.
- Add `CompositePriceProvider` with provenance tracking.
- Add `observability.py` skeleton: stats collector, JSON summary emitter.
- Add `fmp_primary_yfinance_fallback` mode to config but do NOT activate as default.
- Smoke test: `--data-mode fmp_primary_yfinance_fallback --tickers AAPL,MSFT,NVDA` runs end-to-end; cross-check a sample of bars against pickle within tolerance.

### Phase 3 — Fundamentals provider + builder integration (4 days)

- Implement `fmp_provider.prefetch_batch` + `get_snapshot` (statements, ratios, earnings calendar).
- Implement `yfinance_provider.prefetch_batch` + `get_snapshot` (focus on ownership / short-float / earnings dates).
- `CompositeFundamentalsProvider` with field overrides and explicit always-fallback-on-None semantics.
- Extend `historical_builder.py` to accept warmed `fundamentals: FundamentalsProvider`.
- Update `runner.py` to call `fundamentals.prefetch_batch(...)` before forking workers (see Section 16.2).
- Unit tests: composite logic, field override precedence, prefetch sequencing, cache schema version mismatch handling.

### Phase 4 — Activation + baselines (2 days)

- Run legacy-mode regression against the recorded fixture from Phase 1 (must pass tolerance).
- Run full backtest in `fmp_primary_yfinance_fallback` mode on identical universe.
- Capture metric delta in **a new audit log** `codex-backed/ITERATIVE_IMPROVEMENTS_FMP_BASELINE_LOG.md` (do NOT touch `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` — see Section 16.7).
- Apply Phase 4 activation gates from Section 15 (decide flip vs rollback based on documented thresholds).
- Only after gates pass: flip committed `active_mode` to `fmp_primary_yfinance_fallback`.

### Phase 5 — Cleanup and docs sweep (1 day)

- Remove the `yfinance` block from `watchlist_config.json` once `analyze` no longer reads it.
- Delete `data/yfinance_live.py` only after all callers migrated, or keep as thin shim — minor.
- Final pass over `CLAUDE.md`, `HLD.md`, `LLD.md`, `BACKTEST_README.md` to consolidate phase-level docs into the canonical references.

Total: **~12 working days.** Honest planning; not a slip target.

---

## 12. Testing Strategy

### Unit

- `test_pickle_provider.py` — loads existing prices.pkl, returns expected bars.
- `test_yfinance_provider.py` — mocked `yf.Ticker` and `yf.download`; verifies normalization.
- `test_fmp_provider.py` — mocked HTTP responses (saved JSON fixtures from a one-time real call); verifies field mapping.
- `test_composite_fundamentals.py`:
  - Primary returns full snapshot -> primary wins.
  - Primary returns None on a field it supports -> result is None (no fallback).
  - Primary returns None on a field it does NOT support -> fallback consulted.
  - Field override forces fallback even when primary has the field.
  - Fallback never fetched if not needed (assert call count == 0).
- `test_cache.py` — TTL respected, write/read round-trip.
- `test_registry.py` — each mode produces expected provider class hierarchy.

### Integration

- `test_backtest_legacy_mode.py` — running with `legacy_yfinance` produces identical output to a recorded baseline.
- `test_backtest_fmp_mode.py` (gated on `FMP_API_KEY` env) — runs a 2-ticker smoke and asserts non-empty fundamentals.

### Regression

- Compare `results/loop50_49` metrics to a fresh run on the same universe in legacy mode. Must match exactly (no engine change).
- Compare same universe in new mode. Document the delta.

---

## 13. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| FMP returns subtly different OHLCV than yfinance (different dividend adjustment) -> trade decisions shift | Smoke compare 10 tickers × 1yr bars between sources; document the adjustment convention; flip to FMP only after confirmation |
| Rate limit exhaustion during full backtest | Cache aggressively; fundamentals cached per-ticker not per-(ticker, date); rate-limiter blocks rather than drops calls |
| FMP downtime | Composite falls back to yfinance for prices; for fundamentals, stale cache served past TTL with a warning |
| yfinance `.info` schema drift | Per-field try/except; log unknown keys; tests pin the field map |
| Look-ahead bias from restated fundamentals | Documented as known limitation; `fmp_fundamentals_min_date` confines fundamentals to recent history where restatements are smaller; future option: add point-in-time provider (Sharadar, SimFin) without engine changes |
| Backtest output silently changes mid-development | Phase 1 must produce bit-identical results; CI compares to recorded fixture |
| API key in logs | Logger redacts `api_key` query param; tests assert redaction |

---

## 14. Open Decisions for User

1. **Credentials file** — env var only, or also support a `.env` file loaded by the CLI? (Recommend: both, env wins.)
2. **prices.pkl future** — keep as the canonical backtest source even in new mode (faster local iteration, build it from FMP once), or always fetch from FMP at backtest time with disk cache? (Recommend: pickle stays, FMP populates it via a rebuild command.)
3. **CI integration tests** — add a gated job that runs against real FMP with a small ticker list, or keep all integration mocked? (Recommend: mocked; manual smoke before phase 4 activation.)
4. **Pre-2020 backtest fundamentals** — accept yfinance fallback for 2017–2019 (introduces some unreliability), or shorten the backtest start date to 2020-01-01 when fundamentals are enabled? (Recommend: shorten; cleaner story.)
5. **Fundamentals refresh cadence in live `analyze`** — once a day, once a week, on every run? (Recommend: weekly TTL; user can pass `--refresh-fundamentals` to bust the cache.)

---

## 15. Acceptance Criteria

### Phase 1 — Legacy regression (testable, tolerance-based)

The earlier "bit-for-bit identical to `loop50_49`" claim was not testable. Replaced with these gates, run on a fresh `legacy_yfinance` backtest on the **same ticker universe and date range** as a recorded pre-refactor reference run (captured at HEAD before Phase 1 begins):

| Metric | Tolerance | Rationale |
|---|---|---|
| `entry_decisions.count` | exact match | Decisions are deterministic given identical features |
| `trades.count` | exact match | Trade simulation is deterministic |
| `overall.avg_return_pct` | ±0.0001 | Floating-point reordering only |
| `overall.median_return_pct` | ±0.0001 | Same |
| `overall.win_rate_pct` | exact match | Discrete count ratio |
| `overall.profit_factor` | ±0.0001 | Floating-point reordering only |
| `by_horizon.*` slice metrics | same tolerances | Per-slice parity |
| Feature row count after cache rebuild | exact match | Cache key change must not silently invalidate |

Reference run is captured once before Phase 1 lands and stored under `codex-backed/tests/fixtures/legacy_baseline_metrics.json`. CI runs Phase 1 acceptance against this fixture.

### Phase 4 — New-mode activation gates

Running `--data-mode fmp_primary_yfinance_fallback` on the same universe must satisfy ALL of:

| Gate | Threshold | Action on failure |
|---|---|---|
| `fundamentals_populated_rate` for `forward_pe`, `earnings_days_away`, `eps_growth_yoy`, `gross_margin`, `short_float`, `institutional_ownership` | ≥80% on post-2020 rows for default watchlist | Investigate provider coverage before flipping `active_mode` |
| `overall.trade_count` delta vs legacy | within −60% to +20% | If outside, fundamentals filters may be misconfigured or over-aggressive — review before flipping |
| `overall.profit_factor` | ≥2.0 absolute (not relative) | If lower, fundamentals gates may be filtering out winners — review before flipping |
| `overall.win_rate_pct` | ≥45% absolute | Same logic |
| `actionable_count` from a fresh `analyze` run on the default watchlist | ≥1 | If zero, live analyze is unusable in new mode — rollback |
| `cache_hit_rate` (Section 17) on a second consecutive backtest run | ≥95% | Sanity-check that caching is working before declaring activation |

All gate values are written to `ITERATIVE_IMPROVEMENTS_FMP_BASELINE_LOG.md` as the audit trail (Section 16.7).

### Structural / operational

- `validate-config` passes for both modes.
- All existing tests pass without modification (Phase 1 acceptance enforces this).
- Adding a new provider (e.g., Tiingo) requires only: one new file in `data/providers/`, one entry in `providers` config (including `tier_capabilities`), and a one-line entry under any mode that wants to use it. No engine changes. No `historical_builder.py` change. No worker change.
- Tier upgrade (FMP Starter → Premium) is a config change to `tier_capabilities`. No code change.
- `CODEX_FORCE_FALLBACK=1` in env causes the next `backtest` or `analyze` invocation to skip primary entirely, verified by an integration test.

---

## 16. Backtest Integration

The data refactor is the easy half. The backtest is where the integration risk lives. This section is mandatory reading for anyone touching `backtest/runner.py`, `backtest/worker.py`, `backtest/writer.py`, or `features/feature_cache.py`.

### 16.1 Process-pool lifecycle — Option A is mandatory

**Rule:** providers are constructed exactly once, in the main process, before `ProcessPoolExecutor` is created. Workers never construct providers. Workers never make API calls. Workers never touch the cache directory.

```
Main process:
  build_providers(config)
  price_provider.fetch_history_batch(tickers, start, end)         (one call)
  fundamentals_provider.prefetch_batch(tickers, (start, end))     (one batch)
  build feature rows (with fundamentals already in-memory)
  fork ProcessPoolExecutor with worker_init(bundle.data)          (no providers passed)

Worker processes:
  receive pre-built feature rows + pre-built bars in work_items
  run entry / risk / exit / simulation
  return decisions + trades
  exit
```

Why:
- Rate-limit budget stays whole (300/min total, not 38/min × 8 workers)
- Cache is written once by the main process; no concurrent-write races, no file locks needed
- Credentials never cross the fork boundary
- Workers stay pure-CPU, matching today's model

### 16.2 Runner orchestration changes (`backtest/runner.py`)

Today the runner does: `load_price_bars` → `_load_or_build_features` → fan-out. Becomes:

```python
def run_lifecycle_backtest(bundle, paths, options):
    backtest_cfg = bundle.get("backtest")
    provider_cfg = bundle.get("data_provider")               # NEW config bundle entry

    # NEW: providers built from config (or CLI override)
    active_mode = options.data_mode or provider_cfg["active_mode"]
    price_provider, fundamentals_provider = registry.build_providers(
        provider_cfg, mode=active_mode
    )

    # NEW: explicit two-phase prefetch in MAIN process
    bars_by_ticker = price_provider.fetch_history_batch(tickers, start_date, end_date)
    fundamentals_provider.prefetch_batch(tickers, (start_date, end_date))

    # Existing code path — builder uses warmed fundamentals
    feature_rows, diagnostics = _load_or_build_features(
        bundle=bundle,
        backtest_cfg=backtest_cfg,
        bars_by_ticker=bars_by_ticker,
        tickers=tickers,
        ...
        fundamentals=fundamentals_provider,                  # NEW kwarg
        data_mode=active_mode,                               # NEW for cache key
    )

    # Fan-out is unchanged
    ...
```

### 16.3 Worker doesn't see providers — hard rule

`backtest/worker.py::worker_init` and `process_ticker` already receive a pre-built `bundle.data` config dict and pre-built `feature_rows`. **No change.** The rule is asserted in code:

```python
def worker_init(config_data):
    assert "data_provider_runtime" not in config_data, (
        "Providers must not be passed to workers. "
        "Prefetch in the main process; pass feature rows."
    )
    ...
```

This assertion catches the failure mode where someone naively tries to pass a provider instance through `work_items`. Caught at fork time, not at runtime in a worker.

### 16.4 Feature cache key extension

`features/feature_cache.py` keys on a metadata-hash. Today's metadata includes `technical_setup_config`, `entry_config`, ticker list, horizons. **Must be extended with provider identity** or it will serve stale all-None caches when modes switch.

```python
metadata = {
    "source": "native",
    "tickers": requested_tickers,
    "start": start,
    "end": end,
    "horizons": sorted(horizons),
    "signal_frequency": signal_frequency,
    "technical_setup_config": bundle.get("technical_setup"),
    "entry_config": bundle.get("entry"),

    # NEW — invalidates cache when data layer changes
    "data_mode": active_mode,
    "fundamentals_provider_signature": fundamentals_provider.signature(),
    "field_overrides_signature": _hash_overrides(provider_cfg),
    "fundamentals_snapshot_schema_version": FUNDAMENTALS_SNAPSHOT_SCHEMA_VERSION,
}
```

`provider.signature()` is a stable string like `composite:fmp+yfinance@tier_cap_hash=abc123`. Changing modes, tier capabilities, or field overrides all invalidate the feature cache automatically.

### 16.5 Decision-time vs execution-time fundamentals

Decision: **fundamentals are frozen at decision time** (the date when entry signals are computed), not refreshed at execution time (next-open, pullback day, etc.).

Why:
- Simpler — one snapshot per (ticker, decision_date) row, no per-execution refresh
- Matches today's behavior — setups today read the snapshot once
- Matches the prefetch model — workers never call providers, so they can't refresh anyway
- For earnings cap specifically (`earnings_days_away`), the freeze is conservative: an entry approved 5 days before earnings still respects the original cap even if the execution drifts toward earnings

If we ever need refresh-at-execution semantics (e.g., for trailing earnings-window protections), it's an additive feature that doesn't break this design.

### 16.6 Writer column schema pinning (`backtest/writer.py`)

Today the CSV writer uses `csv.DictWriter` over list-of-dict rows. Column set is implicit. With fundamentals populating, this drifts silently. Mitigation:

- Define `ENTRY_DECISIONS_COLUMNS` and `TRADES_COLUMNS` as explicit ordered tuples in `writer.py`
- `write_csv(path, rows, columns=EXPLICIT_COLUMN_LIST)` — extra dict keys ignored, missing keys default to None
- Test pins the column list so adding a snapshot field requires an intentional writer update

This is decoupled from the data refactor but blocks Phase 1 acceptance because column drift would break tolerance comparisons.

### 16.7 Phase 4 audit log

Per CLAUDE.md: do NOT overwrite `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`. Phase 4 produces a new file:

`codex-backed/ITERATIVE_IMPROVEMENTS_FMP_BASELINE_LOG.md`

Contents:
1. Date of activation, git SHA, FMP tier and capabilities snapshot
2. Legacy-mode metrics on the same universe (proof of regression-clean baseline)
3. FMP-mode metrics on the same universe
4. Per-gate result (from Section 15 Phase 4 table) with PASS / FAIL
5. Decision: flipped `active_mode` / rolled back / parked for revisit
6. Free-text notes on which fundamentals rules actually fired and which still need data

This file becomes the new baseline anchor — future tuning iterations append below it without overwriting.

---

## 17. Observability

A paid API without observability is a slow leak. Everything below is built in Phase 2 alongside the FMP price provider, not deferred.

### 17.1 Metrics emitted per backtest / analyze run

Written to `<run_dir>/run_metrics_data_layer.json`:

```json
{
  "active_mode": "fmp_primary_yfinance_fallback",
  "mode_override_origin": "config",
  "providers": {
    "fmp": {
      "requests_made": 1247,
      "cache_hits": 18933,
      "cache_misses": 1247,
      "cache_hit_rate": 0.9382,
      "api_errors_by_status": {"429": 3, "500": 0, "503": 1},
      "rate_limit_throttle_events": 4,
      "latency_p50_ms": 142,
      "latency_p99_ms": 880,
      "daily_spend_count": 1247,
      "daily_budget_remaining": 48753
    },
    "yfinance": {
      "requests_made": 78,
      "cache_hits": 502,
      "cache_misses": 78,
      "cache_hit_rate": 0.8655,
      "api_errors_by_status": {"throttled": 0},
      "latency_p50_ms": 320,
      "latency_p99_ms": 1100
    }
  },
  "composite": {
    "price_primary_serve_count": 198,
    "price_fallback_serve_count": 3,
    "fundamentals_fallback_fire_rate_by_field": {
      "short_float": 1.00,
      "institutional_ownership": 1.00,
      "insider_ownership": 1.00,
      "forward_pe": 0.04,
      "earnings_days_away": 0.07,
      "eps_growth_yoy": 0.12
    }
  }
}
```

### 17.2 Why each metric matters

| Metric | Why it matters |
|---|---|
| `cache_hit_rate` | A backtest re-run that drops below ~95% means the cache invalidation rule (Section 16.4) misfired or TTL is too short. Direct cost signal. |
| `api_errors_by_status` | 429 rate-limit hits = need more caching or batch consolidation. 5xx storms = consider `CODEX_FORCE_FALLBACK`. |
| `fallback_fire_rate_by_field` | If `forward_pe` fires fallback more than ~10% of the time, FMP is degrading or the alias mapping is wrong. Detects silent data-quality regression. |
| `rate_limit_throttle_events` | Bucket pauses indicate the rate limiter is doing its job. Spikes mean rebalance prefetch or upgrade tier. |
| `latency_p99` | Catches FMP slow days that don't show as errors but bloat backtest wall time. |
| `daily_budget_remaining` | Tracks toward the kill switch; if you see 0 unexpectedly, something's looping. |

### 17.3 Log channels (not just JSON)

- Structured INFO logs at provider construction (mode, providers, capabilities summary)
- INFO log at end of prefetch with row counts per ticker
- WARN log every time fallback serves a price ticker (provenance recorded)
- WARN log on cache schema version mismatch (entry discarded + reason)
- ERROR log on `BudgetExceededError` and `RateLimitTimeoutError`
- Sensitive fields (API key in query params) are redacted in all logs and JSON output

### 17.4 No external system required

Phase 2 ships file-based observability only. Prometheus / OpenTelemetry / metrics push are explicit non-goals — easy to add later given the stats collector is already centralized.

---

## 18. Out of Scope (for this refactor)

- Replacing the `prices.pkl` cache format (parquet/sqlite migration).
- Real-time intraday data feed.
- True point-in-time fundamentals provider (Sharadar, SimFin) — design leaves room to add later without further engine changes.
- Multi-currency / international tickers — current scope is US equities, same as today.
- News, sentiment, alternative data — not on the roadmap.
