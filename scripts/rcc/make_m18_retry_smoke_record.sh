#!/usr/bin/env bash
set -euo pipefail

# Create the synthetic Milestone 18 retryable run record used by the retry
# policy smoke.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/m18_make_retry_smoke_record.py"
DEFAULT_POINTER="$REPO_ROOT/.runtime/runs/latest_m18_slurm_run_record.txt"
RUN_RECORD_PATH="${1:-}"
# Second argument overrides the synthetic scheduler state (default: NODE_FAIL).
if [[ -n "${2:-}" ]]; then
  export FLYTETEST_M18_RETRY_SMOKE_STATE="${2}"
fi

if [[ -z "$RUN_RECORD_PATH" && -f "$DEFAULT_POINTER" ]]; then
  RUN_RECORD_PATH="$(tr -d '\n' <"$DEFAULT_POINTER")"
fi

if [[ -z "$RUN_RECORD_PATH" ]]; then
  echo "usage: $0 [run_record_path] [scheduler_state]" >&2
  echo "  scheduler_state defaults to NODE_FAIL; use OUT_OF_MEMORY for escalation smoke." >&2
  echo "or set $DEFAULT_POINTER by running the Milestone 18 Slurm wrapper first." >&2
  exit 1
fi

export FLYTETEST_REPO_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
"$PYTHON_BIN" "$PYTHON_SCRIPT" "$RUN_RECORD_PATH"
