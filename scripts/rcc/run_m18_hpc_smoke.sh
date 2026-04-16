#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUSCO_SMOKE_SBATCH="$SCRIPT_DIR/minimal_busco_image_smoke.sbatch"
BUSCO_SMOKE_LOCAL="$SCRIPT_DIR/minimal_busco_image_smoke.sh"
OUTPUT_DIR="${SBATCH_OUTPUT_DIR:-/scratch/midway3/mehta5/flyteTest/FlyteTest}"

# One-command Milestone 18 HPC smoke defaults. Override these environment
# variables before running when the allocation or image path differs.
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

echo "Milestone 18 HPC smoke"
echo "repo:      $REPO_ROOT"
echo "partition: $FLYTETEST_SLURM_QUEUE"
echo "account:   $FLYTETEST_SLURM_ACCOUNT"
echo "busco sif: $BUSCO_SIF"
echo

# Stage the official BUSCO eukaryota test FASTA under data/ before submission.
bash "$SCRIPT_DIR/download_minimal_busco_fixture.sh"

if [[ "${M18_RUN_BUSCO_IMAGE_SMOKE:-1}" == "1" ]]; then
  if command -v sbatch >/dev/null 2>&1; then
    mkdir -p "$OUTPUT_DIR"
    BUSCO_JOB_ID="$(
      sbatch \
        --parsable \
        --chdir "$REPO_ROOT" \
        --account "$FLYTETEST_SLURM_ACCOUNT" \
        --partition "$FLYTETEST_SLURM_QUEUE" \
        --cpus-per-task "$FLYTETEST_SLURM_CPU" \
        --mem "$FLYTETEST_SLURM_MEMORY" \
        --time "$FLYTETEST_SLURM_WALLTIME" \
        --job-name m18-busco-fixture \
        --output "$OUTPUT_DIR/%x.%j.out" \
        --error "$OUTPUT_DIR/%x.%j.err" \
        "$BUSCO_SMOKE_SBATCH"
    )"
    echo "submitted BUSCO fixture image smoke job: $BUSCO_JOB_ID"
  else
    echo "sbatch not found; running BUSCO fixture image smoke locally"
    bash "$BUSCO_SMOKE_LOCAL"
  fi
else
  echo "skipping BUSCO fixture image smoke because M18_RUN_BUSCO_IMAGE_SMOKE=$M18_RUN_BUSCO_IMAGE_SMOKE"
fi

# The M18 retry policy test exercises FLyteTest's durable Slurm run-record path
# with the same BUSCO fixture FASTA. It does not wait for a real node failure:
# it copies the accepted run record, marks the copy with a retryable synthetic
# scheduler state, and submits a retry child from that copied record.
bash "$SCRIPT_DIR/run_m18_slurm_recipe.sh"
bash "$SCRIPT_DIR/make_m18_retry_smoke_record.sh"
bash "$SCRIPT_DIR/retry_m18_slurm_job.sh"
bash "$SCRIPT_DIR/monitor_m18_slurm_job.sh" "$(tr -d '\n' <"$REPO_ROOT/.runtime/runs/latest_m18_retry_child_run_record.txt")"

cat <<EOF

Milestone 18 HPC smoke submitted.

Pointers:
  source run:  $REPO_ROOT/.runtime/runs/latest_m18_slurm_run_record.txt
  retry seed:  $REPO_ROOT/.runtime/runs/latest_m18_retry_smoke_run_record.txt
  retry child: $REPO_ROOT/.runtime/runs/latest_m18_retry_child_run_record.txt

BUSCO fixture outputs, when that job finishes:
  $REPO_ROOT/results/minimal_busco_image_smoke/
EOF
