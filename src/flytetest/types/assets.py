"""Local-first typed bioinformatics assets for FLyteTest.

This is a staged adoption layer inspired by richer asset systems, but it is
not a full Stargazer-style implementation. These dataclasses intentionally
model local filesystem paths plus lightweight biological metadata only.

Current scope:
- no remote fetch/query/update behavior
- no content addressing or CID management
- no MCP integration
- no task-runtime mutation of the asset graph

Planned Flyte mapping:
- single-file `Path` fields map naturally to `flyte.io.File`
- directory `Path` fields map naturally to `flyte.io.Dir`
- scalar metadata fields stay as normal typed task inputs
- composite dataclasses can first be used in planning/binding layers, then
  gradually replace ad hoc file bundles at workflow boundaries
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Mapping, TypeVar, Union, get_args, get_origin, get_type_hints


_ManifestSerializableT = TypeVar("_ManifestSerializableT", bound="ManifestSerializable")


def _serialize_manifest_value(value: Any) -> Any:
    """Convert asset values into JSON-compatible manifest payloads.

    Args:
        value: Asset value to serialize.

    Returns:
        JSON-compatible representation of the asset value.
    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_serialize_manifest_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_manifest_value(item) for key, item in value.items()}
    if is_dataclass(value):
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return {field_info.name: _serialize_manifest_value(getattr(value, field_info.name)) for field_info in fields(value)}
    return value


def _is_optional_manifest_type(annotation: Any) -> bool:
    """Return whether one type hint is an optional union.

    Args:
        annotation: Type hint being inspected during deserialization.

    Returns:
        ``True`` when the annotation is an optional union.
    """
    origin = get_origin(annotation)
    return origin in (Union, types.UnionType) and type(None) in get_args(annotation)


def _deserialize_manifest_value(annotation: Any, value: Any) -> Any:
    """Rehydrate one serialized asset value using a dataclass type hint.

    Args:
        annotation: Declared field type for the asset member being restored.
        value: Serialized asset value to convert back into a typed object.

    Returns:
        Typed asset value reconstructed from the manifest payload.
    """
    if value is None:
        return None
    if annotation is Any:
        return value
    if annotation is Path:
        return Path(str(value))
    if annotation is str:
        return str(value)
    if annotation is int:
        return int(value)
    if annotation is bool:
        return bool(value)

    origin = get_origin(annotation)
    if origin is tuple:
        item_type = get_args(annotation)[0]
        return tuple(_deserialize_manifest_value(item_type, item) for item in value)
    if origin is dict:
        key_type, value_type = get_args(annotation)
        return {
            _deserialize_manifest_value(key_type, key): _deserialize_manifest_value(value_type, item)
            for key, item in value.items()
        }
    if _is_optional_manifest_type(annotation):
        inner = [item for item in get_args(annotation) if item is not type(None)]
        if len(inner) == 1:
            return _deserialize_manifest_value(inner[0], value)
    if isinstance(annotation, type) and is_dataclass(annotation):
        if hasattr(annotation, "from_dict"):
            return annotation.from_dict(value)
        hints = get_type_hints(annotation)
        return annotation(
            **{
                field_info.name: _deserialize_manifest_value(hints[field_info.name], value[field_info.name])
                for field_info in fields(annotation)
                if isinstance(value, Mapping) and field_info.name in value
            }
        )
    return value


class ManifestSerializable:
    """Mixin for asset dataclasses that need stable manifest round-trips."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize one asset dataclass into JSON-compatible data.

        Returns:
            Field-ordered JSON-compatible payload for the dataclass.
        """
        return {field_info.name: _serialize_manifest_value(getattr(self, field_info.name)) for field_info in fields(self)}

    @classmethod
    def from_dict(cls: type[_ManifestSerializableT], payload: Mapping[str, Any]) -> _ManifestSerializableT:
        """Deserialize one asset dataclass from JSON-compatible data.

        Args:
            payload: Structured payload to restore into the dataclass.

        Returns:
            Dataclass instance reconstructed from the supplied payload.
        """
        hints = get_type_hints(cls)
        kwargs = {}
        for field_info in fields(cls):
            if field_info.name not in payload:
                continue
            kwargs[field_info.name] = _deserialize_manifest_value(hints[field_info.name], payload[field_info.name])
        return cls(**kwargs)


