"""Transcript-evidence task implementations for FLyteTest.

Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
input/output expectations follow the tool references under `docs/tool_refs/`
(notably `trinity.md`, `star.md`, `samtools.md`, and `stringtie.md`).
See those refs for the task-level command context that matches this module.

This module stages the current transcript-evidence branch upstream of PASA:
single-sample de novo Trinity, STAR alignment, one-BAM merge, genome-guided
Trinity, StringTie, and manifest-bearing collection.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir, File

from flytetest.config import (
    RESULTS_ROOT,
    TRANSCRIPT_EVIDENCE_RESULTS_PREFIX,
    TRANSCRIPT_EVIDENCE_WORKFLOW_NAME,
    project_mkdtemp,
    require_path,
    run_tool,
    transcript_evidence_env,
)
from flytetest.types import (
    AssetToolProvenance,
    MergedBamAsset,
    RnaSeqAlignmentResult,
    TrinityDeNovoTranscriptAsset,
    ReadPair,
    ReferenceGenome,
    StarGenomeIndexAsset,
    StringTieAssemblyResult,
    TrinityGenomeGuidedAssemblyResult,
)


STRINGTIE_LABEL = "STRG"
STRINGTIE_MIN_ISOFORM_FRACTION = "0.10"
STRINGTIE_MIN_READ_COVERAGE = "3"
STRINGTIE_MIN_JUNCTION_COVERAGE = "3"


def _as_json_compatible(value: Any) -> Any:
    """Recursively convert manifest values into JSON-serializable primitives."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _as_json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_as_json_compatible(item) for item in value]
    if isinstance(value, list):
        return [_as_json_compatible(item) for item in value]
    return value


def _read_files_command(left_path: Path, right_path: Path) -> list[str]:
    """Return the STAR decompression flag when both mates are gzipped FASTQs."""
    if left_path.suffix == ".gz" and right_path.suffix == ".gz":
        return ["--readFilesCommand", "zcat"]
    return []


def _star_sorted_bam(alignment_dir: Path) -> Path:
    """Resolve the coordinate-sorted BAM emitted by the STAR alignment task."""
    return require_path(alignment_dir / "Aligned.sortedByCoord.out.bam", "STAR sorted BAM")


def _star_log_final(alignment_dir: Path) -> Path | None:
    """Return STAR's final summary log when that optional output is present."""
    candidate = alignment_dir / "Log.final.out"
    if candidate.exists():
        return candidate
    return None


def _star_sj_out(alignment_dir: Path) -> Path | None:
    """Return STAR's splice junction table when it was emitted."""
    candidate = alignment_dir / "SJ.out.tab"
    if candidate.exists():
        return candidate
    return None


def _trinity_denovo_fasta(trinity_dir: Path) -> Path:
    """Resolve the primary de novo Trinity FASTA from a task output directory."""
    for candidate in (
        trinity_dir / "Trinity.fasta",
        trinity_dir / "trinity_denovo.Trinity.fasta",
    ):
        if candidate.exists():
            return candidate

    named_candidates = sorted(trinity_dir.glob("*.Trinity.fasta"))
    if len(named_candidates) == 1:
        return named_candidates[0]

    fasta_candidates = sorted(trinity_dir.glob("*.fasta"))
    if len(fasta_candidates) == 1:
        return fasta_candidates[0]
    raise FileNotFoundError(
        f"De novo Trinity FASTA not found in expected locations under {trinity_dir}"
    )


def _trinity_gg_fasta(trinity_dir: Path) -> Path:
    """Resolve the primary genome-guided Trinity FASTA from a task output directory."""
    for candidate in (
        trinity_dir / "Trinity-GG.fasta",
        trinity_dir / "Trinity.fasta",
    ):
        if candidate.exists():
            return candidate

    fasta_candidates = sorted(trinity_dir.glob("*.fasta"))
    if len(fasta_candidates) == 1:
        return fasta_candidates[0]
    raise FileNotFoundError(
        f"Genome-guided Trinity FASTA not found in expected locations under {trinity_dir}"
    )


def _stringtie_gtf(stringtie_dir: Path) -> Path:
    """Resolve the main StringTie transcript GTF produced by this stage."""
    return require_path(stringtie_dir / "transcripts.gtf", "StringTie transcripts GTF")


def _stringtie_abundance(stringtie_dir: Path) -> Path | None:
    """Return StringTie's gene abundance table when it is present."""
    candidate = stringtie_dir / "gene_abund.tab"
    if candidate.exists():
        return candidate
    return None


