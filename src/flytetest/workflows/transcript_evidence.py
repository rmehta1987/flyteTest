"""Transcript-evidence workflow entrypoint for FLyteTest.

    Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
    input/output expectations follow the tool references under `docs/tool_refs/`
    (notably `trinity.md`, `star.md`, `samtools.md`, and `stringtie.md`).

    This module composes the current transcript branch upstream of PASA: de novo
    Trinity, STAR indexing and alignment, one-BAM merge, genome-guided Trinity,
    StringTie, and stable result collection.
"""

from __future__ import annotations

from flyte.io import Dir, File

from flytetest.config import transcript_evidence_env
from flytetest.tasks.transcript_evidence import (
    collect_transcript_evidence_results,
    samtools_merge_bams,
    star_align_sample,
    star_genome_index,
    stringtie_assemble,
    trinity_denovo_assemble,
    trinity_genome_guided_assemble,
)


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@transcript_evidence_env.task
def transcript_evidence_generation(
    genome: File,
    left: File,
    right: File,
    sample_id: str = "sample",
    star_sif: str = "",
    samtools_sif: str = "",
    trinity_sif: str = "",
    stringtie_sif: str = "",
    star_threads: int = 4,
    trinity_cpu: int = 4,
    trinity_max_memory_gb: int = 8,
    genome_guided_max_intron: int = 10000,
    stringtie_threads: int = 4,
) -> Dir:
    """Orchestrate comprehensive transcript evidence generation from paired-end RNA-seq reads.

    Args:
        genome: A value used by the helper.
        left: A value used by the helper.
        right: A value used by the helper.
        sample_id: A value used by the helper.
        star_sif: A value used by the helper.
        samtools_sif: A value used by the helper.
        trinity_sif: A value used by the helper.
        stringtie_sif: A value used by the helper.
        star_threads: A value used by the helper.
        trinity_cpu: A value used by the helper.
        trinity_max_memory_gb: A value used by the helper.
        genome_guided_max_intron: A value used by the helper.
        stringtie_threads: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    trinity_denovo = trinity_denovo_assemble(
        left=left,
        right=right,
        sample_id=sample_id,
        trinity_sif=trinity_sif,
        trinity_cpu=trinity_cpu,
        trinity_max_memory_gb=trinity_max_memory_gb,
    )
    index = star_genome_index(genome=genome, star_sif=star_sif, star_threads=star_threads)
    alignment = star_align_sample(
        index=index,
        left=left,
        right=right,
        sample_id=sample_id,
        star_sif=star_sif,
        star_threads=star_threads,
    )
    merged_bam = samtools_merge_bams(
        alignment_dirs=[alignment],
        samtools_sif=samtools_sif,
    )
    trinity_gg = trinity_genome_guided_assemble(
        merged_bam=merged_bam,
        trinity_sif=trinity_sif,
        trinity_cpu=trinity_cpu,
        trinity_max_memory_gb=trinity_max_memory_gb,
        genome_guided_max_intron=genome_guided_max_intron,
    )
    stringtie = stringtie_assemble(
        merged_bam=merged_bam,
        stringtie_sif=stringtie_sif,
        stringtie_threads=stringtie_threads,
    )
    return collect_transcript_evidence_results(
        genome=genome,
        left=left,
        right=right,
        trinity_denovo=trinity_denovo,
        star_index=index,
        alignment=alignment,
        merged_bam=merged_bam,
        trinity_gg=trinity_gg,
        stringtie=stringtie,
        sample_id=sample_id,
    )
