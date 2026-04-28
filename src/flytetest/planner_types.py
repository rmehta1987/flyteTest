"""Planner-facing biology types for the `realtime` architecture migration.

This module defines the small stable dataclass layer that `DESIGN.md` describes
as the future planning and input-mapping layer. The types in this file are the
planner's vocabulary for describing workflow families, stage boundaries, and
the biology objects that can flow between registered tasks or workflows.

The key idea is that a planner type is not a runtime object. It is a
structured description of a biological thing the planner can reason about
before execution, such as a reference genome, transcript evidence set, protein
evidence set, consensus annotation, or quality-assessment target. Those
descriptions let the planner match prompts to supported workflow families,
resolve inputs from manifests and result bundles, and freeze a reviewable
binding plan before execution begins.

The module deliberately lives outside `src/flytetest/types/` so these
higher-level biology types stay separate from the existing lower-level
local-path asset catalog used by manifests and result collectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flytetest.serialization import SerializableMixin, deserialize_value_strict, serialize_value_plain

TOP_LEVEL_PLANNER_TYPE_ADDITION_RULES: tuple[str, ...] = (
    "Add a new top-level planner type only when a workflow family introduces a genuinely new biological entity.",
    "Add a new top-level planner type only when a workflow family introduces a reusable stage boundary that existing planner types cannot express clearly.",
    "Add a new top-level planner type only when a workflow family introduces a new compatibility surface that should stay stable across tool churn.",
)


class PlannerSerializable(SerializableMixin):
    _serialize_fn = staticmethod(serialize_value_plain)
    _deserialize_fn = staticmethod(deserialize_value_strict)


@dataclass(frozen=True, slots=True)
class ReferenceGenome(PlannerSerializable):
    """Planner-facing reference genome identity independent of workflow wrappers.

    This is the main genome description used during planning. It stores the
    main FASTA plus optional organism details and, when available, a pointer
    back to the result folder or manifest it came from.
"""

    fasta_path: Path
    organism_name: str | None = None
    assembly_name: str | None = None
    taxonomy_id: int | None = None
    softmasked_fasta_path: Path | None = None
    annotation_gff3_path: Path | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class VariantCallSet(PlannerSerializable):
    """Planner-facing variant call set identity for post-calling workflows."""

    vcf_path: Path
    variant_type: str = "vcf"
    sample_id: str = ""
    source_result_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReadPair(PlannerSerializable):
    """Planner-facing paired-end DNA read identity for germline variant calling.

    Mirrors the ReadPair binding shape used by variant-calling bundles:
    {sample_id, r1_path, r2_path}.  Keeps read identity separate from the
    list-of-paths form consumed by individual workflow scalar inputs.
"""

    sample_id: str
    r1_path: Path
    r2_path: Path
    platform: str = "ILLUMINA"
    source_result_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReadSet(PlannerSerializable):
    """Planner-facing paired-read identity for RNA-seq-backed workflows.

    Planning uses this type for RNA-seq read inputs without tying the meaning
    of the data to any one aligner, quantifier, or transcript-assembly step.
"""

    sample_id: str
    left_reads_path: Path
    right_reads_path: Path
    platform: str = "ILLUMINA"
    strandedness: str | None = None
    condition: str | None = None
    replicate_label: str | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TranscriptEvidenceSet(PlannerSerializable):
    """Planner-facing transcript evidence boundary spanning reads, BAMs, and assemblies.

    This type groups the current transcript-evidence outputs under one
    biological idea so later planning code can reason about transcript support
    without caring which lower-level step produced each file.
"""

    reference_genome: ReferenceGenome
    read_sets: tuple[ReadSet, ...] = field(default_factory=tuple)
    de_novo_transcripts_path: Path | None = None
    genome_guided_transcripts_path: Path | None = None
    stringtie_gtf_path: Path | None = None
    merged_bam_path: Path | None = None
    pasa_assemblies_gff3_path: Path | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ProteinEvidenceSet(PlannerSerializable):
    """Planner-facing protein evidence boundary spanning source FASTAs and aligned evidence.

    This stays broad on purpose: it can describe raw protein FASTA inputs,
    aligned protein evidence, or both, depending on which milestone output or
    manifest is being turned into planner-friendly form.
