from __future__ import annotations

from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import require_path, transdecoder_env
from flytetest.tasks.pasa import _pasa_assemblies_fasta, _pasa_assemblies_gff3, _sqlite_db_path
from flytetest.tasks.transdecoder import (
    _sample_id_from_pasa_results,
    collect_transdecoder_results,
    transdecoder_train_from_pasa,
)


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@transdecoder_env.task
def transdecoder_from_pasa(
    pasa_results: Dir,
    transdecoder_sif: str = "",
    transdecoder_min_protein_length: int = 100,
    transdecoder_genome_orf_script: str = "cdna_alignment_orf_to_genome_orf.pl",
) -> Dir:
    pasa_results_path = require_path(Path(pasa_results.download_sync()), "PASA results directory")
    pasa_dir = require_path(
        pasa_results_path / "pasa",
        "PASA output directory from pasa_transcript_alignment",
    )
    config_dir = require_path(
        pasa_results_path / "config",
        "PASA config directory from pasa_transcript_alignment",
    )
    database_name = _sqlite_db_path(config_dir).name

    pasa_assemblies_fasta = _pasa_assemblies_fasta(pasa_dir, database_name)
    pasa_assemblies_gff3 = _pasa_assemblies_gff3(pasa_dir, database_name)
    if pasa_assemblies_fasta is None:
        raise FileNotFoundError(
            f"PASA assemblies FASTA not found under {pasa_dir}; expected output from pasa_transcript_alignment."
        )
    if pasa_assemblies_gff3 is None:
        raise FileNotFoundError(
            f"PASA assemblies GFF3 not found under {pasa_dir}; expected output from pasa_transcript_alignment."
        )

    transdecoder_run = transdecoder_train_from_pasa(
        pasa_assemblies_fasta=File(path=str(pasa_assemblies_fasta)),
        pasa_assemblies_gff3=File(path=str(pasa_assemblies_gff3)),
        transdecoder_sif=transdecoder_sif,
        transdecoder_min_protein_length=transdecoder_min_protein_length,
        transdecoder_genome_orf_script=transdecoder_genome_orf_script,
    )
    return collect_transdecoder_results(
        pasa_results=pasa_results,
        transdecoder_run=transdecoder_run,
        sample_id=_sample_id_from_pasa_results(pasa_results_path),
    )
