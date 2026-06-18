# Data Provider Refactor — User Stories

Execution-ready breakdown of `DATA_PROVIDER_REFACTOR_PLAN.md` into 22 user stories, sequenced for incremental merging. Each story is sized for a single PR (~0.5 day). A story is **DONE** only when every listed test exists, is exercised by the test suite, and passes.

## Conventions

- **Story ID:** `S<phase>.<seq>` — e.g., `S1.3` = Phase 1, story 3
- **Role:** developer (D), operator (O), maintainer (M)
- **Status:** `[ ]` pending → `[x]` done
- **DoD (Definition of Done):**
  1. Code merged on a feature branch named `refactor/data-provider/<story-id>`
  2. All tests listed under "Tests" exist and pass
  3. Existing test suite remains green
  4. Story-specific docs land with the PR (no doc debt)
- **Dependencies:** each story declares which prior stories must be DONE first
- **No story modifies a config that activates a new mode in production until S4.3.** All wiring up to Phase 4 ships in the dormant `fmp_primary_yfinance_fallback` mode.

---

## Phase 1 — Abstraction without behavior change

**Goal:** all existing functionality routes through the new provider abstraction, but legacy mode is the only active mode. Zero behavior change verifiable via tolerance-based regression.

---

### S1.1 — Provider protocols + capabilities + snapshot dataclass

**Status:** `[x]`

**As a** developer, **I want** typed protocols for `PriceProvider` and `FundamentalsProvider` plus a `ProviderCapabilities` dataclass and a `FundamentalsSnapshot` dataclass, **so that** any concrete provider implementation can be type-checked against a stable contract.

**Files:**
- `codex-backed/src/codex_backed/data/providers/__init__.py` (new)
- `codex-backed/src/codex_backed/data/providers/base.py` (new)
- `codex-backed/src/codex_backed/data/providers/capabilities.py` (new)
- `codex-backed/src/codex_backed/data/fundamentals_snapshot.py` (new)

**Tests:** `codex-backed/tests/test_provider_protocols.py`
- `test_price_provider_protocol_has_required_methods` — protocol declares `fetch_history_batch`, `fetch_live_batch`, `name`, `capabilities`
- `test_fundamentals_provider_protocol_has_required_methods` — protocol declares `prefetch_batch`, `get_snapshot`, `name`, `capabilities`
- `test_capabilities_dataclass_is_frozen` — mutation raises
- `test_capabilities_supports_field_lookup` — helper returns True for declared fields, False otherwise
- `test_fundamentals_snapshot_field_names_match_feature_snapshot_subset` — every fundamental field on `FundamentalsSnapshot` exists on `FeatureSnapshot`
- `test_fundamentals_snapshot_defaults_are_none` — fresh snapshot has all `None` (and `False` for `earnings_within_30_days`)

**Depends on:** none

---

### S1.2 — `PickleProvider` (legacy backtest source as a `PriceProvider`)

**Status:** `[x]`

**As a** developer, **I want** a `PickleProvider` that loads `codex-backed/cache/prices.pkl` and implements `PriceProvider`, **so that** existing backtest cache data is reachable through the new abstraction.

**Files:**
- `codex-backed/src/codex_backed/data/providers/pickle_provider.py` (new)

**Tests:** `codex-backed/tests/test_pickle_provider.py`
- `test_fetch_history_batch_returns_bars_for_known_tickers` — fixture pkl with AAPL/MSFT yields non-empty bar lists
- `test_fetch_history_batch_filters_by_ticker` — only requested tickers returned (SPY/QQQ always passes through)
- `test_fetch_history_batch_filters_by_date_range` — bars outside [start, end] not returned
- `test_fetch_live_batch_raises` — pickle is historical-only; live raises a clear error
- `test_capabilities_declares_no_fundamentals` — `supports_fundamentals` False; `fundamentals_fields` empty
- `test_missing_pickle_raises_data_load_error` — meaningful exception when path doesn't exist

**Depends on:** S1.1

---

### S1.3 — `YFinancePriceProvider` (wraps existing live fetch)

