from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir, File

from flytetest.config import (
    RESULTS_ROOT,
    TRANSCRIPT_EVIDENCE_RESULTS_PREFIX,
    TRANSCRIPT_EVIDENCE_WORKFLOW_NAME,
    require_path,
    run_tool,
    transcript_evidence_env,
)
from flytetest.types import (
    MergedBamAsset,
    ReadPair,
    ReferenceGenome,
    StarAlignmentResult,
    StarGenomeIndexAsset,
    StringTieAssemblyResult,
    TrinityGenomeGuidedAssemblyResult,
)


def _as_json_compatible(value: Any) -> Any:
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
    if left_path.suffix == ".gz" and right_path.suffix == ".gz":
        return ["--readFilesCommand", "zcat"]
    return []


def _star_sorted_bam(alignment_dir: Path) -> Path:
    return require_path(alignment_dir / "Aligned.sortedByCoord.out.bam", "STAR sorted BAM")


def _star_log_final(alignment_dir: Path) -> Path | None:
    candidate = alignment_dir / "Log.final.out"
    if candidate.exists():
        return candidate
    return None


def _star_sj_out(alignment_dir: Path) -> Path | None:
    candidate = alignment_dir / "SJ.out.tab"
    if candidate.exists():
        return candidate
    return None


def _trinity_gg_fasta(trinity_dir: Path) -> Path:
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
    return require_path(stringtie_dir / "transcripts.gtf", "StringTie transcripts GTF")


def _stringtie_abundance(stringtie_dir: Path) -> Path | None:
    candidate = stringtie_dir / "gene_abund.tab"
    if candidate.exists():
        return candidate
    return None


@transcript_evidence_env.task
def star_genome_index(
    genome: File,
    star_sif: str = "",
    star_threads: int = 4,
) -> Dir:
    genome_path = require_path(Path(genome.download_sync()), "Reference genome FASTA")
    out_dir = Path(tempfile.mkdtemp(prefix="star_index_")) / "index"
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
    return Dir.from_local_sync(str(out_dir))


@transcript_evidence_env.task
def star_align_sample(
    index: Dir,
    left: File,
    right: File,
    sample_id: str = "sample",
    star_sif: str = "",
    star_threads: int = 4,
) -> Dir:
    index_path = require_path(Path(index.download_sync()), "STAR index directory")
    left_path = require_path(Path(left.download_sync()), "Read 1 FASTQ")
    right_path = require_path(Path(right.download_sync()), "Read 2 FASTQ")
    out_dir = Path(tempfile.mkdtemp(prefix=f"star_align_{sample_id}_")) / "alignment"
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
    return Dir.from_local_sync(str(out_dir))


