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
)
