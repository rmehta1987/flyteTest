"""Coverage for saved replayable workflow-spec artifacts.

    These tests cover metadata persistence and reloads. They do not execute saved
    specs and do not imply general runtime code generation.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.planner_types import ConsensusAnnotation, ReferenceGenome
from flytetest.planning import plan_typed_request
from flytetest.spec_artifacts import (
    DEFAULT_SPEC_ARTIFACT_FILENAME,
    SPEC_ARTIFACT_SCHEMA_VERSION,
    artifact_from_typed_plan,
    load_workflow_spec_artifact,
    replayable_spec_pair,
    save_workflow_spec_artifact,
)


class SpecArtifactTests(TestCase):
    """Checks for saving and reloading typed planning artifacts.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_generated_workflow_spec_artifact_round_trips_from_typed_plan(self) -> None:
        """Save and reload a generated spec preview with prompt provenance.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        consensus_annotation = ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=Path("results/evm/evm.out.gff3"),
        )
        prompt = "Create a generated WorkflowSpec for repeat filtering and BUSCO QC."
        typed_plan = plan_typed_request(
            prompt,
            explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        )

        artifact = artifact_from_typed_plan(
            typed_plan,
            created_at="2026-04-07T12:00:00Z",
            replay_metadata={"request_id": "test-request"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_path = save_workflow_spec_artifact(artifact, Path(tmp))
            loaded = load_workflow_spec_artifact(Path(tmp))

        self.assertEqual(output_path.name, DEFAULT_SPEC_ARTIFACT_FILENAME)
        self.assertEqual(loaded, artifact)
        self.assertEqual(loaded.schema_version, SPEC_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(loaded.source_prompt, prompt)
        self.assertEqual(loaded.planning_outcome, "generated_workflow_spec")
        self.assertEqual(loaded.referenced_registered_stages, ("annotation_repeat_filtering", "annotation_qc_busco"))
        self.assertIn("repeatmasker_out", loaded.runtime_requirements[0])
        self.assertEqual(loaded.replay_metadata["request_id"], "test-request")

    def test_save_workflow_spec_artifact_creates_missing_parent_directories(self) -> None:
        """Write artifacts into a fresh nested directory without precreating it.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / ".runtime" / "specs"
            output_path = save_workflow_spec_artifact(artifact, destination)

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.parent, destination)
            self.assertEqual(output_path.name, DEFAULT_SPEC_ARTIFACT_FILENAME)
            self.assertTrue(destination.exists())

    def test_replayable_spec_pair_does_not_reparse_prompt(self) -> None:
        """Reload the saved spec and binding plan directly for future replay work.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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

        workflow_spec, binding_plan = replayable_spec_pair(artifact)

        self.assertEqual(workflow_spec.name, "repeat_filter_then_busco_qc")
        self.assertEqual([node.reference_name for node in workflow_spec.nodes], ["annotation_repeat_filtering", "annotation_qc_busco"])
        self.assertEqual(binding_plan.target_kind, "generated_workflow")
        self.assertEqual(binding_plan.target_name, "repeat_filter_then_busco_qc")
        self.assertIn("WorkflowSpec and BindingPlan outputs are metadata-only", binding_plan.assumptions[-1])

    def test_declined_typed_plan_cannot_be_saved(self) -> None:
        """Reject transient decline payloads as non-replayable artifacts.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        typed_plan = plan_typed_request("Run SNP variant calling and emit a VCF.")

        with self.assertRaises(ValueError):
            artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")
