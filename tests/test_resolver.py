"""Synthetic coverage for the first manifest-backed resolver layer.

These tests keep Milestone 3 focused on local input resolution rules without
changing the current prompt planner or execution paths.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.planner_types import ProteinEvidenceSet, QualityAssessmentTarget, ReferenceGenome, TranscriptEvidenceSet
from flytetest.resolver import LocalManifestAssetResolver
from flytetest.types.assets import AbInitioResultBundle, AssetToolProvenance, ProteinEvidenceResultBundle, ProteinReferenceDatasetAsset
from flytetest.types.assets import ReferenceGenome as AssetReferenceGenome


class ResolverTests(TestCase):
    """Coverage for explicit, manifest-backed, and bundle-backed resolution."""

    def test_explicit_binding_wins_over_discovered_sources(self) -> None:
        """Prefer an explicit local planner value over any discovered manifest candidate."""
        resolver = LocalManifestAssetResolver()
        explicit_reference = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))

        result = resolver.resolve(
            "ReferenceGenome",
            explicit_bindings={"ReferenceGenome": explicit_reference},
            manifest_sources=(),
        )

        self.assertTrue(result.is_resolved)
        self.assertIs(result.resolved_value, explicit_reference)
        self.assertEqual(result.selected_source.kind, "explicit_binding")

    def test_resolver_can_build_transcript_evidence_from_manifest_path(self) -> None:
        """Resolve transcript evidence from a current manifest-shaped local results directory."""
        resolver = LocalManifestAssetResolver()
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "transcript_results"
            result_dir.mkdir()
            (result_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow": "transcript_evidence_generation",
                        "notes_alignment": {"reason": "Both Trinity branches remain visible upstream of PASA."},
                        "assumptions": ["Single-sample STAR alignment remains the current simplification."],
                        "outputs": {
                            "trinity_denovo_fasta": str(result_dir / "trinity_denovo.Trinity.fasta"),
                            "trinity_gg_fasta": str(result_dir / "trinity_gg.Trinity-GG.fasta"),
                            "stringtie_gtf": str(result_dir / "transcripts.gtf"),
                            "merged_bam": str(result_dir / "merged.bam"),
                        },
                        "assets": {
                            "reference_genome": {
                                "fasta_path": "data/braker3/reference/genome.fa",
                                "organism_name": "Example organism",
                                "assembly_name": None,
                                "taxonomy_id": None,
                                "softmasked_fasta_path": None,
                                "annotation_gff3_path": None,
                                "notes": [],
                            },
                            "read_pair": {
                                "sample_id": "sampleA",
                                "left_reads_path": "data/transcriptomics/ref-based/reads_1.fq.gz",
                                "right_reads_path": "data/transcriptomics/ref-based/reads_2.fq.gz",
                                "platform": "ILLUMINA",
                                "strandedness": None,
                                "condition": None,
                                "replicate_label": None,
                            },
                        },
                    },
                    indent=2,
                )
            )

            result = resolver.resolve("TranscriptEvidenceSet", manifest_sources=(result_dir,))

        self.assertTrue(result.is_resolved)
        self.assertIsInstance(result.resolved_value, TranscriptEvidenceSet)
        self.assertEqual(result.selected_source.kind, "manifest")
        self.assertEqual(result.resolved_value.reference_genome.fasta_path, Path("data/braker3/reference/genome.fa"))
        self.assertEqual(result.resolved_value.read_sets[0].sample_id, "sampleA")

    def test_resolver_reports_ambiguity_instead_of_guessing(self) -> None:
        """Return an unresolved ambiguity when more than one candidate is found."""
        resolver = LocalManifestAssetResolver()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifests = []
            for index in (1, 2):
                result_dir = tmp_path / f"protein_results_{index}"
                result_dir.mkdir()
                manifest_path = result_dir / "run_manifest.json"
                protein_fasta_path = (
                    "data/braker3/protein_data/fastas/proteins.fa"
                    if index == 1
                    else "data/braker3/protein_data/fastas/proteins_extra.fa"
                )
                manifest_path.write_text(
                    json.dumps(
                        {
                            "workflow": "protein_evidence_alignment",
                            "outputs": {
                                "concatenated_raw_exonerate": str(result_dir / "all_chunks.exonerate.out"),
                                "concatenated_evm_protein_gff3": str(result_dir / "protein_evidence.evm.gff3"),
                            },
                            "assets": {
                                "reference_genome": {
                                    "fasta_path": "data/braker3/reference/genome.fa",
                                    "organism_name": None,
                                    "assembly_name": None,
                                    "taxonomy_id": None,
                                    "softmasked_fasta_path": None,
                                    "annotation_gff3_path": None,
                                    "notes": [],
                                },
                                "protein_reference_dataset": {
                                    "source_fasta_paths": [protein_fasta_path],
                                },
                            },
                        },
                        indent=2,
                    )
                )
                manifests.append(result_dir)

            result = resolver.resolve("ProteinEvidenceSet", manifest_sources=tuple(manifests))

        self.assertFalse(result.is_resolved)
        self.assertEqual(result.candidate_count, 2)
        self.assertIn("choose one explicitly", result.unresolved_requirements[0])

    def test_resolver_reports_missing_when_nothing_matches(self) -> None:
        """Return a missing-input message when no source can satisfy the request."""
        resolver = LocalManifestAssetResolver()

        result = resolver.resolve("QualityAssessmentTarget")

        self.assertFalse(result.is_resolved)
        self.assertEqual(result.candidate_count, 0)
        self.assertIn("No QualityAssessmentTarget", result.unresolved_requirements[0])

    def test_resolver_can_use_current_result_bundle_objects(self) -> None:
        """Resolve from current registered-workflow result bundle objects when provided directly."""
        resolver = LocalManifestAssetResolver()
        bundle = ProteinEvidenceResultBundle(
            result_dir=Path("results/protein"),
            combined_protein_fasta_path=Path("results/protein/proteins.all.fa"),
            chunk_dir=Path("results/protein/chunks"),
            raw_chunk_root=Path("results/protein/raw"),
            evm_chunk_root=Path("results/protein/evm"),
            concatenated_raw_output_path=Path("results/protein/all_chunks.exonerate.out"),
            concatenated_evm_gff3_path=Path("results/protein/protein_evidence.evm.gff3"),
            reference_genome=AssetReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa")),
            staged_dataset=ProteinReferenceDatasetAsset(
                staged_dir=Path("results/protein/staged"),
                combined_fasta_path=Path("results/protein/staged/proteins.all.fa"),
                source_fasta_paths=(Path("data/braker3/protein_data/fastas/proteins.fa"),),
            ),
        )

        result = resolver.resolve("ProteinEvidenceSet", result_bundles=(bundle,))

        self.assertTrue(result.is_resolved)
        self.assertIsInstance(result.resolved_value, ProteinEvidenceSet)
        self.assertEqual(result.selected_source.kind, "result_bundle")
        self.assertEqual(result.resolved_value.evm_ready_gff3_path, Path("results/protein/protein_evidence.evm.gff3"))

    def test_resolver_accepts_generic_ab_initio_bundle_objects(self) -> None:
        """Resolve generic ab initio bundles without losing legacy compatibility."""
        resolver = LocalManifestAssetResolver()
        bundle = AbInitioResultBundle(
            result_dir=Path("results/ab_initio"),
            staged_inputs_dir=Path("results/ab_initio/staged"),
            raw_run_dir=Path("results/ab_initio/raw"),
            normalized_dir=Path("results/ab_initio/normalized"),
            braker_gff3_path=Path("results/ab_initio/raw/braker.gff3"),
            normalized_gff3_path=Path("results/ab_initio/normalized/braker.normalized.gff3"),
            reference_genome=AssetReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa")),
            provenance=AssetToolProvenance(
                tool_name="BRAKER3",
                tool_stage="ab initio annotation",
                legacy_asset_name="Braker3ResultBundle",
            ),
        )

        result = resolver.resolve("AnnotationEvidenceSet", result_bundles=(bundle,))

        self.assertTrue(result.is_resolved)
        self.assertEqual(result.selected_source.bundle_type, "AbInitioResultBundle")
        self.assertEqual(result.resolved_value.ab_initio_predictions_gff3_path, bundle.normalized_gff3_path)
        self.assertIn("BRAKER3", result.resolved_value.notes[0])

    def test_resolver_can_satisfy_downstream_qc_target_from_prior_result_manifest(self) -> None:
        """Resolve a downstream QC target from a prior repeat-filter result bundle manifest."""
        resolver = LocalManifestAssetResolver()
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "repeat_filter_results"
            result_dir.mkdir()
            (result_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow": "annotation_repeat_filtering",
                        "assumptions": ["Repeat-filtered outputs are QC-ready."],
                        "inputs": {
                            "reference_genome": "data/braker3/reference/genome.fa",
                        },
                        "outputs": {
                            "all_repeats_removed_gff3": str(result_dir / "all_repeats_removed.gff3"),
                            "final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                        },
                    },
                    indent=2,
                )
            )

            result = resolver.resolve("QualityAssessmentTarget", manifest_sources=(result_dir,))

        self.assertTrue(result.is_resolved)
        self.assertIsInstance(result.resolved_value, QualityAssessmentTarget)
        self.assertEqual(result.resolved_value.annotation_gff3_path, result_dir / "all_repeats_removed.gff3")
        self.assertEqual(result.resolved_value.proteins_fasta_path, result_dir / "all_repeats_removed.proteins.fa")
