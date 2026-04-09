#!/usr/bin/env bash
#SBATCH --job-name=pe-chunk
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
from pathlib import Path

from flyte.io import File

from flytetest.tasks.protein_evidence import (
    _chunk_fasta_paths,
    chunk_protein_fastas,
    exonerate_align_chunk,
    stage_protein_fastas,
)


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


try:
    genome = File(path="data/braker3/reference/genome.fa")
    protein_fastas = [File(path="data/braker3/protein_data/fastas/proteins.fa")]

    staged = stage_protein_fastas.func(protein_fastas=protein_fastas)
    staged_dir = Path(staged.download_sync())

    chunked = chunk_protein_fastas.func(staged_proteins=staged, proteins_per_chunk=1)
    chunk_dir = Path(chunked.download_sync())
    chunk_fastas = _chunk_fasta_paths(chunk_dir)
    if not chunk_fastas:
        raise FileNotFoundError(f"No chunk FASTA files were produced under {chunk_dir}.")

    chunk_path = chunk_fastas[0]
    chunk_alignment = exonerate_align_chunk.func(
        genome=genome,
        protein_chunk=File(path=str(chunk_path)),
        exonerate_sif="",
        exonerate_model="protein2genome",
    )
    alignment_dir = Path(chunk_alignment.download_sync())

    _emit(
        {
            "staged_dir": str(staged_dir),
            "chunk_dir": str(chunk_dir),
            "chunk_path": str(chunk_path),
            "alignment_dir": str(alignment_dir),
            "manifest_path": str(alignment_dir / "run_manifest.json"),
        }
    )
except Exception as exc:
    _emit(
        {
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    )
    raise
PY
