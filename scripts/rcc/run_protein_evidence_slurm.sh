#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Defaults chosen for the RCC cluster so the recipe can submit without ad hoc
# shell snippets. Override any of these before running the script if needed.
export FLYTETEST_SLURM_ACCOUNT="${FLYTETEST_SLURM_ACCOUNT:-rcc-staff}"
export FLYTETEST_SLURM_QUEUE="${FLYTETEST_SLURM_QUEUE:-caslake}"
export FLYTETEST_SLURM_WALLTIME="${FLYTETEST_SLURM_WALLTIME:-02:00:00}"
export FLYTETEST_SLURM_CPU="${FLYTETEST_SLURM_CPU:-8}"
export FLYTETEST_SLURM_MEMORY="${FLYTETEST_SLURM_MEMORY:-32Gi}"
export FLYTETEST_SLURM_JOB_PREFIX="${FLYTETEST_SLURM_JOB_PREFIX:-pe}"
export FLYTETEST_REPO_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

RUN_RECORD_POINTER="$REPO_ROOT/.runtime/runs/latest_protein_evidence_slurm_run_record.txt"
ARTIFACT_POINTER="$REPO_ROOT/.runtime/runs/latest_protein_evidence_slurm_artifact.txt"
mkdir -p "$(dirname "$RUN_RECORD_POINTER")"

if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # Activate the repo environment when it exists so the cluster run uses the
  # same pinned dependencies as the local workspace.
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

from flytetest.server import _prepare_run_recipe_impl, _run_slurm_recipe_impl

repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
prompt = os.environ.get(
    "FLYTETEST_SLURM_PROMPT",
    "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa",
)

resource_request = {
    "cpu": os.environ.get("FLYTETEST_SLURM_CPU", "8"),
    "memory": os.environ.get("FLYTETEST_SLURM_MEMORY", "32Gi"),
    "queue": os.environ.get("FLYTETEST_SLURM_QUEUE", "caslake"),
    "walltime": os.environ.get("FLYTETEST_SLURM_WALLTIME", "02:00:00"),
    "notes": (
        f"job_prefix={os.environ.get('FLYTETEST_SLURM_JOB_PREFIX', 'pe')}",
    ),
}

prepared = _prepare_run_recipe_impl(
    prompt,
    execution_profile="slurm",
    resource_request=resource_request,
    recipe_dir=repo_root / ".runtime/specs",
)
if not prepared["supported"]:
    print(json.dumps(prepared, indent=2, sort_keys=True))
    raise SystemExit(1)

submitted = _run_slurm_recipe_impl(
    prepared["artifact_path"],
    run_dir=repo_root / ".runtime/runs",
)
if not submitted["supported"]:
    print(json.dumps(submitted, indent=2, sort_keys=True))
    raise SystemExit(1)

run_record_path = Path(submitted["run_record_path"])
artifact_path = Path(prepared["artifact_path"])

(repo_root / ".runtime/runs" / "latest_protein_evidence_slurm_run_record.txt").write_text(f"{run_record_path}\n")
(repo_root / ".runtime/runs" / "latest_protein_evidence_slurm_artifact.txt").write_text(f"{artifact_path}\n")

print(json.dumps({
    "artifact_path": str(artifact_path),
    "job_id": submitted["job_id"],
    "run_record_path": str(run_record_path),
    "stdout": submitted["execution_result"].get("stdout", ""),
    "stderr": submitted["execution_result"].get("stderr", ""),
}, indent=2, sort_keys=True))
PY
