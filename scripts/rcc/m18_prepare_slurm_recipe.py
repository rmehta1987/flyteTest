#!/usr/bin/env python3
"""Prepare a Slurm-profile BUSCO fixture recipe for Milestone 18 retry testing.

    This helper follows the RCC Slurm helper style: the shell or user environment
    chooses concrete cluster paths and resource settings, then the script freezes a
    small BUSCO genome-mode fixture recipe and prints a compact JSON summary.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path

from flytetest.spec_artifacts import (
    SPEC_ARTIFACT_SCHEMA_VERSION,
    SavedWorkflowSpecArtifact,
    save_workflow_spec_artifact,
)
from flytetest.specs import (
    BindingPlan,
    ResourceSpec,
    RuntimeImageSpec,
    TypedFieldSpec,
    WorkflowNodeSpec,
    WorkflowOutputBinding,
    WorkflowSpec,
)


BUSCO_FIXTURE_TASK_NAME = "busco_assess_proteins"


def _repo_relative_path(raw_path: str, repo_root: Path) -> str:
    """Return an absolute path for a repo-relative M18 runtime input."""
    if not raw_path:
        return ""
    path = Path(raw_path)
    return str(path if path.is_absolute() else repo_root / path)


def _created_at() -> str:
    """Return a UTC timestamp suitable for a saved smoke recipe.

    This helper keeps the current behavior explicit and reviewable.

    Returns:
        The returned `str` value used by the caller.
"""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _artifact_destination(repo_root: Path, created_at: str) -> Path:
    """Build a stable, inspectable artifact path for the M18 BUSCO smoke.

    Args:
        repo_root: A value used by the helper.
        created_at: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    digest = hashlib.sha256(f"m18-busco-fixture|{created_at}".encode("utf-8")).hexdigest()[:12]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / ".runtime/specs" / f"{timestamp}-m18-busco-fixture-{digest}.json"


def main() -> int:
    """Freeze the BUSCO fixture recipe, persist a pointer file, and print JSON.

    This helper keeps the current behavior explicit and reviewable.

    Returns:
        The returned `int` value used by the caller.
"""
    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    raw_genome_fasta = Path(
        os.environ.get("FLYTETEST_BUSCO_GENOME_FASTA", "data/busco/test_data/eukaryota/genome.fna")
    )
    genome_fasta = raw_genome_fasta if raw_genome_fasta.is_absolute() else repo_root / raw_genome_fasta
    account = os.environ["FLYTETEST_SLURM_ACCOUNT"]
    cpu = os.environ.get("FLYTETEST_SLURM_CPU", "2")
    busco_cpu = int(os.environ.get("FLYTETEST_BUSCO_CPU", cpu))
    busco_sif = _repo_relative_path(os.environ.get("BUSCO_SIF", ""), repo_root)
    lineage_dataset = os.environ.get("FLYTETEST_BUSCO_LINEAGE_DATASET", "auto-lineage")
    busco_mode = os.environ.get("FLYTETEST_BUSCO_MODE", "geno")

    if not genome_fasta.is_file():
        print(
            json.dumps(
                {
                    "supported": False,
                    "limitations": [
                        f"BUSCO fixture FASTA `{genome_fasta}` does not exist. "
                        "Run scripts/rcc/download_minimal_busco_fixture.sh first.",
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    resource_spec = ResourceSpec(
        cpu=cpu,
        memory=os.environ.get("FLYTETEST_SLURM_MEMORY", "8Gi"),
        partition=os.environ.get("FLYTETEST_SLURM_QUEUE", "caslake"),
        account=account,
        walltime=os.environ.get("FLYTETEST_SLURM_WALLTIME", "00:10:00"),
        notes=(f"job_prefix={os.environ.get('FLYTETEST_SLURM_JOB_PREFIX', 'm18-busco')}",),
    )
    runtime_image = RuntimeImageSpec(apptainer_image=busco_sif or None)
    runtime_bindings: dict[str, object] = {
        "proteins_fasta": genome_fasta,
        "lineage_dataset": lineage_dataset,
        "busco_cpu": busco_cpu,
        "busco_mode": busco_mode,
    }
    if busco_sif:
        runtime_bindings["busco_sif"] = busco_sif

    workflow_spec = WorkflowSpec(
        name="m18_busco_fixture_smoke",
        analysis_goal="Run BUSCO genome-mode fixture smoke for Milestone 18 Slurm retry testing.",
        inputs=(),
        outputs=(
            TypedFieldSpec(
                "busco_run_dir",
                "Dir",
                "Directory containing the BUSCO fixture run plus run_manifest.json.",
            ),
        ),
        nodes=(
            WorkflowNodeSpec(
                name="busco_fixture",
                kind="task",
                reference_name=BUSCO_FIXTURE_TASK_NAME,
                description="Run BUSCO on the upstream eukaryota genome fixture in genome mode.",
                output_names=("busco_run_dir",),
            ),
        ),
        edges=(),
        reusable_registered_refs=(BUSCO_FIXTURE_TASK_NAME,),
        final_output_bindings=(
            WorkflowOutputBinding(
                output_name="busco_run_dir",
                source_node="busco_fixture",
                source_output="busco_run_dir",
                description="BUSCO fixture run directory from the M18 Slurm smoke recipe.",
            ),
        ),
        default_execution_profile="slurm",
        replay_metadata={"selection_mode": "m18_fixture_smoke"},
    )
    binding_plan = BindingPlan(
        target_name=BUSCO_FIXTURE_TASK_NAME,
        target_kind="task",
        execution_profile="slurm",
        resource_spec=resource_spec,
        runtime_image=runtime_image,
        runtime_bindings=runtime_bindings,
        assumptions=(
            "Milestone 18 retry testing uses the official BUSCO eukaryota genome fixture directly.",
            "The production annotation QC workflow still runs BUSCO on repeat-filtered proteins.",
        ),
    )
    created_at = _created_at()
    artifact = SavedWorkflowSpecArtifact(
        schema_version=SPEC_ARTIFACT_SCHEMA_VERSION,
        workflow_spec=workflow_spec,
        binding_plan=binding_plan,
        source_prompt="Run the BUSCO eukaryota genome fixture on Slurm for Milestone 18 retry testing.",
        biological_goal="Run BUSCO genome-mode fixture smoke.",
        planning_outcome="manual_fixture_recipe",
        candidate_outcome="manual_fixture_recipe",
        referenced_registered_stages=(BUSCO_FIXTURE_TASK_NAME,),
        assumptions=(
            "This script prepares a fixture-native smoke recipe instead of requiring a prior repeat-filter run.",
        ),
        created_at=created_at,
        replay_metadata={
            "created_by": "scripts/rcc/m18_prepare_slurm_recipe.py",
            "schema_version": SPEC_ARTIFACT_SCHEMA_VERSION,
        },
    )
    artifact_path = save_workflow_spec_artifact(artifact, _artifact_destination(repo_root, created_at))

    runtime_dir = repo_root / ".runtime/runs"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "latest_m18_slurm_artifact.txt").write_text(f"{artifact_path}\n")

    # This JSON blob is intentionally small: it points to the frozen recipe and
    # echoes the cluster/runtime inputs that matter for the Milestone 18 smoke.
    print(
        json.dumps(
            {
                "artifact_path": str(artifact_path),
                "busco_sif": busco_sif,
                "busco_genome_fasta": str(genome_fasta),
                "lineage_dataset": lineage_dataset,
                "busco_mode": busco_mode,
                "resource_request": resource_spec.to_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
