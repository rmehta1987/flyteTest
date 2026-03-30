"""Local-first typed bioinformatics assets for FLyteTest.

This is a staged adoption layer inspired by richer asset systems, but it is not
a full Stargazer-style implementation. These dataclasses intentionally model
local filesystem paths plus lightweight biological metadata only.

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

from dataclasses import dataclass, field
from pathlib import Path


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
class StarAlignmentResult:
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
    """External or future de novo Trinity transcript FASTA.

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
class PasaCleanedTranscriptAsset:
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
