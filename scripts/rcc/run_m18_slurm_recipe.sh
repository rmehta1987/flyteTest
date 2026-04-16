#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PREPARE_SCRIPT="$SCRIPT_DIR/m18_prepare_slurm_recipe.py"
SUBMIT_SCRIPT="$SCRIPT_DIR/m18_submit_slurm_recipe.py"

# Defaults chosen for the RCC cluster. Override any of these before running the
# wrapper if the account, partition, image path, or fixture location differs.
export FLYTETEST_SLURM_ACCOUNT="${FLYTETEST_SLURM_ACCOUNT:-rcc-staff}"
export FLYTETEST_SLURM_QUEUE="${FLYTETEST_SLURM_QUEUE:-caslake}"
export FLYTETEST_SLURM_WALLTIME="${FLYTETEST_SLURM_WALLTIME:-00:10:00}"
export FLYTETEST_SLURM_CPU="${FLYTETEST_SLURM_CPU:-2}"
export FLYTETEST_BUSCO_CPU="${FLYTETEST_BUSCO_CPU:-$FLYTETEST_SLURM_CPU}"
export FLYTETEST_SLURM_MEMORY="${FLYTETEST_SLURM_MEMORY:-8Gi}"
export FLYTETEST_SLURM_JOB_PREFIX="${FLYTETEST_SLURM_JOB_PREFIX:-m18-busco}"
export FLYTETEST_BUSCO_GENOME_FASTA="${FLYTETEST_BUSCO_GENOME_FASTA:-data/busco/test_data/eukaryota/genome.fna}"
export FLYTETEST_BUSCO_LINEAGE_DATASET="${FLYTETEST_BUSCO_LINEAGE_DATASET:-auto-lineage}"
export FLYTETEST_BUSCO_MODE="${FLYTETEST_BUSCO_MODE:-geno}"
export FLYTETEST_REPO_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$REPO_ROOT/results/.tmp"
export FLYTETEST_TMPDIR="${FLYTETEST_TMPDIR:-$REPO_ROOT/results/.tmp}"
export TMPDIR="$FLYTETEST_TMPDIR"

if [[ -z "${BUSCO_SIF:-}" && -f "$REPO_ROOT/data/images/busco_v6.0.0_cv1.sif" ]]; then
  export BUSCO_SIF="$REPO_ROOT/data/images/busco_v6.0.0_cv1.sif"
fi

if [[ -z "${BUSCO_SIF:-}" ]]; then
  cat >&2 <<'EOF'
BUSCO_SIF is not set and data/images/busco_v6.0.0_cv1.sif was not found.

Download the image first, for example:
  apptainer pull data/images/busco_v6.0.0_cv1.sif docker://ezlabgva/busco:v6.0.0_cv1

Then rerun this wrapper, or export BUSCO_SIF=/path/to/busco_v6.0.0_cv1.sif.
EOF
  exit 1
fi

if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
ARTIFACT_POINTER="$REPO_ROOT/.runtime/runs/latest_m18_slurm_artifact.txt"

if [[ "$FLYTETEST_BUSCO_GENOME_FASTA" = /* ]]; then
  HOST_BUSCO_GENOME_FASTA="$FLYTETEST_BUSCO_GENOME_FASTA"
else
  HOST_BUSCO_GENOME_FASTA="$REPO_ROOT/$FLYTETEST_BUSCO_GENOME_FASTA"
fi
if [[ ! -s "$HOST_BUSCO_GENOME_FASTA" ]]; then
  BUSCO_FIXTURE_FASTA="$HOST_BUSCO_GENOME_FASTA" bash "$SCRIPT_DIR/download_minimal_busco_fixture.sh"
fi

"$PYTHON_BIN" "$PREPARE_SCRIPT"
"$PYTHON_BIN" "$SUBMIT_SCRIPT" "$(tr -d '\n' <"$ARTIFACT_POINTER")"
