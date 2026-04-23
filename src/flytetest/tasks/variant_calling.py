"""GATK4 variant calling task implementations for Milestone A."""

from __future__ import annotations

import tempfile
from pathlib import Path

from flyte.io import File

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
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

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
    _write_json(out_dir / "run_manifest.json", manifest)
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
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

    require_path(expected_index, "GATK IndexFeatureFile output index")

    manifest = build_manifest_envelope(
        stage="index_feature_file",
        assumptions=[
            "VCF is readable; GATK writes the index next to the VCF.",
        ],
        inputs={"vcf": str(vcf_path)},
        outputs={"feature_index": str(expected_index)},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
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
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

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
    _write_json(out_dir / "run_manifest.json", manifest)
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
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

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
    _write_json(out_dir / "run_manifest.json", manifest)
    return File(path=str(out_bam))


@variant_calling_env.task
def haplotype_caller(
    reference_fasta: File,
    aligned_bam: File,
    sample_id: str,
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
    bind_paths = [ref_path.parent, bam_path.parent, out_dir]
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

    require_path(out_gvcf, "GATK HaplotypeCaller output GVCF")
    out_idx = out_dir / f"{out_gvcf.name}.idx"

    manifest = build_manifest_envelope(
        stage="haplotype_caller",
        assumptions=[
            "Aligned BAM is coordinate-sorted, dedup'd, and (recommended) BQSR-recalibrated.",
            "Reference has a .fai and .dict next to the FASTA.",
            "Whole-genome pass; intervals-scoped calling is out of scope for Milestone A.",
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
    _write_json(out_dir / "run_manifest.json", manifest)
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
        run_tool(import_cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)
        require_path(workspace, "GenomicsDBImport workspace")

        genotype_cmd = ["gatk", "GenotypeGVCFs",
                        "-R", str(ref_path),
                        "-V", f"gendb://{workspace}",
                        "-O", str(out_vcf)]
        run_tool(genotype_cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

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
    _write_json(out_dir / "run_manifest.json", manifest)
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
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

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
    _write_json(out_dir / "run_manifest.json", manifest)
    return File(path=str(out_gvcf))


def bwa_mem2_index(
    ref_path: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Index a reference FASTA for BWA-MEM2 alignment."""
    ref = require_path(Path(ref_path), "Reference genome FASTA")
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    index_prefix = out_dir / ref.stem

    cmd = ["bwa-mem2", "index", "-p", str(index_prefix), str(ref)]
    bind_paths = [ref.parent, out_dir]
    run_tool(cmd, sif_path or "data/images/gatk4.sif", bind_paths)

    expected_suffixes = (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac")
    for suffix in expected_suffixes:
        index_file = Path(str(index_prefix) + suffix)
        if not index_file.exists():
            raise FileNotFoundError(
                f"bwa-mem2 index missing expected file: {index_file}"
            )

    manifest = build_manifest_envelope(
        stage="bwa_mem2_index",
        assumptions=[
            "Reference FASTA is readable and has no conflicting index files at the output prefix.",
        ],
        inputs={"ref_path": str(ref), "results_dir": str(out_dir)},
        outputs={"bwa_index_prefix": str(index_prefix)},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return manifest
