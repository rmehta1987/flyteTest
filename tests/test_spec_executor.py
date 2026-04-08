"""Synthetic coverage for local execution of saved workflow-spec artifacts.

These tests exercise Milestone 7 without requiring external bioinformatics
tools. Registered stage handlers are fake, but the executor still uses the
saved `BindingPlan`, resolver inputs, registry references, and manifest-shaped
result directories.
"""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.planner_types import ConsensusAnnotation, ReferenceGenome
from flytetest.planning import plan_typed_request
from flytetest.spec_artifacts import artifact_from_typed_plan
from flytetest.spec_executor import LocalNodeExecutionRequest, LocalWorkflowSpecExecutor


def _artifact_with_runtime_bindings(tmp_path: Path):
    """Build one generated-spec artifact with enough runtime values to run locally."""
    reference_genome = ReferenceGenome(fasta_path=Path("data/genome.fa"))
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


class SpecExecutorTests(TestCase):
    """Checks for the saved-spec local executor path."""

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
