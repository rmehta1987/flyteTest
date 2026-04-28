"""GATK4 germline variant calling workflow compositions for Milestone B."""

from __future__ import annotations

from pathlib import Path

from flyte.io import File

from flytetest.config import variant_calling_env
from flytetest.manifest import build_manifest_envelope, write_json as _write_json
from flytetest.tasks.variant_calling import (
    apply_bqsr,
    apply_vqsr,
    base_recalibrator,
    bcftools_stats,
    bwa_mem2_index,
    bwa_mem2_mem,
    calculate_genotype_posteriors,
    collect_wgs_metrics,
    combine_gvcfs,
    create_sequence_dictionary,
    gather_vcfs,
    haplotype_caller,
    index_feature_file,
    joint_call_gvcfs,
    mark_duplicates,
    merge_bam_alignment,
    multiqc_summarize,
    my_custom_filter,
    snpeff_annotate,
    sort_sam,
    variant_filtration,
    variant_recalibrator,
)


# Source of truth for the registry-manifest contract for this workflow module.
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "prepared_ref",
    "preprocessed_bam",
    "preprocessed_bam_from_ubam",
    "scattered_gvcf",
    "genotyped_vcf",
    "refined_vcf",
    "refined_vcf_cgp",
    # Milestone I new workflow outputs
    "small_cohort_filtered_vcf",
    "pre_call_qc_bundle",
    "post_call_qc_bundle",
    "annotated_vcf",
)


