"""GATK4 variant calling task implementations for Milestone A."""

from __future__ import annotations

import shlex
import subprocess
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
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
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
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest


def bwa_mem2_mem(
    ref_path: str,
    r1_path: str,
    sample_id: str,
    results_dir: str,
    r2_path: str = "",
    threads: int = 4,
    sif_path: str = "",
) -> dict:
    """Align paired-end FASTQ reads to a reference using BWA-MEM2."""
    require_path(Path(ref_path), "Reference genome FASTA")
    require_path(Path(r1_path), "R1 FASTQ")
    if r2_path:
        require_path(Path(r2_path), "R2 FASTQ")

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_bam = out_dir / f"{sample_id}_aligned.bam"

    rg = f"@RG\\tID:{sample_id}\\tSM:{sample_id}\\tLB:lib\\tPL:ILLUMINA"
    pipeline = (
        f"bwa-mem2 mem -R {shlex.quote(rg)} -t {threads} "
        f"{shlex.quote(ref_path)} {shlex.quote(r1_path)}"
        + (f" {shlex.quote(r2_path)}" if r2_path else "")
        + f" | samtools view -bS -o {shlex.quote(str(output_bam))} -"
    )

    if sif_path:
        cmd = f"apptainer exec {sif_path} bash -c {shlex.quote(pipeline)}"
    else:
        cmd = pipeline

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"bwa_mem2_mem failed:\n{result.stderr}")

    if not output_bam.exists():
        raise FileNotFoundError(f"bwa_mem2_mem produced no BAM: {output_bam}")

    manifest = build_manifest_envelope(
        stage="bwa_mem2_mem",
        assumptions=[
            "Reference is indexed (bwa_mem2_index must have run first).",
            "R1 (and R2 if provided) are readable FASTQ files.",
        ],
        inputs={
            "ref_path": ref_path,
            "r1_path": r1_path,
            "r2_path": r2_path,
            "sample_id": sample_id,
            "threads": threads,
        },
        outputs={"aligned_bam": str(output_bam)},
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest


def sort_sam(
    bam_path: str,
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Coordinate-sort a BAM file using GATK SortSam."""
    in_bam = require_path(Path(bam_path), "Input BAM for SortSam")
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_bam = out_dir / f"{sample_id}_sorted.bam"

    cmd = [
        "gatk", "SortSam",
        "-I", str(in_bam),
        "-O", str(out_bam),
        "--SORT_ORDER", "coordinate",
        "--CREATE_INDEX", "true",
    ]
    bind_paths = [in_bam.parent, out_dir]
    run_tool(cmd, sif_path or "data/images/gatk4.sif", bind_paths)

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
        inputs={"bam_path": str(in_bam), "sample_id": sample_id},
        outputs={
            "sorted_bam": str(out_bam),
            "sorted_bam_index": str(out_bai) if out_bai.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest


def mark_duplicates(
    bam_path: str,
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Mark PCR and optical duplicate reads using GATK MarkDuplicates."""
    in_bam = require_path(Path(bam_path), "Coordinate-sorted BAM for MarkDuplicates")
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_bam = out_dir / f"{sample_id}_marked_duplicates.bam"
    metrics = out_dir / f"{sample_id}_duplicate_metrics.txt"

    cmd = [
        "gatk", "MarkDuplicates",
        "-I", str(in_bam),
        "-O", str(out_bam),
        "-M", str(metrics),
        "--CREATE_INDEX", "true",
    ]
    bind_paths = [in_bam.parent, out_dir]
    run_tool(cmd, sif_path or "data/images/gatk4.sif", bind_paths)

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
        inputs={"bam_path": str(in_bam), "sample_id": sample_id},
        outputs={
            "dedup_bam": str(out_bam),
            "duplicate_metrics": str(metrics),
            "dedup_bam_index": str(out_bai) if out_bai.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest


_DEFAULT_VQSR_FILTER_LEVEL: dict[str, float] = {"SNP": 99.5, "INDEL": 99.0}
_SNP_ANNOTATIONS = ["QD", "MQ", "MQRankSum", "ReadPosRankSum", "FS", "SOR"]
_INDEL_ANNOTATIONS = ["QD", "FS", "SOR"]


def variant_recalibrator(
    ref_path: str,
    vcf_path: str,
    known_sites: list[str],
    known_sites_flags: list[dict],
    mode: str,
    cohort_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Build a VQSR recalibration model using GATK4 VariantRecalibrator.

    ``known_sites`` and ``known_sites_flags`` are parallel lists — each entry
    in ``known_sites_flags`` must carry keys ``resource_name``, ``known``,
    ``training``, ``truth``, and ``prior`` (all strings).
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

    require_path(Path(ref_path), "Reference genome FASTA")
    require_path(Path(vcf_path), "Input VCF for VariantRecalibrator")

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    output_recal = out_dir / f"{cohort_id}_{mode.lower()}.recal"
    output_tranches = out_dir / f"{cohort_id}_{mode.lower()}.tranches"

    annotations = _SNP_ANNOTATIONS if mode == "SNP" else _INDEL_ANNOTATIONS

    cmd = [
        "gatk", "VariantRecalibrator",
        "-R", ref_path,
        "-V", vcf_path,
        "-mode", mode,
        "-O", str(output_recal),
        "--tranches-file", str(output_tranches),
    ]
    for vcf, flags in zip(known_sites, known_sites_flags):
        name = flags.get("resource_name", "unknown")
        known = flags.get("known", "false")
        training = flags.get("training", "false")
        truth = flags.get("truth", "false")
        prior = flags.get("prior", "10")
        cmd.extend([
            f"--resource:{name},known={known},training={training},truth={truth},prior={prior}",
            vcf,
        ])
    for ann in annotations:
        cmd.extend(["-an", ann])

    bind_paths = [Path(ref_path).parent, Path(vcf_path).parent, out_dir,
                  *[Path(s).parent for s in known_sites]]
    run_tool(cmd, sif_path or "data/images/gatk4.sif", bind_paths)

    if not output_recal.exists():
        raise FileNotFoundError(
            f"VariantRecalibrator did not produce recal file: {output_recal}"
        )

    manifest = build_manifest_envelope(
        stage="variant_recalibrator",
        assumptions=[
            "Input VCF is a joint-called cohort VCF with sufficient variant count "
            "(≥30k SNPs for SNP mode; ≥2k indels for INDEL mode).",
            "All known-sites VCFs are indexed (.tbi or .idx present next to each VCF).",
            "Reference has .fai and .dict next to the FASTA.",
        ],
        inputs={
            "ref_path": ref_path,
            "vcf_path": vcf_path,
            "mode": mode,
            "cohort_id": cohort_id,
            "known_sites": known_sites,
        },
        outputs={
            "recal_file": str(output_recal),
            "tranches_file": str(output_tranches),
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest


def apply_vqsr(
    ref_path: str,
    vcf_path: str,
    recal_file: str,
    tranches_file: str,
    mode: str,
    cohort_id: str,
    results_dir: str,
    truth_sensitivity_filter_level: float = 0.0,
    sif_path: str = "",
) -> dict:
    """Apply a VQSR recalibration model to a VCF using GATK4 ApplyVQSR.

    ``truth_sensitivity_filter_level`` defaults to 99.5 for SNP and 99.0 for
    INDEL when passed as 0.0.  ``recal_file`` and ``tranches_file`` must come
    from ``variant_recalibrator`` run with the same ``mode``.
    """
    if mode not in ("SNP", "INDEL"):
        raise ValueError(f"mode must be 'SNP' or 'INDEL', got {mode!r}")

    require_path(Path(ref_path), "Reference genome FASTA")
    require_path(Path(vcf_path), "Input VCF for ApplyVQSR")
    require_path(Path(recal_file), "VQSR recalibration file")
    require_path(Path(tranches_file), "VQSR tranches file")

    filter_level = (
        truth_sensitivity_filter_level
        if truth_sensitivity_filter_level != 0.0
        else _DEFAULT_VQSR_FILTER_LEVEL[mode]
    )

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_vcf = out_dir / f"{cohort_id}_vqsr_{mode.lower()}.vcf.gz"
    tbi_path = Path(str(output_vcf) + ".tbi")

    cmd = [
        "gatk", "ApplyVQSR",
        "-R", ref_path,
        "-V", vcf_path,
        "--recal-file", recal_file,
        "--tranches-file", tranches_file,
        "--truth-sensitivity-filter-level", str(filter_level),
        "--create-output-variant-index", "true",
        "-mode", mode,
        "-O", str(output_vcf),
    ]

    bind_paths = [
        Path(ref_path).parent,
        Path(vcf_path).parent,
        Path(recal_file).parent,
        Path(tranches_file).parent,
        out_dir,
    ]
    run_tool(cmd, sif_path or "data/images/gatk4.sif", bind_paths)

    if not output_vcf.exists():
        raise FileNotFoundError(
            f"ApplyVQSR did not produce output VCF: {output_vcf}"
        )

    manifest = build_manifest_envelope(
        stage="apply_vqsr",
        assumptions=[
            "recal_file and tranches_file were produced by variant_recalibrator "
            "for the same mode and the same VCF.",
            "--create-output-variant-index true writes a .vcf.gz.tbi companion automatically.",
        ],
        inputs={
            "ref_path": ref_path,
            "vcf_path": vcf_path,
            "recal_file": recal_file,
            "tranches_file": tranches_file,
            "mode": mode,
            "cohort_id": cohort_id,
            "truth_sensitivity_filter_level": filter_level,
        },
        outputs={
            "vqsr_vcf": str(output_vcf),
            "vqsr_vcf_index": str(tbi_path) if tbi_path.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest


def merge_bam_alignment(
    ref_path: str,
    aligned_bam: str,
    ubam_path: str,
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Merge aligned BAM with unmapped BAM using GATK4 MergeBamAlignment.

    ``ubam_path`` must be queryname-sorted.  ``--SORT_ORDER coordinate``
    produces a coordinate-sorted merged BAM so no separate sort_sam step
    is needed.
    """
    require_path(Path(ref_path), "Reference genome FASTA")
    require_path(Path(aligned_bam), "Aligned BAM for MergeBamAlignment")
    require_path(Path(ubam_path), "Unmapped BAM for MergeBamAlignment")

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_bam = out_dir / f"{sample_id}_merged.bam"

    cmd = [
        "gatk", "MergeBamAlignment",
        "-R", ref_path,
        "-ALIGNED", aligned_bam,
        "-UNMAPPED", ubam_path,
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

    bind_paths = [
        Path(ref_path).parent,
        Path(aligned_bam).parent,
        Path(ubam_path).parent,
        out_dir,
    ]
    run_tool(cmd, sif_path or "data/images/gatk4.sif", bind_paths)

    if not out_bam.exists():
        raise FileNotFoundError(
            f"MergeBamAlignment did not produce output BAM: {out_bam}"
        )

    out_bai = out_bam.with_suffix(".bai")
    if not out_bai.exists():
        alt_bai = Path(str(out_bam) + ".bai")
        if alt_bai.exists():
            out_bai = alt_bai

    manifest = build_manifest_envelope(
        stage="merge_bam_alignment",
        assumptions=[
            "ubam_path is queryname-sorted (GATK requirement).",
            "--SORT_ORDER coordinate eliminates the need for sort_sam.",
            "--CREATE_INDEX true writes a .bai companion alongside the BAM.",
        ],
        inputs={
            "ref_path": ref_path,
            "aligned_bam": aligned_bam,
            "ubam_path": ubam_path,
            "sample_id": sample_id,
        },
        outputs={
            "merged_bam": str(out_bam),
            "merged_bam_index": str(out_bai) if out_bai.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest


def gather_vcfs(
    gvcf_paths: list[str],
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Merge ordered per-interval GVCFs into a single GVCF using GATK GatherVcfs."""
    if not gvcf_paths:
        raise ValueError("gvcf_paths must not be empty")

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_vcf = out_dir / f"{sample_id}_gathered.g.vcf.gz"

    cmd = ["gatk", "GatherVcfs"]
    for gvcf in gvcf_paths:
        cmd.extend(["-I", gvcf])
    cmd.extend(["-O", str(out_vcf), "--CREATE_INDEX", "true"])

    bind_paths = [Path(p).parent for p in gvcf_paths] + [out_dir]
    run_tool(cmd, sif_path or "data/images/gatk4.sif", bind_paths)

    if not out_vcf.exists():
        raise FileNotFoundError(
            f"GatherVcfs did not produce output GVCF: {out_vcf}"
        )

    manifest = build_manifest_envelope(
        stage="gather_vcfs",
        assumptions=[
            "gvcf_paths must be in genomic interval order; GatherVcfs requires non-overlapping inputs.",
            "All input GVCFs must be indexed (.tbi or .idx next to each file).",
            "--CREATE_INDEX true writes a .tbi companion alongside the output GVCF.",
        ],
        inputs={"gvcf_paths": gvcf_paths, "sample_id": sample_id},
        outputs={"gathered_gvcf": str(out_vcf)},
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest


def calculate_genotype_posteriors(
    ref_path: str,
    vcf_path: str,
    cohort_id: str,
    results_dir: str,
    supporting_callsets: list[str] | None = None,
    sif_path: str = "",
) -> dict:
    """Refine genotype posteriors using population priors (GATK4 CGP)."""
    require_path(Path(vcf_path), "Input VCF for CalculateGenotypePosteriors")

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_vcf = out_dir / f"{cohort_id}_cgp.vcf.gz"

    cmd = [
        "gatk", "CalculateGenotypePosteriors",
        "-V", vcf_path,
        "-O", str(out_vcf),
        "--create-output-variant-index", "true",
    ]
    for callset in (supporting_callsets or []):
        cmd.extend(["--supporting-callsets", callset])

    bind_paths = [Path(vcf_path).parent, out_dir]
    run_tool(cmd, sif_path or "data/images/gatk4.sif", bind_paths)

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
            "vcf_path": vcf_path,
            "cohort_id": cohort_id,
            "supporting_callsets": supporting_callsets or [],
        },
        outputs={
            "cgp_vcf": str(out_vcf),
            "cgp_vcf_index": str(tbi) if tbi.exists() else "",
        },
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return manifest
