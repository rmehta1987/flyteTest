"""Registry entries for the evm pipeline family."""

from __future__ import annotations

from flytetest.registry._types import (
    InterfaceField,
    RegistryCompatibilityMetadata,
    RegistryEntry,
)


EVM_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name='consensus_annotation_evm_prep',
        category='workflow',
        description='Consensus annotation preparation workflow that assembles the note-faithful pre-EVM contract from PASA, TransDecoder, protein evidence, and BRAKER3 results and stops before EVM execution.',
        inputs=(
            InterfaceField('pasa_results', 'Dir', 'PASA results directory from pasa_transcript_alignment.'),
            InterfaceField('transdecoder_results', 'Dir', 'TransDecoder results directory from transdecoder_from_pasa.'),
            InterfaceField('protein_evidence_results', 'Dir', 'Protein evidence results directory from protein_evidence_alignment.'),
            InterfaceField('braker3_results', 'Dir', 'BRAKER3 results directory from ab_initio_annotation_braker3.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped pre-EVM directory with `transcripts.gff3`, `predictions.gff3`, `proteins.gff3`, the authoritative reference genome, and run_manifest.json.'),
        ),
        tags=('workflow', 'consensus', 'evm', 'prep'),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage='pre-EVM consensus input preparation',
            accepted_planner_types=('TranscriptEvidenceSet', 'ProteinEvidenceSet', 'AnnotationEvidenceSet',),
            produced_planner_types=('AnnotationEvidenceSet',),
            reusable_as_reference=True,
            execution_defaults={
            'profile': 'local',
            'result_manifest': 'run_manifest.json',
            'resources': {'cpu': '16', 'memory': '64Gi', 'execution_class': 'local'},
            'slurm_resource_hints': {'cpu': '16', 'memory': '64Gi', 'walltime': '02:00:00'},
        },
            supported_execution_profiles=('local', 'slurm',),
            synthesis_eligible=True,
            composition_constraints=('Assembles transcripts.gff3, predictions.gff3, and proteins.gff3 but does not execute EVM.',),
            pipeline_family='annotation',
            pipeline_stage_order=6,
        ),
    ),
    RegistryEntry(
        name='consensus_annotation_evm',
        category='workflow',
        description='Consensus annotation workflow that consumes the existing pre-EVM bundle, stages EVM execution inputs, partitions deterministically, generates commands, executes them sequentially, recombines outputs, and collects a manifest-bearing EVM results bundle.',
        inputs=(
            InterfaceField('evm_prep_results', 'Dir', 'Pre-EVM bundle from consensus_annotation_evm_prep.'),
            InterfaceField('evm_weights_text', 'str', 'Optional explicit EVM weights content. When empty, the workflow uses the documented inferred repo-local weights adaptation.'),
            InterfaceField('evm_partition_script', 'str', 'partition_EVM_inputs.pl path or executable name.'),
            InterfaceField('evm_write_commands_script', 'str', 'write_EVM_commands.pl path or executable name.'),
            InterfaceField('evm_recombine_script', 'str', 'recombine_EVM_partial_outputs.pl path or executable name.'),
            InterfaceField('evm_convert_script', 'str', 'convert_EVM_outputs_to_GFF3.pl path or executable name.'),
            InterfaceField('gff3sort_script', 'str', 'Optional gff3sort.pl path or executable name. When empty, sorting is skipped explicitly.'),
            InterfaceField('evm_output_file_name', 'str', 'EVM output basename; defaults to evm.out.'),
            InterfaceField('evm_segment_size', 'int', 'Segment size passed to EVM partitioning; defaults to the value shown in the notes.'),
            InterfaceField('evm_overlap_size', 'int', 'Overlap size passed to EVM partitioning; defaults to the value shown in the notes.'),
            InterfaceField('evm_sif', 'str', 'Optional Apptainer/Singularity image path for EVM utilities.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped EVM results directory containing copied stage outputs, evm.weights, partitions_list.out, commands.list, final GFF3 files, and run_manifest.json.'),
        ),
        tags=('workflow', 'consensus', 'evm', 'execution'),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage='EVidenceModeler consensus annotation',
            accepted_planner_types=('AnnotationEvidenceSet',),
            produced_planner_types=('ConsensusAnnotation',),
            reusable_as_reference=True,
            execution_defaults={
            'profile': 'local',
            'result_manifest': 'run_manifest.json',
            'resources': {'cpu': '16', 'memory': '64Gi', 'execution_class': 'local'},
            'slurm_resource_hints': {'cpu': '16', 'memory': '64Gi', 'walltime': '04:00:00'},
        },
            supported_execution_profiles=('local', 'slurm',),
            synthesis_eligible=True,
            composition_constraints=('Consumes an existing pre-EVM bundle and stops before PASA update rounds.',),
            pipeline_family='annotation',
            pipeline_stage_order=7,
        ),
    ),
    RegistryEntry(
        name='prepare_evm_transcript_inputs',
        category='task',
        description='Stage `${db}.pasa_assemblies.gff3` from the PASA results bundle as the final `transcripts.gff3` pre-EVM contract file.',
        inputs=(
            InterfaceField('pasa_results', 'Dir', 'PASA results directory containing the PASA assemblies GFF3 output.'),
        ),
        outputs=(
            InterfaceField('transcript_inputs_dir', 'Dir', 'Directory containing `transcripts.gff3` plus run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'transcript', 'prep'),
    ),
    RegistryEntry(
        name='prepare_evm_protein_inputs',
        category='task',
        description='Stage the downstream-ready protein evidence outputs into a deterministic PROTEIN channel bundle for later EVM composition.',
        inputs=(
            InterfaceField('protein_evidence_results', 'Dir', 'Protein evidence results directory containing protein_evidence.evm.gff3 and staged protein FASTA inputs.'),
        ),
        outputs=(
            InterfaceField('protein_inputs_dir', 'Dir', 'Directory containing `proteins.gff3` plus run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'protein', 'prep'),
    ),
    RegistryEntry(
        name='prepare_evm_prediction_inputs',
        category='task',
        description='Assemble the final `predictions.gff3` pre-EVM contract file from source-preserving normalized BRAKER3 output plus the PASA-derived TransDecoder genome GFF3.',
        inputs=(
            InterfaceField('transdecoder_results', 'Dir', 'TransDecoder results directory containing the PASA-derived genome GFF3 output.'),
            InterfaceField('braker3_results', 'Dir', 'BRAKER3 results directory containing staged inputs and the source-preserving normalized braker.gff3-derived output.'),
        ),
        outputs=(
            InterfaceField('prediction_inputs_dir', 'Dir', 'Directory containing `predictions.gff3`, the staged component GFF3 files, the authoritative reference genome, and run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'predictions', 'prep'),
    ),
    RegistryEntry(
        name='collect_evm_prep_results',
        category='task',
        description='Collect staged transcript, prediction, and protein inputs into the note-faithful pre-EVM contract bundle without executing EVM.',
        inputs=(
            InterfaceField('transcript_inputs', 'Dir', 'Directory produced by prepare_evm_transcript_inputs.'),
            InterfaceField('protein_inputs', 'Dir', 'Directory produced by prepare_evm_protein_inputs.'),
            InterfaceField('prediction_inputs', 'Dir', 'Directory produced by prepare_evm_prediction_inputs.'),
            InterfaceField('pasa_results', 'Dir', 'Original PASA results bundle used for provenance and source-manifest copying.'),
            InterfaceField('transdecoder_results', 'Dir', 'Original TransDecoder results bundle used for provenance and source-manifest copying.'),
            InterfaceField('protein_evidence_results', 'Dir', 'Original protein evidence results bundle used for provenance and source-manifest copying.'),
            InterfaceField('braker3_results', 'Dir', 'Original BRAKER3 results bundle used for provenance and source-manifest copying.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped pre-EVM results directory containing `transcripts.gff3`, `predictions.gff3`, `proteins.gff3`, the authoritative reference genome, and run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'results', 'manifest'),
    ),
    RegistryEntry(
        name='prepare_evm_execution_inputs',
        category='task',
        description='Stage the existing pre-EVM bundle into a deterministic EVM execution workspace and write an explicit or inferred evm.weights file.',
        inputs=(
            InterfaceField('evm_prep_results', 'Dir', 'Pre-EVM results directory from consensus_annotation_evm_prep.'),
            InterfaceField('evm_weights_text', 'str', 'Optional explicit EVM weights content. When empty, the task infers weights from the notes example and the staged source-column names.'),
        ),
        outputs=(
            InterfaceField('evm_execution_inputs_dir', 'Dir', 'Directory containing genome.fa, transcripts.gff3, predictions.gff3, proteins.gff3, evm.weights, and run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'execution', 'weights'),
    ),
    RegistryEntry(
        name='evm_partition_inputs',
        category='task',
        description='Run deterministic EVM partitioning against the staged execution workspace and preserve partitions_list.out for reviewable downstream execution.',
        inputs=(
            InterfaceField('evm_execution_inputs', 'Dir', 'Directory produced by prepare_evm_execution_inputs.'),
            InterfaceField('evm_partition_script', 'str', 'Partition_EVM_inputs.pl path or executable name.'),
            InterfaceField('evm_segment_size', 'int', 'Segment size passed to partition_EVM_inputs.pl; defaults to the value shown in the notes.'),
            InterfaceField('evm_overlap_size', 'int', 'Overlap size passed to partition_EVM_inputs.pl; defaults to the value shown in the notes.'),
            InterfaceField('evm_sif', 'str', 'Optional Apptainer/Singularity image path for EVM utilities.'),
        ),
        outputs=(
            InterfaceField('partitioned_evm_inputs_dir', 'Dir', 'Directory containing the staged EVM workspace plus Partitions/, partitions_list.out, and run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'partitioning', 'execution'),
    ),
    RegistryEntry(
        name='evm_write_commands',
        category='task',
        description='Generate and normalize the deterministic per-partition EVM command list from one partitioned workspace.',
        inputs=(
            InterfaceField('partitioned_evm_inputs', 'Dir', 'Directory produced by evm_partition_inputs.'),
            InterfaceField('evm_write_commands_script', 'str', 'write_EVM_commands.pl path or executable name.'),
            InterfaceField('evm_output_file_name', 'str', 'Output basename passed to EVM command generation; defaults to evm.out.'),
            InterfaceField('evm_sif', 'str', 'Optional Apptainer/Singularity image path for EVM utilities.'),
        ),
        outputs=(
            InterfaceField('evm_commands_dir', 'Dir', 'Directory containing commands.list, the partitioned workspace copy, and run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'commands', 'execution'),
    ),
    RegistryEntry(
        name='evm_execute_commands',
        category='task',
        description='Execute generated EVM commands sequentially in deterministic file order instead of submitting HPC job scripts.',
        inputs=(
            InterfaceField('evm_commands', 'Dir', 'Directory produced by evm_write_commands.'),
            InterfaceField('evm_sif', 'str', 'Optional Apptainer/Singularity image path for EVM utilities.'),
        ),
        outputs=(
            InterfaceField('executed_evm_commands_dir', 'Dir', 'Directory containing the executed workspace, execution_logs/, and run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'execution', 'sequential'),
    ),
    RegistryEntry(
        name='evm_recombine_outputs',
        category='task',
        description='Recombine partition outputs, convert them to GFF3, and finalize EVM.all.gff3, EVM.all.removed.gff3, and EVM.all.sort.gff3.',
        inputs=(
            InterfaceField('executed_evm_commands', 'Dir', 'Directory produced by evm_execute_commands.'),
            InterfaceField('evm_recombine_script', 'str', 'recombine_EVM_partial_outputs.pl path or executable name.'),
            InterfaceField('evm_convert_script', 'str', 'convert_EVM_outputs_to_GFF3.pl path or executable name.'),
            InterfaceField('gff3sort_script', 'str', 'Optional gff3sort.pl path or executable name. When empty, sorting is skipped explicitly.'),
            InterfaceField('evm_output_file_name', 'str', 'Output basename used during EVM execution; defaults to evm.out.'),
            InterfaceField('evm_sif', 'str', 'Optional Apptainer/Singularity image path for EVM utilities.'),
        ),
        outputs=(
            InterfaceField('recombined_evm_outputs_dir', 'Dir', 'Directory containing recombined EVM outputs, final GFF3 files, and run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'recombine', 'gff3'),
    ),
    RegistryEntry(
        name='collect_evm_results',
        category='task',
        description='Collect the pre-EVM bundle and all explicit EVM execution stages into one manifest-bearing consensus-annotation results directory.',
        inputs=(
            InterfaceField('evm_prep_results', 'Dir', 'Original pre-EVM bundle from consensus_annotation_evm_prep.'),
            InterfaceField('evm_execution_inputs', 'Dir', 'Directory produced by prepare_evm_execution_inputs.'),
            InterfaceField('partitioned_evm_inputs', 'Dir', 'Directory produced by evm_partition_inputs.'),
            InterfaceField('evm_commands', 'Dir', 'Directory produced by evm_write_commands.'),
            InterfaceField('executed_evm_commands', 'Dir', 'Directory produced by evm_execute_commands.'),
            InterfaceField('recombined_evm_outputs', 'Dir', 'Directory produced by evm_recombine_outputs.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped EVM results directory containing copied stage outputs, evm.weights, partitions_list.out, commands.list, final GFF3 files, and run_manifest.json.'),
        ),
        tags=('consensus', 'evm', 'results', 'manifest'),
    ),
)
