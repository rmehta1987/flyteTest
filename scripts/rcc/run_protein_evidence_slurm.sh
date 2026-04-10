#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/run_protein_evidence_slurm.py"

# Defaults chosen for the RCC cluster so the recipe can submit without ad hoc
# shell snippets. Override any of these before running the script if needed.
export FLYTETEST_SLURM_ACCOUNT="${FLYTETEST_SLURM_ACCOUNT:-rcc-staff}"
export FLYTETEST_SLURM_QUEUE="${FLYTETEST_SLURM_QUEUE:-caslake}"
export FLYTETEST_SLURM_WALLTIME="${FLYTETEST_SLURM_WALLTIME:-02:00:00}"
export FLYTETEST_SLURM_CPU="${FLYTETEST_SLURM_CPU:-8}"
export FLYTETEST_SLURM_MEMORY="${FLYTETEST_SLURM_MEMORY:-32Gi}"
export FLYTETEST_SLURM_JOB_PREFIX="${FLYTETEST_SLURM_JOB_PREFIX:-pe}"
export FLYTETEST_REPO_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "${EXONERATE_SIF:-}" && -f "$REPO_ROOT/data/images/exonerate_2.2.0--1.sif" ]]; then
  export EXONERATE_SIF="$REPO_ROOT/data/images/exonerate_2.2.0--1.sif"
fi

RUN_RECORD_POINTER="$REPO_ROOT/.runtime/runs/latest_protein_evidence_slurm_run_record.txt"
ARTIFACT_POINTER="$REPO_ROOT/.runtime/runs/latest_protein_evidence_slurm_artifact.txt"
mkdir -p "$(dirname "$RUN_RECORD_POINTER")"

# The shell wrapper owns environment bootstrap only:
# - choose repo-relative defaults
# - expose the checkout to Python via PYTHONPATH
# - activate the repo virtualenv when it exists
# - then delegate the actual recipe prepare/submit logic to the Python helper
if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # Activate the repo environment when it exists so the cluster run uses the
  # same pinned dependencies as the local workspace.
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"

# The Python helper prints one machine-readable JSON summary. On success it
# contains the saved recipe path, durable run-record path, accepted Slurm job
# ID, and submission stdout/stderr captured by the server. On failure it prints
# the structured recipe-preparation or submission payload so callers can see the
# exact unsupported state or runtime error.
"$PYTHON_BIN" "$PYTHON_SCRIPT"
