"""BRAKER3 workflow entrypoint for the current ab initio annotation milestone.

    This module stages local inputs, runs the tutorial-backed BRAKER3 boundary, and
    collects source-preserving normalized outputs for later EVM preparation.

    Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
    input/output expectations follow `docs/tool_refs/braker3.md`.
"""

from __future__ import annotations

from flyte.io import Dir, File

from flytetest.config import annotation_env
from flytetest.tasks.annotation import (
    braker3_predict,
    collect_braker3_results,
    normalize_braker3_for_evm,
    stage_braker3_inputs,
)


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@annotation_env.task
def ab_initio_annotation_braker3(
    genome: File,
    rnaseq_bam_path: str = "",
    protein_fasta_path: str = "",
    braker_species: str = "flytetest_braker3",
    braker3_sif: str = "",
) -> Dir:
    """Compose and execute the BRAKER3 ab initio gene prediction workflow with normalization.

    Args:
        genome: A value used by the helper.
        rnaseq_bam_path: A filesystem path used by the helper.
        protein_fasta_path: A filesystem path used by the helper.
        braker_species: A value used by the helper.
        braker3_sif: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    staged_inputs = stage_braker3_inputs(
        genome=genome,
        rnaseq_bam_path=rnaseq_bam_path,
        protein_fasta_path=protein_fasta_path,
    )
    braker_run = braker3_predict(
        staged_inputs=staged_inputs,
        braker_species=braker_species,
        braker3_sif=braker3_sif,
    )
    normalized_braker = normalize_braker3_for_evm(braker_run=braker_run)
    return collect_braker3_results(
        genome=genome,
        staged_inputs=staged_inputs,
        braker_run=braker_run,
        normalized_braker=normalized_braker,
        braker_species=braker_species,
    )