**Status:** `[x]`

**As a** developer, **I want** `YFinancePriceProvider` that wraps today's `fetch_yfinance_bars` and implements `PriceProvider`, **so that** the analyze command's live data path uses the new abstraction.

**Files:**
- `codex-backed/src/codex_backed/data/providers/yfinance_provider.py` (new, prices only — fundamentals in S3.3)

**Tests:** `codex-backed/tests/test_yfinance_price_provider.py`
- `test_fetch_history_batch_calls_yf_download_with_correct_args` — mock `yfinance.download`, assert args
- `test_fetch_history_batch_normalizes_dataframe_to_bar_dicts` — output format matches `bars.normalize_price_frame` contract
- `test_fetch_live_batch_uses_period_and_interval` — period/interval flow through
- `test_capabilities_declares_prices_only` — fundamentals not yet supported in this story
- `test_empty_response_raises_provider_error` — empty data → clear exception
- `test_single_ticker_response_handled` — yfinance single-ticker shape differs from multi-ticker

**Depends on:** S1.1

---

### S1.4 — `NullFundamentalsProvider`

**Status:** `[x]`

**As a** maintainer, **I want** a `NullFundamentalsProvider` that returns all-`None` snapshots, **so that** legacy mode can run through the new pipeline without populating fundamentals.

**Files:**
- `codex-backed/src/codex_backed/data/providers/null_fundamentals.py` (new)

**Tests:** `codex-backed/tests/test_null_fundamentals_provider.py`
- `test_prefetch_batch_is_noop` — no side effects, no exceptions
- `test_get_snapshot_returns_all_none` — every fundamentals field is None / default
- `test_get_snapshot_has_no_io` — assertable via mocking the file/HTTP layer (no calls)
- `test_capabilities_declares_no_fundamentals` — supports_fundamentals False

**Depends on:** S1.1

---

### S1.5 — Provider registry + `data_provider_config.json` (legacy mode only)

**Status:** `[x]`

**As a** developer, **I want** a `registry.build_providers(config, mode)` that returns concrete provider instances based on the active mode, **so that** callers depend only on protocols and config.

**Files:**
- `codex-backed/src/codex_backed/data/providers/registry.py` (new)
- `codex-backed/configs/data_provider_config.json` (new — only `legacy_yfinance` mode defined and active)
- `codex-backed/src/codex_backed/config/loader.py` (extend — validate the new config)

**Tests:** `codex-backed/tests/test_provider_registry.py`
- `test_legacy_yfinance_mode_returns_pickle_for_backtest_prices`
- `test_legacy_yfinance_mode_returns_yfinance_for_live_prices`
- `test_legacy_yfinance_mode_returns_null_for_fundamentals`
- `test_unknown_mode_raises_config_error`
- `test_missing_provider_block_raises_config_error`
- `test_capabilities_loaded_from_config_not_class` — change config tier_capabilities → provider exposes the new capabilities

`codex-backed/tests/test_config_validation.py` additions:
- `test_data_provider_config_valid_legacy_passes`
- `test_data_provider_config_invalid_mode_rejected`
- `test_data_provider_config_missing_tier_capabilities_rejected`

**Depends on:** S1.2, S1.3, S1.4

---

### S1.6 — Wire `runner.py` and `analyze.py` through the registry

**Status:** `[x]`

**As a** developer, **I want** `backtest/runner.py` and `analyze.py` to build providers via the registry instead of directly importing yfinance / loading the pickle, **so that** the engine becomes provider-driven.

**Files:**
- `codex-backed/src/codex_backed/backtest/runner.py` (change — providers built via registry; legacy behavior preserved)
- `codex-backed/src/codex_backed/analyze.py` (change — same)
- `codex-backed/src/codex_backed/cli.py` (change — add `--data-mode` flag, no-op for now but logged)

