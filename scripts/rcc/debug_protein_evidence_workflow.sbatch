#!/usr/bin/env bash
#SBATCH --job-name=pe-debug
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --account=rcc-staff
#SBATCH --partition=caslake
#SBATCH --output=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.out
#SBATCH --error=/scratch/midway3/mehta5/flyteTest/FlyteTest/%x.%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # Activate the repo environment so the compute node uses the same dependency
  # set as the local checkout.
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python3 - <<'PY'
from __future__ import annotations

import json
import traceback

from flytetest.server import run_workflow

try:
    result = run_workflow(
        "protein_evidence_alignment",
        {
            "genome": "data/braker3/reference/genome.fa",
            "protein_fastas": ["data/braker3/protein_data/fastas/proteins.fa"],
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))
except Exception as exc:
    print(json.dumps(
        {
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        },
        indent=2,
        sort_keys=True,
    ))
    raise
PY