@transcript_evidence_env.task
def samtools_merge_bams(
    alignment_dirs: list[Dir],
    samtools_sif: str = "",
) -> File:
    if not alignment_dirs:
        raise ValueError("samtools_merge_bams requires at least one STAR alignment directory.")

    alignment_paths = [
        require_path(Path(alignment.download_sync()), "STAR alignment directory")
        for alignment in alignment_dirs
    ]
    input_bams = [_star_sorted_bam(alignment_path) for alignment_path in alignment_paths]

    out_dir = Path(tempfile.mkdtemp(prefix="merged_bam_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    merged_bam = out_dir / "merged.bam"

    run_tool(
        ["samtools", "merge", "-f", str(merged_bam), *map(str, input_bams)],
        samtools_sif,
        [*{bam.parent for bam in input_bams}, out_dir],
    )
    return File.from_local_sync(str(merged_bam))


@transcript_evidence_env.task
def trinity_genome_guided_assemble(
    merged_bam: File,
    trinity_sif: str = "",
    trinity_cpu: int = 4,
    trinity_max_memory_gb: int = 8,
    genome_guided_max_intron: int = 10000,
) -> Dir:
    merged_bam_path = require_path(Path(merged_bam.download_sync()), "Merged BAM")
    out_dir = Path(tempfile.mkdtemp(prefix="trinity_gg_")) / "trinity_gg"
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
    return Dir.from_local_sync(str(out_dir))


@transcript_evidence_env.task
def stringtie_assemble(
    merged_bam: File,
    stringtie_sif: str = "",
    stringtie_threads: int = 4,
) -> Dir:
    merged_bam_path = require_path(Path(merged_bam.download_sync()), "Merged BAM")
    out_dir = Path(tempfile.mkdtemp(prefix="stringtie_")) / "stringtie"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        [
            "stringtie",
            str(merged_bam_path),
            "-p",
            str(stringtie_threads),
            "-o",
            str(out_dir / "transcripts.gtf"),
            "-A",
            str(out_dir / "gene_abund.tab"),
        ],
        stringtie_sif,
        [merged_bam_path.parent, out_dir.parent],
    )
    return Dir.from_local_sync(str(out_dir))


@transcript_evidence_env.task
def collect_transcript_evidence_results(
    genome: File,
    left: File,
    right: File,
    star_index: Dir,
    alignment: Dir,
    merged_bam: File,
    trinity_gg: Dir,
    stringtie: Dir,
    sample_id: str = "sample",
) -> Dir:
    genome_input = Path(str(genome.path))
    left_input = Path(str(left.path))
    right_input = Path(str(right.path))

    star_index_path = require_path(Path(star_index.download_sync()), "STAR index directory")
    alignment_path = require_path(Path(alignment.download_sync()), "STAR alignment directory")
    merged_bam_path = require_path(Path(merged_bam.download_sync()), "Merged BAM")
    trinity_path = require_path(Path(trinity_gg.download_sync()), "Genome-guided Trinity directory")
    stringtie_path = require_path(Path(stringtie.download_sync()), "StringTie output directory")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{TRANSCRIPT_EVIDENCE_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_index_dir = out_dir / "star_index"
    copied_alignment_dir = out_dir / "star_alignment"
    copied_merged_bam_dir = out_dir / "merged_bam"
    copied_trinity_dir = out_dir / "trinity_gg"
    copied_stringtie_dir = out_dir / "stringtie"

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
    star_index_asset = StarGenomeIndexAsset(
        index_dir=copied_index_dir,
        reference_genome=reference_asset,
        notes=("This first implementation always builds a fresh STAR index.",),
    )
    alignment_asset = StarAlignmentResult(
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
    )
    merged_bam_asset = MergedBamAsset(
        bam_path=copied_merged_bam_path,
        source_bams=(alignment_asset.sorted_bam_path,),
        notes=(
            "The BAM merge stage currently runs on a single STAR-produced BAM to preserve the explicit pipeline boundary for future multi-sample expansion.",
        ),
    )
    trinity_asset = TrinityGenomeGuidedAssemblyResult(
        output_dir=copied_trinity_dir,
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
    )

    manifest = {
        "workflow": TRANSCRIPT_EVIDENCE_WORKFLOW_NAME,
        "sample_id": sample_id,
        "assumptions": [
            "This first transcript-evidence workflow accepts one paired-end read set.",
            "The workflow always builds a fresh STAR genome index rather than reusing a prebuilt one.",
            "The BAM merge stage currently merges a single STAR alignment BAM to preserve the explicit pipeline stage boundary.",
            "When both read inputs end in .gz, STAR is run with --readFilesCommand zcat.",
            "Genome-guided Trinity FASTA resolution is based on common Trinity output filenames inside the task output directory.",
        ],
        "outputs": {
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
                "star_index": asdict(star_index_asset),
                "star_alignment": asdict(alignment_asset),
                "merged_bam": asdict(merged_bam_asset),
                "trinity_genome_guided": asdict(trinity_asset),
                "stringtie": asdict(stringtie_asset),
            }
        ),
        "star_alignment_files": sorted(path.name for path in copied_alignment_dir.glob("*")),
        "trinity_gg_files": sorted(path.name for path in copied_trinity_dir.glob("*")),
        "stringtie_files": sorted(path.name for path in copied_stringtie_dir.glob("*")),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir.from_local_sync(str(out_dir))
