# 4 — Backtest Data Gap Audit

Audit date: 2026-06-05.
Scope: all 11 signal cards across the full backtest pipeline
(`data_loader.py` → `snapshot.py` → `signal_card_service.py`).

Baseline: after the improvement-7 fixes (changelog/3_signal_quality_improvement_plan.md)
and the beta + multi-field extraction fix applied 2026-06-05.

---

## Fixes Applied 2026-06-05

`data_loader.py` `_fetch_quarterly_data` now explicitly extracts from `t.info`:

| Key in quarterly dict | yfinance field | Card |
|---|---|---|
| `beta` | `beta` | volatility_risk |
| `roa` | `returnOnAssets` | quality |
| `quick_ratio` | `quickRatio` | quality |
| `long_term_debt_equity` | `longTermDebtEquity` | quality |
| `insider_ownership` | `heldPercentInsiders` | ownership |
| `institutional_ownership` | `heldPercentInstitutions` | ownership |
| `short_float` | `shortPercentOfFloat` | ownership |
| `short_ratio` | `shortRatio` | ownership |
| `analyst_recommendation` | `recommendationMean` | catalyst |
| `analyst_target_price` | `targetMeanPrice` | catalyst |
| `shares_float` | `floatShares` | — |
| `dividend_yield` | `dividendYield` | — |
| `eps_growth_next_year` | `earningsGrowth` | growth |

`snapshot.py` `build_historical_fundamentals` now also computes from quarterly statements:

| Field | Source |
|---|---|
| `revenue_growth_qoq` | (Q0 − Q1) / \|Q1\| from income_stmt |
| `sales_growth_3y` | 3-year revenue CAGR (TTM vs 12Q-back TTM) |
| `eps_growth_3y` | 3-year EPS CAGR (same method) |
| `roa` | net_income_ttm / total_assets (falls back to info `returnOnAssets`) |
| `roic` | NOPAT / invested_capital with implied tax rate from statements |

---

## Still Missing After Fix

### Completely absent (field is always `None`)

| Field | Card | Why |
|---|---|---|
| `fd.sales_growth_ttm` | growth | Not computed. Equivalent to `revenue_growth_yoy`; trivial fix. |
| `fd.eps_growth_5y` | growth | Not in standard yfinance. No source. |
| `fd.eps_growth_next_5y` | growth | Analyst consensus. Not reliably in yfinance `info`. |
| `fd.insider_transactions` | ownership | Requires `t.insider_transactions` DataFrame — separate yfinance call not made. |
| `fd.institutional_transactions` | ownership | Requires a separate API call. Not in `info_snapshot`. |
| `vd.forward_pe` | valuation | Explicitly `None`; `info.get("forwardPE")` available but current-snapshot (look-ahead). |
| `vd.ev_sales` | valuation | Not computed; `info.get("enterpriseToRevenue")` available but current-snapshot. |
| `fd.target_price_distance` | catalyst | `analyst_target_price` stored but % distance vs `price_at_date` never computed. |
| `news.news_score` (real) | catalyst | `neutral_news()` always returns 50.0. No historical news source exists. Catalyst card's news sub-component is permanently flat for all backtest dates. |

### Silent inaccuracies (field populated but wrong for historical dates)

| Field | Card | Problem |
|---|---|---|
| `fd.eps_growth_yoy` | growth | `info.get("earningsGrowth")` — today's trailing EPS growth applied to all 2018–2024 dates. |
| `fd.eps_growth_next_year` | growth | Same field reused as forward estimate. Both directions use today's number. |
| `vd.ev_to_ebitda` | valuation | Today's EV/EBITDA from `info`; applied statically to all historical dates. |
| `vd.peg_ratio` | valuation | Trailing P/E is correctly historical; divided by `info.earningsGrowth` (today's figure). |
| All `info_snapshot` fields (beta, roa, quick_ratio, ownership, short interest, etc.) | various | Current-snapshot values applied statically across 6+ years. Beta and margins drift slowly — acceptable. Short interest and institutional ownership drift more — mild bias. |

### Structural gaps (require a different data source)

| Gap | Affected fields | Impact |
|---|---|---|
| **Sector ETF map only covers ~20 of ~180 tickers** | `rs_vs_sector`, `rs_vs_sector_20d/63d`, `sector_macro_score` | The 160 tickers outside `SECTOR_ETF_MAP` have no sector RS data; `sector_macro_score` is always 50.0 for them. |
| **`obv_trend` / `ad_trend` default to `0` not `None`** | volume_accumulation card | `TechnicalIndicators` uses `int = 0` defaults. Insufficient data scores a "flat" sub-component rather than excluding the weight from `total`. Inflates volume_accumulation scores. |
| **`return_pct_rank_252d` unreliable for early dates** | relative_strength card | Needs 500+ bars. `HISTORY_START = 2016-01-01` gives ~500 bars by 2018-01-01, making this barely available and noisy for early backtest dates. |

---

## Easily Fixable Without New Data (Pending)

All three require only additions to `snapshot.py` — the data is already in scope:

| Fix | Change |
|---|---|
| `fd.sales_growth_ttm = revenue_growth_yoy` | One-liner alias; they measure the same TTM revenue growth. |
| `fd.target_price_distance` | Compute `(static_analyst_target − price_at_date) / price_at_date × 100`. Both values already in scope. |
| `vd.forward_pe` | `info.get("forwardPE")` — same current-snapshot caveat as `ev_to_ebitda` (already applied). |
| `vd.ev_sales` | `info.get("enterpriseToRevenue")` — same current-snapshot caveat. |

---

## Cache Note

Fields added to `data_loader.py` as explicit keys are only present in **newly fetched** cache files.
Old `quarterly.pkl` files do not have these keys.

`snapshot.py` uses a backward-compatible `_qd(key, info_key)` helper that falls back to
`info_snapshot[info_key]` when the explicit key is absent — so old cache files automatically
extract all fields from the existing `info_snapshot` blob without a re-fetch.

The quarterly-derived fields (`revenue_growth_qoq`, `roic`, `roa`, `eps_growth_3y`,
`sales_growth_3y`) are always recomputed from the cached statement DataFrames and are
available immediately without a cache refresh.
