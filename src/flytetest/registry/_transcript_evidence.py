"""Registry entries for the transcript-evidence pipeline family."""

from __future__ import annotations

from flytetest.registry._types import (
    InterfaceField,
    RegistryCompatibilityMetadata,
    RegistryEntry,
)


TRANSCRIPT_EVIDENCE_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name='transcript_evidence_generation',
        category='workflow',
        description='Single-sample transcript-evidence workflow composed from de novo Trinity, STAR indexing/alignment, one-BAM merge, genome-guided Trinity, and StringTie; it now produces both Trinity branches required upstream of PASA while keeping the all-sample merge contract as a documented simplification.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA.'),
            InterfaceField('left', 'File', 'Read 1 FASTQ input.'),
            InterfaceField('right', 'File', 'Read 2 FASTQ input.'),
            InterfaceField('sample_id', 'str', 'Sample identifier used in manifests and task provenance.'),
            InterfaceField('star_sif', 'str', 'Optional Apptainer/Singularity image path for STAR.'),
            InterfaceField('samtools_sif', 'str', 'Optional Apptainer/Singularity image path for samtools.'),
            InterfaceField('trinity_sif', 'str', 'Optional Apptainer/Singularity image path for Trinity.'),
            InterfaceField('stringtie_sif', 'str', 'Optional Apptainer/Singularity image path for StringTie.'),
            InterfaceField('star_threads', 'int', 'Thread count for STAR tasks.'),
            InterfaceField('trinity_cpu', 'int', 'CPU count for Trinity.'),
            InterfaceField('trinity_max_memory_gb', 'int', 'Memory budget for Trinity in GB.'),
            InterfaceField('genome_guided_max_intron', 'int', 'Genome-guided max intron setting for Trinity.'),
            InterfaceField('stringtie_threads', 'int', 'Thread count for StringTie.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped transcript-evidence directory with de novo Trinity, STAR, merged BAM, genome-guided Trinity, StringTie, and a manifest.'),
        ),
        tags=('workflow', 'transcript-evidence', 'star', 'trinity', 'stringtie'),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage='transcript evidence generation',
            accepted_planner_types=('ReferenceGenome', 'ReadSet',),
            produced_planner_types=('TranscriptEvidenceSet',),
            reusable_as_reference=True,
            execution_defaults={
            'profile': 'local',
            'result_manifest': 'run_manifest.json',
            'resources': {'cpu': '8', 'memory': '32Gi', 'execution_class': 'local'},
            'slurm_resource_hints': {'cpu': '16', 'memory': '64Gi', 'walltime': '04:00:00'},
        },
            supported_execution_profiles=('local', 'slurm',),
            synthesis_eligible=True,
            composition_constraints=('Current implementation is a one paired-end sample subset of the full all-sample branch.', 'Downstream PASA alignment should consume the manifest-bearing transcript evidence result bundle.',),
            pipeline_family='annotation',
            pipeline_stage_order=1,
        ),
    ),
    RegistryEntry(
        name='trinity_denovo_assemble',
        category='task',
        description='Run de novo Trinity on one paired-end RNA-seq sample for the transcript-evidence branch upstream of PASA.',
        inputs=(
            InterfaceField('left', 'File', 'Read 1 FASTQ input.'),
            InterfaceField('right', 'File', 'Read 2 FASTQ input.'),
            InterfaceField('sample_id', 'str', 'Sample identifier used for provenance and temporary output naming.'),
            InterfaceField('trinity_sif', 'str', 'Optional Apptainer/Singularity image path for Trinity.'),
            InterfaceField('trinity_cpu', 'int', 'CPU count passed to Trinity.'),
            InterfaceField('trinity_max_memory_gb', 'int', 'Maximum memory in GB passed to Trinity.'),
        ),
        outputs=(
            InterfaceField('trinity_dir', 'Dir', 'Directory containing de novo Trinity outputs.'),
        ),
        tags=('transcript-evidence', 'trinity', 'de-novo', 'assembly'),
    ),
    RegistryEntry(
        name='star_genome_index',
        category='task',
        description='Build a STAR genome index from a reference genome FASTA.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA.'),
            InterfaceField('star_sif', 'str', 'Optional Apptainer/Singularity image path for STAR.'),
            InterfaceField('star_threads', 'int', 'Thread count passed to STAR.'),
        ),
        outputs=(
            InterfaceField('index_dir', 'Dir', 'Directory containing STAR genome index files.'),
        ),
        tags=('transcript-evidence', 'star', 'index', 'genome'),
    ),
    RegistryEntry(
        name='star_align_sample',
        category='task',
        description='Align one paired-end RNA-seq sample with STAR and emit a sorted coordinate BAM.',
        inputs=(
            InterfaceField('index', 'Dir', 'Existing STAR genome index directory.'),
            InterfaceField('left', 'File', 'Read 1 FASTQ input.'),
            InterfaceField('right', 'File', 'Read 2 FASTQ input.'),
            InterfaceField('sample_id', 'str', 'Sample identifier used for provenance and output naming.'),
            InterfaceField('star_sif', 'str', 'Optional Apptainer/Singularity image path for STAR.'),
            InterfaceField('star_threads', 'int', 'Thread count passed to STAR.'),
        ),
        outputs=(
            InterfaceField('alignment_dir', 'Dir', 'Directory containing STAR alignment outputs and logs.'),
        ),
        tags=('transcript-evidence', 'star', 'alignment', 'paired-end'),
    ),
    RegistryEntry(
        name='samtools_merge_bams',
        category='task',
        description='Merge one or more STAR-produced BAMs into a single coordinate-sorted BAM stage output.',
        inputs=(
            InterfaceField('alignment_dirs', 'list[Dir]', 'STAR alignment directories containing sorted BAM outputs.'),
            InterfaceField('samtools_sif', 'str', 'Optional Apptainer/Singularity image path for samtools.'),
        ),
        outputs=(
            InterfaceField('merged_bam', 'File', 'Merged BAM file for downstream transcript-evidence tasks.'),
        ),
        tags=('transcript-evidence', 'samtools', 'bam', 'merge'),
    ),
    RegistryEntry(
        name='trinity_genome_guided_assemble',
        category='task',
        description='Run genome-guided Trinity from a merged RNA-seq BAM.',
        inputs=(
            InterfaceField('merged_bam', 'File', 'Merged BAM input for genome-guided Trinity.'),
            InterfaceField('trinity_sif', 'str', 'Optional Apptainer/Singularity image path for Trinity.'),
            InterfaceField('trinity_cpu', 'int', 'CPU count passed to Trinity.'),
            InterfaceField('trinity_max_memory_gb', 'int', 'Maximum memory in GB passed to Trinity.'),
            InterfaceField('genome_guided_max_intron', 'int', 'Genome-guided max intron setting passed to Trinity.'),
        ),
        outputs=(
            InterfaceField('trinity_dir', 'Dir', 'Directory containing genome-guided Trinity outputs.'),
        ),
        tags=('transcript-evidence', 'trinity', 'genome-guided', 'assembly'),
    ),
    RegistryEntry(
        name='stringtie_assemble',
        category='task',
        description='Run StringTie transcript assembly from a merged RNA-seq BAM with the fixed flags `-l STRG -f 0.10 -c 3 -j 3`.',
        inputs=(
            InterfaceField('merged_bam', 'File', 'Merged BAM input for StringTie.'),
            InterfaceField('stringtie_sif', 'str', 'Optional Apptainer/Singularity image path for StringTie.'),
            InterfaceField('stringtie_threads', 'int', 'Thread count passed to StringTie.'),
        ),
        outputs=(
            InterfaceField('stringtie_dir', 'Dir', 'Directory containing StringTie outputs.'),
        ),
        tags=('transcript-evidence', 'stringtie', 'assembly', 'gtf'),
    ),
    RegistryEntry(
        name='collect_transcript_evidence_results',
        category='task',
        description='Collect the current single-sample transcript-evidence branch into a structured results directory with both Trinity outputs, STAR/StringTie products, and a manifest that marks the bundle as PASA-ready with documented simplifications.',
        inputs=(
            InterfaceField('genome', 'File', 'Reference genome FASTA.'),
            InterfaceField('left', 'File', 'Read 1 FASTQ input.'),
            InterfaceField('right', 'File', 'Read 2 FASTQ input.'),
            InterfaceField('trinity_denovo', 'Dir', 'De novo Trinity output directory.'),
            InterfaceField('star_index', 'Dir', 'STAR index directory.'),
            InterfaceField('alignment', 'Dir', 'STAR alignment directory.'),
            InterfaceField('merged_bam', 'File', 'Merged BAM file.'),
            InterfaceField('trinity_gg', 'Dir', 'Genome-guided Trinity output directory.'),
            InterfaceField('stringtie', 'Dir', 'StringTie output directory.'),
            InterfaceField('sample_id', 'str', 'Sample identifier used in the manifest.'),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped transcript-evidence results directory with copied outputs and run_manifest.json.'),
        ),
        tags=('transcript-evidence', 'results', 'manifest'),
    ),
)
