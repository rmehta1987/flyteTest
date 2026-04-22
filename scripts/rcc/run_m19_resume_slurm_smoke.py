#!/usr/bin/env python3
"""Prepare and submit the Milestone 19 local-to-Slurm resume smoke.

This helper freezes a single-node BUSCO Slurm recipe, writes a matching prior
local run record that marks the BUSCO node complete, and submits the recipe
through Slurm with that local record as the resume source.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path

from flytetest.planning import plan_typed_request
from flytetest.spec_artifacts import artifact_from_typed_plan, save_workflow_spec_artifact
from flytetest.spec_executor import (
    DEFAULT_LOCAL_RUN_RECORD_FILENAME,
    LOCAL_RUN_RECORD_SCHEMA_VERSION,
    LocalNodeExecutionResult,
    LocalRunRecord,
    SlurmWorkflowSpecExecutor,
    save_local_run_record,
)


DEFAULT_BUSCO_LINEAGE = "embryophyta_odb10"


def _created_at() -> str:
    """Return a UTC timestamp suitable for the resume smoke."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _artifact_destination(repo_root: Path, created_at: str) -> Path:
    """Build a stable, inspectable artifact path for the resume smoke."""
    digest = hashlib.sha256(f"m19-resume-smoke|{created_at}".encode("utf-8")).hexdigest()[:12]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / ".runtime/specs" / f"{timestamp}-m19-resume-smoke-{digest}.json"


def _local_run_dir(repo_root: Path, created_at: str) -> Path:
    """Build a unique durable local-run directory for the resume source record."""
    digest = hashlib.sha256(f"m19-resume-source|{created_at}".encode("utf-8")).hexdigest()[:12]
    timestamp = created_at.replace(":", "").replace("-", "").replace("Z", "Z")
    return repo_root / ".runtime/runs" / f"{timestamp}-m19-local-resume-source-{digest}"


def _write_repeat_filter_fixture(results_dir: Path) -> None:
    """Create the minimal repeat-filter bundle used to resolve the BUSCO input."""
    results_dir.mkdir(parents=True, exist_ok=True)
    gff3_path = results_dir / "all_repeats_removed.gff3"
    proteins_path = results_dir / "all_repeats_removed.proteins.fa"
    gff3_path.write_text(
        "##gff-version 3\n"
        "chr1\tFLyteTest\tgene\t1\t9\t.\t+\t.\tID=gene1\n"
        "chr1\tFLyteTest\tmRNA\t1\t9\t.\t+\t.\tID=mrna1;Parent=gene1\n"
    )
    proteins_path.write_text(
        ">gene1\n"
        "MPEPTIDE\n"
    )
    (results_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_repeat_filtering",
                "assumptions": ["Repeat-filtered outputs are QC-ready."],
                "inputs": {"reference_genome": "data/braker3/reference/genome.fa"},
                "outputs": {
                    "all_repeats_removed_gff3": str(gff3_path),
                    "final_proteins_fasta": str(proteins_path),
                },
            },
            indent=2,
        )
    )


def _write_prior_busco_results(results_dir: Path) -> None:
    """Create the minimal BUSCO output bundle reused by the resume source record."""
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "busco_summary.tsv").write_text(
        "lineage\tnotation\n"
        "embryophyta_odb10\tC:100.0%[S:100.0%,D:0.0%],F:0.0%,M:0.0%,n:1\n"
    )
    (results_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_qc_busco",
                "outputs": {
                    "results_dir": str(results_dir),
                    "busco_summary_tsv": str(results_dir / "busco_summary.tsv"),
                },
            },
            indent=2,
        )
    )