**Tests:** `codex-backed/tests/test_runner_provider_wiring.py`
- `test_runner_uses_pickle_provider_in_legacy_mode` — patches the registry, asserts the registered provider is invoked
- `test_runner_does_not_construct_providers_in_workers` — assert worker_init does not contain provider instances
- `test_analyze_uses_yfinance_provider_in_legacy_mode` — same approach
- `test_cli_data_mode_flag_recorded_in_run_manifest` — manifest contains effective mode + override origin
- `test_codex_no_overrides_blocks_cli_flag` — env var rejection

**Depends on:** S1.5

---

### S1.7 — Feature cache key extension + writer column pinning

**Status:** `[x]`

**As a** maintainer, **I want** the feature cache key to include `data_mode` + provider signature + schema version, AND `backtest/writer.py` to emit a pinned CSV column order, **so that** mode changes invalidate the cache and CSV consumers see a stable schema.

**Files:**
- `codex-backed/src/codex_backed/features/feature_cache.py` (change — extend metadata + schema_version field)
- `codex-backed/src/codex_backed/backtest/writer.py` (change — explicit `ENTRY_DECISIONS_COLUMNS` and `TRADES_COLUMNS`)

**Tests:** `codex-backed/tests/test_feature_cache_keying.py`
- `test_cache_key_changes_when_data_mode_changes`
- `test_cache_key_changes_when_provider_signature_changes`
- `test_cache_key_changes_when_schema_version_bumps`
- `test_cache_hit_returns_stored_rows_when_keys_match`
- `test_cache_miss_rebuilds_when_any_metadata_key_changes`

`codex-backed/tests/test_writer_column_pinning.py`:
- `test_entry_decisions_csv_columns_in_pinned_order`
- `test_trades_csv_columns_in_pinned_order`
- `test_extra_dict_keys_dropped_silently`
- `test_missing_dict_keys_emit_empty_string`

**Depends on:** S1.6

---

### S1.8 — Phase 1 regression baseline fixture + test

**Status:** `[x]`

**As a** maintainer, **I want** a captured legacy-mode baseline (`legacy_baseline_metrics.json`) and a tolerance-based regression test, **so that** Phase 1 acceptance can be verified by CI and any drift is caught early.

**Files:**
- `codex-backed/tests/fixtures/legacy_baseline_metrics.json` (new — captured from a recorded HEAD run on a small fixed universe)
- `codex-backed/tests/test_legacy_mode_regression.py` (new)
- `codex-backed/tests/fixtures/prices_fixture.pkl` (new — small deterministic price sample, AAPL/MSFT/SPY for 2y)

**Tests:** `codex-backed/tests/test_legacy_mode_regression.py`
- `test_entry_decisions_count_matches_baseline_exactly`
- `test_trades_count_matches_baseline_exactly`
- `test_win_rate_pct_matches_baseline_exactly`
- `test_avg_return_pct_matches_baseline_within_0_0001`
- `test_median_return_pct_matches_baseline_within_0_0001`
- `test_profit_factor_matches_baseline_within_0_0001`
- `test_per_horizon_slice_matches_baseline_within_tolerance`
- `test_feature_row_count_matches_baseline_exactly`

**Depends on:** S1.7

**Phase 1 complete when:** S1.1–S1.8 all `[x]`.

---

## Phase 2 — FMP price provider + infrastructure

**Goal:** FMP can be selected as the price source via config. New mode dormant; legacy still active by default.

---

### S2.1 — HTTP client foundation (retries, timeouts, key redaction)

**Status:** `[x]`

**As a** developer, **I want** an `http_client.py` wrapping `requests` with retries, timeouts, structured errors, and credential redaction, **so that** all paid-API calls share a single hardened entry point.

**Files:**
- `codex-backed/src/codex_backed/data/providers/http_client.py` (new)

**Tests:** `codex-backed/tests/test_http_client.py`
- `test_get_returns_parsed_json_on_200`
- `test_get_retries_on_500_up_to_max_retries`
- `test_get_does_not_retry_on_4xx`
- `test_get_raises_after_max_retries`
- `test_timeout_enforced`
- `test_api_key_redacted_in_log_output`
- `test_api_key_redacted_in_exception_message`

**Depends on:** S1.1

---

### S2.2 — Disk-backed cache with schema versioning and atomic writes

