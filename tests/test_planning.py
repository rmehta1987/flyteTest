"""Planner contract checks for the narrow FLyteTest MCP showcase.

These tests freeze the current planner subset while the broader `realtime`
architecture lands behind compatibility seams.
"""

from __future__ import annotations

import json
import sys
import tempfile
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


def _repeat_filter_manifest_dir(base_dir: Path, name: str) -> Path:
    """Create one synthetic repeat-filter manifest directory for BUSCO planning tests."""
    result_dir = base_dir / name
    result_dir.mkdir()
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_repeat_filtering",
                "assumptions": ["Repeat-filtered outputs are QC-ready."],
                "inputs": {"reference_genome": "data/genome.fa"},
                "outputs": {
                    "all_repeats_removed_gff3": str(result_dir / "all_repeats_removed.gff3"),
                    "final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                },
            },
            indent=2,
        )
    )
    return result_dir


def _eggnog_manifest_dir(base_dir: Path, name: str) -> Path:
    """Create one synthetic EggNOG manifest directory for AGAT planning tests."""
    result_dir = base_dir / name
    result_dir.mkdir()
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_functional_eggnog",
                "assumptions": ["EggNOG outputs are AGAT-ready."],
                "outputs": {
                    "eggnog_annotated_gff3": str(result_dir / "all_repeats_removed.eggnog.gff3"),
                    "repeat_filter_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                },
            },
            indent=2,
        )
    )
    return result_dir


