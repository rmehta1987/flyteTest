"""Flat-parameter MCP tools wrapping ``run_workflow`` and ``run_task``.

This module provides one Python function per showcase workflow or task, exposing
explicit named parameters that appear directly in the JSON schema seen by MCP
clients.  Each function assembles ``bindings``, ``inputs``, and an optional
``resource_request`` dict, then delegates to :func:`flytetest.server.run_workflow`
or :func:`flytetest.server.run_task`.

The existing ``run_workflow`` and ``run_task`` power-tools are preserved; these
flat tools are additive conveniences for clients that cannot navigate the
two-layer ``bindings`` / ``inputs`` surface.

Imports from ``flytetest.server`` are deferred to call time to avoid the
circular import that would occur if server.py imported this module at the top
level while this module imported from server.py at the top level.

Naming convention:
  * ``vc_*``           — variant_calling family
  * ``annotation_*``  — annotation family
  * ``rnaseq_*``      — rnaseq family
"""

from __future__ import annotations


def _run_workflow(*args, **kwargs):  # type: ignore[no-untyped-def]
    from flytetest.server import run_workflow
    return run_workflow(*args, **kwargs)


def _run_task(*args, **kwargs):  # type: ignore[no-untyped-def]
    from flytetest.server import run_task
    return run_task(*args, **kwargs)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _resource_request(
    partition: str,
    account: str,
    cpu: int,
    memory: str,
    walltime: str,
    shared_fs_roots: list[str] | None,
    module_loads: list[str] | None,
) -> dict[str, object] | None:
    """Return a resource_request dict from flat resource params, or ``None``."""
    rr: dict[str, object] = {}
    if partition:        rr["partition"]       = partition
    if account:          rr["account"]         = account
    if cpu:              rr["cpu"]             = cpu
    if memory:           rr["memory"]          = memory
    if walltime:         rr["walltime"]        = walltime
    if shared_fs_roots:  rr["shared_fs_roots"] = shared_fs_roots
    if module_loads:     rr["module_loads"]    = module_loads
    return rr or None


# ---------------------------------------------------------------------------
# Step 1 — variant_calling flat tools
# ---------------------------------------------------------------------------


