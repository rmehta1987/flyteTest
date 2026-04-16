"""Planner-facing catalog of available workflows and tasks.

This module lists the registered stages the planner can choose from. Each entry
describes the public inputs, outputs, and biological role of a task or
workflow, so user requests stay tied to known Flyte code instead of ad hoc
runtime generation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Literal


Category = Literal["task", "workflow"]


@dataclass(frozen=True)
class InterfaceField:
    """One named input or output listed in the catalog.

    These fields keep the public shape readable without importing Flyte objects
    or task functions.
    """

    name: str
    type: str
    description: str


@dataclass(frozen=True)
class RegistryCompatibilityMetadata:
    """Planner notes about where a stage fits in the biology pipeline.

    The base catalog says that a task or workflow exists. This metadata says
    which biology types the entry can accept, which types it can produce, and
    when the planner may safely reuse it in a generated plan.
    """

    biological_stage: str = "unspecified"
    accepted_planner_types: tuple[str, ...] = ()
    produced_planner_types: tuple[str, ...] = ()
    reusable_as_reference: bool = False
    execution_defaults: dict[str, object] = field(default_factory=dict)
    supported_execution_profiles: tuple[str, ...] = ("local",)
    runtime_image_policy: str = "Optional local tool image paths remain user-supplied when supported."
    synthesis_eligible: bool = False
    composition_constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegistryEntry:
    """One registered task or workflow that the planner may choose.

    Catalog entries keep the user-facing description separate from the runnable
    Flyte definitions. That separation lets the planner inspect available
    stages without importing every task module or editing workflow code.
    """

    name: str
    category: Category
    description: str
    inputs: tuple[InterfaceField, ...]
    outputs: tuple[InterfaceField, ...]
    tags: tuple[str, ...]
    compatibility: RegistryCompatibilityMetadata = field(default_factory=RegistryCompatibilityMetadata)

    def to_dict(self) -> dict[str, object]:
        """Serialize this catalog entry for callers that need plain dictionaries.

        The method keeps `inputs` and `outputs` as lists of simple dictionaries
        while still including the compatibility metadata.

        Returns:
            A `dict[str, object]` representation of the catalog entry.
        """
        data = asdict(self)
        data["inputs"] = [asdict(field) for field in self.inputs]
        data["outputs"] = [asdict(field) for field in self.outputs]
        return data


REGISTRY_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name="trinity_denovo_assemble",
        category="task",
        description="Run de novo Trinity on one paired-end RNA-seq sample for the transcript-evidence branch upstream of PASA.",
        inputs=(
            InterfaceField("left", "File", "Read 1 FASTQ input."),
            InterfaceField("right", "File", "Read 2 FASTQ input."),
            InterfaceField("sample_id", "str", "Sample identifier used for provenance and temporary output naming."),
            InterfaceField(
                "trinity_sif",
                "str",
                "Optional Apptainer/Singularity image path for Trinity.",
            ),
            InterfaceField("trinity_cpu", "int", "CPU count passed to Trinity."),
            InterfaceField("trinity_max_memory_gb", "int", "Maximum memory in GB passed to Trinity."),
        ),
        outputs=(
            InterfaceField("trinity_dir", "Dir", "Directory containing de novo Trinity outputs."),
        ),
        tags=("transcript-evidence", "trinity", "de-novo", "assembly"),
    ),
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
        description="Run StringTie transcript assembly from a merged RNA-seq BAM with the fixed flags `-l STRG -f 0.10 -c 3 -j 3`.",
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
        description="Collect the current single-sample transcript-evidence branch into a structured results directory with both Trinity outputs, STAR/StringTie products, and a manifest that marks the bundle as PASA-ready with documented simplifications.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField("left", "File", "Read 1 FASTQ input."),
            InterfaceField("right", "File", "Read 2 FASTQ input."),
            InterfaceField("trinity_denovo", "Dir", "De novo Trinity output directory."),
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
        description="Extract PASA TDN accessions from the de novo Trinity FASTA for PASA align/assemble input.",
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
        description="Concatenate de novo and genome-guided Trinity transcript FASTAs into the PASA input order.",
        inputs=(
            InterfaceField("genome_guided_trinity_fasta", "File", "Genome-guided Trinity transcript FASTA."),
            InterfaceField("denovo_trinity_fasta", "File", "De novo Trinity transcript FASTA."),
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
        description="Run the PASA align/assemble command boundary with de novo Trinity, Trinity-GG, and StringTie evidence.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField("cleaned_transcripts", "Dir", "seqclean output directory containing the cleaned Trinity transcript FASTA."),
            InterfaceField("unclean_transcripts", "File", "Combined Trinity transcript FASTA passed to PASA with -u."),
            InterfaceField("stringtie_gtf", "File", "StringTie transcript GTF passed to PASA with --trans_gtf."),
            InterfaceField("pasa_config", "Dir", "Directory containing the PASA config and SQLite database."),
            InterfaceField("tdn_accs", "File", "PASA de novo Trinity accession list."),
            InterfaceField("pasa_sif", "str", "Optional Apptainer/Singularity image path for PASA tools."),
            InterfaceField("pasa_aligners", "str", "Comma-separated PASA aligner list, following the PASA tool reference."),
            InterfaceField("pasa_cpu", "int", "CPU count passed to Launch_PASA_pipeline.pl."),
            InterfaceField("pasa_max_intron_length", "int", "Maximum intron length passed to PASA."),
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
            InterfaceField("trinity_denovo_fasta", "File", "De novo Trinity FASTA used for PASA transcript preparation."),
            InterfaceField("tdn_accs", "File", "PASA TDN accession list used during align/assemble."),
            InterfaceField("sample_id", "str", "Sample identifier propagated from transcript evidence results."),
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
        name="prepare_pasa_update_inputs",
        category="task",
        description="Stage the existing PASA and EVM result bundles into a deterministic PASA post-EVM refinement workspace with rewritten annotCompare config and canonical current annotations.",
        inputs=(
            InterfaceField(
                "pasa_results",
                "Dir",
                "PASA results directory from pasa_transcript_alignment containing seqclean outputs, config/, and PASA database state.",
            ),
            InterfaceField(
                "evm_results",
                "Dir",
                "EVM results directory from consensus_annotation_evm containing EVM.all.sort.gff3 and the staged reference genome.",
            ),
            InterfaceField(
                "pasa_annot_compare_template",
                "File",
                "PASA annotCompare template config supplied from a PASA installation.",
            ),
            InterfaceField(
                "fasta36_binary_path",
                "str",
                "Optional local fasta36 binary path used to create the note-described bin/fasta symlink.",
            ),
        ),
        outputs=(
            InterfaceField(
                "pasa_update_inputs_dir",
                "Dir",
                "Directory containing copied PASA configs and database, cleaned transcripts, genome.fa, current_annotations.gff3, optional bin/fasta, and run_manifest.json.",
            ),
        ),
        tags=("pasa", "post-evm", "staging", "config"),
    ),
    RegistryEntry(
        name="pasa_load_current_annotations",
        category="task",
        description="Load the current annotation GFF3 into the original PASA database state before one PASA post-EVM update round.",
        inputs=(
            InterfaceField(
                "pasa_update_inputs",
                "Dir",
                "Directory produced by prepare_pasa_update_inputs or by a previous PASA update round.",
            ),
            InterfaceField(
                "round_index",
                "int",
                "1-based PASA update round index used for deterministic manifesting and directory naming.",
            ),
            InterfaceField(
                "load_current_annotations_script",
                "str",
                "Load_Current_Gene_Annotations.dbi path or executable name.",
            ),
            InterfaceField(
                "pasa_sif",
                "str",
                "Optional Apptainer/Singularity image path for PASA tools.",
            ),
        ),
        outputs=(
            InterfaceField(
                "loaded_pasa_update_dir",
                "Dir",
                "Directory containing the copied PASA update workspace after loading current annotations plus run_manifest.json.",
            ),
        ),
        tags=("pasa", "post-evm", "load-annotations", "database"),
    ),
    RegistryEntry(
        name="pasa_update_gene_models",
        category="task",
        description="Run one PASA annotation-refinement round, resolve the new post-update GFF3, and promote it as the canonical current annotations file for the next round.",
        inputs=(
            InterfaceField(
                "loaded_pasa_update",
                "Dir",
                "Directory produced by pasa_load_current_annotations.",
            ),
            InterfaceField(
                "round_index",
                "int",
                "1-based PASA update round index used for deterministic manifesting and directory naming.",
            ),
            InterfaceField(
                "pasa_update_script",
                "str",
                "Launch_PASA_pipeline.pl path or executable name for annotCompare mode.",
            ),
            InterfaceField(
                "pasa_sif",
                "str",
                "Optional Apptainer/Singularity image path for PASA tools.",
            ),
            InterfaceField(
                "pasa_update_cpu",
                "int",
                "CPU count passed to Launch_PASA_pipeline.pl during PASA post-EVM update rounds.",
            ),
        ),
        outputs=(
            InterfaceField(
                "pasa_update_round_dir",
                "Dir",
                "Directory containing one PASA update-round workspace, the resolved new gene-model GFF3, optional BED output, promoted current_annotations.gff3, and run_manifest.json.",
            ),
        ),
        tags=("pasa", "post-evm", "annotation-update", "round"),
    ),
    RegistryEntry(
        name="finalize_pasa_update_outputs",
        category="task",
        description="Create stable final PASA post-update GFF3 filenames, remove blank lines, and optionally sort the last-round output with gff3sort.",
        inputs=(
            InterfaceField(
                "pasa_update_round",
                "Dir",
                "Directory produced by pasa_update_gene_models for the final refinement round.",
            ),
            InterfaceField(
                "gff3sort_script",
                "str",
                "Optional gff3sort.pl path or executable name. When empty, sorting is skipped explicitly.",
            ),
            InterfaceField(
                "pasa_sif",
                "str",
                "Optional Apptainer/Singularity image path for PASA tools.",
            ),
        ),
        outputs=(
            InterfaceField(
                "finalized_pasa_update_dir",
                "Dir",
                "Directory containing post_pasa_updates.gff3, post_pasa_updates.removed.gff3, post_pasa_updates.sort.gff3, and run_manifest.json.",
            ),
        ),
        tags=("pasa", "post-evm", "finalize", "gff3"),
    ),
    RegistryEntry(
        name="collect_pasa_update_results",
        category="task",
        description="Collect PASA post-EVM staged inputs, per-round workspaces, and final updated GFF3 outputs into one manifest-bearing results directory.",
        inputs=(
            InterfaceField(
                "pasa_results",
                "Dir",
                "Original PASA results bundle used as the upstream database and transcript source.",
            ),
            InterfaceField(
                "evm_results",
                "Dir",
                "Original EVM results bundle used as the upstream consensus-annotation source.",
            ),
            InterfaceField(
                "pasa_update_inputs",
                "Dir",
                "Directory produced by prepare_pasa_update_inputs.",
            ),
            InterfaceField(
                "load_rounds",
                "list[Dir]",
                "Per-round PASA load-current-annotations directories in workflow order.",
            ),
            InterfaceField(
                "update_rounds",
                "list[Dir]",
                "Per-round PASA update directories in workflow order.",
            ),
            InterfaceField(
                "finalized_outputs",
                "Dir",
                "Directory produced by finalize_pasa_update_outputs.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped PASA-update results directory containing staged inputs, copied round workspaces, final updated GFF3 files, and run_manifest.json.",
            ),
        ),
        tags=("pasa", "post-evm", "results", "manifest"),
    ),
    RegistryEntry(
        name="repeatmasker_out_to_bed",
        category="task",
        description="Convert one external RepeatMasker `.out` file into the note-shaped RepeatMasker GFF3 plus three-column BED used for later overlap filtering.",
        inputs=(
            InterfaceField(
                "repeatmasker_out",
                "File",
                "RepeatMasker `.out` file produced upstream of this milestone.",
            ),
            InterfaceField(
                "rmout_to_gff3_script",
                "str",
                "rmOutToGFF3.pl path or executable name.",
            ),
            InterfaceField(
                "repeat_filter_sif",
                "str",
                "Optional Apptainer/Singularity image path for the repeat-filtering toolchain.",
            ),
        ),
        outputs=(
            InterfaceField(
                "repeatmasker_dir",
                "Dir",
                "Directory containing the staged RepeatMasker `.out`, converted repeatmasker.gff3, repeatmasker.bed, and run_manifest.json.",
            ),
        ),
        tags=("repeat-filtering", "repeatmasker", "conversion", "bed"),
    ),
    RegistryEntry(
        name="gffread_proteins",
        category="task",
        description="Extract proteins from one annotation GFF3 with gffread and emit a second period-stripped FASTA for the later funannotate repeat blast step.",
        inputs=(
            InterfaceField("annotation_gff3", "File", "Annotation GFF3 to translate into proteins."),
            InterfaceField("genome_fasta", "File", "Reference genome FASTA passed to gffread with -g."),
            InterfaceField(
                "protein_output_stem",
                "str",
                "Filename stem used for the emitted protein FASTA files.",
            ),
            InterfaceField(
                "gffread_binary",
                "str",
                "gffread path or executable name.",
            ),
            InterfaceField(
                "repeat_filter_sif",
                "str",
                "Optional Apptainer/Singularity image path for the repeat-filtering toolchain.",
            ),
        ),
        outputs=(
            InterfaceField(
                "proteins_dir",
                "Dir",
                "Directory containing `<stem>.proteins.fa`, `<stem>.proteins.no_periods.fa`, and run_manifest.json.",
            ),
        ),
        tags=("repeat-filtering", "gffread", "proteins", "diamond-ready"),
    ),
    RegistryEntry(
        name="funannotate_remove_bad_models",
        category="task",
        description="Run the note-shaped funannotate overlap filter against the current annotation, protein FASTA, and RepeatMasker BED to emit a clean GFF3 plus the overlap-removal list.",
        inputs=(
            InterfaceField("annotation_gff3", "File", "Current annotation GFF3 being overlap-filtered."),
            InterfaceField(
                "proteins_fasta",
                "File",
                "Protein FASTA, typically the period-stripped gffread output for the same annotation.",
            ),
            InterfaceField(
                "repeatmasker_bed",
                "File",
                "RepeatMasker BED produced by repeatmasker_out_to_bed.",
            ),
            InterfaceField(
                "clean_output_name",
                "str",
                "Filename used for the clean GFF3 emitted by the funannotate overlap stage.",
            ),
            InterfaceField(
                "funannotate_python",
                "str",
                "Python interpreter used to call the funannotate library wrapper shown in the notes.",
            ),
            InterfaceField(
                "repeat_filter_sif",
                "str",
                "Optional Apptainer/Singularity image path for the repeat-filtering toolchain.",
            ),
            InterfaceField(
                "min_protlen",
                "int",
                "Minimum protein length passed to funannotate RemoveBadModels.",
            ),
        ),
        outputs=(
            InterfaceField(
                "overlap_filter_dir",
                "Dir",
                "Directory containing the clean GFF3, the overlap-removal list emitted by funannotate, and run_manifest.json.",
            ),
        ),
        tags=("repeat-filtering", "funannotate", "overlap", "cleanup"),
    ),
    RegistryEntry(
        name="remove_overlap_repeat_models",
        category="task",
        description="Apply the overlap-removal list to the current annotation GFF3 as a deterministic local transform instead of a shell `grep -vFf` helper.",
        inputs=(
            InterfaceField("annotation_gff3", "File", "Current annotation GFF3."),
            InterfaceField(
                "models_to_remove",
                "File",
                "Overlap-removal list produced by funannotate_remove_bad_models.",
            ),
            InterfaceField(
                "output_name",
                "str",
                "Filename used for the filtered GFF3 output.",
            ),
        ),
        outputs=(
            InterfaceField(
                "filtered_dir",
                "Dir",
                "Directory containing the overlap-filtered GFF3 plus run_manifest.json.",
            ),
        ),
        tags=("repeat-filtering", "filtering", "overlap", "gff3"),
    ),
    RegistryEntry(
        name="funannotate_repeat_blast",
        category="task",
        description="Run the note-shaped funannotate repeat blast against the explicit local funannotate database root and emit repeat.dmnd.blast.txt.",
        inputs=(
            InterfaceField(
                "proteins_fasta",
                "File",
                "Protein FASTA, typically the period-stripped proteins from the overlap-filtered annotation.",
            ),
            InterfaceField(
                "funannotate_db_path",
                "str",
                "Local path to the funannotate database root used by RepeatBlast.",
            ),
            InterfaceField(
                "funannotate_python",
                "str",
                "Python interpreter used to call the funannotate library wrapper shown in the notes.",
            ),
            InterfaceField(
                "repeat_filter_sif",
                "str",
                "Optional Apptainer/Singularity image path for the repeat-filtering toolchain.",
            ),
            InterfaceField(
                "repeat_blast_cpu",
                "int",
                "CPU count passed to funannotate RepeatBlast.",
            ),
            InterfaceField(
                "repeat_blast_evalue",
                "float",
                "E-value threshold passed to funannotate RepeatBlast.",
            ),
        ),
        outputs=(
            InterfaceField(
                "repeat_blast_dir",
                "Dir",
                "Directory containing repeat.dmnd.blast.txt and run_manifest.json.",
            ),
        ),
        tags=("repeat-filtering", "funannotate", "blast", "repeats"),
    ),
    RegistryEntry(
        name="remove_repeat_blast_hits",
        category="task",
        description="Remove repeat-blast-hit models from the current annotation GFF3 using the notes-shaped Parent/ID filtering rules as a deterministic transform.",
        inputs=(
            InterfaceField("annotation_gff3", "File", "Current overlap-filtered annotation GFF3."),
            InterfaceField(
                "repeat_blast_results",
                "Dir",
                "Directory produced by funannotate_repeat_blast.",
            ),
            InterfaceField(
                "output_name",
                "str",
                "Filename used for the final repeat-filtered GFF3 output.",
            ),
        ),
        outputs=(
            InterfaceField(
                "filtered_dir",
                "Dir",
                "Directory containing the blast-filtered GFF3 plus run_manifest.json.",
            ),
        ),
        tags=("repeat-filtering", "filtering", "blast", "gff3"),
    ),
    RegistryEntry(
        name="collect_repeat_filter_results",
        category="task",
        description="Collect repeat-filtering stage outputs into a manifest-bearing results bundle rooted in the PASA-updated boundary and ending at final repeat-free GFF3 plus protein FASTA outputs.",
        inputs=(
            InterfaceField(
                "pasa_update_results",
                "Dir",
                "PASA post-EVM refinement results directory from annotation_refinement_pasa.",
            ),
            InterfaceField(
                "repeatmasker_conversion",
                "Dir",
                "Directory produced by repeatmasker_out_to_bed.",
            ),
            InterfaceField(
                "initial_proteins",
                "Dir",
                "Directory produced by the first gffread_proteins call against the PASA-updated GFF3.",
            ),
            InterfaceField(
                "overlap_filter",
                "Dir",
                "Directory produced by funannotate_remove_bad_models.",
            ),
            InterfaceField(
                "overlap_removed",
                "Dir",
                "Directory produced by remove_overlap_repeat_models.",
            ),
            InterfaceField(
                "bed_filtered_proteins",
                "Dir",
                "Directory produced by the second gffread_proteins call after overlap filtering.",
            ),
            InterfaceField(
                "repeat_blast",
                "Dir",
                "Directory produced by funannotate_repeat_blast.",
            ),
            InterfaceField(
                "blast_removed",
                "Dir",
                "Directory produced by remove_repeat_blast_hits.",
            ),
            InterfaceField(
                "final_proteins",
                "Dir",
                "Directory produced by the final gffread_proteins call after repeat blast filtering.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped repeat-filtering results directory containing copied stage outputs, final repeat-free GFF3/protein FASTA files, and run_manifest.json.",
            ),
        ),
        tags=("repeat-filtering", "results", "manifest", "cleanup"),
    ),
    RegistryEntry(
        name="busco_assess_proteins",
        category="task",
        description="Run one BUSCO protein-mode assessment against one selected lineage dataset downstream of repeat filtering.",
        inputs=(
            InterfaceField("proteins_fasta", "File", "Repeat-filtered protein FASTA used as the BUSCO input."),
            InterfaceField(
                "lineage_dataset",
                "str",
                "BUSCO lineage dataset identifier or local lineage path passed with `-l`; use `auto-lineage` to omit `-l` for fixture smoke runs.",
            ),
            InterfaceField(
                "busco_sif",
                "str",
                "Optional Apptainer/Singularity image path for BUSCO.",
            ),
            InterfaceField("busco_cpu", "int", "CPU count passed to BUSCO with `-c`."),
            InterfaceField("busco_mode", "str", "BUSCO mode passed with `-m`; this milestone uses `prot`."),
        ),
        outputs=(
            InterfaceField(
                "busco_run_dir",
                "Dir",
                "Directory containing one BUSCO lineage run plus run_manifest.json.",
            ),
        ),
        tags=("busco", "annotation-qc", "proteins", "lineage"),
    ),
    RegistryEntry(
        name="collect_busco_results",
        category="task",
        description="Collect BUSCO lineage runs into a manifest-bearing annotation-QC bundle rooted in the repeat-filtered protein FASTA boundary.",
        inputs=(
            InterfaceField(
                "repeat_filter_results",
                "Dir",
                "Repeat-filtering results directory containing the final repeat-free proteins FASTA.",
            ),
            InterfaceField("busco_runs", "list[Dir]", "One or more BUSCO lineage run directories to collect."),
            InterfaceField(
                "busco_lineages_text",
                "str",
                "Comma-separated lineage list recorded in the collector manifest and summary table.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped BUSCO QC results directory containing copied lineage runs, busco_summary.tsv, and run_manifest.json.",
            ),
        ),
        tags=("busco", "annotation-qc", "results", "manifest"),
    ),
    RegistryEntry(
        name="eggnog_map",
        category="task",
        description="Run EggNOG-mapper on the repeat-filtered protein FASTA boundary, preserve a deterministic tx2gene bridge, and propagate gene names into a reviewable annotated GFF3.",
        inputs=(
            InterfaceField(
                "repeat_filter_results",
                "Dir",
                "Repeat-filtering results directory containing the final repeat-free proteins FASTA and GFF3.",
            ),
            InterfaceField(
                "eggnog_data_dir",
                "str",
                "Local EggNOG database directory staged outside the repo milestone.",
            ),
            InterfaceField(
                "eggnog_sif",
                "str",
                "Optional Apptainer/Singularity image path for EggNOG-mapper.",
            ),
            InterfaceField("eggnog_cpu", "int", "CPU count passed to EggNOG-mapper with `--cpu`."),
            InterfaceField("eggnog_database", "str", "EggNOG taxonomic database or scope passed with `-d`."),
            InterfaceField("eggnog_mode", "str", "EggNOG mode passed with `-m`; this milestone uses `hmmer`."),
        ),
        outputs=(
            InterfaceField(
                "eggnog_run_dir",
                "Dir",
                "Directory containing EggNOG-mapper outputs, tx2gene.tsv, annotated GFF3, and run_manifest.json.",
            ),
        ),
        tags=("eggnog", "functional-annotation", "proteins", "gff3"),
    ),
    RegistryEntry(
        name="collect_eggnog_results",
        category="task",
        description="Collect EggNOG functional-annotation outputs into a manifest-bearing results bundle rooted in the repeat-filtered protein FASTA boundary.",
        inputs=(
            InterfaceField(
                "repeat_filter_results",
                "Dir",
                "Repeat-filtering results directory containing the final repeat-free proteins FASTA and GFF3.",
            ),
            InterfaceField("eggnog_run", "Dir", "EggNOG-mapper run directory to collect."),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped EggNOG results directory containing copied source boundary files, EggNOG outputs, and run_manifest.json.",
            ),
        ),
        tags=("eggnog", "functional-annotation", "results", "manifest"),
    ),
    RegistryEntry(
        name="agat_statistics",
        category="task",
        description="Run AGAT statistics on the EggNOG-annotated GFF3 bundle and collect the resulting summary files in a manifest-bearing results directory.",
        inputs=(
            InterfaceField(
                "eggnog_results",
                "Dir",
                "EggNOG results directory containing the annotated GFF3 boundary and run manifest.",
            ),
            InterfaceField(
                "annotation_fasta_path",
                "str",
                "Optional companion FASTA path for the AGAT statistics command.",
            ),
            InterfaceField(
                "agat_sif",
                "str",
                "Optional Apptainer/Singularity image path for AGAT.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped AGAT results directory containing the EggNOG-annotated GFF3 boundary, AGAT statistics output, and run_manifest.json.",
            ),
        ),
        tags=("agat", "post-processing", "statistics", "gff3"),
    ),
    RegistryEntry(
        name="agat_convert_sp_gxf2gxf",
        category="task",
        description="Run AGAT conversion on the EggNOG-annotated GFF3 bundle with `agat_convert_sp_gxf2gxf.pl` and collect the normalized GFF3 into a manifest-bearing results directory.",
        inputs=(
            InterfaceField(
                "eggnog_results",
                "Dir",
                "EggNOG results directory containing the annotated GFF3 boundary and run manifest.",
            ),
            InterfaceField(
                "agat_sif",
                "str",
                "Optional Apptainer/Singularity image path for AGAT.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped AGAT results directory containing the EggNOG-annotated GFF3 boundary, converted GFF3, and run_manifest.json.",
            ),
        ),
        tags=("agat", "post-processing", "conversion", "gff3"),
    ),
    RegistryEntry(
        name="agat_cleanup_gff3",
        category="task",
        description="Apply the deterministic post-AGAT GFF3 attribute cleanup to an AGAT conversion bundle and collect the cleaned GFF3 into a manifest-bearing results directory.",
        inputs=(
            InterfaceField(
                "agat_conversion_results",
                "Dir",
                "AGAT conversion results directory containing the converted GFF3 boundary and run manifest.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped AGAT cleanup results directory containing the converted source GFF3, cleaned GFF3, cleanup summary, and run_manifest.json.",
            ),
        ),
        tags=("agat", "post-processing", "cleanup", "gff3"),
    ),
    RegistryEntry(
        name="transdecoder_train_from_pasa",
        category="task",
        description="Run the TransDecoder LongOrfs/Predict phase sequence from PASA assemblies and lift ORFs onto genome coordinates.",
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
        name="stage_protein_fastas",
        category="task",
        description="Stage one or more local protein FASTA inputs into a deterministic combined protein evidence bundle.",
        inputs=(
            InterfaceField(
                "protein_fastas",
                "list[File]",
                "Local protein FASTA inputs supplied by the user in deterministic order.",
            ),
        ),
        outputs=(
            InterfaceField(
                "staged_dataset_dir",
                "Dir",
                "Directory containing staged protein FASTA inputs plus the combined evidence FASTA and manifest.",
            ),
        ),
        tags=("protein-evidence", "staging", "proteins", "local-inputs"),
    ),
    RegistryEntry(
        name="chunk_protein_fastas",
        category="task",
        description="Split a staged protein evidence FASTA deterministically into chunk FASTAs for parallel Exonerate runs.",
        inputs=(
            InterfaceField(
                "staged_proteins",
                "Dir",
                "Directory produced by stage_protein_fastas containing the combined protein FASTA.",
            ),
            InterfaceField(
                "proteins_per_chunk",
                "int",
                "Maximum number of protein records per chunk.",
            ),
        ),
        outputs=(
            InterfaceField(
                "chunk_dir",
                "Dir",
                "Directory containing deterministic chunk FASTAs and a chunk manifest.",
            ),
        ),
        tags=("protein-evidence", "chunking", "proteins", "exonerate"),
    ),
    RegistryEntry(
        name="exonerate_align_chunk",
        category="task",
        description="Run Exonerate for one protein FASTA chunk against the genome and preserve the raw alignment output.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA used as the alignment target."),
            InterfaceField(
                "protein_chunk",
                "File",
                "One chunk FASTA produced by chunk_protein_fastas.",
            ),
            InterfaceField(
                "exonerate_sif",
                "str",
                "Optional Apptainer/Singularity image path for Exonerate.",
            ),
            InterfaceField(
                "exonerate_model",
                "str",
                "Exonerate model name; defaults to protein2genome in this milestone.",
            ),
        ),
        outputs=(
            InterfaceField(
                "alignment_dir",
                "Dir",
                "Directory containing the raw Exonerate output and per-chunk metadata.",
            ),
        ),
        tags=("protein-evidence", "exonerate", "chunked", "alignment"),
    ),
    RegistryEntry(
        name="exonerate_to_evm_gff3",
        category="task",
        description="Convert one raw Exonerate chunk result into an EVM-compatible protein evidence GFF3.",
        inputs=(
            InterfaceField(
                "exonerate_alignment",
                "Dir",
                "Directory produced by exonerate_align_chunk containing the raw Exonerate output.",
            ),
        ),
        outputs=(
            InterfaceField(
                "converted_dir",
                "Dir",
                "Directory containing the chunk-level downstream-ready protein evidence GFF3 and per-chunk metadata.",
            ),
        ),
        tags=("protein-evidence", "exonerate", "gff3", "evm-ready"),
    ),
    RegistryEntry(
        name="exonerate_concat_results",
        category="task",
        description="Collect raw and converted Exonerate chunk outputs into stable concatenated artifacts and a manifest.",
        inputs=(
            InterfaceField(
                "genome",
                "File",
                "Reference genome FASTA used for provenance in the results bundle.",
            ),
            InterfaceField(
                "staged_proteins",
                "Dir",
                "Directory produced by stage_protein_fastas.",
            ),
            InterfaceField(
                "protein_chunks",
                "Dir",
                "Directory produced by chunk_protein_fastas.",
            ),
            InterfaceField(
                "raw_chunk_results",
                "list[Dir]",
                "Per-chunk Exonerate output directories in deterministic chunk order.",
            ),
            InterfaceField(
                "evm_chunk_results",
                "list[Dir]",
                "Per-chunk converted EVM-ready protein evidence directories in deterministic chunk order.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped protein-evidence results directory with raw and converted chunk artifacts plus a manifest.",
            ),
        ),
        tags=("protein-evidence", "results", "manifest", "exonerate", "evm-ready"),
    ),
    RegistryEntry(
        name="stage_braker3_inputs",
        category="task",
        description="Stage local BRAKER3-ready inputs into a deterministic bundle containing the genome plus explicitly provided evidence files.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField(
                "rnaseq_bam_path",
                "str",
                "Optional local RNA-seq BAM evidence path. This milestone requires at least one evidence input across RNA-seq BAM and protein FASTA.",
            ),
            InterfaceField(
                "protein_fasta_path",
                "str",
                "Optional local protein FASTA evidence path. This milestone requires at least one evidence input across RNA-seq BAM and protein FASTA.",
            ),
        ),
        outputs=(
            InterfaceField(
                "staged_inputs_dir",
                "Dir",
                "Directory containing staged BRAKER3 inputs plus run_manifest.json.",
            ),
        ),
        tags=("annotation", "braker3", "staging", "local-inputs"),
    ),
    RegistryEntry(
        name="braker3_predict",
        category="task",
        description="Run the repo's Galaxy tutorial-backed BRAKER3 command boundary and preserve the raw output directory with resolved braker.gff3.",
        inputs=(
            InterfaceField(
                "staged_inputs",
                "Dir",
                "Directory produced by stage_braker3_inputs.",
            ),
            InterfaceField(
                "braker_species",
                "str",
                "Species/model name passed to BRAKER3. The notes do not specify it; this repo uses a deterministic local default as a repo policy.",
            ),
            InterfaceField(
                "braker3_sif",
                "str",
                "Optional Apptainer/Singularity image path for BRAKER3.",
            ),
        ),
        outputs=(
            InterfaceField(
                "braker_run_dir",
                "Dir",
                "Directory containing raw BRAKER3 outputs, including braker.gff3, plus run_manifest.json.",
            ),
        ),
        tags=("annotation", "braker3", "prediction", "ab-initio"),
    ),
    RegistryEntry(
        name="normalize_braker3_for_evm",
        category="task",
        description="Normalize resolved braker.gff3 into a stable later-EVM-ready GFF3 boundary while preserving upstream source-column values.",
        inputs=(
            InterfaceField(
                "braker_run",
                "Dir",
                "Directory produced by braker3_predict containing braker.gff3.",
            ),
        ),
        outputs=(
            InterfaceField(
                "normalized_dir",
                "Dir",
                "Directory containing a deterministically normalized source-preserving BRAKER3 GFF3 plus run_manifest.json.",
            ),
        ),
        tags=("annotation", "braker3", "normalization", "evm-ready"),
    ),
    RegistryEntry(
        name="collect_braker3_results",
        category="task",
        description="Collect staged inputs, raw BRAKER3 outputs, and source-preserving normalized BRAKER3 GFF3 into a manifest-bearing results bundle.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA used for provenance."),
            InterfaceField(
                "staged_inputs",
                "Dir",
                "Directory produced by stage_braker3_inputs.",
            ),
            InterfaceField(
                "braker_run",
                "Dir",
                "Directory produced by braker3_predict.",
            ),
            InterfaceField(
                "normalized_braker",
                "Dir",
                "Directory produced by normalize_braker3_for_evm.",
            ),
            InterfaceField(
                "braker_species",
                "str",
                "Species/model name associated with the BRAKER3 run.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped BRAKER3 results directory containing staged inputs, raw outputs, source-preserving normalized outputs, and run_manifest.json.",
            ),
        ),
        tags=("annotation", "braker3", "results", "manifest"),
    ),
    RegistryEntry(
        name="prepare_evm_transcript_inputs",
        category="task",
        description="Stage `${db}.pasa_assemblies.gff3` from the PASA results bundle as the final `transcripts.gff3` pre-EVM contract file.",
        inputs=(
            InterfaceField(
                "pasa_results",
                "Dir",
                "PASA results directory containing the PASA assemblies GFF3 output.",
            ),
        ),
        outputs=(
            InterfaceField(
                "transcript_inputs_dir",
                "Dir",
                "Directory containing `transcripts.gff3` plus run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "transcript", "prep"),
    ),
    RegistryEntry(
        name="prepare_evm_protein_inputs",
        category="task",
        description="Stage the downstream-ready protein evidence outputs into a deterministic PROTEIN channel bundle for later EVM composition.",
        inputs=(
            InterfaceField(
                "protein_evidence_results",
                "Dir",
                "Protein evidence results directory containing protein_evidence.evm.gff3 and staged protein FASTA inputs.",
            ),
        ),
        outputs=(
            InterfaceField(
                "protein_inputs_dir",
                "Dir",
                "Directory containing `proteins.gff3` plus run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "protein", "prep"),
    ),
    RegistryEntry(
        name="prepare_evm_prediction_inputs",
        category="task",
        description="Assemble the final `predictions.gff3` pre-EVM contract file from source-preserving normalized BRAKER3 output plus the PASA-derived TransDecoder genome GFF3.",
        inputs=(
            InterfaceField(
                "transdecoder_results",
                "Dir",
                "TransDecoder results directory containing the PASA-derived genome GFF3 output.",
            ),
            InterfaceField(
                "braker3_results",
                "Dir",
                "BRAKER3 results directory containing staged inputs and the source-preserving normalized braker.gff3-derived output.",
            ),
        ),
        outputs=(
            InterfaceField(
                "prediction_inputs_dir",
                "Dir",
                "Directory containing `predictions.gff3`, the staged component GFF3 files, the authoritative reference genome, and run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "predictions", "prep"),
    ),
    RegistryEntry(
        name="collect_evm_prep_results",
        category="task",
        description="Collect staged transcript, prediction, and protein inputs into the note-faithful pre-EVM contract bundle without executing EVM.",
        inputs=(
            InterfaceField("transcript_inputs", "Dir", "Directory produced by prepare_evm_transcript_inputs."),
            InterfaceField("protein_inputs", "Dir", "Directory produced by prepare_evm_protein_inputs."),
            InterfaceField("prediction_inputs", "Dir", "Directory produced by prepare_evm_prediction_inputs."),
            InterfaceField(
                "pasa_results",
                "Dir",
                "Original PASA results bundle used for provenance and source-manifest copying.",
            ),
            InterfaceField(
                "transdecoder_results",
                "Dir",
                "Original TransDecoder results bundle used for provenance and source-manifest copying.",
            ),
            InterfaceField(
                "protein_evidence_results",
                "Dir",
                "Original protein evidence results bundle used for provenance and source-manifest copying.",
            ),
            InterfaceField(
                "braker3_results",
                "Dir",
                "Original BRAKER3 results bundle used for provenance and source-manifest copying.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped pre-EVM results directory containing `transcripts.gff3`, `predictions.gff3`, `proteins.gff3`, the authoritative reference genome, and run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "results", "manifest"),
    ),
    RegistryEntry(
        name="prepare_evm_execution_inputs",
        category="task",
        description="Stage the existing pre-EVM bundle into a deterministic EVM execution workspace and write an explicit or inferred evm.weights file.",
        inputs=(
            InterfaceField(
                "evm_prep_results",
                "Dir",
                "Pre-EVM results directory from consensus_annotation_evm_prep.",
            ),
            InterfaceField(
                "evm_weights_text",
                "str",
                "Optional explicit EVM weights content. When empty, the task infers weights from the notes example and the staged source-column names.",
            ),
        ),
        outputs=(
            InterfaceField(
                "evm_execution_inputs_dir",
                "Dir",
                "Directory containing genome.fa, transcripts.gff3, predictions.gff3, proteins.gff3, evm.weights, and run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "execution", "weights"),
    ),
    RegistryEntry(
        name="evm_partition_inputs",
        category="task",
        description="Run deterministic EVM partitioning against the staged execution workspace and preserve partitions_list.out for reviewable downstream execution.",
        inputs=(
            InterfaceField(
                "evm_execution_inputs",
                "Dir",
                "Directory produced by prepare_evm_execution_inputs.",
            ),
            InterfaceField(
                "evm_partition_script",
                "str",
                "Partition_EVM_inputs.pl path or executable name.",
            ),
            InterfaceField(
                "evm_segment_size",
                "int",
                "Segment size passed to partition_EVM_inputs.pl; defaults to the value shown in the notes.",
            ),
            InterfaceField(
                "evm_overlap_size",
                "int",
                "Overlap size passed to partition_EVM_inputs.pl; defaults to the value shown in the notes.",
            ),
            InterfaceField(
                "evm_sif",
                "str",
                "Optional Apptainer/Singularity image path for EVM utilities.",
            ),
        ),
        outputs=(
            InterfaceField(
                "partitioned_evm_inputs_dir",
                "Dir",
                "Directory containing the staged EVM workspace plus Partitions/, partitions_list.out, and run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "partitioning", "execution"),
    ),
    RegistryEntry(
        name="evm_write_commands",
        category="task",
        description="Generate and normalize the deterministic per-partition EVM command list from one partitioned workspace.",
        inputs=(
            InterfaceField(
                "partitioned_evm_inputs",
                "Dir",
                "Directory produced by evm_partition_inputs.",
            ),
            InterfaceField(
                "evm_write_commands_script",
                "str",
                "write_EVM_commands.pl path or executable name.",
            ),
            InterfaceField(
                "evm_output_file_name",
                "str",
                "Output basename passed to EVM command generation; defaults to evm.out.",
            ),
            InterfaceField(
                "evm_sif",
                "str",
                "Optional Apptainer/Singularity image path for EVM utilities.",
            ),
        ),
        outputs=(
            InterfaceField(
                "evm_commands_dir",
                "Dir",
                "Directory containing commands.list, the partitioned workspace copy, and run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "commands", "execution"),
    ),
    RegistryEntry(
        name="evm_execute_commands",
        category="task",
        description="Execute generated EVM commands sequentially in deterministic file order instead of submitting HPC job scripts.",
        inputs=(
            InterfaceField(
                "evm_commands",
                "Dir",
                "Directory produced by evm_write_commands.",
            ),
            InterfaceField(
                "evm_sif",
                "str",
                "Optional Apptainer/Singularity image path for EVM utilities.",
            ),
        ),
        outputs=(
            InterfaceField(
                "executed_evm_commands_dir",
                "Dir",
                "Directory containing the executed workspace, execution_logs/, and run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "execution", "sequential"),
    ),
    RegistryEntry(
        name="evm_recombine_outputs",
        category="task",
        description="Recombine partition outputs, convert them to GFF3, and finalize EVM.all.gff3, EVM.all.removed.gff3, and EVM.all.sort.gff3.",
        inputs=(
            InterfaceField(
                "executed_evm_commands",
                "Dir",
                "Directory produced by evm_execute_commands.",
            ),
            InterfaceField(
                "evm_recombine_script",
                "str",
                "recombine_EVM_partial_outputs.pl path or executable name.",
            ),
            InterfaceField(
                "evm_convert_script",
                "str",
                "convert_EVM_outputs_to_GFF3.pl path or executable name.",
            ),
            InterfaceField(
                "gff3sort_script",
                "str",
                "Optional gff3sort.pl path or executable name. When empty, sorting is skipped explicitly.",
            ),
            InterfaceField(
                "evm_output_file_name",
                "str",
                "Output basename used during EVM execution; defaults to evm.out.",
            ),
            InterfaceField(
                "evm_sif",
                "str",
                "Optional Apptainer/Singularity image path for EVM utilities.",
            ),
        ),
        outputs=(
            InterfaceField(
                "recombined_evm_outputs_dir",
                "Dir",
                "Directory containing recombined EVM outputs, final GFF3 files, and run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "recombine", "gff3"),
    ),
    RegistryEntry(
        name="collect_evm_results",
        category="task",
        description="Collect the pre-EVM bundle and all explicit EVM execution stages into one manifest-bearing consensus-annotation results directory.",
        inputs=(
            InterfaceField(
                "evm_prep_results",
                "Dir",
                "Original pre-EVM bundle from consensus_annotation_evm_prep.",
            ),
            InterfaceField(
                "evm_execution_inputs",
                "Dir",
                "Directory produced by prepare_evm_execution_inputs.",
            ),
            InterfaceField(
                "partitioned_evm_inputs",
                "Dir",
                "Directory produced by evm_partition_inputs.",
            ),
            InterfaceField(
                "evm_commands",
                "Dir",
                "Directory produced by evm_write_commands.",
            ),
            InterfaceField(
                "executed_evm_commands",
                "Dir",
                "Directory produced by evm_execute_commands.",
            ),
            InterfaceField(
                "recombined_evm_outputs",
                "Dir",
                "Directory produced by evm_recombine_outputs.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped EVM results directory containing copied stage outputs, evm.weights, partitions_list.out, commands.list, final GFF3 files, and run_manifest.json.",
            ),
        ),
        tags=("consensus", "evm", "results", "manifest"),
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
        description="Single-sample transcript-evidence workflow composed from de novo Trinity, STAR indexing/alignment, one-BAM merge, genome-guided Trinity, and StringTie; it now produces both Trinity branches required upstream of PASA while keeping the all-sample merge contract as a documented simplification.",
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
                "Timestamped transcript-evidence directory with de novo Trinity, STAR, merged BAM, genome-guided Trinity, StringTie, and a manifest.",
            ),
        ),
        tags=("workflow", "transcript-evidence", "star", "trinity", "stringtie"),
    ),
    RegistryEntry(
        name="pasa_transcript_alignment",
        category="workflow",
        description="PASA transcript preparation and align/assemble workflow built from the PASA tool reference and the transcript-evidence bundle's de novo Trinity, Trinity-GG, and StringTie outputs.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField(
                "transcript_evidence_results",
                "Dir",
                "Transcript evidence results directory containing trinity_denovo/, trinity_gg/, and stringtie/ outputs.",
            ),
            InterfaceField("univec_fasta", "File", "UniVec FASTA used by seqclean."),
            InterfaceField(
                "pasa_config_template",
                "File",
                "PASA alignAssembly template config file supplied from a PASA installation.",
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
        name="annotation_refinement_pasa",
        category="workflow",
        description="PASA post-EVM annotation-refinement workflow built from the PASA tool reference, explicit update rounds, and the existing PASA and EVM bundles.",
        inputs=(
            InterfaceField(
                "pasa_results",
                "Dir",
                "PASA results directory from pasa_transcript_alignment.",
            ),
            InterfaceField(
                "evm_results",
                "Dir",
                "EVM results directory from consensus_annotation_evm.",
            ),
            InterfaceField(
                "pasa_annot_compare_template",
                "File",
                "PASA annotCompare template config file supplied from a PASA installation.",
            ),
            InterfaceField(
                "fasta36_binary_path",
                "str",
                "Optional local fasta36 binary path used to create the note-described bin/fasta symlink.",
            ),
            InterfaceField(
                "load_current_annotations_script",
                "str",
                "Load_Current_Gene_Annotations.dbi path or executable name.",
            ),
            InterfaceField(
                "pasa_update_script",
                "str",
                "Launch_PASA_pipeline.pl path or executable name for annotCompare mode.",
            ),
            InterfaceField(
                "gff3sort_script",
                "str",
                "Optional gff3sort.pl path or executable name. When empty, sorting is skipped explicitly.",
            ),
            InterfaceField(
                "pasa_update_rounds",
                "int",
                "Number of PASA post-EVM update rounds to run; must be at least 2 to match the current PASA refinement contract.",
            ),
            InterfaceField(
                "pasa_sif",
                "str",
                "Optional Apptainer/Singularity image path for PASA tools.",
            ),
            InterfaceField(
                "pasa_update_cpu",
                "int",
                "CPU count passed to Launch_PASA_pipeline.pl during PASA post-EVM update rounds.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped PASA-update results directory with staged inputs, copied round workspaces, final updated GFF3 files, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "pasa", "post-evm", "annotation-refinement"),
    ),
    RegistryEntry(
        name="annotation_repeat_filtering",
        category="workflow",
        description="Repeat-filtering workflow that starts from the PASA-updated GFF3 boundary plus an external RepeatMasker `.out` file, runs explicit RepeatMasker conversion, gffread protein extraction, funannotate overlap filtering, repeat blasting, deterministic removal transforms, and collects a manifest-bearing repeat-free results bundle.",
        inputs=(
            InterfaceField(
                "pasa_update_results",
                "Dir",
                "PASA post-EVM refinement results directory from annotation_refinement_pasa.",
            ),
            InterfaceField(
                "repeatmasker_out",
                "File",
                "RepeatMasker `.out` file supplied as the upstream repeat-mask annotation source for this stage.",
            ),
            InterfaceField(
                "funannotate_db_path",
                "str",
                "Local path to the funannotate database root used for RepeatBlast.",
            ),
            InterfaceField(
                "rmout_to_gff3_script",
                "str",
                "rmOutToGFF3.pl path or executable name.",
            ),
            InterfaceField(
                "gffread_binary",
                "str",
                "gffread path or executable name.",
            ),
            InterfaceField(
                "funannotate_python",
                "str",
                "Python interpreter used to call the funannotate library wrappers shown in the notes.",
            ),
            InterfaceField(
                "repeat_filter_sif",
                "str",
                "Optional Apptainer/Singularity image path for the repeat-filtering toolchain.",
            ),
            InterfaceField(
                "min_protlen",
                "int",
                "Minimum protein length passed to funannotate RemoveBadModels.",
            ),
            InterfaceField(
                "repeat_blast_cpu",
                "int",
                "CPU count passed to funannotate RepeatBlast.",
            ),
            InterfaceField(
                "repeat_blast_evalue",
                "float",
                "E-value threshold passed to funannotate RepeatBlast.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped repeat-filtering results directory containing repeatmasker.gff3, repeatmasker.bed, intermediate filtered GFF3/protein FASTA files, final repeat-free outputs, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "repeat-filtering", "cleanup", "funannotate"),
    ),
    RegistryEntry(
        name="annotation_qc_busco",
        category="workflow",
        description="BUSCO-based annotation quality-assessment workflow that consumes the repeat-filtered protein FASTA boundary, runs one BUSCO task per selected lineage, and collects a manifest-bearing quality-assessment bundle.",
        inputs=(
            InterfaceField(
                "repeat_filter_results",
                "Dir",
                "Repeat-filtering results directory from annotation_repeat_filtering containing the final repeat-free protein FASTA that BUSCO treats as the quality-assessment input.",
            ),
            InterfaceField(
                "busco_lineages_text",
                "str",
                "Comma-separated BUSCO lineage list. The workflow currently defaults to the eukaryota, metazoa, insecta, arthropoda, and diptera lineages.",
            ),
            InterfaceField(
                "busco_sif",
                "str",
                "Optional Apptainer/Singularity image path for BUSCO.",
            ),
            InterfaceField("busco_cpu", "int", "CPU count passed to each BUSCO lineage run."),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped BUSCO quality-assessment results directory containing copied lineage runs, busco_summary.tsv, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "busco", "annotation-qc", "proteins"),
    ),
    RegistryEntry(
        name="annotation_functional_eggnog",
        category="workflow",
        description="EggNOG functional-annotation workflow that consumes the repeat-filtered protein FASTA boundary after quality assessment, runs EggNOG-mapper with an explicit database directory, and collects a manifest-bearing annotated GFF3 bundle.",
        inputs=(
            InterfaceField(
                "repeat_filter_results",
                "Dir",
                "Repeat-filtering results directory from annotation_repeat_filtering containing the final repeat-free proteins FASTA and GFF3 that the planner treats as the current quality-assessed source bundle.",
            ),
            InterfaceField(
                "eggnog_data_dir",
                "str",
                "Local EggNOG database directory staged outside the repo milestone.",
            ),
            InterfaceField(
                "eggnog_sif",
                "str",
                "Optional Apptainer/Singularity image path for EggNOG-mapper.",
            ),
            InterfaceField("eggnog_cpu", "int", "CPU count passed to EggNOG-mapper."),
            InterfaceField("eggnog_database", "str", "EggNOG database or taxonomic scope passed with `-d`."),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped EggNOG results directory containing copied source boundary files, EggNOG outputs, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "eggnog", "functional-annotation", "proteins"),
    ),
    RegistryEntry(
        name="annotation_postprocess_agat",
        category="workflow",
        description="AGAT post-processing workflow that consumes the EggNOG-annotated GFF3 bundle after quality assessment and collects the statistics slice in a manifest-bearing results directory.",
        inputs=(
            InterfaceField(
                "eggnog_results",
                "Dir",
                "EggNOG results directory from annotation_functional_eggnog containing the annotated GFF3 boundary that serves as the post-quality-assessment input for AGAT statistics.",
            ),
            InterfaceField(
                "annotation_fasta_path",
                "str",
                "Optional companion FASTA path for the AGAT statistics command.",
            ),
            InterfaceField(
                "agat_sif",
                "str",
                "Optional Apptainer/Singularity image path for AGAT.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped AGAT results directory containing copied source files, AGAT statistics output, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "agat", "post-processing", "statistics"),
    ),
    RegistryEntry(
        name="annotation_postprocess_agat_conversion",
        category="workflow",
        description="AGAT conversion workflow that consumes the EggNOG-annotated GFF3 bundle after quality assessment and collects the normalized GFF3 slice in a manifest-bearing results directory.",
        inputs=(
            InterfaceField(
                "eggnog_results",
                "Dir",
                "EggNOG results directory from annotation_functional_eggnog containing the annotated GFF3 boundary that serves as the post-quality-assessment input for AGAT conversion.",
            ),
            InterfaceField(
                "agat_sif",
                "str",
                "Optional Apptainer/Singularity image path for AGAT.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped AGAT results directory containing copied source files, the converted GFF3, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "agat", "post-processing", "conversion"),
    ),
    RegistryEntry(
        name="annotation_postprocess_agat_cleanup",
        category="workflow",
        description="AGAT cleanup workflow that consumes the AGAT conversion bundle after quality assessment and collects the deterministic cleaned GFF3 slice without running table2asn.",
        inputs=(
            InterfaceField(
                "agat_conversion_results",
                "Dir",
                "AGAT conversion results directory from annotation_postprocess_agat_conversion containing the converted GFF3 boundary that serves as the cleanup input after quality assessment.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped AGAT cleanup results directory containing copied source files, the cleaned GFF3, cleanup summary, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "agat", "post-processing", "cleanup"),
    ),
    RegistryEntry(
        name="annotation_postprocess_table2asn",
        category="workflow",
        description="table2asn submission workflow that consumes the AGAT cleanup bundle and produces an NCBI .sqn submission file alongside validation artefacts.",
        inputs=(
            InterfaceField(
                "agat_cleanup_results",
                "Dir",
                "AGAT cleanup results directory from annotation_postprocess_agat_cleanup containing the cleaned GFF3 that serves as the -f input to table2asn.",
            ),
            InterfaceField(
                "genome_fasta",
                "str",
                "Path to the repeat-masked genome FASTA used as the -i input to table2asn.",
            ),
            InterfaceField(
                "submission_template",
                "str",
                "Path to the NCBI .sbt template file generated on submit.ncbi.nlm.nih.gov (-t).",
            ),
            InterfaceField(
                "locus_tag_prefix",
                "str",
                "BioProject locus-tag prefix assigned by NCBI (-locus-tag-prefix). Omitted from the command when empty.",
            ),
            InterfaceField(
                "organism_annotation",
                "str",
                "NCBI organism annotation string such as [organism=Foo bar][isolate=X] (-j). Omitted when empty.",
            ),
            InterfaceField(
                "table2asn_binary",
                "str",
                "Name or path of the table2asn executable. Defaults to 'table2asn'.",
            ),
            InterfaceField(
                "table2asn_sif",
                "str",
                "Optional Apptainer/Singularity image path for table2asn.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped table2asn results directory containing the .sqn submission file, validation artefacts, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "table2asn", "ncbi", "submission", "post-processing"),
    ),
    RegistryEntry(
        name="transdecoder_from_pasa",
        category="workflow",
        description="TransDecoder coding-prediction workflow built from the PASA results bundle and the TransDecoder tool reference.",
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
        name="protein_evidence_alignment",
        category="workflow",
        description="Protein-evidence workflow that stages local protein FASTAs, chunks them deterministically, aligns each chunk with Exonerate, converts outputs to EVM-ready GFF3, and collects a manifest-bearing results bundle.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA used as the Exonerate target."),
            InterfaceField(
                "protein_fastas",
                "list[File]",
                "One or more local protein FASTA inputs supplied in deterministic order.",
            ),
            InterfaceField(
                "proteins_per_chunk",
                "int",
                "Maximum number of protein records per chunk produced by the workflow.",
            ),
            InterfaceField(
                "exonerate_sif",
                "str",
                "Optional Apptainer/Singularity image path for Exonerate.",
            ),
            InterfaceField(
                "exonerate_model",
                "str",
                "Exonerate model name passed to each chunk run; defaults to protein2genome.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped protein-evidence results directory containing raw and converted chunk outputs plus run_manifest.json.",
            ),
        ),
        tags=("workflow", "protein-evidence", "exonerate", "annotation"),
    ),
    RegistryEntry(
        name="ab_initio_annotation_braker3",
        category="workflow",
        description="BRAKER3-only ab initio annotation workflow that stages local inputs, runs a Galaxy tutorial-backed BRAKER3 boundary, preserves upstream braker.gff3 source values during normalization for later EVM use, and collects a manifest-bearing results bundle.",
        inputs=(
            InterfaceField("genome", "File", "Reference genome FASTA."),
            InterfaceField(
                "rnaseq_bam_path",
                "str",
                "Optional local RNA-seq BAM evidence path. This milestone requires at least one evidence input across RNA-seq BAM and protein FASTA.",
            ),
            InterfaceField(
                "protein_fasta_path",
                "str",
                "Optional local protein FASTA evidence path. This milestone requires at least one evidence input across RNA-seq BAM and protein FASTA.",
            ),
            InterfaceField(
                "braker_species",
                "str",
                "Species/model name passed to BRAKER3.",
            ),
            InterfaceField(
                "braker3_sif",
                "str",
                "Optional Apptainer/Singularity image path for BRAKER3.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped BRAKER3 results directory containing staged inputs, raw BRAKER3 outputs, source-preserving normalized GFF3, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "annotation", "braker3", "ab-initio"),
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
    RegistryEntry(
        name="consensus_annotation_evm_prep",
        category="workflow",
        description="Consensus annotation preparation workflow that assembles the note-faithful pre-EVM contract from PASA, TransDecoder, protein evidence, and BRAKER3 results and stops before EVM execution.",
        inputs=(
            InterfaceField(
                "pasa_results",
                "Dir",
                "PASA results directory from pasa_transcript_alignment.",
            ),
            InterfaceField(
                "transdecoder_results",
                "Dir",
                "TransDecoder results directory from transdecoder_from_pasa.",
            ),
            InterfaceField(
                "protein_evidence_results",
                "Dir",
                "Protein evidence results directory from protein_evidence_alignment.",
            ),
            InterfaceField(
                "braker3_results",
                "Dir",
                "BRAKER3 results directory from ab_initio_annotation_braker3.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped pre-EVM directory with `transcripts.gff3`, `predictions.gff3`, `proteins.gff3`, the authoritative reference genome, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "consensus", "evm", "prep"),
    ),
    RegistryEntry(
        name="consensus_annotation_evm",
        category="workflow",
        description="Consensus annotation workflow that consumes the existing pre-EVM bundle, stages EVM execution inputs, partitions deterministically, generates commands, executes them sequentially, recombines outputs, and collects a manifest-bearing EVM results bundle.",
        inputs=(
            InterfaceField(
                "evm_prep_results",
                "Dir",
                "Pre-EVM bundle from consensus_annotation_evm_prep.",
            ),
            InterfaceField(
                "evm_weights_text",
                "str",
                "Optional explicit EVM weights content. When empty, the workflow uses the documented inferred repo-local weights adaptation.",
            ),
            InterfaceField(
                "evm_partition_script",
                "str",
                "partition_EVM_inputs.pl path or executable name.",
            ),
            InterfaceField(
                "evm_write_commands_script",
                "str",
                "write_EVM_commands.pl path or executable name.",
            ),
            InterfaceField(
                "evm_recombine_script",
                "str",
                "recombine_EVM_partial_outputs.pl path or executable name.",
            ),
            InterfaceField(
                "evm_convert_script",
                "str",
                "convert_EVM_outputs_to_GFF3.pl path or executable name.",
            ),
            InterfaceField(
                "gff3sort_script",
                "str",
                "Optional gff3sort.pl path or executable name. When empty, sorting is skipped explicitly.",
            ),
            InterfaceField(
                "evm_output_file_name",
                "str",
                "EVM output basename; defaults to evm.out.",
            ),
            InterfaceField(
                "evm_segment_size",
                "int",
                "Segment size passed to EVM partitioning; defaults to the value shown in the notes.",
            ),
            InterfaceField(
                "evm_overlap_size",
                "int",
                "Overlap size passed to EVM partitioning; defaults to the value shown in the notes.",
            ),
            InterfaceField(
                "evm_sif",
                "str",
                "Optional Apptainer/Singularity image path for EVM utilities.",
            ),
        ),
        outputs=(
            InterfaceField(
                "results_dir",
                "Dir",
                "Timestamped EVM results directory containing copied stage outputs, evm.weights, partitions_list.out, commands.list, final GFF3 files, and run_manifest.json.",
            ),
        ),
        tags=("workflow", "consensus", "evm", "execution"),
    ),
)


# Workflow compatibility is layered on after the base entries so the original
# catalog list remains easy to scan and older callers still see the same entry
# names, descriptions, inputs, and outputs. Most task entries keep the safe
# default metadata; `busco_assess_proteins` has an explicit M18 fixture recipe
# path because it is exposed through the MCP saved-recipe surface.
_WORKFLOW_COMPATIBILITY_METADATA: dict[str, RegistryCompatibilityMetadata] = {
    "busco_assess_proteins": RegistryCompatibilityMetadata(
        biological_stage="BUSCO fixture and lineage assessment",
        accepted_planner_types=(),
        produced_planner_types=("Dir",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        composition_constraints=(
            "The M18 fixture path uses genome mode against the upstream BUSCO eukaryota test FASTA while the annotation QC workflow still runs BUSCO on repeat-filtered proteins.",
        ),
    ),
    "rnaseq_qc_quant": RegistryCompatibilityMetadata(
        biological_stage="RNA-seq QC and transcript quantification",
        accepted_planner_types=("ReadSet",),
        produced_planner_types=(),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "This workflow is a standalone RNA-seq QC/quantification branch and does not produce genome-annotation evidence.",
        ),
    ),
    "transcript_evidence_generation": RegistryCompatibilityMetadata(
        biological_stage="transcript evidence generation",
        accepted_planner_types=("ReferenceGenome", "ReadSet"),
        produced_planner_types=("TranscriptEvidenceSet",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Current implementation is a one paired-end sample subset of the full all-sample branch.",
            "Downstream PASA alignment should consume the manifest-bearing transcript evidence result bundle.",
        ),
    ),
    "pasa_transcript_alignment": RegistryCompatibilityMetadata(
        biological_stage="PASA transcript alignment and assembly",
        accepted_planner_types=("ReferenceGenome", "TranscriptEvidenceSet"),
        produced_planner_types=("TranscriptEvidenceSet",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes the existing transcript evidence result bundle directly.",
            "Requires a user-supplied UniVec FASTA and PASA config template.",
        ),
    ),
    "transdecoder_from_pasa": RegistryCompatibilityMetadata(
        biological_stage="TransDecoder coding-region prediction from PASA assemblies",
        accepted_planner_types=("TranscriptEvidenceSet",),
        produced_planner_types=("AnnotationEvidenceSet",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "TransDecoder command sequence remains documented as inferred from the notes.",
        ),
    ),
    "protein_evidence_alignment": RegistryCompatibilityMetadata(
        biological_stage="protein evidence alignment",
        accepted_planner_types=("ReferenceGenome", "ProteinEvidenceSet"),
        produced_planner_types=("ProteinEvidenceSet",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Protein FASTA inputs are local and explicit; the workflow does not fetch UniProt or RefSeq automatically.",
        ),
    ),
    "ab_initio_annotation_braker3": RegistryCompatibilityMetadata(
        biological_stage="BRAKER3 ab initio annotation",
        accepted_planner_types=("ReferenceGenome", "TranscriptEvidenceSet", "ProteinEvidenceSet"),
        produced_planner_types=("AnnotationEvidenceSet",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Requires a genome plus at least one explicit evidence source across RNA-seq BAM or protein FASTA.",
            "BRAKER3 invocation details remain Galaxy tutorial-backed where the notes are not explicit.",
        ),
    ),
    "consensus_annotation_evm_prep": RegistryCompatibilityMetadata(
        biological_stage="pre-EVM consensus input preparation",
        accepted_planner_types=("TranscriptEvidenceSet", "ProteinEvidenceSet", "AnnotationEvidenceSet"),
        produced_planner_types=("AnnotationEvidenceSet",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Assembles transcripts.gff3, predictions.gff3, and proteins.gff3 but does not execute EVM.",
        ),
    ),
    "consensus_annotation_evm": RegistryCompatibilityMetadata(
        biological_stage="EVidenceModeler consensus annotation",
        accepted_planner_types=("AnnotationEvidenceSet",),
        produced_planner_types=("ConsensusAnnotation",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes an existing pre-EVM bundle and stops before PASA update rounds.",
        ),
    ),
    "annotation_refinement_pasa": RegistryCompatibilityMetadata(
        biological_stage="PASA-based gene model update",
        accepted_planner_types=("TranscriptEvidenceSet", "ConsensusAnnotation"),
        produced_planner_types=("ConsensusAnnotation",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes existing PASA and EVM result bundles without reopening upstream evidence generation.",
        ),
    ),
    "annotation_repeat_filtering": RegistryCompatibilityMetadata(
        biological_stage="repeat filtering and annotation cleanup",
        accepted_planner_types=("ConsensusAnnotation",),
        produced_planner_types=("ConsensusAnnotation", "QualityAssessmentTarget"),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Starts from the PASA-updated sorted GFF3 boundary plus a user-supplied RepeatMasker .out file.",
        ),
    ),
    "annotation_qc_busco": RegistryCompatibilityMetadata(
        biological_stage="BUSCO annotation quality assessment",
        accepted_planner_types=("QualityAssessmentTarget",),
        produced_planner_types=("QualityAssessmentTarget",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes the repeat-filtered protein FASTA boundary as the current QC target and does not run EggNOG, AGAT, or submission prep.",
        ),
    ),
    "annotation_functional_eggnog": RegistryCompatibilityMetadata(
        biological_stage="EggNOG functional annotation",
        accepted_planner_types=("QualityAssessmentTarget",),
        produced_planner_types=("QualityAssessmentTarget",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes the repeat-filtered protein FASTA boundary after BUSCO-style quality assessment and keeps AGAT and submission prep deferred.",
        ),
    ),
    "annotation_postprocess_agat": RegistryCompatibilityMetadata(
        biological_stage="AGAT post-processing",
        accepted_planner_types=("QualityAssessmentTarget",),
        produced_planner_types=("QualityAssessmentTarget",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes the EggNOG-annotated GFF3 boundary after quality assessment and keeps AGAT conversion, cleanup, and table2asn as separate follow-on slices.",
        ),
    ),
    "annotation_postprocess_agat_conversion": RegistryCompatibilityMetadata(
        biological_stage="AGAT post-processing",
        accepted_planner_types=("QualityAssessmentTarget",),
        produced_planner_types=("QualityAssessmentTarget",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes the EggNOG-annotated GFF3 boundary after quality assessment, uses the AGAT conversion command family explicitly, and keeps cleanup as a separate follow-on slice before table2asn.",
        ),
    ),
    "annotation_postprocess_agat_cleanup": RegistryCompatibilityMetadata(
        biological_stage="AGAT post-processing",
        accepted_planner_types=("QualityAssessmentTarget",),
        produced_planner_types=("QualityAssessmentTarget",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes the AGAT conversion GFF3 boundary after quality assessment, applies the deterministic cleanup rules, and keeps table2asn deferred.",
        ),
    ),
    "annotation_postprocess_table2asn": RegistryCompatibilityMetadata(
        biological_stage="NCBI submission preparation",
        accepted_planner_types=("QualityAssessmentTarget",),
        produced_planner_types=("QualityAssessmentTarget",),
        reusable_as_reference=True,
        execution_defaults={"profile": "local", "result_manifest": "run_manifest.json"},
        synthesis_eligible=True,
        composition_constraints=(
            "Consumes the AGAT cleanup GFF3 boundary and runs table2asn to produce an NCBI .sqn submission file. Requires a valid NCBI .sbt submission template and a BioProject locus-tag prefix.",
        ),
    ),
}


_WORKFLOW_LOCAL_RESOURCE_DEFAULTS: dict[str, dict[str, str]] = {
    "busco_assess_proteins": {"cpu": "2", "memory": "8Gi", "execution_class": "local"},
    "rnaseq_qc_quant": {"cpu": "4", "memory": "16Gi", "execution_class": "local"},
    "transcript_evidence_generation": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "pasa_transcript_alignment": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "transdecoder_from_pasa": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "protein_evidence_alignment": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "ab_initio_annotation_braker3": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
    "consensus_annotation_evm_prep": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
    "consensus_annotation_evm": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
    "annotation_refinement_pasa": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "annotation_repeat_filtering": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
    "annotation_qc_busco": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
    "annotation_functional_eggnog": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
    "annotation_postprocess_agat": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "annotation_postprocess_agat_conversion": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "annotation_postprocess_agat_cleanup": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "annotation_postprocess_table2asn": {"cpu": "4", "memory": "16Gi", "execution_class": "local"},
}

# Slurm resource hints per workflow.  These are starting-point suggestions for
# HPC submission, not enforced limits.  cpu and memory match or slightly exceed
# the local defaults to account for Slurm job overhead; walltime is a
# conservative upper bound for a typical small-to-medium eukaryote genome.
# queue and account are intentionally absent — those are cluster-specific and
# must be supplied by the user via resource_request or the prompt.
_WORKFLOW_SLURM_RESOURCE_HINTS: dict[str, dict[str, str]] = {
    # Lightweight QC and quantification
    "busco_assess_proteins": {"cpu": "4", "memory": "16Gi", "walltime": "01:00:00"},
    "rnaseq_qc_quant": {"cpu": "4", "memory": "16Gi", "walltime": "01:00:00"},
    # RNA-seq evidence — Trinity can be memory-intensive; STAR index needs ~30 Gi
    "transcript_evidence_generation": {"cpu": "16", "memory": "64Gi", "walltime": "04:00:00"},
    # PASA alignment and refinement
    "pasa_transcript_alignment": {"cpu": "8", "memory": "32Gi", "walltime": "04:00:00"},
    "annotation_refinement_pasa": {"cpu": "8", "memory": "32Gi", "walltime": "08:00:00"},
    # TransDecoder is fast; conservative 1-hour ceiling covers large transcript sets
    "transdecoder_from_pasa": {"cpu": "8", "memory": "32Gi", "walltime": "01:00:00"},
    # Exonerate protein alignment — runtime scales with chunk count
    "protein_evidence_alignment": {"cpu": "8", "memory": "32Gi", "walltime": "04:00:00"},
    # BRAKER3 ab initio — heaviest stage; 24 hours covers most small eukaryotes
    "ab_initio_annotation_braker3": {"cpu": "16", "memory": "64Gi", "walltime": "24:00:00"},
    # EVM consensus steps
    "consensus_annotation_evm_prep": {"cpu": "16", "memory": "64Gi", "walltime": "02:00:00"},
    "consensus_annotation_evm": {"cpu": "16", "memory": "64Gi", "walltime": "04:00:00"},
    # RepeatMasker — slow; 12-hour ceiling for genome-scale repeat masking
    "annotation_repeat_filtering": {"cpu": "16", "memory": "64Gi", "walltime": "12:00:00"},
    # Post-filtering QC and annotation
    "annotation_qc_busco": {"cpu": "16", "memory": "64Gi", "walltime": "04:00:00"},
    "annotation_functional_eggnog": {"cpu": "16", "memory": "64Gi", "walltime": "04:00:00"},
    # AGAT post-processing — statistics and conversion are fast; cleanup is moderate
    "annotation_postprocess_agat": {"cpu": "4", "memory": "16Gi", "walltime": "00:30:00"},
    "annotation_postprocess_agat_conversion": {"cpu": "4", "memory": "16Gi", "walltime": "00:30:00"},
    "annotation_postprocess_agat_cleanup": {"cpu": "8", "memory": "32Gi", "walltime": "01:00:00"},
    "annotation_postprocess_table2asn": {"cpu": "4", "memory": "16Gi", "walltime": "02:00:00"},
}


def _with_resource_defaults(name: str, metadata: RegistryCompatibilityMetadata) -> RegistryCompatibilityMetadata:
    """Attach local resource defaults and Slurm resource hints to workflow compatibility metadata.

    Local defaults are placed under ``execution_defaults["resources"]`` and are
    used when no ``resource_request`` is supplied for a local run.  Slurm hints
    are placed under ``execution_defaults["slurm_resource_hints"]`` and serve as
    starting-point suggestions when the user requests Slurm execution without
    specifying explicit resources.  Both are advisory; any explicit
    ``resource_request`` from the caller takes precedence.

    Args:
        name: Workflow name to look up in the resource tables.
        metadata: The compatibility metadata to augment with resource guidance.

    Returns:
        Compatibility metadata with ``resources`` and ``slurm_resource_hints``
        populated where table entries exist, and ``slurm`` added to
        ``supported_execution_profiles`` when local defaults are present.
    """
    local_resources = _WORKFLOW_LOCAL_RESOURCE_DEFAULTS.get(name)
    slurm_hints = _WORKFLOW_SLURM_RESOURCE_HINTS.get(name)
    if local_resources is None and slurm_hints is None:
        return metadata
    execution_defaults = dict(metadata.execution_defaults)
    if local_resources is not None:
        execution_defaults.setdefault("resources", local_resources)
    if slurm_hints is not None:
        execution_defaults.setdefault("slurm_resource_hints", slurm_hints)
    supported_profiles = (
        tuple(dict.fromkeys((*metadata.supported_execution_profiles, "slurm")))
        if local_resources is not None
        else metadata.supported_execution_profiles
    )
    return replace(
        metadata,
        execution_defaults=execution_defaults,
        supported_execution_profiles=supported_profiles,
    )


def _backfill_workflow_compatibility_metadata(
    entries: tuple[RegistryEntry, ...],
) -> tuple[RegistryEntry, ...]:
    """Attach workflow planning notes while preserving the public catalog list.

    Args:
        entries: Catalog entries or workflow stages being combined for planning.

    Returns:
        The catalog entries with workflow planning notes attached where available.
    """
    return tuple(
        # `replace` keeps the existing name, category, description, inputs,
        # outputs, and tags intact while swapping in planner-facing notes.
        replace(
            entry,
            compatibility=_with_resource_defaults(entry.name, _WORKFLOW_COMPATIBILITY_METADATA[entry.name]),
        )
        if entry.name in _WORKFLOW_COMPATIBILITY_METADATA
        else entry
        for entry in entries
    )


REGISTRY_ENTRIES = _backfill_workflow_compatibility_metadata(REGISTRY_ENTRIES)
_REGISTRY = {entry.name: entry for entry in REGISTRY_ENTRIES}


def list_entries(category: Category | None = None) -> tuple[RegistryEntry, ...]:
    """List supported catalog entries, optionally restricted to tasks or workflows.

    Args:
        category: Optional category filter for tasks or workflows.

    Returns:
        The supported catalog entries in the requested category, if any.
    """
    if category is None:
        return REGISTRY_ENTRIES
    return tuple(entry for entry in REGISTRY_ENTRIES if entry.category == category)


def get_entry(name: str) -> RegistryEntry:
    """Return one catalog entry by name with a helpful error for unknown names.

    Args:
        name: The supported entry name being looked up.

    Returns:
        The catalog entry for the requested name.
    """
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        supported = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"Unknown catalog entry '{name}'. Supported entries: {supported}") from exc
