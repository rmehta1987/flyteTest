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
from flytetest.specs import ResourceSpec
from flytetest.spec_artifacts import (
    artifact_from_typed_plan,
    save_workflow_spec_artifact,
    DURABLE_ASSET_INDEX_SCHEMA_VERSION,
    DEFAULT_DURABLE_ASSET_INDEX_FILENAME,
    DurableAssetRef,
    load_durable_asset_index,
)
from flytetest.spec_executor import (
    DEFAULT_LOCAL_RUN_RECORD_FILENAME,
    DEFAULT_SLURM_MAX_ATTEMPTS,
    DEFAULT_SLURM_MODULE_LOADS,
    DEFAULT_SLURM_RUN_RECORD_FILENAME,
    LOCAL_RUN_RECORD_SCHEMA_VERSION,
    LocalNodeExecutionRequest,
    LocalNodeExecutionResult,
    LocalRunRecord,
    LocalWorkflowSpecExecutor,
    SLURM_RUN_RECORD_SCHEMA_VERSION,
    SlurmWorkflowSpecExecutor,
    classify_slurm_failure,
    load_local_run_record,
    load_slurm_run_record,
    parse_sbatch_job_id,
    render_slurm_script,
    save_local_run_record,
    save_slurm_run_record,
    SlurmRunRecord,
)
from flytetest.staging import StagingFinding, check_offline_staging


def _typed_plan(
    target_name: str,
    *,
    source_prompt: str = "",
    biological_goal: str | None = None,
    **kwargs: object,
) -> dict[str, object]:
    """Build one structured typed plan for executor tests."""
    if biological_goal is None:
        biological_goal = target_name
    return plan_typed_request(
        biological_goal=biological_goal,
        target_name=target_name,
        source_prompt=source_prompt,
        **kwargs,
    )


def _artifact_with_runtime_bindings(tmp_path: Path):
    """Build one generated-spec artifact with enough runtime values to run locally."""
    reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
    consensus_annotation = ConsensusAnnotation(
        reference_genome=reference_genome,
        annotation_gff3_path=Path("results/evm/evm.out.gff3"),
    )
    typed_plan = _typed_plan(
        "repeat_filter_then_busco_qc",
        source_prompt="Create a generated WorkflowSpec for repeat filtering and BUSCO QC.",
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
    typed_plan = _typed_plan(
        "annotation_qc_busco",
        source_prompt="Run BUSCO quality assessment on the annotation.",
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
    typed_plan = _typed_plan(
        "annotation_qc_busco",
        source_prompt="Run BUSCO quality assessment on the annotation using execution profile slurm.",
        manifest_sources=(result_dir,),
        runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
        resource_request={"cpu": 20, "memory": "80Gi", "queue": "batch", "walltime": "04:00:00"},
        execution_profile="slurm",
    )
    return artifact_from_typed_plan(typed_plan, created_at="2026-04-08T12:00:00Z")


def _quality_target_artifact(
    target_name: str,
    prompt: str,
    target: QualityAssessmentTarget,
    *,
    runtime_bindings: dict[str, object] | None = None,
):
    """Build a direct registered-workflow artifact from one quality target."""
    typed_plan = _typed_plan(
        target_name,
        source_prompt=prompt,
        explicit_bindings={"QualityAssessmentTarget": target.to_dict()},
        runtime_bindings=runtime_bindings or {},
    )
    return artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")


class SpecExecutorTests(TestCase):
    """Checks for the saved-spec local executor path.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_executes_saved_busco_spec_with_synthetic_registered_handler(self) -> None:
        """Run a saved BUSCO recipe and derive the repeat-filter input from the target.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact, target = _busco_artifact_with_runtime_bindings(tmp_path)
            calls: list[tuple[str, dict[str, object]]] = []

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                """Capture the BUSCO node inputs and stage a synthetic results directory."""
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
        """Run a saved EggNOG recipe and derive repeat-filter inputs from the target.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
                "annotation_functional_eggnog",
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
                """Capture the EggNOG node inputs and stage a synthetic results directory."""
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
        """Map EggNOG and AGAT conversion targets into the concrete AGAT inputs.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
                "annotation_postprocess_agat",
                "Run AGAT statistics on the EggNOG-annotated GFF3.",
                eggnog_target,
                runtime_bindings={"annotation_fasta_path": "data/braker3/reference/genome.fa", "agat_sif": "agat.sif"},
            )
            convert_artifact = _quality_target_artifact(
                "annotation_postprocess_agat_conversion",
                "Run AGAT conversion on the EggNOG-annotated GFF3.",
                eggnog_target,
                runtime_bindings={"agat_sif": "agat.sif"},
            )
            cleanup_artifact = _quality_target_artifact(
                "annotation_postprocess_agat_cleanup",
                "Run AGAT cleanup on the converted GFF3.",
                conversion_target,
            )
            calls: list[tuple[str, dict[str, object]]] = []

            def handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                """Capture the AGAT node inputs and stage a synthetic results directory."""
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
        """Run one composed saved spec and preserve manifest-bearing result outputs.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact, consensus_annotation = _artifact_with_runtime_bindings(tmp_path)
            calls: list[tuple[str, dict[str, object]]] = []

            def repeat_filtering_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                """Capture the repeat-filtering node inputs and stage a synthetic results directory."""
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
                """Capture the BUSCO node inputs and stage a synthetic results directory."""
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
        """Use the resolver path and stop cleanly when saved inputs cannot resolve.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
        """Validate that saved specs only run through explicitly registered handlers.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
        """Recover the durable scheduler ID from sbatch output.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        self.assertEqual(parse_sbatch_job_id("Submitted batch job 12345\n"), "12345")

    def test_classify_slurm_failure_marks_node_fail_retryable(self) -> None:
        """Treat scheduler infrastructure failures as conservatively retryable.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        record = SlurmRunRecord(
            schema_version=SLURM_RUN_RECORD_SCHEMA_VERSION,
            run_id="run-1",
            recipe_id="recipe",
            workflow_name="annotation_qc_busco",
            artifact_path=Path("/tmp/recipe.json"),
            script_path=Path("/tmp/submit_slurm.sh"),
            stdout_path=Path("/tmp/slurm.out"),
            stderr_path=Path("/tmp/slurm.err"),
            run_record_path=Path("/tmp/slurm_run_record.json"),
            job_id="12345",
            execution_profile="slurm",
            scheduler_state="NODE_FAIL",
            final_scheduler_state="NODE_FAIL",
            scheduler_exit_code="0:0",
            scheduler_reason="Node failure detected by scheduler.",
        )

        classification = classify_slurm_failure(record)

        self.assertEqual(classification.status, "retryable_failure")
        self.assertTrue(classification.retryable)
        self.assertEqual(classification.failure_class, "scheduler_infrastructure")

    def test_slurm_script_rendering_is_deterministic(self) -> None:
        """Render the same frozen recipe into the same Slurm script text.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
        self.assertIn("module load apptainer/1.4.1", first)
        self.assertIn("export FLYTETEST_TMPDIR=", first)
        self.assertIn("export TMPDIR=", first)
        self.assertIn("results/.tmp", first)
        self.assertIn("source", first)
        self.assertIn("run_local_recipe", first)
        self.assertIn(str(artifact_path), first)

    def test_slurm_executor_persists_run_record_after_submission(self) -> None:
        """Submit through a fake sbatch runner and persist the accepted run record.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            captured: dict[str, object] = {}

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
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
        self.assertEqual(result.run_record.retry_policy.max_attempts, DEFAULT_SLURM_MAX_ATTEMPTS)
        self.assertEqual(result.run_record.attempt_number, 1)

    def test_slurm_reconcile_updates_running_job_record(self) -> None:
        """Reconcile a submitted run record with live scheduler state.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 11111\n", stderr="")

            scheduler_calls: list[list[str]] = []

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate scheduler inspection commands with a canned state snapshot."""
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
        """Recover terminal state from accounting when the live queue has no row.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 22222\n", stderr="")

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate scheduler inspection commands with a canned state snapshot."""
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
        """Request cancellation through scancel and persist the lifecycle marker.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 33333\n", stderr="")

            scheduler_calls: list[list[str]] = []

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate scheduler inspection commands with a canned state snapshot."""
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

    def test_slurm_retry_resubmits_retryable_failure_with_linked_child_record(self) -> None:
        """Retry a node-failure record by reusing the frozen saved recipe.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            job_ids = iter(("90001", "90002"))

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=f"Submitted batch job {next(job_ids)}\n",
                    stderr="",
                )

            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            submitted = executor.submit(artifact_path)
            failed_record = replace(
                load_slurm_run_record(submitted.run_record.run_record_path),
                scheduler_state="NODE_FAIL",
                scheduler_state_source="sacct",
                scheduler_exit_code="0:0",
                scheduler_reason="Node failure detected by scheduler.",
                final_scheduler_state="NODE_FAIL",
                failure_classification=None,
            )
            save_slurm_run_record(failed_record)

            retried = executor.retry(failed_record.run_record_path)
            updated_source = load_slurm_run_record(failed_record.run_record_path)
            child_record = load_slurm_run_record(retried.retry_execution.run_record.run_record_path)

        self.assertTrue(retried.supported)
        self.assertEqual(retried.failure_classification.status, "retryable_failure")
        self.assertEqual(updated_source.retry_child_run_record_paths, (child_record.run_record_path,))
        self.assertEqual(child_record.attempt_number, 2)
        self.assertEqual(child_record.retry_parent_run_id, updated_source.run_id)
        self.assertEqual(child_record.retry_parent_run_record_path, updated_source.run_record_path)
        self.assertEqual(child_record.lineage_root_run_id, updated_source.run_id)
        self.assertEqual(child_record.lineage_root_run_record_path, updated_source.run_record_path)
        self.assertEqual(child_record.retry_policy.max_attempts, DEFAULT_SLURM_MAX_ATTEMPTS)
        self.assertEqual(child_record.execution_profile, "slurm")
        self.assertEqual(child_record.artifact_path, updated_source.artifact_path)

    def test_slurm_retry_enforces_attempt_limit(self) -> None:
        """Decline manual retries once the explicit attempt limit is reached.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 90100\n", stderr="")

            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            submitted = executor.submit(artifact_path)
            limited_record = replace(
                load_slurm_run_record(submitted.run_record.run_record_path),
                scheduler_state="NODE_FAIL",
                scheduler_exit_code="0:0",
                scheduler_reason="Node failure detected by scheduler.",
                final_scheduler_state="NODE_FAIL",
                attempt_number=DEFAULT_SLURM_MAX_ATTEMPTS,
                failure_classification=None,
            )
            save_slurm_run_record(limited_record)

            retried = executor.retry(limited_record.run_record_path)

        self.assertFalse(retried.supported)
        self.assertIn(f"attempt {DEFAULT_SLURM_MAX_ATTEMPTS}", retried.limitations[0])

    def test_slurm_retry_declines_stale_parent_record_after_child_exists(self) -> None:
        """Refuse to branch from the same failed parent record twice.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            job_ids = iter(("90201", "90202"))

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=f"Submitted batch job {next(job_ids)}\n",
                    stderr="",
                )

            executor = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            submitted = executor.submit(artifact_path)
            failed_record = replace(
                load_slurm_run_record(submitted.run_record.run_record_path),
                scheduler_state="NODE_FAIL",
                scheduler_exit_code="0:0",
                scheduler_reason="Node failure detected by scheduler.",
                final_scheduler_state="NODE_FAIL",
                failure_classification=None,
            )
            save_slurm_run_record(failed_record)
            first_retry = executor.retry(failed_record.run_record_path)
            second_retry = executor.retry(failed_record.run_record_path)

        self.assertTrue(first_retry.supported)
        self.assertFalse(second_retry.supported)
        self.assertIn("stale parent", second_retry.limitations[0])

    def test_slurm_reconcile_reports_missing_record_without_guessing(self) -> None:
        """Decline status checks when the filesystem record is missing.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = SlurmWorkflowSpecExecutor(
                run_root=Path(tmp) / "runs",
                repo_root=Path(tmp),
            ).reconcile(Path(tmp) / "runs" / "missing")

        self.assertFalse(result.supported)
        self.assertIn("No such file", result.limitations[0])

    def test_slurm_submit_reports_missing_sbatch_as_unsupported_environment(self) -> None:
        """Decline submission cleanly when `sbatch` is unavailable on PATH.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
        """Decline monitoring cleanly when no scheduler query command is available.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
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
        """Decline cancellation cleanly when `scancel` is unavailable on PATH.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
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


