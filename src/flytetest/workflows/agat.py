"""AGAT workflow entrypoints for the post-EggNOG milestone slices.

This module exposes the post-processing stages that consume EggNOG-annotated
GFF3 bundles and produce AGAT-converted and cleanup results. The AGAT stage
references follow `docs/tool_refs/agat.md` and the repo's README-backed
workflow boundaries.
"""

from __future__ import annotations

from flyte.io import Dir

from flytetest.config import agat_cleanup_env, agat_conversion_env, agat_env
from flytetest.tasks.agat import agat_cleanup_gff3, agat_convert_sp_gxf2gxf, agat_statistics


@agat_env.task
def annotation_postprocess_agat(
    eggnog_results: Dir,
    annotation_fasta_path: str = "",
    agat_sif: str = "",
) -> Dir:
    """Collect AGAT statistics for the EggNOG-annotated GFF3 boundary."""
    return agat_statistics(
        eggnog_results=eggnog_results,
        annotation_fasta_path=annotation_fasta_path,
        agat_sif=agat_sif,
    )


@agat_conversion_env.task
def annotation_postprocess_agat_conversion(
    eggnog_results: Dir,
    agat_sif: str = "",
) -> Dir:
    """Convert the EggNOG-annotated GFF3 boundary with AGAT."""
    return agat_convert_sp_gxf2gxf(
        eggnog_results=eggnog_results,
        agat_sif=agat_sif,
    )


@agat_cleanup_env.task
def annotation_postprocess_agat_cleanup(
    agat_conversion_results: Dir,
) -> Dir:
    """Apply the deterministic attribute cleanup slice to AGAT output."""
    return agat_cleanup_gff3(
        agat_conversion_results=agat_conversion_results,
    )


__all__ = [
    "annotation_postprocess_agat",
    "annotation_postprocess_agat_cleanup",
    "annotation_postprocess_agat_conversion",
]
