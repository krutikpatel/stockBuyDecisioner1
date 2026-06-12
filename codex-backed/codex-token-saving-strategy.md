# Codex Token-Saving Strategy

This project's backtest tuning loop can consume a lot of conversation context because each iteration repeats the same steps: run, inspect metrics, compare to a baseline, decide, log, patch config, and continue. The fix is to move repetitive state and reporting into files and scripts, then keep chat messages focused on compact deltas.

## Goals

- Keep optimization state outside the chat transcript.
- Avoid rereading the full improvement log for every iteration.
- Prefer compact JSON summaries over long pasted metrics.
- Keep the Markdown audit readable but terse.
- Batch or summarize repetitive work when possible.

## Rules For Future Iterative Tuning

1. Use `codex-backed/optimization_state.json` as the first file to read before resuming optimization.
2. Use `codex-backed/optimization_memory.json` to avoid repeating rejected parameter values and banned tactics.
3. Use `codex-backed/scripts/optimize_loop.py summarize-run` to inspect runs instead of pasting full `metrics.json`.
4. Use `codex-backed/scripts/optimize_loop.py append-audit` for short Markdown audit entries.
5. Keep chat updates to the smallest useful delta:

```json
{
  "run": "loop100_064_w8",
  "change": "short.initial_stop.support_buffer_pct 1.0 -> 0.75",
  "short_term": {"avg": 11.4994, "win": 67.8571, "pf": 7.3712},
  "overall": {"avg": 14.7733, "win": 58.9286, "pf": 9.2139},
  "decision": "reject"
}
```

## Current Optimization Priority

The latest user direction changed the objective order:

1. Short-term win rate.
2. Short-term average return and return quality.
3. Overall win rate.
4. Overall average return and profit factor.
5. Medium-term metrics only if short-term metrics are unchanged or explicitly requested.

Ticker pruning is frozen. Do not add more ticker exclusions just to lift headline backtest metrics.

## Compact File Layout

```text
codex-backed/
  codex-token-saving-strategy.md
  optimization_state.json
  optimization_memory.json
  scripts/
    optimize_loop.py
```

## Script Usage

Compact summary for a run:

```bash
codex-backed/scripts/optimize_loop.py summarize-run \
  --run-id loop100_064_w8 \
  --baseline-run-id loop100_061_w8
```

Append a terse audit entry and update state:

```bash
codex-backed/scripts/optimize_loop.py append-audit \
  --iteration 115 \
  --run-id loop100_065_w8 \
  --baseline-run-id loop100_061_w8 \
  --change "short.initial_stop.support_buffer_pct 1.0 -> 1.25" \
  --decision "pending" \
  --next "Compare short-term win rate first"
```

## Expected Token Savings

The old loop required repeatedly reading and discussing long Markdown sections and full metric objects. The new loop should usually require only:

- `optimization_state.json`
- `optimization_memory.json`
- one compact run summary
- one short audit entry

That should reduce tuning-loop token usage by roughly 70-90%.