"""

    reference_genome: ReferenceGenome | None = None
    source_protein_fastas: tuple[Path, ...] = field(default_factory=tuple)
    evm_ready_gff3_path: Path | None = None
    raw_alignment_path: Path | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AnnotationEvidenceSet(PlannerSerializable):
    """Planner-facing annotation evidence boundary across transcript, protein, and ab initio inputs.

    This is the planning-level evidence bundle for consensus-annotation steps.
    It can point to transcript, protein, and prediction evidence together while
    keeping the reference genome and the source location for later reruns or
    review.
"""

    reference_genome: ReferenceGenome
    transcript_evidence: TranscriptEvidenceSet | None = None
    protein_evidence: ProteinEvidenceSet | None = None
    transcript_alignments_gff3_path: Path | None = None
    protein_alignments_gff3_path: Path | None = None
    ab_initio_predictions_gff3_path: Path | None = None
    combined_predictions_gff3_path: Path | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ConsensusAnnotation(PlannerSerializable):
    """Planner-facing consensus annotation boundary for downstream refinement or QC.

    Downstream stages such as PASA refinement, repeat filtering, and BUSCO can
    all use this higher-level annotation idea even if the underlying tool
    details or supporting evidence files change over time.
"""

    reference_genome: ReferenceGenome
    annotation_gff3_path: Path
    weights_path: Path | None = None
    supporting_evidence: AnnotationEvidenceSet | None = None
    protein_fasta_path: Path | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QualityAssessmentTarget(PlannerSerializable):
    """Planner-facing QC target for BUSCO, functional annotation, or later review.

    This type is intentionally flexible enough to describe the current BUSCO
    protein boundary as well as future quality-control or annotation-review
    stages that need one clear planning target.
"""

    reference_genome: ReferenceGenome | None = None
    consensus_annotation: ConsensusAnnotation | None = None
    annotation_gff3_path: Path | None = None
    proteins_fasta_path: Path | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AlignmentSet(PlannerSerializable):
    """Planner-facing aligned-read boundary for DNA variant calling workflows.

    Describes a coordinate-sorted, duplicate-marked BAM plus the metadata a
    variant-calling planner needs to reason about sample identity, reference
    build, and recalibration state without peeking at the BAM header.
"""

    bam_path: Path
    sample_id: str
    reference_fasta_path: Path | None = None
    sorted: str | None = None
    duplicates_marked: bool = False
    bqsr_applied: bool = False
    bam_index_path: Path | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReadPair(PlannerSerializable):
    """Paired-end FASTQ inputs for one sample."""

    sample_id: str
    r1_path: str
    r2_path: str | None = None


@dataclass(frozen=True, slots=True)
class UnmappedBAM(PlannerSerializable):
    """An unmapped BAM file with original read metadata preserved.

    Must be queryname-sorted (GATK MergeBamAlignment requirement).
    """

    bam_path: str
    sample_id: str


@dataclass(frozen=True, slots=True)
class VariantCallSet(PlannerSerializable):
    """Planner-facing variant-call boundary spanning per-sample GVCFs and joint VCFs.

    One dataclass covers both GVCF and VCF outputs; ``variant_type`` is the
    discriminator so composed workflows can enforce GVCF-in for joint-calling
    stages and VCF-out for downstream filtering stages.
"""

    vcf_path: Path
    variant_type: str
    caller: str
    sample_ids: tuple[str, ...] = field(default_factory=tuple)
    reference_fasta_path: Path | None = None
    vcf_index_path: Path | None = None
    build: str | None = None
    cohort_id: str | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class KnownSites(PlannerSerializable):
    """Planner-facing known-variant resource for BQSR and VQSR stages.

    VQSR-facing fields (``training``, ``truth``, ``prior``, ``vqsr_mode``) are
    carried here even though VQSR is out of scope for Milestone A so the type
    stays stable when Milestone B/C lights up VariantRecalibrator.
"""

    vcf_path: Path
    resource_name: str
    index_path: Path | None = None
    build: str | None = None
    known: bool = True
    training: bool = False
    truth: bool = False
    prior: float | None = None
    vqsr_mode: str | None = None
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


__all__ = [
    "AlignmentSet",
    "AnnotationEvidenceSet",
    "ConsensusAnnotation",
    "KnownSites",
    "PlannerSerializable",
    "ProteinEvidenceSet",
    "QualityAssessmentTarget",
    "ReadPair",
    "ReadSet",
    "UnmappedBAM",
    "ReferenceGenome",
    "TOP_LEVEL_PLANNER_TYPE_ADDITION_RULES",
    "TranscriptEvidenceSet",
    "VariantCallSet",
]
