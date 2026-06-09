#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <run-id> [--rebuild-feature-cache]" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

EXTRA_ARGS=()
if [[ $# -eq 2 ]]; then
  if [[ "$2" != "--rebuild-feature-cache" ]]; then
    echo "unsupported option: $2" >&2
    exit 2
  fi
  EXTRA_ARGS+=("--rebuild-feature-cache")
fi

CMD=(
  codex-backed/.venv/bin/codex-backed backtest
  --config-dir codex-backed/configs
  --output-dir codex-backed/results
  --run-id "$1"
  --workers 8
)

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  CMD+=("${EXTRA_ARGS[@]}")
fi

"${CMD[@]}"
