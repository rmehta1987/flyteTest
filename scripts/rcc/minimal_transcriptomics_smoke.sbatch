#!/usr/bin/env bash
#SBATCH --job-name=minimal-transcriptomics-smoke
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --account=rcc-staff
#SBATCH --partition=caslake
#SBATCH --output=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.out
#SBATCH --error=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.err

# Slurm entrypoint for the Trinity, STAR, and StringTie transcriptomics smoke
# on RCC.
set -euo pipefail

# Load the cluster toolchain needed by the smoke wrappers and Apptainer runtime.
module load gcc/13.2.0
module load apptainer/1.4.1

REPO_ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
exec "$REPO_ROOT/scripts/rcc/minimal_transcriptomics_smoke.sh"
