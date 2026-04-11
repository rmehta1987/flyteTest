"""Protein-evidence workflow entrypoint for FLyteTest.

This module stages local protein FASTAs, chunks them deterministically, runs
Exonerate per chunk, and collects the later-EVM protein evidence bundle.

Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
input/output expectations follow `docs/tool_refs/exonerate.md`.
"""

from __future__ import annotations

from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import protein_evidence_env, require_path
from flytetest.tasks.protein_evidence import (
    _chunk_fasta_paths,
    chunk_protein_fastas,
    exonerate_align_chunk,
    exonerate_concat_results,
    exonerate_to_evm_gff3,
    stage_protein_fastas,
)


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@protein_evidence_env.task
def protein_evidence_alignment(
    genome: File,
    protein_fastas: list[File],
    proteins_per_chunk: int = 500,
    exonerate_sif: str = "",
    exonerate_model: str = "protein2genome",
) -> Dir:
    """Build the current protein-evidence bundle from local FASTA inputs."""
    staged_proteins = stage_protein_fastas(protein_fastas=protein_fastas)
    protein_chunks = chunk_protein_fastas(
        staged_proteins=staged_proteins,
        proteins_per_chunk=proteins_per_chunk,
    )

    chunk_dir = require_path(
        Path(protein_chunks.download_sync()),
        "Protein chunk directory from chunk_protein_fastas",
    )
    chunk_fastas = _chunk_fasta_paths(chunk_dir)
    if not chunk_fastas:
        raise FileNotFoundError(
            f"No chunk FASTA files were found under {chunk_dir}; expected output from chunk_protein_fastas."
        )

    raw_chunk_results: list[Dir] = []
    evm_chunk_results: list[Dir] = []
    for chunk_fasta in chunk_fastas:
        raw_chunk_result = exonerate_align_chunk(
            genome=genome,
            protein_chunk=File(path=str(chunk_fasta)),
            exonerate_sif=exonerate_sif,
            exonerate_model=exonerate_model,
        )
        raw_chunk_results.append(raw_chunk_result)
        evm_chunk_results.append(exonerate_to_evm_gff3(exonerate_alignment=raw_chunk_result))

    return exonerate_concat_results(
        genome=genome,
        staged_proteins=staged_proteins,
        protein_chunks=protein_chunks,
        raw_chunk_results=raw_chunk_results,
        evm_chunk_results=evm_chunk_results,
    )