**Status:** `[x]`

**As a** developer, **I want** `cache.py` providing per-key get/set with TTL, `schema_version` check, and atomic write via tmp + rename, **so that** the FMP provider can persist results safely across concurrent reads.

**Files:**
- `codex-backed/src/codex_backed/data/providers/cache.py` (new)

**Tests:** `codex-backed/tests/test_provider_cache.py`
- `test_set_then_get_roundtrip`
- `test_get_returns_none_when_missing`
- `test_get_returns_none_when_ttl_expired`
- `test_get_returns_none_when_schema_version_mismatch`
- `test_atomic_write_uses_rename` — observable by patching `os.rename`
- `test_concurrent_reads_during_write_never_see_partial_data` — write to tmp + rename + read in interleaved threads
- `test_set_writes_payload_with_schema_version_envelope`

**Depends on:** S1.1

---

### S2.3 — Token-bucket rate limiter + daily spend budget

**Status:** `[x]`

**As an** operator, **I want** a token-bucket rate limiter and a daily request budget per provider, **so that** I cannot accidentally exhaust paid API quota.

**Files:**
- `codex-backed/src/codex_backed/data/providers/rate_limiter.py` (new)
- `codex-backed/src/codex_backed/data/providers/budget.py` (new)

**Tests:** `codex-backed/tests/test_rate_limiter.py`
- `test_bucket_allows_burst_up_to_capacity`
- `test_bucket_blocks_when_empty`
- `test_bucket_refills_over_time`
- `test_throttle_event_counted_in_stats`

`codex-backed/tests/test_budget.py`:
- `test_increment_persists_to_disk`
- `test_exceeds_budget_raises_when_action_is_fail`
- `test_exceeds_budget_warns_when_action_is_warn`
- `test_counter_resets_at_utc_midnight`
- `test_disabled_budget_is_unlimited`

**Depends on:** S2.1

---

### S2.4 — FMP price provider (history + live)

**Status:** `[x]`

**As a** developer, **I want** `FMPProvider.fetch_history_batch` and `fetch_live_batch` implemented against FMP REST endpoints, **so that** FMP prices flow into the same pipeline that pickle does today.

**Files:**
- `codex-backed/src/codex_backed/data/providers/fmp_provider.py` (new — prices only; fundamentals in S3.2)
- `codex-backed/tests/fixtures/fmp/historical_aapl.json` (new — recorded response)
- `codex-backed/tests/fixtures/fmp/quote_aapl_msft.json` (new — recorded response)

**Tests:** `codex-backed/tests/test_fmp_price_provider.py`
- `test_fetch_history_batch_parses_recorded_response`
- `test_fetch_history_batch_normalizes_dates_to_iso`
- `test_fetch_history_batch_filters_by_date_range`
- `test_fetch_history_batch_uses_cache_on_second_call`
- `test_fetch_history_batch_skips_tickers_returning_empty`
- `test_fetch_live_batch_parses_quote_endpoint`
- `test_capabilities_match_config_tier_capabilities`
- `test_4xx_error_does_not_corrupt_cache`
- `test_request_counted_against_daily_budget`

**Depends on:** S2.1, S2.2, S2.3

---

### S2.5 — `CompositePriceProvider` with provenance

**Status:** `[x]`

**As a** developer, **I want** a `CompositePriceProvider(primary, fallback)` that records which source served each ticker and never splices bars across sources, **so that** price-source provenance is auditable.

**Files:**
- `codex-backed/src/codex_backed/data/providers/composite.py` (new — price half only; fundamentals in S3.4)

**Tests:** `codex-backed/tests/test_composite_price_provider.py`
- `test_primary_success_serves_all_tickers`
- `test_primary_failure_falls_back_for_all_tickers`
- `test_primary_partial_coverage_falls_back_only_for_missing`
- `test_never_splices_bars_within_single_ticker`
- `test_provenance_records_source_per_ticker`
- `test_stats_increment_on_primary_failure`
- `test_stats_increment_on_fallback_serve`

**Depends on:** S2.4

---

### S2.6 — Observability skeleton (stats collector + JSON summary)

