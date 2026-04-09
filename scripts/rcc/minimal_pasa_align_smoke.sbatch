#!/usr/bin/env bash
#SBATCH --job-name=minimal-pasa-align-smoke
#SBATCH --partition=caslake
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=%x.%j.out
#SBATCH --error=%x.%j.err

set -euo pipefail

# Load the cluster toolchain needed by the smoke wrappers and Apptainer runtime.
module load gcc/13.2.0
module load apptainer/1.4.1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

cd "$REPO_ROOT"
bash scripts/rcc/minimal_pasa_align_smoke.sh
