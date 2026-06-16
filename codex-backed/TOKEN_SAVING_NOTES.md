# Token-Saving Notes for Tuning Loops

When running long iterative tuning loops (10+ backtests in one session), repeated tool output drives most of the conversation-token cost. This file documents the conventions to use to keep each iteration cheap, the new helper script that makes it easy, and the cumulative savings estimate.

The goal is not to skip information; it is to print only what we actually read when deciding accept/reject. Anything we never look at should not be in the context window.

## TL;DR

For each tuning iteration, run:

```bash
# 1. Validate config silently; only echo on failure
PYTHONPATH=codex-backed/src claude-backend/.venv/bin/python -m codex_backed.cli \
  validate-config --config-dir codex-backed/configs > /dev/null

# 2. Run backtest (output goes to a tmp file via run_in_background, we do not read it)
PYTHONPATH=codex-backed/src claude-backend/.venv/bin/python -m codex_backed.cli \
  backtest --config-dir codex-backed/configs --output-dir codex-backed/results \
  --run-id claude_loop_NN --workers 8

# 3. After completion, read metrics with the compact helper
claude-backend/.venv/bin/python codex-backed/scripts/run_summary.py \
  codex-backed/results/claude_loop_NN
```

Do NOT:

- `cat` `metrics.json` raw (verbose JSON with fields we ignore)
- Pipe through `python -m json.tool` (pretty-print bloats output ~2x)
- `tail` the backtest stdout/stderr file just to confirm completion (the task-notification already confirms it)
- Echo the validate-config status JSON
- Create a separate TaskCreate entry for every iteration

## What We Changed and Why

### 1. Compact metrics helper script — `codex-backed/scripts/run_summary.py`

Prints the ten numbers we actually use per iteration: overall avg/median/win-rate/profit-factor, per-horizon breakdown, per-exit-reason breakdown. About 6 lines of output vs ~30 lines from a full `metrics.json` dump.

**Before** (full `cat metrics.json | python3 -m json.tool` or hand-built print loops): ~600 tokens per iteration just for metrics.

**After** (`run_summary.py`): ~150 tokens per iteration.

**Savings**: ~450 tokens × 10 iterations = ~4,500 tokens per loop.

Try it on any existing run:

```bash
claude-backend/.venv/bin/python codex-backed/scripts/run_summary.py codex-backed/results/claude_loop_10
```

Output (real):

```
overall  n= 766  avg= 12.826  med=  8.700  wr= 68.799  pf=  7.748
  medium_term n= 383  avg= 14.766  med=  4.566  wr= 69.713  pf=  8.604
  short_term  n= 383  avg= 10.885  med=  9.907  wr= 67.885  pf=  6.854
  MAX_SIM_WINDOW_EXIT    n= 267  avg= 28.870  wr= 97.378
  STOP_LOSS_EXIT         n= 320  avg= -3.513  wr= 27.500
  TRAILING_STOP_EXIT     n= 179  avg= 18.103  wr=100.000
```

### 2. Silence the `validate-config` status JSON

`validate-config` prints `{"status": "ok", "config_dir": "..."}` on success. We never read this output; we only need the exit code.

**Before**:

```bash
PYTHONPATH=... validate-config --config-dir codex-backed/configs 2>&1 | tail -3
# ~80 tokens of JSON every time
```

**After**:

```bash
PYTHONPATH=... validate-config --config-dir codex-backed/configs > /dev/null
# 0 tokens on success; if it exits non-zero the harness shows the error
```

**Savings**: ~80 tokens × 10 iterations = ~800 tokens per loop.

### 3. Skip the backtest status-JSON tail

After each backtest, the runner writes a `~200-token` status JSON to its log file (`run_id`, `tickers`, `feature_cache_status`, etc.). The Claude Code task-notification already confirms completion. Reading the tail is duplicate information.

**Before** (per iteration):

```bash
tail -15 /tmp/...output
# echoes the {"status": "ok", "run_id": "...", "tickers": 199, ...} block
```

**After**: trust the task-notification; jump straight to `run_summary.py`.

**Savings**: ~200 tokens × 10 iterations = ~2,000 tokens per loop.

### 4. Pre-extract "what has been tried" once, at loop start

The audit log (`docs/pre-refactoring-iterative-fine-tuning-logs/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md`) is 4,400+ lines. Grepping into it multiple times during a loop is expensive and wastes context on duplicated history.

**Convention**:

- Read `TUNING_STATUS.md` once at the start of every session. It has a "Things Already Tested" table that summarizes the full audit log.
- Only grep the audit log when proposing a specific change you suspect might already be covered; do it once per change, not per iteration.
- Append the new iteration to the audit log via `Edit` (not `Write`), so we never re-send the whole log file in a tool call.

**Savings**: ~1,000-3,000 tokens per loop depending on how many cross-checks you would otherwise do.

### 5. `Edit` instead of `Write` for log appends

`Write` echoes the entire file to confirm the write. The audit log is huge. `Edit` only sends the changed strings.

**Before**: `Write` of a 4,400-line file = ~50,000 tokens per append.

**After**: `Edit` of a single `old_string` -> `new_string` pair = ~300-600 tokens per append.

**Savings**: ~50,000 tokens × 10 iterations = ~500,000 tokens per loop in the worst case. This is the single biggest saver. Already used in the most recent loop.

### 6. Don't `TaskCreate` per iteration

Each `TaskCreate` is ~80 tokens; each `TaskUpdate` is ~30 tokens. Creating one task per iteration with start/complete transitions burns ~150 tokens × 10 iterations = ~1,500 tokens.

**Convention**:

- One parent task per loop ("Run 10-iter tuning loop")
- One task at the start for setup work (cache build, env check)
- No per-iteration tasks; the audit log already tracks per-iteration state

**Savings**: ~1,200 tokens per loop.

## Cumulative Estimate

Per 10-iter tuning loop, applying all six conventions:

| Source | Savings |
|--------|---------|
| Compact metrics helper | ~4,500 |
| Silence validate-config | ~800 |
| Skip backtest status tail | ~2,000 |
| Pre-extract audit log once | ~1,000-3,000 |
| Edit (not Write) for log appends | ~50,000+ |
| Drop per-iter TaskCreate | ~1,200 |
| **Total per loop** | **~60,000-70,000** |

This is a rough estimate; real numbers depend on log size and how chatty the iteration was. The `Edit`-vs-`Write` discipline dominates everything else.

## Conventions to Carry Forward

1. Use `run_summary.py` for every metrics check.
2. Silence successful tool outputs; only surface failures.
3. Trust task-notifications for completion; do not re-read the runner's stdout.
4. Update the audit log with `Edit`, never `Write`.
5. Reference `TUNING_STATUS.md` as the cached prior-work summary; only re-grep `docs/pre-refactoring-iterative-fine-tuning-logs/ITERATIVE_IMPROVEMENTS_50_LOOP_LOG.md` when you need detail that the summary lacks.
6. Keep TaskList granular at the loop level, not the iteration level.
