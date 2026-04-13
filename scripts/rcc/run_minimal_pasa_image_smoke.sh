#!/usr/bin/env bash
set -euo pipefail

# Launch the Apptainer-backed PASA image smoke locally or through Slurm,
# creating the smoke workspace when the scheduler path is available.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SBATCH_SCRIPT="$SCRIPT_DIR/minimal_pasa_image_smoke.sbatch"
LOCAL_SCRIPT="$SCRIPT_DIR/minimal_pasa_image_smoke.sh"

# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

# Create the smoke workspace only when Slurm submission is available.
if command -v sbatch >/dev/null 2>&1; then
  mkdir -p "$REPO_ROOT/results/minimal_pasa_image_smoke"
fi

submit_or_run_smoke "$REPO_ROOT" "$SBATCH_SCRIPT" "$LOCAL_SCRIPT"
