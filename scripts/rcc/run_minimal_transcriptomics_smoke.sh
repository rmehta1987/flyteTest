#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SBATCH_SCRIPT="$SCRIPT_DIR/minimal_transcriptomics_smoke.sbatch"
OUTPUT_DIR="${SBATCH_OUTPUT_DIR:-/scratch/midway3/mehta5/flyteTest/FlyteTest}"

mkdir -p "$OUTPUT_DIR"
sbatch "$SBATCH_SCRIPT"
