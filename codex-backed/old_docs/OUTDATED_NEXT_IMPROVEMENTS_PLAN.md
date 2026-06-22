# Next Improvements Plan - OUTDATED

This plan implements the seven changes proposed from `codex-backed/results/my_run_02`.

## Goal

Improve short- and medium-term backtest quality by reducing broad low-edge entries and focusing on the strongest native-feature setup:

- `BROKEN_CHART_QUALITY_RECOVERY`
- especially in `BEAR_RISK_OFF` and `SIDEWAYS_CHOPPY`

Primary success metrics for the next run:

- higher average realized return than `my_run_02`
- higher profit factor than `my_run_02`
- lower stop-loss rate than `my_run_02`
- lower actionable trade count from broad low-edge routes
- meaningful setup distribution remains populated

## Planned Changes

1. Promote `BROKEN_CHART_QUALITY_RECOVERY` as the core quality-dislocation setup.
   - Route it to `quality_dislocation` only in `BEAR_RISK_OFF` and `SIDEWAYS_CHOPPY`.
   - Keep scoring focused on real technical dislocation, oversold/rebound behavior, and volume/RS confirmation.

2. Disable `GROWTH_LEADER_PULLBACK` in `LIQUIDITY_RALLY`.
   - Add a route-level regime guard so pullbacks in liquidity-rally regimes do not become actionable.

3. Tighten `GROWTH_LEADER_PULLBACK`.
   - Require at least one optional confirmation signal: `VOLUME_DRY_UP` or `RS_LEADER_VS_SPY`.
   - Keep the setup valid in other regimes when confirmation exists.

4. Downgrade broad `bull_leadership`.
   - Remove `BUY_AGGRESSIVE` from broad bull-leadership output.
   - Let higher-priority concrete setups (`BREAKOUT_MOMENTUM`, `GROWTH_LEADER_PULLBACK`) own stronger labels.
   - Broad leadership without a concrete setup should only produce `BUY_STARTER` or `WATCHLIST`.

5. Keep `extended_starter` as starter-only.
   - No upgrade path to `BUY_FULL` or `BUY_AGGRESSIVE`.
   - Keep current starter sizing.

6. Add weak-ticker exclusion/penalty config.
   - Add an explicit high-priority route to `no_trade` for tickers that underperformed with sufficient sample size in `my_run_02`.
   - Initial list: `SLB`, `DLTR`, `TXN`, `SYK`, `BA`, `GIS`, `SNOW`, `BIIB`, `ADI`.

7. Defer deeper exit optimization until entry filters improve.
   - Keep current first-pass exit settings in place.
   - Add documentation that the next exit-tuning pass should happen after the filtered entry run is reviewed.

## Files To Change

- `configs/entry_signal_config.json`
- `configs/technical_setup_config.json`
- `docs/baseProject/PROGRESS.md`
- `BACKTEST_README.md`

## Validation

Run:

```bash
codex-backed/.venv/bin/python -m pytest codex-backed/tests -q
```

Run config validation:

```bash
codex-backed/.venv/bin/codex-backed validate-config \
  --config-dir codex-backed/configs
```

Run a comparison backtest:

```bash
codex-backed/.venv/bin/codex-backed backtest \
  --config-dir codex-backed/configs \
  --output-dir codex-backed/results \
  --run-id my_run_03 \
  --rebuild-feature-cache
```

Compare `my_run_03` against `my_run_02` using:

- `metrics.json -> overall`
- `by_entry_strategy.csv`
- `by_entry_setup.csv`
- `by_market_regime.csv`
- `by_exit_reason.csv`
- `input_quality`

## Implementation Status

Implemented in the current config pass:

- `BROKEN_CHART_QUALITY_RECOVERY` is routed to `quality_dislocation` only in `BEAR_RISK_OFF` and `SIDEWAYS_CHOPPY`.
- `GROWTH_LEADER_PULLBACK` requires `VOLUME_DRY_UP` or `RS_LEADER_VS_SPY`.
- `GROWTH_LEADER_PULLBACK` is blocked in `LIQUIDITY_RALLY`.
- Broad `bull_leadership` can only produce `BUY_STARTER` or `WATCHLIST`.
- `extended_starter` remains starter-only.
- Weak tickers from `my_run_02` are routed to `NO_TRADE`.
- Exit tuning remains deferred until filtered entry results are reviewed.

Validation result:

- `codex-backed/.venv/bin/python -m pytest codex-backed/tests -q` -> 25 passed.
- `validate-config` -> passed.
- Full serial comparison run: `my_run_03_workers1`.
