from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


Category = Literal["task", "workflow"]


@dataclass(frozen=True)
class InterfaceField:
    name: str
    type: str
    description: str


@dataclass(frozen=True)
class RegistryEntry:
    name: str
    category: Category
    description: str
    inputs: tuple[InterfaceField, ...]
    outputs: tuple[InterfaceField, ...]
    tags: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["inputs"] = [asdict(field) for field in self.inputs]
        data["outputs"] = [asdict(field) for field in self.outputs]
        return data


REGISTRY_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name="star_genome_index",
        category="task",
        description="Build a STAR genome index from a reference genome FASTA.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField("star_sif", "str", "Optional Apptainer/Singularity image path for STAR."),
            InterfaceField("star_threads", "int", "Thread count passed to STAR."),
        ),
        outputs=(
            InterfaceField("index_dir", "Dir", "Directory containing STAR genome index files."),
        ),
        tags=("transcript-evidence", "star", "index", "genome"),
    ),
    RegistryEntry(
        name="star_align_sample",
        category="task",
        description="Align one paired-end RNA-seq sample with STAR and emit a sorted coordinate BAM.",
        inputs=(
            InterfaceField("index", "Dir", "Existing STAR genome index directory."),
            InterfaceField("left", "File", "Read 1 FASTQ input."),
            InterfaceField("right", "File", "Read 2 FASTQ input."),
            InterfaceField("sample_id", "str", "Sample identifier used for provenance and output naming."),
            InterfaceField("star_sif", "str", "Optional Apptainer/Singularity image path for STAR."),
            InterfaceField("star_threads", "int", "Thread count passed to STAR."),
        ),
        outputs=(
            InterfaceField("alignment_dir", "Dir", "Directory containing STAR alignment outputs and logs."),
        ),
        tags=("transcript-evidence", "star", "alignment", "paired-end"),
    ),
    RegistryEntry(
        name="samtools_merge_bams",
        category="task",
        description="Merge one or more STAR-produced BAMs into a single coordinate-sorted BAM stage output.",
        inputs=(
            InterfaceField("alignment_dirs", "list[Dir]", "STAR alignment directories containing sorted BAM outputs."),
            InterfaceField(
                "samtools_sif",
                "str",
                "Optional Apptainer/Singularity image path for samtools.",
            ),
        ),
        outputs=(
            InterfaceField("merged_bam", "File", "Merged BAM file for downstream transcript-evidence tasks."),
        ),
        tags=("transcript-evidence", "samtools", "bam", "merge"),
    ),
    RegistryEntry(
        name="trinity_genome_guided_assemble",
        category="task",
        description="Run genome-guided Trinity from a merged RNA-seq BAM.",
        inputs=(
            InterfaceField("merged_bam", "File", "Merged BAM input for genome-guided Trinity."),
            InterfaceField(
                "trinity_sif",
                "str",
                "Optional Apptainer/Singularity image path for Trinity.",
            ),
            InterfaceField("trinity_cpu", "int", "CPU count passed to Trinity."),
            InterfaceField("trinity_max_memory_gb", "int", "Maximum memory in GB passed to Trinity."),
            InterfaceField(
                "genome_guided_max_intron",
                "int",
                "Genome-guided max intron setting passed to Trinity.",
            ),
        ),
        outputs=(
            InterfaceField("trinity_dir", "Dir", "Directory containing genome-guided Trinity outputs."),
        ),
        tags=("transcript-evidence", "trinity", "genome-guided", "assembly"),
    ),
    RegistryEntry(
        name="stringtie_assemble",
        category="task",
        description="Run StringTie transcript assembly from a merged RNA-seq BAM.",
        inputs=(
            InterfaceField("merged_bam", "File", "Merged BAM input for StringTie."),
            InterfaceField(
                "stringtie_sif",
                "str",
                "Optional Apptainer/Singularity image path for StringTie.",
            ),
            InterfaceField("stringtie_threads", "int", "Thread count passed to StringTie."),
        ),
        outputs=(
            InterfaceField("stringtie_dir", "Dir", "Directory containing StringTie outputs."),
        ),
        tags=("transcript-evidence", "stringtie", "assembly", "gtf"),
    ),
    RegistryEntry(
        name="collect_transcript_evidence_results",
        category="task",
        description="Collect transcript-evidence outputs into a structured results directory with a manifest.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField("left", "File", "Read 1 FASTQ input."),
            InterfaceField("right", "File", "Read 2 FASTQ input."),
            InterfaceField("star_index", "Dir", "STAR index directory."),
            InterfaceField("alignment", "Dir", "STAR alignment directory."),
            InterfaceField("merged_bam", "File", "Merged BAM file."),
            InterfaceField("trinity_gg", "Dir", "Genome-guided Trinity output directory."),
            InterfaceField("stringtie", "Dir", "StringTie output directory."),
            InterfaceField("sample_id", "str", "Sample identifier used in the manifest."),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped transcript-evidence results directory with copied outputs and run_manifest.json.",
            ),
        ),
        tags=("transcript-evidence", "results", "manifest"),
    ),
    RegistryEntry(
        name="pasa_accession_extract",
        category="task",
        description="Extract de novo Trinity transcript accessions for PASA TDN input.",
        inputs=(
            InterfaceField("denovo_trinity_fasta", "File", "De novo Trinity transcript FASTA."),
            InterfaceField("pasa_sif", "str", "Optional Apptainer/Singularity image path for PASA tools."),
        ),
        outputs=(
            InterfaceField("tdn_accs", "File", "PASA de novo transcript accession list."),
        ),
        tags=("pasa", "transcript-prep", "accessions", "trinity"),
    ),
    RegistryEntry(
        name="combine_trinity_fastas",
        category="task",
        description="Concatenate de novo and genome-guided Trinity transcript FASTAs for PASA transcript input.",
        inputs=(
            InterfaceField("genome_guided_trinity_fasta", "File", "Genome-guided Trinity transcript FASTA."),
            InterfaceField(
                "denovo_trinity_fasta_path",
                "str",
                "Optional path to a de novo Trinity transcript FASTA. When empty, only the genome-guided Trinity FASTA is used.",
            ),
        ),
        outputs=(
            InterfaceField("combined_fasta", "File", "Combined Trinity transcript FASTA for PASA."),
        ),
        tags=("pasa", "transcript-prep", "trinity", "concatenate"),
    ),
    RegistryEntry(
        name="pasa_seqclean",
        category="task",
        description="Run PASA seqclean against the combined Trinity transcript FASTA using a UniVec reference.",
        inputs=(
            InterfaceField("transcripts", "File", "Combined Trinity transcript FASTA."),
            InterfaceField("univec_fasta", "File", "UniVec FASTA used by seqclean."),
            InterfaceField("pasa_sif", "str", "Optional Apptainer/Singularity image path for PASA tools."),
            InterfaceField("seqclean_threads", "int", "Thread count passed to seqclean with -c."),
        ),
        outputs=(
            InterfaceField("seqclean_dir", "Dir", "Directory containing seqclean outputs, including the .clean FASTA."),
        ),
        tags=("pasa", "transcript-prep", "seqclean", "univec"),
    ),
    RegistryEntry(
        name="pasa_create_sqlite_db",
        category="task",
        description="Prepare a SQLite-backed PASA align/assemble config from a user-supplied PASA template.",
        inputs=(
            InterfaceField(
                "pasa_config_template",
                "File",
                "PASA alignAssembly template config file supplied from a PASA installation.",
            ),
            InterfaceField("pasa_db_name", "str", "SQLite database filename to create for PASA."),
        ),
        outputs=(
            InterfaceField("config_dir", "Dir", "Directory containing the rewritten PASA config and SQLite database."),
        ),
        tags=("pasa", "sqlite", "config", "database"),
    ),
    RegistryEntry(
        name="pasa_align_assemble",
        category="task",
        description="Run PASA Launch_PASA_pipeline.pl for transcript alignment and assembly using Trinity and StringTie evidence.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField("cleaned_transcripts", "Dir", "seqclean output directory containing the cleaned Trinity transcript FASTA."),
            InterfaceField("unclean_transcripts", "File", "Combined Trinity transcript FASTA passed to PASA with -u."),
            InterfaceField("stringtie_gtf", "File", "StringTie transcript GTF passed to PASA with --trans_gtf."),
            InterfaceField("pasa_config", "Dir", "Directory containing the PASA config and SQLite database."),
            InterfaceField("pasa_sif", "str", "Optional Apptainer/Singularity image path for PASA tools."),
            InterfaceField("pasa_aligners", "str", "Comma-separated PASA aligner list, following the attached notes."),
            InterfaceField("pasa_cpu", "int", "CPU count passed to Launch_PASA_pipeline.pl."),
            InterfaceField("pasa_max_intron_length", "int", "Maximum intron length passed to PASA."),
            InterfaceField(
                "tdn_accs_path",
                "str",
                "Optional path to a PASA TDN accession file. When empty, --TDN is omitted.",
            ),
        ),
        outputs=(
            InterfaceField("pasa_dir", "Dir", "Directory containing PASA align/assemble outputs."),
        ),
        tags=("pasa", "align-assemble", "sqlite", "stringtie", "trinity"),
    ),
    RegistryEntry(
        name="collect_pasa_results",
        category="task",
        description="Collect PASA preparation and align/assemble outputs into a structured results directory with a manifest.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField("transcript_evidence_results", "Dir", "Transcript evidence results directory used as PASA source input."),
            InterfaceField("univec_fasta", "File", "UniVec FASTA used by seqclean."),
            InterfaceField("combined_trinity", "File", "Combined Trinity transcript FASTA."),
            InterfaceField("seqclean", "Dir", "seqclean output directory."),
            InterfaceField("pasa_config", "Dir", "PASA config directory containing the SQLite database."),
            InterfaceField("pasa_run", "Dir", "PASA output directory."),
            InterfaceField("stringtie_gtf", "File", "StringTie transcript GTF used for PASA."),
            InterfaceField("sample_id", "str", "Sample identifier propagated from transcript evidence results."),
            InterfaceField(
                "trinity_denovo_fasta_path",
                "str",
                "Optional path to a de novo Trinity FASTA used for the PASA input combination stage.",
            ),
            InterfaceField(
                "tdn_accs_path",
                "str",
                "Optional path to a PASA TDN accession list used during align/assemble.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped PASA results directory with combined transcripts, seqclean, config, PASA outputs, and run_manifest.json.",
            ),
        ),
        tags=("pasa", "results", "manifest"),
    ),
    RegistryEntry(
        name="transdecoder_train_from_pasa",
        category="task",
        description="Run TransDecoder coding-region prediction from PASA assemblies and lift ORFs onto genome coordinates for downstream annotation.",
        inputs=(
            InterfaceField("pasa_assemblies_fasta", "File", "PASA assemblies FASTA generated from the PASA align/assemble stage."),
            InterfaceField("pasa_assemblies_gff3", "File", "PASA assemblies GFF3 used to project TransDecoder ORFs onto genome coordinates."),
            InterfaceField(
                "transdecoder_sif",
                "str",
                "Optional Apptainer/Singularity image path for TransDecoder.",
            ),
            InterfaceField(
                "transdecoder_min_protein_length",
                "int",
                "Minimum predicted protein length passed to TransDecoder.LongOrfs with -m.",
            ),
            InterfaceField(
                "transdecoder_genome_orf_script",
                "str",
                "TransDecoder utility script used to convert transcript-level ORFs to genome-coordinates; defaults to cdna_alignment_orf_to_genome_orf.pl.",
            ),
        ),
        outputs=(
            InterfaceField(
                "transdecoder_dir",
                "Dir",
                "Directory containing TransDecoder intermediates plus transcript-level and genome-level coding predictions.",
            ),
        ),
        tags=("transdecoder", "coding-prediction", "pasa", "orfs"),
    ),
    RegistryEntry(
        name="collect_transdecoder_results",
        category="task",
        description="Collect TransDecoder outputs into a structured results directory with a manifest and typed asset summary.",
        inputs=(
            InterfaceField(
                "pasa_results",
                "Dir",
                "PASA results directory used as the source input boundary for TransDecoder.",
            ),
            InterfaceField("transdecoder_run", "Dir", "TransDecoder output directory to collect."),
            InterfaceField("sample_id", "str", "Sample identifier propagated from the PASA results manifest."),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped TransDecoder results directory with copied outputs and run_manifest.json.",
            ),
        ),
        tags=("transdecoder", "results", "manifest"),
    ),
    RegistryEntry(
        name="salmon_index",
        category="task",
        description="Build a Salmon transcriptome index from a reference FASTA.",
        inputs=(
            InterfaceField("ref", "File", "Transcriptome FASTA used for indexing."),
            InterfaceField(
                "salmon_sif",
                "str",
                "Optional Apptainer/Singularity image path for Salmon.",
            ),
        ),
        outputs=(
            InterfaceField("index", "Dir", "Directory containing the Salmon index."),
        ),
        tags=("rnaseq", "quant", "salmon", "index"),
    ),
    RegistryEntry(
        name="fastqc",
        category="task",
        description="Run FastQC on paired-end RNA-seq reads.",
        inputs=(
            InterfaceField("left", "File", "Read 1 FASTQ input."),
            InterfaceField("right", "File", "Read 2 FASTQ input."),
            InterfaceField(
                "fastqc_sif",
                "str",
                "Optional Apptainer/Singularity image path for FastQC.",
            ),
        ),
        outputs=(
            InterfaceField("qc_dir", "Dir", "Directory containing FastQC reports."),
        ),
        tags=("rnaseq", "qc", "fastqc", "paired-end"),
    ),
    RegistryEntry(
        name="salmon_quant",
        category="task",
        description="Quantify transcript abundance from paired-end reads with Salmon.",
        inputs=(
            InterfaceField("index", "Dir", "Existing Salmon index directory."),
            InterfaceField("left", "File", "Read 1 FASTQ input."),
            InterfaceField("right", "File", "Read 2 FASTQ input."),
            InterfaceField(
                "salmon_sif",
                "str",
                "Optional Apptainer/Singularity image path for Salmon.",
            ),
        ),
        outputs=(
            InterfaceField(
                "quant_dir",
                "Dir",
                "Directory containing Salmon quantification outputs.",
            ),
        ),
        tags=("rnaseq", "quant", "salmon", "paired-end"),
    ),
    RegistryEntry(
        name="collect_results",
        category="task",
        description="Copy QC and quant outputs into a stable results bundle with a run manifest.",
        inputs=(
            InterfaceField("qc", "Dir", "FastQC output directory."),
            InterfaceField("quant", "Dir", "Salmon quantification directory."),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped results directory with qc/, quant/, and run_manifest.json.",
            ),
        ),
        tags=("rnaseq", "results", "manifest"),
    ),
    RegistryEntry(
        name="transcript_evidence_generation",
        category="workflow",
        description="Transcript evidence workflow composed from STAR indexing/alignment, BAM merge, genome-guided Trinity, and StringTie.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField("left", "File", "Read 1 FASTQ input."),
            InterfaceField("right", "File", "Read 2 FASTQ input."),
            InterfaceField("sample_id", "str", "Sample identifier used in manifests and task provenance."),
            InterfaceField("star_sif", "str", "Optional Apptainer/Singularity image path for STAR."),
            InterfaceField("samtools_sif", "str", "Optional Apptainer/Singularity image path for samtools."),
            InterfaceField("trinity_sif", "str", "Optional Apptainer/Singularity image path for Trinity."),
            InterfaceField("stringtie_sif", "str", "Optional Apptainer/Singularity image path for StringTie."),
            InterfaceField("star_threads", "int", "Thread count for STAR tasks."),
            InterfaceField("trinity_cpu", "int", "CPU count for Trinity."),
            InterfaceField("trinity_max_memory_gb", "int", "Memory budget for Trinity in GB."),
            InterfaceField(
                "genome_guided_max_intron",
                "int",
                "Genome-guided max intron setting for Trinity.",
            ),
            InterfaceField("stringtie_threads", "int", "Thread count for StringTie."),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped transcript-evidence directory with STAR, merged BAM, Trinity, StringTie, and a manifest.",
            ),
        ),
        tags=("workflow", "transcript-evidence", "star", "trinity", "stringtie"),
    ),
    RegistryEntry(
        name="pasa_transcript_alignment",
        category="workflow",
        description="PASA transcript preparation and align/assemble workflow consuming transcript evidence outputs plus optional de novo Trinity transcripts.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField(
                "transcript_evidence_results",
                "Dir",
                "Transcript evidence results directory containing trinity_gg/ and stringtie/ outputs.",
            ),
            InterfaceField("univec_fasta", "File", "UniVec FASTA used by seqclean."),
            InterfaceField(
                "pasa_config_template",
                "File",
                "PASA alignAssembly template config file supplied from a PASA installation.",
            ),
            InterfaceField(
                "trinity_denovo_fasta_path",
                "str",
                "Optional path to a de novo Trinity FASTA. When empty, PASA runs without a de novo Trinity TDN input.",
            ),
            InterfaceField("pasa_sif", "str", "Optional Apptainer/Singularity image path for PASA tools."),
            InterfaceField("seqclean_threads", "int", "Thread count for seqclean."),
            InterfaceField("pasa_cpu", "int", "CPU count for PASA Launch_PASA_pipeline.pl."),
            InterfaceField("pasa_max_intron_length", "int", "Maximum intron length passed to PASA."),
            InterfaceField("pasa_aligners", "str", "Comma-separated PASA aligner list."),
            InterfaceField("pasa_db_name", "str", "SQLite database filename created for PASA."),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped PASA results directory with combined transcripts, seqclean outputs, SQLite config, PASA outputs, and a manifest.",
            ),
        ),
        tags=("workflow", "pasa", "transcript-alignment", "sqlite"),
    ),
    RegistryEntry(
        name="transdecoder_from_pasa",
        category="workflow",
        description="TransDecoder coding-prediction workflow consuming the PASA results bundle and producing transcript-level and genome-level ORF evidence.",
        inputs=(
            InterfaceField(
                "pasa_results",
                "Dir",
                "PASA results directory containing pasa/ and config/ outputs from pasa_transcript_alignment.",
            ),
            InterfaceField(
                "transdecoder_sif",
                "str",
                "Optional Apptainer/Singularity image path for TransDecoder.",
            ),
            InterfaceField(
                "transdecoder_min_protein_length",
                "int",
                "Minimum predicted protein length passed to TransDecoder.LongOrfs with -m.",
            ),
            InterfaceField(
                "transdecoder_genome_orf_script",
                "str",
                "TransDecoder utility script used to convert transcript-level ORFs to genome-coordinates.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped TransDecoder results directory with copied outputs and a manifest.",
            ),
        ),
        tags=("workflow", "transdecoder", "coding-prediction", "pasa"),
    ),
    RegistryEntry(
        name="rnaseq_qc_quant",
        category="workflow",
        description="Current RNA-seq QC and quantification workflow composed from FastQC and Salmon tasks.",
        inputs=(
            InterfaceField("ref", "File", "Transcriptome FASTA used to build the Salmon index."),
            InterfaceField("left", "File", "Read 1 FASTQ input."),
            InterfaceField("right", "File", "Read 2 FASTQ input."),
            InterfaceField(
                "salmon_sif",
                "str",
                "Optional Apptainer/Singularity image path for Salmon.",
            ),
            InterfaceField(
                "fastqc_sif",
                "str",
                "Optional Apptainer/Singularity image path for FastQC.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped results directory containing qc/, quant/, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "rnaseq", "qc", "quant"),
    ),
)

_REGISTRY = {entry.name: entry for entry in REGISTRY_ENTRIES}


def list_entries(category: Category | None = None) -> tuple[RegistryEntry, ...]:
    if category is None:
        return REGISTRY_ENTRIES
    return tuple(entry for entry in REGISTRY_ENTRIES if entry.category == category)


def get_entry(name: str) -> RegistryEntry:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        supported = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"Unknown registry entry '{name}'. Supported entries: {supported}") from exc