@transcript_evidence_env.task
def trinity_denovo_assemble(
    left: File,
    right: File,
    sample_id: str = "sample",
    trinity_sif: str = "",
    trinity_cpu: int = 4,
    trinity_max_memory_gb: int = 8,
) -> Dir:
    """Run de novo Trinity on one paired-end RNA-seq sample.

    The notes show a multi-sample `--samples_file` invocation. This repo keeps
    the current transcript branch single-sample, so it conservatively maps that
    boundary to Trinity's explicit paired-end `--left/--right` inputs.
    """
    left_path = require_path(Path(left.download_sync()), "Read 1 FASTQ")
    right_path = require_path(Path(right.download_sync()), "Read 2 FASTQ")
    out_dir = project_mkdtemp(f"trinity_denovo_{sample_id}_") / "trinity_denovo"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        [
            "Trinity",
            "--seqType",
            "fq",
            "--left",
            str(left_path),
            "--right",
            str(right_path),
            "--max_memory",
            f"{trinity_max_memory_gb}G",
            "--CPU",
            str(trinity_cpu),
            "--output",
            str(out_dir),
        ],
        trinity_sif,
        [left_path.parent, right_path.parent, out_dir.parent],
    )
    return Dir(path=str(out_dir))


@transcript_evidence_env.task
def star_genome_index(
    genome: File,
    star_sif: str = "",
    star_threads: int = 4,
) -> Dir:
    """Build a STAR genome index from the reference genome FASTA."""
    genome_path = require_path(Path(genome.download_sync()), "Reference genome FASTA")
    out_dir = project_mkdtemp("star_index_") / "index"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        [
            "STAR",
            "--runMode",
            "genomeGenerate",
            "--runThreadN",
            str(star_threads),
            "--genomeDir",
            str(out_dir),
            "--genomeFastaFiles",
            str(genome_path),
        ],
        star_sif,
        [genome_path.parent, out_dir.parent],
    )
    return Dir(path=str(out_dir))


@transcript_evidence_env.task
def star_align_sample(
    index: Dir,
    left: File,
    right: File,
    sample_id: str = "sample",
    star_sif: str = "",
    star_threads: int = 4,
) -> Dir:
    """Align one paired-end RNA-seq sample with STAR and emit its run directory."""
    index_path = require_path(Path(index.download_sync()), "STAR index directory")
    left_path = require_path(Path(left.download_sync()), "Read 1 FASTQ")
    right_path = require_path(Path(right.download_sync()), "Read 2 FASTQ")
    out_dir = project_mkdtemp(f"star_align_{sample_id}_") / "alignment"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "STAR",
        "--runThreadN",
        str(star_threads),
        "--genomeDir",
        str(index_path),
        "--readFilesIn",
        str(left_path),
        str(right_path),
        "--outSAMtype",
        "BAM",
        "SortedByCoordinate",
        "--outFileNamePrefix",
        f"{out_dir}/",
    ]
    cmd.extend(_read_files_command(left_path, right_path))

    run_tool(
        cmd,
        star_sif,
        [index_path.parent, left_path.parent, right_path.parent, out_dir.parent],
    )
    return Dir(path=str(out_dir))


@transcript_evidence_env.task
def samtools_merge_bams(
    alignment_dirs: list[Dir],
    samtools_sif: str = "",
) -> File:
    """Merge one or more STAR-produced BAMs into a downstream transcript-evidence BAM."""
    if not alignment_dirs:
        raise ValueError("samtools_merge_bams requires at least one STAR alignment directory.")

    alignment_paths = [
        require_path(Path(alignment.download_sync()), "STAR alignment directory")
        for alignment in alignment_dirs
    ]
    input_bams = [_star_sorted_bam(alignment_path) for alignment_path in alignment_paths]

    out_dir = project_mkdtemp("merged_bam_")
    out_dir.mkdir(parents=True, exist_ok=True)
    merged_bam = out_dir / "merged.bam"

    run_tool(
        ["samtools", "merge", "-f", str(merged_bam), *map(str, input_bams)],
        samtools_sif,
        [*{bam.parent for bam in input_bams}, out_dir],
    )
    return File(path=str(merged_bam))


@transcript_evidence_env.task
def trinity_genome_guided_assemble(
    merged_bam: File,
    trinity_sif: str = "",
    trinity_cpu: int = 4,
    trinity_max_memory_gb: int = 8,
    genome_guided_max_intron: int = 10000,
) -> Dir:
    """Run genome-guided Trinity from the merged RNA-seq BAM."""
    merged_bam_path = require_path(Path(merged_bam.download_sync()), "Merged BAM")
    out_dir = project_mkdtemp("trinity_gg_") / "trinity_gg"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        [
            "Trinity",
            "--genome_guided_bam",
            str(merged_bam_path),
            "--genome_guided_max_intron",
            str(genome_guided_max_intron),
            "--CPU",
            str(trinity_cpu),
            "--max_memory",
            f"{trinity_max_memory_gb}G",
            "--output",
            str(out_dir),
        ],
        trinity_sif,
        [merged_bam_path.parent, out_dir.parent],
    )
    return Dir(path=str(out_dir))


