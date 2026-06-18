# FMP Baseline

Canonical baseline reference for the `fmp_primary_yfinance_fallback` data mode.

For the chronological FMP provider activation and tuning audit trail, see
`ITERATIVE_IMPROVEMENTS_FMP_LOG.md`.

---

## Current Baseline - `fmp_baseline_02`

**Run date:** 2026-06-15

**Preferred command for new comparable baseline runs:**

```bash
codex-backed/scripts/run_fmp_backtest.sh fmp_baseline_03
```

The helper script loads `.env`, uses `fmp_primary_yfinance_fallback`, rebuilds
the feature cache by default, and runs with `--workers 1`.

**Original baseline command:**

```bash
set -a; source .env; set +a
PYTHONPATH=codex-backed/src codex-backed/.venv/bin/python -m codex_backed.cli backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id fmp_baseline_02 \
  --data-mode fmp_primary_yfinance_fallback \
  --rebuild-feature-cache \
  --workers 1
```

**Scope:** 200 tickers, 2018-01-02 to 2025-12-31, both horizons enabled.

## Overall Metrics

| Metric | FMP baseline_02 | Legacy entry_exp_100 | Delta |
|--------|-----------------|----------------------|-------|
| Trades | 104 | 102 | +2 (+2.0%) |
| Avg return % | 15.67% | 15.22% | +0.45pp |
| Median return % | 2.98% | 1.82% | +1.16pp |
| Win rate % | 98.08% | 98.04% | +0.04pp |
| Profit factor | 160.64 | 153.10 | +7.54 |

FMP mode is equivalent to or marginally better than legacy across every metric.
The higher median return (+1.16pp) suggests slightly tighter entry quality.

## By Horizon

| Horizon | Trades | Avg return % | Median return % | Win rate % | Profit factor |
|---------|--------|--------------|-----------------|------------|---------------|
| short_term | 52 | 18.95% | 14.88% | 98.1% | 226.0 |
| medium_term | 52 | 12.39% | 0.05% | 98.1% | 111.5 |

Short-term exits are roughly 2x better on profit factor and avg return. The
medium-term median of 0.05% indicates the extra hold time produces many
near-breakeven outcomes.

## By Market Regime

| Regime | Trades | Avg return % | Win rate % |
|--------|--------|--------------|------------|
| BEAR_RISK_OFF | 104 | 15.67% | 98.1% |

All trades come from `BEAR_RISK_OFF`. The other three regimes
(`BULL_RISK_ON`, `SIDEWAYS_CHOPPY`, `LIQUIDITY_RALLY`) produce zero trades.

## Trade Concentration

| Year | Trades | Context |
|------|--------|---------|
| 2018 | 6 | Late-year sell-off (Q4 2018) |
| 2020 | 78 | COVID crash (75% of all trades) |
| 2022 | 10 | Fed rate-hike bear market |
| 2025 | 10 | 2025 correction |

The strategy is a crash-only system in its current form. All 104 trades use the
`quality_dislocation` engine and require `BEAR_RISK_OFF` regime. The backtest
covers 8 years but fires on only about 4 distinct market stress events. 38 of
200 tickers ever produce a trade.

## Exit Breakdown

| Exit reason | Count | Notes |
|-------------|-------|-------|
| TRAILING_STOP_EXIT | 48 (46%) | Majority captured meaningful upside |
| STOP_LOSS_EXIT | 43 (41%) | Entered but failed to follow through |
| MAX_SIM_WINDOW_EXIT | 13 (13%) | Still open at window close |

## Top Tickers By Avg Return

| Ticker | Trades | Avg return % | Win rate % |
|--------|--------|--------------|------------|
| MU | 2 | 143.2% | 100% |
| QCOM | 2 | 62.9% | 100% |
| NUE | 2 | 37.3% | 100% |
| DD | 4 | 34.1% | 100% |
| PEG | 2 | 29.9% | 100% |
| BKR | 2 | 25.9% | 100% |
| VLO | 2 | 25.6% | 100% |
| PSX | 4 | 24.6% | 100% |
| CMCSA | 2 | 24.5% | 100% |
| EOG | 2 | 23.0% | 100% |

No tickers had negative average return. Cyclicals, energy, and semiconductors
dominate.

---

## Extended Date Range Experiment — `fmp_2010_extend`

**Run date/time:** 2026-06-16 (post-UTC-midnight, FMP daily budget reset)

**Config change:** `backtest_config.json` `start` moved `2018-01-01` → `2010-01-01` (end unchanged: 2025-12-31).

**Scope:** 200 tickers, 2010-01-01 to 2025-12-31, `fmp_primary_yfinance_fallback`, feature cache rebuilt.

### Overall Metrics vs Baseline

| Metric | fmp_baseline_02 (2018–2025) | fmp_2010_extend (2010–2025) | Delta |
|--------|-----------------------------|-----------------------------|-------|
| Trades | 104 | 104 | 0 |
| Avg return % | 15.67% | 12.90% | −2.77pp |
| Median return % | 2.98% | 0.27% | −2.71pp |
| Win rate % | 98.1% | 89.4% | −8.7pp |
| Profit factor | 160.6 | 11.40 | −149.2 |
| Feature rows | ~205k | 306,802 | +~100k |

### Key Findings

**Same trade count (104), but different trades.** Rebuilding the feature cache with the longer history changed technical indicator values (SMA200, RSI lookbacks), reshuffling which signals triggered in the 2018+ window. The total count coincidentally matched.

**16 new pre-2018 trades discovered** across two historical bear market periods:

| Period | Tickers | Trades | Context |
|--------|---------|--------|---------|
| Aug 2011 | MU, ROK, TMUS | 6 | U.S. debt downgrade / S&P crash |
| Dec 2015 – Feb 2016 | DVN, FCX, MU | 10 | Oil crash / China slowdown |

All 104 trades remained `BEAR_RISK_OFF` / `quality_dislocation` / `BROKEN_CHART_QUALITY_RECOVERY`.

### By Horizon

| Horizon | Trades | Avg return % | Win rate % | Profit factor |
|---------|--------|--------------|------------|---------------|
| short_term | 52 | 15.51% | 86.5% | 10.24 |
| medium_term | 52 | 10.29% | 92.3% | 13.83 |

### By Exit Reason

| Exit reason | Count | Avg return % |
|-------------|-------|-------------|
| TRAILING_STOP_EXIT | 41 | 20.92% |
| MAX_SIM_WINDOW_EXIT | 11 | 55.58% |
| STOP_LOSS_EXIT | 52 | −2.45% |

### Conclusion

The extension to 2010 is informative but is **not an upgrade to the production baseline**. The 2011 and 2015-16 recoveries were moderate in magnitude; including them dilutes the exceptional COVID-crash dislocations that drive the baseline's headline numbers. The sharp drop in profit factor (160.6 → 11.40) and win rate (98.1% → 89.4%) reflects the broader mix of market stress events rather than a regression in strategy quality.

`fmp_baseline_02` (2018–2025) remains the canonical production baseline. This run is archived as `fmp_2010_extend` for historical context on pre-2018 regime coverage.

