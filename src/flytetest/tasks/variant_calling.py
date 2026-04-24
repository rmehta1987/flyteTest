"""GATK4 variant calling task implementations for Milestone A."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import (
    variant_calling_env,
    project_mkdtemp,
    require_path,
    run_tool,
)
from flytetest.manifest_envelope import build_manifest_envelope
from flytetest.manifest_io import write_json as _write_json


# Source of truth for the registry-manifest contract: every key this module
# writes under manifest["outputs"].  Grows as each task lands.
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "sequence_dict",
    "feature_index",
    "bqsr_report",
    "recalibrated_bam",
    "gvcf",
    "combined_gvcf",
    "joint_vcf",
    "bwa_index_prefix",
    "aligned_bam",
    "sorted_bam",
    "dedup_bam",
    "duplicate_metrics",
    # Milestone D
    "recal_file",
    "tranches_file",
    "vqsr_vcf",
    # Milestone E
    "merged_bam",
    # Milestone F
    "gathered_gvcf",
    # Milestone G
    "cgp_vcf",
    # Milestone H — workflow-level outputs for showcased workflows
    "prepared_ref",
    "preprocessed_bam",
    "preprocessed_bam_from_ubam",
    "scattered_gvcf",
    "refined_vcf_cgp",
    "genotyped_vcf",
    "refined_vcf",
    # Milestone I — new tasks (Steps 04–06)
    "filtered_vcf",
    "wgs_metrics",
    "insert_size_metrics",
    "bcftools_stats_txt",
    "multiqc_report_html",
    "snpeff_vcf",
    "snpeff_genes_txt",
    # Milestone I — new workflow outputs (Steps 04–06)
    "small_cohort_filtered_vcf",
    "pre_call_qc_bundle",
    "post_call_qc_bundle",
    "annotated_vcf",
)


@variant_calling_env.task
def create_sequence_dictionary(
    reference_fasta: File,
    gatk_sif: str = "",
) -> File:
    """Emit a GATK sequence dictionary (.dict) next to the reference FASTA."""
    ref_path = require_path(Path(reference_fasta.download_sync()),
                            "Reference genome FASTA")
    out_dir = project_mkdtemp("gatk_seqdict_")
    dict_path = out_dir / f"{ref_path.stem}.dict"

    cmd = ["gatk", "CreateSequenceDictionary",
           "-R", str(ref_path), "-O", str(dict_path)]
    bind_paths = [ref_path.parent, out_dir]
    run_tool(cmd, gatk_sif, bind_paths)

    require_path(dict_path, "GATK CreateSequenceDictionary output")

    manifest = build_manifest_envelope(
        stage="create_sequence_dictionary",
        assumptions=[
            "Reference FASTA is readable and has no pre-existing "
            ".dict that would conflict; GATK overwrites -O when run.",
        ],
        inputs={"reference_fasta": str(ref_path)},
        outputs={"sequence_dict": str(dict_path)},
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return File(path=str(dict_path))


@variant_calling_env.task
def index_feature_file(
    vcf: File,
    gatk_sif: str = "",
) -> File:
    """Emit a GATK4 feature-file index (.idx or .tbi) next to a VCF/GVCF."""
    vcf_path = require_path(Path(vcf.download_sync()),
                            "VCF/GVCF input for IndexFeatureFile")
    out_dir = project_mkdtemp("gatk_index_")

    if vcf_path.suffix == ".gz":
        expected_index = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
    else:
        expected_index = vcf_path.with_suffix(vcf_path.suffix + ".idx")

    cmd = ["gatk", "IndexFeatureFile", "-I", str(vcf_path)]
    bind_paths = [vcf_path.parent, out_dir]
    run_tool(cmd, gatk_sif, bind_paths)

    require_path(expected_index, "GATK IndexFeatureFile output index")

    manifest = build_manifest_envelope(
        stage="index_feature_file",
        assumptions=[
            "VCF is readable; GATK writes the index next to the VCF.",
        ],
        inputs={"vcf": str(vcf_path)},
        outputs={"feature_index": str(expected_index)},
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return File(path=str(expected_index))


@variant_calling_env.task
def base_recalibrator(
    reference_fasta: File,
    aligned_bam: File,
    known_sites: list[File],
    sample_id: str,
    gatk_sif: str = "",
) -> File:
    """Generate a BQSR recalibration table via GATK4 BaseRecalibrator."""
    if not known_sites:
        raise ValueError("known_sites list cannot be empty for BQSR")

    ref_path = require_path(Path(reference_fasta.download_sync()),
                            "Reference genome FASTA")
    bam_path = require_path(Path(aligned_bam.download_sync()),
                            "Aligned BAM")
    site_paths = [
        require_path(Path(s.download_sync()), f"KnownSites VCF #{i}")
        for i, s in enumerate(known_sites)
    ]

    out_dir = project_mkdtemp("gatk_bqsr_report_")
    recal_path = out_dir / f"{sample_id}_bqsr.table"

    cmd = ["gatk", "BaseRecalibrator",
           "-R", str(ref_path),
           "-I", str(bam_path),
           "-O", str(recal_path)]
    for site in site_paths:
        cmd.extend(["--known-sites", str(site)])

    bind_paths = [ref_path.parent, bam_path.parent, out_dir,
                  *[s.parent for s in site_paths]]
    run_tool(cmd, gatk_sif, bind_paths)

    require_path(recal_path, "GATK BaseRecalibrator output table")

    manifest = build_manifest_envelope(
        stage="base_recalibrator",
        assumptions=[
            "Aligned BAM is coordinate-sorted and has duplicates marked (caller responsibility).",
            "All known-sites VCFs are indexed (.idx or .tbi present next to each VCF).",
            "Reference has a .fai and .dict next to the FASTA.",
        ],
        inputs={
            "reference_fasta": str(ref_path),
            "aligned_bam": str(bam_path),
            "known_sites": [str(s) for s in site_paths],
            "sample_id": sample_id,
        },
        outputs={"bqsr_report": str(recal_path)},
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return File(path=str(recal_path))


@variant_calling_env.task
def apply_bqsr(
    reference_fasta: File,
    aligned_bam: File,
    bqsr_report: File,
    sample_id: str,
    gatk_sif: str = "",
) -> File:
    """Apply a BQSR recalibration table to an aligned BAM via GATK4 ApplyBQSR."""
    ref_path = require_path(Path(reference_fasta.download_sync()),
                            "Reference genome FASTA")
    bam_path = require_path(Path(aligned_bam.download_sync()),
                            "Aligned BAM for ApplyBQSR")
    recal_path = require_path(Path(bqsr_report.download_sync()),
                              "BQSR recalibration table")

    out_dir = project_mkdtemp("gatk_apply_bqsr_")
    out_bam = out_dir / f"{sample_id}_recalibrated.bam"

    cmd = ["gatk", "ApplyBQSR",
           "-R", str(ref_path),
           "-I", str(bam_path),
           "--bqsr-recal-file", str(recal_path),
           "-O", str(out_bam)]
    bind_paths = [ref_path.parent, bam_path.parent, recal_path.parent, out_dir]
    run_tool(cmd, gatk_sif, bind_paths)

    require_path(out_bam, "GATK ApplyBQSR output BAM")
    out_bai = out_bam.with_suffix(".bai")  # GATK writes this; may also be .bam.bai
    if not out_bai.exists():
        alt_bai = Path(str(out_bam) + ".bai")
        if alt_bai.exists():
            out_bai = alt_bai

    manifest = build_manifest_envelope(
        stage="apply_bqsr",
        assumptions=[
            "Input BAM is coordinate-sorted and dedup'd (caller responsibility).",
            "BQSR table was generated from this BAM + the same reference + known sites.",
        ],
        inputs={
            "reference_fasta": str(ref_path),
            "aligned_bam": str(bam_path),
            "bqsr_report": str(recal_path),
            "sample_id": sample_id,
        },
        outputs={
            "recalibrated_bam": str(out_bam),
            "recalibrated_bam_index": str(out_bai) if out_bai.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return File(path=str(out_bam))


@variant_calling_env.task
def haplotype_caller(
    reference_fasta: File,
    aligned_bam: File,
    sample_id: str,
    intervals: list[str] | None = None,
    gatk_sif: str = "",
) -> File:
    """Call per-sample germline GVCF via GATK4 HaplotypeCaller in GVCF mode."""
    ref_path = require_path(Path(reference_fasta.download_sync()),
                            "Reference genome FASTA")
    bam_path = require_path(Path(aligned_bam.download_sync()),
                            "Aligned BAM for HaplotypeCaller")

    out_dir = project_mkdtemp("gatk_hc_")
    out_gvcf = out_dir / f"{sample_id}.g.vcf"

    cmd = ["gatk", "HaplotypeCaller",
           "-R", str(ref_path),
           "-I", str(bam_path),
           "-O", str(out_gvcf),
           "--emit-ref-confidence", "GVCF"]
    for interval in (intervals or []):
        cmd.extend(["-L", interval])
    bind_paths = [ref_path.parent, bam_path.parent, out_dir]
    run_tool(cmd, gatk_sif, bind_paths)

    require_path(out_gvcf, "GATK HaplotypeCaller output GVCF")
    out_idx = out_dir / f"{out_gvcf.name}.idx"

    manifest = build_manifest_envelope(
        stage="haplotype_caller",
        assumptions=[
            "Aligned BAM is coordinate-sorted, dedup'd, and (recommended) BQSR-recalibrated.",
            "Reference has a .fai and .dict next to the FASTA.",
            "Intervals scoping is supported via the `intervals` parameter (Milestone F); whole-genome when omitted.",
        ],
        inputs={
            "reference_fasta": str(ref_path),
            "aligned_bam": str(bam_path),
            "sample_id": sample_id,
        },
        outputs={
            "gvcf": str(out_gvcf),
            "gvcf_index": str(out_idx) if out_idx.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return File(path=str(out_gvcf))


@variant_calling_env.task
def joint_call_gvcfs(
    reference_fasta: File,
    gvcfs: list[File],
    sample_ids: list[str],
    intervals: list[str],
    cohort_id: str = "cohort",
    gatk_sif: str = "",
) -> File:
    """GenomicsDBImport + GenotypeGVCFs → joint-called VCF for a cohort."""
    if not gvcfs:
        raise ValueError("gvcfs list cannot be empty")
    if not intervals:
        raise ValueError("intervals list cannot be empty for GenomicsDBImport")
    if len(sample_ids) != len(gvcfs):
        raise ValueError(
            f"sample_ids length ({len(sample_ids)}) must match gvcfs "
            f"length ({len(gvcfs)}); sample_name_map requires a 1:1 mapping."
        )

    ref_path = require_path(Path(reference_fasta.download_sync()),
                            "Reference genome FASTA")
    gvcf_paths = [
        require_path(Path(g.download_sync()), f"Input GVCF #{i}")
        for i, g in enumerate(gvcfs)
    ]

    out_dir = project_mkdtemp("gatk_joint_")
    out_vcf = out_dir / f"{cohort_id}_genotyped.vcf"

    with tempfile.TemporaryDirectory(
        prefix="gatk_genomicsdb_", dir=str(out_dir)
    ) as tmpdir:
        tmp = Path(tmpdir)
        workspace = tmp / f"{cohort_id}_genomicsdb"
        sample_map = tmp / "sample_map.txt"
        sample_map.write_text(
            "\n".join(
                f"{sid}\t{gp}" for sid, gp in zip(sample_ids, gvcf_paths)
            ) + "\n"
        )

        import_cmd = ["gatk", "GenomicsDBImport",
                      "--genomicsdb-workspace-path", str(workspace),
                      "--sample-name-map", str(sample_map)]
        for interval in intervals:
            import_cmd.extend(["-L", interval])

        bind_paths = [ref_path.parent, out_dir, tmp,
                      *[g.parent for g in gvcf_paths]]
        run_tool(import_cmd, gatk_sif, bind_paths)
        require_path(workspace, "GenomicsDBImport workspace")

        genotype_cmd = ["gatk", "GenotypeGVCFs",
                        "-R", str(ref_path),
                        "-V", f"gendb://{workspace}",
                        "-O", str(out_vcf)]
        run_tool(genotype_cmd, gatk_sif, bind_paths)

    require_path(out_vcf, "GATK GenotypeGVCFs output VCF")
    out_idx = out_dir / f"{out_vcf.name}.idx"

    manifest = build_manifest_envelope(
        stage="joint_call_gvcfs",
        assumptions=[
            "All inputs are per-sample GVCFs from HaplotypeCaller against the same reference.",
            "Intervals cover the genomic region of interest; GenomicsDBImport requires ≥1 interval.",
            "GenomicsDB workspace is ephemeral (tempdir); the workspace does not leave this task.",
        ],
        inputs={
            "reference_fasta": str(ref_path),
            "gvcfs": [str(g) for g in gvcf_paths],
            "sample_ids": list(sample_ids),
            "intervals": list(intervals),
            "cohort_id": cohort_id,
        },
        outputs={
            "joint_vcf": str(out_vcf),
            "joint_vcf_index": str(out_idx) if out_idx.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return File(path=str(out_vcf))


@variant_calling_env.task
def combine_gvcfs(
    reference_fasta: File,
    gvcfs: list[File],
    cohort_id: str = "cohort",
    gatk_sif: str = "",
) -> File:
    """Combine per-sample GVCFs into a cohort GVCF via GATK4 CombineGVCFs."""
    if not gvcfs:
        raise ValueError("gvcfs list cannot be empty")

    ref_path = require_path(Path(reference_fasta.download_sync()),
                            "Reference genome FASTA")
    gvcf_paths = [
        require_path(Path(g.download_sync()), f"Input GVCF #{i}")
        for i, g in enumerate(gvcfs)
    ]

    out_dir = project_mkdtemp("gatk_combine_")
    out_gvcf = out_dir / f"{cohort_id}_combined.g.vcf"

    cmd = ["gatk", "CombineGVCFs",
           "-R", str(ref_path),
           "-O", str(out_gvcf)]
    for gp in gvcf_paths:
        cmd.extend(["-V", str(gp)])

    bind_paths = [ref_path.parent, out_dir, *[g.parent for g in gvcf_paths]]
    run_tool(cmd, gatk_sif, bind_paths)

    require_path(out_gvcf, "GATK CombineGVCFs output GVCF")
    out_idx = out_dir / f"{out_gvcf.name}.idx"

    manifest = build_manifest_envelope(
        stage="combine_gvcfs",
        assumptions=[
            "Every input is a per-sample GVCF emitted with --emit-ref-confidence GVCF.",
            "All inputs call against the same reference build as the one supplied here.",
        ],
        inputs={
            "reference_fasta": str(ref_path),
            "gvcfs": [str(g) for g in gvcf_paths],
            "cohort_id": cohort_id,
        },
        outputs={
            "combined_gvcf": str(out_gvcf),
            "combined_gvcf_index": str(out_idx) if out_idx.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return File(path=str(out_gvcf))


@variant_calling_env.task
def bwa_mem2_index(
    reference_fasta: File,
    bwa_sif: str = "",
) -> Dir:
    """Index a reference FASTA for BWA-MEM2 alignment."""
    ref = require_path(Path(reference_fasta.download_sync()), "Reference FASTA")
    out_dir = project_mkdtemp("bwa_mem2_index_")
    index_prefix = out_dir / ref.stem

    cmd = ["bwa-mem2", "index", "-p", str(index_prefix), str(ref)]
    run_tool(cmd, bwa_sif, [ref.parent, out_dir])

    for suffix in (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"):
        if not Path(f"{index_prefix}{suffix}").exists():
            raise FileNotFoundError(f"bwa-mem2 index missing: {index_prefix}{suffix}")

    manifest = build_manifest_envelope(
        stage="bwa_mem2_index",
        assumptions=["Reference FASTA readable; no pre-existing conflicting index files."],
        inputs={"reference_fasta": str(ref)},
        outputs={"bwa_index_prefix": str(index_prefix)},
    )
    _write_json(out_dir / "run_manifest_bwa_mem2_index.json", manifest)
    return Dir(path=str(out_dir))


@variant_calling_env.task
def bwa_mem2_mem(
    reference_fasta: File,
    r1: File,
    sample_id: str,
    r2: File | None = None,
    threads: int = 4,
    library_id: str | None = None,
    platform: str = "ILLUMINA",
    bwa_sif: str = "",
) -> File:
    """Align paired-end FASTQ reads to a reference using BWA-MEM2."""
    ref = require_path(Path(reference_fasta.download_sync()), "Reference FASTA")
    r1_path = require_path(Path(r1.download_sync()), "R1 FASTQ")
    r2_path = require_path(Path(r2.download_sync()), "R2 FASTQ") if r2 is not None else None
    lib = library_id or f"{sample_id}_lib"

    out_dir = project_mkdtemp("bwa_mem2_mem_")
    out_bam = out_dir / f"{sample_id}_aligned.bam"

    rg = f"@RG\\tID:{sample_id}\\tSM:{sample_id}\\tLB:{lib}\\tPL:{platform}"
    pipeline = (
        f"bwa-mem2 mem -R {shlex.quote(rg)} -t {threads} "
        f"{shlex.quote(str(ref))} {shlex.quote(str(r1_path))}"
        + (f" {shlex.quote(str(r2_path))}" if r2_path is not None else "")
        + f" | samtools view -bS -o {shlex.quote(str(out_bam))} -"
    )

    bind_paths = [ref.parent, r1_path.parent, out_dir]
    if r2_path is not None:
        bind_paths.append(r2_path.parent)
    run_tool(["bash", "-c", pipeline], bwa_sif, bind_paths)

    if not out_bam.exists():
        raise FileNotFoundError(f"bwa_mem2_mem produced no BAM: {out_bam}")

    manifest = build_manifest_envelope(
        stage="bwa_mem2_mem",
        assumptions=[
            "Reference is indexed (bwa_mem2_index must have run first).",
            "R1 (and R2 if provided) are readable FASTQ files.",
        ],
        inputs={
            "reference_fasta": str(ref),
            "r1": str(r1_path),
            "r2": str(r2_path) if r2_path is not None else "",
            "sample_id": sample_id,
            "library_id": lib,
            "platform": platform,
            "threads": threads,
        },
        outputs={"aligned_bam": str(out_bam)},
    )
    _write_json(out_dir / "run_manifest_bwa_mem2_mem.json", manifest)
    return File(path=str(out_bam))


@variant_calling_env.task
def sort_sam(
    aligned_bam: File,
    sample_id: str,
    gatk_sif: str = "",
) -> File:
    """Coordinate-sort a BAM file using GATK SortSam."""
    in_bam = require_path(Path(aligned_bam.download_sync()), "Input BAM for SortSam")
    out_dir = project_mkdtemp("gatk_sort_sam_")
    out_bam = out_dir / f"{sample_id}_sorted.bam"

    cmd = [
        "gatk", "SortSam",
        "-I", str(in_bam),
        "-O", str(out_bam),
        "--SORT_ORDER", "coordinate",
        "--CREATE_INDEX", "true",
    ]
    run_tool(cmd, gatk_sif, [in_bam.parent, out_dir])

    require_path(out_bam, "GATK SortSam output BAM")
    out_bai = out_bam.with_suffix(".bai")
    if not out_bai.exists():
        alt_bai = Path(str(out_bam) + ".bai")
        if alt_bai.exists():
            out_bai = alt_bai

    manifest = build_manifest_envelope(
        stage="sort_sam",
        assumptions=[
            "Input BAM is an unsorted aligned BAM produced by bwa_mem2_mem.",
            "--CREATE_INDEX true writes the index alongside the sorted BAM.",
        ],
        inputs={"aligned_bam": str(in_bam), "sample_id": sample_id},
        outputs={
            "sorted_bam": str(out_bam),
            "sorted_bam_index": str(out_bai) if out_bai.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_sort_sam.json", manifest)
    return File(path=str(out_bam))


@variant_calling_env.task
def mark_duplicates(
    sorted_bam: File,
    sample_id: str,
    gatk_sif: str = "",
) -> tuple[File, File]:
    """Mark PCR/optical duplicates; returns (dedup_bam, metrics_file)."""
    in_bam = require_path(Path(sorted_bam.download_sync()), "Coordinate-sorted BAM for MarkDuplicates")
    out_dir = project_mkdtemp("gatk_mark_dup_")

    out_bam = out_dir / f"{sample_id}_marked_duplicates.bam"
    metrics = out_dir / f"{sample_id}_duplicate_metrics.txt"

    cmd = [
        "gatk", "MarkDuplicates",
        "-I", str(in_bam),
        "-O", str(out_bam),
        "-M", str(metrics),
        "--CREATE_INDEX", "true",
    ]
    run_tool(cmd, gatk_sif, [in_bam.parent, out_dir])

    require_path(out_bam, "GATK MarkDuplicates output BAM")
    require_path(metrics, "GATK MarkDuplicates metrics file")

    out_bai = out_bam.with_suffix(".bai")
    if not out_bai.exists():
        alt_bai = Path(str(out_bam) + ".bai")
        if alt_bai.exists():
            out_bai = alt_bai

    manifest = build_manifest_envelope(
        stage="mark_duplicates",
        assumptions=[
            "Input BAM is coordinate-sorted (sort_sam must have run first).",
            "--CREATE_INDEX true writes the BAI alongside the output BAM.",
        ],
        inputs={"sorted_bam": str(in_bam), "sample_id": sample_id},
        outputs={
            "dedup_bam": str(out_bam),
            "duplicate_metrics": str(metrics),
            "dedup_bam_index": str(out_bai) if out_bai.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_mark_duplicates.json", manifest)
    return File(path=str(out_bam)), File(path=str(metrics))


_DEFAULT_VQSR_FILTER_LEVEL: dict[str, float] = {"SNP": 99.5, "INDEL": 99.0}
_DEFAULT_SNP_ANNOTATIONS = ("QD", "MQ", "MQRankSum", "ReadPosRankSum", "FS", "SOR")
_DEFAULT_INDEL_ANNOTATIONS = ("QD", "FS", "SOR")
_INBREEDING_COEFF_MIN_SAMPLES = 10


def _resolve_vqsr_annotations(
    mode: str,
    sample_count: int,
    annotations: list[str] | None,
) -> list[str]:
    """Return the effective -an list for VariantRecalibrator."""
    if annotations is not None:
        return list(annotations)
    if mode == "SNP":
        base = list(_DEFAULT_SNP_ANNOTATIONS)
    elif mode == "INDEL":
        base = list(_DEFAULT_INDEL_ANNOTATIONS)
    else:
        raise ValueError(f"mode must be 'SNP' or 'INDEL', got {mode!r}")
    if mode == "SNP" and sample_count >= _INBREEDING_COEFF_MIN_SAMPLES:
        if "InbreedingCoeff" not in base:
            base.append("InbreedingCoeff")
    return base


@variant_calling_env.task
def variant_recalibrator(
    reference_fasta: File,
    cohort_vcf: File,
    known_sites: list[File],
    known_sites_flags: list[dict],
    mode: str,
    cohort_id: str,
    sample_count: int,
    annotations: list[str] | None = None,
    gatk_sif: str = "",
) -> tuple[File, File]:
    """Build a VQSR recalibration model; returns (recal_file, tranches_file).

    ``known_sites`` and ``known_sites_flags`` are parallel lists — each entry
    in ``known_sites_flags`` must carry keys ``resource_name``, ``known``,
    ``training``, ``truth``, and ``prior`` (all strings).
    InbreedingCoeff is auto-added to SNP-mode annotations when sample_count >= 10
    (GATK Best Practices).
    """
    if mode not in ("SNP", "INDEL"):
        raise ValueError(f"mode must be 'SNP' or 'INDEL', got {mode!r}")
    if not known_sites:
        raise ValueError(f"known_sites cannot be empty for mode={mode!r}")
    if len(known_sites) != len(known_sites_flags):
        raise ValueError(
            f"known_sites ({len(known_sites)}) and known_sites_flags "
            f"({len(known_sites_flags)}) must have the same length"
        )

    ref = require_path(Path(reference_fasta.download_sync()), "Reference genome FASTA")
    vcf = require_path(Path(cohort_vcf.download_sync()), "Input VCF for VariantRecalibrator")
    site_paths = [
        require_path(Path(s.download_sync()), f"KnownSites VCF #{i}")
        for i, s in enumerate(known_sites)
    ]

    out_dir = project_mkdtemp("gatk_vqsr_")
    output_recal = out_dir / f"{cohort_id}_{mode.lower()}.recal"
    output_tranches = out_dir / f"{cohort_id}_{mode.lower()}.tranches"

    effective = _resolve_vqsr_annotations(mode, sample_count, annotations)

    cmd = [
        "gatk", "VariantRecalibrator",
        "-R", str(ref),
        "-V", str(vcf),
        "-mode", mode,
        "-O", str(output_recal),
        "--tranches-file", str(output_tranches),
    ]
    for site, flags in zip(site_paths, known_sites_flags):
        name = flags.get("resource_name", "unknown")
        known_flag = flags.get("known", "false")
        training = flags.get("training", "false")
        truth = flags.get("truth", "false")
        prior = flags.get("prior", "10")
        cmd.extend([
            f"--resource:{name},known={known_flag},training={training},truth={truth},prior={prior}",
            str(site),
        ])
    for ann in effective:
        cmd.extend(["-an", ann])

    bind_paths = [ref.parent, vcf.parent, out_dir, *[s.parent for s in site_paths]]
    run_tool(cmd, gatk_sif, bind_paths)

    if not output_recal.exists():
        raise FileNotFoundError(
            f"VariantRecalibrator did not produce recal file: {output_recal}"
        )

    manifest = build_manifest_envelope(
        stage="variant_recalibrator",
        assumptions=[
            "InbreedingCoeff is auto-added to SNP-mode annotations when sample_count >= 10 (GATK Best Practices).",
            "Override via the `annotations` parameter when non-default sets are needed.",
            "Input VCF is a joint-called cohort VCF with sufficient variant count "
            "(≥30k SNPs for SNP mode; ≥2k indels for INDEL mode).",
            "All known-sites VCFs are indexed (.tbi or .idx present next to each VCF).",
            "Reference has .fai and .dict next to the FASTA.",
        ],
        inputs={
            "reference_fasta": str(ref),
            "cohort_vcf": str(vcf),
            "mode": mode,
            "cohort_id": cohort_id,
            "sample_count": sample_count,
            "effective_annotations": effective,
        },
        outputs={
            "recal_file": str(output_recal),
            "tranches_file": str(output_tranches),
        },
    )
    _write_json(out_dir / "run_manifest_variant_recalibrator.json", manifest)
    return File(path=str(output_recal)), File(path=str(output_tranches))


@variant_calling_env.task
def apply_vqsr(
    reference_fasta: File,
    input_vcf: File,
    recal_file: File,
    tranches_file: File,
    mode: str,
    cohort_id: str,
    truth_sensitivity_filter_level: float = 0.0,
    gatk_sif: str = "",
) -> File:
    """Apply a VQSR recalibration model to a VCF via ApplyVQSR.

    ``truth_sensitivity_filter_level`` defaults to 99.5 for SNP and 99.0 for
    INDEL when passed as 0.0.  ``recal_file`` and ``tranches_file`` must come
    from ``variant_recalibrator`` run with the same ``mode``.
    """
    if mode not in ("SNP", "INDEL"):
        raise ValueError(f"mode must be 'SNP' or 'INDEL', got {mode!r}")

    ref = require_path(Path(reference_fasta.download_sync()), "Reference genome FASTA")
    vcf = require_path(Path(input_vcf.download_sync()), "Input VCF for ApplyVQSR")
    recal = require_path(Path(recal_file.download_sync()), "VQSR recalibration file")
    tranches = require_path(Path(tranches_file.download_sync()), "VQSR tranches file")

    filter_level = (
        truth_sensitivity_filter_level
        if truth_sensitivity_filter_level != 0.0
        else _DEFAULT_VQSR_FILTER_LEVEL[mode]
    )

    out_dir = project_mkdtemp("gatk_apply_vqsr_")
    output_vcf = out_dir / f"{cohort_id}_vqsr_{mode.lower()}.vcf.gz"
    tbi_path = Path(str(output_vcf) + ".tbi")

    cmd = [
        "gatk", "ApplyVQSR",
        "-R", str(ref),
        "-V", str(vcf),
        "--recal-file", str(recal),
        "--tranches-file", str(tranches),
        "--truth-sensitivity-filter-level", str(filter_level),
        "--create-output-variant-index", "true",
        "-mode", mode,
        "-O", str(output_vcf),
    ]

    bind_paths = [ref.parent, vcf.parent, recal.parent, tranches.parent, out_dir]
    run_tool(cmd, gatk_sif, bind_paths)

    if not output_vcf.exists():
        raise FileNotFoundError(f"ApplyVQSR did not produce output VCF: {output_vcf}")

    manifest = build_manifest_envelope(
        stage="apply_vqsr",
        assumptions=[
            "recal_file and tranches_file were produced by variant_recalibrator "
            "for the same mode and the same VCF.",
            "--create-output-variant-index true writes a .vcf.gz.tbi companion automatically.",
        ],
        inputs={
            "reference_fasta": str(ref),
            "input_vcf": str(vcf),
            "recal_file": str(recal),
            "tranches_file": str(tranches),
            "mode": mode,
            "cohort_id": cohort_id,
            "truth_sensitivity_filter_level": filter_level,
        },
        outputs={
            "vqsr_vcf": str(output_vcf),
            "vqsr_vcf_index": str(tbi_path) if tbi_path.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_apply_vqsr.json", manifest)
    return File(path=str(output_vcf))


@variant_calling_env.task
def merge_bam_alignment(
    reference_fasta: File,
    aligned_bam: File,
    ubam: File,
    sample_id: str,
    gatk_sif: str = "",
) -> File:
    """Merge aligned BAM with unmapped BAM via GATK4 MergeBamAlignment.

    ``ubam`` must be queryname-sorted.  ``--SORT_ORDER coordinate``
    produces a coordinate-sorted merged BAM so no separate sort_sam step
    is needed.
    """
    ref = require_path(Path(reference_fasta.download_sync()), "Reference genome FASTA")
    aln = require_path(Path(aligned_bam.download_sync()), "Aligned BAM for MergeBamAlignment")
    ubam_path = require_path(Path(ubam.download_sync()), "Unmapped BAM for MergeBamAlignment")

    out_dir = project_mkdtemp("gatk_merge_bam_")
    out_bam = out_dir / f"{sample_id}_merged.bam"

    cmd = [
        "gatk", "MergeBamAlignment",
        "-R", str(ref),
        "-ALIGNED", str(aln),
        "-UNMAPPED", str(ubam_path),
        "-O", str(out_bam),
        "--SORT_ORDER", "coordinate",
        "--ADD_MATE_CIGAR", "true",
        "--CLIP_ADAPTERS", "false",
        "--CLIP_OVERLAPPING_READS", "true",
        "--INCLUDE_SECONDARY_ALIGNMENTS", "true",
        "--MAX_INSERTIONS_OR_DELETIONS", "-1",
        "--PRIMARY_ALIGNMENT_STRATEGY", "MostDistant",
        "--ATTRIBUTES_TO_RETAIN", "X0",
        "--CREATE_INDEX", "true",
    ]

    bind_paths = [ref.parent, aln.parent, ubam_path.parent, out_dir]
    run_tool(cmd, gatk_sif, bind_paths)

    if not out_bam.exists():
        raise FileNotFoundError(f"MergeBamAlignment did not produce output BAM: {out_bam}")

    out_bai = out_bam.with_suffix(".bai")
    if not out_bai.exists():
        alt_bai = Path(str(out_bam) + ".bai")
        if alt_bai.exists():
            out_bai = alt_bai

    manifest = build_manifest_envelope(
        stage="merge_bam_alignment",
        assumptions=[
            "ubam is queryname-sorted (GATK requirement).",
            "--SORT_ORDER coordinate eliminates the need for sort_sam.",
            "--CREATE_INDEX true writes a .bai companion alongside the BAM.",
        ],
        inputs={
            "reference_fasta": str(ref),
            "aligned_bam": str(aln),
            "ubam": str(ubam_path),
            "sample_id": sample_id,
        },
        outputs={
            "merged_bam": str(out_bam),
            "merged_bam_index": str(out_bai) if out_bai.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_merge_bam_alignment.json", manifest)
    return File(path=str(out_bam))


@variant_calling_env.task
def gather_vcfs(
    gvcfs: list[File],
    sample_id: str,
    gatk_sif: str = "",
) -> File:
    """Merge ordered per-interval GVCFs into a single GVCF via GatherVcfs."""
    if not gvcfs:
        raise ValueError("gvcfs must not be empty")

    gvcf_paths = [
        require_path(Path(g.download_sync()), f"Input GVCF #{i}")
        for i, g in enumerate(gvcfs)
    ]

    out_dir = project_mkdtemp("gatk_gather_vcfs_")
    out_vcf = out_dir / f"{sample_id}_gathered.g.vcf.gz"

    cmd = ["gatk", "GatherVcfs"]
    for gp in gvcf_paths:
        cmd.extend(["-I", str(gp)])
    cmd.extend(["-O", str(out_vcf), "--CREATE_INDEX", "true"])

    bind_paths = [gp.parent for gp in gvcf_paths] + [out_dir]
    run_tool(cmd, gatk_sif, bind_paths)

    if not out_vcf.exists():
        raise FileNotFoundError(f"GatherVcfs did not produce output GVCF: {out_vcf}")

    manifest = build_manifest_envelope(
        stage="gather_vcfs",
        assumptions=[
            "gvcfs must be in genomic interval order; GatherVcfs requires non-overlapping inputs.",
            "All input GVCFs must be indexed (.tbi or .idx next to each file).",
            "--CREATE_INDEX true writes a .tbi companion alongside the output GVCF.",
        ],
        inputs={"gvcfs": [str(gp) for gp in gvcf_paths], "sample_id": sample_id},
        outputs={"gathered_gvcf": str(out_vcf)},
    )
    _write_json(out_dir / "run_manifest_gather_vcfs.json", manifest)
    return File(path=str(out_vcf))


@variant_calling_env.task
def calculate_genotype_posteriors(
    input_vcf: File,
    cohort_id: str,
    supporting_callsets: list[File] | None = None,
    gatk_sif: str = "",
) -> File:
    """Refine genotype posteriors via GATK4 CalculateGenotypePosteriors."""
    vcf = require_path(Path(input_vcf.download_sync()), "Input VCF for CalculateGenotypePosteriors")
    callset_paths = [
        require_path(Path(cs.download_sync()), f"Supporting callset #{i}")
        for i, cs in enumerate(supporting_callsets or [])
    ]

    out_dir = project_mkdtemp("gatk_cgp_")
    out_vcf = out_dir / f"{cohort_id}_cgp.vcf.gz"

    cmd = [
        "gatk", "CalculateGenotypePosteriors",
        "-V", str(vcf),
        "-O", str(out_vcf),
        "--create-output-variant-index", "true",
    ]
    for csp in callset_paths:
        cmd.extend(["--supporting-callsets", str(csp)])

    bind_paths = [vcf.parent, out_dir, *[csp.parent for csp in callset_paths]]
    run_tool(cmd, gatk_sif, bind_paths)

    if not out_vcf.exists():
        raise FileNotFoundError(
            f"CalculateGenotypePosteriors did not produce output VCF: {out_vcf}"
        )

    tbi = Path(str(out_vcf) + ".tbi")

    manifest = build_manifest_envelope(
        stage="calculate_genotype_posteriors",
        assumptions=[
            "Input VCF should be joint-called (joint_call_gvcfs) or VQSR-filtered (genotype_refinement).",
            "supporting_callsets VCFs must be indexed (.tbi or .idx present).",
            "No -R flag; CalculateGenotypePosteriors does not require a reference FASTA.",
        ],
        inputs={
            "input_vcf": str(vcf),
            "cohort_id": cohort_id,
            "supporting_callsets": [str(csp) for csp in callset_paths],
        },
        outputs={
            "cgp_vcf": str(out_vcf),
            "cgp_vcf_index": str(tbi) if tbi.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_calculate_genotype_posteriors.json", manifest)
    return File(path=str(out_vcf))


# ---------------------------------------------------------------------------
# Step 04 — Hard-filtering fallback
# ---------------------------------------------------------------------------

# GATK Best Practices hard-filtering defaults.
# Source: https://gatk.broadinstitute.org/hc/en-us/articles/360035531112
_DEFAULT_SNP_FILTER_EXPRESSIONS: tuple[tuple[str, str], ...] = (
    ("QD2", "QD < 2.0"),
    ("FS60", "FS > 60.0"),
    ("MQ40", "MQ < 40.0"),
    ("MQRankSum-12.5", "MQRankSum < -12.5"),
    ("ReadPosRankSum-8", "ReadPosRankSum < -8.0"),
    ("SOR3", "SOR > 3.0"),
)
_DEFAULT_INDEL_FILTER_EXPRESSIONS: tuple[tuple[str, str], ...] = (
    ("QD2", "QD < 2.0"),
    ("FS200", "FS > 200.0"),
    ("ReadPosRankSum-20", "ReadPosRankSum < -20.0"),
    ("SOR10", "SOR > 10.0"),
)


@variant_calling_env.task
def variant_filtration(
    reference_fasta: File,
    input_vcf: File,
    mode: str,
    cohort_id: str,
    filter_expressions: list[tuple[str, str]] | None = None,
    gatk_sif: str = "",
) -> File:
    """Apply GATK VariantFiltration with Best Practices defaults.

    ``mode``: 'SNP' or 'INDEL' — selects default filter expressions when
    ``filter_expressions`` is None.
    ``filter_expressions``: parallel list of (filter_name, expression)
    tuples. Overrides defaults when provided.
    Source: https://gatk.broadinstitute.org/hc/en-us/articles/360035531112
    """
    if mode not in ("SNP", "INDEL"):
        raise ValueError(f"mode must be 'SNP' or 'INDEL', got {mode!r}")

    effective = list(filter_expressions) if filter_expressions is not None else (
        list(_DEFAULT_SNP_FILTER_EXPRESSIONS) if mode == "SNP"
        else list(_DEFAULT_INDEL_FILTER_EXPRESSIONS)
    )

    ref = require_path(Path(reference_fasta.download_sync()), "Reference FASTA")
    vcf = require_path(Path(input_vcf.download_sync()), f"VCF for {mode} filtration")

    out_dir = project_mkdtemp(f"gatk_filt_{mode.lower()}_")
    out_vcf = out_dir / f"{cohort_id}_{mode.lower()}_filtered.vcf.gz"

    cmd = ["gatk", "VariantFiltration",
           "-R", str(ref),
           "-V", str(vcf),
           "-O", str(out_vcf)]
    for name, expression in effective:
        cmd.extend(["--filter-name", name, "--filter-expression", expression])

    run_tool(cmd, gatk_sif,
             [ref.parent, vcf.parent, out_dir])

    require_path(out_vcf, "VariantFiltration output VCF")
    tbi = Path(str(out_vcf) + ".tbi")

    manifest = build_manifest_envelope(
        stage="variant_filtration",
        assumptions=[
            "Filter expressions default to GATK Best Practices hard-filtering thresholds.",
            "Input VCF should be joint-called; filtration marks records rather than removing them.",
            "--create-output-variant-index is implied by .vcf.gz output.",
        ],
        inputs={
            "reference_fasta": str(ref),
            "input_vcf": str(vcf),
            "mode": mode,
            "cohort_id": cohort_id,
            "effective_filter_expressions": effective,
        },
        outputs={
            "filtered_vcf": str(out_vcf),
            "filtered_vcf_index": str(tbi) if tbi.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_variant_filtration.json", manifest)
    return File(path=str(out_vcf))


# ---------------------------------------------------------------------------
# Step 05 — QC bookends
# ---------------------------------------------------------------------------

@variant_calling_env.task
def collect_wgs_metrics(
    reference_fasta: File,
    aligned_bam: File,
    sample_id: str,
    gatk_sif: str = "",
) -> tuple[File, File]:
    """Picard CollectWgsMetrics + CollectInsertSizeMetrics on one BAM.

    Returns (wgs_metrics_txt, insert_size_metrics_txt).
    """
    ref = require_path(Path(reference_fasta.download_sync()), "Reference FASTA")
    bam = require_path(Path(aligned_bam.download_sync()), "Aligned BAM")

    out_dir = project_mkdtemp("picard_wgs_")
    wgs_out = out_dir / f"{sample_id}_wgs_metrics.txt"
    insert_out = out_dir / f"{sample_id}_insert_size_metrics.txt"
    insert_hist = out_dir / f"{sample_id}_insert_size_histogram.pdf"

    run_tool(
        ["gatk", "CollectWgsMetrics",
         "-R", str(ref), "-I", str(bam), "-O", str(wgs_out)],
        gatk_sif,
        [ref.parent, bam.parent, out_dir],
    )
    run_tool(
        ["gatk", "CollectInsertSizeMetrics",
         "-I", str(bam), "-O", str(insert_out), "-H", str(insert_hist)],
        gatk_sif,
        [bam.parent, out_dir],
    )

    require_path(wgs_out, "WGS metrics output")
    require_path(insert_out, "Insert size metrics output")

    manifest = build_manifest_envelope(
        stage="collect_wgs_metrics",
        assumptions=[
            "Input BAM must be coordinate-sorted and indexed.",
            "Reference has .fai and .dict present.",
            "Both Picard tools are bundled in the GATK4 SIF.",
        ],
        inputs={"reference_fasta": str(ref), "aligned_bam": str(bam), "sample_id": sample_id},
        outputs={"wgs_metrics": str(wgs_out), "insert_size_metrics": str(insert_out)},
    )
    _write_json(out_dir / "run_manifest_collect_wgs_metrics.json", manifest)
    return File(path=str(wgs_out)), File(path=str(insert_out))


@variant_calling_env.task
def bcftools_stats(
    input_vcf: File,
    cohort_id: str,
    bcftools_sif: str = "",
) -> File:
    """Run bcftools stats on a VCF/GVCF; return the stats text file."""
    vcf = require_path(Path(input_vcf.download_sync()), "Input VCF")
    out_dir = project_mkdtemp("bcftools_stats_")
    out_txt = out_dir / f"{cohort_id}_bcftools_stats.txt"

    # bcftools stats writes to stdout; redirect via bash -c.
    cmd_str = f"bcftools stats {shlex.quote(str(vcf))} > {shlex.quote(str(out_txt))}"
    run_tool(["bash", "-c", cmd_str], bcftools_sif, [vcf.parent, out_dir])

    require_path(out_txt, "bcftools stats output")

    manifest = build_manifest_envelope(
        stage="bcftools_stats",
        assumptions=[
            "Input VCF must be valid; malformed records cause non-zero exit.",
            "Output is plain text; MultiQC parses the standard format.",
        ],
        inputs={"input_vcf": str(vcf), "cohort_id": cohort_id},
        outputs={"bcftools_stats_txt": str(out_txt)},
    )
    _write_json(out_dir / "run_manifest_bcftools_stats.json", manifest)
    return File(path=str(out_txt))


@variant_calling_env.task
def multiqc_summarize(
    qc_inputs: list[File],
    cohort_id: str,
    multiqc_sif: str = "",
) -> File:
    """Aggregate one or more QC tool outputs into a single MultiQC HTML report.

    Copies each input into a fresh scan directory before running MultiQC so
    the report is self-contained and deterministic regardless of original
    file locations.
    """
    if not qc_inputs:
        raise ValueError("qc_inputs must not be empty")

    out_dir = project_mkdtemp("multiqc_")
    scan_root = out_dir / "scan"
    scan_root.mkdir()
    for qc_file in qc_inputs:
        src = require_path(Path(qc_file.download_sync()), "MultiQC input")
        shutil.copy2(src, scan_root / src.name)

    report_html = out_dir / f"{cohort_id}_multiqc.html"
    run_tool(
        ["multiqc", str(scan_root), "-n", report_html.name, "-o", str(out_dir)],
        multiqc_sif,
        [scan_root, out_dir],
    )
    require_path(report_html, "MultiQC HTML report")

    manifest = build_manifest_envelope(
        stage="multiqc_summarize",
        assumptions=[
            "MultiQC auto-detects Picard, bcftools, FastQC, and GATK MarkDuplicates outputs by filename patterns.",
            "Scan root is populated deterministically by copying inputs; no reliance on caller directory layouts.",
        ],
        inputs={"qc_input_count": len(qc_inputs), "cohort_id": cohort_id},
        outputs={"multiqc_report_html": str(report_html)},
    )
    _write_json(out_dir / "run_manifest_multiqc_summarize.json", manifest)
    return File(path=str(report_html))


# ---------------------------------------------------------------------------
# Step 06 — Variant annotation (SnpEff)
# ---------------------------------------------------------------------------

@variant_calling_env.task
def snpeff_annotate(
    input_vcf: File,
    cohort_id: str,
    snpeff_database: str,
    snpeff_data_dir: str,
    snpeff_sif: str = "",
) -> tuple[File, File]:
    """Annotate a VCF with SnpEff; return (annotated_vcf, genes_summary_txt).

    snpeff_database: database identifier (e.g. "GRCh38.105", "hg38").
    snpeff_data_dir: directory containing the pre-downloaded database
        cache. Must be staged on shared FS for Slurm runs (see
        check_offline_staging).
    """
    vcf = require_path(Path(input_vcf.download_sync()), "Input VCF")
    data_dir = require_path(Path(snpeff_data_dir), "SnpEff data directory")

    out_dir = project_mkdtemp("snpeff_")
    annotated_vcf = out_dir / f"{cohort_id}_snpeff.vcf"
    stats_html = out_dir / f"{cohort_id}_snpeff_summary.html"
    genes_txt = out_dir / f"{cohort_id}_snpeff_summary.genes.txt"

    # snpEff writes to stdout; shell redirect is standard.
    cmd_str = (
        f"snpEff ann "
        f"-dataDir {shlex.quote(str(data_dir))} "
        f"-stats {shlex.quote(str(stats_html))} "
        f"{shlex.quote(snpeff_database)} "
        f"{shlex.quote(str(vcf))} "
        f"> {shlex.quote(str(annotated_vcf))}"
    )
    run_tool(
        ["bash", "-c", cmd_str],
        snpeff_sif,
        [vcf.parent, data_dir, out_dir],
    )

    require_path(annotated_vcf, "SnpEff annotated VCF")
    genes_path_str = str(genes_txt) if genes_txt.exists() else ""

    manifest = build_manifest_envelope(
        stage="snpeff_annotate",
        assumptions=[
            "snpeff_data_dir contains the pre-downloaded database for snpeff_database.",
            "SnpEff writes annotation fields into INFO; original VCF records are preserved.",
            "Database cache is NOT downloaded at runtime; compute nodes typically have no internet.",
        ],
        inputs={
            "input_vcf": str(vcf),
            "cohort_id": cohort_id,
            "snpeff_database": snpeff_database,
            "snpeff_data_dir": str(data_dir),
        },
        outputs={
            "snpeff_vcf": str(annotated_vcf),
            "snpeff_genes_txt": genes_path_str,
            "snpeff_summary_html": str(stats_html) if stats_html.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_snpeff_annotate.json", manifest)
    return File(path=str(annotated_vcf)), File(path=str(genes_txt))
