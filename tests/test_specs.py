"""Synthetic coverage for normalized planning and replay specs.

    These tests cover metadata contracts and serialization without implying that
    runtime generation or resolver behavior already exists.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.registry import get_entry
from flytetest.specs import (
    BindingPlan,
    DeterministicExecutionContract,
    ExecutionProfile,
    GeneratedEntityRecord,
    ResourceSpec,
    RuntimeImageSpec,
    TaskSpec,
    TypedFieldSpec,
    WorkflowEdgeSpec,
    WorkflowNodeSpec,
    WorkflowOutputBinding,
    WorkflowSpec,
)


def _field(
    name: str,
    type_name: str,
    description: str,
    *,
    required: bool = True,
    repeated: bool = False,
    planner_type_names: tuple[str, ...] = (),
) -> TypedFieldSpec:
    """Build one compact typed-field fixture for normalized spec tests.

    Args:
        name: Field name mirrored from a planner or workflow contract.
        type_name: Canonical planner type label stored in the spec fixture.
        description: Human-readable field description copied into the spec.
        required: Whether the field is required in the synthetic contract.
        repeated: Whether the field accepts repeated values.
        planner_type_names: Alternate planner type names used for lookup.

    Returns:
        Typed field metadata that the tests can round-trip through `TypedFieldSpec`.
    """
    return TypedFieldSpec(
        name=name,
        type_name=type_name,
        description=description,
        required=required,
        repeated=repeated,
        planner_type_names=planner_type_names,
    )


class SpecTests(TestCase):
    """Coverage for normalized architecture spec creation and serialization.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_task_spec_round_trips_with_runtime_metadata(self) -> None:
        """Round-trip a task spec that mirrors the current Exonerate task boundary.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        registry_entry = get_entry("exonerate_align_chunk")
        task_spec = TaskSpec(
            name=registry_entry.name,
            biological_stage="protein evidence alignment",
            description=registry_entry.description,
            inputs=tuple(
                _field(field.name, field.type, field.description, required=field.name in {"genome", "protein_chunk"})
                for field in registry_entry.inputs
            ),
            outputs=tuple(_field(field.name, field.type, field.description) for field in registry_entry.outputs),
            deterministic_execution=DeterministicExecutionContract(
                result_boundary="One chunk-level Exonerate alignment directory.",
                assumptions=("Chunk FASTA order remains deterministic.",),
                limitations=("This spec is metadata-only in this planning contract.",),
            ),
            resource_spec=ResourceSpec(cpu="8", memory="32Gi"),
            runtime_image=RuntimeImageSpec(
                apptainer_image="exonerate.sif",
                runtime_assumptions=("Optional local Singularity image path remains user-supplied.",),
            ),
            supported_execution_profiles=("local",),
            compatibility_constraints=("Current Flyte task signature remains unchanged.",),
        )

        self.assertEqual(TaskSpec.from_dict(task_spec.to_dict()), task_spec)
        self.assertTrue(task_spec.metadata_only)
        self.assertEqual([field.name for field in task_spec.inputs[:2]], ["genome", "protein_chunk"])

    def test_binding_plan_round_trips_with_manifest_and_runtime_bindings(self) -> None:
        """Round-trip a binding plan without implying resolver execution is implemented.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        binding_plan = BindingPlan(
            target_name="annotation_qc_busco",
            target_kind="workflow",
            explicit_user_bindings={"repeat_filter_results": "results/repeat_filter_20260406_120000"},
            resolved_prior_assets={"quality_target": "all_repeats_removed.proteins.fa"},
            manifest_derived_paths={"repeat_filter_manifest": "results/repeat_filter_20260406_120000/run_manifest.json"},
            execution_profile="local",
            resource_spec=ResourceSpec(cpu="16", memory="64Gi", partition="short", walltime="02:00:00"),
            runtime_image=RuntimeImageSpec(apptainer_image="busco.sif"),
            runtime_bindings={"busco_cpu": 16, "busco_sif": "busco.sif"},
            unresolved_requirements=("lineage datasets must remain available locally",),
            assumptions=("This is a planning-time binding record only.",),
        )

        self.assertEqual(BindingPlan.from_dict(binding_plan.to_dict()), binding_plan)
        self.assertTrue(binding_plan.metadata_only)
        self.assertEqual(binding_plan.resource_spec.cpu, "16")
        self.assertEqual(binding_plan.runtime_image.apptainer_image, "busco.sif")

    def test_workflow_spec_can_represent_registered_workflow_selection(self) -> None:
        """Represent a direct registered-workflow choice without composition.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        registry_entry = get_entry("ab_initio_annotation_braker3")
        workflow_spec = WorkflowSpec(
            name="select_registered_braker3_workflow",
            analysis_goal="Run the existing BRAKER3 stage as a direct registered workflow selection.",
            inputs=tuple(
                _field(field.name, field.type, field.description, required=field.name == "genome")
                for field in registry_entry.inputs
            ),
            outputs=tuple(_field(field.name, field.type, field.description) for field in registry_entry.outputs),
            nodes=(
                WorkflowNodeSpec(
                    name="braker3_workflow",
                    kind="workflow",
                    reference_name=registry_entry.name,
                    description="Direct selection of the registered BRAKER3 workflow.",
                    output_names=("results_dir",),
                ),
            ),
            edges=(),
            reusable_registered_refs=(registry_entry.name,),
            final_output_bindings=(
                WorkflowOutputBinding(
                    output_name="results_dir",
                    source_node="braker3_workflow",
                    source_output="results_dir",
                    description="Pass through the registered workflow output bundle.",
                ),
            ),
            default_execution_profile="local",
            replay_metadata={"selection_mode": "registered_workflow"},
        )

        self.assertEqual(WorkflowSpec.from_dict(workflow_spec.to_dict()), workflow_spec)
        self.assertEqual(workflow_spec.nodes[0].reference_name, "ab_initio_annotation_braker3")
        self.assertEqual(workflow_spec.replay_metadata["selection_mode"], "registered_workflow")

    def test_workflow_spec_can_represent_registered_stage_composition(self) -> None:
        """Represent a composition built from registered workflow and task stages.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        workflow_spec = WorkflowSpec(
            name="compose_consensus_annotation_from_registered_stages",
            analysis_goal="Compose pre-EVM preparation and EVM execution from registered reviewed stages.",
            inputs=(
                _field("pasa_results", "Dir", "PASA results bundle.", planner_type_names=("TranscriptEvidenceSet",)),
                _field(
                    "protein_evidence_results",
                    "Dir",
                    "Protein evidence results bundle.",
                    planner_type_names=("ProteinEvidenceSet",),
                ),
                _field("braker3_results", "Dir", "BRAKER3 results bundle.", planner_type_names=("AnnotationEvidenceSet",)),
                _field(
                    "transdecoder_results",
                    "Dir",
                    "TransDecoder results bundle.",
                    planner_type_names=("AnnotationEvidenceSet",),
                ),
            ),
            outputs=(
                _field(
                    "results_dir",
                    "Dir",
                    "Consensus EVM results bundle.",
                    planner_type_names=("ConsensusAnnotation",),
                ),
            ),
            nodes=(
                WorkflowNodeSpec(
                    name="prep",
                    kind="workflow",
                    reference_name="consensus_annotation_evm_prep",
                    description="Assemble the note-faithful pre-EVM contract.",
                    input_bindings={
                        "pasa_results": "workflow.pasa_results",
                        "transdecoder_results": "workflow.transdecoder_results",
                        "protein_evidence_results": "workflow.protein_evidence_results",
                        "braker3_results": "workflow.braker3_results",
                    },
                    output_names=("results_dir",),
                ),
                WorkflowNodeSpec(
                    name="execute",
                    kind="workflow",
                    reference_name="consensus_annotation_evm",
                    description="Execute deterministic EVM from the prepared bundle.",
                    input_bindings={"evm_prep_results": "prep.results_dir"},
                    output_names=("results_dir",),
                ),
            ),
            edges=(
                WorkflowEdgeSpec(
                    source_node="prep",
                    source_output="results_dir",
                    target_node="execute",
                    target_input="evm_prep_results",
                ),
            ),
            ordering_constraints=("prep before execute",),
            reusable_registered_refs=("consensus_annotation_evm_prep", "consensus_annotation_evm"),
            final_output_bindings=(
                WorkflowOutputBinding(
                    output_name="results_dir",
                    source_node="execute",
                    source_output="results_dir",
                    description="Final consensus annotation results bundle.",
                ),
            ),
            default_execution_profile="local",
            replay_metadata={"selection_mode": "registered_stage_composition"},
        )

        self.assertEqual(WorkflowSpec.from_dict(workflow_spec.to_dict()), workflow_spec)
        self.assertEqual(len(workflow_spec.nodes), 2)
        self.assertEqual(len(workflow_spec.edges), 1)
        self.assertEqual(workflow_spec.edges[0].target_input, "evm_prep_results")

    def test_workflow_spec_can_represent_saved_generated_artifact(self) -> None:
        """Represent a saved generated workflow artifact without implying generic synthesis exists.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        generated_record = GeneratedEntityRecord(
            generated_entity_id="generated::annotation_qc_bundle::2026-04-06T12:30:00Z",
            source_prompt="Assess the prepared consensus annotation with BUSCO after repeat filtering.",
            assumptions=(
                "The generated artifact references only existing reviewed stages.",
                "This record is metadata-only in this saved-artifact contract.",
            ),
            selected_execution_profile="local",
            referenced_registered_building_blocks=("annotation_repeat_filtering", "annotation_qc_busco"),
            created_at="2026-04-06T12:30:00Z",
            replay_metadata={"workflow_spec_version": "v1"},
        )
        workflow_spec = WorkflowSpec(
            name="generated_annotation_qc_bundle",
            analysis_goal="Represent one saved generated workflow artifact for later replay metadata.",
            inputs=(
                _field(
                    "consensus_annotation_dir",
                    "Dir",
                    "Upstream consensus annotation bundle.",
                    planner_type_names=("ConsensusAnnotation",),
                ),
            ),
            outputs=(
                _field(
                    "qc_results_dir",
                    "Dir",
                    "BUSCO QC result bundle.",
                    planner_type_names=("QualityAssessmentTarget",),
                ),
            ),
            nodes=(
                WorkflowNodeSpec(
                    name="generated_qc_workflow",
                    kind="generated_workflow",
                    reference_name=generated_record.generated_entity_id,
                    description="Saved generated artifact that can be replayed later.",
                    output_names=("qc_results_dir",),
                ),
            ),
            edges=(),
            reusable_registered_refs=("annotation_repeat_filtering", "annotation_qc_busco"),
            final_output_bindings=(
                WorkflowOutputBinding(
                    output_name="qc_results_dir",
                    source_node="generated_qc_workflow",
                    source_output="qc_results_dir",
                    description="Saved generated QC artifact output.",
                ),
            ),
            default_execution_profile="local",
            replay_metadata={"selection_mode": "generated_workflow_artifact"},
            generated_entity_record=generated_record,
        )

        self.assertEqual(WorkflowSpec.from_dict(workflow_spec.to_dict()), workflow_spec)
        self.assertEqual(workflow_spec.generated_entity_record.generated_entity_id, generated_record.generated_entity_id)
        self.assertEqual(workflow_spec.nodes[0].kind, "generated_workflow")

    def test_execution_profile_round_trips_with_resource_overrides(self) -> None:
        """Round-trip one named execution profile used by normalized specs.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        profile = ExecutionProfile(
            name="high-mem",
            description="Use the same biology with a larger memory envelope.",
            resource_overrides=ResourceSpec(cpu="16", memory="64Gi", partition="highmem"),
            runtime_image=RuntimeImageSpec(
                container_image="ghcr.io/flytetest/annotation:latest",
                compatibility_notes=("Container usage remains future-facing metadata here.",),
            ),
            scheduler_profile="highmem",
            notes=("Profiles remain policy-only metadata in this contract.",),
        )

        self.assertEqual(ExecutionProfile.from_dict(profile.to_dict()), profile)
