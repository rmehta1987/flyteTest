"""Synthetic coverage for the planner-facing biology type layer.

    These tests cover planning-time dataclasses and adapter logic without changing
    any runnable Flyte task signatures.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.planner_adapters import (
    annotation_evidence_from_ab_initio_bundle,
    annotation_evidence_from_braker_bundle,
    annotation_evidence_from_manifest,
    consensus_annotation_from_manifest,
    protein_evidence_from_bundle,
    protein_evidence_from_manifest,
    quality_assessment_target_from_manifest,
    read_set_from_asset,
    reference_genome_from_asset,
    transcript_evidence_from_manifest,
)
from flytetest.planner_types import (
    AlignmentSet,
    AnnotationEvidenceSet,
    ConsensusAnnotation,
    KnownSites,
    ProteinEvidenceSet,
    QualityAssessmentTarget,
    ReadSet,
    ReferenceGenome,
    TOP_LEVEL_PLANNER_TYPE_ADDITION_RULES,
    TranscriptEvidenceSet,
    VariantCallSet,
)
from flytetest.types.assets import (
    AbInitioResultBundle,
    AssetToolProvenance,
    Braker3ResultBundle,
    CleanedTranscriptDataset,
    CombinedTrinityTranscriptAsset,
    ProteinEvidenceResultBundle,
    ProteinReferenceDatasetAsset,
    ReadPair,
    RnaSeqAlignmentResult,
    TrinityGenomeGuidedAssemblyResult,
)
from flytetest.types.assets import ReferenceGenome as AssetReferenceGenome


class PlannerTypeTests(TestCase):
    """Coverage for the new planner-facing dataclasses and adapter rules.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_nested_planner_types_round_trip_through_dicts(self) -> None:
        """Round-trip nested planner dataclasses through the planning-time serialization path.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        reference = ReferenceGenome(
            fasta_path=Path("data/braker3/reference/genome.fa"),
            organism_name="fly",
            source_result_dir=Path("results/reference"),
            notes=("Planner-facing genome boundary.",),
        )
        reads = ReadSet(
            sample_id="sampleA",
            left_reads_path=Path("data/transcriptomics/ref-based/reads_1.fq.gz"),
            right_reads_path=Path("data/transcriptomics/ref-based/reads_2.fq.gz"),
            source_manifest_path=Path("results/transcript/run_manifest.json"),
        )
        transcript_evidence = TranscriptEvidenceSet(
            reference_genome=reference,
            read_sets=(reads,),
            de_novo_transcripts_path=Path("results/trinity_denovo.Trinity.fasta"),
            genome_guided_transcripts_path=Path("results/trinity_gg.Trinity-GG.fasta"),
            stringtie_gtf_path=Path("results/transcripts.gtf"),
            merged_bam_path=Path("results/merged.bam"),
        )
        protein_evidence = ProteinEvidenceSet(
            reference_genome=reference,
            source_protein_fastas=(Path("data/braker3/protein_data/fastas/proteins.fa"),),
            evm_ready_gff3_path=Path("results/protein_evidence.evm.gff3"),
        )
        annotation_evidence = AnnotationEvidenceSet(
            reference_genome=reference,
            transcript_evidence=transcript_evidence,
            protein_evidence=protein_evidence,
            transcript_alignments_gff3_path=Path("results/transcripts.gff3"),
            protein_alignments_gff3_path=Path("results/proteins.gff3"),
            combined_predictions_gff3_path=Path("results/predictions.gff3"),
        )
        consensus = ConsensusAnnotation(
            reference_genome=reference,
            annotation_gff3_path=Path("results/EVM.all.sort.gff3"),
            supporting_evidence=annotation_evidence,
        )
        target = QualityAssessmentTarget(
            reference_genome=reference,
            consensus_annotation=consensus,
            annotation_gff3_path=consensus.annotation_gff3_path,
            proteins_fasta_path=Path("results/all_repeats_removed.proteins.fa"),
        )

        self.assertEqual(ReferenceGenome.from_dict(reference.to_dict()), reference)
        self.assertEqual(TranscriptEvidenceSet.from_dict(transcript_evidence.to_dict()), transcript_evidence)
        self.assertEqual(AnnotationEvidenceSet.from_dict(annotation_evidence.to_dict()), annotation_evidence)
        self.assertEqual(QualityAssessmentTarget.from_dict(target.to_dict()), target)

    def test_addition_rules_match_design_constraints(self) -> None:
        """Keep the top-level planner type addition rules explicit and biology-first.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        self.assertEqual(len(TOP_LEVEL_PLANNER_TYPE_ADDITION_RULES), 3)
        self.assertIn("biological entity", TOP_LEVEL_PLANNER_TYPE_ADDITION_RULES[0])
        self.assertIn("reusable stage boundary", TOP_LEVEL_PLANNER_TYPE_ADDITION_RULES[1])
        self.assertIn("compatibility surface", TOP_LEVEL_PLANNER_TYPE_ADDITION_RULES[2])

    def test_lower_level_asset_adapters_preserve_current_metadata(self) -> None:
        """Adapt the existing path-centric asset layer into planner-facing types without mutation.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        genome_asset = AssetReferenceGenome(
            fasta_path=Path("data/braker3/reference/genome.fa"),
            organism_name="Example organism",
            assembly_name="asm1",
            taxonomy_id=7227,
        )
        read_pair = ReadPair(
            sample_id="sampleA",
            left_reads_path=Path("data/transcriptomics/ref-based/reads_1.fq.gz"),
            right_reads_path=Path("data/transcriptomics/ref-based/reads_2.fq.gz"),
            condition="treated",
        )

        reference = reference_genome_from_asset(
            genome_asset,
            source_result_dir=Path("results/braker3"),
            source_manifest_path=Path("results/braker3/run_manifest.json"),
        )
        reads = read_set_from_asset(
            read_pair,
            source_result_dir=Path("results/transcript"),
            source_manifest_path=Path("results/transcript/run_manifest.json"),
        )

        self.assertEqual(reference.organism_name, "Example organism")
        self.assertEqual(reference.assembly_name, "asm1")
        self.assertEqual(reference.taxonomy_id, 7227)
        self.assertEqual(reference.source_result_dir, Path("results/braker3"))
        self.assertEqual(reads.sample_id, "sampleA")
        self.assertEqual(reads.condition, "treated")
        self.assertEqual(reads.left_reads_path, Path("data/transcriptomics/ref-based/reads_1.fq.gz"))

    def test_generic_asset_names_round_trip_with_typed_provenance(self) -> None:
        """Round-trip generic asset names while preserving legacy provenance.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        alignment = RnaSeqAlignmentResult(
            sample_id="sampleA",
            output_dir=Path("results/star"),
            sorted_bam_path=Path("results/star/Aligned.sortedByCoord.out.bam"),
            provenance=AssetToolProvenance(
                tool_name="STAR",
                tool_stage="RNA-seq genome alignment",
                legacy_asset_name="StarAlignmentResult",
                source_manifest_key="rna_seq_alignment",
            ),
        )
        genome_guided = TrinityGenomeGuidedAssemblyResult(
            output_dir=Path("results/trinity_gg"),
            assembly_fasta_path=Path("results/trinity_gg/Trinity-GG.fasta"),
        )
        cleaned = CleanedTranscriptDataset(
            output_dir=Path("results/pasa/seqclean"),
            clean_fasta_path=Path("results/pasa/seqclean/transcripts.fa.clean"),
            input_transcripts=CombinedTrinityTranscriptAsset(
                fasta_path=Path("results/pasa/combined.fa"),
                genome_guided_transcripts=genome_guided,
            ),
            provenance=AssetToolProvenance(
                tool_name="PASA seqclean",
                tool_stage="transcript cleaning",
                legacy_asset_name="PasaCleanedTranscriptAsset",
                source_manifest_key="cleaned_transcript_dataset",
            ),
        )
        ab_initio = AbInitioResultBundle(
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
                source_manifest_key="ab_initio_result_bundle",
            ),
        )

        self.assertEqual(RnaSeqAlignmentResult.from_dict(alignment.to_dict()), alignment)
        self.assertEqual(CleanedTranscriptDataset.from_dict(cleaned.to_dict()), cleaned)
        self.assertEqual(AbInitioResultBundle.from_dict(ab_initio.to_dict()), ab_initio)
        self.assertEqual(ab_initio.provenance.legacy_asset_name, "Braker3ResultBundle")

    def test_transcript_evidence_manifest_adapter_uses_current_bundle_shape(self) -> None:
        """Lift the transcript-evidence collector manifest into the new planner type.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        manifest = {
            "workflow": "transcript_evidence_generation",
            "notes_alignment": {
                "reason": "Both Trinity branches remain visible upstream of PASA.",
            },
            "assumptions": ["Single-sample STAR alignment remains the current simplification."],
            "outputs": {
                "trinity_denovo_fasta": "results/trinity_denovo.Trinity.fasta",
                "trinity_gg_fasta": "results/trinity_gg.Trinity-GG.fasta",
                "stringtie_gtf": "results/transcripts.gtf",
                "merged_bam": "results/merged.bam",
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
        }

        adapted = transcript_evidence_from_manifest(manifest)

        self.assertEqual(adapted.reference_genome.fasta_path, Path("data/braker3/reference/genome.fa"))
        self.assertEqual(adapted.read_sets[0].sample_id, "sampleA")
        self.assertEqual(adapted.de_novo_transcripts_path, Path("results/trinity_denovo.Trinity.fasta"))
        self.assertEqual(adapted.genome_guided_transcripts_path, Path("results/trinity_gg.Trinity-GG.fasta"))
        self.assertIn("Both Trinity branches", adapted.notes[0])

    def test_protein_evidence_adapters_cover_bundle_and_manifest_inputs(self) -> None:
        """Adapt both the current result bundle and the current manifest shape.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        genome_asset = AssetReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        staged_dataset = ProteinReferenceDatasetAsset(
            staged_dir=Path("results/protein/staged"),
            combined_fasta_path=Path("results/protein/staged/proteins.all.fa"),
            source_fasta_paths=(
                Path("data/braker3/protein_data/fastas/proteins.fa"),
                Path("data/braker3/protein_data/fastas/proteins_extra.fa"),
            ),
        )
        bundle = ProteinEvidenceResultBundle(
            result_dir=Path("results/protein"),
            combined_protein_fasta_path=Path("results/protein/proteins.all.fa"),
            chunk_dir=Path("results/protein/chunks"),
            raw_chunk_root=Path("results/protein/raw"),
            evm_chunk_root=Path("results/protein/evm"),
            concatenated_raw_output_path=Path("results/protein/all_chunks.exonerate.out"),
            concatenated_evm_gff3_path=Path("results/protein/protein_evidence.evm.gff3"),
            reference_genome=genome_asset,
            staged_dataset=staged_dataset,
            notes=("Bundle notes stay visible.",),
        )
        manifest = {
            "workflow": "protein_evidence_alignment",
            "assumptions": ["Chunking follows the combined FASTA order."],
            "outputs": {
                "concatenated_raw_exonerate": "results/protein/all_chunks.exonerate.out",
                "concatenated_evm_protein_gff3": "results/protein/protein_evidence.evm.gff3",
            },
            "chunking": {"proteins_per_chunk": 250},
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
                    "source_fasta_paths": [
                        "data/braker3/protein_data/fastas/proteins.fa",
                        "data/braker3/protein_data/fastas/proteins_extra.fa",
                    ],
                },
            },
        }

        from_bundle = protein_evidence_from_bundle(bundle)
        from_manifest = protein_evidence_from_manifest(manifest)

        self.assertEqual(
            from_bundle.source_protein_fastas,
            (
                Path("data/braker3/protein_data/fastas/proteins.fa"),
                Path("data/braker3/protein_data/fastas/proteins_extra.fa"),
            ),
        )
        self.assertEqual(from_bundle.evm_ready_gff3_path, Path("results/protein/protein_evidence.evm.gff3"))
        self.assertEqual(from_manifest.source_protein_fastas, from_bundle.source_protein_fastas)
        self.assertIn("250 proteins", from_manifest.notes[-1])

    def test_annotation_evidence_adapters_cover_braker_and_pre_evm_boundaries(self) -> None:
        """Adapt both the BRAKER-only and pre-EVM evidence boundaries into one planner type.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        braker_bundle = Braker3ResultBundle(
            result_dir=Path("results/braker3"),
            staged_inputs_dir=Path("results/braker3/staged"),
            raw_run_dir=Path("results/braker3/raw"),
            normalized_dir=Path("results/braker3/normalized"),
            braker_gff3_path=Path("results/braker3/raw/braker.gff3"),
            normalized_gff3_path=Path("results/braker3/normalized/braker.normalized.gff3"),
            reference_genome=AssetReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa")),
            notes=("BRAKER notes.",),
        )
        pre_evm_manifest = {
            "workflow": "consensus_annotation_evm_prep",
            "notes_backed_behavior": ["Pre-EVM contract is assembled from the current stage bundles."],
            "repo_policy": ["Predictions stay source-preserving."],
            "source_bundles": {
                "pasa_results": "results/pasa",
                "protein_evidence_results": "results/protein",
            },
            "outputs": {
                "transcripts_gff3": "results/pre_evm/transcripts.gff3",
                "predictions_gff3": "results/pre_evm/predictions.gff3",
                "proteins_gff3": "results/pre_evm/proteins.gff3",
            },
            "assets": {
                "evm_input_preparation_bundle": {
                    "reference_genome_fasta_path": "data/braker3/reference/genome.fa",
                    "prediction_bundle": {
                        "braker_gff3_path": "results/pre_evm/braker.gff3",
                    },
                },
            },
            "pre_evm_contract": {
                "reference_genome_fasta": {"path": "data/braker3/reference/genome.fa"},
            },
        }

        generic_bundle = AbInitioResultBundle(
            result_dir=Path("results/ab_initio"),
            staged_inputs_dir=Path("results/ab_initio/staged"),
            raw_run_dir=Path("results/ab_initio/raw"),
            normalized_dir=Path("results/ab_initio/normalized"),
            braker_gff3_path=Path("results/ab_initio/raw/braker.gff3"),
            normalized_gff3_path=Path("results/ab_initio/normalized/braker.normalized.gff3"),
            reference_genome=AssetReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa")),
            provenance=AssetToolProvenance(tool_name="BRAKER3", tool_stage="ab initio annotation"),
        )

        from_bundle = annotation_evidence_from_braker_bundle(braker_bundle)
        from_generic_bundle = annotation_evidence_from_ab_initio_bundle(generic_bundle)
        from_manifest = annotation_evidence_from_manifest(pre_evm_manifest)

        self.assertEqual(from_bundle.ab_initio_predictions_gff3_path, Path("results/braker3/normalized/braker.normalized.gff3"))
        self.assertEqual(from_generic_bundle.ab_initio_predictions_gff3_path, Path("results/ab_initio/normalized/braker.normalized.gff3"))
        self.assertIn("BRAKER3", from_generic_bundle.notes[0])
        self.assertEqual(from_manifest.reference_genome.fasta_path, Path("data/braker3/reference/genome.fa"))
        self.assertEqual(from_manifest.transcript_alignments_gff3_path, Path("results/pre_evm/transcripts.gff3"))
        self.assertEqual(from_manifest.protein_alignments_gff3_path, Path("results/pre_evm/proteins.gff3"))
        self.assertEqual(from_manifest.combined_predictions_gff3_path, Path("results/pre_evm/predictions.gff3"))
        self.assertEqual(from_manifest.ab_initio_predictions_gff3_path, Path("results/pre_evm/braker.gff3"))

    def test_consensus_and_qc_adapters_cover_current_downstream_boundaries(self) -> None:
        """Adapt EVM and repeat-filter manifests into consensus and QC planner targets.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        evm_manifest = {
            "workflow": "consensus_annotation_evm",
            "assumptions": ["EVM execution remains deterministic and local."],
            "source_bundle": {"evm_prep_results": "results/pre_evm"},
            "outputs": {
                "sorted_gff3": "results/evm/EVM.all.sort.gff3",
                "weights_path": "results/evm/evm.weights",
            },
            "stage_manifests": {
                "evm_execution_inputs": {
                    "outputs": {
                        "transcripts_gff3": "results/pre_evm/transcripts.gff3",
                        "predictions_gff3": "results/pre_evm/predictions.gff3",
                        "proteins_gff3": "results/pre_evm/proteins.gff3",
                    },
                },
            },
            "assets": {
                "evm_consensus_result_bundle": {
                    "execution_input_bundle": {
                        "reference_genome_fasta_path": "data/braker3/reference/genome.fa",
                    },
                },
            },
        }
        repeat_filter_manifest = {
            "workflow": "annotation_repeat_filtering",
            "assumptions": ["Repeat-filtered outputs are QC-ready."],
            "inputs": {"reference_genome": "data/braker3/reference/genome.fa"},
            "outputs": {
                "all_repeats_removed_gff3": "results/repeat/all_repeats_removed.gff3",
                "final_proteins_fasta": "results/repeat/all_repeats_removed.proteins.fa",
            },
        }

        consensus = consensus_annotation_from_manifest(evm_manifest)
        qc_target = quality_assessment_target_from_manifest(repeat_filter_manifest)

        self.assertEqual(consensus.annotation_gff3_path, Path("results/evm/EVM.all.sort.gff3"))
        self.assertEqual(consensus.weights_path, Path("results/evm/evm.weights"))
        self.assertEqual(consensus.supporting_evidence.combined_predictions_gff3_path, Path("results/pre_evm/predictions.gff3"))
        self.assertEqual(qc_target.annotation_gff3_path, Path("results/repeat/all_repeats_removed.gff3"))
        self.assertEqual(qc_target.proteins_fasta_path, Path("results/repeat/all_repeats_removed.proteins.fa"))

    def test_alignment_set_round_trips(self) -> None:
        """Round-trip AlignmentSet with every field populated."""
        alignment = AlignmentSet(
            bam_path=Path("results/align/NA12878.bam"),
            sample_id="NA12878",
            reference_fasta_path=Path("data/gatk/reference/GRCh38.fa"),
            sorted="coordinate",
            duplicates_marked=True,
            bqsr_applied=True,
            bam_index_path=Path("results/align/NA12878.bai"),
            source_result_dir=Path("results/align"),
            source_manifest_path=Path("results/align/run_manifest.json"),
            notes=("Coordinate-sorted, dedup'd, BQSR-recalibrated.",),
        )
        self.assertEqual(AlignmentSet.from_dict(alignment.to_dict()), alignment)

    def test_variant_call_set_round_trips_gvcf(self) -> None:
        """Round-trip a per-sample GVCF VariantCallSet."""
        gvcf = VariantCallSet(
            vcf_path=Path("results/hc/NA12878.g.vcf"),
            variant_type="gvcf",
            caller="haplotype_caller",
            sample_ids=("NA12878",),
            reference_fasta_path=Path("data/gatk/reference/GRCh38.fa"),
            vcf_index_path=Path("results/hc/NA12878.g.vcf.idx"),
            build="GRCh38",
            source_manifest_path=Path("results/hc/run_manifest.json"),
        )
        self.assertEqual(gvcf.variant_type, "gvcf")
        self.assertEqual(VariantCallSet.from_dict(gvcf.to_dict()), gvcf)

    def test_variant_call_set_round_trips_vcf(self) -> None:
        """Round-trip a joint-called VCF VariantCallSet."""
        vcf = VariantCallSet(
            vcf_path=Path("results/joint/cohort_genotyped.vcf"),
            variant_type="vcf",
            caller="joint_call_gvcfs",
            sample_ids=("NA12878", "NA12891", "NA12892"),
            reference_fasta_path=Path("data/gatk/reference/GRCh38.fa"),
            vcf_index_path=Path("results/joint/cohort_genotyped.vcf.idx"),
            build="GRCh38",
            cohort_id="cohort",
            notes=("Joint-genotyped across trio.",),
        )
        self.assertEqual(vcf.variant_type, "vcf")
        self.assertEqual(VariantCallSet.from_dict(vcf.to_dict()), vcf)

    def test_known_sites_round_trips_with_vqsr_fields(self) -> None:
        """Round-trip KnownSites carrying VQSR-facing training / truth / prior fields."""
        sites = KnownSites(
            vcf_path=Path("data/gatk/known_sites/hapmap_3.3.hg38.vcf.gz"),
            resource_name="hapmap",
            index_path=Path("data/gatk/known_sites/hapmap_3.3.hg38.vcf.gz.tbi"),
            build="GRCh38",
            known=False,
            training=True,
            truth=True,
            prior=15.0,
            vqsr_mode="SNP",
            notes=("VQSR SNP truth resource.",),
        )
        self.assertEqual(KnownSites.from_dict(sites.to_dict()), sites)

    def test_known_sites_defaults_minimal(self) -> None:
        """Minimal KnownSites (vcf_path + resource_name) lands expected defaults."""
        sites = KnownSites(
            vcf_path=Path("data/gatk/known_sites/dbsnp.vcf.gz"),
            resource_name="dbsnp",
        )
        self.assertTrue(sites.known)
        self.assertFalse(sites.training)
        self.assertFalse(sites.truth)
        self.assertIsNone(sites.prior)
        self.assertIsNone(sites.vqsr_mode)
        self.assertEqual(sites.notes, ())
        self.assertEqual(KnownSites.from_dict(sites.to_dict()), sites)