def vc_germline_discovery(
    reference_fasta: str,
    sample_ids: list[str],
    r1_paths: list[str],
    known_sites: list[str],
    intervals: list[str],
    cohort_id: str,
    r2_paths: list[str] | None = None,
    threads: int = 4,
    gatk_sif: str = "",
    bwa_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run end-to-end germline short variant discovery from raw reads to joint VCF.

    Parameters
    ----------
    reference_fasta : str
        Absolute path to the reference FASTA file.
    sample_ids : list[str]
        Sample identifiers, one per sample.
    r1_paths : list[str]
        Absolute paths to R1 FASTQ files, 1-to-1 with sample_ids.
    known_sites : list[str]
        Absolute paths to indexed known-sites VCF files for BQSR.
    intervals : list[str]
        Genomic intervals for GenomicsDBImport (e.g. ``["chr20"]``).
    cohort_id : str
        Cohort identifier used to name output files.
    r2_paths : list[str] | None
        Absolute paths to R2 FASTQ files (omit for single-end).
    threads : int
        BWA-MEM2 alignment threads (default 4).
    gatk_sif : str
        Absolute path to GATK4 Apptainer SIF. Empty = use cluster module.
    bwa_sif : str
        Absolute path to BWA-MEM2 Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"64G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"48:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_germline_discovery(
    ...     reference_fasta="/data/ref/hg38.fa",
    ...     sample_ids=["NA12878"],
    ...     r1_paths=["/data/reads/NA12878_R1.fastq.gz"],
    ...     r2_paths=["/data/reads/NA12878_R2.fastq.gz"],
    ...     known_sites=["/data/ref/dbsnp138.vcf.gz"],
    ...     intervals=["chr20"],
    ...     cohort_id="NA12878_chr20",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": reference_fasta},
    }
    if sample_ids and r1_paths:
        bindings["ReadPair"] = {
            "sample_id": sample_ids[0],
            "r1_path": r1_paths[0],
            "r2_path": r2_paths[0] if r2_paths else "",
        }
    inputs: dict[str, object] = {
        "reference_fasta": reference_fasta,
        "sample_ids": sample_ids,
        "r1_paths": r1_paths,
        "known_sites": known_sites,
        "intervals": intervals,
        "cohort_id": cohort_id,
        "threads": threads,
    }
    if r2_paths:
        inputs["r2_paths"] = r2_paths
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    if bwa_sif:
        runtime_images["bwa_sif"] = bwa_sif
    return _run_workflow(
        workflow_name="germline_short_variant_discovery",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_prepare_reference(
    reference_fasta: str,
    known_sites: list[str],
    gatk_sif: str = "",
    bwa_sif: str = "",
    force: bool = False,
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Prepare a reference genome for GATK germline variant calling.

    Parameters
    ----------
    reference_fasta : str
        Absolute path to the reference FASTA file.
    known_sites : list[str]
        Absolute paths to known-sites VCF files to index.
    gatk_sif : str
        Absolute path to GATK4 Apptainer SIF. Empty = use cluster module.
    bwa_sif : str
        Absolute path to BWA-MEM2 Apptainer SIF. Empty = use cluster module.
    force : bool
        Rerun all steps even if outputs exist.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"32G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"04:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_prepare_reference(
    ...     reference_fasta="/data/ref/hg38.fa",
    ...     known_sites=["/data/ref/dbsnp138.vcf.gz", "/data/ref/mills.vcf.gz"],
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": reference_fasta},
    }
    inputs: dict[str, object] = {
        "reference_fasta": reference_fasta,
        "known_sites": known_sites,
        "force": force,
    }
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    if bwa_sif:
        runtime_images["bwa_sif"] = bwa_sif
    return _run_workflow(
        workflow_name="prepare_reference",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_preprocess_sample(
    reference_fasta: str,
    r1: str,
    sample_id: str,
    known_sites: list[str],
    r2: str = "",
    threads: int = 4,
    gatk_sif: str = "",
    bwa_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Preprocess one sample from paired-end FASTQs to BQSR-recalibrated BAM.

    Parameters
    ----------
    reference_fasta : str
        Absolute path to the reference FASTA file.
    r1 : str
        Absolute path to the R1 FASTQ file.
    sample_id : str
        Sample identifier.
    known_sites : list[str]
        Absolute paths to indexed known-sites VCF files for BQSR.
    r2 : str
        Absolute path to the R2 FASTQ file. Empty = single-end.
    threads : int
        BWA-MEM2 alignment threads (default 4).
    gatk_sif : str
        Absolute path to GATK4 Apptainer SIF. Empty = use cluster module.
    bwa_sif : str
        Absolute path to BWA-MEM2 Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"64G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"12:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_preprocess_sample(
    ...     reference_fasta="/data/ref/hg38.fa",
    ...     r1="/data/reads/NA12878_R1.fastq.gz",
    ...     r2="/data/reads/NA12878_R2.fastq.gz",
    ...     sample_id="NA12878",
    ...     known_sites=["/data/ref/dbsnp138.vcf.gz"],
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": reference_fasta},
        "ReadPair": {
            "sample_id": sample_id,
            "r1_path": r1,
            "r2_path": r2,
        },
    }
    inputs: dict[str, object] = {
        "reference_fasta": reference_fasta,
        "r1": r1,
        "sample_id": sample_id,
        "known_sites": known_sites,
        "threads": threads,
    }
    if r2:
        inputs["r2"] = r2
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    if bwa_sif:
        runtime_images["bwa_sif"] = bwa_sif
    return _run_workflow(
        workflow_name="preprocess_sample",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_genotype_refinement(
    reference_fasta: str,
    joint_vcf: str,
    snp_resources: list[str],
    snp_resource_flags: list[dict],
    indel_resources: list[str],
    indel_resource_flags: list[dict],
    cohort_id: str,
    sample_count: int,
    gatk_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Refine a joint-called VCF with two-pass VQSR (SNP then INDEL).

    Parameters
    ----------
    reference_fasta : str
        Absolute path to the reference FASTA file.
    joint_vcf : str
        Absolute path to the joint-called cohort VCF.
    snp_resources : list[str]
        Absolute paths to VCF files for SNP VQSR training.
    snp_resource_flags : list[dict]
        Per-resource flag dicts for SNP pass, e.g.
        ``[{"resource_name": "hapmap", "known": "false", "training": "true",
        "truth": "true", "prior": "15"}]``.
    indel_resources : list[str]
        Absolute paths to VCF files for INDEL VQSR training.
    indel_resource_flags : list[dict]
        Per-resource flag dicts for INDEL pass.
    cohort_id : str
        Cohort identifier.
    sample_count : int
        Number of samples in the cohort.
    gatk_sif : str
        Absolute path to GATK4 Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"32G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"08:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_genotype_refinement(
    ...     reference_fasta="/data/ref/hg38.fa",
    ...     joint_vcf="/data/vcf/cohort_joint.vcf.gz",
    ...     snp_resources=["/data/ref/hapmap.vcf.gz"],
    ...     snp_resource_flags=[{"resource_name": "hapmap", "known": "false",
    ...         "training": "true", "truth": "true", "prior": "15"}],
    ...     indel_resources=["/data/ref/mills.vcf.gz"],
    ...     indel_resource_flags=[{"resource_name": "mills", "known": "false",
    ...         "training": "true", "truth": "true", "prior": "12"}],
    ...     cohort_id="cohort1",
    ...     sample_count=30,
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": reference_fasta},
    }
    inputs: dict[str, object] = {
        "reference_fasta": reference_fasta,
        "joint_vcf": joint_vcf,
        "snp_resources": snp_resources,
        "snp_resource_flags": snp_resource_flags,
        "indel_resources": indel_resources,
        "indel_resource_flags": indel_resource_flags,
        "cohort_id": cohort_id,
        "sample_count": sample_count,
    }
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    return _run_workflow(
        workflow_name="genotype_refinement",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_small_cohort_filter(
    reference_fasta: str,
    joint_vcf: str,
    cohort_id: str,
    gatk_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Hard-filter a joint-called VCF for cohorts too small for VQSR.

    Parameters
    ----------
    reference_fasta : str
        Absolute path to the reference FASTA file.
    joint_vcf : str
        Absolute path to the joint-called cohort VCF to filter.
    cohort_id : str
        Cohort identifier.
    gatk_sif : str
        Absolute path to GATK4 Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"8G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"01:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_small_cohort_filter(
    ...     reference_fasta="/data/ref/hg38.fa",
    ...     joint_vcf="/data/vcf/small_cohort_joint.vcf.gz",
    ...     cohort_id="trio1",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": reference_fasta},
    }
    inputs: dict[str, object] = {
        "reference_fasta": reference_fasta,
        "joint_vcf": joint_vcf,
        "cohort_id": cohort_id,
    }
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    return _run_workflow(
        workflow_name="small_cohort_filter",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_post_genotyping_refinement(
    input_vcf: str,
    cohort_id: str,
    gatk_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Apply CalculateGenotypePosteriors to a joint-called or VQSR-filtered VCF.

    Parameters
    ----------
    input_vcf : str
        Absolute path to the input VCF (joint-called or VQSR-filtered).
    cohort_id : str
        Cohort identifier used to name the output VCF.
    gatk_sif : str
        Absolute path to GATK4 Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"02:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_post_genotyping_refinement(
    ...     input_vcf="/data/vcf/cohort_vqsr.vcf.gz",
    ...     cohort_id="cohort1",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    inputs: dict[str, object] = {
        "input_vcf": input_vcf,
        "cohort_id": cohort_id,
    }
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    return _run_workflow(
        workflow_name="post_genotyping_refinement",
        bindings=None,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_sequential_interval_haplotype_caller(
    reference_fasta: str,
    aligned_bam: str,
    sample_id: str,
    intervals: list[str],
    gatk_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Call per-sample GVCFs serially across intervals, then gather into one GVCF.

    Parameters
    ----------
    reference_fasta : str
        Absolute path to the reference FASTA file.
    aligned_bam : str
        Absolute path to the BQSR-recalibrated BAM.
    sample_id : str
        Sample identifier.
    intervals : list[str]
        Non-empty list of genomic intervals in genomic order (e.g. ``["chr20"]``).
    gatk_sif : str
        Absolute path to GATK4 Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"64G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"24:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_sequential_interval_haplotype_caller(
    ...     reference_fasta="/data/ref/hg38.fa",
    ...     aligned_bam="/data/bam/NA12878_recal.bam",
    ...     sample_id="NA12878",
    ...     intervals=["chr20", "chr21"],
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": reference_fasta},
    }
    inputs: dict[str, object] = {
        "reference_fasta": reference_fasta,
        "aligned_bam": aligned_bam,
        "sample_id": sample_id,
        "intervals": intervals,
    }
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    return _run_workflow(
        workflow_name="sequential_interval_haplotype_caller",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_pre_call_coverage_qc(
    reference_fasta: str,
    aligned_bams: list[str],
    sample_ids: list[str],
    cohort_id: str,
    gatk_sif: str = "",
    multiqc_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Aggregate per-sample WGS and insert-size metrics into a MultiQC report.

    Parameters
    ----------
    reference_fasta : str
        Absolute path to the reference FASTA file.
    aligned_bams : list[str]
        Absolute paths to coordinate-sorted, indexed BAMs.
    sample_ids : list[str]
        Sample identifiers, 1-to-1 with aligned_bams.
    cohort_id : str
        Cohort identifier.
    gatk_sif : str
        Absolute path to GATK4/Picard Apptainer SIF. Empty = use cluster module.
    multiqc_sif : str
        Absolute path to MultiQC Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"04:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_pre_call_coverage_qc(
    ...     reference_fasta="/data/ref/hg38.fa",
    ...     aligned_bams=["/data/bam/NA12878_recal.bam"],
    ...     sample_ids=["NA12878"],
    ...     cohort_id="cohort1",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": reference_fasta},
    }
    inputs: dict[str, object] = {
        "reference_fasta": reference_fasta,
        "aligned_bams": aligned_bams,
        "sample_ids": sample_ids,
        "cohort_id": cohort_id,
    }
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    if multiqc_sif:
        runtime_images["multiqc_sif"] = multiqc_sif
    return _run_workflow(
        workflow_name="pre_call_coverage_qc",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_post_call_qc_summary(
    input_vcf: str,
    cohort_id: str,
    bcftools_sif: str = "",
    multiqc_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run bcftools stats and MultiQC for post-call VCF QC.

    Parameters
    ----------
    input_vcf : str
        Absolute path to the input VCF for bcftools stats.
    cohort_id : str
        Cohort identifier.
    bcftools_sif : str
        Absolute path to bcftools Apptainer SIF. Empty = use cluster module.
    multiqc_sif : str
        Absolute path to MultiQC Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"8G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"01:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_post_call_qc_summary(
    ...     input_vcf="/data/vcf/cohort_filtered.vcf.gz",
    ...     cohort_id="cohort1",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    inputs: dict[str, object] = {
        "input_vcf": input_vcf,
        "cohort_id": cohort_id,
    }
    runtime_images: dict[str, str] = {}
    if bcftools_sif:
        runtime_images["bcftools_sif"] = bcftools_sif
    if multiqc_sif:
        runtime_images["multiqc_sif"] = multiqc_sif
    return _run_workflow(
        workflow_name="post_call_qc_summary",
        bindings=None,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def vc_annotate_variants_snpeff(
    input_vcf: str,
    cohort_id: str,
    snpeff_database: str,
    snpeff_data_dir: str,
    snpeff_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Annotate a VCF with SnpEff functional variant annotation.

    Parameters
    ----------
    input_vcf : str
        Absolute path to the input VCF to annotate.
    cohort_id : str
        Cohort identifier used to name output files.
    snpeff_database : str
        SnpEff database name, e.g. ``"GRCh38.105"`` or ``"hg38"``.
    snpeff_data_dir : str
        Absolute path to the directory containing the pre-downloaded SnpEff
        database cache.
    snpeff_sif : str
        Absolute path to SnpEff Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"04:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> vc_annotate_variants_snpeff(
    ...     input_vcf="/data/vcf/cohort_filtered.vcf.gz",
    ...     cohort_id="cohort1",
    ...     snpeff_database="GRCh38.105",
    ...     snpeff_data_dir="/data/snpeff/data",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    inputs: dict[str, object] = {
        "input_vcf": input_vcf,
        "cohort_id": cohort_id,
        "snpeff_database": snpeff_database,
        "snpeff_data_dir": snpeff_data_dir,
    }
    runtime_images: dict[str, str] = {}
    if snpeff_sif:
        runtime_images["snpeff_sif"] = snpeff_sif
    return _run_workflow(
        workflow_name="annotate_variants_snpeff",
        bindings=None,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Step 2 — annotation flat tools
# ---------------------------------------------------------------------------


def annotation_braker3(
    genome: str,
    rnaseq_bam_path: str = "",
    protein_fasta_path: str = "",
    braker_species: str = "",
    braker3_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the BRAKER3 ab initio annotation workflow.

    At least one of ``rnaseq_bam_path`` or ``protein_fasta_path`` must be
    provided; BRAKER3 requires evidence in practice.

    Parameters
    ----------
    genome : str
        Absolute path to the reference genome FASTA.
    rnaseq_bam_path : str
        Absolute path to the RNA-seq BAM evidence file.
    protein_fasta_path : str
        Absolute path to the protein FASTA evidence file.
    braker_species : str
        Species/model name passed to BRAKER3.
    braker3_sif : str
        Absolute path to the BRAKER3 Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"64G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"24:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_braker3(
    ...     genome="/data/ref/genome.fa",
    ...     rnaseq_bam_path="/data/rnaseq/RNAseq.bam",
    ...     protein_fasta_path="/data/proteins/proteins.fa",
    ...     braker_species="fly",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": genome},
    }
    inputs: dict[str, object] = {"genome": genome}
    if rnaseq_bam_path:
        inputs["rnaseq_bam_path"] = rnaseq_bam_path
    if protein_fasta_path:
        inputs["protein_fasta_path"] = protein_fasta_path
    if braker_species:
        inputs["braker_species"] = braker_species
    runtime_images: dict[str, str] = {}
    if braker3_sif:
        runtime_images["braker3_sif"] = braker3_sif
    return _run_workflow(
        workflow_name="ab_initio_annotation_braker3",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_protein_evidence(
    genome: str,
    protein_fastas: list[str],
    proteins_per_chunk: int = 100,
    exonerate_model: str = "protein2genome",
    exonerate_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run protein evidence alignment with Exonerate against a genome.

    Parameters
    ----------
    genome : str
        Absolute path to the reference genome FASTA.
    protein_fastas : list[str]
        Absolute paths to protein FASTA input files.
    proteins_per_chunk : int
        Maximum number of protein records per Exonerate chunk (default 100).
    exonerate_model : str
        Exonerate alignment model (default ``"protein2genome"``).
    exonerate_sif : str
        Absolute path to Exonerate Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"32G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"04:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_protein_evidence(
    ...     genome="/data/ref/genome.fa",
    ...     protein_fastas=["/data/proteins/uniprot.fa"],
    ...     proteins_per_chunk=200,
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": genome},
    }
    inputs: dict[str, object] = {
        "genome": genome,
        "protein_fastas": protein_fastas,
        "proteins_per_chunk": proteins_per_chunk,
        "exonerate_model": exonerate_model,
    }
    runtime_images: dict[str, str] = {}
    if exonerate_sif:
        runtime_images["exonerate_sif"] = exonerate_sif
    return _run_workflow(
        workflow_name="protein_evidence_alignment",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Step 3 — RNA-seq and remaining showcase families
# ---------------------------------------------------------------------------


def rnaseq_qc(
    ref: str,
    left: str,
    right: str,
    sample_id: str = "sample",
    salmon_sif: str = "",
    fastqc_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run RNA-seq QC and Salmon transcript quantification.

    Parameters
    ----------
    ref : str
        Absolute path to the transcriptome FASTA used for Salmon indexing.
    left : str
        Absolute path to the R1 FASTQ file.
    right : str
        Absolute path to the R2 FASTQ file.
    sample_id : str
        Sample identifier (used for planner type hints, default ``"sample"``).
    salmon_sif : str
        Absolute path to Salmon Apptainer SIF. Empty = use cluster module.
    fastqc_sif : str
        Absolute path to FastQC Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"01:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> rnaseq_qc(
    ...     ref="/data/ref/transcriptome.fa",
    ...     left="/data/reads/sample_R1.fastq.gz",
    ...     right="/data/reads/sample_R2.fastq.gz",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReadSet": {
            "sample_id": sample_id,
            "left_reads_path": left,
            "right_reads_path": right,
        },
    }
    inputs: dict[str, object] = {
        "ref": ref,
        "left": left,
        "right": right,
    }
    runtime_images: dict[str, str] = {}
    if salmon_sif:
        runtime_images["salmon_sif"] = salmon_sif
    if fastqc_sif:
        runtime_images["fastqc_sif"] = fastqc_sif
    return _run_workflow(
        workflow_name="rnaseq_qc_quant",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def rnaseq_fastqc(
    left: str,
    right: str,
    fastqc_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run FastQC quality control on paired-end RNA-seq reads.

    Parameters
    ----------
    left : str
        Absolute path to the R1 FASTQ file.
    right : str
        Absolute path to the R2 FASTQ file.
    fastqc_sif : str
        Absolute path to FastQC Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"8G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"01:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> rnaseq_fastqc(
    ...     left="/data/reads/sample_R1.fastq.gz",
    ...     right="/data/reads/sample_R2.fastq.gz",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    inputs: dict[str, object] = {
        "left": left,
        "right": right,
    }
    runtime_images: dict[str, str] = {}
    if fastqc_sif:
        runtime_images["fastqc_sif"] = fastqc_sif
    return _run_task(
        task_name="fastqc",
        bindings=None,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_busco_qc(
    repeat_filter_results: str,
    busco_lineages_text: str = "eukaryota,metazoa,insecta,arthropoda,diptera",
    busco_sif: str = "",
    busco_cpu: int = 8,
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run BUSCO quality assessment on repeat-filtered proteins.

    Parameters
    ----------
    repeat_filter_results : str
        Absolute path to the repeat-filtering results directory from
        ``annotation_repeat_filtering``.
    busco_lineages_text : str
        Comma-separated BUSCO lineage list.
    busco_sif : str
        Absolute path to BUSCO Apptainer SIF. Empty = use cluster module.
    busco_cpu : int
        CPU count passed to each BUSCO lineage run (default 8).
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"64G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"04:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_busco_qc(
    ...     repeat_filter_results="/results/repeat_filter_20260401/",
    ...     busco_lineages_text="eukaryota,insecta",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "QualityAssessmentTarget": {"source_result_dir": repeat_filter_results},
    }
    inputs: dict[str, object] = {
        "repeat_filter_results": repeat_filter_results,
        "busco_lineages_text": busco_lineages_text,
        "busco_cpu": busco_cpu,
    }
    runtime_images: dict[str, str] = {}
    if busco_sif:
        runtime_images["busco_sif"] = busco_sif
    return _run_workflow(
        workflow_name="annotation_qc_busco",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_eggnog(
    repeat_filter_results: str,
    eggnog_data_dir: str,
    eggnog_sif: str = "",
    eggnog_cpu: int = 24,
    eggnog_database: str = "Diptera",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run EggNOG functional annotation on repeat-filtered proteins.

    Parameters
    ----------
    repeat_filter_results : str
        Absolute path to the repeat-filtering results directory from
        ``annotation_repeat_filtering``.
    eggnog_data_dir : str
        Absolute path to the local EggNOG database directory.
    eggnog_sif : str
        Absolute path to EggNOG-mapper Apptainer SIF. Empty = use cluster module.
    eggnog_cpu : int
        CPU count passed to EggNOG-mapper (default 24).
    eggnog_database : str
        EggNOG database or taxonomic scope (default ``"Diptera"``).
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"64G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"04:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_eggnog(
    ...     repeat_filter_results="/results/repeat_filter_20260401/",
    ...     eggnog_data_dir="/data/eggnog_data/",
    ...     eggnog_database="Diptera",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "QualityAssessmentTarget": {"source_result_dir": repeat_filter_results},
    }
    inputs: dict[str, object] = {
        "repeat_filter_results": repeat_filter_results,
        "eggnog_data_dir": eggnog_data_dir,
        "eggnog_cpu": eggnog_cpu,
        "eggnog_database": eggnog_database,
    }
    runtime_images: dict[str, str] = {}
    if eggnog_sif:
        runtime_images["eggnog_sif"] = eggnog_sif
    return _run_workflow(
        workflow_name="annotation_functional_eggnog",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_agat_stats(
    eggnog_results: str,
    annotation_fasta_path: str = "",
    agat_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Collect AGAT statistics for the EggNOG-annotated GFF3 boundary.

    Parameters
    ----------
    eggnog_results : str
        Absolute path to the EggNOG results directory from
        ``annotation_functional_eggnog``.
    annotation_fasta_path : str
        Optional absolute path to the companion FASTA for AGAT statistics.
    agat_sif : str
        Absolute path to AGAT Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"00:30:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_agat_stats(
    ...     eggnog_results="/results/eggnog_20260402/",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "QualityAssessmentTarget": {"source_result_dir": eggnog_results},
    }
    inputs: dict[str, object] = {"eggnog_results": eggnog_results}
    if annotation_fasta_path:
        inputs["annotation_fasta_path"] = annotation_fasta_path
    runtime_images: dict[str, str] = {}
    if agat_sif:
        runtime_images["agat_sif"] = agat_sif
    return _run_workflow(
        workflow_name="annotation_postprocess_agat",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_agat_convert(
    eggnog_results: str,
    agat_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Convert the EggNOG-annotated GFF3 boundary with AGAT.

    Parameters
    ----------
    eggnog_results : str
        Absolute path to the EggNOG results directory from
        ``annotation_functional_eggnog``.
    agat_sif : str
        Absolute path to AGAT Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"00:30:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_agat_convert(
    ...     eggnog_results="/results/eggnog_20260402/",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "QualityAssessmentTarget": {"source_result_dir": eggnog_results},
    }
    inputs: dict[str, object] = {"eggnog_results": eggnog_results}
    runtime_images: dict[str, str] = {}
    if agat_sif:
        runtime_images["agat_sif"] = agat_sif
    return _run_workflow(
        workflow_name="annotation_postprocess_agat_conversion",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_agat_cleanup(
    agat_conversion_results: str,
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Apply deterministic attribute cleanup to AGAT conversion output.

    Parameters
    ----------
    agat_conversion_results : str
        Absolute path to the AGAT conversion results directory from
        ``annotation_agat_convert``.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"32G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"01:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_agat_cleanup(
    ...     agat_conversion_results="/results/agat_convert_20260403/",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "QualityAssessmentTarget": {"source_result_dir": agat_conversion_results},
    }
    inputs: dict[str, object] = {"agat_conversion_results": agat_conversion_results}
    return _run_workflow(
        workflow_name="annotation_postprocess_agat_cleanup",
        bindings=bindings,
        inputs=inputs,
        runtime_images=None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_table2asn(
    agat_cleanup_results: str,
    genome_fasta: str,
    submission_template: str,
    locus_tag_prefix: str = "",
    organism_annotation: str = "",
    table2asn_binary: str = "table2asn",
    table2asn_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run table2asn to produce an NCBI .sqn submission file.

    Parameters
    ----------
    agat_cleanup_results : str
        Absolute path to the AGAT cleanup results directory from
        ``annotation_agat_cleanup``.
    genome_fasta : str
        Absolute path to the repeat-masked genome FASTA (-i input to table2asn).
    submission_template : str
        Absolute path to the NCBI .sbt template file.
    locus_tag_prefix : str
        BioProject locus-tag prefix assigned by NCBI. Empty = omitted from command.
    organism_annotation : str
        NCBI organism annotation string, e.g.
        ``"[organism=Drosophila melanogaster][isolate=Canton-S]"``.
    table2asn_binary : str
        Name or path of the table2asn executable (default ``"table2asn"``).
    table2asn_sif : str
        Absolute path to table2asn Apptainer SIF. Empty = use cluster module.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"02:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_table2asn(
    ...     agat_cleanup_results="/results/agat_cleanup_20260404/",
    ...     genome_fasta="/data/ref/genome_masked.fa",
    ...     submission_template="/data/ncbi/template.sbt",
    ...     locus_tag_prefix="DMELA",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "QualityAssessmentTarget": {"source_result_dir": agat_cleanup_results},
    }
    inputs: dict[str, object] = {
        "agat_cleanup_results": agat_cleanup_results,
        "genome_fasta": genome_fasta,
        "submission_template": submission_template,
        "table2asn_binary": table2asn_binary,
    }
    if locus_tag_prefix:
        inputs["locus_tag_prefix"] = locus_tag_prefix
    if organism_annotation:
        inputs["organism_annotation"] = organism_annotation
    runtime_images: dict[str, str] = {}
    if table2asn_sif:
        runtime_images["table2asn_sif"] = table2asn_sif
    return _run_workflow(
        workflow_name="annotation_postprocess_table2asn",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_gffread_proteins(
    annotation_gff3: str,
    genome_fasta: str,
    protein_output_stem: str = "annotation",
    gffread_binary: str = "gffread",
    repeat_filter_sif: str = "",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Extract protein sequences from an annotation GFF3 with gffread.

    Parameters
    ----------
    annotation_gff3 : str
        Absolute path to the annotation GFF3 to translate into proteins.
    genome_fasta : str
        Absolute path to the reference genome FASTA passed to gffread with -g.
    protein_output_stem : str
        Filename stem for the emitted protein FASTA files (default
        ``"annotation"``).
    gffread_binary : str
        gffread path or executable name (default ``"gffread"``).
    repeat_filter_sif : str
        Absolute path to the repeat-filter toolchain Apptainer SIF.
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"01:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_gffread_proteins(
    ...     annotation_gff3="/results/braker3/braker.gff3",
    ...     genome_fasta="/data/ref/genome.fa",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": genome_fasta},
    }
    inputs: dict[str, object] = {
        "annotation_gff3": annotation_gff3,
        "genome_fasta": genome_fasta,
        "protein_output_stem": protein_output_stem,
        "gffread_binary": gffread_binary,
    }
    runtime_images: dict[str, str] = {}
    if repeat_filter_sif:
        runtime_images["repeat_filter_sif"] = repeat_filter_sif
    return _run_task(
        task_name="gffread_proteins",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_busco_assess(
    proteins_fasta: str,
    lineage_dataset: str,
    busco_sif: str = "",
    busco_cpu: int = 8,
    busco_mode: str = "prot",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run one BUSCO lineage assessment on a repeat-filtered protein FASTA.

    Parameters
    ----------
    proteins_fasta : str
        Absolute path to the repeat-filtered protein FASTA.
    lineage_dataset : str
        BUSCO lineage dataset identifier or local lineage path passed with
        ``-l``; use ``"auto-lineage"`` to omit ``-l``.
    busco_sif : str
        Absolute path to BUSCO Apptainer SIF. Empty = use cluster module.
    busco_cpu : int
        CPU count passed to BUSCO with ``-c`` (default 8).
    busco_mode : str
        BUSCO mode passed with ``-m`` (default ``"prot"``).
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"16G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"01:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_busco_assess(
    ...     proteins_fasta="/results/proteins/annotation.proteins.fa",
    ...     lineage_dataset="insecta_odb10",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "QualityAssessmentTarget": {"proteins_fasta_path": proteins_fasta},
    }
    inputs: dict[str, object] = {
        "proteins_fasta": proteins_fasta,
        "lineage_dataset": lineage_dataset,
        "busco_cpu": busco_cpu,
        "busco_mode": busco_mode,
    }
    runtime_images: dict[str, str] = {}
    if busco_sif:
        runtime_images["busco_sif"] = busco_sif
    return _run_task(
        task_name="busco_assess_proteins",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


def annotation_exonerate_chunk(
    genome: str,
    protein_chunk: str,
    exonerate_sif: str = "",
    exonerate_model: str = "protein2genome",
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run Exonerate alignment for one protein FASTA chunk against the genome.

    Parameters
    ----------
    genome : str
        Absolute path to the reference genome FASTA used as the Exonerate target.
    protein_chunk : str
        Absolute path to one protein FASTA chunk from ``chunk_protein_fastas``.
    exonerate_sif : str
        Absolute path to Exonerate Apptainer SIF. Empty = use cluster module.
    exonerate_model : str
        Exonerate alignment model (default ``"protein2genome"``).
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"32G"``. Empty = use server default.
    walltime : str
        Wall time, e.g. ``"04:00:00"``. Empty = use server default.
    shared_fs_roots : list[str] | None
        Filesystem prefixes visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS.
    dry_run : bool
        If True, freeze the recipe without executing it.

    Example
    -------
    >>> annotation_exonerate_chunk(
    ...     genome="/data/ref/genome.fa",
    ...     protein_chunk="/data/chunks/chunk_001.fa",
    ...     partition="caslake",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": genome},
    }
    inputs: dict[str, object] = {
        "genome": genome,
        "protein_chunk": protein_chunk,
        "exonerate_model": exonerate_model,
    }
    runtime_images: dict[str, str] = {}
    if exonerate_sif:
        runtime_images["exonerate_sif"] = exonerate_sif
    return _run_task(
        task_name="exonerate_align_chunk",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )


__all__ = [
    # variant_calling
    "vc_germline_discovery",
    "vc_prepare_reference",
    "vc_preprocess_sample",
    "vc_genotype_refinement",
    "vc_small_cohort_filter",
    "vc_post_genotyping_refinement",
    "vc_sequential_interval_haplotype_caller",
    "vc_pre_call_coverage_qc",
    "vc_post_call_qc_summary",
    "vc_annotate_variants_snpeff",
    # annotation
    "annotation_braker3",
    "annotation_protein_evidence",
    "annotation_busco_qc",
    "annotation_eggnog",
    "annotation_agat_stats",
    "annotation_agat_convert",
    "annotation_agat_cleanup",
    "annotation_table2asn",
    "annotation_gffread_proteins",
    "annotation_busco_assess",
    "annotation_exonerate_chunk",
    # rnaseq
    "rnaseq_qc",
    "rnaseq_fastqc",
]
