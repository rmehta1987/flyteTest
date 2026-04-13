#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/run_m19_resume_slurm_smoke.py"

# RCC-first defaults for the Milestone 19 local-to-Slurm resume smoke.
export FLYTETEST_SLURM_ACCOUNT="${FLYTETEST_SLURM_ACCOUNT:-rcc-staff}"
export FLYTETEST_SLURM_QUEUE="${FLYTETEST_SLURM_QUEUE:-caslake}"
export FLYTETEST_SLURM_WALLTIME="${FLYTETEST_SLURM_WALLTIME:-00:10:00}"
export FLYTETEST_SLURM_CPU="${FLYTETEST_SLURM_CPU:-2}"
export FLYTETEST_BUSCO_CPU="${FLYTETEST_BUSCO_CPU:-$FLYTETEST_SLURM_CPU}"
export FLYTETEST_SLURM_MEMORY="${FLYTETEST_SLURM_MEMORY:-8Gi}"
export FLYTETEST_SLURM_JOB_PREFIX="${FLYTETEST_SLURM_JOB_PREFIX:-m19-resume}"
export FLYTETEST_REPO_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$REPO_ROOT/results/.tmp"
export FLYTETEST_TMPDIR="${FLYTETEST_TMPDIR:-$REPO_ROOT/results/.tmp}"
export TMPDIR="$FLYTETEST_TMPDIR"

if [[ -z "${BUSCO_SIF:-}" && -f "$REPO_ROOT/data/images/busco_v6.0.0_cv1.sif" ]]; then
  export BUSCO_SIF="$REPO_ROOT/data/images/busco_v6.0.0_cv1.sif"
fi

if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
"$PYTHON_BIN" "$PYTHON_SCRIPT"