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

# Debug Slurm entrypoint for the full protein-evidence workflow probe when you
# need the cluster-side JSON traceback.
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
from pathlib import Path
import traceback

from flyte.io import File

from flytetest.workflows.protein_evidence import protein_evidence_alignment

try:
    result = protein_evidence_alignment(
        genome=File(path="data/braker3/reference/genome.fa"),
        protein_fastas=[File(path="data/braker3/protein_data/fastas/proteins.fa")],
    )
    result_path = Path(result.download_sync())
    print(json.dumps(
        {
            "output_dir": str(result_path),
            "manifest_path": str(result_path / "run_manifest.json"),
        },
        indent=2,
        sort_keys=True,
    ))
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