**Status:** `[x]`

**As an** operator, **I want** per-run stats (cache hit rate, error counts, latency p50/p99, throttle events) emitted to `run_metrics_data_layer.json`, **so that** I can detect data-layer regressions without scraping logs.

**Files:**
- `codex-backed/src/codex_backed/data/providers/observability.py` (new — `StatsCollector`, summary emitter)
- `codex-backed/src/codex_backed/backtest/runner.py` (change — emit summary at end of run)
- `codex-backed/src/codex_backed/analyze.py` (change — emit summary at end of run)

**Tests:** `codex-backed/tests/test_observability.py`
- `test_cache_hit_miss_accumulate`
- `test_latency_percentiles_computed_correctly`
- `test_api_error_counted_by_status`
- `test_summary_json_redacts_credentials`
- `test_summary_written_to_run_dir`
- `test_stats_reset_between_runs`

**Depends on:** S2.5

---

### S2.7 — `fmp_primary_yfinance_fallback` mode (dormant)

**Status:** `[x]`

**As a** maintainer, **I want** the new mode added to `data_provider_config.json` and wired through the registry — but NOT activated as default — **so that** Phase 3 work can be exercised end-to-end without affecting production runs.

**Files:**
- `codex-backed/configs/data_provider_config.json` (change — add new mode; `active_mode` stays `legacy_yfinance`)
- `codex-backed/src/codex_backed/data/providers/registry.py` (change — handle composite construction)

**Tests:** `codex-backed/tests/test_provider_registry_fmp_mode.py`
- `test_fmp_mode_returns_composite_price_provider`
- `test_fmp_mode_composite_uses_fmp_primary`
- `test_fmp_mode_composite_uses_yfinance_fallback`
- `test_active_mode_unchanged_after_this_story` — guard: `active_mode == "legacy_yfinance"`

**Depends on:** S2.6

**Phase 2 complete when:** S2.1–S2.7 all `[x]`.

---

## Phase 3 — Fundamentals provider + builder integration

**Goal:** fundamentals data flows into feature rows under the new mode; engine logic in `stock_classification_config.json` and `risk_config.json` actually fires.

---

### S3.1 — Field-alias registry (canonical → vendor-specific names)

**Status:** `[x]`

**As a** maintainer, **I want** a single `field_aliases.py` that maps canonical `FundamentalsSnapshot` field names to vendor-specific JSON keys for each provider, **so that** adding a new provider means editing one file, not N.

**Files:**
- `codex-backed/src/codex_backed/data/providers/field_aliases.py` (new — `FMP_ALIASES`, `YFINANCE_ALIASES`)
- `codex-backed/src/codex_backed/data/providers/alias_apply.py` (new — helper: `apply_aliases(payload, aliases) -> dict`)

**Tests:** `codex-backed/tests/test_field_aliases.py`
- `test_fmp_aliases_cover_all_supported_fields` — every field in `fmp.tier_capabilities.fundamentals_fields` has an alias
- `test_yfinance_aliases_cover_all_supported_fields` — same for yfinance
- `test_apply_aliases_picks_first_present_key`
- `test_apply_aliases_returns_none_when_no_alias_matches`
- `test_aliases_are_immutable`

**Depends on:** S1.1

---

### S3.2 — FMP fundamentals provider (prefetch + snapshot)

**Status:** `[x]`

**As a** developer, **I want** `FMPProvider.prefetch_batch` and `get_snapshot` implemented over `/key-metrics`, `/ratios`, `/income-statement`, `/balance-sheet-statement`, `/cash-flow-statement`, `/earning_calendar`, `/profile`, **so that** FMP fundamentals populate the snapshot fields it sells.

**Files:**
- `codex-backed/src/codex_backed/data/providers/fmp_provider.py` (extend — add fundamentals methods)
- `codex-backed/tests/fixtures/fmp/key_metrics_aapl.json`, `ratios_aapl.json`, `earning_calendar.json`, `profile_aapl.json` (recorded fixtures)

