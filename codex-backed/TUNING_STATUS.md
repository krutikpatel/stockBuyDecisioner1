# Tuning Status (Handoff)

Quick-start doc for the next Claude session to resume iterative fine-tuning without re-deriving context. For deep history see `docs/pre-refactoring-iterative-fine-tuning-logs/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`. For per-iteration token-saving conventions (compact metrics helper, silenced status JSON, `Edit` vs `Write` for log appends) see `TOKEN_SAVING_NOTES.md`.

## Scope: What Has Been Tuned So Far

| Config | Status |
|--------|--------|
| `exit_policy_config.json` | ✅ Fully optimized (70 iterations) |
| `entry_signal_config.json` | ✅ Optimized (entry loop iters 71-80) |
| `technical_setup_config.json` | ✅ Optimized (iter 79-80, RSI oversold bound) |
| `risk_config.json` | ❌ Not tuned (also no-op in backtests; live `analyze` only) |
| `backtest_ticker_universe_config.json` | ❌ Not tuned — frozen by user instruction |

The entry universe remains: `BROKEN_CHART_QUALITY_RECOVERY` in `BEAR_RISK_OFF`, score buckets 70 and 80. The entry optimization loop (iters 71-80) improved the QUALITY FILTER for what qualifies as a trade: deeper dislocation (-30% from 52w high, up from -20%) and tighter RSI oversold bound (≤40, down from ≤42).

---

## What We Are Doing

We are iteratively fine-tuning the codex-backed trade lifecycle engine to improve backtest performance under a defined priority order (short-term win rate first; see Priority section below). The engine's behavior is fully controlled by JSON configs in `codex-backed/configs/`, so each iteration changes a config knob, re-runs a full historical backtest over the default ticker universe (199 tickers, 2018-2025), compares the result to the current accepted baseline, and either accepts or rejects the change.

### Steps of Each Iteration

1. **Run the backtest** with the current config and a fresh run-id (`claude_loop_NN`):
   - 8 workers per current user instruction
   - Outputs land in `codex-backed/results/<run-id>/` (CSVs, `metrics.json`, `report.html`)
2. **Investigate the result**:
   - Read `metrics.json`: overall, by_horizon, by_exit_reason
   - Compare to the prior accepted baseline and the iter 1 baseline of this loop
   - Cross-check `docs/pre-refactoring-iterative-fine-tuning-logs/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` to confirm the change you are about to suggest has not already been tried and rejected
3. **Decide and log**:
   - Accept the run if higher-priority metrics improved (or stayed flat) and lower-priority metrics did not regress materially
   - Reject if any higher-priority metric regressed
   - Append a `### Claude Iteration N` block to `docs/pre-refactoring-iterative-fine-tuning-logs/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` with the Run / Investigation / Improvement Implemented sections
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

**EXIT RE-VALIDATION LOOP COMPLETE at iteration 100.** All 10 iterations (91-100) re-tested exit_policy_config.json knobs against the 102-trade universe — every knob confirmed at the same optimum as the 766-trade universe. Best run unchanged: `entry_exp_83`.

| metric | exit-tuned baseline | entry_exp_80 (loop 1) | **current (entry_exp_83)** |
|--------|---------------------|----------------------|---------------------------|
| trades | 766 | 266 | **102** |
| overall avg return | 7.503% | 10.371% | **15.097%** |
| overall median return | 0.520% | 0.660% | **2.393%** |
| overall win rate | 89.295% | 92.481% | **98.039%** |
| overall profit factor | 11.162 | 22.584 | **151.846** |
| short-term avg return | 7.286% | 10.171% | **17.566%** |
| short-term median return | 3.296% | 5.458% | **11.989%** |
| short-term win rate | 84.856% | 89.474% | **98.039%** |
| short-term profit factor | 8.474 | 17.261 | **205.533** |
| medium-term avg return | 7.721% | 10.572% | **12.629%** |
| medium-term median return | 0.017% | 0.022% | **0.053%** |
| medium-term win rate | 93.734% | 95.489% | **98.039%** |
| medium-term profit factor | 16.382 | 32.505 | **111.502** |

All 102 trades come from `BROKEN_CHART_QUALITY_RECOVERY` in `BEAR_RISK_OFF` regime, routed through `quality_dislocation`. Score buckets 70 (BUY_STARTER) and 80 (BUY_FULL) only.