@dataclass(frozen=True, slots=True)
class AssetToolProvenance(ManifestSerializable):
    """Typed provenance for generic asset names that preserve tool lineage."""

    tool_name: str
    tool_stage: str
    tool_version: str | None = None
    legacy_asset_name: str | None = None
    source_manifest_key: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReferenceGenome:
    """Local reference genome asset.

    Future Flyte mapping:
    - `fasta_path` -> `flyte.io.File`
    - `softmasked_fasta_path` -> optional `flyte.io.File`
    - `annotation_gff3_path` -> optional `flyte.io.File`
"""

    fasta_path: Path
    organism_name: str | None = None
    assembly_name: str | None = None
    taxonomy_id: int | None = None
    softmasked_fasta_path: Path | None = None
    annotation_gff3_path: Path | None = None


@dataclass(frozen=True, slots=True)
class TranscriptomeReference:
    """Local transcriptome FASTA plus minimal provenance metadata.

    Future Flyte mapping:
    - `fasta_path` -> `flyte.io.File`
    - `derived_from_genome` remains a planning-time typed relation
"""

    fasta_path: Path
    organism_name: str | None = None
    source_description: str | None = None
    transcript_count: int | None = None
    derived_from_genome: ReferenceGenome | None = None


@dataclass(frozen=True, slots=True)
class ReadPair:
    """Paired-end read inputs with sample-level metadata.

    Future Flyte mapping:
    - `left_reads_path` -> `flyte.io.File`
    - `right_reads_path` -> `flyte.io.File`
    - sample and library fields remain scalar task inputs
"""

    sample_id: str
    left_reads_path: Path
    right_reads_path: Path
    platform: str = "ILLUMINA"
    strandedness: str | None = None
    condition: str | None = None
    replicate_label: str | None = None


@dataclass(frozen=True, slots=True)
class QcReport:
    """QC output bundle for a sample.

    Future Flyte mapping:
    - `report_dir` -> `flyte.io.Dir`
    - report members can remain derived metadata instead of separate task outputs
"""

    sample_id: str
    report_dir: Path
    tool_name: str = "fastqc"
    html_reports: tuple[Path, ...] = field(default_factory=tuple)
    archive_files: tuple[Path, ...] = field(default_factory=tuple)
    source_reads: ReadPair | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SalmonIndexAsset:
    """Local Salmon index artifact and its transcriptome provenance.

    Future Flyte mapping:
    - `index_dir` -> `flyte.io.Dir`
    - `transcriptome` stays as a typed upstream asset reference
"""

    index_dir: Path
    transcriptome: TranscriptomeReference
    salmon_version: str | None = None
    kmer_size: int | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SalmonQuantResult:
    """Local Salmon quantification result bundle for one sample.

    Future Flyte mapping:
    - `quant_dir` -> `flyte.io.Dir`
    - `quant_sf_path` -> `flyte.io.File`
    - related assets stay explicit instead of being inferred from filenames
"""

    sample_id: str
    quant_dir: Path
    quant_sf_path: Path
    source_reads: ReadPair
    index_asset: SalmonIndexAsset | None = None
    library_type: str = "A"
    used_validate_mappings: bool = True
    cmd_info_json_path: Path | None = None
    aux_info_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StarGenomeIndexAsset:
    """Local STAR genome index artifact.

    Future Flyte mapping:
    - `index_dir` -> `flyte.io.Dir`
    - `reference_genome` stays as a typed upstream asset reference
"""

    index_dir: Path
    reference_genome: ReferenceGenome
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StarAlignmentResult(ManifestSerializable):
    """Local STAR alignment result for one paired-end sample.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - `sorted_bam_path` -> `flyte.io.File`
"""

    sample_id: str
    output_dir: Path
    sorted_bam_path: Path
    log_final_out_path: Path | None = None
    splice_junction_tab_path: Path | None = None
    source_reads: ReadPair | None = None
    star_index: StarGenomeIndexAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)
    provenance: AssetToolProvenance | None = None