**Tests:** `codex-backed/tests/test_fmp_fundamentals_provider.py`
- `test_prefetch_batch_makes_no_call_for_empty_tickers`
- `test_prefetch_batch_calls_each_endpoint_once_per_ticker`
- `test_get_snapshot_performs_no_io_after_prefetch` — patches http_client; expects zero calls
- `test_get_snapshot_returns_field_values_through_aliases`
- `test_get_snapshot_returns_none_for_fields_not_supported`
- `test_get_snapshot_returns_none_for_dates_before_history_start_date`
- `test_earnings_days_away_computed_correctly_from_calendar`
- `test_prefetch_uses_cache_on_second_call`

**Depends on:** S2.4, S3.1

---

### S3.3 — YFinance fundamentals provider (focus on ownership/short-float)

**Status:** `[x]`

**As a** developer, **I want** `YFinanceProvider.prefetch_batch` + `get_snapshot` that pull from `yfinance.Ticker(...).info` and `.calendar`, **so that** the fields FMP does not sell at our tier (short_float, institutional_ownership, insider_ownership) are populated.

**Files:**
- `codex-backed/src/codex_backed/data/providers/yfinance_provider.py` (extend — add fundamentals methods)
- `codex-backed/tests/fixtures/yfinance/info_aapl.json` (captured `.info` dict)

**Tests:** `codex-backed/tests/test_yfinance_fundamentals_provider.py`
- `test_prefetch_batch_calls_ticker_info_once_per_ticker`
- `test_get_snapshot_returns_short_float_from_info`
- `test_get_snapshot_returns_institutional_ownership_from_info`
- `test_get_snapshot_returns_insider_ownership_from_info`
- `test_missing_info_field_yields_none_not_exception`
- `test_unexpected_info_shape_logged_but_does_not_crash`
- `test_cache_ttl_respected`

**Depends on:** S1.3, S3.1

---

### S3.4 — `CompositeFundamentalsProvider` with field overrides

**Status:** `[x]`

**As a** developer, **I want** `CompositeFundamentalsProvider(primary, fallback, field_overrides)` with explicit "always fall through on None" semantics and lazy fallback prefetch, **so that** the gap fields go to yfinance while paid fields go to FMP without redundant fallback calls.

**Files:**
- `codex-backed/src/codex_backed/data/providers/composite.py` (extend — add fundamentals composite)

**Tests:** `codex-backed/tests/test_composite_fundamentals_provider.py`
- `test_field_override_forces_fallback_even_when_primary_has_value`
- `test_primary_value_used_when_present_and_not_overridden`
- `test_fallback_value_used_when_primary_returns_none`
- `test_fallback_value_used_when_primary_field_not_in_capabilities`
- `test_fallback_value_used_when_date_before_primary_history_start`
- `test_fallback_prefetch_only_called_for_needed_tickers_and_fields`
- `test_get_snapshot_performs_no_io_after_prefetch`
- `test_capabilities_is_union_of_primary_and_fallback`

**Depends on:** S3.2, S3.3

---

### S3.5 — `historical_builder.py` accepts warmed `FundamentalsProvider`

**Status:** `[x]`

**As a** developer, **I want** `build_historical_feature_rows` to accept an already-warmed `FundamentalsProvider` and merge each snapshot into the corresponding feature row, **so that** fundamentals fields on `FeatureSnapshot` populate from real data.

**Files:**
- `codex-backed/src/codex_backed/features/historical_builder.py` (change — add `fundamentals` kwarg)

**Tests:** `codex-backed/tests/test_historical_builder_fundamentals.py`
- `test_builder_without_fundamentals_emits_none_for_fundamental_fields` — legacy parity
- `test_builder_with_fundamentals_merges_snapshot_into_row`
- `test_builder_never_calls_fundamentals_methods_other_than_get_snapshot` — patch and assert
- `test_builder_calls_get_snapshot_once_per_ticker_date`
- `test_unknown_snapshot_field_ignored_not_raises`

**Depends on:** S1.7, S3.4

---

### S3.6 — Runner orchestration: prefetch in main process, assert in worker

**Status:** `[x]`