class LocalRunRecordTests(TestCase):
    """Phase A checks for durable local run-record persistence and round-trip fidelity.

    These tests cover three properties required before Phase B resume logic can
    be added: (1) a LocalRunRecord serializes and deserializes without loss,
    (2) the schema version is validated on load so stale records are rejected,
    and (3) the executor writes a record to disk when a run_root is configured.
"""

    def _minimal_run_record(self, run_dir: Path) -> LocalRunRecord:
        """Build a minimal LocalRunRecord with all required fields filled.

        Args:
            run_dir: Temporary directory where run_record_path will point.

        Returns:
            A fully populated LocalRunRecord ready for save/load tests.
"""
        node_result = LocalNodeExecutionResult(
            node_name="test_stage",
            reference_name="annotation_qc_busco",
            outputs={"results_dir": str(run_dir / "busco_out")},
            manifest_paths={"results_dir": run_dir / "busco_out" / "run_manifest.json"},
        )
        return LocalRunRecord(
            schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
            run_id="20260412T120000Z-test-workflow-abc123",
            workflow_name="test_workflow",
            run_record_path=run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
            created_at="2026-04-12T12:00:00Z",
            execution_profile="local",
            resolved_planner_inputs={"QualityAssessmentTarget": {"source_result_dir": "/tmp/src"}},
            binding_plan_target="test_target",
            node_completion_state={"test_stage": True},
            node_results=(node_result,),
            artifact_path=run_dir / "workflow_spec_artifact.json",
            final_outputs={"results_dir": str(run_dir / "busco_out")},
            completed_at="2026-04-12T12:00:01Z",
            assumptions=("Test run assumption.",),
        )

    def test_local_run_record_round_trips_cleanly(self) -> None:
        """Save a LocalRunRecord and reload it; all fields must survive the round-trip.

        This test proves that the durable record format is stable and that
        Phase B resume logic can rely on the loaded record matching the original.
"""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_001"
            run_dir.mkdir()

            record = self._minimal_run_record(run_dir)
            saved_path = save_local_run_record(record)

            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path, run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME)

            loaded = load_local_run_record(run_dir)

            self.assertEqual(loaded.schema_version, record.schema_version)
            self.assertEqual(loaded.run_id, record.run_id)
            self.assertEqual(loaded.workflow_name, record.workflow_name)
            self.assertEqual(loaded.execution_profile, record.execution_profile)
            self.assertEqual(loaded.created_at, record.created_at)
            self.assertEqual(loaded.completed_at, record.completed_at)
            self.assertEqual(loaded.binding_plan_target, record.binding_plan_target)
            self.assertEqual(loaded.node_completion_state, {"test_stage": True})
            self.assertEqual(len(loaded.node_results), 1)
            self.assertEqual(loaded.node_results[0].node_name, "test_stage")
            self.assertEqual(loaded.node_results[0].reference_name, "annotation_qc_busco")
            self.assertEqual(
                loaded.node_results[0].manifest_paths["results_dir"],
                run_dir / "busco_out" / "run_manifest.json",
            )
            self.assertEqual(loaded.final_outputs["results_dir"], str(run_dir / "busco_out"))
            self.assertEqual(loaded.assumptions, ("Test run assumption.",))
            self.assertEqual(loaded.artifact_path, run_dir / "workflow_spec_artifact.json")
            self.assertEqual(
                loaded.resolved_planner_inputs["QualityAssessmentTarget"]["source_result_dir"],
                "/tmp/src",
            )

    def test_local_run_record_schema_version_is_validated_on_load(self) -> None:
        """Loading a record with an unrecognised schema version must raise ValueError.

        This test guards the Phase B resume path against silently accepting stale
        or schema-mismatched records that could produce wrong skip decisions.
"""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_002"
            run_dir.mkdir()

            record = self._minimal_run_record(run_dir)
            save_local_run_record(record)

            # Corrupt the schema version in the saved JSON.
            record_path = run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME
            payload = json.loads(record_path.read_text())
            payload["schema_version"] = "local-run-record-v99"
            record_path.write_text(json.dumps(payload))

            with self.assertRaises(ValueError) as ctx:
                load_local_run_record(run_dir)

            self.assertIn("local-run-record-v99", str(ctx.exception))

    def test_local_run_record_is_written_by_executor_when_run_root_is_set(self) -> None:
        """LocalWorkflowSpecExecutor writes a run record when constructed with run_root.

        This test verifies Phase A integration: after successful execution, a
        local_run_record.json must exist under run_root and its node completion
        state must show every node as completed.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact, _ = _busco_artifact_with_runtime_bindings(tmp_path)

            artifact_path = tmp_path / "workflow_spec_artifact.json"
            save_workflow_spec_artifact(artifact, artifact_path)

            busco_out = tmp_path / "busco_results"
            busco_out.mkdir()
            (busco_out / "run_manifest.json").write_text(
                json.dumps({"workflow": "annotation_qc_busco", "outputs": {"results_dir": str(busco_out)}})
            )

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                """Return a synthetic result directory for the BUSCO stage."""
                return {"results_dir": busco_out}

            run_root = tmp_path / "local_runs"
            executor = LocalWorkflowSpecExecutor(
                {"annotation_qc_busco": busco_handler},
                run_root=run_root,
            )
            result = executor.execute(artifact_path)

            # Capture filesystem data inside the with-block before cleanup.
            run_dirs = list(run_root.iterdir()) if run_root.exists() else []
            record_exists = len(run_dirs) == 1 and (run_dirs[0] / DEFAULT_LOCAL_RUN_RECORD_FILENAME).exists()
            record = load_local_run_record(run_dirs[0]) if record_exists else None
            record_payload = json.loads((run_dirs[0] / DEFAULT_LOCAL_RUN_RECORD_FILENAME).read_text()) if record_exists else {}

        self.assertTrue(result.supported)
        self.assertEqual(len(run_dirs), 1, "Expected exactly one run directory under run_root")
        self.assertTrue(record_exists)
        self.assertIsNotNone(record)
        self.assertEqual(record.schema_version, LOCAL_RUN_RECORD_SCHEMA_VERSION)
        self.assertEqual(record.workflow_name, "select_annotation_qc_busco")
        self.assertEqual(record.execution_profile, "local")
        self.assertEqual(record.node_completion_state, {"annotation_qc_busco": True})
        self.assertIsNotNone(record.completed_at)
        self.assertEqual(record.artifact_path, artifact_path)
        self.assertIsNotNone(record.final_outputs.get("results_dir"))
        self.assertEqual(record_payload["schema_version"], LOCAL_RUN_RECORD_SCHEMA_VERSION)

    def test_local_executor_does_not_write_record_without_run_root(self) -> None:
        """LocalWorkflowSpecExecutor must not write any record when run_root is None.

        This guards backward compatibility: existing callers that do not pass
        run_root must see no filesystem side-effects from Phase A changes.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact, _ = _busco_artifact_with_runtime_bindings(tmp_path)

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                """Return a synthetic result directory for the BUSCO stage."""
                busco_out = tmp_path / "busco_results"
                busco_out.mkdir(exist_ok=True)
                return {"results_dir": busco_out}

            # No run_root → falls back to default (None).
            executor = LocalWorkflowSpecExecutor({"annotation_qc_busco": busco_handler})
            result = executor.execute(artifact)

        self.assertTrue(result.supported)
        # No run record files should exist anywhere under tmp_path.
        run_records = list(tmp_path.rglob(DEFAULT_LOCAL_RUN_RECORD_FILENAME))
        self.assertEqual(run_records, [], "Expected no run record files when run_root is None")


