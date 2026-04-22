"""GATK4 variant calling task implementations for Milestone A."""

from __future__ import annotations

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
