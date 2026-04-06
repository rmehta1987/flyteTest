"""Consensus-stage workflow entrypoints for FLyteTest.

This module preserves the note-faithful pre-EVM bundle workflow and adds the
downstream deterministic EVidenceModeler execution workflow that consumes it.
"""

from __future__ import annotations

from flyte.io import Dir

from flytetest.config import consensus_env
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


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@consensus_env.task
def consensus_annotation_evm_prep(
    pasa_results: Dir,
    transdecoder_results: Dir,
    protein_evidence_results: Dir,
    braker3_results: Dir,
) -> Dir:
    """Assemble the corrected pre-EVM file contract from upstream evidence bundles."""
    transcript_inputs = prepare_evm_transcript_inputs(
        pasa_results=pasa_results,
    )
    protein_inputs = prepare_evm_protein_inputs(
        protein_evidence_results=protein_evidence_results,
    )
    prediction_inputs = prepare_evm_prediction_inputs(
        transdecoder_results=transdecoder_results,
        braker3_results=braker3_results,
    )
    return collect_evm_prep_results(
        transcript_inputs=transcript_inputs,
        protein_inputs=protein_inputs,
        prediction_inputs=prediction_inputs,
        pasa_results=pasa_results,
        transdecoder_results=transdecoder_results,
        protein_evidence_results=protein_evidence_results,
        braker3_results=braker3_results,
    )


@consensus_env.task
def consensus_annotation_evm(
    evm_prep_results: Dir,
    evm_weights_text: str = "",
    evm_partition_script: str = "partition_EVM_inputs.pl",
    evm_write_commands_script: str = "write_EVM_commands.pl",
    evm_recombine_script: str = "recombine_EVM_partial_outputs.pl",
    evm_convert_script: str = "convert_EVM_outputs_to_GFF3.pl",
    gff3sort_script: str = "gff3sort.pl",
    evm_output_file_name: str = "evm.out",
    evm_segment_size: int = 3000000,
    evm_overlap_size: int = 300000,
    evm_sif: str = "",
) -> Dir:
    """Run deterministic EVM execution downstream of the existing pre-EVM bundle."""
    execution_inputs = prepare_evm_execution_inputs(
        evm_prep_results=evm_prep_results,
        evm_weights_text=evm_weights_text,
    )
    partitioned = evm_partition_inputs(
        evm_execution_inputs=execution_inputs,
        evm_partition_script=evm_partition_script,
        evm_segment_size=evm_segment_size,
        evm_overlap_size=evm_overlap_size,
        evm_sif=evm_sif,
    )
    commands = evm_write_commands(
        partitioned_evm_inputs=partitioned,
        evm_write_commands_script=evm_write_commands_script,
        evm_output_file_name=evm_output_file_name,
        evm_sif=evm_sif,
    )
    executed = evm_execute_commands(
        evm_commands=commands,
        evm_sif=evm_sif,
    )
    recombined = evm_recombine_outputs(
        executed_evm_commands=executed,
        evm_recombine_script=evm_recombine_script,
        evm_convert_script=evm_convert_script,
        gff3sort_script=gff3sort_script,
        evm_output_file_name=evm_output_file_name,
        evm_sif=evm_sif,
    )
    return collect_evm_results(
        evm_prep_results=evm_prep_results,
        evm_execution_inputs=execution_inputs,
        partitioned_evm_inputs=partitioned,
        evm_commands=commands,
        executed_evm_commands=executed,
        recombined_evm_outputs=recombined,
    )


__all__ = ["consensus_annotation_evm", "consensus_annotation_evm_prep"]