class LocalResumeTests(TestCase):
    """Phase B checks for local resume-from-record semantics.

    These tests verify that ``LocalWorkflowSpecExecutor.execute(resume_from=...)``
    correctly skips completed nodes, rejects identity mismatches, records skip
    reasons, and handles partial completion.
    """

    def _run_initial_execution(self, tmp_path: Path):
        """Run one full execution and return the run record directory.

        Returns:
            (artifact_path, run_dir, result) tuple.
        """
        artifact, _ = _busco_artifact_with_runtime_bindings(tmp_path)
        artifact_path = tmp_path / "workflow_spec_artifact.json"
        save_workflow_spec_artifact(artifact, artifact_path)

        busco_out = tmp_path / "busco_results"
        busco_out.mkdir(exist_ok=True)

        def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
            return {"results_dir": busco_out}

        run_root = tmp_path / "local_runs"
        executor = LocalWorkflowSpecExecutor(
            {"annotation_qc_busco": busco_handler},
            run_root=run_root,
        )
        result = executor.execute(artifact_path)
        run_dirs = list(run_root.iterdir())
        return artifact_path, run_dirs[0], result

    def test_resume_from_complete_record_skips_all_nodes(self) -> None:
        """Resuming from a fully complete record should skip all nodes.

        No handler should be called when every node is already marked complete
        in the prior record.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact_path, prior_run_dir, initial_result = self._run_initial_execution(tmp_path)

            handler_called = False

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                nonlocal handler_called
                handler_called = True
                return {"results_dir": tmp_path / "busco_results"}

            run_root = tmp_path / "resume_runs"
            executor = LocalWorkflowSpecExecutor(
                {"annotation_qc_busco": busco_handler},
                run_root=run_root,
            )
            result = executor.execute(artifact_path, resume_from=prior_run_dir)

        self.assertTrue(result.supported)
        self.assertFalse(handler_called, "Handler should not be called for completed nodes")
        self.assertEqual(len(result.node_results), 1)
        self.assertEqual(result.node_results[0].node_name, "annotation_qc_busco")

    def test_resume_records_skip_reasons_in_durable_record(self) -> None:
        """The durable run record written after a resume must include node_skip_reasons.

        Each skipped node should have a human-readable reason referencing the
        prior run ID.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact_path, prior_run_dir, _ = self._run_initial_execution(tmp_path)

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                return {"results_dir": tmp_path / "busco_results"}

            run_root = tmp_path / "resume_runs"
            executor = LocalWorkflowSpecExecutor(
                {"annotation_qc_busco": busco_handler},
                run_root=run_root,
            )
            executor.execute(artifact_path, resume_from=prior_run_dir)

            resume_dirs = list(run_root.iterdir())
            record = load_local_run_record(resume_dirs[0])

        self.assertIn("annotation_qc_busco", record.node_skip_reasons)
        self.assertIn("prior run", record.node_skip_reasons["annotation_qc_busco"].lower())

    def test_resume_rejects_workflow_name_mismatch(self) -> None:
        """Resume must fail when the prior record's workflow name differs.

        This guards against silently reusing outputs from a different workflow.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, prior_run_dir, _ = self._run_initial_execution(tmp_path)

            # Tamper the prior record to have a different workflow name.
            record_path = prior_run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME
            payload = json.loads(record_path.read_text())
            payload["workflow_name"] = "completely_different_workflow"
            record_path.write_text(json.dumps(payload))

            # Build a second artifact in a subdirectory to avoid collisions.
            sub = tmp_path / "retry_inputs"
            sub.mkdir()
            artifact, _ = _busco_artifact_with_runtime_bindings(sub)
            artifact_path = sub / "workflow_spec_artifact.json"
            save_workflow_spec_artifact(artifact, artifact_path)

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                return {"results_dir": tmp_path / "busco_results"}

            executor = LocalWorkflowSpecExecutor(
                {"annotation_qc_busco": busco_handler},
            )
            result = executor.execute(artifact_path, resume_from=prior_run_dir)

        self.assertFalse(result.supported)
        self.assertTrue(any("mismatch" in lim.lower() for lim in result.limitations))

    def test_resume_rejects_artifact_path_mismatch(self) -> None:
        """Resume must fail when the prior record's artifact path differs.

        This prevents stale reuse when a different artifact is submitted.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, prior_run_dir, _ = self._run_initial_execution(tmp_path)

            # Tamper the prior record to have a different artifact path.
            record_path = prior_run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME
            payload = json.loads(record_path.read_text())
            payload["artifact_path"] = "/some/other/artifact.json"
            record_path.write_text(json.dumps(payload))

            # Build a second artifact in a subdirectory to avoid collisions.
            sub = tmp_path / "retry_inputs"
            sub.mkdir()
            artifact, _ = _busco_artifact_with_runtime_bindings(sub)
            artifact_path = sub / "workflow_spec_artifact.json"
            save_workflow_spec_artifact(artifact, artifact_path)

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                return {"results_dir": tmp_path / "busco_results"}

            executor = LocalWorkflowSpecExecutor(
                {"annotation_qc_busco": busco_handler},
            )
            result = executor.execute(artifact_path, resume_from=prior_run_dir)

        self.assertFalse(result.supported)
        self.assertTrue(any("mismatch" in lim.lower() for lim in result.limitations))

    def test_resume_partial_completion_reruns_incomplete_nodes(self) -> None:
        """When a prior record has incomplete nodes, those should be re-executed.

        This simulates a partial run where one node was completed but another
        was not (by tampering with node_completion_state).
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact_path, prior_run_dir, _ = self._run_initial_execution(tmp_path)

            # Tamper the prior record to mark the node as incomplete.
            record_path = prior_run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME
            payload = json.loads(record_path.read_text())
            payload["node_completion_state"]["annotation_qc_busco"] = False
            record_path.write_text(json.dumps(payload))

            handler_called = False

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                nonlocal handler_called
                handler_called = True
                busco_out = tmp_path / "busco_results_new"
                busco_out.mkdir(exist_ok=True)
                return {"results_dir": busco_out}

            run_root = tmp_path / "resume_runs"
            executor = LocalWorkflowSpecExecutor(
                {"annotation_qc_busco": busco_handler},
                run_root=run_root,
            )
            result = executor.execute(artifact_path, resume_from=prior_run_dir)

        self.assertTrue(result.supported)
        self.assertTrue(handler_called, "Handler should be called for incomplete nodes")

    def test_node_skip_reasons_round_trips_through_run_record(self) -> None:
        """node_skip_reasons must survive a save/load round-trip through the durable record."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_rt"
            run_dir.mkdir()
            node_result = LocalNodeExecutionResult(
                node_name="stage_a",
                reference_name="annotation_qc_busco",
                outputs={"out": "val"},
            )
            record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="test-skip-rt",
                workflow_name="test_wf",
                run_record_path=run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-04-12T12:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target="t",
                node_completion_state={"stage_a": True},
                node_results=(node_result,),
                node_skip_reasons={"stage_a": "Reused from prior run abc: node was completed."},
            )
            save_local_run_record(record)
            loaded = load_local_run_record(run_dir)
        self.assertEqual(loaded.node_skip_reasons, {"stage_a": "Reused from prior run abc: node was completed."})


