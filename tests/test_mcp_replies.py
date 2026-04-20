"""Coverage for typed MCP reply dataclasses introduced by the reshape plan."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.mcp_replies import (
    BundleAvailabilityReply,
    DryRunReply,
    PlanDecline,
    PlanSuccess,
    RunReply,
    SuggestedBundle,
    SuggestedPriorRun,
    ValidateRecipeReply,
)


def _assert_single_run_target_name(reply: RunReply) -> None:
    """Document the run-reply contract that exactly one target name is populated."""

    has_task_name = bool(reply.task_name)
    has_workflow_name = bool(reply.workflow_name)
    assert has_task_name != has_workflow_name


class McpRepliesTests(TestCase):
    """Synthetic coverage for the additive MCP reply dataclasses."""

    def test_suggested_bundle_round_trips_through_asdict(self) -> None:
        """Round-trip the simplest decline recovery bundle payload."""

        reply = SuggestedBundle(
            name="braker3_small_eukaryote",
            description="Starter kit for small-eukaryote BRAKER3 runs.",
            applies_to=("braker3_annotation_workflow",),
            available=True,
        )

        payload = asdict(reply)
        round_trip = SuggestedBundle(**payload)

        self.assertEqual(round_trip, reply)

    def test_suggested_prior_run_round_trips_through_asdict(self) -> None:
        """Round-trip the prior-run recovery hint payload."""

        reply = SuggestedPriorRun(
            run_id="20260420T101112.123Z-braker3_annotation_workflow",
            produced_type="ReadSet",
            output_name="rnaseq_reads",
            hint="Use bindings={'ReadSet': {'$ref': {...}}}",
        )

        payload = asdict(reply)
        round_trip = SuggestedPriorRun(**payload)

        self.assertEqual(round_trip, reply)

    def test_run_reply_round_trips_through_asdict(self) -> None:
        """Round-trip a success reply with task-scoped naming."""

        reply = RunReply(
            supported=True,
            recipe_id="20260420T101112.123Z-exonerate_align_chunk",
            run_record_path="results/exonerate/run_record.json",
            artifact_path=".runtime/specs/20260420T101112.123Z-exonerate_align_chunk.json",
            execution_profile="local",
            execution_status="success",
            exit_status=0,
            outputs={"alignment_dir": "results/exonerate/alignment_dir"},
            limitations=(),
            task_name="exonerate_align_chunk",
        )

        payload = asdict(reply)
        round_trip = RunReply(**payload)

        self.assertEqual(round_trip, reply)

    def test_run_reply_contract_uses_exactly_one_target_name(self) -> None:
        """Document the run-reply invariant that task and workflow names do not overlap."""

        task_reply = RunReply(
            supported=True,
            recipe_id="20260420T101112.123Z-fastqc",
            run_record_path="results/fastqc/run_record.json",
            artifact_path=".runtime/specs/20260420T101112.123Z-fastqc.json",
            execution_profile="local",
            execution_status="success",
            exit_status=0,
            outputs={"qc_dir": "results/fastqc/qc_dir"},
            limitations=(),
            task_name="fastqc",
        )
        workflow_reply = RunReply(
            supported=True,
            recipe_id="20260420T101112.123Z-protein_evidence_alignment",
            run_record_path="results/protein_evidence/run_record.json",
            artifact_path=".runtime/specs/20260420T101112.123Z-protein_evidence_alignment.json",
            execution_profile="slurm",
            execution_status="success",
            exit_status=None,
            outputs={"results_dir": "results/protein_evidence/results_dir"},
            limitations=("Slurm job submitted; inspect the run record for lifecycle updates.",),
            workflow_name="protein_evidence_alignment",
        )

        _assert_single_run_target_name(task_reply)
        _assert_single_run_target_name(workflow_reply)

    def test_plan_decline_round_trips_through_asdict(self) -> None:
        """Round-trip a structured decline with all recovery channels populated."""

        reply = PlanDecline(
            supported=False,
            target="braker3_annotation_workflow",
            pipeline_family="annotation",
            limitations=("BRAKER3 requires at least one evidence input.",),
            suggested_bundles=(
                SuggestedBundle(
                    name="braker3_small_eukaryote",
                    description="Starter BRAKER3 bundle.",
                    applies_to=("braker3_annotation_workflow",),
                    available=True,
                ),
            ),
            suggested_prior_runs=(
                SuggestedPriorRun(
                    run_id="20260420T101112.123Z-transcript_evidence_generation",
                    produced_type="ReadSet",
                    output_name="rnaseq_reads",
                    hint="Reuse the prior ReadSet via $ref.",
                ),
            ),
            next_steps=("load_bundle('braker3_small_eukaryote')",),
        )

        payload = asdict(reply)
        round_trip = PlanDecline(
            supported=payload["supported"],
            target=payload["target"],
            pipeline_family=payload["pipeline_family"],
            limitations=tuple(payload["limitations"]),
            suggested_bundles=tuple(SuggestedBundle(**item) for item in payload["suggested_bundles"]),
            suggested_prior_runs=tuple(SuggestedPriorRun(**item) for item in payload["suggested_prior_runs"]),
            next_steps=tuple(payload["next_steps"]),
        )

        self.assertEqual(round_trip, reply)

    def test_plan_decline_defaults_recovery_channels_to_empty_tuples(self) -> None:
        """Keep the default decline payload sparse when no recovery hints are available."""

        reply = PlanDecline(
            supported=False,
            target="unknown_goal",
            pipeline_family="",
            limitations=("No supported plan could be formed.",),
        )

        self.assertEqual(reply.suggested_bundles, ())
        self.assertEqual(reply.suggested_prior_runs, ())
        self.assertEqual(reply.next_steps, ())

    def test_plan_success_round_trips_through_asdict(self) -> None:
        """Round-trip a plan preview payload with composed-stage metadata."""

        reply = PlanSuccess(
            supported=True,
            target="consensus_annotation_evm",
            pipeline_family="annotation",
            biological_goal="compose consensus annotation",
            requires_user_approval=True,
            bindings={"AnnotationEvidenceSet": {"results_dir": "results/evm_prep"}},
            scalar_inputs={"evm_weights": "data/evm/weights.txt"},
            composition_stages=("consensus_annotation_evm_prep", "consensus_annotation_evm"),
            artifact_path=".runtime/specs/20260420T101112.123Z-composed.json",
            suggested_next_call={"tool": "approve_composed_recipe", "kwargs": {}},
            limitations=("Composed plans require approval before execution.",),
        )

        payload = asdict(reply)
        round_trip = PlanSuccess(
            supported=payload["supported"],
            target=payload["target"],
            pipeline_family=payload["pipeline_family"],
            biological_goal=payload["biological_goal"],
            requires_user_approval=payload["requires_user_approval"],
            bindings=payload["bindings"],
            scalar_inputs=payload["scalar_inputs"],
            composition_stages=tuple(payload["composition_stages"]),
            artifact_path=payload["artifact_path"],
            suggested_next_call=payload["suggested_next_call"],
            limitations=tuple(payload["limitations"]),
        )

        self.assertEqual(round_trip, reply)

    def test_bundle_availability_reply_round_trips_through_asdict(self) -> None:
        """Round-trip one bundle-listing payload."""

        reply = BundleAvailabilityReply(
            name="m18_busco_demo",
            description="BUSCO demo bundle.",
            pipeline_family="annotation_qc",
            applies_to=("annotation_qc_busco",),
            binding_types=("QualityAssessmentTarget",),
            available=False,
            reasons=("Missing lineage directory.",),
        )

        payload = asdict(reply)
        round_trip = BundleAvailabilityReply(**payload)

        self.assertEqual(round_trip, reply)

    def test_validate_recipe_reply_round_trips_through_asdict(self) -> None:
        """Round-trip a recipe-validation payload with findings."""

        reply = ValidateRecipeReply(
            supported=False,
            recipe_id="20260420T101112.123Z-busco_annotation_qc_workflow",
            execution_profile="slurm",
            findings=(
                {
                    "kind": "container",
                    "key": "busco_sif",
                    "reason": "not_found",
                },
            ),
        )

        payload = asdict(reply)
        round_trip = ValidateRecipeReply(
            supported=payload["supported"],
            recipe_id=payload["recipe_id"],
            execution_profile=payload["execution_profile"],
            findings=tuple(payload["findings"]),
        )

        self.assertEqual(round_trip, reply)

    def test_dry_run_reply_round_trips_through_asdict(self) -> None:
        """Round-trip a dry-run preview payload with staged environment detail."""

        reply = DryRunReply(
            supported=True,
            recipe_id="20260420T101112.123Z-busco_annotation_qc_workflow",
            artifact_path=".runtime/specs/20260420T101112.123Z-busco_annotation_qc_workflow.json",
            execution_profile="slurm",
            resolved_bindings={
                "ReferenceGenome": {"fasta_path": "/project/data/genome.fa"},
            },
            resolved_environment={
                "runtime_images": {"busco_sif": "/project/images/busco.sif"},
                "tool_databases": {"busco_lineage_dir": "/project/data/lineages/eukaryota_odb10"},
                "module_loads": ("python/3.11.9", "apptainer/1.4.1"),
                "env_vars": {},
            },
            staging_findings=(),
            limitations=(),
            workflow_name="busco_annotation_qc_workflow",
        )

        payload = asdict(reply)
        round_trip = DryRunReply(
            supported=payload["supported"],
            recipe_id=payload["recipe_id"],
            artifact_path=payload["artifact_path"],
            execution_profile=payload["execution_profile"],
            resolved_bindings=payload["resolved_bindings"],
            resolved_environment=payload["resolved_environment"],
            staging_findings=tuple(payload["staging_findings"]),
            limitations=tuple(payload["limitations"]),
            task_name=payload["task_name"],
            workflow_name=payload["workflow_name"],
        )

        self.assertEqual(round_trip, reply)