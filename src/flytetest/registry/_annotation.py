"""Registry entries for the annotation pipeline family."""

from __future__ import annotations

from flytetest.registry._types import (
    InterfaceField,
    RegistryCompatibilityMetadata,
    RegistryEntry,
)


ANNOTATION_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name='ab_initio_annotation_braker3',
        category='workflow',
        description='BRAKER3-only ab initio annotation workflow that stages local inputs, runs a Galaxy tutorial-backed BRAKER3 boundary, preserves upstream braker.gff3 source values during normalization for later EVM use, and collects a manifest-bearing results bundle.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA.'),
            InterfaceField('rnaseq_bam_path', 'str', 'Optional local RNA-seq BAM evidence path. This milestone requires at least one evidence input across RNA-seq BAM and protein FASTA.'),
            InterfaceField('protein_fasta_path', 'str', 'Optional local protein FASTA evidence path. This milestone requires at least one evidence input across RNA-seq BAM and protein FASTA.'),
            InterfaceField('braker_species', 'str', 'Species/model name passed to BRAKER3.'),
            InterfaceField('braker3_sif', 'str', 'Optional Apptainer/Singularity image path for BRAKER3.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped BRAKER3 results directory containing staged inputs, raw BRAKER3 outputs, source-preserving normalized GFF3, and run_manifest.json.'),
        ),
        tags=('workflow', 'annotation', 'braker3', 'ab-initio'),
        showcase_module='flytetest.workflows.annotation',
        compatibility=RegistryCompatibilityMetadata(
            biological_stage='BRAKER3 ab initio annotation',
            accepted_planner_types=('ReferenceGenome', 'TranscriptEvidenceSet', 'ProteinEvidenceSet',),
            produced_planner_types=('AnnotationEvidenceSet',),
            reusable_as_reference=True,
            execution_defaults={
            'profile': 'local',
            'result_manifest': 'run_manifest.json',
            'resources': {'cpu': '16', 'memory': '64Gi', 'execution_class': 'local'},
            'slurm_resource_hints': {'cpu': '16', 'memory': '64Gi', 'walltime': '24:00:00'},
        },
            supported_execution_profiles=('local', 'slurm',),
            synthesis_eligible=True,
            composition_constraints=('Requires a genome plus at least one explicit evidence source across RNA-seq BAM or protein FASTA.', 'BRAKER3 invocation details remain Galaxy tutorial-backed where the notes are not explicit.',),
            pipeline_family='annotation',
            pipeline_stage_order=5,
        ),
    ),
    RegistryEntry(
        name='stage_braker3_inputs',
        category='task',
        description='Stage local BRAKER3-ready inputs into a deterministic bundle containing the genome plus explicitly provided evidence files.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA.'),
            InterfaceField('rnaseq_bam_path', 'str', 'Optional local RNA-seq BAM evidence path. This milestone requires at least one evidence input across RNA-seq BAM and protein FASTA.'),
            InterfaceField('protein_fasta_path', 'str', 'Optional local protein FASTA evidence path. This milestone requires at least one evidence input across RNA-seq BAM and protein FASTA.'),
        ),
        outputs=(
            InterfaceField('staged_inputs_dir', 'Dir', 'Directory containing staged BRAKER3 inputs plus run_manifest.json.'),
        ),
        tags=('annotation', 'braker3', 'staging', 'local-inputs'),
    ),
    RegistryEntry(
        name='braker3_predict',
        category='task',
        description="Run the repo's Galaxy tutorial-backed BRAKER3 command boundary and preserve the raw output directory with resolved braker.gff3.",
        inputs=(
            InterfaceField('staged_inputs', 'Dir', 'Directory produced by stage_braker3_inputs.'),
            InterfaceField('braker_species', 'str', 'Species/model name passed to BRAKER3. The notes do not specify it; this repo uses a deterministic local default as a repo policy.'),
            InterfaceField('braker3_sif', 'str', 'Optional Apptainer/Singularity image path for BRAKER3.'),
        ),
        outputs=(
            InterfaceField('braker_run_dir', 'Dir', 'Directory containing raw BRAKER3 outputs, including braker.gff3, plus run_manifest.json.'),
        ),
        tags=('annotation', 'braker3', 'prediction', 'ab-initio'),
    ),
    RegistryEntry(
        name='normalize_braker3_for_evm',
        category='task',
        description='Normalize resolved braker.gff3 into a stable later-EVM-ready GFF3 boundary while preserving upstream source-column values.',
        inputs=(
            InterfaceField('braker_run', 'Dir', 'Directory produced by braker3_predict containing braker.gff3.'),
        ),
        outputs=(
            InterfaceField('normalized_dir', 'Dir', 'Directory containing a deterministically normalized source-preserving BRAKER3 GFF3 plus run_manifest.json.'),
        ),
        tags=('annotation', 'braker3', 'normalization', 'evm-ready'),
    ),
    RegistryEntry(
        name='collect_braker3_results',
        category='task',
        description='Collect staged inputs, raw BRAKER3 outputs, and source-preserving normalized BRAKER3 GFF3 into a manifest-bearing results bundle.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA used for provenance.'),
            InterfaceField('staged_inputs', 'Dir', 'Directory produced by stage_braker3_inputs.'),
            InterfaceField('braker_run', 'Dir', 'Directory produced by braker3_predict.'),
            InterfaceField('normalized_braker', 'Dir', 'Directory produced by normalize_braker3_for_evm.'),
            InterfaceField('braker_species', 'str', 'Species/model name associated with the BRAKER3 run.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped BRAKER3 results directory containing staged inputs, raw outputs, source-preserving normalized outputs, and run_manifest.json.'),
        ),
        tags=('annotation', 'braker3', 'results', 'manifest'),
    ),
)
