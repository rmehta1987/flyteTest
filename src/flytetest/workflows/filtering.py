"""Repeat-filtering workflow entrypoint for the post-PASA FLyteTest milestone.

This module starts from the PASA-updated annotation bundle, applies the
repeat-filtering toolchain, and stops at repeat-free GFF3 plus protein FASTA
outputs before functional annotation.

Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
input/output expectations follow the tool references under `docs/tool_refs/`
(notably `repeatmasker.md`, `gffread.md`, and `funannotate.md`).
"""

from __future__ import annotations

from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import repeat_filter_env, require_path
from flytetest.tasks.filtering import (
    _filtered_gff3_path,
    _models_to_remove_path,
    _pasa_update_reference_genome,
    _pasa_update_sorted_gff3,
    _repeatmasker_bed_path,
    _sanitized_protein_fasta,
    collect_repeat_filter_results,
    funannotate_remove_bad_models,
    funannotate_repeat_blast,
    gffread_proteins,
    remove_overlap_repeat_models,
    remove_repeat_blast_hits,
    repeatmasker_out_to_bed,
)


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@repeat_filter_env.task
def annotation_repeat_filtering(
    pasa_update_results: Dir,
    repeatmasker_out: File,
    funannotate_db_path: str,
    rmout_to_gff3_script: str = "rmOutToGFF3.pl",
    gffread_binary: str = "gffread",
    funannotate_python: str = "python3",
    repeat_filter_sif: str = "",
    min_protlen: int = 50,
    repeat_blast_cpu: int = 1,
    repeat_blast_evalue: float = 1e-10,
) -> Dir:
    """Run repeat filtering and cleanup strictly downstream of PASA post-EVM refinement."""
    pasa_update_dir = require_path(
        Path(pasa_update_results.download_sync()),
        "PASA post-EVM refinement results directory",
    )
    annotation_gff3 = File(path=str(_pasa_update_sorted_gff3(pasa_update_dir)))
    genome_fasta = File(path=str(_pasa_update_reference_genome(pasa_update_dir)))

    repeatmasker_conversion = repeatmasker_out_to_bed(
        repeatmasker_out=repeatmasker_out,
        rmout_to_gff3_script=rmout_to_gff3_script,
        repeat_filter_sif=repeat_filter_sif,
    )

    initial_proteins = gffread_proteins(
        annotation_gff3=annotation_gff3,
        genome_fasta=genome_fasta,
        protein_output_stem="post_pasa_updates",
        gffread_binary=gffread_binary,
        repeat_filter_sif=repeat_filter_sif,
    )

    overlap_filter = funannotate_remove_bad_models(
        annotation_gff3=annotation_gff3,
        proteins_fasta=File(path=str(_sanitized_protein_fasta(Path(initial_proteins.download_sync())))),
        repeatmasker_bed=File(
            path=str(_repeatmasker_bed_path(Path(repeatmasker_conversion.download_sync())))
        ),
        clean_output_name="post_pasa_updates.clean.gff3",
        funannotate_python=funannotate_python,
        repeat_filter_sif=repeat_filter_sif,
        min_protlen=min_protlen,
    )

    overlap_removed = remove_overlap_repeat_models(
        annotation_gff3=annotation_gff3,
        models_to_remove=File(path=str(_models_to_remove_path(Path(overlap_filter.download_sync())))),
        output_name="bed_repeats_removed.gff3",
    )

    bed_filtered_gff3 = File(path=str(_filtered_gff3_path(Path(overlap_removed.download_sync()))))
    bed_filtered_proteins = gffread_proteins(
        annotation_gff3=bed_filtered_gff3,
        genome_fasta=genome_fasta,
        protein_output_stem="bed_repeats_removed",
        gffread_binary=gffread_binary,
        repeat_filter_sif=repeat_filter_sif,
    )

    repeat_blast = funannotate_repeat_blast(
        proteins_fasta=File(
            path=str(_sanitized_protein_fasta(Path(bed_filtered_proteins.download_sync())))
        ),
        funannotate_db_path=funannotate_db_path,
        funannotate_python=funannotate_python,
        repeat_filter_sif=repeat_filter_sif,
        repeat_blast_cpu=repeat_blast_cpu,
        repeat_blast_evalue=repeat_blast_evalue,
    )

    blast_removed = remove_repeat_blast_hits(
        annotation_gff3=bed_filtered_gff3,
        repeat_blast_results=repeat_blast,
        output_name="all_repeats_removed.gff3",
    )

    final_proteins = gffread_proteins(
        annotation_gff3=File(path=str(_filtered_gff3_path(Path(blast_removed.download_sync())))),
        genome_fasta=genome_fasta,
        protein_output_stem="all_repeats_removed",
        gffread_binary=gffread_binary,
        repeat_filter_sif=repeat_filter_sif,
    )

    return collect_repeat_filter_results(
        pasa_update_results=pasa_update_results,
        repeatmasker_conversion=repeatmasker_conversion,
        initial_proteins=initial_proteins,
        overlap_filter=overlap_filter,
        overlap_removed=overlap_removed,
        bed_filtered_proteins=bed_filtered_proteins,
        repeat_blast=repeat_blast,
        blast_removed=blast_removed,
        final_proteins=final_proteins,
    )


__all__ = ["annotation_repeat_filtering"]
