"""Registry checks for the active notes-backed public workflow surface.

These tests make sure the catalog still exposes the key workflow and task
interfaces described in the repository docs while milestone refactors land.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.registry import get_entry


class RegistryTests(TestCase):
    """Basic registry coverage for the active milestone-facing catalog surface."""

    def test_trinity_denovo_task_entry_is_registered(self) -> None:
        """Expose the de novo Trinity task as a first-class transcript-evidence boundary."""
        entry = get_entry("trinity_denovo_assemble")

        self.assertEqual(entry.category, "task")
        self.assertIn("de novo Trinity", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["left", "right", "sample_id", "trinity_sif", "trinity_cpu", "trinity_max_memory_gb"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["trinity_dir"])

    def test_protein_evidence_workflow_entry_is_registered(self) -> None:
        """Expose the workflow as a first-class catalog entry."""
        entry = get_entry("protein_evidence_alignment")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("Exonerate", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["genome", "protein_fastas", "proteins_per_chunk", "exonerate_sif", "exonerate_model"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["results_dir"])

    def test_exonerate_task_entry_is_registered(self) -> None:
        """Expose the chunked Exonerate task in the catalog."""
        entry = get_entry("exonerate_align_chunk")

        self.assertEqual(entry.category, "task")
        self.assertIn("Exonerate", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["genome", "protein_chunk", "exonerate_sif", "exonerate_model"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["alignment_dir"])

    def test_busco_task_entry_is_registered(self) -> None:
        """Expose the BUSCO task at the new annotation-QC stage boundary."""
        entry = get_entry("busco_assess_proteins")

        self.assertEqual(entry.category, "task")
        self.assertIn("BUSCO", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["proteins_fasta", "lineage_dataset", "busco_sif", "busco_cpu", "busco_mode"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["busco_run_dir"])

    def test_consensus_prep_workflow_entry_uses_corrected_pre_evm_inputs(self) -> None:
        """Expose the corrected pre-EVM workflow contract in the registry."""
        entry = get_entry("consensus_annotation_evm_prep")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("pre-EVM", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["pasa_results", "transdecoder_results", "protein_evidence_results", "braker3_results"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["results_dir"])

    def test_prediction_prep_task_entry_is_registered(self) -> None:
        """Expose the merged BRAKER3-plus-TransDecoder prediction staging task."""
        entry = get_entry("prepare_evm_prediction_inputs")

        self.assertEqual(entry.category, "task")
        self.assertIn("predictions.gff3", entry.description)
        self.assertIn("source-preserving", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["transdecoder_results", "braker3_results"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["prediction_inputs_dir"])

    def test_evm_execution_task_entry_is_registered(self) -> None:
        """Expose the downstream EVM execution-input boundary in the catalog."""
        entry = get_entry("prepare_evm_execution_inputs")

        self.assertEqual(entry.category, "task")
        self.assertIn("evm.weights", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["evm_prep_results", "evm_weights_text"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["evm_execution_inputs_dir"])

    def test_consensus_evm_workflow_entry_consumes_prep_bundle(self) -> None:
        """Expose the Milestone 2 EVM workflow as downstream of the pre-EVM bundle."""
        entry = get_entry("consensus_annotation_evm")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("pre-EVM bundle", entry.description)
        self.assertEqual(entry.inputs[0].name, "evm_prep_results")
        self.assertEqual([field.name for field in entry.outputs], ["results_dir"])

    def test_transcript_evidence_workflow_entry_mentions_internal_denovo_branch(self) -> None:
        """Expose the transcript workflow as including both Trinity branches."""
        entry = get_entry("transcript_evidence_generation")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("de novo Trinity", entry.description)
        self.assertIn("both Trinity branches required upstream of PASA", entry.description)
        self.assertIn("all-sample merge contract", entry.description)

    def test_pasa_transcript_alignment_entry_uses_internal_denovo_input(self) -> None:
        """Expose the PASA workflow as consuming the transcript bundle directly."""
        entry = get_entry("pasa_transcript_alignment")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("internally produced de novo Trinity", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            [
                "genome",
                "transcript_evidence_results",
                "univec_fasta",
                "pasa_config_template",
                "pasa_sif",
                "seqclean_threads",
                "pasa_cpu",
                "pasa_max_intron_length",
                "pasa_aligners",
                "pasa_db_name",
            ],
        )
        self.assertIn("trinity_denovo/", entry.inputs[1].description)

    def test_pasa_post_evm_staging_task_entry_is_registered(self) -> None:
        """Expose the PASA post-EVM staging boundary in the catalog."""
        entry = get_entry("prepare_pasa_update_inputs")

        self.assertEqual(entry.category, "task")
        self.assertIn("PASA and EVM result bundles", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["pasa_results", "evm_results", "pasa_annot_compare_template", "fasta36_binary_path"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["pasa_update_inputs_dir"])

    def test_annotation_refinement_pasa_workflow_entry_is_registered(self) -> None:
        """Expose the Milestone 3 PASA refinement workflow as downstream of PASA and EVM bundles."""
        entry = get_entry("annotation_refinement_pasa")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("PASA and EVM bundles", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs[:3]],
            ["pasa_results", "evm_results", "pasa_annot_compare_template"],
        )
        self.assertIn("at least 2", entry.inputs[7].description)
        self.assertEqual([field.name for field in entry.outputs], ["results_dir"])

    def test_repeatmasker_conversion_task_entry_is_registered(self) -> None:
        """Expose the RepeatMasker conversion task at the new post-PASA stage boundary."""
        entry = get_entry("repeatmasker_out_to_bed")

        self.assertEqual(entry.category, "task")
        self.assertIn("RepeatMasker", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["repeatmasker_out", "rmout_to_gff3_script", "repeat_filter_sif"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["repeatmasker_dir"])

    def test_annotation_repeat_filtering_workflow_entry_is_registered(self) -> None:
        """Expose the repeat-filtering workflow as the next boundary after PASA refinement."""
        entry = get_entry("annotation_repeat_filtering")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("PASA-updated GFF3 boundary", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs[:3]],
            ["pasa_update_results", "repeatmasker_out", "funannotate_db_path"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["results_dir"])

    def test_annotation_qc_busco_workflow_entry_is_registered(self) -> None:
        """Expose BUSCO QC as the next workflow boundary after repeat filtering."""
        entry = get_entry("annotation_qc_busco")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("repeat-filtered protein FASTA boundary", entry.description)
        self.assertEqual(
            [field.name for field in entry.inputs],
            ["repeat_filter_results", "busco_lineages_text", "busco_sif", "busco_cpu"],
        )
        self.assertEqual([field.name for field in entry.outputs], ["results_dir"])

    def test_braker3_workflow_entry_uses_tutorial_backed_language(self) -> None:
        """Expose the BRAKER3 workflow as tutorial-backed rather than purely inferred."""
        entry = get_entry("ab_initio_annotation_braker3")

        self.assertEqual(entry.category, "workflow")
        self.assertIn("Galaxy tutorial-backed", entry.description)
        self.assertIn("preserves upstream braker.gff3 source values", entry.description)
