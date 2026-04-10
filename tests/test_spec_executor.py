"""Synthetic coverage for saved workflow-spec executor behavior.

These tests cover the local saved-spec executor path plus the later Slurm
submission, reconciliation, and cancellation helpers without requiring
external bioinformatics tools. Registered stage handlers are fake, but the
executors still use saved `BindingPlan` data, resolver inputs, registry
references, durable run records, and manifest-shaped result directories.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.planner_types import ConsensusAnnotation, QualityAssessmentTarget, ReferenceGenome
from flytetest.planning import plan_typed_request
from flytetest.spec_artifacts import artifact_from_typed_plan, save_workflow_spec_artifact
from flytetest.spec_executor import (
    DEFAULT_SLURM_RUN_RECORD_FILENAME,
    LocalNodeExecutionRequest,
    LocalWorkflowSpecExecutor,
    SlurmWorkflowSpecExecutor,
    load_slurm_run_record,
    parse_sbatch_job_id,
)


def _artifact_with_runtime_bindings(tmp_path: Path):
    """Build one generated-spec artifact with enough runtime values to run locally."""
    reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
    consensus_annotation = ConsensusAnnotation(
        reference_genome=reference_genome,
        annotation_gff3_path=Path("results/evm/evm.out.gff3"),
    )
    typed_plan = plan_typed_request(
        "Create a generated WorkflowSpec for repeat filtering and BUSCO QC.",
        explicit_bindings={"ConsensusAnnotation": consensus_annotation},
    )
    artifact = artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")
    binding_plan = replace(
        artifact.binding_plan,
        runtime_bindings={
            "repeat_filtering.repeatmasker_out": str(tmp_path / "repeatmasker.out"),
            "busco_qc.busco_lineages_text": "embryophyta_odb10",
        },
    )
    return replace(artifact, binding_plan=binding_plan), consensus_annotation


def _busco_artifact_with_runtime_bindings(tmp_path: Path):
    """Build one BUSCO artifact with a manifest-backed quality target and runtime settings."""
    result_dir = tmp_path / "repeat_filter_results"
    result_dir.mkdir()
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_repeat_filtering",
                "assumptions": ["Repeat-filtered outputs are QC-ready."],
                "inputs": {"reference_genome": "data/braker3/reference/genome.fa"},
                "outputs": {
                    "all_repeats_removed_gff3": str(result_dir / "all_repeats_removed.gff3"),
                    "final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                },
            },
            indent=2,
        )
    )
    target = QualityAssessmentTarget(
        source_result_dir=result_dir,
        source_manifest_path=result_dir / "run_manifest.json",
        annotation_gff3_path=result_dir / "all_repeats_removed.gff3",
        proteins_fasta_path=result_dir / "all_repeats_removed.proteins.fa",
    )
    typed_plan = plan_typed_request(
        "Run BUSCO quality assessment on the annotation.",
        explicit_bindings={"QualityAssessmentTarget": target.to_dict()},
        runtime_bindings={
            "busco_lineages_text": "embryophyta_odb10",
            "busco_sif": "busco.sif",
            "busco_cpu": 12,
        },
        resource_request={"cpu": 12, "memory": "48Gi"},
        runtime_image={"apptainer_image": "busco.sif"},
    )
    artifact = artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")
    return artifact, target


def _slurm_busco_artifact_with_runtime_bindings(tmp_path: Path):
    """Build one Slurm-profile BUSCO artifact for submission tests."""
    result_dir = tmp_path / "repeat_filter_results"
    result_dir.mkdir()
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_repeat_filtering",
                "assumptions": ["Repeat-filtered outputs are QC-ready."],
                "inputs": {"reference_genome": "data/braker3/reference/genome.fa"},
                "outputs": {
                    "all_repeats_removed_gff3": str(result_dir / "all_repeats_removed.gff3"),
                    "final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                },
            },
            indent=2,
        )
    )
    typed_plan = plan_typed_request(
        "Run BUSCO quality assessment on the annotation using execution profile slurm.",
        manifest_sources=(result_dir,),
        runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
        resource_request={"cpu": 20, "memory": "80Gi", "queue": "batch", "walltime": "04:00:00"},
        execution_profile="slurm",
    )
    return artifact_from_typed_plan(typed_plan, created_at="2026-04-08T12:00:00Z")


def _quality_target_artifact(
    prompt: str,
    target: QualityAssessmentTarget,
    *,
    runtime_bindings: dict[str, object] | None = None,
):
    """Build a direct registered-workflow artifact from one quality target."""
    typed_plan = plan_typed_request(
        prompt,
        explicit_bindings={"QualityAssessmentTarget": target.to_dict()},
        runtime_bindings=runtime_bindings or {},
    )
    return artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")


class SpecExecutorTests(TestCase):
    """Checks for the saved-spec local executor path."""

    def test_executes_saved_busco_spec_with_synthetic_registered_handler(self) -> None:
        """Run a saved BUSCO recipe and derive the repeat-filter input from the target."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact, target = _busco_artifact_with_runtime_bindings(tmp_path)
            calls: list[tuple[str, dict[str, object]]] = []

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                calls.append((request.node.reference_name, dict(request.inputs)))
                self.assertEqual(request.inputs["repeat_filter_results"], tmp_path / "repeat_filter_results")
                self.assertEqual(request.inputs["busco_lineages_text"], "embryophyta_odb10")
                self.assertEqual(request.inputs["busco_sif"], "busco.sif")
                self.assertEqual(request.inputs["busco_cpu"], 12)
                self.assertEqual(request.execution_profile, "local")
                self.assertEqual(request.resource_spec.cpu, "12")
                self.assertEqual(request.resource_spec.memory, "48Gi")
                self.assertEqual(request.runtime_image.apptainer_image, "busco.sif")
                result_dir = tmp_path / "busco_results"
                result_dir.mkdir()
                (result_dir / "run_manifest.json").write_text(
                    json.dumps(
                        {
                            "workflow": "annotation_qc_busco",
                            "inputs": {
                                "repeat_filter_results": str(request.inputs["repeat_filter_results"]),
                                "busco_lineages_text": request.inputs["busco_lineages_text"],
                                "busco_cpu": request.inputs["busco_cpu"],
                            },
                            "outputs": {"results_dir": str(result_dir)},
                        },
                        indent=2,
                    )
                )
                return {"results_dir": result_dir}

            executor = LocalWorkflowSpecExecutor({"annotation_qc_busco": busco_handler})
            result = executor.execute(artifact)

        self.assertTrue(result.supported)
        self.assertEqual([reference for reference, _ in calls], ["annotation_qc_busco"])
        self.assertEqual(result.workflow_name, "select_annotation_qc_busco")
        self.assertEqual(result.execution_profile, "local")
        self.assertEqual(result.resource_spec.memory, "48Gi")
        self.assertEqual(result.runtime_image.apptainer_image, "busco.sif")
        self.assertEqual(result.final_outputs["results_dir"].name, "busco_results")
        self.assertEqual(result.resolved_planner_inputs["QualityAssessmentTarget"]["source_result_dir"], str(target.source_result_dir))
        self.assertEqual(result.node_results[0].manifest_paths["results_dir"].name, "run_manifest.json")

    def test_executes_saved_eggnog_spec_with_synthetic_registered_handler(self) -> None:
        """Run a saved EggNOG recipe and derive repeat-filter inputs from the target."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repeat_dir = tmp_path / "repeat_filter_results"
            repeat_dir.mkdir()
            target = QualityAssessmentTarget(
                source_result_dir=repeat_dir,
                source_manifest_path=repeat_dir / "run_manifest.json",
                proteins_fasta_path=repeat_dir / "all_repeats_removed.proteins.fa",
            )
            artifact = _quality_target_artifact(
                "Run EggNOG functional annotation on the repeat-filtered proteins.",
                target,
                runtime_bindings={
                    "eggnog_data_dir": "/db/eggnog",
                    "eggnog_sif": "eggnog.sif",
                    "eggnog_cpu": 16,
                    "eggnog_database": "Diptera",
                },
            )
            calls: list[dict[str, object]] = []

            def eggnog_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                calls.append(dict(request.inputs))
                result_dir = tmp_path / "eggnog_results"
                result_dir.mkdir()
                (result_dir / "run_manifest.json").write_text('{"workflow": "annotation_functional_eggnog"}\n')
                return {"results_dir": result_dir}

            result = LocalWorkflowSpecExecutor({"annotation_functional_eggnog": eggnog_handler}).execute(artifact)

        self.assertTrue(result.supported)
        self.assertEqual(
            calls[0],
            {
                "repeat_filter_results": repeat_dir,
                "eggnog_data_dir": "/db/eggnog",
                "eggnog_sif": "eggnog.sif",
                "eggnog_cpu": 16,
                "eggnog_database": "Diptera",
            },
        )
        self.assertEqual(result.final_outputs["results_dir"].name, "eggnog_results")

    def test_executes_saved_agat_specs_with_synthetic_registered_handlers(self) -> None:
        """Map EggNOG and AGAT conversion targets into the concrete AGAT inputs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eggnog_dir = tmp_path / "eggnog_results"
            conversion_dir = tmp_path / "agat_conversion_results"
            eggnog_dir.mkdir()
            conversion_dir.mkdir()
            eggnog_target = QualityAssessmentTarget(
                source_result_dir=eggnog_dir,
                source_manifest_path=eggnog_dir / "run_manifest.json",
                annotation_gff3_path=eggnog_dir / "all_repeats_removed.eggnog.gff3",
            )
            conversion_target = QualityAssessmentTarget(
                source_result_dir=conversion_dir,
                source_manifest_path=conversion_dir / "run_manifest.json",
                annotation_gff3_path=conversion_dir / "all_repeats_removed.agat.gff3",
            )
            stats_artifact = _quality_target_artifact(
                "Run AGAT statistics on the EggNOG-annotated GFF3.",
                eggnog_target,
                runtime_bindings={"annotation_fasta_path": "data/braker3/reference/genome.fa", "agat_sif": "agat.sif"},
            )
            convert_artifact = _quality_target_artifact(
                "Run AGAT conversion on the EggNOG-annotated GFF3.",
                eggnog_target,
                runtime_bindings={"agat_sif": "agat.sif"},
            )
            cleanup_artifact = _quality_target_artifact(
                "Run AGAT cleanup on the converted GFF3.",
                conversion_target,
            )
            calls: list[tuple[str, dict[str, object]]] = []

            def handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                calls.append((request.node.reference_name, dict(request.inputs)))
                result_dir = tmp_path / f"{request.node.reference_name}_results"
                result_dir.mkdir()
                (result_dir / "run_manifest.json").write_text(
                    json.dumps({"workflow": request.node.reference_name}, indent=2)
                )
                return {"results_dir": result_dir}

            executor = LocalWorkflowSpecExecutor(
                {
                    "annotation_postprocess_agat": handler,
                    "annotation_postprocess_agat_conversion": handler,
                    "annotation_postprocess_agat_cleanup": handler,
                }
            )
            stats = executor.execute(stats_artifact)
            conversion = executor.execute(convert_artifact)
            cleanup = executor.execute(cleanup_artifact)

        self.assertTrue(stats.supported)
        self.assertTrue(conversion.supported)
        self.assertTrue(cleanup.supported)
        self.assertEqual(
            calls,
            [
                (
                    "annotation_postprocess_agat",
                    {"eggnog_results": eggnog_dir, "annotation_fasta_path": "data/braker3/reference/genome.fa", "agat_sif": "agat.sif"},
                ),
                ("annotation_postprocess_agat_conversion", {"eggnog_results": eggnog_dir, "agat_sif": "agat.sif"}),
                ("annotation_postprocess_agat_cleanup", {"agat_conversion_results": conversion_dir}),
            ],
        )
        self.assertEqual(cleanup.final_outputs["results_dir"].name, "annotation_postprocess_agat_cleanup_results")

    def test_executes_saved_generated_spec_with_synthetic_registered_handlers(self) -> None:
        """Run one composed saved spec and preserve manifest-bearing result outputs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact, consensus_annotation = _artifact_with_runtime_bindings(tmp_path)
            calls: list[tuple[str, dict[str, object]]] = []

            def repeat_filtering_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                calls.append((request.node.reference_name, dict(request.inputs)))
                self.assertEqual(request.inputs["pasa_update_results"]["annotation_gff3_path"], "results/evm/evm.out.gff3")
                self.assertEqual(request.inputs["repeatmasker_out"], str(tmp_path / "repeatmasker.out"))
                result_dir = tmp_path / "repeat_filter_results"
                result_dir.mkdir()
                (result_dir / "run_manifest.json").write_text(
                    json.dumps(
                        {
                            "workflow": "annotation_repeat_filtering",
                            "inputs": request.inputs,
                            "outputs": {"final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa")},
                        },
                        indent=2,
                    )
                )
                return {"results_dir": result_dir}

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                calls.append((request.node.reference_name, dict(request.inputs)))
                self.assertEqual(request.inputs["repeat_filter_results"], tmp_path / "repeat_filter_results")
                self.assertEqual(request.inputs["busco_lineages_text"], "embryophyta_odb10")
                result_dir = tmp_path / "busco_results"
                result_dir.mkdir()
                (result_dir / "run_manifest.json").write_text(
                    json.dumps(
                        {
                            "workflow": "annotation_qc_busco",
                            "inputs": {"repeat_filter_results": str(request.inputs["repeat_filter_results"])},
                            "outputs": {"busco_summary": str(result_dir / "busco_summary.txt")},
                        },
                        indent=2,
                    )
                )
                return {"results_dir": result_dir}

            executor = LocalWorkflowSpecExecutor(
                {
                    "annotation_repeat_filtering": repeat_filtering_handler,
                    "annotation_qc_busco": busco_handler,
                }
            )
            result = executor.execute(
                artifact,
                explicit_bindings={"ConsensusAnnotation": consensus_annotation},
            )

        self.assertTrue(result.supported)
        self.assertEqual([reference for reference, _ in calls], ["annotation_repeat_filtering", "annotation_qc_busco"])
        self.assertEqual(result.workflow_name, "repeat_filter_then_busco_qc")
        self.assertEqual(result.final_outputs["results_dir"].name, "busco_results")
        self.assertEqual(result.node_results[0].manifest_paths["results_dir"].name, "run_manifest.json")
        self.assertEqual(result.node_results[1].manifest_paths["results_dir"].name, "run_manifest.json")
        self.assertEqual(result.resolved_planner_inputs["ConsensusAnnotation"]["annotation_gff3_path"], "results/evm/evm.out.gff3")

    def test_executor_reports_missing_resolver_input_before_running_handlers(self) -> None:
        """Use the resolver path and stop cleanly when saved inputs cannot resolve."""
        with tempfile.TemporaryDirectory() as tmp:
            artifact, _ = _artifact_with_runtime_bindings(Path(tmp))
            artifact = replace(
                artifact,
                binding_plan=replace(artifact.binding_plan, explicit_user_bindings={}),
            )

            executor = LocalWorkflowSpecExecutor(
                {
                    "annotation_repeat_filtering": lambda request: {"results_dir": Path("should_not_run")},
                    "annotation_qc_busco": lambda request: {"results_dir": Path("should_not_run")},
                }
            )
            result = executor.execute(artifact)

        self.assertFalse(result.supported)
        self.assertEqual(result.node_results, ())
        self.assertIn("No ConsensusAnnotation", result.limitations[0])

    def test_executor_reports_missing_registered_handler(self) -> None:
        """Validate that saved specs only run through explicitly registered handlers."""
        with tempfile.TemporaryDirectory() as tmp:
            artifact, consensus_annotation = _artifact_with_runtime_bindings(Path(tmp))

            executor = LocalWorkflowSpecExecutor({"annotation_repeat_filtering": lambda request: {"results_dir": Path(tmp)}})
            result = executor.execute(
                artifact,
                explicit_bindings={"ConsensusAnnotation": consensus_annotation},
            )

        self.assertFalse(result.supported)
        self.assertEqual(result.node_results[0].reference_name, "annotation_repeat_filtering")
        self.assertIn("annotation_qc_busco", result.limitations[0])

    def test_parse_sbatch_job_id_accepts_standard_output(self) -> None:
        """Recover the durable scheduler ID from sbatch output."""
        self.assertEqual(parse_sbatch_job_id("Submitted batch job 12345\n"), "12345")

    def test_slurm_script_rendering_is_deterministic(self) -> None:
        """Render the same frozen recipe into the same Slurm script text."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=Path("/repo/flyteTest"),
                python_executable="/repo/flyteTest/.venv/bin/python",
                command_available=lambda command: True,
            )

            first = executor.render_script(
                artifact_path,
                run_id="run-1",
                stdout_path=Path("/runs/run-1/slurm-%j.out"),
                stderr_path=Path("/runs/run-1/slurm-%j.err"),
            )
            second = executor.render_script(
                artifact_path,
                run_id="run-1",
                stdout_path=Path("/runs/run-1/slurm-%j.out"),
                stderr_path=Path("/runs/run-1/slurm-%j.err"),
            )

        self.assertEqual(first, second)
        self.assertIn("#SBATCH --partition=batch", first)
        self.assertIn("#SBATCH --account=rcc-staff", first)
        self.assertIn("#SBATCH --cpus-per-task=20", first)
        self.assertIn("#SBATCH --mem=80G", first)
        self.assertIn("module load python/3.11.9", first)
        self.assertIn("source", first)
        self.assertIn("run_local_recipe", first)
        self.assertIn(str(artifact_path), first)

    def test_slurm_executor_persists_run_record_after_submission(self) -> None:
        """Submit through a fake sbatch runner and persist the accepted run record."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            captured: dict[str, object] = {}

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                captured["args"] = args
                captured.update(kwargs)
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 98765\n", stderr="")

            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                python_executable="/usr/bin/python3",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            ).submit(artifact_path)
            script_exists = result.run_record.script_path.exists()
            record_exists = result.run_record.run_record_path.exists()
            record_payload = json.loads(result.run_record.run_record_path.read_text())

        self.assertTrue(result.supported)
        self.assertEqual(result.run_record.job_id, "98765")
        self.assertEqual(result.run_record.execution_profile, "slurm")
        self.assertEqual(result.run_record.resource_spec.queue, "batch")
        self.assertEqual(result.run_record.resource_spec.account, "rcc-staff")
        self.assertTrue(script_exists)
        self.assertTrue(record_exists)
        self.assertEqual(Path(captured["args"][1]), result.run_record.script_path)
        self.assertEqual(record_payload["schema_version"], "slurm-run-record-v1")
        self.assertEqual(record_payload["job_id"], "98765")
        self.assertEqual(record_payload["resource_spec"]["memory"], "80Gi")
        self.assertEqual(record_payload["resource_spec"]["account"], "rcc-staff")
        self.assertEqual(result.run_record.run_record_path.name, DEFAULT_SLURM_RUN_RECORD_FILENAME)

    def test_slurm_reconcile_updates_running_job_record(self) -> None:
        """Reconcile a submitted run record with live scheduler state."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 11111\n", stderr="")

            scheduler_calls: list[list[str]] = []

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                scheduler_calls.append(args)
                if args[0] == "squeue":
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="RUNNING\n", stderr="")
                if args[0] == "scontrol":
                    return subprocess.CompletedProcess(
                        args=args,
                        returncode=0,
                        stdout=f"JobId=11111 JobState=RUNNING ExitCode=0:0 StdOut={tmp_path / 'job.out'} StdErr={tmp_path / 'job.err'} Reason=None\n",
                        stderr="",
                    )
                if args[0] == "sacct":
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="11111|RUNNING|0:0\n", stderr="")
                raise AssertionError(args)

            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                scheduler_runner=fake_scheduler,
                command_available=lambda command: True,
            )
            submitted = executor.submit(artifact_path)
            status = executor.reconcile(submitted.run_record.run_record_path)
            reloaded = load_slurm_run_record(submitted.run_record.run_record_path)

        self.assertTrue(status.supported)
        self.assertEqual([call[0] for call in scheduler_calls], ["squeue", "scontrol", "sacct"])
        self.assertEqual(status.run_record.scheduler_state, "RUNNING")
        self.assertEqual(status.run_record.scheduler_state_source, "squeue")
        self.assertEqual(status.run_record.scheduler_exit_code, "0:0")
        self.assertEqual(status.run_record.stdout_path, tmp_path / "job.out")
        self.assertEqual(status.run_record.stderr_path, tmp_path / "job.err")
        self.assertEqual(reloaded.scheduler_state, "RUNNING")

    def test_slurm_reconcile_uses_sacct_for_terminal_state_when_live_queue_is_empty(self) -> None:
        """Recover terminal state from accounting when the live queue has no row."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 22222\n", stderr="")

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                if args[0] == "squeue":
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
                if args[0] == "scontrol":
                    return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="Invalid job id specified\n")
                if args[0] == "sacct":
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="22222|COMPLETED|0:0\n", stderr="")
                raise AssertionError(args)

            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                scheduler_runner=fake_scheduler,
                command_available=lambda command: True,
            )
            submitted = executor.submit(artifact_path)
            status = executor.reconcile(submitted.run_record.run_record_path)

        self.assertTrue(status.supported)
        self.assertEqual(status.run_record.scheduler_state, "COMPLETED")
        self.assertEqual(status.run_record.final_scheduler_state, "COMPLETED")
        self.assertEqual(status.run_record.scheduler_state_source, "sacct")
        self.assertEqual(status.run_record.scheduler_exit_code, "0:0")

    def test_slurm_cancel_records_requested_cancellation(self) -> None:
        """Request cancellation through scancel and persist the lifecycle marker."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 33333\n", stderr="")

            scheduler_calls: list[list[str]] = []

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                scheduler_calls.append(args)
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                scheduler_runner=fake_scheduler,
                command_available=lambda command: True,
            )
            submitted = executor.submit(artifact_path)
            cancelled = executor.cancel(submitted.run_record.run_record_path)
            reloaded = load_slurm_run_record(submitted.run_record.run_record_path)

        self.assertTrue(cancelled.supported)
        self.assertEqual(scheduler_calls, [["scancel", "33333"]])
        self.assertEqual(cancelled.run_record.scheduler_state, "cancellation_requested")
        self.assertEqual(cancelled.run_record.scheduler_state_source, "scancel")
        self.assertIsNotNone(reloaded.cancellation_requested_at)

    def test_slurm_reconcile_reports_missing_record_without_guessing(self) -> None:
        """Decline status checks when the filesystem record is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            result = SlurmWorkflowSpecExecutor(
                run_root=Path(tmp) / "runs",
                repo_root=Path(tmp),
            ).reconcile(Path(tmp) / "runs" / "missing")

        self.assertFalse(result.supported)
        self.assertIn("No such file", result.limitations[0])

    def test_slurm_submit_reports_missing_sbatch_as_unsupported_environment(self) -> None:
        """Decline submission cleanly when `sbatch` is unavailable on PATH."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                command_available=lambda command: False,
            ).submit(artifact_path)

        self.assertFalse(result.supported)
        self.assertIn("already-authenticated scheduler environment", result.limitations[0])
        self.assertIn("`sbatch`", result.limitations[0])

    def test_slurm_reconcile_reports_missing_scheduler_commands_as_unsupported_environment(self) -> None:
        """Decline monitoring cleanly when no scheduler query command is available."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 66666\n", stderr="")

            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                scheduler_runner=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("scheduler runner should not be called")),
                command_available=lambda command: command == "sbatch",
            )
            submitted = executor.submit(artifact_path)
            status = executor.reconcile(submitted.run_record.run_record_path)

        self.assertFalse(status.supported)
        self.assertIn("already-authenticated scheduler environment", status.limitations[0])
        self.assertIn("`squeue`, `scontrol`, and `sacct`", status.limitations[0])

    def test_slurm_cancel_reports_missing_scancel_as_unsupported_environment(self) -> None:
        """Decline cancellation cleanly when `scancel` is unavailable on PATH."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 77777\n", stderr="")

            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                command_available=lambda command: command == "sbatch",
            )
            submitted = executor.submit(artifact_path)
            cancelled = executor.cancel(submitted.run_record.run_record_path)

        self.assertFalse(cancelled.supported)
        self.assertIn("already-authenticated scheduler environment", cancelled.limitations[0])
        self.assertIn("`scancel`", cancelled.limitations[0])