@dataclass(frozen=True, slots=True)
class RnaSeqAlignmentResult(StarAlignmentResult):
    """STAR-shaped RNA-seq alignment result alias used by downstream workflows."""


@dataclass(frozen=True, slots=True)
class MergedBamAsset:
    """Merged BAM artifact used by downstream transcript-evidence tasks.

    Future Flyte mapping:
    - `bam_path` -> `flyte.io.File`
    - optional `bai_path` -> `flyte.io.File`
"""

    bam_path: Path
    source_bams: tuple[Path, ...] = field(default_factory=tuple)
    bai_path: Path | None = None
    sort_order: str = "coordinate"
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TrinityGenomeGuidedAssemblyResult:
    """Genome-guided Trinity transcript assembly output.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - `assembly_fasta_path` -> `flyte.io.File`
"""

    output_dir: Path
    assembly_fasta_path: Path
    source_bam: MergedBamAsset | None = None
    genome_guided_max_intron: int | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StringTieAssemblyResult:
    """StringTie transcript assembly output from a merged RNA-seq BAM.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - `transcript_gtf_path` -> `flyte.io.File`
"""

    output_dir: Path
    transcript_gtf_path: Path
    gene_abundance_path: Path | None = None
    source_bam: MergedBamAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TrinityDeNovoTranscriptAsset:
    """De novo Trinity transcript FASTA.

    Future Flyte mapping:
    - `fasta_path` -> `flyte.io.File`
    - optional provenance stays as planning-time metadata
"""

    fasta_path: Path
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CombinedTrinityTranscriptAsset:
    """Combined Trinity transcript FASTA used as PASA transcript input.

    Future Flyte mapping:
    - `fasta_path` -> `flyte.io.File`
"""

    fasta_path: Path
    genome_guided_transcripts: TrinityGenomeGuidedAssemblyResult
    de_novo_transcripts: TrinityDeNovoTranscriptAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PasaCleanedTranscriptAsset(ManifestSerializable):
    """seqclean output used by PASA align/assemble.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - `clean_fasta_path` -> `flyte.io.File`
"""

    output_dir: Path
    clean_fasta_path: Path
    input_transcripts: CombinedTrinityTranscriptAsset
    univec_fasta_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)
    provenance: AssetToolProvenance | None = None


@dataclass(frozen=True, slots=True)
class CleanedTranscriptDataset(PasaCleanedTranscriptAsset):
    """PASA seqclean output alias used by transcript-evidence and PASA stages."""


