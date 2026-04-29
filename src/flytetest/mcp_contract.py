"""Shared contract data for the FLyteTest MCP recipe surface.

This module centralizes the stdio MCP surface exposed by the recipe-backed
server: explicit runnable targets, tool and resource names, example prompts,
stable prompt-and-run result codes, typed-planning fields, and the canonical
MCP tool descriptions injected by ``create_mcp_server`` into FastMCP.

Canonical reply shapes live in ``src/flytetest/mcp_replies.py``
(``RunReply``, ``PlanDecline``, ``PlanSuccess``, ``DryRunReply``, etc.).

Tools are organised into three groups discoverable via the module-level
tuple constants ``EXPERIMENT_LOOP_TOOLS``, ``INSPECT_TOOLS``, and
``LIFECYCLE_TOOLS``, and in ``TOOL_DESCRIPTIONS`` keyed by tool name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flytetest.config import (
    ANNOTATION_WORKFLOW_NAME,
    PROTEIN_EVIDENCE_WORKFLOW_NAME,
)
from flytetest.registry import REGISTRY_ENTRIES


@dataclass(frozen=True, slots=True)
class ShowcaseTarget:
    """Describe one runnable workflow or task exposed by the MCP showcase.

    Attributes:
        name: Registered workflow or task name exposed through MCP.
        category: Whether the target is a workflow or task.
        module_name: Import path for the implementation module.
        source_path: Filesystem path to the implementation source file.
    """

    name: str
    category: str
    module_name: str
    source_path: Path


SHOWCASE_SERVER_NAME = "FLyteTest"
PRIMARY_TOOL_NAME = "prompt_and_run"
PREPARE_RECIPE_TOOL_NAME = "prepare_run_recipe"
RUN_RECIPE_TOOL_NAME = "run_local_recipe"
RUN_SLURM_RECIPE_TOOL_NAME = "run_slurm_recipe"
RUN_TASK_TOOL_NAME = "run_task"
RUN_WORKFLOW_TOOL_NAME = "run_workflow"
VALIDATE_RUN_RECIPE_TOOL_NAME = "validate_run_recipe"
LIST_SLURM_RUN_HISTORY_TOOL_NAME = "list_slurm_run_history"
MONITOR_SLURM_JOB_TOOL_NAME = "monitor_slurm_job"
RETRY_SLURM_JOB_TOOL_NAME = "retry_slurm_job"
CANCEL_SLURM_JOB_TOOL_NAME = "cancel_slurm_job"
APPROVE_COMPOSED_RECIPE_TOOL_NAME = "approve_composed_recipe"
LIST_AVAILABLE_BINDINGS_TOOL_NAME = "list_available_bindings"
LIST_BUNDLES_TOOL_NAME = "list_bundles"
LOAD_BUNDLE_TOOL_NAME = "load_bundle"
GET_RUN_SUMMARY_TOOL_NAME = "get_run_summary"
INSPECT_RUN_RESULT_TOOL_NAME = "inspect_run_result"
FETCH_JOB_LOG_TOOL_NAME = "fetch_job_log"
WAIT_FOR_SLURM_JOB_TOOL_NAME = "wait_for_slurm_job"
GET_PIPELINE_STATUS_TOOL_NAME = "get_pipeline_status"
# Flat-parameter convenience tools (one per showcase target).
VC_GERMLINE_DISCOVERY_TOOL_NAME = "vc_germline_discovery"
VC_PREPARE_REFERENCE_TOOL_NAME = "vc_prepare_reference"
VC_PREPROCESS_SAMPLE_TOOL_NAME = "vc_preprocess_sample"
VC_GENOTYPE_REFINEMENT_TOOL_NAME = "vc_genotype_refinement"
VC_SMALL_COHORT_FILTER_TOOL_NAME = "vc_small_cohort_filter"
VC_POST_GENOTYPING_REFINEMENT_TOOL_NAME = "vc_post_genotyping_refinement"
VC_SEQUENTIAL_INTERVAL_HC_TOOL_NAME = "vc_sequential_interval_haplotype_caller"
VC_PRE_CALL_COVERAGE_QC_TOOL_NAME = "vc_pre_call_coverage_qc"
VC_POST_CALL_QC_SUMMARY_TOOL_NAME = "vc_post_call_qc_summary"
VC_ANNOTATE_SNPEFF_TOOL_NAME = "vc_annotate_variants_snpeff"
VC_CUSTOM_FILTER_TOOL_NAME = "vc_custom_filter"
VC_APPLY_CUSTOM_FILTER_TOOL_NAME = "vc_apply_custom_filter"
VC_COUNT_RECORDS_TOOL_NAME = "vc_count_records"
ANNOTATION_BRAKER3_TOOL_NAME = "annotation_braker3"
ANNOTATION_PROTEIN_EVIDENCE_TOOL_NAME = "annotation_protein_evidence"
ANNOTATION_BUSCO_QC_TOOL_NAME = "annotation_busco_qc"
ANNOTATION_EGGNOG_TOOL_NAME = "annotation_eggnog"
ANNOTATION_AGAT_STATS_TOOL_NAME = "annotation_agat_stats"
ANNOTATION_AGAT_CONVERT_TOOL_NAME = "annotation_agat_convert"
ANNOTATION_AGAT_CLEANUP_TOOL_NAME = "annotation_agat_cleanup"
ANNOTATION_TABLE2ASN_TOOL_NAME = "annotation_table2asn"
ANNOTATION_GFFREAD_PROTEINS_TOOL_NAME = "annotation_gffread_proteins"
ANNOTATION_BUSCO_ASSESS_TOOL_NAME = "annotation_busco_assess"
ANNOTATION_EXONERATE_CHUNK_TOOL_NAME = "annotation_exonerate_chunk"
RNASEQ_QC_TOOL_NAME = "rnaseq_qc"
RNASEQ_FASTQC_TOOL_NAME = "rnaseq_fastqc"
RUN_RECIPE_RESOURCE_URI_PREFIX = "flytetest://run-recipes/"
RESULT_MANIFEST_RESOURCE_URI_PREFIX = "flytetest://result-manifests/"
# Experiment-loop tools: the scientist picks a target, loads a bundle, runs it.
EXPERIMENT_LOOP_TOOLS: tuple[str, ...] = (
    "list_entries",
    LIST_BUNDLES_TOOL_NAME,
    LOAD_BUNDLE_TOOL_NAME,
    RUN_TASK_TOOL_NAME,
    RUN_WORKFLOW_TOOL_NAME,
)

# Flat-parameter tools: one tool per showcase target for clients that cannot
# navigate the two-layer bindings/inputs surface.
FLAT_TOOLS: tuple[str, ...] = (
    VC_GERMLINE_DISCOVERY_TOOL_NAME,
    VC_PREPARE_REFERENCE_TOOL_NAME,
    VC_PREPROCESS_SAMPLE_TOOL_NAME,
    VC_GENOTYPE_REFINEMENT_TOOL_NAME,
    VC_SMALL_COHORT_FILTER_TOOL_NAME,
    VC_POST_GENOTYPING_REFINEMENT_TOOL_NAME,
    VC_SEQUENTIAL_INTERVAL_HC_TOOL_NAME,
    VC_PRE_CALL_COVERAGE_QC_TOOL_NAME,
    VC_POST_CALL_QC_SUMMARY_TOOL_NAME,
    VC_ANNOTATE_SNPEFF_TOOL_NAME,
    VC_CUSTOM_FILTER_TOOL_NAME,
    VC_APPLY_CUSTOM_FILTER_TOOL_NAME,
    VC_COUNT_RECORDS_TOOL_NAME,
    ANNOTATION_BRAKER3_TOOL_NAME,
    ANNOTATION_PROTEIN_EVIDENCE_TOOL_NAME,
    ANNOTATION_BUSCO_QC_TOOL_NAME,
    ANNOTATION_EGGNOG_TOOL_NAME,
    ANNOTATION_AGAT_STATS_TOOL_NAME,
    ANNOTATION_AGAT_CONVERT_TOOL_NAME,
    ANNOTATION_AGAT_CLEANUP_TOOL_NAME,
    ANNOTATION_TABLE2ASN_TOOL_NAME,
    ANNOTATION_GFFREAD_PROTEINS_TOOL_NAME,
    ANNOTATION_BUSCO_ASSESS_TOOL_NAME,
    ANNOTATION_EXONERATE_CHUNK_TOOL_NAME,
    RNASEQ_QC_TOOL_NAME,
    RNASEQ_FASTQC_TOOL_NAME,
)

# Inspect-before-execute tools: power-user surface between plan and execute.
INSPECT_TOOLS: tuple[str, ...] = (
    PREPARE_RECIPE_TOOL_NAME,
    RUN_RECIPE_TOOL_NAME,
    RUN_SLURM_RECIPE_TOOL_NAME,
    APPROVE_COMPOSED_RECIPE_TOOL_NAME,
    VALIDATE_RUN_RECIPE_TOOL_NAME,
)

# Lifecycle tools: observability, job management.
LIFECYCLE_TOOLS: tuple[str, ...] = (
    LIST_AVAILABLE_BINDINGS_TOOL_NAME,
    MONITOR_SLURM_JOB_TOOL_NAME,
    CANCEL_SLURM_JOB_TOOL_NAME,
    RETRY_SLURM_JOB_TOOL_NAME,
    WAIT_FOR_SLURM_JOB_TOOL_NAME,
    FETCH_JOB_LOG_TOOL_NAME,
    LIST_SLURM_RUN_HISTORY_TOOL_NAME,
    GET_RUN_SUMMARY_TOOL_NAME,
    INSPECT_RUN_RESULT_TOOL_NAME,
    GET_PIPELINE_STATUS_TOOL_NAME,
)

MCP_TOOL_NAMES: tuple[str, ...] = EXPERIMENT_LOOP_TOOLS + FLAT_TOOLS + INSPECT_TOOLS + LIFECYCLE_TOOLS

# ---------------------------------------------------------------------------
# Canonical tool descriptions
# ---------------------------------------------------------------------------

# Sentence appended verbatim to run_task, run_workflow, and run_slurm_recipe
# so tooling that surfaces tool descriptions to an LLM stays consistent.
QUEUE_ACCOUNT_HANDOFF: str = (
    'execution_defaults["slurm_resource_hints"] supplies sensible defaults for'
    " cpu / memory / walltime, but partition and account must come from the user —"
    " the server never invents them."
)

TOOL_DESCRIPTIONS: dict[str, str] = {
    # -- experiment-loop -------------------------------------------------------
    "list_entries": (
        "[experiment-loop] List registered pipeline workflows and tasks, optionally"
        " filtered by category or pipeline family."
    ),
    LIST_BUNDLES_TOOL_NAME: (
        "[experiment-loop] List curated starter bundles of typed biological inputs,"
        " optionally filtered by pipeline family; each entry includes an available"
        " flag and a reasons list so missing paths are visible even for unavailable"
        " bundles."
    ),
    LOAD_BUNDLE_TOOL_NAME: (
        "[experiment-loop] Load one curated starter bundle by name and return its"
        " typed bindings, scalar inputs, runtime images, and tool-database paths"
        " ready to spread into run_task or run_workflow; returns a structured"
        " decline instead of a KeyError when the name is unknown."
    ),
    RUN_TASK_TOOL_NAME: (
        "[experiment-loop] Run one registered task against typed biological bindings"
        " and scalar inputs, freezing the run into a WorkflowSpec artifact before"
        " execution so the experiment is reproducible from the returned recipe_id."
        " " + QUEUE_ACCOUNT_HANDOFF
    ),
    RUN_WORKFLOW_TOOL_NAME: (
        "[experiment-loop] Run one registered workflow against typed biological"
        " bindings and scalar inputs, freezing the run into a WorkflowSpec artifact"
        " before execution so the experiment is reproducible from the returned"
        " recipe_id. " + QUEUE_ACCOUNT_HANDOFF
    ),
    # -- inspect-before-execute ------------------------------------------------
    PREPARE_RECIPE_TOOL_NAME: (
        "[inspect-before-execute] Plan one natural-language prompt and save a frozen"
        " workflow-spec recipe artifact without executing it; inspect the artifact"
        " via validate_run_recipe or execute it later with run_local_recipe /"
        " run_slurm_recipe."
    ),
    RUN_RECIPE_TOOL_NAME: (
        "[inspect-before-execute] Execute a previously frozen workflow-spec recipe"
        " artifact on the local machine."
    ),
    RUN_SLURM_RECIPE_TOOL_NAME: (
        "[inspect-before-execute] Submit a previously frozen workflow-spec recipe"
        " artifact to Slurm. " + QUEUE_ACCOUNT_HANDOFF
    ),
    APPROVE_COMPOSED_RECIPE_TOOL_NAME: (
        "[inspect-before-execute] Grant explicit approval for a composed-recipe"
        " artifact; composed recipes cannot be executed until a valid approval record"
        " exists alongside the artifact."
    ),
    VALIDATE_RUN_RECIPE_TOOL_NAME: (
        "[inspect-before-execute] Validate a frozen recipe's bindings and staging"
        " paths without executing it; returns structured findings keyed by kind"
        " (binding, container, tool_database, shared_fs). Safe to call repeatedly —"
        " never submits, never writes, never mutates."
    ),
    # -- lifecycle -------------------------------------------------------------
    LIST_AVAILABLE_BINDINGS_TOOL_NAME: (
        "[lifecycle] Discover files in the workspace that could satisfy each"
        " parameter of a registered task, scanning up to depth 3 under search_root."
    ),
    MONITOR_SLURM_JOB_TOOL_NAME: (
        "[lifecycle] Inspect and reconcile a submitted Slurm job from its durable run"
        " record; for terminal jobs returns bounded stdout/stderr tails controlled by"
        " tail_lines."
    ),
    CANCEL_SLURM_JOB_TOOL_NAME: (
        "[lifecycle] Request cancellation for a submitted Slurm job from its durable"
        " run record."
    ),
    RETRY_SLURM_JOB_TOOL_NAME: (
        "[lifecycle] Retry a failed Slurm job from its durable run record; supply"
        " resource_overrides to escalate cpu / memory / walltime for OUT_OF_MEMORY"
        " or TIMEOUT failures without preparing a new recipe."
    ),
    WAIT_FOR_SLURM_JOB_TOOL_NAME: (
        "[lifecycle] Block until a Slurm job reaches a terminal state or the timeout"
        " expires, polling monitor_slurm_job at poll_interval_s second intervals."
    ),
    FETCH_JOB_LOG_TOOL_NAME: (
        "[lifecycle] Return the tail of a Slurm scheduler log file (stdout or"
        " stderr), bounded by tail_lines."
    ),
    LIST_SLURM_RUN_HISTORY_TOOL_NAME: (
        "[lifecycle] List recent durable Slurm submissions from .runtime/runs/"
        " without querying the scheduler, optionally filtered by workflow_name,"
        " active_only, or terminal_only."
    ),
    GET_RUN_SUMMARY_TOOL_NAME: (
        "[lifecycle] Return a state-grouped summary of recent local and Slurm run"
        " records from .runtime/runs/ without scheduler calls."
    ),
    INSPECT_RUN_RESULT_TOOL_NAME: (
        "[lifecycle] Load one run record and return a structured human-readable"
        " summary including workflow name, state, output paths, and the durable"
        " asset index; no scheduler calls."
    ),
    GET_PIPELINE_STATUS_TOOL_NAME: (
        "[lifecycle] Return a per-stage status checklist for the 15-stage annotation"
        " pipeline based on durable Slurm run records."
    ),
    # -- flat-parameter tools (one per showcase target) -------------------------
    VC_GERMLINE_DISCOVERY_TOOL_NAME: (
        "[flat] Run end-to-end germline short variant discovery from raw paired-end"
        " FASTQs to a joint-genotyped VCF. Accepts reference_fasta (str),"
        " sample_ids (list[str]), r1_paths (list[str]), known_sites (list[str]),"
        " intervals (list[str]), cohort_id (str), and optional r2_paths, threads,"
        " gatk_sif, bwa_sif, partition, account, cpu, memory, walltime,"
        " shared_fs_roots, module_loads, dry_run. All paths must be absolute. "
        + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_PREPARE_REFERENCE_TOOL_NAME: (
        "[flat] Prepare a reference genome for GATK4 germline variant calling"
        " (CreateSequenceDictionary, samtools faidx, BWA-MEM2 index, IndexFeatureFile"
        " for each known-sites VCF). Accepts reference_fasta (str), known_sites"
        " (list[str]), and optional gatk_sif, bwa_sif, force, partition, account,"
        " cpu, memory, walltime, shared_fs_roots, module_loads, dry_run. All paths"
        " must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_PREPROCESS_SAMPLE_TOOL_NAME: (
        "[flat] Preprocess one sample from paired-end FASTQs to a BQSR-recalibrated"
        " BAM (BWA-MEM2 align → sort → MarkDuplicates → BaseRecalibrator →"
        " ApplyBQSR). Accepts reference_fasta (str), r1 (str), sample_id (str),"
        " known_sites (list[str]), and optional r2, threads, gatk_sif, bwa_sif,"
        " partition, account, cpu, memory, walltime, shared_fs_roots, module_loads,"
        " dry_run. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_GENOTYPE_REFINEMENT_TOOL_NAME: (
        "[flat] Refine a joint-called VCF with two-pass VQSR (SNP then INDEL)"
        " followed by CalculateGenotypePosteriors. Accepts reference_fasta (str),"
        " joint_vcf (str), snp_resources (list[str]), snp_resource_flags"
        " (list[dict]), indel_resources (list[str]), indel_resource_flags"
        " (list[dict]), cohort_id (str), sample_count (int), and optional gatk_sif,"
        " partition, account, cpu, memory, walltime, shared_fs_roots, module_loads,"
        " dry_run. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_SMALL_COHORT_FILTER_TOOL_NAME: (
        "[flat] Hard-filter a joint-called VCF for cohorts too small for VQSR"
        " (< 30 samples). Accepts reference_fasta (str), joint_vcf (str),"
        " cohort_id (str), and optional gatk_sif, partition, account, cpu, memory,"
        " walltime, shared_fs_roots, module_loads, dry_run. All paths must be"
        " absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_POST_GENOTYPING_REFINEMENT_TOOL_NAME: (
        "[flat] Apply CalculateGenotypePosteriors to a joint-called or"
        " VQSR-filtered VCF. Accepts input_vcf (str), cohort_id (str), and optional"
        " gatk_sif, partition, account, cpu, memory, walltime, shared_fs_roots,"
        " module_loads, dry_run. All paths must be absolute. "
        + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_SEQUENTIAL_INTERVAL_HC_TOOL_NAME: (
        "[flat] Call per-sample GVCFs serially across intervals, then gather into"
        " one GVCF (HaplotypeCaller → GatherVCFs). Accepts reference_fasta (str),"
        " aligned_bam (str), sample_id (str), intervals (list[str]), and optional"
        " gatk_sif, partition, account, cpu, memory, walltime, shared_fs_roots,"
        " module_loads, dry_run. All paths must be absolute. "
        + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_PRE_CALL_COVERAGE_QC_TOOL_NAME: (
        "[flat] Aggregate per-sample WGS and insert-size metrics into a MultiQC"
        " report (CollectWgsMetrics → multiqc_summarize). Accepts reference_fasta"
        " (str), aligned_bams (list[str]), sample_ids (list[str]), cohort_id (str),"
        " and optional gatk_sif, multiqc_sif, partition, account, cpu, memory,"
        " walltime, shared_fs_roots, module_loads, dry_run. All paths must be"
        " absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_POST_CALL_QC_SUMMARY_TOOL_NAME: (
        "[flat] Run bcftools stats and MultiQC for post-call VCF QC. Accepts"
        " input_vcf (str), cohort_id (str), and optional bcftools_sif, multiqc_sif,"
        " partition, account, cpu, memory, walltime, shared_fs_roots, module_loads,"
        " dry_run. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_ANNOTATE_SNPEFF_TOOL_NAME: (
        "[flat] Annotate a filtered VCF with SnpEff functional variant annotation."
        " Accepts input_vcf (str), cohort_id (str), snpeff_database (str),"
        " snpeff_data_dir (str), and optional snpeff_sif, partition, account, cpu,"
        " memory, walltime, shared_fs_roots, module_loads, dry_run. All paths must"
        " be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_CUSTOM_FILTER_TOOL_NAME: (
        "[flat] Apply a pure-Python QUAL threshold filter to a plain-text VCF."
        " On-ramp reference task — drops records with QUAL below min_qual or with"
        " missing QUAL ('.'); header lines are always preserved; no container"
        " required. Accepts input_vcf (str) and optional min_qual (default 30.0),"
        " partition, account, cpu, memory, walltime, shared_fs_roots, module_loads,"
        " dry_run. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_APPLY_CUSTOM_FILTER_TOOL_NAME: (
        "[flat] Apply a user-authored QUAL filter to an existing variant call set."
        " On-ramp reference composition — wires my_custom_filter into the variant"
        " calling pipeline without re-running upstream GATK steps. Accepts vcf_path"
        " (str) and optional min_qual (default 30.0), partition, account, cpu,"
        " memory, walltime, shared_fs_roots, module_loads, dry_run. All paths must"
        " be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    VC_COUNT_RECORDS_TOOL_NAME: (
        "[flat] Count header and data lines in a plain-text VCF and emit a small"
        " JSON report. Tutorial-chapter toy task (chapter 07): the smallest"
        " end-to-end pure-Python example a reader can copy. Accepts vcf (str) and"
        " optional partition, account, cpu, memory, walltime, shared_fs_roots,"
        " module_loads, dry_run. All paths must be absolute. "
        + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_BRAKER3_TOOL_NAME: (
        "[flat] Run the BRAKER3 ab initio gene prediction workflow. Accepts genome"
        " (str) and optional rnaseq_bam_path, protein_fasta_path, braker_species,"
        " braker3_sif, partition, account, cpu, memory, walltime, shared_fs_roots,"
        " module_loads, dry_run. All paths must be absolute. "
        + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_PROTEIN_EVIDENCE_TOOL_NAME: (
        "[flat] Align protein evidence to a genome with Exonerate"
        " (protein_evidence_alignment workflow). Accepts genome (str),"
        " protein_fastas (list[str]), and optional proteins_per_chunk,"
        " exonerate_model, exonerate_sif, partition, account, cpu, memory, walltime,"
        " shared_fs_roots, module_loads, dry_run. All paths must be absolute. "
        + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_BUSCO_QC_TOOL_NAME: (
        "[flat] Run multi-lineage BUSCO quality assessment on repeat-filtered"
        " proteins (annotation_qc_busco workflow). Accepts repeat_filter_results"
        " (str) and optional busco_lineages_text, busco_sif, busco_cpu, partition,"
        " account, cpu, memory, walltime, shared_fs_roots, module_loads, dry_run."
        " All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_EGGNOG_TOOL_NAME: (
        "[flat] Run EggNOG functional annotation on repeat-filtered proteins"
        " (annotation_functional_eggnog workflow). Accepts repeat_filter_results"
        " (str), eggnog_data_dir (str), and optional eggnog_sif, eggnog_cpu,"
        " eggnog_database, partition, account, cpu, memory, walltime,"
        " shared_fs_roots, module_loads, dry_run. All paths must be absolute. "
        + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_AGAT_STATS_TOOL_NAME: (
        "[flat] Collect AGAT statistics for the EggNOG-annotated GFF3 boundary"
        " (annotation_postprocess_agat workflow). Accepts eggnog_results (str) and"
        " optional annotation_fasta_path, agat_sif, partition, account, cpu, memory,"
        " walltime, shared_fs_roots, module_loads, dry_run. All paths must be"
        " absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_AGAT_CONVERT_TOOL_NAME: (
        "[flat] Convert the EggNOG-annotated GFF3 with AGAT"
        " (annotation_postprocess_agat_conversion workflow). Accepts eggnog_results"
        " (str) and optional agat_sif, partition, account, cpu, memory, walltime,"
        " shared_fs_roots, module_loads, dry_run. All paths must be absolute. "
        + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_AGAT_CLEANUP_TOOL_NAME: (
        "[flat] Apply deterministic attribute cleanup to AGAT conversion output"
        " (annotation_postprocess_agat_cleanup workflow). Accepts"
        " agat_conversion_results (str) and optional partition, account, cpu, memory,"
        " walltime, shared_fs_roots, module_loads, dry_run. All paths must be"
        " absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_TABLE2ASN_TOOL_NAME: (
        "[flat] Run table2asn to produce an NCBI .sqn submission file"
        " (annotation_postprocess_table2asn workflow). Accepts agat_cleanup_results"
        " (str), genome_fasta (str), submission_template (str), and optional"
        " locus_tag_prefix, organism_annotation, table2asn_binary, table2asn_sif,"
        " partition, account, cpu, memory, walltime, shared_fs_roots, module_loads,"
        " dry_run. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_GFFREAD_PROTEINS_TOOL_NAME: (
        "[flat] Extract protein sequences from an annotation GFF3 with gffread"
        " (gffread_proteins task). Accepts annotation_gff3 (str), genome_fasta (str),"
        " and optional protein_output_stem, gffread_binary, repeat_filter_sif,"
        " partition, account, cpu, memory, walltime, shared_fs_roots, module_loads,"
        " dry_run. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_BUSCO_ASSESS_TOOL_NAME: (
        "[flat] Run one BUSCO lineage assessment on a repeat-filtered protein FASTA"
        " (busco_assess_proteins task). Accepts proteins_fasta (str),"
        " lineage_dataset (str), and optional busco_sif, busco_cpu, busco_mode,"
        " partition, account, cpu, memory, walltime, shared_fs_roots, module_loads,"
        " dry_run. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    ANNOTATION_EXONERATE_CHUNK_TOOL_NAME: (
        "[flat] Run Exonerate alignment for one protein FASTA chunk against the"
        " genome (exonerate_align_chunk task). Accepts genome (str),"
        " protein_chunk (str), and optional exonerate_sif, exonerate_model,"
        " partition, account, cpu, memory, walltime, shared_fs_roots, module_loads,"
        " dry_run. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    RNASEQ_QC_TOOL_NAME: (
        "[flat] Run RNA-seq QC and Salmon transcript quantification"
        " (rnaseq_qc_quant workflow). Accepts ref (str), left (str), right (str),"
        " and optional sample_id, salmon_sif, fastqc_sif, partition, account, cpu,"
        " memory, walltime, shared_fs_roots, module_loads, dry_run. All paths must"
        " be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
    RNASEQ_FASTQC_TOOL_NAME: (
        "[flat] Run FastQC quality control on paired-end RNA-seq reads (fastqc"
        " task). Accepts left (str), right (str), and optional fastqc_sif, partition,"
        " account, cpu, memory, walltime, shared_fs_roots, module_loads, dry_run."
        " All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
    ),
}

MCP_RESOURCE_URIS = (
    "flytetest://scope",
    "flytetest://supported-targets",
    "flytetest://example-prompts",
    "flytetest://prompt-and-run-contract",
    RUN_RECIPE_RESOURCE_URI_PREFIX + "{path}",
    RESULT_MANIFEST_RESOURCE_URI_PREFIX + "{path}",
)

SUPPORTED_WORKFLOW_NAME = ANNOTATION_WORKFLOW_NAME
SUPPORTED_PROTEIN_WORKFLOW_NAME = PROTEIN_EVIDENCE_WORKFLOW_NAME
SUPPORTED_TASK_NAME = "exonerate_align_chunk"
SUPPORTED_BUSCO_FIXTURE_TASK_NAME = "busco_assess_proteins"

_PACKAGE_ROOT = Path(__file__).resolve().parent


def _resolve_source_path(module_name: str) -> Path:
    """Derive the source file path for a flytetest module from its import path."""
    relative = module_name.removeprefix("flytetest.").replace(".", "/") + ".py"
    return _PACKAGE_ROOT / relative


SHOWCASE_TARGETS = tuple(
    ShowcaseTarget(
        name=entry.name,
        category=entry.category,
        module_name=entry.showcase_module,
        source_path=_resolve_source_path(entry.showcase_module),
    )
    for entry in REGISTRY_ENTRIES
    if entry.showcase_module
)
SHOWCASE_TARGETS_BY_NAME = {target.name: target for target in SHOWCASE_TARGETS}
SUPPORTED_TARGET_NAMES = tuple(target.name for target in SHOWCASE_TARGETS)
SUPPORTED_WORKFLOW_NAMES = tuple(target.name for target in SHOWCASE_TARGETS if target.category == "workflow")
SUPPORTED_TASK_NAMES = tuple(target.name for target in SHOWCASE_TARGETS if target.category == "task")

RECIPE_INPUT_CONTEXT_FIELDS = (
    "manifest_sources",
    "explicit_bindings",
    "runtime_bindings",
    "resource_request",
    "execution_profile",
    "runtime_image",
)
RECIPE_INPUT_MANIFEST_RULES = (
    "Provide each manifest source as a `run_manifest.json` path or a result directory containing one.",
    "Manifest sources are validated before typed planning runs, and unreadable or missing sources are rejected.",
    "The resolver refuses to guess when multiple manifests could satisfy the requested planner type.",
)
RECIPE_INPUT_BINDING_RULES = (
    "Serialized planner bindings are accepted as JSON mappings keyed by planner type name.",
    "Direct MCP clients must send structured binding arguments as real JSON/object mappings, not stringified pseudo-dicts.",
    "BUSCO, EggNOG, and AGAT use a `QualityAssessmentTarget` binding when the target is supplied directly instead of recovered from a manifest.",
)
RECIPE_INPUT_RUNTIME_RULES = (
    "Runtime bindings are frozen into the saved recipe and are not inferred from prompt text.",
    "Direct MCP clients must send `runtime_bindings`, `resource_request`, and `runtime_image` as real JSON/object mappings.",
    "If an LLM-driven client drops optional tool arguments, encode the execution profile and resource choices in the prompt text and verify the returned frozen profile before Slurm submission.",
    "The M18 BUSCO fixture task uses `proteins_fasta`, `lineage_dataset`, `busco_mode`, optional `busco_sif`, and `busco_cpu` runtime bindings.",
    "BUSCO runtime bindings begin with `busco_lineages_text`, optional `busco_sif`, and `busco_cpu`.",
    "EggNOG runtime bindings are `eggnog_data_dir`, optional `eggnog_sif`, `eggnog_cpu`, and `eggnog_database`.",
    "AGAT runtime bindings are `annotation_fasta_path` and optional `agat_sif` for statistics, and optional `agat_sif` for conversion.",
    "Resource requests use structured `ResourceSpec` fields such as `cpu`, `memory`, `partition`, `account`, and `walltime`.",
    "`local` recipes run through explicit local handlers; `slurm` recipes can be submitted with `run_slurm_recipe` after they are frozen.",
    "`list_slurm_run_history` reads durable `.runtime/runs/` records only, supports optional `workflow_name`, `active_only`, and `terminal_only` filters, and does not require live scheduler access.",
    "Slurm recipe submission and lifecycle tools require FLyteTest to run inside an already-authenticated scheduler-capable environment with the needed Slurm CLI commands on PATH.",
    "`monitor_slurm_job`, `retry_slurm_job`, and `cancel_slurm_job` operate from durable `.runtime/runs/` Slurm run records and return explicit unsupported-environment limitations when that scheduler boundary is unavailable.",
    "`retry_slurm_job` stays Slurm-specific, reuses the frozen saved recipe plus recorded execution profile, and declines when the run record is not terminal, not clearly retryable, or already at its attempt limit. For `resource_exhaustion` failures (`OUT_OF_MEMORY`, `TIMEOUT`), pass `resource_overrides` with one or more of `cpu`, `memory`, `walltime`, `partition`, `account`, or `gpu` to escalate resources without re-preparing the recipe. `DEADLINE` failures are excluded from escalation and require a new `prepare_run_recipe` call.",
    "`monitor_slurm_job` accepts an optional `tail_lines` parameter (default 50, max 500). When the job has reached a terminal state, the response includes `stdout_tail` and `stderr_tail` with the last N lines of the scheduler log files. Set `tail_lines=0` to disable log reading.",
    "Runtime image policy can be frozen as `RuntimeImageSpec` metadata, while existing workflow SIF inputs remain explicit runtime bindings.",
)

WORKFLOW_EXAMPLE_PROMPT = (
    "Annotate the genome sequence of a small eukaryote using BRAKER3 "
    "with genome data/braker3/reference/genome.fa, RNA-seq evidence data/braker3/rnaseq/RNAseq.bam, "
    "and protein evidence data/braker3/protein_data/fastas/proteins.fa"
)
PROTEIN_WORKFLOW_EXAMPLE_PROMPT = (
    "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein "
    "evidence data/braker3/protein_data/fastas/proteins.fa"
)
TASK_EXAMPLE_PROMPT = (
    "Experiment with Exonerate protein-to-genome alignment using genome "
    "data/braker3/reference/genome.fa and protein chunk data/braker3/protein_data/fastas/proteins.fa"
)
SHOWCASE_LIMITATIONS = (
    "This server runs a fixed set of analysis pipelines — call list_entries to see what is available.",
    "Every job is saved as a frozen recipe before it runs, so the exact inputs and settings used are always recorded.",
    "Additional pipelines can be added by the server administrator when needed.",
)
LIST_ENTRIES_LIMITATIONS = (
    "Only the pipelines listed above are available to run from this server.",
    "Describe what you want in plain language — the server will match it to the right pipeline, prepare a recipe, and submit the job.",
)
PROMPT_REQUIREMENTS = (
    "Write explicit local file paths directly in the prompt when you want prompt-derived runtime bindings.",
    "Provide manifest sources, serialized planner bindings, runtime bindings, resource requests, execution profiles, and runtime-image policy explicitly when the prompt text does not already carry them.",
    "When an LLM-driven client does not preserve optional tool arguments reliably, place critical execution policy such as `execution profile slurm` and resource choices directly in the prompt text and verify the returned frozen recipe.",
    "Keep the request to one supported target per prompt.",
)
EXAMPLE_PROMPT_REQUIREMENTS = (
    "Include explicit local file paths in the prompt text.",
    "Use one of the currently runnable MCP recipe targets until additional local handlers are registered.",
)

RESULT_CODE_SUCCEEDED = "succeeded"
RESULT_CODE_DECLINED_MISSING_INPUTS = "declined_missing_inputs"
RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST = "declined_unsupported_request"
RESULT_CODE_FAILED_EXECUTION = "failed_execution"

REASON_CODE_COMPLETED = "completed"
REASON_CODE_MISSING_REQUIRED_INPUTS = "missing_required_inputs"
REASON_CODE_UNSUPPORTED_OR_AMBIGUOUS_REQUEST = "unsupported_or_ambiguous_request"
REASON_CODE_NONZERO_EXIT_STATUS = "nonzero_exit_status"
REASON_CODE_UNSUPPORTED_EXECUTION_TARGET = "unsupported_execution_target"

RESULT_SUMMARY_FIELDS = (
    "status",
    "result_code",
    "reason_code",
    "target_name",
    "target_category",
    "execution_attempted",
    "used_inputs",
    "output_paths",
    "exit_status",
    "decline_reason",
    "supported_targets",
    "typed_planning_available",
    "artifact_path",
    "execution_profile",
    "resource_spec",
    "runtime_image",
    "message",
)
RESULT_CODE_DEFINITIONS = {
    RESULT_CODE_SUCCEEDED: {
        "status": "succeeded",
        "reason_codes": [REASON_CODE_COMPLETED],
    },
    RESULT_CODE_DECLINED_MISSING_INPUTS: {
        "status": "declined",
        "reason_codes": [REASON_CODE_MISSING_REQUIRED_INPUTS],
    },
    RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST: {
        "status": "declined",
        "reason_codes": [REASON_CODE_UNSUPPORTED_OR_AMBIGUOUS_REQUEST],
    },
    RESULT_CODE_FAILED_EXECUTION: {
        "status": "failed",
        "reason_codes": [
            REASON_CODE_NONZERO_EXIT_STATUS,
            REASON_CODE_UNSUPPORTED_EXECUTION_TARGET,
        ],
    },
}
DECLINE_CATEGORY_CODES = {
    "missing_inputs": RESULT_CODE_DECLINED_MISSING_INPUTS,
    "unsupported_or_ambiguous_request": RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST,
}


def supported_runnable_targets_payload() -> list[dict[str, str]]:
    """Return the runnable MCP targets as a stable resource payload."""
    return [{"name": target.name, "category": target.category} for target in SHOWCASE_TARGETS]
