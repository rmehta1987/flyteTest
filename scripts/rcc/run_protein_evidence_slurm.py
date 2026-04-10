#!/usr/bin/env python3
"""Prepare and submit the protein-evidence Slurm recipe.

This helper is called by `scripts/rcc/run_protein_evidence_slurm.sh` after the
shell wrapper has chosen repo-relative defaults and activated the expected
Python environment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from flytetest.server import _prepare_run_recipe_impl, _run_slurm_recipe_impl


def main() -> int:
    """Freeze the Slurm recipe, submit it, persist pointer files, and print JSON."""
    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    prompt = os.environ.get(
        "FLYTETEST_SLURM_PROMPT",
        "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa",
    )
    exonerate_sif = os.environ.get("EXONERATE_SIF", "")

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
        runtime_bindings={"exonerate_sif": exonerate_sif} if exonerate_sif else None,
        resource_request=resource_request,
        recipe_dir=repo_root / ".runtime/specs",
    )
    if not prepared["supported"]:
        print(json.dumps(prepared, indent=2, sort_keys=True))
        return 1

    submitted = _run_slurm_recipe_impl(
        prepared["artifact_path"],
        run_dir=repo_root / ".runtime/runs",
    )
    if not submitted["supported"]:
        print(json.dumps(submitted, indent=2, sort_keys=True))
        return 1

    run_record_path = Path(submitted["run_record_path"])
    artifact_path = Path(prepared["artifact_path"])
    runtime_dir = repo_root / ".runtime/runs"

    (runtime_dir / "latest_protein_evidence_slurm_run_record.txt").write_text(f"{run_record_path}\n")
    (runtime_dir / "latest_protein_evidence_slurm_artifact.txt").write_text(f"{artifact_path}\n")

    # This JSON blob is the user-facing submit summary. It is intentionally
    # small: it points to the saved recipe, durable run record, accepted Slurm
    # job ID, and the scheduler submission stdout/stderr captured by the server.
    print(
        json.dumps(
            {
                "artifact_path": str(artifact_path),
                "job_id": submitted["job_id"],
                "run_record_path": str(run_record_path),
                "stdout": submitted["execution_result"].get("stdout", ""),
                "stderr": submitted["execution_result"].get("stderr", ""),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