@variant_calling_env.task
def prepare_reference(
    reference_fasta: File,
    known_sites: list[File],
    gatk_sif: str = "",
    bwa_sif: str = "",
    force: bool = False,
) -> File:
    """Prepare a reference genome for GATK germline variant calling.

    Steps (each skipped when the expected output already exists and
    ``force=False``):
      1. CreateSequenceDictionary — produces .dict file.
      2. IndexFeatureFile — indexes each known-sites VCF.
      3. bwa_mem2_index — creates BWA-MEM2 index files.

    Re-running with force=False skips steps whose outputs are present;
    pass force=True to rerun unconditionally.
    """
    from flytetest.config import project_mkdtemp

    ref_path = reference_fasta.download_sync()
    ref = Path(ref_path)
    skipped_steps: list[str] = []

    dict_path = ref.with_suffix(".dict")
    if force or not dict_path.exists():
        create_sequence_dictionary(
            reference_fasta=reference_fasta,
            gatk_sif=gatk_sif,
        )
    else:
        skipped_steps.append("create_sequence_dictionary")

    for vcf_file in known_sites:
        vcf = Path(vcf_file.download_sync())
        idx = vcf.with_suffix(vcf.suffix + ".idx")
        tbi = vcf.with_suffix(vcf.suffix + ".tbi")
        if force or (not idx.exists() and not tbi.exists()):
            index_feature_file(
                vcf=vcf_file,
                gatk_sif=gatk_sif,
            )
        else:
            skipped_steps.append("index_feature_file")

    bwa_suffixes = (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac")
    all_bwa_present = all(Path(ref_path + s).exists() for s in bwa_suffixes)
    if force or not all_bwa_present:
        bwa_mem2_index(
            reference_fasta=reference_fasta,
            bwa_sif=bwa_sif,
        )
    else:
        skipped_steps.append("bwa_mem2_index")

    out_dir = project_mkdtemp("prepare_reference_")
    manifest = build_manifest_envelope(
        stage="prepare_reference",
        assumptions=[
            "Reference FASTA is readable; all known-sites VCFs are accessible.",
            "Re-running with force=False skips steps whose outputs are present; pass force=True to rerun unconditionally.",
        ],
        inputs={"reference_fasta": ref_path, "force": force},
        outputs={"prepared_ref": ref_path, "skipped_steps": skipped_steps},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return File(path=ref_path)


@variant_calling_env.task
def preprocess_sample(
    reference_fasta: File,
    r1: File,
    sample_id: str,
    known_sites: list[File],
    r2: File | None = None,
    threads: int = 4,
    library_id: str | None = None,
    platform: str = "ILLUMINA",
    gatk_sif: str = "",
    bwa_sif: str = "",
) -> File:
    """Preprocess a sample from raw reads to BQSR-recalibrated BAM.

    Steps:
    1. bwa_mem2_mem — align reads → unsorted BAM.
    2. sort_sam — coordinate-sort BAM.
    3. mark_duplicates — mark PCR/optical duplicates.
    4. base_recalibrator — generate BQSR recalibration table.
    5. apply_bqsr — apply recalibration → final BAM.
    """
    from flytetest.config import project_mkdtemp

    aligned = bwa_mem2_mem(
        reference_fasta=reference_fasta, r1=r1, r2=r2,
        sample_id=sample_id, threads=threads,
        library_id=library_id, platform=platform, bwa_sif=bwa_sif,
    )
    sorted_bam = sort_sam(aligned_bam=aligned, sample_id=sample_id, gatk_sif=gatk_sif)
    dedup_bam, _metrics = mark_duplicates(sorted_bam=sorted_bam, sample_id=sample_id, gatk_sif=gatk_sif)
    bqsr_table = base_recalibrator(
        reference_fasta=reference_fasta, aligned_bam=dedup_bam,
        known_sites=known_sites, sample_id=sample_id, gatk_sif=gatk_sif,
    )
    recal_bam = apply_bqsr(
        reference_fasta=reference_fasta, aligned_bam=dedup_bam,
        bqsr_report=bqsr_table, sample_id=sample_id, gatk_sif=gatk_sif,
    )

    out_dir = project_mkdtemp("preprocess_sample_")
    manifest = build_manifest_envelope(
        stage="preprocess_sample",
        assumptions=[
            "Reference is prepared (prepare_reference must have run first).",
            "All known-sites VCFs are indexed.",
        ],
        inputs={
            "reference_fasta": reference_fasta.download_sync(),
            "r1": r1.download_sync(),
            "r2": r2.download_sync() if r2 is not None else "",
            "sample_id": sample_id,
        },
        outputs={"preprocessed_bam": recal_bam.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return recal_bam


@variant_calling_env.task
def germline_short_variant_discovery(
    reference_fasta: File,
    sample_ids: list[str],
    r1_paths: list[File],
    known_sites: list[File],
    intervals: list[str],
    r2_paths: list[File] | None = None,
    cohort_id: str = "cohort",
    threads: int = 4,
    gatk_sif: str = "",
    bwa_sif: str = "",
) -> File:
    """End-to-end germline short variant discovery from raw reads to joint VCF.

    Steps (per sample):
    1. preprocess_sample — align, sort, dedup, BQSR.
    2. haplotype_caller — per-sample GVCF.
    Then:
    3. combine_gvcfs — merge per-sample GVCFs.
    4. joint_call_gvcfs — joint genotyping → final VCF.
    """
    from flytetest.config import project_mkdtemp

    if len(sample_ids) != len(r1_paths):
        raise ValueError("sample_ids and r1_paths must be the same length")
    if r2_paths is not None and len(r2_paths) != len(sample_ids):
        raise ValueError("r2_paths must match sample_ids length when provided")
    if r2_paths is None:
        r2_paths = [None] * len(sample_ids)

    gvcf_files: list[File] = []
    for sample_id, r1, r2 in zip(sample_ids, r1_paths, r2_paths):
        recal_bam = preprocess_sample(
            reference_fasta=reference_fasta, r1=r1, r2=r2,
            sample_id=sample_id, known_sites=known_sites,
            threads=threads, gatk_sif=gatk_sif, bwa_sif=bwa_sif,
        )
        gvcf = haplotype_caller(
            reference_fasta=reference_fasta, aligned_bam=recal_bam,
            sample_id=sample_id, gatk_sif=gatk_sif,
        )
        gvcf_files.append(gvcf)

    combine_gvcfs(
        reference_fasta=reference_fasta, gvcfs=gvcf_files,
        cohort_id=cohort_id, gatk_sif=gatk_sif,
    )
    joint_vcf = joint_call_gvcfs(
        reference_fasta=reference_fasta, gvcfs=gvcf_files,
        sample_ids=sample_ids, intervals=intervals,
        cohort_id=cohort_id, gatk_sif=gatk_sif,
    )

    out_dir = project_mkdtemp("germline_discovery_")
    manifest = build_manifest_envelope(
        stage="germline_short_variant_discovery",
        assumptions=[
            "Reference is prepared (prepare_reference must have run first).",
            "All known-sites VCFs are indexed.",
            "At least one genomic interval is provided for GenomicsDBImport.",
        ],
        inputs={
            "reference_fasta": reference_fasta.download_sync(),
            "sample_ids": sample_ids,
            "intervals": intervals,
            "cohort_id": cohort_id,
        },
        outputs={"genotyped_vcf": joint_vcf.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return joint_vcf


@variant_calling_env.task
def genotype_refinement(
    reference_fasta: File,
    joint_vcf: File,
    snp_resources: list[File],
    snp_resource_flags: list[dict],
    indel_resources: list[File],
    indel_resource_flags: list[dict],
    cohort_id: str,
    sample_count: int,
    snp_filter_level: float = 0.0,
    indel_filter_level: float = 0.0,
    gatk_sif: str = "",
) -> File:
    """Refine a joint-called VCF with two-pass VQSR (SNP then INDEL).

    Pass 1 — SNP VQSR on the joint VCF.
    Pass 2 — INDEL VQSR on the SNP-filtered VCF (not the original joint VCF).
    """
    from flytetest.config import project_mkdtemp

    # Pass 1 — SNP
    snp_recal, snp_tranches = variant_recalibrator(
        reference_fasta=reference_fasta, cohort_vcf=joint_vcf,
        known_sites=snp_resources, known_sites_flags=snp_resource_flags,
        mode="SNP", cohort_id=cohort_id, sample_count=sample_count,
        gatk_sif=gatk_sif,
    )
    snp_vcf = apply_vqsr(
        reference_fasta=reference_fasta, input_vcf=joint_vcf,
        recal_file=snp_recal, tranches_file=snp_tranches,
        mode="SNP", cohort_id=cohort_id,
        truth_sensitivity_filter_level=snp_filter_level, gatk_sif=gatk_sif,
    )

    # Pass 2 — INDEL (input is the SNP-filtered VCF)
    indel_recal, indel_tranches = variant_recalibrator(
        reference_fasta=reference_fasta, cohort_vcf=snp_vcf,
        known_sites=indel_resources, known_sites_flags=indel_resource_flags,
        mode="INDEL", cohort_id=cohort_id, sample_count=sample_count,
        gatk_sif=gatk_sif,
    )
    refined_vcf = apply_vqsr(
        reference_fasta=reference_fasta, input_vcf=snp_vcf,
        recal_file=indel_recal, tranches_file=indel_tranches,
        mode="INDEL", cohort_id=cohort_id,
        truth_sensitivity_filter_level=indel_filter_level, gatk_sif=gatk_sif,
    )

    out_dir = project_mkdtemp("genotype_refinement_")
    manifest = build_manifest_envelope(
        stage="genotype_refinement",
        assumptions=[
            "joint_vcf is a cohort-level VCF with sufficient variant count for VQSR training.",
            "INDEL pass consumes the SNP-filtered VCF, not the original joint VCF.",
        ],
        inputs={
            "reference_fasta": reference_fasta.download_sync(),
            "joint_vcf": joint_vcf.download_sync(),
            "cohort_id": cohort_id,
            "sample_count": sample_count,
        },
        outputs={"refined_vcf": refined_vcf.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return refined_vcf


@variant_calling_env.task
def preprocess_sample_from_ubam(
    reference_fasta: File,
    r1: File,
    ubam: File,
    sample_id: str,
    known_sites: list[File],
    r2: File | None = None,
    threads: int = 4,
    library_id: str | None = None,
    platform: str = "ILLUMINA",
    gatk_sif: str = "",
    bwa_sif: str = "",
) -> File:
    """Preprocess a sample using the uBAM path (align → merge → dedup → BQSR)."""
    from flytetest.config import project_mkdtemp

    aligned = bwa_mem2_mem(
        reference_fasta=reference_fasta, r1=r1, r2=r2,
        sample_id=sample_id, threads=threads,
        library_id=library_id, platform=platform, bwa_sif=bwa_sif,
    )
    merged = merge_bam_alignment(
        reference_fasta=reference_fasta, aligned_bam=aligned,
        ubam=ubam, sample_id=sample_id, gatk_sif=gatk_sif,
    )
    dedup_bam, _metrics = mark_duplicates(sorted_bam=merged, sample_id=sample_id, gatk_sif=gatk_sif)
    bqsr_table = base_recalibrator(
        reference_fasta=reference_fasta, aligned_bam=dedup_bam,
        known_sites=known_sites, sample_id=sample_id, gatk_sif=gatk_sif,
    )
    recal_bam = apply_bqsr(
        reference_fasta=reference_fasta, aligned_bam=dedup_bam,
        bqsr_report=bqsr_table, sample_id=sample_id, gatk_sif=gatk_sif,
    )

    out_dir = project_mkdtemp("preprocess_from_ubam_")
    manifest = build_manifest_envelope(
        stage="preprocess_sample_from_ubam",
        assumptions=[
            "Reference is prepared (prepare_reference must have run first).",
            "All known-sites VCFs are indexed.",
            "ubam is queryname-sorted (MergeBamAlignment requirement).",
            "No sort_sam step — MergeBamAlignment --SORT_ORDER coordinate handles sorting.",
        ],
        inputs={
            "reference_fasta": reference_fasta.download_sync(),
            "r1": r1.download_sync(),
            "r2": r2.download_sync() if r2 is not None else "",
            "ubam": ubam.download_sync(),
            "sample_id": sample_id,
        },
        outputs={"preprocessed_bam_from_ubam": recal_bam.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return recal_bam


@variant_calling_env.task
def sequential_interval_haplotype_caller(
    reference_fasta: File,
    aligned_bam: File,
    sample_id: str,
    intervals: list[str],
    gatk_sif: str = "",
) -> File:
    """Call per-sample GVCFs serially across intervals, then gather.

    Execution is synchronous — all intervals run serially inside one task
    invocation. True scheduler-level scatter (job arrays or per-interval
    sbatch fan-out) is Milestone K HPC work.
    """
    from flytetest.config import project_mkdtemp

    if not intervals:
        raise ValueError("intervals must not be empty")

    interval_gvcfs: list[File] = []
    for interval in intervals:
        gvcf_file = haplotype_caller(
            reference_fasta=reference_fasta,
            aligned_bam=aligned_bam,
            sample_id=sample_id,
            intervals=[interval],
            gatk_sif=gatk_sif,
        )
        interval_gvcfs.append(gvcf_file)

    gathered = gather_vcfs(
        gvcfs=interval_gvcfs,
        sample_id=sample_id,
        gatk_sif=gatk_sif,
    )

    out_dir = project_mkdtemp("sequential_hc_")
    manifest = build_manifest_envelope(
        stage="sequential_interval_haplotype_caller",
        assumptions=[
            "Intervals must be non-empty and in genomic order for GatherVcfs.",
            "Execution is synchronous — all intervals run serially inside one task "
            "invocation. True scheduler-level scatter (job arrays or per-interval "
            "sbatch fan-out) is Milestone K HPC work.",
            "BAM must be BQSR-recalibrated (preprocess_sample or preprocess_sample_from_ubam must have run first).",
        ],
        inputs={
            "reference_fasta": reference_fasta.download_sync(),
            "aligned_bam": aligned_bam.download_sync(),
            "sample_id": sample_id,
            "intervals": intervals,
        },
        outputs={"scattered_gvcf": gathered.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return gathered


@variant_calling_env.task
def post_genotyping_refinement(
    input_vcf: File,
    cohort_id: str,
    supporting_callsets: list[File] | None = None,
    gatk_sif: str = "",
) -> File:
    """Apply CalculateGenotypePosteriors to a joint-called or VQSR-filtered VCF."""
    from flytetest.config import project_mkdtemp

    cgp = calculate_genotype_posteriors(
        input_vcf=input_vcf,
        cohort_id=cohort_id,
        supporting_callsets=supporting_callsets,
        gatk_sif=gatk_sif,
    )
    out_dir = project_mkdtemp("post_genotyping_")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest_envelope(
        stage="post_genotyping_refinement",
        assumptions=[
            "input_vcf is a joint-called or VQSR-filtered cohort VCF.",
            "supporting_callsets VCFs are indexed when provided.",
        ],
        inputs={"input_vcf": input_vcf.download_sync(), "cohort_id": cohort_id},
        outputs={"refined_vcf_cgp": cgp.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return cgp


# ---------------------------------------------------------------------------
# Step 04 — Hard-filtering fallback workflow
# ---------------------------------------------------------------------------

@variant_calling_env.task
def small_cohort_filter(
    reference_fasta: File,
    joint_vcf: File,
    cohort_id: str,
    snp_filter_expressions: list[tuple[str, str]] | None = None,
    indel_filter_expressions: list[tuple[str, str]] | None = None,
    gatk_sif: str = "",
) -> File:
    """Hard-filter a joint-called VCF with separate SNP and INDEL passes.

    Intended for cohorts too small for VQSR (<30k SNPs / <2k indels).
    Mirrors the two-pass structure of `genotype_refinement`:
      Pass 1 — SNP filtration on joint_vcf.
      Pass 2 — INDEL filtration on the SNP-filtered VCF.
    """
    from flytetest.config import project_mkdtemp

    snp_filtered = variant_filtration(
        reference_fasta=reference_fasta,
        input_vcf=joint_vcf,
        mode="SNP",
        cohort_id=cohort_id,
        filter_expressions=snp_filter_expressions,
        gatk_sif=gatk_sif,
    )
    final_vcf = variant_filtration(
        reference_fasta=reference_fasta,
        input_vcf=snp_filtered,
        mode="INDEL",
        cohort_id=cohort_id,
        filter_expressions=indel_filter_expressions,
        gatk_sif=gatk_sif,
    )

    out_dir = project_mkdtemp("small_cohort_filter_")
    manifest = build_manifest_envelope(
        stage="small_cohort_filter",
        assumptions=[
            "For cohorts with <30k SNPs or <2k indels where VQSR training fails.",
            "Pass 1 applies SNP filters to joint_vcf; Pass 2 applies INDEL filters to the SNP-filtered result.",
        ],
        inputs={
            "reference_fasta": reference_fasta.download_sync(),
            "joint_vcf": joint_vcf.download_sync(),
            "cohort_id": cohort_id,
        },
        outputs={"small_cohort_filtered_vcf": final_vcf.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return final_vcf


# ---------------------------------------------------------------------------
# Step 05 — QC bookend workflows
# ---------------------------------------------------------------------------

@variant_calling_env.task
def pre_call_coverage_qc(
    reference_fasta: File,
    aligned_bams: list[File],
    sample_ids: list[str],
    cohort_id: str,
    gatk_sif: str = "",
    multiqc_sif: str = "",
) -> File:
    """Per-sample WGS + insert-size metrics aggregated into one MultiQC report."""
    from flytetest.config import project_mkdtemp

    if len(aligned_bams) != len(sample_ids):
        raise ValueError("aligned_bams and sample_ids must be the same length")

    qc_files: list[File] = []
    for bam, sid in zip(aligned_bams, sample_ids):
        wgs, insert = collect_wgs_metrics(
            reference_fasta=reference_fasta, aligned_bam=bam,
            sample_id=sid, gatk_sif=gatk_sif,
        )
        qc_files.extend([wgs, insert])

    report = multiqc_summarize(qc_inputs=qc_files, cohort_id=cohort_id, multiqc_sif=multiqc_sif)

    out_dir = project_mkdtemp("pre_call_qc_")
    manifest = build_manifest_envelope(
        stage="pre_call_coverage_qc",
        assumptions=[
            "All BAMs must be coordinate-sorted and indexed.",
        ],
        inputs={"cohort_id": cohort_id, "sample_count": len(sample_ids)},
        outputs={"pre_call_qc_bundle": report.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return report


@variant_calling_env.task
def post_call_qc_summary(
    input_vcf: File,
    cohort_id: str,
    extra_qc_files: list[File] | None = None,
    bcftools_sif: str = "",
    multiqc_sif: str = "",
) -> File:
    """bcftools stats + MultiQC; optional extra_qc_files merges additional tool logs."""
    from flytetest.config import project_mkdtemp

    stats = bcftools_stats(input_vcf=input_vcf, cohort_id=cohort_id, bcftools_sif=bcftools_sif)
    qc_files = [stats, *(extra_qc_files or [])]
    report = multiqc_summarize(qc_inputs=qc_files, cohort_id=cohort_id, multiqc_sif=multiqc_sif)

    out_dir = project_mkdtemp("post_call_qc_")
    manifest = build_manifest_envelope(
        stage="post_call_qc_summary",
        assumptions=[
            "Input VCF must be valid for bcftools stats.",
        ],
        inputs={"input_vcf": input_vcf.download_sync(), "cohort_id": cohort_id},
        outputs={"post_call_qc_bundle": report.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return report


# ---------------------------------------------------------------------------
# Step 06 — Variant annotation workflow
# ---------------------------------------------------------------------------

@variant_calling_env.task
def annotate_variants_snpeff(
    input_vcf: File,
    cohort_id: str,
    snpeff_database: str,
    snpeff_data_dir: str,
    snpeff_sif: str = "",
) -> File:
    """Thin wrapper: annotate a VCF with SnpEff; return the annotated VCF."""
    from flytetest.config import project_mkdtemp

    annotated_vcf, _genes = snpeff_annotate(
        input_vcf=input_vcf,
        cohort_id=cohort_id,
        snpeff_database=snpeff_database,
        snpeff_data_dir=snpeff_data_dir,
        snpeff_sif=snpeff_sif,
    )

    out_dir = project_mkdtemp("annotate_snpeff_")
    manifest = build_manifest_envelope(
        stage="annotate_variants_snpeff",
        assumptions=[
            "snpeff_data_dir contains the pre-downloaded database for snpeff_database.",
            "No runtime database fetching; data must be staged before execution.",
        ],
        inputs={
            "input_vcf": input_vcf.download_sync(),
            "cohort_id": cohort_id,
            "snpeff_database": snpeff_database,
            "snpeff_data_dir": snpeff_data_dir,
        },
        outputs={"annotated_vcf": annotated_vcf.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return annotated_vcf


# ---------------------------------------------------------------------------
# Step 07 — On-ramp reference composition: user-authored filter on existing VCF
# ---------------------------------------------------------------------------

@variant_calling_env.task
def apply_custom_filter(
    vcf_path: File,
    min_qual: float = 30.0,
) -> File:
    """Apply a user-authored QUAL filter to an existing variant call set.

    On-ramp reference composition: wires ``my_custom_filter`` into the variant
    calling pipeline without re-running upstream GATK steps. Use when you
    already have a joint-called or VQSR-filtered VCF and want a custom quality
    threshold applied before downstream analysis. The minimal copyable template
    for adding a user-authored Python-callable task to the end of an existing
    pipeline.
    """
    from flytetest.config import project_mkdtemp

    filtered_vcf = my_custom_filter(vcf_path=vcf_path, min_qual=min_qual)
    out_dir = project_mkdtemp("apply_custom_filter_")
    manifest = build_manifest_envelope(
        stage="apply_custom_filter",
        assumptions=[
            "Input VCF is uncompressed plain text (no companion index needed).",
            "Filtering is QUAL-threshold only; no model-based filtering applied.",
        ],
        inputs={
            "vcf_path": vcf_path.download_sync(),
            "min_qual": min_qual,
        },
        outputs={"my_filtered_vcf": filtered_vcf.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return filtered_vcf
