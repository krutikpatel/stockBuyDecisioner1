# Tuning Status (Handoff)

Quick-start doc for the next Claude session to resume iterative fine-tuning without re-deriving context. For deep history see `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`. For per-iteration token-saving conventions (compact metrics helper, silenced status JSON, `Edit` vs `Write` for log appends) see `TOKEN_SAVING_NOTES.md`.

## What We Are Doing

We are iteratively fine-tuning the codex-backed trade lifecycle engine to improve backtest performance under a defined priority order (short-term win rate first; see Priority section below). The engine's behavior is fully controlled by JSON configs in `codex-backed/configs/`, so each iteration changes a config knob, re-runs a full historical backtest over the default ticker universe (199 tickers, 2018-2025), compares the result to the current accepted baseline, and either accepts or rejects the change.

### Steps of Each Iteration

1. **Run the backtest** with the current config and a fresh run-id (`claude_loop_NN`):
   - 8 workers per current user instruction
   - Outputs land in `codex-backed/results/<run-id>/` (CSVs, `metrics.json`, `report.html`)
2. **Investigate the result**:
   - Read `metrics.json`: overall, by_horizon, by_exit_reason
   - Compare to the prior accepted baseline and the iter 1 baseline of this loop
   - Cross-check `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` to confirm the change you are about to suggest has not already been tried and rejected
3. **Decide and log**:
   - Accept the run if higher-priority metrics improved (or stayed flat) and lower-priority metrics did not regress materially
   - Reject if any higher-priority metric regressed
   - Append a `### Claude Iteration N` block to `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` with the Run / Investigation / Improvement Implemented sections
4. **Implement the next change**:
   - Edit the relevant JSON config (typically `exit_policy_config.json`)
   - Run `validate-config` to confirm the edit parses cleanly
   - Trigger the next backtest (iteration N+1)

If a change is rejected, the "Improvement Implemented" of that iteration is the revert plus the next experiment to try. The cycle is self-contained per iteration; there is no global rollback at loop end.

### What We Are Optimizing

Headline backtest metrics, evaluated in priority order (see below). The engine produces per-trade outcomes; the report aggregates them to win rate, avg/median return, and profit factor at the overall, by-horizon, by-setup, by-regime, and by-exit-reason levels. We tune toward the priority order, not toward any single metric.

### What We Are NOT Doing

- Not exploring new entry setups or new market regimes - the trade universe is already pinned to `BROKEN_CHART_QUALITY_RECOVERY` in `BEAR_RISK_OFF` by design.
- Not changing entry decision thresholds for the `quality_dislocation` engine - the prior loop pinned them to exact-score gates (70 and 80) after seeing score 75 and 90+ underperform.
- Not touching the ticker exclusion list (frozen by user instruction).
- Not changing source code unless explicitly required to unlock a knob (e.g. wiring `earnings_days_away` into the historical feature builder is a candidate future code change).
- Not running multi-loop optimization automations - this is sequential single-iteration work with explicit accept/reject reasoning per step.

## Where We Are

**LOOP COMPLETE at iteration 70.** Last accepted run: `claude_loop_64`. All major config knobs have been exhausted.

| metric | value |
|--------|-------|
| trades | 766 |
| overall avg return | 7.503% |
| overall median return | 0.520% |
| overall win rate | 89.295% |
| overall profit factor | 11.162 |
| short-term avg return | 7.286% |
| short-term median return | 3.296% |
| short-term win rate | 84.856% |
| short-term profit factor | 8.474 |
| medium-term avg return | 7.721% |
| medium-term median return | 0.017% |
| medium-term win rate | 93.734% |
| medium-term profit factor | 16.382 |

All 766 trades come from a single setup: `BROKEN_CHART_QUALITY_RECOVERY` in `BEAR_RISK_OFF` regime, routed through `quality_dislocation`. Score buckets 70 (BUY_STARTER) and 80 (BUY_FULL) only.

## Optimization Priority (Do Not Change Without User OK)

1. Short-term win rate
2. Short-term return quality (avg + median)
3. Overall win rate
4. Overall avg return / profit factor

A change is accepted only if it improves a higher-priority metric without harming the priorities above it.

## Current Accepted Config

Lives in `codex-backed/configs/exit_policy_config.json`. Key knobs:

**Short-term:**
- `max_simulation_days`: 60
- `initial_stop`: 2.5 ATR, 1.0% support buffer
- `partial_profit`: enabled, target **0.75R**, sell 20%, BE at **0.75R**
- `trailing_stop`: enabled, **3.0 ATR**, activate after target 1
- `time_stop`: disabled

**Medium-term:**
- `max_simulation_days`: 141
- `initial_stop`: **2.375 ATR**, 2.5% support buffer
- `partial_profit`: enabled, target **0.2R**, sell 1%, BE at **0.2R** (near-pure BE trigger)
- `trailing_stop`: **disabled** (tested at 3.0, 4.0, 5.0 ATR — all rejected)
- `time_stop`: disabled

`risk_config.json` and ticker exclusion list unchanged from prior `loop100_061_w8` baseline.

## Environment Setup

The `codex-backed/.venv` does NOT exist. Use `claude-backend/.venv` via PYTHONPATH:

```bash
PYTHONPATH=codex-backed/src claude-backend/.venv/bin/python -m codex_backed.cli <subcommand> ...
```

Price cache (`codex-backed/cache/prices.pkl`) is rebuilt by `codex-backed/scripts/build_prices_cache.py` if missing. Currently 199 tickers (DFS delisted) + SPY/QQQ, 2017-06-01 → 2026-01-01, ~20MB.

