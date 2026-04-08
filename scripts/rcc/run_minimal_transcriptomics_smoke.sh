#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SBATCH_SCRIPT="$SCRIPT_DIR/minimal_transcriptomics_smoke.sbatch"
OUTPUT_DIR="${SBATCH_OUTPUT_DIR:-/scratch/midway3/mehta5/flyteTest/FlyteTest}"

mkdir -p "$OUTPUT_DIR"
sbatch --chdir "$REPO_ROOT" "$SBATCH_SCRIPT"
