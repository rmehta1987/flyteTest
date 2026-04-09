#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SBATCH_SCRIPT="$SCRIPT_DIR/minimal_transcriptomics_smoke.sbatch"
LOCAL_SCRIPT="$SCRIPT_DIR/minimal_transcriptomics_smoke.sh"
OUTPUT_DIR="${SBATCH_OUTPUT_DIR:-/scratch/midway3/mehta5/flyteTest/FlyteTest}"

# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

# Create the Slurm output directory only when we are about to submit to Slurm.
if command -v sbatch >/dev/null 2>&1; then
  mkdir -p "$OUTPUT_DIR"
fi

submit_or_run_smoke "$REPO_ROOT" "$SBATCH_SCRIPT" "$LOCAL_SCRIPT"
