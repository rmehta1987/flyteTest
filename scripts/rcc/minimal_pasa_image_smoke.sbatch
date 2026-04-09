#!/usr/bin/env bash
#SBATCH --job-name=minimal-pasa-image-smoke
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --account=rcc-staff
#SBATCH --partition=caslake
#SBATCH --output=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.out
#SBATCH --error=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

cd "$REPO_ROOT"
exec bash scripts/rcc/minimal_pasa_image_smoke.sh