**As a** maintainer, **I want** `backtest/runner.py` to call `fundamentals.prefetch_batch(...)` in the main process before workers fork, AND `worker_init` to assert no provider is in its config dict, **so that** the process-pool concurrency rule is structurally enforced.

**Files:**
- `codex-backed/src/codex_backed/backtest/runner.py` (change — prefetch sequence)
- `codex-backed/src/codex_backed/backtest/worker.py` (change — assertion in `worker_init`)

**Tests:** `codex-backed/tests/test_runner_prefetch_sequencing.py`
- `test_prefetch_called_before_process_pool_constructed` — patch and verify call order
- `test_prefetch_called_exactly_once_per_run`
- `test_worker_init_asserts_no_provider_runtime_in_config`
- `test_workers_perform_zero_provider_calls` — mock provider, expect 0 calls inside workers

**Depends on:** S2.5, S3.5

---

### S3.7 — End-to-end smoke in `fmp_primary_yfinance_fallback` mode (mocked HTTP)

**Status:** `[x]`

**As a** developer, **I want** an end-to-end test that runs `backtest` and `analyze` in the new mode against fixtures (no real network), **so that** the full data → features → entry → output path is exercised without an API key.

**Files:**
- `codex-backed/tests/test_e2e_fmp_mode_smoke.py` (new)
- `codex-backed/tests/fixtures/fmp/__mocked_session__.py` (test helper that patches `http_client.get`)

**Tests:** `codex-backed/tests/test_e2e_fmp_mode_smoke.py`
- `test_backtest_completes_in_fmp_mode_on_2_tickers`
- `test_backtest_produces_non_zero_actionable_decisions_when_fundamentals_present`
- `test_fundamentals_populated_rate_above_threshold_for_forward_pe`
- `test_analyze_completes_in_fmp_mode_on_2_tickers`
- `test_run_metrics_data_layer_json_emitted_with_expected_fields`

**Depends on:** S3.6

**Phase 3 complete when:** S3.1–S3.7 all `[x]`.

---

## Phase 4 — Activation + baselines

**Goal:** controlled activation of `fmp_primary_yfinance_fallback` with documented audit trail.

---

### S4.1 — Phase 1 regression re-validation under all Phase 2/3 code changes

**Status:** `[x]`

**As a** maintainer, **I want** the Phase 1 legacy-baseline regression (`legacy_baseline_metrics.json`) to still pass after every Phase 2/3 change has landed, **so that** legacy mode is provably untouched.

**Files:**
- (no new files — re-run `tests/test_legacy_mode_regression.py` against current HEAD)

**Tests:** `codex-backed/tests/test_legacy_mode_regression.py` (already exists from S1.8)
- All tests must pass with no fixture update
- If any tolerance is breached, this story is BLOCKED until the offending change is identified and corrected

**Depends on:** S3.7

---

### S4.2 — Real-FMP baseline backtest + capture metrics

**Status:** `[x]`

**As an** operator, **I want** a full backtest in `fmp_primary_yfinance_fallback` mode on the default ticker universe with a real `FMP_API_KEY`, **so that** the new-mode baseline is captured for activation gates.

**Files:**
- `codex-backed/results/fmp_baseline_run/` (output — backtest run artifacts)
- `codex-backed/tests/test_fmp_baseline_capture.py` (new — gated on `FMP_API_KEY` env)

**Tests:** `codex-backed/tests/test_fmp_baseline_capture.py`
- `test_backtest_runs_to_completion_in_fmp_mode_with_real_key` — only runs when key present; otherwise skipped
- `test_run_metrics_data_layer_json_contains_expected_provenance`
- `test_cache_hit_rate_above_95_on_second_consecutive_run` — proves caching works

Manual operator steps (logged in PR description, not automated):
1. Run the backtest with `FMP_API_KEY` set
2. Run a fresh `analyze` invocation; confirm `actionable_count` ≥ 1
3. Diff `run_metrics_data_layer.json` for both modes

**Depends on:** S4.1

---

### S4.3 — Phase 4 activation gates + audit log + mode flip