@dataclass(frozen=True, slots=True)
class PasaSqliteConfigAsset:
    """SQLite-backed PASA configuration bundle for align/assemble runs.

    Future Flyte mapping:
    - `config_dir` -> `flyte.io.Dir`
    - `config_path` -> `flyte.io.File`
    - `database_path` -> `flyte.io.File`
"""

    config_dir: Path
    config_path: Path
    database_path: Path
    database_backend: str = "sqlite"
    template_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PasaAlignmentAssemblyResult:
    """Primary PASA transcript alignment and assembly outputs.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - key member paths remain explicit file outputs
"""

    output_dir: Path
    database_name: str
    assemblies_fasta_path: Path | None = None
    pasa_assemblies_gff3_path: Path | None = None
    pasa_assemblies_gtf_path: Path | None = None
    alt_splicing_support_path: Path | None = None
    polyasites_fasta_path: Path | None = None
    cleaned_transcripts: PasaCleanedTranscriptAsset | None = None
    stringtie_gtf_path: Path | None = None
    database_config: PasaSqliteConfigAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PasaGeneModelUpdateInputBundleAsset:
    """Staged PASA post-EVM refinement inputs rooted in PASA and EVM bundles.

    Future Flyte mapping:
    - `workspace_dir` -> `flyte.io.Dir`
    - key config, genome, transcript, and annotation members remain explicit files
"""

    workspace_dir: Path
    reference_genome_fasta_path: Path
    current_annotations_gff3_path: Path
    cleaned_transcripts_fasta_path: Path
    align_config_path: Path
    annot_compare_config_path: Path
    database_path: Path
    source_pasa_results_dir: Path | None = None
    source_evm_results_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PasaGeneModelUpdateRoundResult:
    """One PASA annotation-refinement round after loading current annotations.

    Future Flyte mapping:
    - `workspace_dir` -> `flyte.io.Dir`
    - updated GFF3 and BED members remain explicit file outputs
"""

    workspace_dir: Path
    round_index: int
    loaded_annotations_gff3_path: Path
    updated_gff3_path: Path
    updated_bed_path: Path | None = None
    current_annotations_gff3_path: Path | None = None
    input_bundle: PasaGeneModelUpdateInputBundleAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PasaGeneModelUpdateResultBundle:
    """Collected PASA post-EVM refinement outputs spanning staged inputs and rounds.

    Future Flyte mapping:
    - `result_dir` -> `flyte.io.Dir`
    - final updated GFF3 members remain explicit file outputs
"""

    result_dir: Path
    staged_inputs_dir: Path
    load_round_root: Path
    update_round_root: Path
    finalized_dir: Path
    final_updated_gff3_path: Path
    final_removed_gff3_path: Path
    final_sorted_gff3_path: Path
    manifest_path: Path | None = None
    staged_inputs: PasaGeneModelUpdateInputBundleAsset | None = None
    update_rounds: tuple[PasaGeneModelUpdateRoundResult, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TransDecoderPredictionResult:
    """TransDecoder coding-region prediction outputs derived from PASA assemblies.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - key member paths remain explicit file outputs
"""

    output_dir: Path
    input_transcripts_fasta_path: Path
    transdecoder_dir_path: Path | None = None
    predicted_orfs_gff3_path: Path | None = None
    predicted_genome_gff3_path: Path | None = None
    predicted_bed_path: Path | None = None
    cds_fasta_path: Path | None = None
    peptide_fasta_path: Path | None = None
    mrna_fasta_path: Path | None = None
    source_pasa: PasaAlignmentAssemblyResult | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CodingPredictionResult(TransDecoderPredictionResult):
    """Biology-facing alias for a PASA-derived coding-prediction bundle.

    This generic sibling keeps the planner surface stable if a future
    implementation replaces TransDecoder with a different ORF predictor.
    All existing `TransDecoderPredictionResult` construction sites remain
    valid — this class inherits every field unchanged.
"""


@dataclass(frozen=True, slots=True)
class ProteinReferenceDatasetAsset:
    """Local staged protein evidence inputs for Exonerate alignment.

    Future Flyte mapping:
    - `staged_dir` -> `flyte.io.Dir`
    - `combined_fasta_path` -> `flyte.io.File`
    - `source_fasta_paths` -> tuple of `flyte.io.File` at workflow boundaries
"""

    staged_dir: Path
    combined_fasta_path: Path
    source_fasta_paths: tuple[Path, ...] = field(default_factory=tuple)
    staged_input_paths: tuple[Path, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ChunkedProteinFastaAsset:
    """One deterministic chunk of a staged protein FASTA dataset.

    Future Flyte mapping:
    - `chunk_fasta_path` -> `flyte.io.File`
    - `chunk_dir` -> `flyte.io.Dir` when chunks are grouped as one artifact set
"""

    chunk_dir: Path
    chunk_fasta_path: Path
    chunk_index: int
    protein_count: int
    source_dataset: ProteinReferenceDatasetAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ExonerateChunkAlignmentResult:
    """Raw Exonerate alignment output for one protein chunk.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - `raw_output_path` -> `flyte.io.File`
"""

    chunk_label: str
    output_dir: Path
    protein_chunk_fasta_path: Path
    raw_output_path: Path
    model: str = "protein2genome"
    source_chunk: ChunkedProteinFastaAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvmProteinEvidenceGff3Asset:
    """Converted protein-evidence GFF3 intended for later EVM input.

    Future Flyte mapping:
    - `gff3_path` -> `flyte.io.File`
"""

    chunk_label: str
    gff3_path: Path
    source_alignment: ExonerateChunkAlignmentResult | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ProteinEvidenceResultBundle:
    """Collected protein-evidence outputs spanning staging through conversion.

    Future Flyte mapping:
    - `result_dir` -> `flyte.io.Dir`
    - final combined files remain explicit file members
"""

    result_dir: Path
    combined_protein_fasta_path: Path
    chunk_dir: Path
    raw_chunk_root: Path
    evm_chunk_root: Path
    concatenated_raw_output_path: Path
    concatenated_evm_gff3_path: Path
    reference_genome: ReferenceGenome | None = None
    staged_dataset: ProteinReferenceDatasetAsset | None = None
    chunk_assets: tuple[ChunkedProteinFastaAsset, ...] = field(default_factory=tuple)
    raw_chunk_results: tuple[ExonerateChunkAlignmentResult, ...] = field(default_factory=tuple)
    converted_chunk_results: tuple[EvmProteinEvidenceGff3Asset, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Braker3InputBundleAsset:
    """Local staged inputs for a BRAKER3 run.

    Future Flyte mapping:
    - `staged_dir` -> `flyte.io.Dir`
    - `genome_fasta_path` -> `flyte.io.File`
    - optional evidence members map to optional `flyte.io.File`
"""

    staged_dir: Path
    genome_fasta_path: Path
    rnaseq_bam_path: Path | None = None
    protein_fasta_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Braker3RawRunResultAsset:
    """Raw BRAKER3 run outputs with resolved `braker.gff3`.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - `braker_gff3_path` -> `flyte.io.File`
"""

    output_dir: Path
    braker_gff3_path: Path
    species_name: str
    input_bundle: Braker3InputBundleAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Braker3NormalizedGff3Asset:
    """Deterministically normalized BRAKER3 GFF3 for later EVM use.

    Future Flyte mapping:
    - `output_dir` -> `flyte.io.Dir`
    - `normalized_gff3_path` -> `flyte.io.File`
"""

    output_dir: Path
    normalized_gff3_path: Path
    source_run: Braker3RawRunResultAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Braker3ResultBundle(ManifestSerializable):
    """Collected BRAKER3 outputs spanning staging, raw run, and normalization.

    Future Flyte mapping:
    - `result_dir` -> `flyte.io.Dir`
    - stable GFF3 members remain explicit file paths
"""

    result_dir: Path
    staged_inputs_dir: Path
    raw_run_dir: Path
    normalized_dir: Path
    braker_gff3_path: Path
    normalized_gff3_path: Path
    reference_genome: ReferenceGenome | None = None
    input_bundle: Braker3InputBundleAsset | None = None
    raw_run: Braker3RawRunResultAsset | None = None
    normalized_prediction: Braker3NormalizedGff3Asset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)
    provenance: AssetToolProvenance | None = None


@dataclass(frozen=True, slots=True)
class AbInitioResultBundle(Braker3ResultBundle):
    """BRAKER3-derived ab initio annotation bundle alias for planner-facing use."""


@dataclass(frozen=True, slots=True)
class EvmTranscriptInputBundleAsset:
    """Deterministically staged PASA transcript evidence for pre-EVM assembly.

    Future Flyte mapping:
    - `staged_dir` -> `flyte.io.Dir`
    - `transcripts_gff3_path` -> `flyte.io.File`
"""

    staged_dir: Path
    transcripts_gff3_path: Path
    source_results_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvmProteinInputBundleAsset:
    """Deterministically staged protein evidence for pre-EVM assembly.

    Future Flyte mapping:
    - `staged_dir` -> `flyte.io.Dir`
    - `proteins_gff3_path` -> `flyte.io.File`
"""

    staged_dir: Path
    proteins_gff3_path: Path
    source_results_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvmPredictionInputBundleAsset:
    """Deterministically staged prediction evidence for the pre-EVM contract.

    Future Flyte mapping:
    - `staged_dir` -> `flyte.io.Dir`
    - `predictions_gff3_path` -> `flyte.io.File`
    - component GFF3 and reference members remain explicit file outputs
"""

    staged_dir: Path
    predictions_gff3_path: Path
    braker_gff3_path: Path
    transdecoder_genome_gff3_path: Path
    reference_genome_fasta_path: Path
    source_braker3_results_dir: Path | None = None
    source_transdecoder_results_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvmInputPreparationBundle:
    """Collected pre-EVM contract outputs spanning all upstream evidence channels.

    Future Flyte mapping:
    - `result_dir` -> `flyte.io.Dir`
    - final contract files remain explicit file outputs for downstream EVM execution
"""

    result_dir: Path
    reference_genome_fasta_path: Path
    transcripts_gff3_path: Path
    predictions_gff3_path: Path
    proteins_gff3_path: Path
    transcript_bundle: EvmTranscriptInputBundleAsset | None = None
    protein_bundle: EvmProteinInputBundleAsset | None = None
    prediction_bundle: EvmPredictionInputBundleAsset | None = None
    manifest_path: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvmExecutionInputBundleAsset:
    """Prepared EVM execution workspace staged from the pre-EVM contract bundle.

    Future Flyte mapping:
    - `workspace_dir` -> `flyte.io.Dir`
    - stable evidence and weights members remain explicit file outputs
"""

    workspace_dir: Path
    reference_genome_fasta_path: Path
    transcripts_gff3_path: Path
    predictions_gff3_path: Path
    proteins_gff3_path: Path
    weights_path: Path
    source_pre_evm_results_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvmPartitionBundleAsset:
    """Partitioned EVM workspace with a deterministic partition listing.

    Future Flyte mapping:
    - `workspace_dir` -> `flyte.io.Dir`
    - `partitions_dir` -> `flyte.io.Dir`
    - `partition_listing_path` -> `flyte.io.File`
"""

    workspace_dir: Path
    partitions_dir: Path
    partition_listing_path: Path
    segment_size: int
    overlap_size: int
    execution_input_bundle: EvmExecutionInputBundleAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvmCommandSetAsset:
    """Deterministic EVM command list generated from one partitioned workspace.

    Future Flyte mapping:
    - `workspace_dir` -> `flyte.io.Dir`
    - `commands_path` -> `flyte.io.File`
"""

    workspace_dir: Path
    commands_path: Path
    output_file_name: str
    command_count: int
    partition_bundle: EvmPartitionBundleAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvmConsensusResultBundle:
    """Collected EVM execution outputs with stage-level provenance.

    Future Flyte mapping:
    - `result_dir` -> `flyte.io.Dir`
    - stable final GFF3 and manifest members remain explicit file outputs
"""

    result_dir: Path
    pre_evm_bundle_dir: Path
    execution_input_dir: Path
    partition_dir: Path
    command_dir: Path
    execution_dir: Path
    recombined_dir: Path
    weights_path: Path
    partition_listing_path: Path
    commands_path: Path
    concatenated_gff3_path: Path
    blank_lines_removed_gff3_path: Path
    sorted_gff3_path: Path
    manifest_path: Path | None = None
    execution_input_bundle: EvmExecutionInputBundleAsset | None = None
    partition_bundle: EvmPartitionBundleAsset | None = None
    command_set: EvmCommandSetAsset | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


# Deprecated aliases kept local for older draft imports.
EvmTranscriptInputBundle = EvmTranscriptInputBundleAsset
EvmProteinInputBundle = EvmProteinInputBundleAsset
EvmAbInitioInputBundleAsset = EvmPredictionInputBundleAsset
EvmBraker3InputBundle = EvmPredictionInputBundleAsset
EvmPrepBundle = EvmInputPreparationBundle