## Optimization Priority (Do Not Change Without User OK)

1. Short-term win rate
2. Short-term return quality (avg + median)
3. Overall win rate
4. Overall avg return / profit factor

A change is accepted only if it improves a higher-priority metric without harming the priorities above it.

## Current Accepted Config

**Exit policy** (`exit_policy_config.json`) — unchanged from claude_loop_64:

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

**Entry signal** (`entry_signal_config.json`) — updated by entry loop 1:
- `quality_dislocation` engine, `deep_dislocation` rule: `dist_from_52w_high <= -30` (was -20)
- All other entry scoring rules and thresholds unchanged (score 70 = BUY_STARTER, score 80 = BUY_FULL)
- `penalty_rules`: empty (all tested penalties removed good trades)
- Route: BEAR_RISK_OFF only (SIDEWAYS_CHOPPY and LIQUIDITY_RALLY tested and rejected)

**Technical setup** (`technical_setup_config.json`) — updated by entry loops 1 & 2:
- `OVERSOLD_REVERSAL` signal: RSI upper bound `<= 40` (was 42) — from loop 1
- `TRUE_BROKEN_CHART` signal: `sma50_relative < -20` (was -5) — from loop 2 (sweep: -10→-15→-20 all accepted, -25 rejected)

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

### From exit re-validation loop (iters 91-100):

| change | result |
|--------|--------|
| ST max_simulation_days 60 → 45 | rejected (ST WR -1.961pp; time cap cuts winners) |
| ST max_simulation_days 60 → 75 | rejected (ST WR -5.882pp; trailing over-fires on extended window) |
| ST trailing_stop ATR 3.0 → 2.5 | rejected (ST avg -3.349pp; tighter clips winners) |
| ST trailing_stop ATR 3.0 → 3.5 | rejected (ST avg -0.858pp; looser pushes into MAX_SIM) |
| MT max_simulation_days 141 → 120 | rejected (MT avg -2.315pp) |
| MT max_simulation_days 141 → 150 | rejected (MT avg -0.749pp; 141 confirmed) |
| MT trailing_stop enabled at 3.0 ATR | rejected (MT avg -4.131pp; over-fires on MT recovery trades) |
| ST sell_pct 20% → 30% | rejected (ST avg -0.504pp) |
| ST partial_profit target 0.75R → 1.0R | rejected (ST WR -1.961pp; later BE exposes 1 extra trade) |
| ST sell_pct 20% → 15% | rejected (P2 mixed ±0.25pp; noise level) |

**Key finding:** All exit policy optima from the 766-trade universe hold exactly for the 102-trade universe. The exit config is globally robust.

### From entry optimization loop 2 (iters 81-90):

| change | result |
|--------|--------|
| TRUE_BROKEN_CHART sma50_relative < -5% → < -10% | **accepted** (+0.88pp ST WR) |
| sma50_relative < -10% → < -15% | **accepted** (+5.36pp more ST WR) |
| sma50_relative < -15% → < -20% | **accepted** (+2.33pp more; 98% WR, PF 151) |
| sma50_relative < -20% → < -25% | rejected (MT avg collapse, sample too small) |
| sma200_relative < -5%, < -10% | no-op (redundant given sma50 < -20%) |
| OVERSOLD_REVERSAL RSI upper bound 40 → 39 | rejected (ST WR -1.07pp per priority framework) |
| score 90 as BUY_AGGRESSIVE | rejected (ST WR -7.47pp; RSI ≤35 always underperforms) |
| LIQUIDITY_RALLY regime | rejected (ST WR -1.81pp) |
| sma50_relative < -20% → < -18% (fine-bracket) | rejected (-20% is exact quality cliff) |

### From entry optimization loop 1 (iters 71-80):

