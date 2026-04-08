"""AGAT workflow entrypoints for the post-EggNOG milestone slices."""

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
    """Run the AGAT statistics slice on an EggNOG-annotated GFF3 bundle."""
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
    """Run the AGAT conversion slice on an EggNOG-annotated GFF3 bundle."""
    return agat_convert_sp_gxf2gxf(
        eggnog_results=eggnog_results,
        agat_sif=agat_sif,
    )


@agat_cleanup_env.task
def annotation_postprocess_agat_cleanup(
    agat_conversion_results: Dir,
) -> Dir:
    """Run the AGAT cleanup slice on an AGAT-converted GFF3 bundle."""
    return agat_cleanup_gff3(
        agat_conversion_results=agat_conversion_results,
    )


__all__ = [
    "annotation_postprocess_agat",
    "annotation_postprocess_agat_cleanup",
    "annotation_postprocess_agat_conversion",
]
