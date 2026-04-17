"""Registry entries for the protein-evidence pipeline family."""

from __future__ import annotations

from flytetest.registry._types import (
    InterfaceField,
    RegistryCompatibilityMetadata,
    RegistryEntry,
)


PROTEIN_EVIDENCE_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name='protein_evidence_alignment',
        category='workflow',
        description='Protein-evidence workflow that stages local protein FASTAs, chunks them deterministically, aligns each chunk with Exonerate, converts outputs to EVM-ready GFF3, and collects a manifest-bearing results bundle.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA used as the Exonerate target.'),
            InterfaceField('protein_fastas', 'list[File]', 'One or more local protein FASTA inputs supplied in deterministic order.'),
            InterfaceField('proteins_per_chunk', 'int', 'Maximum number of protein records per chunk produced by the workflow.'),
            InterfaceField('exonerate_sif', 'str', 'Optional Apptainer/Singularity image path for Exonerate.'),
            InterfaceField('exonerate_model', 'str', 'Exonerate model name passed to each chunk run; defaults to protein2genome.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped protein-evidence results directory containing raw and converted chunk outputs plus run_manifest.json.'),
        ),
        tags=('workflow', 'protein-evidence', 'exonerate', 'annotation'),
        showcase_module='flytetest.workflows.protein_evidence',
        compatibility=RegistryCompatibilityMetadata(
            biological_stage='protein evidence alignment',
            accepted_planner_types=('ReferenceGenome', 'ProteinEvidenceSet',),
            produced_planner_types=('ProteinEvidenceSet',),
            reusable_as_reference=True,
            execution_defaults={
            'profile': 'local',
            'result_manifest': 'run_manifest.json',
            'resources': {'cpu': '8', 'memory': '32Gi', 'execution_class': 'local'},
            'slurm_resource_hints': {'cpu': '8', 'memory': '32Gi', 'walltime': '04:00:00'},
        },
            supported_execution_profiles=('local', 'slurm',),
            synthesis_eligible=True,
            composition_constraints=('Protein FASTA inputs are local and explicit; the workflow does not fetch UniProt or RefSeq automatically.',),
            pipeline_family='annotation',
            pipeline_stage_order=4,
        ),
    ),
    RegistryEntry(
        name='stage_protein_fastas',
        category='task',
        description='Stage one or more local protein FASTA inputs into a deterministic combined protein evidence bundle.',
        inputs=(
            InterfaceField('protein_fastas', 'list[File]', 'Local protein FASTA inputs supplied by the user in deterministic order.'),
        ),
        outputs=(
            InterfaceField('staged_dataset_dir', 'Dir', 'Directory containing staged protein FASTA inputs plus the combined evidence FASTA and manifest.'),
        ),
        tags=('protein-evidence', 'staging', 'proteins', 'local-inputs'),
    ),
    RegistryEntry(
        name='chunk_protein_fastas',
        category='task',
        description='Split a staged protein evidence FASTA deterministically into chunk FASTAs for parallel Exonerate runs.',
        inputs=(
            InterfaceField('staged_proteins', 'Dir', 'Directory produced by stage_protein_fastas containing the combined protein FASTA.'),
            InterfaceField('proteins_per_chunk', 'int', 'Maximum number of protein records per chunk.'),
        ),
        outputs=(
            InterfaceField('chunk_dir', 'Dir', 'Directory containing deterministic chunk FASTAs and a chunk manifest.'),
        ),
        tags=('protein-evidence', 'chunking', 'proteins', 'exonerate'),
    ),
    RegistryEntry(
        name='exonerate_align_chunk',
        category='task',
        description='Run Exonerate for one protein FASTA chunk against the genome and preserve the raw alignment output.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA used as the alignment target.'),
            InterfaceField('protein_chunk', 'File', 'One chunk FASTA produced by chunk_protein_fastas.'),
            InterfaceField('exonerate_sif', 'str', 'Optional Apptainer/Singularity image path for Exonerate.'),
            InterfaceField('exonerate_model', 'str', 'Exonerate model name; defaults to protein2genome in this milestone.'),
        ),
        outputs=(
            InterfaceField('alignment_dir', 'Dir', 'Directory containing the raw Exonerate output and per-chunk metadata.'),
        ),
        tags=('protein-evidence', 'exonerate', 'chunked', 'alignment'),
        showcase_module='flytetest.tasks.protein_evidence',
    ),
    RegistryEntry(
        name='exonerate_to_evm_gff3',
        category='task',
        description='Convert one raw Exonerate chunk result into an EVM-compatible protein evidence GFF3.',
        inputs=(
            InterfaceField('exonerate_alignment', 'Dir', 'Directory produced by exonerate_align_chunk containing the raw Exonerate output.'),
        ),
        outputs=(
            InterfaceField('converted_dir', 'Dir', 'Directory containing the chunk-level downstream-ready protein evidence GFF3 and per-chunk metadata.'),
        ),
        tags=('protein-evidence', 'exonerate', 'gff3', 'evm-ready'),
    ),
    RegistryEntry(
        name='exonerate_concat_results',
        category='task',
        description='Collect raw and converted Exonerate chunk outputs into stable concatenated artifacts and a manifest.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA used for provenance in the results bundle.'),
            InterfaceField('staged_proteins', 'Dir', 'Directory produced by stage_protein_fastas.'),
            InterfaceField('protein_chunks', 'Dir', 'Directory produced by chunk_protein_fastas.'),
            InterfaceField('raw_chunk_results', 'list[Dir]', 'Per-chunk Exonerate output directories in deterministic chunk order.'),
            InterfaceField('evm_chunk_results', 'list[Dir]', 'Per-chunk converted EVM-ready protein evidence directories in deterministic chunk order.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped protein-evidence results directory with raw and converted chunk artifacts plus a manifest.'),
        ),
        tags=('protein-evidence', 'results', 'manifest', 'exonerate', 'evm-ready'),
    ),
)
