"""GATK4 germline variant calling workflow compositions for Milestone B."""

from __future__ import annotations

from pathlib import Path

from flyte.io import File

from flytetest.config import variant_calling_env
from flytetest.manifest_envelope import build_manifest_envelope
from flytetest.manifest_io import write_json as _write_json
from flytetest.tasks.variant_calling import (
    apply_bqsr,
    base_recalibrator,
    bwa_mem2_index,
    bwa_mem2_mem,
    combine_gvcfs,
    create_sequence_dictionary,
    haplotype_caller,
    index_feature_file,
    joint_call_gvcfs,
    mark_duplicates,
    sort_sam,
)


# Source of truth for the registry-manifest contract for this workflow module.
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "prepared_ref",
    "preprocessed_bam",
    "genotyped_vcf",
)


@variant_calling_env.task
def prepare_reference(
    ref_path: str,
    known_sites: list[str],
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Prepare a reference genome for GATK germline variant calling.

    Steps:
    1. CreateSequenceDictionary — produces .dict file.
    2. IndexFeatureFile — indexes each known-sites VCF.
    3. bwa_mem2_index — creates BWA-MEM2 index files.
    """
    create_sequence_dictionary(
        reference_fasta=File(path=ref_path),
        gatk_sif=sif_path,
    )
    for vcf_path in known_sites:
        index_feature_file(
            vcf=File(path=vcf_path),
            gatk_sif=sif_path,
        )
    bwa_mem2_index(
        ref_path=ref_path,
        results_dir=results_dir,
        sif_path=sif_path,
    )

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest_envelope(
        stage="prepare_reference",
        assumptions=[
            "Reference FASTA is readable; all known-sites VCFs are accessible.",
            "bwa_mem2_index writes index files into results_dir.",
        ],
        inputs={"ref_path": ref_path, "known_sites": known_sites},
        outputs={"prepared_ref": ref_path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return manifest


@variant_calling_env.task
def preprocess_sample(
    ref_path: str,
    r1_path: str,
    sample_id: str,
    known_sites: list[str],
    results_dir: str,
    r2_path: str = "",
    threads: int = 4,
    sif_path: str = "",
) -> dict:
    """Preprocess a sample from raw reads to BQSR-recalibrated BAM.

    Steps:
    1. bwa_mem2_mem — align reads → unsorted BAM.
    2. sort_sam — coordinate-sort BAM.
    3. mark_duplicates — mark PCR/optical duplicates.
    4. base_recalibrator — generate BQSR recalibration table.
    5. apply_bqsr — apply recalibration → final BAM.
    """
    aligned = bwa_mem2_mem(
        ref_path=ref_path,
        r1_path=r1_path,
        sample_id=sample_id,
        results_dir=results_dir,
        r2_path=r2_path,
        threads=threads,
        sif_path=sif_path,
    )
    sorted_bam = sort_sam(
        bam_path=aligned["outputs"]["aligned_bam"],
        sample_id=sample_id,
        results_dir=results_dir,
        sif_path=sif_path,
    )
    deduped = mark_duplicates(
        bam_path=sorted_bam["outputs"]["sorted_bam"],
        sample_id=sample_id,
        results_dir=results_dir,
        sif_path=sif_path,
    )
    known_site_files = [File(path=vcf) for vcf in known_sites]
    bqsr_table = base_recalibrator(
        reference_fasta=File(path=ref_path),
        aligned_bam=File(path=deduped["outputs"]["dedup_bam"]),
        known_sites=known_site_files,
        sample_id=sample_id,
        gatk_sif=sif_path,
    )
    recal_bam = apply_bqsr(
        reference_fasta=File(path=ref_path),
        aligned_bam=File(path=deduped["outputs"]["dedup_bam"]),
        bqsr_report=File(path=bqsr_table.path),
        sample_id=sample_id,
        gatk_sif=sif_path,
    )

    out_dir = Path(results_dir)
    manifest = build_manifest_envelope(
        stage="preprocess_sample",
        assumptions=[
            "Reference is prepared (prepare_reference must have run first).",
            "All known-sites VCFs are indexed.",
        ],
        inputs={
            "ref_path": ref_path,
            "r1_path": r1_path,
            "r2_path": r2_path,
            "sample_id": sample_id,
            "known_sites": known_sites,
        },
        outputs={"preprocessed_bam": recal_bam.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return manifest


@variant_calling_env.task
def germline_short_variant_discovery(
    ref_path: str,
    sample_ids: list[str],
    r1_paths: list[str],
    known_sites: list[str],
    intervals: list[str],
    results_dir: str,
    r2_paths: list[str] | None = None,
    cohort_id: str = "cohort",
    threads: int = 4,
    sif_path: str = "",
) -> dict:
    """End-to-end germline short variant discovery from raw reads to joint VCF.

    Steps (per sample):
    1. preprocess_sample — align, sort, dedup, BQSR.
    2. haplotype_caller — per-sample GVCF.
    Then:
    3. combine_gvcfs — merge per-sample GVCFs.
    4. joint_call_gvcfs — joint genotyping → final VCF.
    """
    if r2_paths is None:
        r2_paths = [""] * len(sample_ids)

    gvcf_paths: list[str] = []
    for sample_id, r1, r2 in zip(sample_ids, r1_paths, r2_paths):
        preprocessed = preprocess_sample(
            ref_path=ref_path,
            r1_path=r1,
            sample_id=sample_id,
            known_sites=known_sites,
            results_dir=results_dir,
            r2_path=r2,
            threads=threads,
            sif_path=sif_path,
        )
        recal_bam_path = preprocessed["outputs"]["preprocessed_bam"]
        gvcf = haplotype_caller(
            reference_fasta=File(path=ref_path),
            aligned_bam=File(path=recal_bam_path),
            sample_id=sample_id,
            gatk_sif=sif_path,
        )
        gvcf_paths.append(gvcf.path)

    gvcf_files = [File(path=p) for p in gvcf_paths]
    combine_gvcfs(
        reference_fasta=File(path=ref_path),
        gvcfs=gvcf_files,
        cohort_id=cohort_id,
        gatk_sif=sif_path,
    )
    joint_vcf = joint_call_gvcfs(
        reference_fasta=File(path=ref_path),
        gvcfs=gvcf_files,
        sample_ids=sample_ids,
        intervals=intervals,
        cohort_id=cohort_id,
        gatk_sif=sif_path,
    )

    out_dir = Path(results_dir)
    manifest = build_manifest_envelope(
        stage="germline_short_variant_discovery",
        assumptions=[
            "Reference is prepared (prepare_reference must have run first).",
            "All known-sites VCFs are indexed.",
            "At least one genomic interval is provided for GenomicsDBImport.",
        ],
        inputs={
            "ref_path": ref_path,
            "sample_ids": sample_ids,
            "known_sites": known_sites,
            "intervals": intervals,
            "cohort_id": cohort_id,
        },
        outputs={"genotyped_vcf": joint_vcf.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return manifest