Feature cache (`codex-backed/cache/features.pkl`) auto-rebuilds when feature-relevant config changes. Use `--rebuild-feature-cache` only on the first run after a price cache rebuild.

## Commands

```bash
# Validate after any config change
PYTHONPATH=codex-backed/src claude-backend/.venv/bin/python -m codex_backed.cli \
  validate-config --config-dir codex-backed/configs

# Backtest with 8 workers (user-requested default for this session)
PYTHONPATH=codex-backed/src claude-backend/.venv/bin/python -m codex_backed.cli \
  backtest --config-dir codex-backed/configs --output-dir codex-backed/results \
  --run-id claude_loop_NN --workers 8

# Read metrics (compact, ~6-line summary; see TOKEN_SAVING_NOTES.md)
claude-backend/.venv/bin/python codex-backed/scripts/run_summary.py codex-backed/results/<run-id>
```

## Complete "Things Already Tested" Summary

### From this 70-iteration loop (iters 21-70):

| change | result |
|--------|--------|
| ST `sell_pct` 25 → 20 | **accepted** (+minor WR) |
| MT `target+BE` 1.75R → 1.5R | **accepted** (+4.18 pp MT WR) |
| ST `target+BE` 2.25R → 0.75R (swept) | **accepted** (cumulative +14 pp ST WR) |
| ST `target+BE` 0.75R → 0.5R | rejected (ST PF -0.815) |
| MT `target+BE` 1.5R → 1.25R | **accepted** (+2.09 pp MT WR) |
| ST `breakeven_after` 0.75 → 1.25R (decouple) | no-op (trailing supersedes) |
| MT `breakeven_after` 0.75 → 1.25R (decouple) | no-op (no trailing on MT) |
| MT `sell_pct` 25 → 1% (swept) | **accepted** (+0.186 pp avg per 5pp step, WR flat) |
| MT `target+BE` 1.25R → 0.2R (swept) | **accepted** (cumulative +17.755 pp MT WR) |
| MT `target+BE` 0.15R / 0.1R | rejected (PF cliff) |
| ST `target+BE` 0.5R / 0.625R (at 20% sell) | rejected (avg/median collapse) |
| ST `target+BE` 0.5R (at 1% sell) | rejected (avg collapse) |
| MT `trailing_stop` 5.0 ATR | rejected (avg -3.35 pp, trims winners) |
| ST `initial_stop` ATR 2.5→2.625 | no-op |
| ST `max_simulation_days` 60→45/75 | rejected (both worse, 60 confirmed) |
| MT `max_simulation_days` 141→120/150 | rejected (both worse, 141 confirmed) |
| MT `initial_stop` ATR 2.25→2.375 | **accepted** (+0.261 pp MT WR, +0.652 MT PF) |
| MT `initial_stop` ATR 2.375→2.4375 | no-op |
| MT `support_buffer` 1.5→2.0→2.5% | **accepted** (cumulative +1.567 pp MT WR) |
| MT `support_buffer` 2.5→3.0% | rejected |
| MT `target+BE` 0.25→0.2R | **accepted** (+0.261 pp MT WR) |
| ST `sell_pct` 20→15% | rejected (priority-2 combined metric negative) |
| ST `support_buffer` 1.0→1.5% | rejected (ST WR -0.261 pp) |
| ST `initial_stop` ATR 2.5→2.375 | rejected (ST avg -0.100 pp, PF -0.083) |
| ST `trailing_stop` ATR 3.0→2.75 / 3.5 / 4.0 | rejected (all cut winners) |
| MT `target+BE` 0.2→0.15R | rejected (PF cliff) |
| MT `initial_stop` ATR 2.375→2.5 | rejected (priority-4 regression) |
| ST `breakeven_after` 0.75→0.5R (BE < target) | rejected (ST WR -15.9 pp; disrupts trailing) |
| MT `support_buffer` 2.5→2.75% | rejected (MT PF -0.401, noise-level) |

### From `claude_loop_01` to `claude_loop_10` (prior loop) — see prior TUNING_STATUS.md

### From prior 114-iteration loop — see `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`

## What's Worth Testing Next

All major config knobs within the current architecture are exhausted. Further gains require structural changes:

1. **Wire `earnings_days_away` into the historical feature builder**: Unlocks earnings-risk tuning. Currently a no-op for backtests (live-only). This is a code change to the native feature builder.
2. **New entry setups beyond `BROKEN_CHART_QUALITY_RECOVERY`**: The current universe is intentionally narrow; widening it requires user approval and careful validation.
3. **Expand ticker universe**: Frozen by user instruction; would require explicit re-authorization.
4. **Regime expansion beyond `BEAR_RISK_OFF`**: Adding other regimes would require new signal validation.

## Things Not to Do

- Do not re-introduce medium-term trailing stop at any ATR (3.0, 4.0, 5.0 all tested and rejected).
- Do not widen quality_dislocation BUY_FULL threshold above score 80; scores 90 and 100 are deliberately WATCHLIST per the prior loop.
- Do not expand the ticker exclusion list to chase metrics.
- Do not change `risk_config.json` expecting backtest impact; it only affects live `analyze`.
- Do not pass `--workers > 1` unless the user re-confirms; this session ran 8 successfully but the prior loop warned of sandbox/multiprocessing friction.
- Do not test ST `breakeven_after_r_multiple` below 0.75R — catastrophic ST WR regression.
- Do not test MT `target+BE` at 0.15R or lower — PF cliff.

## How to Resume

The optimization loop is complete. If the user wants to continue:

1. Read this file and the tail of `ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`.
2. Run `validate-config` to confirm config is still valid.
3. Run a baseline backtest (should match loop_64 metrics above).
4. Only pursue structural changes listed in "What's Worth Testing Next" above.
