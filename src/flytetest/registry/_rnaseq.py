"""Registry entries for the rnaseq pipeline family."""

from __future__ import annotations

from flytetest.registry._types import (
    InterfaceField,
    RegistryCompatibilityMetadata,
    RegistryEntry,
)


RNASEQ_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name='rnaseq_qc_quant',
        category='workflow',
        description='Current RNA-seq QC and quantification workflow composed from FastQC and Salmon tasks.',
        inputs=(
            InterfaceField('ref', 'File', 'Transcriptome FASTA used to build the Salmon index.'),
            InterfaceField('left', 'File', 'Read 1 FASTQ input.'),
            InterfaceField('right', 'File', 'Read 2 FASTQ input.'),
            InterfaceField('salmon_sif', 'str', 'Optional Apptainer/Singularity image path for Salmon.'),
            InterfaceField('fastqc_sif', 'str', 'Optional Apptainer/Singularity image path for FastQC.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped results directory containing qc/, quant/, and run_manifest.json.'),
        ),
        tags=('workflow', 'rnaseq', 'qc', 'quant'),
        showcase_module='flytetest.workflows.rnaseq_qc_quant',
        compatibility=RegistryCompatibilityMetadata(
            biological_stage='RNA-seq QC and transcript quantification',
            accepted_planner_types=('ReadSet',),
            reusable_as_reference=True,
            execution_defaults={
            'profile': 'local',
            'result_manifest': 'run_manifest.json',
            'resources': {'cpu': '4', 'memory': '16Gi', 'execution_class': 'local'},
            'slurm_resource_hints': {'cpu': '4', 'memory': '16Gi', 'walltime': '01:00:00'},
        },
            supported_execution_profiles=('local', 'slurm',),
            synthesis_eligible=True,
            composition_constraints=('This workflow is a standalone RNA-seq QC/quantification branch and does not produce genome-annotation evidence.',),
        ),
    ),
    RegistryEntry(
        name='salmon_index',
        category='task',
        description='Build a Salmon transcriptome index from a reference FASTA.',
        inputs=(
            InterfaceField('ref', 'File', 'Transcriptome FASTA used for indexing.'),
            InterfaceField('salmon_sif', 'str', 'Optional Apptainer/Singularity image path for Salmon.'),
        ),
        outputs=(
            InterfaceField('index', 'Dir', 'Directory containing the Salmon index.'),
        ),
        tags=('rnaseq', 'quant', 'salmon', 'index'),
    ),
    RegistryEntry(
        name='fastqc',
        category='task',
        description='Run FastQC on paired-end RNA-seq reads.',
        inputs=(
            InterfaceField('left', 'File', 'Read 1 FASTQ input.'),
            InterfaceField('right', 'File', 'Read 2 FASTQ input.'),
            InterfaceField('fastqc_sif', 'str', 'Optional Apptainer/Singularity image path for FastQC.'),
        ),
        outputs=(
            InterfaceField('qc_dir', 'Dir', 'Directory containing FastQC reports.'),
        ),
        tags=('rnaseq', 'qc', 'fastqc', 'paired-end'),
        showcase_module='flytetest.tasks.qc',
    ),
    RegistryEntry(
        name='salmon_quant',
        category='task',
        description='Quantify transcript abundance from paired-end reads with Salmon.',
        inputs=(
            InterfaceField('index', 'Dir', 'Existing Salmon index directory.'),
            InterfaceField('left', 'File', 'Read 1 FASTQ input.'),
            InterfaceField('right', 'File', 'Read 2 FASTQ input.'),
            InterfaceField('salmon_sif', 'str', 'Optional Apptainer/Singularity image path for Salmon.'),
        ),
        outputs=(
            InterfaceField('quant_dir', 'Dir', 'Directory containing Salmon quantification outputs.'),
        ),
        tags=('rnaseq', 'quant', 'salmon', 'paired-end'),
    ),
    RegistryEntry(
        name='collect_results',
        category='task',
        description='Copy QC and quant outputs into a stable results bundle with a run manifest.',
        inputs=(
            InterfaceField('qc', 'Dir', 'FastQC output directory.'),
            InterfaceField('quant', 'Dir', 'Salmon quantification directory.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped results directory with qc/, quant/, and run_manifest.json.'),
        ),
        tags=('rnaseq', 'results', 'manifest'),
    ),
)
