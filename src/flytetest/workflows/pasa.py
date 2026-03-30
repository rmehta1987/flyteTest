from __future__ import annotations

from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import pasa_env, require_path
from flytetest.tasks.pasa import (
    _sample_id_from_transcript_evidence,
    _stringtie_gtf,
    _trinity_gg_fasta,
    collect_pasa_results,
    combine_trinity_fastas,
    pasa_accession_extract,
    pasa_align_assemble,
    pasa_create_sqlite_db,
    pasa_seqclean,
)


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@pasa_env.task
def pasa_transcript_alignment(
    genome: File,
    transcript_evidence_results: Dir,
    univec_fasta: File,
    pasa_config_template: File,
    trinity_denovo_fasta_path: str = "",
    pasa_sif: str = "",
    seqclean_threads: int = 4,
    pasa_cpu: int = 4,
    pasa_max_intron_length: int = 100000,
    pasa_aligners: str = "blat,gmap,minimap2",
    pasa_db_name: str = "pasa.sqlite",
) -> Dir:
    transcript_evidence_path = require_path(
        Path(transcript_evidence_results.download_sync()),
        "Transcript evidence results directory",
    )
    trinity_gg_dir = require_path(
        transcript_evidence_path / "trinity_gg",
        "Transcript evidence Trinity genome-guided directory",
    )
    stringtie_dir = require_path(
        transcript_evidence_path / "stringtie",
        "Transcript evidence StringTie directory",
    )

    trinity_gg_fasta = File(path=str(_trinity_gg_fasta(trinity_gg_dir)))
    stringtie_gtf = File(path=str(_stringtie_gtf(stringtie_dir)))
    sample_id = _sample_id_from_transcript_evidence(transcript_evidence_path)

    combined_trinity = combine_trinity_fastas(
        genome_guided_trinity_fasta=trinity_gg_fasta,
        denovo_trinity_fasta_path=trinity_denovo_fasta_path,
    )

    tdn_accs_path = ""
    if trinity_denovo_fasta_path:
        tdn_accs = pasa_accession_extract(
            denovo_trinity_fasta=File(path=trinity_denovo_fasta_path),
            pasa_sif=pasa_sif,
        )
        tdn_accs_path = str(tdn_accs.path)

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
        tdn_accs_path=tdn_accs_path,
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
        trinity_denovo_fasta_path=trinity_denovo_fasta_path,
        tdn_accs_path=tdn_accs_path,
    )
