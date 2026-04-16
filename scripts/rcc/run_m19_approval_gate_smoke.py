#!/usr/bin/env python3
"""Prepare, approve, and submit the Milestone 19 approval-gate Slurm smoke.

This helper freezes a generated workflow artifact for repeat filtering followed
by BUSCO QC, proves that unapproved submission is rejected, writes the durable
approval sidecar, and then submits the approved artifact through Slurm.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path

from flytetest.planner_types import ConsensusAnnotation, ReferenceGenome
from flytetest.planning import plan_typed_request
from flytetest.server import _run_slurm_recipe_impl, approve_composed_recipe
from flytetest.spec_artifacts import artifact_from_typed_plan, save_workflow_spec_artifact


DEFAULT_APPROVAL_PROMPT = "Create a generated WorkflowSpec for repeat filtering and BUSCO QC."
DEFAULT_BUSCO_LINEAGES_TEXT = (
    "eukaryota_odb10,metazoa_odb10,insecta_odb10,arthropoda_odb10,diptera_odb10"
)


def _created_at() -> str:
    """Return a UTC timestamp suitable for the approval-gate smoke."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _artifact_destination(repo_root: Path, created_at: str) -> Path:
    """Build a stable, inspectable artifact path for the approval smoke."""
    digest = hashlib.sha256(f"m19-approval-smoke|{created_at}".encode("utf-8")).hexdigest()[:12]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / ".runtime/specs" / f"{timestamp}-m19-approval-smoke-{digest}.json"


