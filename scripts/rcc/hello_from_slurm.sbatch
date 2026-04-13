#!/usr/bin/env bash
#SBATCH --job-name=hello-from-slurm
#SBATCH --time=00:05:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=1M
#SBATCH --account=rcc-staff
#SBATCH --partition=caslake
#SBATCH --output=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.out
#SBATCH --error=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.err

# Minimal Slurm job used by the RCC smoke wrappers to confirm batch submission
# and stdout capture.
set -euo pipefail

echo "hello from slurm"
sleep 5