| change | result |
|--------|--------|
| quality_dislocation route + SIDEWAYS_CHOPPY regime | rejected (ST WR -7.6pp; SIDEWAYS_CHOPPY produces inferior setups) |
| deep_dislocation threshold -20 → -25% | **accepted** (+1.19pp ST WR) |
| deep_dislocation threshold -25 → -30% | **accepted** (+2.53pp more ST WR) |
| deep_dislocation threshold -30 → -35% | rejected (MT regression; -30% confirmed optimum) |
| oversold rule RSI<=35 → RSI<=30 (adds RSI 31-35 as BUY) | rejected (ST WR -3.9pp; RSI 31-35 stocks inferior in -30% filter) |
| RS penalty -20pts (rs<=-15%) | rejected (penalty bug: 90-20=70 accidentally promotes score-90 stocks) |
| RS penalty -25pts (rs<=-15%) | rejected (extreme RS underperformance in bear regime = best setups, not worst) |
| seller domination penalty -25pts (updown<=0.5) | rejected (removes good MT trades) |
| OVERSOLD_REVERSAL RSI upper bound 42 → 38 | rejected (too aggressive; sample too small, median -3pp) |
| OVERSOLD_REVERSAL RSI upper bound 42 → 40 | **accepted** (+0.90pp ST WR, all metrics improved) |

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

### From prior 114-iteration loop — see `docs/pre-refactoring-iterative-fine-tuning-logs/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`

## What's Worth Testing Next

All major config knobs for exit AND entry are now exhausted across 100 iterations. Every exit and entry dimension has been tested under both the original 766-trade universe and the current 102-trade universe. Further gains require structural changes:

1. **Wire `earnings_days_away` into the historical feature builder**: Unlocks earnings-risk tuning. Currently a no-op for backtests (live-only). This is a code change to the native feature builder.
2. **New entry setups beyond `BROKEN_CHART_QUALITY_RECOVERY`**: The current universe is intentionally narrow; widening it requires user approval and careful validation.
3. **Expand ticker universe**: Frozen by user instruction; would require explicit re-authorization.

## Things Not to Do

- Do not re-introduce medium-term trailing stop at any ATR (3.0, 4.0, 5.0 all tested and rejected).
- Do not widen quality_dislocation BUY_FULL threshold above score 80; score 90 tested as BUY_AGGRESSIVE under sma50 < -20% filter and rejected (ST WR -7.47pp; RSI ≤35 = falling knife regardless of filter).
- Do not expand the ticker exclusion list to chase metrics.
- Do not change `risk_config.json` expecting backtest impact; it only affects live `analyze`.
- Do not test ST `breakeven_after_r_multiple` below 0.75R — catastrophic ST WR regression.
- Do not test MT `target+BE` at 0.15R or lower — PF cliff.
- Do not loosen `deep_dislocation` above -25% — quality degrades monotonically (tested -20, -25, -30, -35).
- Do not loosen `OVERSOLD_REVERSAL` RSI upper bound above 40 — RSI 41-42 stocks are marginal entries.
- Do not tighten `OVERSOLD_REVERSAL` RSI upper bound below 40 to 39 or 38 — removes high-avg RSI 39-40 winners (WR% drops due to denominator math, not quality).
- Do not loosen TRUE_BROKEN_CHART sma50_relative above -18% — tested and rejected (-20% is a quality cliff).
- Do not tighten TRUE_BROKEN_CHART sma50_relative below -20% (to -25%) — MT avg collapses.
- Do not add RS-based penalty rules: extreme RS underperformance (rs_vs_spy_20d <= -15%) in BEAR_RISK_OFF = best entries.
- Do not use penalty values of exactly 10, 20, or 30 pts — these accidentally promote score-90/100 stocks to score 70/80 BUY thresholds.
- Do not add SIDEWAYS_CHOPPY or LIQUIDITY_RALLY to quality_dislocation route — both tested and rejected.

## How to Resume

All exit and entry optimization loops are complete (100 total iterations). Every JSON config knob has been exhausted — both for exit (70 iters) and entry (20 iters) and exit re-validation (10 iters). If the user wants to continue, only structural changes (see "What's Worth Testing Next") can yield further improvement.

1. Read this file and the tail of `docs/pre-refactoring-iterative-fine-tuning-logs/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`.
2. Run `validate-config` to confirm config is still valid.
3. Run a baseline backtest (should match entry_exp_83 metrics: 102 trades, 98% WR, 17.566% ST avg).

**Current best run:** `entry_exp_83`
**All accepted changes (vs original):**
- `entry_signal_config.json`: `deep_dislocation` threshold: -20% → -30%
- `technical_setup_config.json`: `OVERSOLD_REVERSAL` RSI upper bound: 42 → 40
- `technical_setup_config.json`: `TRUE_BROKEN_CHART` sma50_relative: < -5 → < -20
