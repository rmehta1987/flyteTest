from __future__ import annotations

import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from flytetest.tasks.qc import fastqc
from flytetest.tasks.quant import collect_results, salmon_index, salmon_quant
from flytetest.tasks.pasa import (
    collect_pasa_results,
    combine_trinity_fastas,
    pasa_accession_extract,
    pasa_align_assemble,
    pasa_create_sqlite_db,
    pasa_seqclean,
)
from flytetest.tasks.transdecoder import collect_transdecoder_results, transdecoder_train_from_pasa
from flytetest.tasks.transcript_evidence import (
    collect_transcript_evidence_results,
    samtools_merge_bams,
    star_align_sample,
    star_genome_index,
    stringtie_assemble,
    trinity_genome_guided_assemble,
)
from flytetest.workflows.pasa import pasa_transcript_alignment
from flytetest.workflows.rnaseq_qc_quant import rnaseq_qc_quant
from flytetest.workflows.transdecoder import transdecoder_from_pasa
from flytetest.workflows.transcript_evidence import transcript_evidence_generation

__all__ = [
    "collect_pasa_results",
    "collect_results",
    "collect_transdecoder_results",
    "collect_transcript_evidence_results",
    "combine_trinity_fastas",
    "fastqc",
    "pasa_accession_extract",
    "pasa_align_assemble",
    "pasa_create_sqlite_db",
    "pasa_seqclean",
    "pasa_transcript_alignment",
    "rnaseq_qc_quant",
    "salmon_index",
    "salmon_quant",
    "samtools_merge_bams",
    "star_align_sample",
    "star_genome_index",
    "stringtie_assemble",
    "transdecoder_from_pasa",
    "transdecoder_train_from_pasa",
    "transcript_evidence_generation",
    "trinity_genome_guided_assemble",
]
