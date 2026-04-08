"""Planner contract checks for the narrow FLyteTest MCP showcase.

These tests freeze the current planner subset while the broader `realtime`
architecture lands behind compatibility seams.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest.planner_types import (
    AnnotationEvidenceSet,
    ConsensusAnnotation,
    ProteinEvidenceSet,
    QualityAssessmentTarget,
    ReferenceGenome,
    TranscriptEvidenceSet,
)
from flytetest.planning import plan_request, plan_typed_request, split_entry_inputs, supported_entry_parameters


class PlanningTests(TestCase):
    """Compatibility checks for the current planner-facing showcase behavior."""

    def test_typed_plan_resolves_direct_registered_workflow(self) -> None:
        """Select a registered workflow through planner types and resolver bindings."""
        reference_genome = ReferenceGenome(fasta_path=Path("data/genome.fa"))
        protein_evidence = ProteinEvidenceSet(
            reference_genome=reference_genome,
            source_protein_fastas=(Path("data/proteins.fa"),),
        )

        payload = plan_typed_request(
            "Run protein evidence alignment for this genome.",
            explicit_bindings={
                "ReferenceGenome": reference_genome,
                "ProteinEvidenceSet": protein_evidence,
            },
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "protein_evidence_alignment")
        self.assertEqual(payload["matched_entry_names"], ["protein_evidence_alignment"])
        self.assertEqual(payload["required_planner_types"], ["ReferenceGenome", "ProteinEvidenceSet"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["workflow_spec"]["replay_metadata"]["selection_mode"], "registered_workflow")
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_builds_registered_stage_composition(self) -> None:
        """Represent an EVM consensus request as reviewed registered workflow stages."""
        reference_genome = ReferenceGenome(fasta_path=Path("data/genome.fa"))
        transcript_evidence = TranscriptEvidenceSet(
            reference_genome=reference_genome,
            pasa_assemblies_gff3_path=Path("results/pasa/pasa_assemblies.gff3"),
        )
        protein_evidence = ProteinEvidenceSet(
            reference_genome=reference_genome,
            evm_ready_gff3_path=Path("results/protein/proteins.gff3"),
        )
        annotation_evidence = AnnotationEvidenceSet(
            reference_genome=reference_genome,
            transcript_evidence=transcript_evidence,
            protein_evidence=protein_evidence,
            ab_initio_predictions_gff3_path=Path("results/braker/braker.gff3"),
        )

        payload = plan_typed_request(
            "Create a consensus annotation with EVM.",
            explicit_bindings={
                "TranscriptEvidenceSet": transcript_evidence,
                "ProteinEvidenceSet": protein_evidence,
                "AnnotationEvidenceSet": annotation_evidence,
            },
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_stage_composition")
        self.assertEqual(
            payload["matched_entry_names"],
            ["consensus_annotation_evm_prep", "consensus_annotation_evm"],
        )
        self.assertEqual(payload["workflow_spec"]["replay_metadata"]["selection_mode"], "registered_stage_composition")
        self.assertEqual([node["reference_name"] for node in payload["workflow_spec"]["nodes"]], payload["matched_entry_names"])
        self.assertEqual(payload["workflow_spec"]["edges"][0]["target_input"], "evm_prep_results")

    def test_typed_plan_builds_generated_workflow_spec_preview(self) -> None:
        """Represent a not-yet-checked-in multi-stage request as a metadata-only spec preview."""
        reference_genome = ReferenceGenome(fasta_path=Path("data/genome.fa"))
        consensus_annotation = ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=Path("results/evm/evm.out.gff3"),
        )

        payload = plan_typed_request(
            "Create a generated WorkflowSpec for repeat filtering and BUSCO QC.",
            explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "generated_workflow_spec")
        self.assertEqual(payload["candidate_outcome"], "generated_workflow_spec")
        self.assertEqual(payload["missing_requirements"], [])
        self.assertIn("repeatmasker_out", payload["runtime_requirements"][0])
        self.assertIn("repeatmasker_out", payload["binding_plan"]["unresolved_requirements"][0])
        self.assertEqual(
            payload["workflow_spec"]["generated_entity_record"]["generated_entity_id"],
            "generated::repeat_filter_then_busco_qc::preview",
        )
        self.assertEqual(payload["binding_plan"]["target_kind"], "generated_workflow")

    def test_typed_plan_selects_eggnog_functional_annotation(self) -> None:
        """Represent post-BUSCO functional annotation as a registered EggNOG workflow."""
        target = QualityAssessmentTarget(
            annotation_gff3_path=Path("results/repeat_filter/all_repeats_removed.eggnog.gff3"),
            proteins_fasta_path=Path("results/repeat_filter/all_repeats_removed.proteins.fa"),
        )

        payload = plan_typed_request(
            "Run EggNOG functional annotation on the repeat-filtered proteins.",
            explicit_bindings={"QualityAssessmentTarget": target},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_functional_eggnog")
        self.assertEqual(payload["matched_entry_names"], ["annotation_functional_eggnog"])
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_selects_agat_post_processing(self) -> None:
        """Represent post-EggNOG AGAT statistics as a registered workflow."""
        target = QualityAssessmentTarget(
            annotation_gff3_path=Path("results/eggnog/all_repeats_removed.eggnog.gff3"),
        )

        payload = plan_typed_request(
            "Run AGAT statistics on the EggNOG-annotated GFF3.",
            explicit_bindings={"QualityAssessmentTarget": target},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_postprocess_agat")
        self.assertEqual(payload["matched_entry_names"], ["annotation_postprocess_agat"])
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_selects_agat_conversion(self) -> None:
        """Represent post-EggNOG AGAT conversion as a registered workflow."""
        target = QualityAssessmentTarget(
            annotation_gff3_path=Path("results/eggnog/all_repeats_removed.eggnog.gff3"),
        )

        payload = plan_typed_request(
            "Run AGAT conversion on the EggNOG-annotated GFF3.",
            explicit_bindings={"QualityAssessmentTarget": target},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_postprocess_agat_conversion")
        self.assertEqual(payload["matched_entry_names"], ["annotation_postprocess_agat_conversion"])
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_selects_agat_cleanup(self) -> None:
        """Represent post-conversion AGAT cleanup as a registered workflow."""
        target = QualityAssessmentTarget(
            annotation_gff3_path=Path("results/agat/all_repeats_removed.agat.gff3"),
        )

        payload = plan_typed_request(
            "Run AGAT cleanup on the converted GFF3.",
            explicit_bindings={"QualityAssessmentTarget": target},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_postprocess_agat_cleanup")
        self.assertEqual(payload["matched_entry_names"], ["annotation_postprocess_agat_cleanup"])
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_reports_missing_inputs_without_guessing(self) -> None:
        """Decline a recognized typed goal when resolver sources cannot satisfy it."""
        payload = plan_typed_request("Run BUSCO quality assessment on the annotation.")

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "declined")
        self.assertEqual(payload["candidate_outcome"], "registered_workflow")
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertIn("No QualityAssessmentTarget", payload["missing_requirements"][0])

    def test_typed_plan_declines_unsupported_biology(self) -> None:
        """Reject unsupported biology instead of inventing registry entries."""
        payload = plan_typed_request("Run SNP variant calling and emit a VCF.")

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "declined")
        self.assertEqual(payload["matched_entry_names"], [])
        self.assertIn("does not map to a supported typed biology goal", payload["missing_requirements"][0])

    def test_supported_entry_parameters_match_current_workflow_signature(self) -> None:
        """Treat the current BRAKER3 showcase workflow signature as compatibility-critical."""
        parameters = supported_entry_parameters("ab_initio_annotation_braker3")

        self.assertEqual(
            [(parameter.name, parameter.required) for parameter in parameters],
            [
                ("genome", True),
                ("rnaseq_bam_path", False),
                ("protein_fasta_path", False),
                ("braker_species", False),
                ("braker3_sif", False),
            ],
        )

    def test_split_entry_inputs_preserves_required_and_optional_groups(self) -> None:
        """Expose the current protein-evidence planner grouping without changing task signatures."""
        required_inputs, optional_inputs = split_entry_inputs("protein_evidence_alignment")

        self.assertEqual([field.name for field in required_inputs], ["genome", "protein_fastas"])
        self.assertEqual(
            [field.name for field in optional_inputs],
            ["proteins_per_chunk", "exonerate_sif", "exonerate_model"],
        )

    def test_plan_request_keeps_current_supported_payload_shape(self) -> None:
        """Return the stable planning payload for a supported protein-evidence prompt."""
        prompt = (
            "Run protein evidence alignment with genome data/genome.fa and "
            "protein evidence data/proteins.fa"
        )

        payload = plan_request(prompt)

        self.assertEqual(
            set(payload),
            {
                "supported",
                "original_request",
                "matched_entry_name",
                "matched_entry_category",
                "matched_entry_description",
                "required_inputs",
                "optional_inputs",
                "extracted_inputs",
                "missing_required_inputs",
                "declined_downstream_stages",
                "assumptions",
                "limitations",
                "confidence",
                "rationale",
            },
        )
        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_name"], "protein_evidence_alignment")
        self.assertEqual(payload["matched_entry_category"], "workflow")
        self.assertEqual(
            payload["extracted_inputs"],
            {
                "genome": "data/genome.fa",
                "protein_fastas": ["data/proteins.fa"],
            },
        )
        self.assertEqual(payload["missing_required_inputs"], [])
        self.assertEqual(payload["declined_downstream_stages"], [])
        self.assertEqual(
            [field["name"] for field in payload["required_inputs"]],
            ["genome", "protein_fastas"],
        )
        self.assertEqual(
            [field["name"] for field in payload["optional_inputs"]],
            ["proteins_per_chunk", "exonerate_sif", "exonerate_model"],
        )

    def test_plan_request_no_longer_blocks_downstream_terms(self) -> None:
        """Keep prompt-path planning available without the old MCP downstream blocklist."""
        payload = plan_request(
            "Run protein evidence alignment with genome data/genome.fa and protein evidence "
            "data/proteins.fa, then continue into EVM and BUSCO."
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_name"], "protein_evidence_alignment")
        self.assertEqual(payload["declined_downstream_stages"], [])
