#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SBATCH_SCRIPT="$SCRIPT_DIR/minimal_busco_image_smoke.sbatch"
LOCAL_SCRIPT="$SCRIPT_DIR/minimal_busco_image_smoke.sh"
OUTPUT_DIR="${SBATCH_OUTPUT_DIR:-/scratch/midway3/mehta5/flyteTest/FlyteTest}"

# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

if command -v sbatch >/dev/null 2>&1; then
  mkdir -p "$OUTPUT_DIR"
  # Stage the upstream BUSCO test FASTA before submission so compute nodes do
  # not need GitLab access just to read the repo-local input fixture.
  bash "$SCRIPT_DIR/download_minimal_busco_fixture.sh"
fi

submit_or_run_smoke "$REPO_ROOT" "$SBATCH_SCRIPT" "$LOCAL_SCRIPT"