class SlurmResumeFromLocalRecordTests(TestCase):
    """Phase C checks for Slurm resume from a prior local run record.

    These tests verify that ``SlurmWorkflowSpecExecutor.submit()`` accepts
    a ``resume_from_local_record`` parameter, identity-validates the prior
    local record, and records pre-completed node state in the Slurm run record.
    """

    def test_slurm_submit_with_local_resume_records_pre_completed_nodes(self) -> None:
        """Slurm submission with a matching local run record should capture pre-completed state."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            # Create a fake prior local run record that matches the artifact.
            from flytetest.spec_executor import LOCAL_RUN_RECORD_SCHEMA_VERSION, DEFAULT_LOCAL_RUN_RECORD_FILENAME
            prior_run_dir = tmp_path / "prior_run"
            prior_run_dir.mkdir()
            prior_record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="prior-local-run-001",
                workflow_name=artifact.workflow_spec.name,
                run_record_path=prior_run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-04-12T10:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target=artifact.binding_plan.target_name,
                node_completion_state={"annotation_qc_busco": True},
                node_results=(
                    LocalNodeExecutionResult(
                        node_name="annotation_qc_busco",
                        reference_name="annotation_qc_busco",
                        outputs={"results_dir": str(tmp_path / "busco_out")},
                    ),
                ),
                artifact_path=artifact_path,
                completed_at="2026-04-12T10:00:01Z",
            )
            save_local_run_record(prior_record)

            def fake_sbatch(args, **kwargs):
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 55555\n", stderr="")

            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                command_available=lambda cmd: True,
            ).submit(artifact_path, resume_from_local_record=prior_run_dir)

            record = result.run_record

        self.assertTrue(result.supported)
        self.assertEqual(record.local_resume_node_state, {"annotation_qc_busco": True})
        self.assertEqual(record.local_resume_run_id, "prior-local-run-001")
        self.assertTrue(any("prior-local-run-001" in a for a in record.assumptions))
        self.assertIn(str(prior_run_dir), result.script_text)
        self.assertIn("resume_from_local_record", result.script_text)

    def test_slurm_submit_rejects_local_resume_identity_mismatch(self) -> None:
        """Slurm submission must reject a local resume record with a different workflow name."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            prior_run_dir = tmp_path / "prior_run"
            prior_run_dir.mkdir()
            prior_record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="prior-mismatched-run",
                workflow_name="completely_different_workflow",
                run_record_path=prior_run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-04-12T10:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target="other_target",
                node_completion_state={"some_node": True},
                node_results=(),
                artifact_path=artifact_path,
            )
            save_local_run_record(prior_record)

            def fake_sbatch(args, **kwargs):
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 66666\n", stderr="")

            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                command_available=lambda cmd: True,
            ).submit(artifact_path, resume_from_local_record=prior_run_dir)

        self.assertFalse(result.supported)
        self.assertTrue(any("mismatch" in lim.lower() for lim in result.limitations))

    def test_slurm_run_record_local_resume_fields_round_trip(self) -> None:
        """local_resume_node_state and local_resume_run_id must survive save/load."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir = tmp_path / "run_001"
            run_dir.mkdir()
            record = SlurmRunRecord(
                schema_version=SLURM_RUN_RECORD_SCHEMA_VERSION,
                run_id="run-rt-001",
                recipe_id="recipe",
                workflow_name="test_wf",
                artifact_path=Path("/tmp/artifact.json"),
                script_path=Path("/tmp/submit.sh"),
                stdout_path=Path("/tmp/out.log"),
                stderr_path=Path("/tmp/err.log"),
                run_record_path=run_dir / DEFAULT_SLURM_RUN_RECORD_FILENAME,
                job_id="99999",
                execution_profile="slurm",
                local_resume_node_state={"node_a": True, "node_b": False},
                local_resume_run_id="local-prior-xyz",
            )
            save_slurm_run_record(record)
            loaded = load_slurm_run_record(run_dir)
        self.assertEqual(loaded.local_resume_node_state, {"node_a": True, "node_b": False})
        self.assertEqual(loaded.local_resume_run_id, "local-prior-xyz")


class CacheIdentityKeyTests(TestCase):
    """Phase D checks for deterministic cache-key normalization and versioned invalidation.

    These tests verify that ``cache_identity_key()`` produces stable hex digests,
    that cosmetic path differences are normalized away, that genuine semantic
    differences produce different keys, and that the ``handler_schema_version``
    field invalidates otherwise-matching records.
    """

    def test_same_inputs_produce_same_digest(self) -> None:
        """Identical frozen inputs must always yield the same cache key."""
        from flytetest.spec_executor import cache_identity_key
        ws = {"name": "wf", "nodes": [{"name": "n1"}]}
        bp = {"target_name": "t", "runtime_bindings": {"k": "v"}}
        rp = {"genome": "/data/genome.fa"}
        key1 = cache_identity_key(ws, bp, rp)
        key2 = cache_identity_key(ws, bp, rp)
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 16)

    def test_changing_workflow_nodes_produces_different_digest(self) -> None:
        """Altering the workflow spec nodes must change the cache key."""
        from flytetest.spec_executor import cache_identity_key
        ws_a = {"name": "wf", "nodes": [{"name": "n1"}]}
        ws_b = {"name": "wf", "nodes": [{"name": "n1"}, {"name": "n2"}]}
        bp = {"target_name": "t"}
        rp = {}
        self.assertNotEqual(
            cache_identity_key(ws_a, bp, rp),
            cache_identity_key(ws_b, bp, rp),
        )

    def test_changing_runtime_binding_produces_different_digest(self) -> None:
        """A different runtime binding value must change the cache key."""
        from flytetest.spec_executor import cache_identity_key
        ws = {"name": "wf", "nodes": []}
        bp_a = {"target_name": "t", "runtime_bindings": {"k": "v1"}}
        bp_b = {"target_name": "t", "runtime_bindings": {"k": "v2"}}
        rp = {}
        self.assertNotEqual(
            cache_identity_key(ws, bp_a, rp),
            cache_identity_key(ws, bp_b, rp),
        )

    def test_changing_resource_spec_produces_different_digest(self) -> None:
        """A different resource spec must change the cache key."""
        from flytetest.spec_executor import cache_identity_key
        ws = {"name": "wf", "nodes": []}
        bp_a = {"target_name": "t", "resource_spec": {"cpu": 4}}
        bp_b = {"target_name": "t", "resource_spec": {"cpu": 8}}
        rp = {}
        self.assertNotEqual(
            cache_identity_key(ws, bp_a, rp),
            cache_identity_key(ws, bp_b, rp),
        )

    def test_changing_runtime_image_produces_different_digest(self) -> None:
        """A different runtime image must change the cache key."""
        from flytetest.spec_executor import cache_identity_key
        ws = {"name": "wf", "nodes": []}
        bp_a = {"target_name": "t", "runtime_image": {"image": "busco:1.0"}}
        bp_b = {"target_name": "t", "runtime_image": {"image": "busco:2.0"}}
        rp = {}
        self.assertNotEqual(
            cache_identity_key(ws, bp_a, rp),
            cache_identity_key(ws, bp_b, rp),
        )

    def test_cosmetic_repo_root_path_difference_produces_same_digest(self) -> None:
        """Stripping the repo-root prefix must make two checkout paths equivalent."""
        from flytetest.spec_executor import cache_identity_key
        ws = {"name": "wf", "nodes": []}
        bp = {"target_name": "t"}
        rp_a = {"genome": "/home/alice/project/data/genome.fa"}
        rp_b = {"genome": "/home/bob/project/data/genome.fa"}
        key_a = cache_identity_key(ws, bp, rp_a, repo_root="/home/alice/project")
        key_b = cache_identity_key(ws, bp, rp_b, repo_root="/home/bob/project")
        self.assertEqual(key_a, key_b)

    def test_handler_schema_version_change_invalidates_key(self) -> None:
        """Bumping handler_schema_version must produce a different key."""
        from flytetest.spec_executor import cache_identity_key
        ws = {"name": "wf", "nodes": []}
        bp = {"target_name": "t"}
        rp = {}
        key_v1 = cache_identity_key(ws, bp, rp, handler_schema_version="1")
        key_v2 = cache_identity_key(ws, bp, rp, handler_schema_version="2")
        self.assertNotEqual(key_v1, key_v2)

    def test_resume_accepted_when_cache_keys_match(self) -> None:
        """Resume must succeed when the prior record's cache key matches the current key."""
        from flytetest.spec_executor import _validate_resume_identity
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_001"
            run_dir.mkdir()
            record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="run-match",
                workflow_name="wf",
                run_record_path=run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-04-12T12:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target="t",
                node_completion_state={},
                node_results=(),
                artifact_path=run_dir / "artifact.json",
                cache_identity_key="abcd1234abcd1234",
            )
            result = _validate_resume_identity(
                record, "wf", run_dir / "artifact.json",
                current_cache_key="abcd1234abcd1234",
            )
        self.assertIsNone(result)

    def test_resume_rejected_when_cache_keys_differ(self) -> None:
        """Resume must fail with a clear message when cache keys do not match."""
        from flytetest.spec_executor import _validate_resume_identity
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_002"
            run_dir.mkdir()
            record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="run-mismatch",
                workflow_name="wf",
                run_record_path=run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-04-12T12:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target="t",
                node_completion_state={},
                node_results=(),
                artifact_path=run_dir / "artifact.json",
                cache_identity_key="oldkey0000000000",
            )
            result = _validate_resume_identity(
                record, "wf", run_dir / "artifact.json",
                current_cache_key="newkey0000000000",
            )
        self.assertIsNotNone(result)
        self.assertIn("cache identity key mismatch", result)
        self.assertIn("oldkey0000000000", result)
        self.assertIn("newkey0000000000", result)

    def test_cache_key_round_trips_in_local_run_record(self) -> None:
        """cache_identity_key must survive save/load for LocalRunRecord."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_003"
            run_dir.mkdir()
            record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="run-rt-cache",
                workflow_name="wf",
                run_record_path=run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-04-12T12:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target="t",
                node_completion_state={},
                node_results=(),
                cache_identity_key="abc123def4567890",
            )
            save_local_run_record(record)
            loaded = load_local_run_record(run_dir)
        self.assertEqual(loaded.cache_identity_key, "abc123def4567890")

    def test_cache_key_round_trips_in_slurm_run_record(self) -> None:
        """cache_identity_key must survive save/load for SlurmRunRecord."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_004"
            run_dir.mkdir()
            record = SlurmRunRecord(
                schema_version=SLURM_RUN_RECORD_SCHEMA_VERSION,
                run_id="run-rt-slurm-cache",
                recipe_id="recipe",
                workflow_name="wf",
                artifact_path=Path("/tmp/artifact.json"),
                script_path=Path("/tmp/submit.sh"),
                stdout_path=Path("/tmp/out.log"),
                stderr_path=Path("/tmp/err.log"),
                run_record_path=run_dir / DEFAULT_SLURM_RUN_RECORD_FILENAME,
                job_id="12345",
                execution_profile="slurm",
                cache_identity_key="slurm_cache_key00",
            )
            save_slurm_run_record(record)
            loaded = load_slurm_run_record(run_dir)
        self.assertEqual(loaded.cache_identity_key, "slurm_cache_key00")

    def test_executor_persists_cache_key_in_local_run_record(self) -> None:
        """The local executor must persist a non-None cache_identity_key in the run record."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact, _ = _busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = tmp_path / "workflow_spec_artifact.json"
            save_workflow_spec_artifact(artifact, artifact_path)

            busco_out = tmp_path / "busco_results"
            busco_out.mkdir()

            def busco_handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
                return {"results_dir": busco_out}

            run_root = tmp_path / "local_runs"
            executor = LocalWorkflowSpecExecutor(
                {"annotation_qc_busco": busco_handler},
                run_root=run_root,
            )
            executor.execute(artifact_path)

            run_dirs = list(run_root.iterdir())
            record = load_local_run_record(run_dirs[0])

        self.assertIsNotNone(record.cache_identity_key)
        self.assertEqual(len(record.cache_identity_key), 16)


class ModuleLoadsAndResourceOverrideTests(TestCase):
    """M20a tests for ResourceSpec.module_loads, render_slurm_script, and escalation retry.

    Covers:
    - module_loads round-trips through ResourceSpec.from_dict/_coerce_resource_spec
    - merge preserves base module_loads when override is empty
    - render_slurm_script uses custom module_loads when set and falls back to defaults
    - shell-quoting of module names
    - escalation retry (OOM / TIMEOUT) with resource_overrides
    - DEADLINE is not eligible for escalation retry
    - unknown resource_overrides key is rejected before sbatch
    - child resource_overrides round-trips through save/load
