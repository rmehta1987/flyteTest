#!/usr/bin/env bash
set -euo pipefail

# Passively watch one durable Slurm run record so background slurm_poll_loop
# updates are visible in the terminal without calling the manual monitor helper
# or making any scheduler calls.  Run from a login-node shell or RCC session;
# the MCP server must already be running and actively polling for the record to
# update between cycles.
#
# Usage:
#   watch_slurm_run_record.sh RUN_RECORD_PATH_OR_POINTER [interval_seconds] [max_cycles]
#
# RUN_RECORD_PATH_OR_POINTER may be:
#   - a run directory (e.g. .runtime/runs/20260413T120000Z-rna_seq_pipeline-abc123)
#   - a direct path to slurm_run_record.json
#   - a .txt pointer file written by other rcc scripts (e.g. latest_slurm_run_record.txt)

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

# Add src/ to PYTHONPATH so the flytetest package is importable without
# requiring a pip install.  Prepend rather than replace so any caller-supplied
# PYTHONPATH entries (e.g. from a module-loaded environment) are preserved.
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# Load the cluster Python and Apptainer modules when the module system is
# available.  On nodes without `module` this block is silently skipped, so
# the script works on developer laptops and in CI as well as on the HPC
# login node.
if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

# Activate the project virtualenv when it exists.  This ensures the same
# interpreter and package versions used by the MCP server are used here,
# which matters when flytetest is not installed system-wide.
if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

# Allow callers to pin a specific interpreter via PYTHON_BIN (e.g. in cluster
# job scripts where the module-loaded python3 may differ from the venv).
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"

WATCH_ARGS=("$RUN_RECORD_PATH" "--interval-seconds" "$INTERVAL_SECONDS")
if [[ -n "$MAX_CYCLES" ]]; then
  WATCH_ARGS+=("--max-cycles" "$MAX_CYCLES")
fi

"$PYTHON_BIN" "$PYTHON_SCRIPT" "${WATCH_ARGS[@]}"