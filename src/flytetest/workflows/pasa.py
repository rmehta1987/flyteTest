"""PASA workflow entrypoints for FLyteTest.

This module runs PASA align/assemble from the internally collected transcript
bundle and adds post-EVM PASA annotation refinement with explicit update
rounds.
"""

from __future__ import annotations

from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import pasa_env, pasa_update_env, require_path
from flytetest.tasks.pasa import (
    _sample_id_from_transcript_evidence,
    _stringtie_gtf,
    _trinity_denovo_fasta,
    _trinity_gg_fasta,
    collect_pasa_results,
    collect_pasa_update_results,
    combine_trinity_fastas,
    finalize_pasa_update_outputs,
    pasa_accession_extract,
    pasa_align_assemble,
    pasa_create_sqlite_db,
    pasa_load_current_annotations,
    pasa_seqclean,
    pasa_update_gene_models,
    prepare_pasa_update_inputs,
)


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@pasa_env.task
def pasa_transcript_alignment(
    genome: File,
    transcript_evidence_results: Dir,
    univec_fasta: File,
    pasa_config_template: File,
    pasa_sif: str = "",
    seqclean_threads: int = 4,
    pasa_cpu: int = 4,
    pasa_max_intron_length: int = 100000,
    pasa_aligners: str = "blat,gmap,minimap2",
    pasa_db_name: str = "pasa.sqlite",
) -> Dir:
    """Run PASA align/assemble from the collected transcript-evidence bundle."""
    transcript_evidence_path = require_path(
        Path(transcript_evidence_results.download_sync()),
        "Transcript evidence results directory",
    )
    trinity_denovo_dir = require_path(
        transcript_evidence_path / "trinity_denovo",
        "Transcript evidence Trinity de novo directory",
    )
    trinity_gg_dir = require_path(
        transcript_evidence_path / "trinity_gg",
        "Transcript evidence Trinity genome-guided directory",
    )
    stringtie_dir = require_path(
        transcript_evidence_path / "stringtie",
        "Transcript evidence StringTie directory",
    )

    trinity_denovo_fasta = File(path=str(_trinity_denovo_fasta(trinity_denovo_dir)))
    trinity_gg_fasta = File(path=str(_trinity_gg_fasta(trinity_gg_dir)))
    stringtie_gtf = File(path=str(_stringtie_gtf(stringtie_dir)))
    sample_id = _sample_id_from_transcript_evidence(transcript_evidence_path)

    combined_trinity = combine_trinity_fastas(
        genome_guided_trinity_fasta=trinity_gg_fasta,
        denovo_trinity_fasta=trinity_denovo_fasta,
    )

    tdn_accs = pasa_accession_extract(
        denovo_trinity_fasta=trinity_denovo_fasta,
        pasa_sif=pasa_sif,
    )

    cleaned_transcripts = pasa_seqclean(
        transcripts=combined_trinity,
        univec_fasta=univec_fasta,
        pasa_sif=pasa_sif,
        seqclean_threads=seqclean_threads,
    )
    pasa_config = pasa_create_sqlite_db(
        pasa_config_template=pasa_config_template,
        pasa_db_name=pasa_db_name,
    )
    pasa_run = pasa_align_assemble(
        genome=genome,
        cleaned_transcripts=cleaned_transcripts,
        unclean_transcripts=combined_trinity,
        stringtie_gtf=stringtie_gtf,
        pasa_config=pasa_config,
        pasa_sif=pasa_sif,
        pasa_aligners=pasa_aligners,
        pasa_cpu=pasa_cpu,
        pasa_max_intron_length=pasa_max_intron_length,
        tdn_accs=tdn_accs,
    )
    return collect_pasa_results(
        genome=genome,
        transcript_evidence_results=transcript_evidence_results,
        univec_fasta=univec_fasta,
        combined_trinity=combined_trinity,
        seqclean=cleaned_transcripts,
        pasa_config=pasa_config,
        pasa_run=pasa_run,
        stringtie_gtf=stringtie_gtf,
        sample_id=sample_id,
        trinity_denovo_fasta=trinity_denovo_fasta,
        tdn_accs=tdn_accs,
    )


@pasa_update_env.task
def annotation_refinement_pasa(
    pasa_results: Dir,
    evm_results: Dir,
    pasa_annot_compare_template: File,
    fasta36_binary_path: str = "",
    load_current_annotations_script: str = "Load_Current_Gene_Annotations.dbi",
    pasa_update_script: str = "Launch_PASA_pipeline.pl",
    gff3sort_script: str = "gff3sort.pl",
    pasa_update_rounds: int = 2,
    pasa_sif: str = "",
    pasa_update_cpu: int = 8,
) -> Dir:
    """Run the note-backed PASA post-EVM annotation-refinement rounds."""
    if pasa_update_rounds < 2:
        raise ValueError(
            "annotation_refinement_pasa requires at least two PASA update rounds to match the notes-backed milestone contract."
        )

    staged_inputs = prepare_pasa_update_inputs(
        pasa_results=pasa_results,
        evm_results=evm_results,
        pasa_annot_compare_template=pasa_annot_compare_template,
        fasta36_binary_path=fasta36_binary_path,
    )

    load_rounds: list[Dir] = []
    update_rounds: list[Dir] = []
    current_workspace = staged_inputs
    for round_index in range(1, pasa_update_rounds + 1):
        loaded_round = pasa_load_current_annotations(
            pasa_update_inputs=current_workspace,
            round_index=round_index,
            load_current_annotations_script=load_current_annotations_script,
            pasa_sif=pasa_sif,
        )
        updated_round = pasa_update_gene_models(
            loaded_pasa_update=loaded_round,
            round_index=round_index,
            pasa_update_script=pasa_update_script,
            pasa_sif=pasa_sif,
            pasa_update_cpu=pasa_update_cpu,
        )
        load_rounds.append(loaded_round)
        update_rounds.append(updated_round)
        current_workspace = updated_round

    finalized_outputs = finalize_pasa_update_outputs(
        pasa_update_round=current_workspace,
        gff3sort_script=gff3sort_script,
        pasa_sif=pasa_sif,
    )
    return collect_pasa_update_results(
        pasa_results=pasa_results,
        evm_results=evm_results,
        pasa_update_inputs=staged_inputs,
        load_rounds=load_rounds,
        update_rounds=update_rounds,
        finalized_outputs=finalized_outputs,
    )


__all__ = ["annotation_refinement_pasa", "pasa_transcript_alignment"]