"""

    # ------------------------------------------------------------------
    # Data-model tests
    # ------------------------------------------------------------------

    def test_resource_spec_module_loads_round_trips_via_from_dict(self) -> None:
        """ResourceSpec.from_dict restores module_loads for both new and legacy records.

        A new record with an explicit module_loads list must survive a to_dict /
        from_dict round-trip unchanged. A legacy dict without the key must
        deserialize cleanly with the default empty tuple.
"""
        spec = ResourceSpec(cpu="4", memory="16Gi", module_loads=("gcc/11.2", "samtools/1.16"))
        payload = spec.to_dict()
        reloaded = ResourceSpec.from_dict(payload)

        self.assertEqual(reloaded.module_loads, ("gcc/11.2", "samtools/1.16"))

        # Legacy dict without module_loads key must default to empty tuple.
        legacy_payload = {k: v for k, v in payload.items() if k != "module_loads"}
        legacy = ResourceSpec.from_dict(legacy_payload)
        self.assertEqual(legacy.module_loads, ())

    def test_merge_resource_specs_preserves_base_module_loads_when_override_is_empty(self) -> None:
        """_merge_resource_specs keeps base module_loads when the override has none.

        This guards the common case where a per-call resource_request does not
        include module_loads but the registry default does.
"""
        from flytetest.planning import _merge_resource_specs

        base = ResourceSpec(cpu="8", module_loads=("python/3.11.9", "apptainer/1.4.1"))
        override = ResourceSpec(memory="64Gi")

        merged = _merge_resource_specs(base, override)

        self.assertIsNotNone(merged)
        self.assertEqual(merged.module_loads, ("python/3.11.9", "apptainer/1.4.1"))
        self.assertEqual(merged.memory, "64Gi")
        self.assertEqual(merged.cpu, "8")

    def test_merge_resource_specs_override_module_loads_takes_precedence(self) -> None:
        """_merge_resource_specs uses override.module_loads when the override has a value."""
        from flytetest.planning import _merge_resource_specs

        base = ResourceSpec(cpu="8", module_loads=("python/3.11.9",))
        override = ResourceSpec(module_loads=("python/3.12.0", "cuda/12.0"))

        merged = _merge_resource_specs(base, override)

        self.assertIsNotNone(merged)
        self.assertEqual(merged.module_loads, ("python/3.12.0", "cuda/12.0"))

    # ------------------------------------------------------------------
    # render_slurm_script module-load tests
    # ------------------------------------------------------------------

    def test_render_slurm_script_uses_custom_module_loads(self) -> None:
        """Custom module_loads from ResourceSpec appear in the rendered script."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            # Render with a custom ResourceSpec carrying extra modules.
            custom_spec = ResourceSpec(
                cpu="4",
                memory="16Gi",
                queue="batch",
                walltime="01:00:00",
                module_loads=("custom_tool/9.9", "extra_lib/2.0"),
            )
            script = render_slurm_script(
                artifact_path=artifact_path,
                workflow_name="annotation_qc_busco",
                run_id="run-custom",
                stdout_path=Path("/runs/run-custom/slurm-%j.out"),
                stderr_path=Path("/runs/run-custom/slurm-%j.err"),
                resource_spec=custom_spec,
                repo_root=tmp_path,
                python_executable="/usr/bin/python3",
            )

        self.assertIn("module load custom_tool/9.9", script)
        self.assertIn("module load extra_lib/2.0", script)
        # The defaults must NOT appear when custom loads are specified.
        self.assertNotIn("module load python/3.11.9", script)
        self.assertNotIn("module load apptainer/1.4.1", script)

    def test_render_slurm_script_falls_back_to_default_module_loads(self) -> None:
        """A spec with no module_loads renders the DEFAULT_SLURM_MODULE_LOADS."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            bare_spec = ResourceSpec(cpu="4", memory="16Gi", queue="batch", walltime="01:00:00")
            script = render_slurm_script(
                artifact_path=artifact_path,
                workflow_name="annotation_qc_busco",
                run_id="run-bare",
                stdout_path=Path("/runs/run-bare/slurm-%j.out"),
                stderr_path=Path("/runs/run-bare/slurm-%j.err"),
                resource_spec=bare_spec,
                repo_root=tmp_path,
                python_executable="/usr/bin/python3",
            )

        for mod in DEFAULT_SLURM_MODULE_LOADS:
            self.assertIn(f"module load {mod}", script)

    def test_render_slurm_script_shell_quotes_module_names(self) -> None:
        """Module names with spaces are shell-quoted so the rendered script is safe."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            # A module name with a space would break shell parsing unless quoted.
            spec_with_space = ResourceSpec(
                cpu="4",
                memory="16Gi",
                queue="batch",
                module_loads=("tool with spaces/1.0",),
            )
            script = render_slurm_script(
                artifact_path=artifact_path,
                workflow_name="annotation_qc_busco",
                run_id="run-quoted",
                stdout_path=Path("/runs/run-quoted/slurm-%j.out"),
                stderr_path=Path("/runs/run-quoted/slurm-%j.err"),
                resource_spec=spec_with_space,
                repo_root=tmp_path,
                python_executable="/usr/bin/python3",
            )

        # shlex.quote wraps names containing spaces in single quotes.
        self.assertIn("module load 'tool with spaces/1.0'", script)

    # ------------------------------------------------------------------
    # Escalation retry tests
    # ------------------------------------------------------------------

    def _submit_busco_slurm_artifact(
        self, tmp_path: Path, job_id: str
    ) -> tuple[Path, Path]:
        """Return (artifact_path, run_record_path) from a fake sbatch submission."""
        artifact = _slurm_busco_artifact_with_runtime_bindings(tmp_path)
        artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
        result = SlurmWorkflowSpecExecutor(
            run_root=tmp_path / "runs",
            repo_root=tmp_path,
            sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                args=args, returncode=0, stdout=f"Submitted batch job {job_id}\n", stderr=""
            ),
            command_available=lambda _: True,
        ).submit(artifact_path)
        return artifact_path, result.run_record.run_record_path

    def _force_terminal_state(
        self,
        run_record_path: Path,
        *,
        state: str,
        exit_code: str = "1:0",
        reason: str = "",
    ) -> None:
        """Overwrite a submitted run record with a synthetic terminal state."""
        record = load_slurm_run_record(run_record_path)
        forced = record.__class__.from_dict({
            **record.to_dict(),
            "scheduler_state": state,
            "scheduler_exit_code": exit_code,
            "final_scheduler_state": state,
            "scheduler_reason": reason,
            "failure_classification": None,
        })
        save_slurm_run_record(forced)

    def test_oom_with_resource_overrides_escalates_memory_and_records_override(self) -> None:
        """OOM + memory resource_override resubmits with the new memory, records both specs.

        Validates:
        - Child run record resource_spec.memory == the overridden value.
        - Child run record resource_overrides.memory == the overridden value.
        - Rendered sbatch script contains the overridden memory directive.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, run_record_path = self._submit_busco_slurm_artifact(tmp_path, "80001")
            self._force_terminal_state(run_record_path, state="OUT_OF_MEMORY", exit_code="1:0", reason="Out Of Memory")

            retry_job_ids = iter(("80002",))
            retried = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=f"Submitted batch job {next(retry_job_ids)}\n", stderr=""
                ),
                command_available=lambda _: True,
            ).retry(run_record_path, resource_overrides={"memory": "64Gi"})

            child_record = load_slurm_run_record(retried.retry_execution.run_record.run_record_path)
            child_script = child_record.script_path.read_text()

        self.assertTrue(retried.supported)
        # Child resource_spec carries the escalated memory.
        self.assertEqual(child_record.resource_spec.memory, "64Gi")
        # resource_overrides records what the caller supplied.
        self.assertIsNotNone(child_record.resource_overrides)
        self.assertEqual(child_record.resource_overrides.memory, "64Gi")
        # The rendered sbatch directive reflects the escalated value.
        self.assertIn("--mem=64G", child_script)

    def test_timeout_with_walltime_resource_override_escalates_walltime(self) -> None:
        """TIMEOUT + walltime resource_override resubmits with the extended walltime."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, run_record_path = self._submit_busco_slurm_artifact(tmp_path, "81001")
            self._force_terminal_state(run_record_path, state="TIMEOUT", exit_code="0:1")

            retry_job_ids = iter(("81002",))
            retried = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=f"Submitted batch job {next(retry_job_ids)}\n", stderr=""
                ),
                command_available=lambda _: True,
            ).retry(run_record_path, resource_overrides={"walltime": "08:00:00"})

            child_record = load_slurm_run_record(retried.retry_execution.run_record.run_record_path)

        self.assertTrue(retried.supported)
        self.assertEqual(child_record.resource_spec.walltime, "08:00:00")
        self.assertIsNotNone(child_record.resource_overrides)
        self.assertEqual(child_record.resource_overrides.walltime, "08:00:00")

    def test_oom_without_resource_overrides_is_declined_without_escalation(self) -> None:
        """OOM with no resource_overrides must be declined: unchanged behavior."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, run_record_path = self._submit_busco_slurm_artifact(tmp_path, "82001")
            self._force_terminal_state(run_record_path, state="OUT_OF_MEMORY", exit_code="1:0", reason="Out Of Memory")

            retried = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sbatch must not be called")),
                command_available=lambda _: True,
            ).retry(run_record_path)

        self.assertFalse(retried.supported)
        self.assertIn("not retryable", retried.limitations[0])

    def test_deadline_is_declined_even_with_walltime_override(self) -> None:
        """DEADLINE (scheduler-enforced, not walltime-soft) must not be escalated.

        DEADLINE is excluded from the escalation path because it reflects a
        policy-level rejection, not a soft resource exhaustion.  A new
        prepare_run_recipe call is required.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, run_record_path = self._submit_busco_slurm_artifact(tmp_path, "83001")
            self._force_terminal_state(run_record_path, state="DEADLINE", exit_code="0:1")

            retried = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sbatch must not be called")),
                command_available=lambda _: True,
            ).retry(run_record_path, resource_overrides={"walltime": "24:00:00"})

        self.assertFalse(retried.supported)

    def test_unknown_resource_override_key_is_rejected_before_sbatch(self) -> None:
        """An unrecognised resource_overrides key must decline without calling sbatch."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, run_record_path = self._submit_busco_slurm_artifact(tmp_path, "84001")
            self._force_terminal_state(run_record_path, state="NODE_FAIL", exit_code="0:0")

            retried = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sbatch must not be called")),
                command_available=lambda _: True,
            ).retry(run_record_path, resource_overrides={"unknown_field": "value"})

        self.assertFalse(retried.supported)
        self.assertTrue(
            any("unknown_field" in lim or "not supported" in lim or "unsupported" in lim for lim in retried.limitations),
            f"Expected limitation mentioning unknown_field or unsupported, got: {retried.limitations}",
        )

    def test_child_resource_overrides_round_trip_through_save_load(self) -> None:
        """resource_overrides written into a child run record survive a save/load cycle."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, run_record_path = self._submit_busco_slurm_artifact(tmp_path, "85001")
            self._force_terminal_state(run_record_path, state="OUT_OF_MEMORY", exit_code="1:0", reason="Out Of Memory")

            retry_job_ids = iter(("85002",))
            retried = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=f"Submitted batch job {next(retry_job_ids)}\n", stderr=""
                ),
                command_available=lambda _: True,
            ).retry(run_record_path, resource_overrides={"memory": "128Gi", "cpu": "32"})

            child_record_path = retried.retry_execution.run_record.run_record_path
            reloaded = load_slurm_run_record(child_record_path)

        self.assertIsNotNone(reloaded.resource_overrides)
        self.assertEqual(reloaded.resource_overrides.memory, "128Gi")
        self.assertEqual(reloaded.resource_overrides.cpu, "32")


