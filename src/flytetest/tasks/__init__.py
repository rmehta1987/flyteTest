"""Task exports for the implemented FLyteTest pipeline stages.

    This package-level shim keeps optional task families importable from one place
    while newer annotation modules continue to land incrementally.
"""

from importlib.util import find_spec

if find_spec("flytetest.tasks.annotation") is not None:
    from flytetest.tasks.annotation import (
        braker3_predict,
        collect_braker3_results,
        normalize_braker3_for_evm,
        stage_braker3_inputs,
    )

    _annotation_exports = (
        "braker3_predict",
        "collect_braker3_results",
        "normalize_braker3_for_evm",
        "stage_braker3_inputs",
    )
else:
    _annotation_exports = ()

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

    _consensus_exports = (
        "collect_evm_results",
        "collect_evm_prep_results",
        "evm_execute_commands",
        "evm_partition_inputs",
        "evm_recombine_outputs",
        "evm_write_commands",
        "prepare_evm_execution_inputs",
        "prepare_evm_prediction_inputs",
        "prepare_evm_protein_inputs",
        "prepare_evm_transcript_inputs",
    )
else:
    _consensus_exports = ()

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

    _filtering_exports = (
        "collect_repeat_filter_results",
        "funannotate_remove_bad_models",
        "funannotate_repeat_blast",
        "gffread_proteins",
        "remove_overlap_repeat_models",
        "remove_repeat_blast_hits",
        "repeatmasker_out_to_bed",
    )
else:
    _filtering_exports = ()

if find_spec("flytetest.tasks.functional") is not None:
    from flytetest.tasks.functional import (
        busco_assess_proteins,
        collect_busco_results,
    )

    _functional_exports = (
        "busco_assess_proteins",
        "collect_busco_results",
    )
else:
    _functional_exports = ()

if find_spec("flytetest.tasks.eggnog") is not None:
    from flytetest.tasks.eggnog import collect_eggnog_results, eggnog_map

    _eggnog_exports = (
        "collect_eggnog_results",
        "eggnog_map",
    )
else:
    _eggnog_exports = ()

if find_spec("flytetest.tasks.agat") is not None:
    from flytetest.tasks.agat import agat_cleanup_gff3, agat_convert_sp_gxf2gxf, agat_statistics

    _agat_exports = ("agat_cleanup_gff3", "agat_convert_sp_gxf2gxf", "agat_statistics")
else:
    _agat_exports = ()

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
from flytetest.tasks.qc import fastqc
from flytetest.tasks.quant import collect_results, salmon_index, salmon_quant
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

if find_spec("flytetest.tasks.protein_evidence") is not None:
    from flytetest.tasks.protein_evidence import (
        chunk_protein_fastas,
        exonerate_align_chunk,
        exonerate_concat_results,
        exonerate_to_evm_gff3,
        stage_protein_fastas,
    )

    _protein_exports = (
        "chunk_protein_fastas",
        "exonerate_align_chunk",
        "exonerate_concat_results",
        "exonerate_to_evm_gff3",
        "stage_protein_fastas",
    )
else:
    _protein_exports = ()

__all__ = [
    *_annotation_exports,
    *_consensus_exports,
    *_filtering_exports,
    *_functional_exports,
    *_eggnog_exports,
    *_agat_exports,
    "collect_pasa_results",
    "collect_pasa_update_results",
    "collect_results",
    "collect_transdecoder_results",
    "collect_transcript_evidence_results",
    "combine_trinity_fastas",
    "fastqc",
    "finalize_pasa_update_outputs",
    "pasa_accession_extract",
    "pasa_align_assemble",
    "pasa_create_sqlite_db",
    "pasa_load_current_annotations",
    "pasa_seqclean",
    "pasa_update_gene_models",
    "prepare_pasa_update_inputs",
    "salmon_index",
    "salmon_quant",
    "samtools_merge_bams",
    "star_align_sample",
    "star_genome_index",
    "stringtie_assemble",
    "transdecoder_train_from_pasa",
    "trinity_denovo_assemble",
    "trinity_genome_guided_assemble",
    *_protein_exports,
]
