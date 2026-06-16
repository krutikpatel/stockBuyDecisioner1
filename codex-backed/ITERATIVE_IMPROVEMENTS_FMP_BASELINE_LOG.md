# FMP Baseline Activation Audit Log

Records Phase 4 acceptance gate evaluation for the `fmp_primary_yfinance_fallback` mode.

Per the working contract, `active_mode` in `data_provider_config.json` may only be flipped from
`legacy_yfinance` to `fmp_primary_yfinance_fallback` after ALL gates below are evaluated and pass.

---

## Activation Checklist

| Gate | Threshold | Status | Actual Value | Notes |
|------|-----------|--------|--------------|-------|
| `fundamentals_populated_rate` — `forward_pe` | ≥ 80% post-2020 rows | ⏳ PENDING | — | Requires real FMP_API_KEY |
| `fundamentals_populated_rate` — `earnings_days_away` | ≥ 80% post-2020 rows | ⏳ PENDING | — | Requires real FMP_API_KEY |
| `fundamentals_populated_rate` — `eps_growth_yoy` | ≥ 80% post-2020 rows | ⏳ PENDING | — | Requires real FMP_API_KEY |
| `fundamentals_populated_rate` — `gross_margin` | ≥ 80% post-2020 rows | ⏳ PENDING | — | Requires real FMP_API_KEY |
| `fundamentals_populated_rate` — `short_float` | ≥ 80% post-2020 rows | ⏳ PENDING | — | yfinance fallback field |
| `fundamentals_populated_rate` — `institutional_ownership` | ≥ 80% post-2020 rows | ⏳ PENDING | — | yfinance fallback field |
| `overall.trade_count` delta vs legacy | within −60% to +20% | ⏳ PENDING | — | Requires FMP baseline run |
| `overall.profit_factor` | ≥ 2.0 absolute | ⏳ PENDING | — | Requires FMP baseline run |
| `overall.win_rate_pct` | ≥ 45% absolute | ⏳ PENDING | — | Requires FMP baseline run |
| `actionable_count` from fresh analyze run | ≥ 1 | ⏳ PENDING | — | Manual check with real key |
| `cache_hit_rate` on second consecutive run | ≥ 95% | ⏳ PENDING | — | Automated in test_fmp_baseline_capture.py |

**Decision:** ⏳ PENDING — awaiting operator to run with real FMP_API_KEY.

---

## How to complete this audit

1. Set `FMP_API_KEY` environment variable with a valid FMP Starter (or higher) key.
2. Run:
   ```
   FMP_API_KEY=<key> PYTHONPATH=codex-backed/src backend/.venv/bin/python -m pytest \
     codex-backed/tests/test_fmp_baseline_capture.py \
     codex-backed/tests/test_activation_gates.py \
     -v
   ```
3. Update this file with actual gate values and PASS/FAIL per row.
4. If ALL gates pass: flip `active_mode` to `fmp_primary_yfinance_fallback` in `data_provider_config.json` and mark S4.3 `[x]`.
5. If any gate fails: keep mode as `legacy_yfinance`, document the failure below, investigate, then re-run.

---

## Gate Evaluation History

*(No runs recorded yet — awaiting first run with real FMP_API_KEY)*