**Status:** `[ ]`

**As a** maintainer, **I want** every Phase 4 acceptance gate from Section 15 evaluated against captured metrics and recorded in `ITERATIVE_IMPROVEMENTS_FMP_LOG.md`, **so that** the decision to flip `active_mode` is defensible.

**Files:**
- `codex-backed/ITERATIVE_IMPROVEMENTS_FMP_LOG.md` (new — audit log)
- `codex-backed/configs/data_provider_config.json` (change — only if all gates pass: set `active_mode` to `fmp_primary_yfinance_fallback`)

**Tests:** `codex-backed/tests/test_activation_gates.py`
- `test_fundamentals_populated_rate_meets_threshold_for_each_required_field`
- `test_trade_count_delta_within_acceptance_range`
- `test_profit_factor_above_absolute_threshold`
- `test_win_rate_above_absolute_threshold`
- `test_actionable_count_in_live_analyze_at_least_one`
- `test_cache_hit_rate_on_warm_run_above_threshold`
- `test_audit_log_file_exists_and_contains_all_gate_results`

**If any gate fails:** mode stays `legacy_yfinance`, story remains `[ ]`, problem documented in audit log, investigate before reattempting.

**Depends on:** S4.2

**Phase 4 complete when:** S4.1–S4.3 all `[x]`.

---

## Phase 5 — Cleanup and docs

**Goal:** remove transitional shims, consolidate documentation.

---

### S5.1 — Remove legacy yfinance block from `watchlist_config.json` + optional cleanup of `yfinance_live.py`

**Status:** `[x]`

**As a** maintainer, **I want** the `yfinance` block dropped from `watchlist_config.json` and a decision made on `data/yfinance_live.py` (delete or keep as compatibility shim), **so that** the dormant legacy surface area is minimized.

**Files:**
- `codex-backed/configs/watchlist_config.json` (change — remove `yfinance` block)
- `codex-backed/src/codex_backed/data/yfinance_live.py` (delete or keep — documented)

**Tests:** existing `tests/test_legacy_mode_regression.py` and `tests/test_e2e_fmp_mode_smoke.py` must still pass.

- `test_watchlist_config_validation_passes_without_yfinance_block`
- `test_analyze_runs_without_yfinance_block_in_watchlist_config`

**Depends on:** S4.3

---

### S5.2 — Documentation consolidation sweep

**Status:** `[x]`

**As a** maintainer, **I want** `CLAUDE.md`, `HLD.md`, `LLD.md`, and `BACKTEST_README.md` updated to describe the new data-provider architecture, FMP+yfinance composite, and operating procedures (kill switches, audit log), **so that** the canonical references stay current.

**Files:**
- `codex-backed/CLAUDE.md` (change)
- `codex-backed/HLD.md` (change)
- `codex-backed/LLD.md` (change)
- `codex-backed/BACKTEST_README.md` (change)

**Tests:** `codex-backed/tests/test_docs_consistency.py` (new, lightweight)
- `test_claude_md_mentions_data_provider_config_path`
- `test_hld_describes_provider_protocol_layer`
- `test_lld_describes_composite_and_field_overrides`
- `test_backtest_readme_documents_data_mode_cli_flag`

**Depends on:** S5.1

**Phase 5 complete when:** S5.1–S5.2 all `[x]`.

---

## Summary

| Phase | Stories | Working days (estimated) |
|---|---|---|
| Phase 1 | S1.1 – S1.8 | 2 |
| Phase 2 | S2.1 – S2.7 | 3 |
| Phase 3 | S3.1 – S3.7 | 4 |
| Phase 4 | S4.1 – S4.3 | 2 |
| Phase 5 | S5.1 – S5.2 | 1 |
| **Total** | **22 stories** | **~12 days** |

## Tracking

Update each story's checkbox `[ ]` → `[x]` only after:
1. All tests in the story's "Tests" block exist and pass locally
2. Existing suite still green
3. PR merged
4. Story-specific docs landed

When a phase is complete, append a line to the bottom of this file:
> `Phase N complete: <date>, commit <sha>`
