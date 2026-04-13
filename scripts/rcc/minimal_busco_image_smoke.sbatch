#!/usr/bin/env bash
#SBATCH --job-name=minimal-busco-image-smoke
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --account=rcc-staff
#SBATCH --partition=caslake
#SBATCH --output=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.out
#SBATCH --error=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.err

# Slurm entrypoint for the BUSCO image smoke when you want to exercise the
# container-backed path on RCC.
set -euo pipefail

module load gcc/13.2.0
module load apptainer/1.4.1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

cd "$REPO_ROOT"
exec bash scripts/rcc/minimal_busco_image_smoke.sh
