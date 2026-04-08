#!/usr/bin/env bash
#SBATCH --job-name=minimal-transcriptomics-smoke
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --account=rcc-staff
#SBATCH --partition=broadwl
#SBATCH --output=/scratch/midway3/mehta5/flyteTest/FlyteTest/%j.out
#SBATCH --error=/scratch/midway3/mehta5/flyteTest/FlyteTest/%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/minimal_transcriptomics_smoke.sh"
