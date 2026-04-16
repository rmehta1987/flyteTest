"""Transcript-evidence workflow entrypoint for FLyteTest.

Stage ordering follows `docs/braker3_evm_notes.md`, and this workflow composes
the current transcript-evidence branch upstream of PASA: de novo Trinity, STAR
indexing and alignment, merged BAM collection, genome-guided Trinity, StringTie,
and stable result collection.
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
    """Compose the transcript-evidence branch that feeds the PASA stage boundary.

    Args:
        genome: Reference genome FASTA used to seed STAR indexing.
        left: First RNA-seq mate passed through Trinity and STAR.
        right: Second RNA-seq mate passed through Trinity and STAR.
        sample_id: Sample label threaded through the transcript-evidence bundle.
        star_sif: Optional container image for STAR stages.
        samtools_sif: Optional container image for the BAM merge stage.
        trinity_sif: Optional container image for the Trinity stages.
        stringtie_sif: Optional container image for StringTie.
        star_threads: Thread count shared by STAR index and alignment stages.
        trinity_cpu: Thread count shared by Trinity assembly stages.
        trinity_max_memory_gb: Memory bound shared by Trinity stages in
            gigabytes.
        genome_guided_max_intron: Maximum intron length passed to the
            genome-guided Trinity step.
        stringtie_threads: Thread count passed to StringTie.

    Returns:
        Manifest-bearing transcript-evidence bundle ready for the PASA branch.
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
