#!/usr/bin/env bash
set -euo pipefail

# Submit the minimal hello-world Slurm job when you only need a scheduler
# sanity check.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SBATCH_SCRIPT="$SCRIPT_DIR/hello_from_slurm.sbatch"
OUTPUT_DIR="${SBATCH_OUTPUT_DIR:-/scratch/midway3/mehta5/flyteTest/FlyteTest}"

mkdir -p "$OUTPUT_DIR"
sbatch "$SBATCH_SCRIPT"
