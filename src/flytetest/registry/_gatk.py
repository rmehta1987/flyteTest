"""Registry entries for the GATK variant-calling pipeline family.

This is a catalog-only placeholder for future GATK4 workflow support.
No handler, planning coverage, or execution support is implemented yet.
"""

from __future__ import annotations

from flytetest.registry._types import (
    InterfaceField,
    RegistryCompatibilityMetadata,
    RegistryEntry,
)


GATK_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name='gatk_haplotype_caller',
        category='workflow',
        description=(
            'GATK4 HaplotypeCaller variant-calling workflow that aligns reads '
            'against a reference genome, calls SNPs and indels in GVCF mode per '
            'sample, and collects a manifest-bearing results bundle suitable for '
            'downstream joint genotyping.'
        ),
        inputs=(
            InterfaceField('reference_fasta', 'File', 'Reference genome FASTA with accompanying .fai and .dict index files.'),
            InterfaceField('input_bam', 'File', 'Coordinate-sorted, duplicate-marked BAM file with .bai index.'),
            InterfaceField('sample_name', 'str', 'Sample identifier used to name output files and recorded in the GVCF header.'),
            InterfaceField('dbsnp_vcf', 'str', 'Optional path to a dbSNP VCF used for variant annotation and BQSR; omitted when empty.'),
            InterfaceField('gatk_sif', 'str', 'Optional Apptainer/Singularity image path for GATK4.'),
            InterfaceField('emit_ref_confidence', 'str', "GVCF emission mode passed to HaplotypeCaller with --emit-ref-confidence; defaults to 'GVCF'."),
        ),
        outputs=(
            InterfaceField('results_dir', 'Dir', 'Timestamped variant-calling results directory containing the per-sample GVCF, its .tbi index, and run_manifest.json.'),
        ),
        tags=('workflow', 'variant-calling', 'gatk4', 'haplotype-caller', 'gvcf'),
        showcase_module='',
        compatibility=RegistryCompatibilityMetadata(
            biological_stage='GATK4 HaplotypeCaller variant calling',
            accepted_planner_types=('ReferenceGenome', 'AlignmentSet'),
            produced_planner_types=('VariantCallSet',),
            reusable_as_reference=True,
            execution_defaults={
                'profile': 'local',
                'result_manifest': 'run_manifest.json',
                'resources': {'cpu': '4', 'memory': '10Gi', 'execution_class': 'local'},
                'slurm_resource_hints': {'cpu': '8', 'memory': '32Gi', 'walltime': '08:00:00'},
            },
            supported_execution_profiles=('local', 'slurm'),
            synthesis_eligible=False,
            composition_constraints=(
                'Requires a coordinate-sorted duplicate-marked BAM with index.',
                'GVCF output is suitable for joint genotyping with GenomicsDBImport + GenotypeGVCFs.',
                'No handler or planning coverage implemented yet; catalog-only placeholder.',
            ),
            pipeline_family='variant_calling',
            pipeline_stage_order=3,
        ),
    ),
)