class DurableAssetIndexIntegrationTests(TestCase):
    """M20b checks for durable_asset_index.json written after local execution.

    These tests verify that LocalWorkflowSpecExecutor writes the index sidecar
    alongside local_run_record.json, that index fields match the run record, and
    that pre-M20b run directories load without error.
"""

    def _run_busco_with_run_root(self, tmp_path: Path):
        """Execute the BUSCO spec with run_root and return (run_dir, result)."""
        artifact, _ = _busco_artifact_with_runtime_bindings(tmp_path)
        artifact_path = tmp_path / "workflow_spec_artifact.json"
        save_workflow_spec_artifact(artifact, artifact_path)

        busco_out = tmp_path / "busco_results"
        busco_out.mkdir(exist_ok=True)
        (busco_out / "run_manifest.json").write_text(
            json.dumps({"workflow": "annotation_qc_busco", "outputs": {"results_dir": str(busco_out)}})
        )

        def busco_handler(request: LocalNodeExecutionRequest) -> dict:
            return {"results_dir": busco_out}

        run_root = tmp_path / "local_runs"
        executor = LocalWorkflowSpecExecutor({"annotation_qc_busco": busco_handler}, run_root=run_root)
        result = executor.execute(artifact_path)
        run_dirs = list(run_root.iterdir())
        return run_dirs[0], result

    def test_local_execution_writes_durable_asset_index_alongside_run_record(self) -> None:
        """After a successful local execution the run directory must contain
        durable_asset_index.json next to local_run_record.json.  At minimum the
        entry must have the correct run_id, workflow_name, output_name, and asset_path.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir, result = self._run_busco_with_run_root(tmp_path)
            index_exists = (run_dir / DEFAULT_DURABLE_ASSET_INDEX_FILENAME).exists()
            refs = load_durable_asset_index(run_dir) if index_exists else []
            record = load_local_run_record(run_dir)

        self.assertTrue(result.supported)
        self.assertTrue(index_exists, "durable_asset_index.json must be written next to local_run_record.json")
        self.assertEqual(len(refs), 1)
        ref = refs[0]
        self.assertEqual(ref.run_id, record.run_id)
        self.assertEqual(ref.workflow_name, "select_annotation_qc_busco")
        self.assertEqual(ref.output_name, "results_dir")
        self.assertIsNotNone(ref.asset_path)

    def test_durable_asset_index_fields_match_run_record(self) -> None:
        """The run_id, workflow_name, and created_at fields in the durable asset
        index must be identical to those in the companion local_run_record.json.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir, _ = self._run_busco_with_run_root(tmp_path)
            record = load_local_run_record(run_dir)
            refs = load_durable_asset_index(run_dir)

        self.assertEqual(len(refs), 1)
        ref = refs[0]
        self.assertEqual(ref.run_id, record.run_id)
        self.assertEqual(ref.workflow_name, record.workflow_name)
        self.assertEqual(ref.created_at, record.created_at)
        self.assertEqual(ref.run_record_path, record.run_record_path)

    def test_legacy_run_record_loads_without_durable_index(self) -> None:
        """A pre-M20b run directory with only local_run_record.json must load
        without error.  load_local_run_record must succeed and
        load_durable_asset_index must return [] for the same directory.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_legacy"
            run_dir.mkdir()
            node_result = LocalNodeExecutionResult(
                node_name="annotation_qc_busco",
                reference_name="annotation_qc_busco",
                outputs={"results_dir": str(run_dir / "busco_results")},
            )
            record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="legacy-run-001",
                workflow_name="select_annotation_qc_busco",
                run_record_path=run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-01-01T00:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target="select_annotation_qc_busco",
                node_completion_state={"annotation_qc_busco": True},
                node_results=(node_result,),
            )
            save_local_run_record(record)
            # No durable_asset_index.json is written (simulates pre-M20b run)
            loaded_record = load_local_run_record(run_dir)
            loaded_refs = load_durable_asset_index(run_dir)

        self.assertEqual(loaded_record.run_id, "legacy-run-001")
        self.assertEqual(loaded_refs, [])


def _build_slurm_staging_artifact(
    tmp_path: Path,
    *,
    runtime_images: dict[str, str] | None = None,
    tool_databases: dict[str, str] | None = None,
):
    """Build one Slurm-profile artifact with configurable staging paths for preflight tests."""
    result_dir = tmp_path / "repeat_filter_results_staging"
    result_dir.mkdir(exist_ok=True)
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_repeat_filtering",
                "assumptions": [],
                "inputs": {"reference_genome": "data/braker3/reference/genome.fa"},
                "outputs": {
                    "all_repeats_removed_gff3": str(result_dir / "all_repeats_removed.gff3"),
                    "final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                },
            },
            indent=2,
        )
    )
    typed_plan = _typed_plan(
        "annotation_qc_busco",
        source_prompt="staging preflight test",
        manifest_sources=(result_dir,),
        runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
        resource_request={"cpu": 4, "memory": "16Gi", "queue": "batch", "walltime": "01:00:00"},
        execution_profile="slurm",
        runtime_images=runtime_images if runtime_images is not None else {},
        tool_databases=tool_databases if tool_databases is not None else {},
    )
    return artifact_from_typed_plan(typed_plan, created_at="2026-04-21T00:00:00Z")


class StagingPreflightTests(TestCase):
    """Step 23: SlurmWorkflowSpecExecutor gates sbatch on check_offline_staging.

    These tests keep the current contract explicit and document the pre-submission
    staging gate introduced in Step 23.
