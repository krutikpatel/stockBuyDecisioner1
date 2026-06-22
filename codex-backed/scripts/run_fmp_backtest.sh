#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 2 ]]; then
  echo "usage: $0 [run-id] [--no-rebuild-feature-cache]" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "missing .env at repo root: $ROOT_DIR/.env" >&2
  exit 1
fi

RUN_ID="${1:-fmp_baseline_$(date +%Y%m%d_%H%M%S)}"
REBUILD_FEATURE_CACHE=1

if [[ $# -eq 2 ]]; then
  if [[ "$2" != "--no-rebuild-feature-cache" ]]; then
    echo "unsupported option: $2" >&2
    echo "usage: $0 [run-id] [--no-rebuild-feature-cache]" >&2
    exit 2
  fi
  REBUILD_FEATURE_CACHE=0
fi

set -a
source .env
set +a

CMD=(
  codex-backed/.venv/bin/python -m codex_backed.cli backtest
  --config-dir codex-backed/configs
  --output-dir codex-backed/results
  --run-id "$RUN_ID"
  --data-mode fmp_primary_yfinance_fallback
  --workers 8
)

if [[ "$REBUILD_FEATURE_CACHE" -eq 1 ]]; then
  CMD+=("--rebuild-feature-cache")
fi

echo "run-id: $RUN_ID"
PYTHONPATH="$ROOT_DIR/codex-backed/src" "${CMD[@]}"
