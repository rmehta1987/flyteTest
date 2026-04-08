"""Compatibility exports for `flyte run` against the FLyteTest package layout.

This module preserves the original single-file entry surface while the real
task and workflow implementations now live under `src/flytetest/`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from importlib.util import find_spec


SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if find_spec("flytetest.tasks.annotation") is not None:
    from flytetest.tasks.annotation import (
        braker3_predict,
        collect_braker3_results,
        normalize_braker3_for_evm,
        stage_braker3_inputs,
    )
else:
    braker3_predict = None
    collect_braker3_results = None
    normalize_braker3_for_evm = None
    stage_braker3_inputs = None

if find_spec("flytetest.tasks.consensus") is not None:
    from flytetest.tasks.consensus import (
        collect_evm_results,
        collect_evm_prep_results,
        evm_execute_commands,
        evm_partition_inputs,
        evm_recombine_outputs,
        evm_write_commands,
        prepare_evm_execution_inputs,
        prepare_evm_prediction_inputs,
        prepare_evm_protein_inputs,
        prepare_evm_transcript_inputs,
    )
else:
    collect_evm_results = None
    collect_evm_prep_results = None
    evm_execute_commands = None
    evm_partition_inputs = None
    evm_recombine_outputs = None
    evm_write_commands = None
    prepare_evm_execution_inputs = None
    prepare_evm_prediction_inputs = None
    prepare_evm_protein_inputs = None
    prepare_evm_transcript_inputs = None

if find_spec("flytetest.tasks.filtering") is not None:
    from flytetest.tasks.filtering import (
        collect_repeat_filter_results,
        funannotate_remove_bad_models,
        funannotate_repeat_blast,
        gffread_proteins,
        remove_overlap_repeat_models,
        remove_repeat_blast_hits,
        repeatmasker_out_to_bed,
    )
else:
    collect_repeat_filter_results = None
    funannotate_remove_bad_models = None
    funannotate_repeat_blast = None
    gffread_proteins = None
    remove_overlap_repeat_models = None
    remove_repeat_blast_hits = None
    repeatmasker_out_to_bed = None

if find_spec("flytetest.tasks.functional") is not None:
    from flytetest.tasks.functional import busco_assess_proteins, collect_busco_results
else:
    busco_assess_proteins = None
    collect_busco_results = None

if find_spec("flytetest.tasks.eggnog") is not None:
    from flytetest.tasks.eggnog import collect_eggnog_results, eggnog_map
else:
    collect_eggnog_results = None
    eggnog_map = None

if find_spec("flytetest.tasks.agat") is not None:
    from flytetest.tasks.agat import agat_cleanup_gff3, agat_convert_sp_gxf2gxf, agat_statistics
else:
    agat_cleanup_gff3 = None
    agat_convert_sp_gxf2gxf = None
    agat_statistics = None

from flytetest.tasks.qc import fastqc
from flytetest.tasks.quant import collect_results, salmon_index, salmon_quant
from flytetest.tasks.pasa import (
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
from flytetest.tasks.transdecoder import collect_transdecoder_results, transdecoder_train_from_pasa
from flytetest.tasks.transcript_evidence import (
    collect_transcript_evidence_results,
    samtools_merge_bams,
    star_align_sample,
    star_genome_index,
    stringtie_assemble,
    trinity_denovo_assemble,
    trinity_genome_guided_assemble,
)
if find_spec("flytetest.workflows.annotation") is not None:
    from flytetest.workflows.annotation import ab_initio_annotation_braker3
else:
    ab_initio_annotation_braker3 = None

if find_spec("flytetest.workflows.consensus") is not None:
    from flytetest.workflows.consensus import consensus_annotation_evm, consensus_annotation_evm_prep
else:
    consensus_annotation_evm = None
    consensus_annotation_evm_prep = None

if find_spec("flytetest.workflows.filtering") is not None:
    from flytetest.workflows.filtering import annotation_repeat_filtering
else:
    annotation_repeat_filtering = None

if find_spec("flytetest.workflows.functional") is not None:
    from flytetest.workflows.functional import annotation_qc_busco
else:
    annotation_qc_busco = None

if find_spec("flytetest.workflows.eggnog") is not None:
    from flytetest.workflows.eggnog import annotation_functional_eggnog
else:
    annotation_functional_eggnog = None

if find_spec("flytetest.workflows.agat") is not None:
    from flytetest.workflows.agat import (
        annotation_postprocess_agat,
        annotation_postprocess_agat_cleanup,
        annotation_postprocess_agat_conversion,
    )
else:
    annotation_postprocess_agat = None
    annotation_postprocess_agat_cleanup = None
    annotation_postprocess_agat_conversion = None

from flytetest.workflows.pasa import annotation_refinement_pasa, pasa_transcript_alignment
from flytetest.workflows.rnaseq_qc_quant import rnaseq_qc_quant
from flytetest.workflows.transdecoder import transdecoder_from_pasa
from flytetest.workflows.transcript_evidence import transcript_evidence_generation

if find_spec("flytetest.tasks.protein_evidence") is not None:
    from flytetest.tasks.protein_evidence import (
        chunk_protein_fastas,
        exonerate_align_chunk,
        exonerate_concat_results,
        exonerate_to_evm_gff3,
        stage_protein_fastas,
    )
else:
    chunk_protein_fastas = None
    exonerate_align_chunk = None
    exonerate_concat_results = None
    exonerate_to_evm_gff3 = None
    stage_protein_fastas = None

if find_spec("flytetest.workflows.protein_evidence") is not None:
    from flytetest.workflows.protein_evidence import protein_evidence_alignment
else:
    protein_evidence_alignment = None

__all__ = [
    "ab_initio_annotation_braker3",
    "agat_cleanup_gff3",
    "agat_convert_sp_gxf2gxf",
    "braker3_predict",
    "busco_assess_proteins",
    "collect_eggnog_results",
    "collect_busco_results",
    "collect_braker3_results",
    "collect_evm_results",
    "collect_evm_prep_results",
    "collect_pasa_results",
    "collect_pasa_update_results",
    "collect_repeat_filter_results",
    "collect_results",
    "collect_transdecoder_results",
    "collect_transcript_evidence_results",
    "combine_trinity_fastas",
    "fastqc",
    "finalize_pasa_update_outputs",
    "annotation_refinement_pasa",
    "annotation_functional_eggnog",
    "annotation_postprocess_agat",
    "annotation_postprocess_agat_cleanup",
    "annotation_postprocess_agat_conversion",
    "annotation_repeat_filtering",
    "annotation_qc_busco",
    "funannotate_remove_bad_models",
    "funannotate_repeat_blast",
    "gffread_proteins",
    "pasa_accession_extract",
    "pasa_align_assemble",
    "pasa_create_sqlite_db",
    "pasa_load_current_annotations",
    "pasa_seqclean",
    "pasa_update_gene_models",
    "pasa_transcript_alignment",
    "protein_evidence_alignment",
    "remove_overlap_repeat_models",
    "remove_repeat_blast_hits",
    "rnaseq_qc_quant",
    "salmon_index",
    "salmon_quant",
    "repeatmasker_out_to_bed",
    "eggnog_map",
    "agat_statistics",
    "chunk_protein_fastas",
    "exonerate_align_chunk",
    "exonerate_concat_results",
    "exonerate_to_evm_gff3",
    "evm_execute_commands",
    "evm_partition_inputs",
    "evm_recombine_outputs",
    "evm_write_commands",
    "normalize_braker3_for_evm",
    "prepare_evm_execution_inputs",
    "prepare_evm_prediction_inputs",
    "prepare_evm_protein_inputs",
    "prepare_evm_transcript_inputs",
    "prepare_pasa_update_inputs",
    "samtools_merge_bams",
    "star_align_sample",
    "star_genome_index",
    "stage_braker3_inputs",
    "stringtie_assemble",
    "stage_protein_fastas",
    "consensus_annotation_evm",
    "transdecoder_from_pasa",
    "transdecoder_train_from_pasa",
    "consensus_annotation_evm_prep",
    "transcript_evidence_generation",
    "trinity_denovo_assemble",
    "trinity_genome_guided_assemble",
]