"""

    def _fake_sbatch(self, calls: list[list[str]]):
        """Return a fake sbatch runner that records its invocations."""
        def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 99001\n", stderr="")
        return runner

    def test_unreachable_container_blocks_sbatch(self) -> None:
        """An artifact with a non-existent container image path must block sbatch.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        sbatch_calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            valid_db = tmp_path / "busco_db"
            valid_db.mkdir()
            # Override registry defaults: bad container path, valid tool_database.
            artifact = _build_slurm_staging_artifact(
                tmp_path,
                runtime_images={"busco_sif": "/nonexistent/busco.sif"},
                tool_databases={"busco_lineage_dir": str(valid_db)},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=self._fake_sbatch(sbatch_calls),
                command_available=lambda cmd: cmd == "sbatch",
            ).submit(artifact_path, shared_fs_roots=(tmp_path,))

        self.assertFalse(result.supported)
        self.assertEqual(sbatch_calls, [], "sbatch must not be called when staging fails")
        self.assertEqual(len(result.limitations), 1)
        finding_str = result.limitations[0]
        self.assertIn("container", finding_str)
        self.assertIn("busco_sif", finding_str)
        self.assertIn("not_found", finding_str)
        self.assertIsNone(result.run_record, "no run record must be created for a staging failure")

    def test_unreachable_tool_database_blocks_sbatch(self) -> None:
        """An artifact with a non-existent tool_database path must block sbatch.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        sbatch_calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            valid_sif = tmp_path / "busco.sif"
            valid_sif.write_bytes(b"fake-sif")
            # Override registry defaults: valid container path, bad tool_database.
            artifact = _build_slurm_staging_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(valid_sif)},
                tool_databases={"busco_lineage_dir": str(tmp_path / "missing_busco_db")},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=self._fake_sbatch(sbatch_calls),
                command_available=lambda cmd: cmd == "sbatch",
            ).submit(artifact_path, shared_fs_roots=(tmp_path,))

        self.assertFalse(result.supported)
        self.assertEqual(sbatch_calls, [], "sbatch must not be called when staging fails")
        self.assertEqual(len(result.limitations), 1)
        finding_str = result.limitations[0]
        self.assertIn("tool_database", finding_str)
        self.assertIn("busco_lineage_dir", finding_str)
        self.assertIn("not_found", finding_str)

    def test_happy_path_on_shared_fs_root_calls_sbatch(self) -> None:
        """When all paths exist under the shared FS root, sbatch must be called.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        sbatch_calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sif_path = tmp_path / "busco.sif"
            sif_path.write_bytes(b"fake-sif")
            db_path = tmp_path / "busco_db"
            db_path.mkdir()
            # Override both registry defaults with existing paths under tmp_path (shared root).
            artifact = _build_slurm_staging_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(sif_path)},
                tool_databases={"busco_lineage_dir": str(db_path)},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=self._fake_sbatch(sbatch_calls),
                command_available=lambda cmd: cmd == "sbatch",
            ).submit(artifact_path, shared_fs_roots=(tmp_path,))

        self.assertTrue(result.supported)
        self.assertEqual(len(sbatch_calls), 1, "sbatch must be called exactly once for a clean staging check")
        self.assertIsNotNone(result.run_record)

    def test_broken_symlink_surfaces_as_not_readable(self) -> None:
        """A symlink whose target is absent must yield reason='not_readable'.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        sbatch_calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            valid_sif = tmp_path / "busco.sif"
            valid_sif.write_bytes(b"fake-sif")
            link = tmp_path / "link_db"
            link.symlink_to(tmp_path / "nonexistent_target")
            # Override both registry defaults; tool_database is a broken symlink.
            artifact = _build_slurm_staging_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(valid_sif)},
                tool_databases={"busco_lineage_dir": str(link)},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=self._fake_sbatch(sbatch_calls),
                command_available=lambda cmd: cmd == "sbatch",
            ).submit(artifact_path, shared_fs_roots=(tmp_path,))

        self.assertFalse(result.supported)
        self.assertEqual(sbatch_calls, [])
        self.assertEqual(len(result.limitations), 1)
        self.assertIn("not_readable", result.limitations[0])

    def test_symlink_pointing_inside_root_passes(self) -> None:
        """A symlink that resolves inside the shared FS root must pass staging.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        sbatch_calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            valid_sif = tmp_path / "busco.sif"
            valid_sif.write_bytes(b"fake-sif")
            real_db = tmp_path / "real_db"
            real_db.mkdir()
            link = tmp_path / "link_db"
            link.symlink_to(real_db)
            # Override both registry defaults; symlink resolves inside tmp_path (shared root).
            artifact = _build_slurm_staging_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(valid_sif)},
                tool_databases={"busco_lineage_dir": str(link)},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=self._fake_sbatch(sbatch_calls),
                command_available=lambda cmd: cmd == "sbatch",
            ).submit(artifact_path, shared_fs_roots=(tmp_path,))

        self.assertTrue(result.supported)
        self.assertEqual(len(sbatch_calls), 1, "sbatch must be called when symlink resolves inside root")

    def test_symlink_pointing_outside_root_is_blocked(self) -> None:
        """A symlink that resolves outside every shared FS root must fail staging.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        sbatch_calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            tmp_path = Path(tmp)
            valid_sif = tmp_path / "busco.sif"
            valid_sif.write_bytes(b"fake-sif")
            outside_dir = Path(outside_tmp) / "external_db"
            outside_dir.mkdir()
            link = tmp_path / "link_outside"
            link.symlink_to(outside_dir)
            # Override both registry defaults; symlink resolves outside tmp_path (shared root).
            artifact = _build_slurm_staging_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(valid_sif)},
                tool_databases={"busco_lineage_dir": str(link)},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = SlurmWorkflowSpecExecutor(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=self._fake_sbatch(sbatch_calls),
                command_available=lambda cmd: cmd == "sbatch",
            ).submit(artifact_path, shared_fs_roots=(tmp_path,))

        self.assertFalse(result.supported)
        self.assertEqual(sbatch_calls, [])
        self.assertIn("not_on_shared_fs", result.limitations[0])

    def test_local_profile_skips_shared_fs_check(self) -> None:
        """check_offline_staging with execution_profile='local' must skip the
        shared-FS check even when a path does not lie under any shared root.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other_tmp:
            tmp_path = Path(tmp)
            other_path = Path(other_tmp)
            local_db = other_path / "local_db"
            local_db.mkdir()

            class _FakeWorkflowSpec:
                runtime_images: dict[str, str] = {}
                tool_databases = {"mydb": str(local_db)}
                resolved_input_paths: dict[str, str] = {}

            # shared root is tmp_path, but local_db is under other_path (different root)
            # execution_profile="local" must skip the shared-FS membership check
            findings = check_offline_staging(
                _FakeWorkflowSpec(),
                (tmp_path,),
                execution_profile="local",
            )

        self.assertEqual(findings, [], "local profile must not flag paths off the shared root")