def _repo_path(repo_root: Path, raw_path: str) -> Path:
    """Resolve one repo-relative or absolute path from the helper environment."""
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def main() -> int:
    """Freeze the approval smoke artifact, prove the gate, and submit the approved recipe."""
    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    runtime_dir = repo_root / ".runtime/runs"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    prompt = os.environ.get("FLYTETEST_APPROVAL_PROMPT", DEFAULT_APPROVAL_PROMPT)
    reference_genome = _repo_path(
        repo_root,
        os.environ.get("FLYTETEST_APPROVAL_REFERENCE_GENOME", "data/braker3/reference/genome.fa"),
    )
    annotation_gff3 = _repo_path(
        repo_root,
        os.environ.get("FLYTETEST_APPROVAL_ANNOTATION_GFF3", "results/evm/evm.out.gff3"),
    )

    runtime_bindings: dict[str, object] = {
        "busco_lineages_text": os.environ.get("FLYTETEST_BUSCO_LINEAGES_TEXT", DEFAULT_BUSCO_LINEAGES_TEXT),
        "busco_cpu": int(os.environ.get("FLYTETEST_BUSCO_CPU", os.environ.get("FLYTETEST_SLURM_CPU", "2"))),
    }
    repeatmasker_out = os.environ.get("FLYTETEST_APPROVAL_REPEATMASKER_OUT", "")
    if repeatmasker_out:
        runtime_bindings["repeatmasker_out"] = str(_repo_path(repo_root, repeatmasker_out))
    busco_sif = os.environ.get("BUSCO_SIF", "")
    if busco_sif:
        runtime_bindings["busco_sif"] = busco_sif

    resource_request = {
        "cpu": os.environ.get("FLYTETEST_SLURM_CPU", "2"),
        "memory": os.environ.get("FLYTETEST_SLURM_MEMORY", "8Gi"),
        "queue": os.environ.get("FLYTETEST_SLURM_QUEUE", "caslake"),
        "account": os.environ.get("FLYTETEST_SLURM_ACCOUNT", "rcc-staff"),
        "walltime": os.environ.get("FLYTETEST_SLURM_WALLTIME", "00:15:00"),
        "notes": (f"job_prefix={os.environ.get('FLYTETEST_SLURM_JOB_PREFIX', 'm19-approval')}",),
    }

    consensus_annotation = ConsensusAnnotation(
        reference_genome=ReferenceGenome(fasta_path=reference_genome),
        annotation_gff3_path=annotation_gff3,
    )
    typed_plan = plan_typed_request(
        prompt,
        explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        runtime_bindings=runtime_bindings,
        resource_request=resource_request,
        execution_profile="slurm",
        runtime_image={"apptainer_image": busco_sif} if busco_sif else None,
    )
    if not typed_plan.get("supported", False):
        print(json.dumps(typed_plan, indent=2, sort_keys=True))
        return 1

    created_at = _created_at()
    artifact = artifact_from_typed_plan(
        typed_plan,
        created_at=created_at,
        replay_metadata={"created_by": "scripts/rcc/run_m19_approval_gate_smoke.py"},
    )
    artifact = replace(
        artifact,
        binding_plan=replace(
            artifact.binding_plan,
            target_kind="generated_workflow",
            assumptions=tuple(
                dict.fromkeys(
                    (
                        *artifact.binding_plan.assumptions,
                        "This RCC smoke validates composed-recipe approval gating before Slurm submission.",
                        "The submitted composed job may still fail later because the current local handler map does not execute every generated workflow stage.",
                    )
                )
            ),
        ),
        assumptions=tuple(
            dict.fromkeys(
                (
                    *artifact.assumptions,
                    "The approval-gate smoke proves that generated WorkflowSpec artifacts are blocked until a human approval record exists.",
                )
            )
        ),
    )
    artifact_path = save_workflow_spec_artifact(artifact, _artifact_destination(repo_root, created_at))

    blocked = _run_slurm_recipe_impl(artifact_path, run_dir=runtime_dir)
    if blocked.get("supported", False):
        print(
            json.dumps(
                {
                    "supported": False,
                    "artifact_path": str(artifact_path),
                    "limitations": [
                        "The Milestone 19 approval smoke expected the first Slurm submission to be blocked, but it was accepted.",
                    ],
                    "unexpected_submission": blocked,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    approval = approve_composed_recipe(
        str(artifact_path),
        approved_by=os.environ.get("FLYTETEST_APPROVED_BY", "scripts/rcc/run_m19_approval_gate_smoke.py"),
        reason=os.environ.get(
            "FLYTETEST_APPROVAL_REASON",
            "RCC Milestone 19 approval-gate smoke for generated recipe submission.",
        ),
    )
    if not approval.get("supported", False):
        print(json.dumps(approval, indent=2, sort_keys=True))
        return 1

    submitted = _run_slurm_recipe_impl(artifact_path, run_dir=runtime_dir)
    if not submitted.get("supported", False):
        print(json.dumps(submitted, indent=2, sort_keys=True))
        return 1

    run_record_path = Path(str(submitted["run_record_path"]))
    (runtime_dir / "latest_m19_approval_artifact.txt").write_text(f"{artifact_path}\n")
    (runtime_dir / "latest_m19_approval_run_record.txt").write_text(f"{run_record_path}\n")
    (runtime_dir / "latest_m19_approval_record.txt").write_text(f"{approval['approval_path']}\n")

    limitations: list[str] = []
    if not repeatmasker_out:
        limitations.append(
            "No `repeatmasker_out` runtime binding was frozen, so this smoke validates approval enforcement and scheduler submission only."
        )
    if not annotation_gff3.exists():
        limitations.append(
            f"Default annotation GFF3 `{annotation_gff3}` was not present locally; the generated artifact remains reviewable because planning is metadata-only."
        )

    print(
        json.dumps(
            {
                "approval_path": approval["approval_path"],
                "artifact_path": str(artifact_path),
                "approval_required_block_reason": blocked.get("limitations", [None])[0],
                "approved_at": approval["approved_at"],
                "approved_by": approval["approved_by"],
                "job_id": submitted["job_id"],
                "limitations": limitations,
                "preapproval_blocked": True,
                "run_record_path": str(run_record_path),
                "runtime_bindings": runtime_bindings,
                "stderr": submitted["execution_result"].get("stderr", ""),
                "stdout": submitted["execution_result"].get("stdout", ""),
                "workflow_name": artifact.workflow_spec.name,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())