@transcript_evidence_env.task
def stringtie_assemble(
    merged_bam: File,
    stringtie_sif: str = "",
    stringtie_threads: int = 4,
) -> Dir:
    """Run StringTie transcript assembly from the merged RNA-seq BAM.

    The command contract for this stage is captured in
    `docs/tool_refs/stringtie.md`. This implementation uses a fixed,
    deterministic flag set for the current milestone and records it in the
    result manifest.
    """
    merged_bam_path = require_path(Path(merged_bam.download_sync()), "Merged BAM")
    out_dir = project_mkdtemp("stringtie_") / "stringtie"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        [
            "stringtie",
            str(merged_bam_path),
            "-p",
            str(stringtie_threads),
            "-o",
            str(out_dir / "transcripts.gtf"),
            "-l",
            STRINGTIE_LABEL,
            "-f",
            STRINGTIE_MIN_ISOFORM_FRACTION,
            "-A",
            str(out_dir / "gene_abund.tab"),
            "-c",
            STRINGTIE_MIN_READ_COVERAGE,
            "-j",
            STRINGTIE_MIN_JUNCTION_COVERAGE,
        ],
        stringtie_sif,
        [merged_bam_path.parent, out_dir.parent],
    )
    return Dir(path=str(out_dir))


@transcript_evidence_env.task
def collect_transcript_evidence_results(
    genome: File,
    left: File,
    right: File,
    trinity_denovo: Dir,
    star_index: Dir,
    alignment: Dir,
    merged_bam: File,
    trinity_gg: Dir,
    stringtie: Dir,
    sample_id: str = "sample",
) -> Dir:
    """Collect the current transcript-evidence branch into a stable PASA-ready bundle."""
    genome_input = Path(str(genome.path))
    left_input = Path(str(left.path))
    right_input = Path(str(right.path))

    star_index_path = require_path(Path(star_index.download_sync()), "STAR index directory")
    alignment_path = require_path(Path(alignment.download_sync()), "STAR alignment directory")
    merged_bam_path = require_path(Path(merged_bam.download_sync()), "Merged BAM")
    trinity_denovo_path = require_path(
        Path(trinity_denovo.download_sync()),
        "De novo Trinity directory",
    )
    trinity_path = require_path(Path(trinity_gg.download_sync()), "Genome-guided Trinity directory")
    stringtie_path = require_path(Path(stringtie.download_sync()), "StringTie output directory")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{TRANSCRIPT_EVIDENCE_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_denovo_dir = out_dir / "trinity_denovo"
    copied_index_dir = out_dir / "star_index"
    copied_alignment_dir = out_dir / "star_alignment"
    copied_merged_bam_dir = out_dir / "merged_bam"
    copied_trinity_dir = out_dir / "trinity_gg"
    copied_stringtie_dir = out_dir / "stringtie"

    shutil.copytree(trinity_denovo_path, copied_denovo_dir, dirs_exist_ok=True)
    shutil.copytree(star_index_path, copied_index_dir, dirs_exist_ok=True)
    shutil.copytree(alignment_path, copied_alignment_dir, dirs_exist_ok=True)
    copied_merged_bam_dir.mkdir(parents=True, exist_ok=True)
    copied_merged_bam_path = copied_merged_bam_dir / merged_bam_path.name
    shutil.copy2(merged_bam_path, copied_merged_bam_path)
    shutil.copytree(trinity_path, copied_trinity_dir, dirs_exist_ok=True)
    shutil.copytree(stringtie_path, copied_stringtie_dir, dirs_exist_ok=True)

    reference_asset = ReferenceGenome(fasta_path=genome_input)
    read_pair_asset = ReadPair(
        sample_id=sample_id,
        left_reads_path=left_input,
        right_reads_path=right_input,
    )
    trinity_denovo_asset = TrinityDeNovoTranscriptAsset(
        fasta_path=_trinity_denovo_fasta(copied_denovo_dir),
        notes=(
            "The notes show a multi-sample Trinity --samples_file invocation; this single-sample workflow maps that boundary to paired-end --left/--right inputs.",
        ),
    )
    star_index_asset = StarGenomeIndexAsset(
        index_dir=copied_index_dir,
        reference_genome=reference_asset,
        notes=("This first implementation always builds a fresh STAR index.",),
    )
    alignment_asset = RnaSeqAlignmentResult(
        sample_id=sample_id,
        output_dir=copied_alignment_dir,
        sorted_bam_path=_star_sorted_bam(copied_alignment_dir),
        log_final_out_path=_star_log_final(copied_alignment_dir),
        splice_junction_tab_path=_star_sj_out(copied_alignment_dir),
        source_reads=read_pair_asset,
        star_index=star_index_asset,
        notes=(
            "Gzipped FASTQ inputs use STAR --readFilesCommand zcat when both mates end in .gz.",
        ),
        provenance=AssetToolProvenance(
            tool_name="STAR",
            tool_stage="RNA-seq genome alignment",
            legacy_asset_name="StarAlignmentResult",
            source_manifest_key="rna_seq_alignment",
        ),
    )
    merged_bam_asset = MergedBamAsset(
        bam_path=copied_merged_bam_path,
        source_bams=(alignment_asset.sorted_bam_path,),
        notes=(
            "The notes describe merging BAMs from all RNA-seq samples, but this constrained workflow currently merges only the single staged STAR BAM.",
        ),
    )
    trinity_asset = TrinityGenomeGuidedAssemblyResult(
        output_dir=copied_trinity_dir,
        # Trinity output names vary slightly across installations, so collection
        # resolves a small conservative filename set instead of hardcoding one.
        assembly_fasta_path=_trinity_gg_fasta(copied_trinity_dir),
        source_bam=merged_bam_asset,
        genome_guided_max_intron=10000,
        notes=(
            "Genome-guided Trinity output FASTA is resolved from common Trinity filenames inside the output directory.",
        ),
    )
    stringtie_asset = StringTieAssemblyResult(
        output_dir=copied_stringtie_dir,
        transcript_gtf_path=_stringtie_gtf(copied_stringtie_dir),
        gene_abundance_path=_stringtie_abundance(copied_stringtie_dir),
        source_bam=merged_bam_asset,
        notes=(
            "StringTie runs with the fixed flag set -l STRG -f 0.10 -c 3 -j 3 plus -A and the requested thread count.",
        ),
    )

    manifest = {
        "workflow": TRANSCRIPT_EVIDENCE_WORKFLOW_NAME,
        "sample_id": sample_id,
        "notes_alignment": {
            "status": "implemented_with_documented_simplifications",
            "pasa_ready": True,
            "reason": "This bundle now contains both Trinity branches required upstream of PASA, while STAR alignment and BAM merge remain simplified to one paired-end sample instead of the full all-sample path.",
        },
        "assumptions": [
            "This workflow preserves the upstream stage order from the biological notes by running de novo Trinity before STAR alignment, BAM merge, genome-guided Trinity, and StringTie.",
            "The notes show de novo Trinity with --samples_file across RNA-seq inputs; this workflow currently keeps the repo's single-sample shape and uses Trinity --left/--right for one paired-end read set.",
            "The notes describe aligning all RNA-seq samples with STAR and then merging all BAMs; this workflow currently aligns one paired-end sample and merges only that sample's BAM.",
            "The workflow always builds a fresh STAR genome index rather than reusing a prebuilt one.",
            "StringTie is run with the fixed flags -l STRG -f 0.10 -c 3 -j 3 in addition to -A and the requested thread count.",
            "When both read inputs end in .gz, STAR is run with --readFilesCommand zcat.",
            "De novo and genome-guided Trinity FASTA resolution are both based on common Trinity output filenames inside their respective task output directories.",
        ],
        "outputs": {
            "trinity_denovo_dir": str(copied_denovo_dir),
            "trinity_denovo_fasta": str(trinity_denovo_asset.fasta_path),
            "star_index_dir": str(copied_index_dir),
            "star_alignment_dir": str(copied_alignment_dir),
            "merged_bam": str(copied_merged_bam_path),
            "trinity_gg_dir": str(copied_trinity_dir),
            "stringtie_dir": str(copied_stringtie_dir),
            "stringtie_gtf": str(stringtie_asset.transcript_gtf_path),
            "trinity_gg_fasta": str(trinity_asset.assembly_fasta_path),
        },
        "assets": _as_json_compatible(
            {
                "reference_genome": asdict(reference_asset),
                "read_pair": asdict(read_pair_asset),
                "trinity_de_novo": asdict(trinity_denovo_asset),
                "star_index": asdict(star_index_asset),
                "rna_seq_alignment": alignment_asset.to_dict(),
                "star_alignment": alignment_asset.to_dict(),
                "merged_bam": asdict(merged_bam_asset),
                "trinity_genome_guided": asdict(trinity_asset),
                "stringtie": asdict(stringtie_asset),
            }
        ),
        "trinity_denovo_files": sorted(path.name for path in copied_denovo_dir.glob("*")),
        "star_alignment_files": sorted(path.name for path in copied_alignment_dir.glob("*")),
        "trinity_gg_files": sorted(path.name for path in copied_trinity_dir.glob("*")),
        "stringtie_files": sorted(path.name for path in copied_stringtie_dir.glob("*")),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))