def _agat_conversion_manifest_dir(base_dir: Path, name: str) -> Path:
    """Create one synthetic AGAT conversion manifest directory for cleanup planning tests."""
    result_dir = base_dir / name
    result_dir.mkdir()
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_postprocess_agat_conversion",
                "assumptions": ["AGAT conversion outputs are cleanup-ready."],
                "outputs": {
                    "agat_converted_gff3": str(result_dir / "all_repeats_removed.agat.gff3"),
                },
            },
            indent=2,
        )
    )
    return result_dir


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

    def test_typed_plan_accepts_serialized_quality_assessment_target_binding(self) -> None:
        """Resolve BUSCO from an explicit serialized quality target plus runtime bindings."""
        target = QualityAssessmentTarget(
            source_result_dir=Path("results/repeat_filter_20260407_120000"),
            source_manifest_path=Path("results/repeat_filter_20260407_120000/run_manifest.json"),
            annotation_gff3_path=Path("results/repeat_filter_20260407_120000/all_repeats_removed.gff3"),
            proteins_fasta_path=Path("results/repeat_filter_20260407_120000/all_repeats_removed.proteins.fa"),
        )

        payload = plan_typed_request(
            "Run BUSCO quality assessment on the annotation.",
            explicit_bindings={"QualityAssessmentTarget": target.to_dict()},
            runtime_bindings={
                "busco_lineages_text": "embryophyta_odb10",
                "busco_sif": "busco.sif",
                "busco_cpu": 12,
            },
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_qc_busco")
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(
            payload["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(target.source_result_dir),
        )
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {
                "busco_lineages_text": "embryophyta_odb10",
                "busco_sif": "busco.sif",
                "busco_cpu": 12,
            },
        )

    def test_typed_plan_resolves_busco_from_manifest_sources(self) -> None:
        """Resolve BUSCO from a repeat-filter manifest source without guessing."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")

            payload = plan_typed_request(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={
                    "busco_lineages_text": "embryophyta_odb10",
                    "busco_cpu": 12,
                },
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["biological_goal"], "annotation_qc_busco")
        self.assertEqual(
            payload["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(result_dir),
        )
        self.assertEqual(
            payload["binding_plan"]["manifest_derived_paths"]["QualityAssessmentTarget"]["label"],
            str(result_dir / "run_manifest.json"),
        )
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {
                "busco_lineages_text": "embryophyta_odb10",
                "busco_cpu": 12,
            },
        )

    def test_typed_plan_freezes_resource_policy_from_prompt_and_caller_inputs(self) -> None:
        """Persist structured resource and runtime-image policy in the binding plan."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")

            payload = plan_typed_request(
                "Run BUSCO quality assessment on the annotation with 12 CPUs, memory 48Gi, queue short, walltime 02:00:00.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={"memory": "64Gi"},
                execution_profile="local",
                runtime_image={"apptainer_image": "busco.sif"},
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["execution_profile"], "local")
        self.assertEqual(payload["resource_spec"]["cpu"], "12")
        self.assertEqual(payload["resource_spec"]["memory"], "64Gi")
        self.assertEqual(payload["resource_spec"]["queue"], "short")
        self.assertEqual(payload["resource_spec"]["walltime"], "02:00:00")
        self.assertEqual(payload["runtime_image"]["apptainer_image"], "busco.sif")
        self.assertEqual(payload["binding_plan"]["execution_profile"], "local")
        self.assertEqual(payload["binding_plan"]["resource_spec"], payload["resource_spec"])
        self.assertEqual(payload["binding_plan"]["runtime_image"], payload["runtime_image"])

    def test_typed_plan_accepts_slurm_execution_profile(self) -> None:
        """Freeze Slurm resource policy for later submission without running it."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")

            payload = plan_typed_request(
                "Run BUSCO quality assessment on the annotation using execution profile slurm on queue batch.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["candidate_outcome"], "registered_workflow")
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["execution_profile"], "slurm")
        self.assertEqual(payload["binding_plan"]["execution_profile"], "slurm")
        self.assertEqual(payload["resource_spec"]["execution_class"], "slurm")

    def test_typed_plan_reports_ambiguous_busco_manifest_sources(self) -> None:
        """Decline BUSCO planning when multiple manifests could satisfy the QC target."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dirs = (
                _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results_a"),
                _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results_b"),
            )

            payload = plan_typed_request(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=result_dirs,
            )

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "declined")
        self.assertEqual(payload["candidate_outcome"], "registered_workflow")
        self.assertIn("choose one explicitly", payload["missing_requirements"][0])

    def test_typed_plan_resolves_eggnog_from_busco_manifest_source(self) -> None:
        """Use a BUSCO manifest to recover the repeat-filter boundary for EggNOG."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repeat_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")
            busco_dir = tmp_path / "busco_results"
            busco_dir.mkdir()
            (busco_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow": "annotation_qc_busco",
                        "source_bundle": {"repeat_filter_results": str(repeat_dir)},
                        "outputs": {
                            "final_proteins_fasta": str(busco_dir / "all_repeats_removed.proteins.fa"),
                            "busco_summary_tsv": str(busco_dir / "busco_summary.tsv"),
                        },
                    },
                    indent=2,
                )
            )

            payload = plan_typed_request(
                "Run EggNOG functional annotation on the repeat-filtered proteins.",
                manifest_sources=(busco_dir,),
                runtime_bindings={"eggnog_data_dir": "/db/eggnog", "eggnog_database": "Diptera"},
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_names"], ["annotation_functional_eggnog"])
        self.assertEqual(
            payload["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(repeat_dir),
        )
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {"eggnog_data_dir": "/db/eggnog", "eggnog_database": "Diptera"},
        )

    def test_typed_plan_resolves_agat_targets_from_manifest_sources(self) -> None:
        """Resolve AGAT statistics/conversion and cleanup from compatible manifests."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eggnog_dir = _eggnog_manifest_dir(tmp_path, "eggnog_results")
            conversion_dir = _agat_conversion_manifest_dir(tmp_path, "agat_conversion_results")

            conversion = plan_typed_request(
                "Run AGAT conversion on the EggNOG-annotated GFF3.",
                manifest_sources=(eggnog_dir,),
                runtime_bindings={"agat_sif": "agat.sif"},
            )
            cleanup = plan_typed_request(
                "Run AGAT cleanup on the converted GFF3.",
                manifest_sources=(conversion_dir,),
            )

        self.assertTrue(conversion["supported"])
        self.assertTrue(cleanup["supported"])
        self.assertEqual(conversion["matched_entry_names"], ["annotation_postprocess_agat_conversion"])
        self.assertEqual(cleanup["matched_entry_names"], ["annotation_postprocess_agat_cleanup"])
        self.assertEqual(
            conversion["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(eggnog_dir),
        )
        self.assertEqual(
            cleanup["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(conversion_dir),
        )

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
