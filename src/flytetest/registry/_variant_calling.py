"""Registry entries for the variant_calling pipeline family."""

from __future__ import annotations

from flytetest.registry._types import (
    InterfaceField,
    RegistryCompatibilityMetadata,
    RegistryEntry,
)

VARIANT_CALLING_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name="create_sequence_dictionary",
        category="task",
        description="Emit a GATK4 sequence dictionary (.dict) next to a reference FASTA via CreateSequenceDictionary.",
        inputs=(
            InterfaceField("reference_fasta", "File", "Reference genome FASTA."),
            InterfaceField("gatk_sif", "str", "Optional Apptainer/Singularity image path for GATK4."),
        ),
        outputs=(
            InterfaceField("sequence_dict", "File", "GATK4 sequence dictionary (.dict) file emitted next to the reference FASTA."),
        ),
        tags=("variant_calling", "gatk4", "reference_prep"),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage="GATK4 reference sequence dictionary",
            accepted_planner_types=("ReferenceGenome",),
            produced_planner_types=(),
            reusable_as_reference=True,
            execution_defaults={
                "profile": "local",
                "result_manifest": "run_manifest.json",
                "resources": {"cpu": "1", "memory": "4Gi", "execution_class": "local"},
                "slurm_resource_hints": {"cpu": "1", "memory": "4Gi", "walltime": "00:30:00"},
                "runtime_images": {"gatk_sif": "data/images/gatk4.sif"},
                "module_loads": ("python/3.11.9", "apptainer/1.4.1"),
            },
            supported_execution_profiles=("local", "slurm"),
            synthesis_eligible=True,
            composition_constraints=(
                "Requires a reference genome FASTA; emits the sequence dictionary downstream tools depend on.",
            ),
            pipeline_family="variant_calling",
            pipeline_stage_order=1,
        ),
    ),
    RegistryEntry(
        name="index_feature_file",
        category="task",
        description="Emit a GATK4 feature-file index (.idx or .tbi) next to a VCF/GVCF via IndexFeatureFile.",
        inputs=(
            InterfaceField("vcf", "File", "VCF or GVCF to index."),
            InterfaceField("gatk_sif", "str", "Optional Apptainer/Singularity image path for GATK4."),
        ),
        outputs=(
            InterfaceField("feature_index", "File", "GATK4 index (.idx for plain VCF, .tbi for .vcf.gz) written next to the input VCF."),
        ),
        tags=("variant_calling", "gatk4", "reference_prep"),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage="GATK4 feature-file indexing",
            accepted_planner_types=("KnownSites",),
            produced_planner_types=(),
            reusable_as_reference=True,
            execution_defaults={
                "profile": "local",
                "result_manifest": "run_manifest.json",
                "resources": {"cpu": "1", "memory": "4Gi", "execution_class": "local"},
                "slurm_resource_hints": {"cpu": "1", "memory": "4Gi", "walltime": "00:30:00"},
                "runtime_images": {"gatk_sif": "data/images/gatk4.sif"},
                "module_loads": ("python/3.11.9", "apptainer/1.4.1"),
            },
            supported_execution_profiles=("local", "slurm"),
            synthesis_eligible=True,
            composition_constraints=(
                "Requires a VCF or GVCF; emits the index file BQSR and downstream steps depend on.",
            ),
            pipeline_family="variant_calling",
            pipeline_stage_order=2,
        ),
    ),
    RegistryEntry(
        name="base_recalibrator",
        category="task",
        description="Generate a GATK4 BQSR recalibration table via BaseRecalibrator.",
        inputs=(
            InterfaceField("reference_fasta", "File", "Reference genome FASTA."),
            InterfaceField("aligned_bam", "File", "Coordinate-sorted, duplicate-marked BAM."),
            InterfaceField("known_sites", "list[File]", "Indexed known-sites VCF(s) for BQSR."),
            InterfaceField("sample_id", "str", "Sample identifier used to name the output table."),
            InterfaceField("gatk_sif", "str", "Optional Apptainer/Singularity image path for GATK4."),
        ),
        outputs=(
            InterfaceField("bqsr_report", "File", "GATK4 BQSR recalibration table (.table)."),
        ),
        tags=("variant_calling", "gatk4", "bqsr"),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage="GATK4 base quality score recalibration report",
            accepted_planner_types=("ReferenceGenome", "AlignmentSet", "KnownSites"),
            produced_planner_types=(),
            reusable_as_reference=False,
            execution_defaults={
                "profile": "local",
                "result_manifest": "run_manifest.json",
                "resources": {"cpu": "4", "memory": "16Gi", "execution_class": "local"},
                "slurm_resource_hints": {"cpu": "8", "memory": "32Gi", "walltime": "06:00:00"},
                "runtime_images": {"gatk_sif": "data/images/gatk4.sif"},
                "module_loads": ("python/3.11.9", "apptainer/1.4.1"),
            },
            supported_execution_profiles=("local", "slurm"),
            synthesis_eligible=True,
            composition_constraints=(
                "Requires coordinate-sorted dedup'd BAM + reference + \u22651 indexed known-sites VCF.",
            ),
            pipeline_family="variant_calling",
            pipeline_stage_order=3,
        ),
    ),
    RegistryEntry(
        name="apply_bqsr",
        category="task",
        description="Apply a GATK4 BQSR recalibration table to an aligned BAM via ApplyBQSR.",
        inputs=(
            InterfaceField("reference_fasta", "File", "Reference genome FASTA."),
            InterfaceField("aligned_bam", "File", "Coordinate-sorted, duplicate-marked BAM."),
            InterfaceField("bqsr_report", "File", "BQSR recalibration table from base_recalibrator."),
            InterfaceField("sample_id", "str", "Sample identifier used to name the output BAM."),
            InterfaceField("gatk_sif", "str", "Optional Apptainer/Singularity image path for GATK4."),
        ),
        outputs=(
            InterfaceField("recalibrated_bam", "File", "Recalibrated BAM produced by GATK4 ApplyBQSR."),
        ),
        tags=("variant_calling", "gatk4", "bqsr"),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage="GATK4 apply base quality score recalibration",
            accepted_planner_types=("ReferenceGenome", "AlignmentSet"),
            produced_planner_types=("AlignmentSet",),
            reusable_as_reference=False,
            execution_defaults={
                "profile": "local",
                "result_manifest": "run_manifest.json",
                "resources": {"cpu": "4", "memory": "16Gi", "execution_class": "local"},
                "slurm_resource_hints": {"cpu": "8", "memory": "32Gi", "walltime": "06:00:00"},
                "runtime_images": {"gatk_sif": "data/images/gatk4.sif"},
                "module_loads": ("python/3.11.9", "apptainer/1.4.1"),
            },
            supported_execution_profiles=("local", "slurm"),
            synthesis_eligible=True,
            composition_constraints=(
                "Requires coordinate-sorted dedup'd BAM + reference + BQSR table from base_recalibrator.",
            ),
            pipeline_family="variant_calling",
            pipeline_stage_order=4,
        ),
    ),
    RegistryEntry(
        name="haplotype_caller",
        category="task",
        description="Call per-sample germline variants in GVCF mode via GATK4 HaplotypeCaller.",
        inputs=(
            InterfaceField("reference_fasta", "File", "Reference genome FASTA."),
            InterfaceField("aligned_bam", "File", "Coordinate-sorted, dedup'd, BQSR-recalibrated BAM."),
            InterfaceField("sample_id", "str", "Sample identifier used to name the output GVCF."),
            InterfaceField("gatk_sif", "str", "Optional Apptainer/Singularity image path for GATK4."),
        ),
        outputs=(
            InterfaceField("gvcf", "File", "Per-sample GVCF produced by GATK4 HaplotypeCaller."),
        ),
        tags=("variant_calling", "gatk4", "gvcf"),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage="GATK4 per-sample GVCF generation",
            accepted_planner_types=("ReferenceGenome", "AlignmentSet"),
            produced_planner_types=("VariantCallSet",),
            reusable_as_reference=False,
            execution_defaults={
                "profile": "local",
                "result_manifest": "run_manifest.json",
                "resources": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
                "slurm_resource_hints": {"cpu": "16", "memory": "64Gi", "walltime": "24:00:00"},
                "runtime_images": {"gatk_sif": "data/images/gatk4.sif"},
                "module_loads": ("python/3.11.9", "apptainer/1.4.1"),
            },
            supported_execution_profiles=("local", "slurm"),
            synthesis_eligible=True,
            composition_constraints=(
                "Requires coordinate-sorted dedup'd BAM + reference; BQSR-recalibrated BAM strongly recommended.",
            ),
            pipeline_family="variant_calling",
            pipeline_stage_order=5,
        ),
    ),
)
