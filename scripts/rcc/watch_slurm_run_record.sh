#!/usr/bin/env bash
set -euo pipefail

# Watch one durable Slurm run record passively so background poll-loop updates
# are visible without calling the manual monitor helper.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/watch_slurm_run_record.py"
RUN_RECORD_PATH="${1:-}"
INTERVAL_SECONDS="${2:-15}"
MAX_CYCLES="${3:-}"

if [[ -z "$RUN_RECORD_PATH" ]]; then
  echo "usage: $0 RUN_RECORD_PATH_OR_POINTER [interval_seconds] [max_cycles]" >&2
  echo "example: $0 .runtime/runs/latest_slurm_run_record.txt 15" >&2
  exit 1
fi

export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"

WATCH_ARGS=("$RUN_RECORD_PATH" "--interval-seconds" "$INTERVAL_SECONDS")
if [[ -n "$MAX_CYCLES" ]]; then
  WATCH_ARGS+=("--max-cycles" "$MAX_CYCLES")
fi

"$PYTHON_BIN" "$PYTHON_SCRIPT" "${WATCH_ARGS[@]}"