def main() -> int:
    """Freeze the resume smoke artifact, write the prior local record, and submit it."""
    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    runtime_dir = repo_root / ".runtime/runs"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    repeat_filter_results = repo_root / "results/m19_resume_smoke/repeat_filter_results"
    _write_repeat_filter_fixture(repeat_filter_results)

    runtime_bindings: dict[str, object] = {
        "busco_lineages_text": os.environ.get("FLYTETEST_BUSCO_LINEAGE_DATASET", DEFAULT_BUSCO_LINEAGE),
    }
    busco_sif = os.environ.get("BUSCO_SIF", "")
    if busco_sif:
        runtime_bindings["busco_sif"] = busco_sif
    busco_cpu = os.environ.get("FLYTETEST_BUSCO_CPU", os.environ.get("FLYTETEST_SLURM_CPU", "2"))
    runtime_bindings["busco_cpu"] = int(busco_cpu)

    resource_request = {
        "cpu": os.environ.get("FLYTETEST_SLURM_CPU", "2"),
        "memory": os.environ.get("FLYTETEST_SLURM_MEMORY", "8Gi"),
        "partition": os.environ.get("FLYTETEST_SLURM_QUEUE", "caslake"),
        "account": os.environ.get("FLYTETEST_SLURM_ACCOUNT", "rcc-staff"),
        "walltime": os.environ.get("FLYTETEST_SLURM_WALLTIME", "00:10:00"),
        "notes": (f"job_prefix={os.environ.get('FLYTETEST_SLURM_JOB_PREFIX', 'm19-resume')}",),
    }

    typed_plan = plan_typed_request(
        "Run BUSCO quality assessment on the annotation using execution profile slurm.",
        manifest_sources=(repeat_filter_results,),
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
        replay_metadata={"created_by": "scripts/rcc/run_m19_resume_slurm_smoke.py"},
    )
    artifact_path = save_workflow_spec_artifact(artifact, _artifact_destination(repo_root, created_at))

    if len(artifact.workflow_spec.nodes) != 1:
        print(
            json.dumps(
                {
                    "supported": False,
                    "artifact_path": str(artifact_path),
                    "limitations": [
                        "The Milestone 19 resume smoke expects a single-node BUSCO workflow artifact.",
                    ],
                    "workflow_nodes": [node.name for node in artifact.workflow_spec.nodes],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    node = artifact.workflow_spec.nodes[0]
    node_output_name = node.output_names[0]
    prior_results_dir = repo_root / "results/m19_resume_smoke/prior_busco_results"
    _write_prior_busco_results(prior_results_dir)

    prior_run_dir = _local_run_dir(repo_root, created_at)
    prior_run_dir.mkdir(parents=True, exist_ok=True)
    prior_record = LocalRunRecord(
        schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
        run_id="m19-local-resume-source",
        workflow_name=artifact.workflow_spec.name,
        run_record_path=prior_run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
        created_at=created_at,
        execution_profile="local",
        resolved_planner_inputs={},
        binding_plan_target=artifact.binding_plan.target_name,
        node_completion_state={node.name: True},
        node_results=(
            LocalNodeExecutionResult(
                node_name=node.name,
                reference_name=node.reference_name,
                outputs={node_output_name: str(prior_results_dir)},
            ),
        ),
        artifact_path=artifact_path,
        final_outputs={
            binding.output_name: str(prior_results_dir)
            for binding in artifact.workflow_spec.final_output_bindings
        },
        completed_at=created_at,
        assumptions=(
            "This synthetic local run record exists solely to validate Milestone 19 local-to-Slurm resume on cluster.",
        ),
    )
    save_local_run_record(prior_record)

    submitted = SlurmWorkflowSpecExecutor(
        run_root=runtime_dir,
        repo_root=repo_root,
    ).submit(artifact_path, resume_from_local_record=prior_run_dir)
    if not submitted.supported or submitted.run_record is None:
        print(
            json.dumps(
                {
                    "supported": False,
                    "artifact_path": str(artifact_path),
                    "limitations": list(submitted.limitations),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    run_record_path = submitted.run_record.run_record_path
    (runtime_dir / "latest_m19_resume_artifact.txt").write_text(f"{artifact_path}\n")
    (runtime_dir / "latest_m19_resume_slurm_run_record.txt").write_text(f"{run_record_path}\n")
    (runtime_dir / "latest_m19_resume_local_run_record.txt").write_text(f"{prior_run_dir}\n")

    print(
        json.dumps(
            {
                "artifact_path": str(artifact_path),
                "expected_behavior": (
                    "The submitted Slurm job should reuse the prior local BUSCO node result and exit successfully without rerunning BUSCO."
                ),
                "job_id": submitted.run_record.job_id,
                "local_resume_node_state": submitted.run_record.local_resume_node_state,
                "local_resume_run_id": submitted.run_record.local_resume_run_id,
                "local_run_record_path": str(prior_run_dir),
                "resume_embedded_in_script": str(prior_run_dir) in submitted.script_text,
                "run_record_path": str(run_record_path),
                "stderr": submitted.scheduler_stderr,
                "stdout": submitted.scheduler_stdout,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())