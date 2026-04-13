#!/usr/bin/env bash
set -euo pipefail

# Reconcile the latest protein-evidence Slurm run record, or a run record path
# passed explicitly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/monitor_protein_evidence_slurm.py"
DEFAULT_POINTER="$REPO_ROOT/.runtime/runs/latest_protein_evidence_slurm_run_record.txt"
RUN_RECORD_PATH="${1:-}"

if [[ -z "$RUN_RECORD_PATH" ]]; then
  if [[ -f "$DEFAULT_POINTER" ]]; then
    RUN_RECORD_PATH="$(tr -d '\n' <"$DEFAULT_POINTER")"
  fi
fi

if [[ -z "$RUN_RECORD_PATH" ]]; then
  echo "usage: $0 [run_record_path]" >&2
  echo "or set $DEFAULT_POINTER by running the protein evidence Slurm submit script first." >&2
  exit 1
fi

export FLYTETEST_REPO_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# The shell wrapper is intentionally small: it resolves which durable run record
# to inspect, bootstraps the repo Python environment, and then hands the real
# reconciliation work to the Python helper.
if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"

# The Python helper prints one machine-readable JSON snapshot of the monitor
# result. Expect fields such as the observed scheduler state, any stdout/stderr
# log paths recorded in the durable run record, and reconciliation limits if
# Slurm commands were unavailable or incomplete.
"$PYTHON_BIN" "$PYTHON_SCRIPT" "$RUN_RECORD_PATH"
