"""Curated resource bundles — turn-key starter inputs for registered entries.

A bundle is a named, typed snapshot of bindings + scalar inputs + container
images pointing at existing fixtures under ``data/``. Bundles stay portable
across pipeline families because they key on the stable planner types from
``planner_types.py`` and the biology types produced by M23–M26 tasks.

Adding a new family's bundle means appending one entry to ``BUNDLES`` — nothing
in server.py, planning.py, or mcp_contract.py needs to change.

Availability is checked at call time inside ``list_bundles`` / ``load_bundle``
so the server boots regardless of whether every seeded bundle's backing data is
present on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flytetest.registry import get_entry


@dataclass(frozen=True)
class ResourceBundle:
    name: str
    description: str
    pipeline_family: str
    bindings: dict[str, dict]       # planner-type name → field dict
    inputs: dict[str, object]       # scalar defaults
    runtime_images: dict[str, str]  # container defaults; scientist may override
    tool_databases: dict[str, str]  # reference data (BUSCO lineage, EVM weights, dbSNP, ...)
    applies_to: tuple[str, ...]     # registered entry names
    fetch_hints: tuple[str, ...] = ()  # scientist-actionable fetch/stage instructions


BUNDLES: dict[str, ResourceBundle] = {
    "braker3_small_eukaryote": ResourceBundle(
        name="braker3_small_eukaryote",
        description=(
            "Small-eukaryote BRAKER3 annotation starter kit: reference genome, "
            "RNA-seq BAM evidence, and protein FASTA evidence."
        ),
        pipeline_family="annotation",
        bindings={
            "ReferenceGenome": {"fasta_path": "data/braker3/reference/genome.fa"},
            "TranscriptEvidenceSet": {"bam_path": "data/braker3/rnaseq/RNAseq.bam"},
            "ProteinEvidenceSet": {
                "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
            },
        },
        inputs={"braker_species": "demo_species"},
        runtime_images={"braker_sif": "data/images/braker3.sif"},
        tool_databases={},
        applies_to=("ab_initio_annotation_braker3",),
        fetch_hints=(
            "Pull the BRAKER3 container: `scripts/rcc/download_minimal_images.sh` (or `apptainer pull data/images/braker3.sif docker://teambraker/braker3:latest`)",
            "Stage the BRAKER3 fixture set under data/braker3/ (reference, rnaseq BAM, protein FASTA) — see scripts/rcc/README.md for expected layout",
        ),
    ),
    "busco_eukaryota_genome_fixture": ResourceBundle(
        name="busco_eukaryota_genome_fixture",
        description=(
            "BUSCO genome-mode fixture for the eukaryota test FASTA: "
            "runs auto-lineage detection against the minimal eukaryota genome "
            "included under data/busco/test_data/."
        ),
        pipeline_family="annotation",
        bindings={},
        inputs={
            "proteins_fasta": "data/busco/test_data/eukaryota/genome.fna",
            "lineage_dataset": "auto-lineage",
            "busco_cpu": 2,
            "busco_mode": "geno",
        },
        runtime_images={"busco_sif": "data/images/busco_v6.0.0_cv1.sif"},
        tool_databases={},
        applies_to=("busco_assess_proteins",),
        fetch_hints=(
            "Pull the BUSCO container: `apptainer pull data/images/busco_v6.0.0_cv1.sif docker://ezlabgva/busco:v6.0.0_cv1`",
            "Download the eukaryota test fixture: `scripts/rcc/download_minimal_busco_fixture.sh`",
        ),
    ),
    "m18_busco_demo": ResourceBundle(
        name="m18_busco_demo",
        description=(
            "M18 BUSCO fixture: protein quality assessment against the "
            "eukaryota_odb10 lineage dataset."
        ),
        pipeline_family="annotation",
        bindings={
            "QualityAssessmentTarget": {"fasta_path": "data/busco/fixtures/proteins.fa"},
        },
        inputs={"lineage_dataset": "eukaryota_odb10", "busco_cpu": 2, "busco_mode": "proteins"},
        runtime_images={"busco_sif": "data/images/busco_v6.0.0_cv1.sif"},
        tool_databases={"busco_lineage_dir": "data/busco/lineages/eukaryota_odb10"},
        applies_to=("annotation_qc_busco",),
        fetch_hints=(
            "Pull the BUSCO container: `scripts/rcc/download_minimal_images.sh` (or `apptainer pull data/images/busco_v6.0.0_cv1.sif docker://ezlabgva/busco:v6.0.0_cv1`)",
            "Download the eukaryota_odb10 lineage into data/busco/lineages/ (see https://busco.ezlabgva.org/ for the tarball) and extract to data/busco/lineages/eukaryota_odb10/",
            "Stage a protein FASTA at data/busco/fixtures/proteins.fa — a BRAKER3 run output or any reference proteome works",
        ),
    ),
    "protein_evidence_demo": ResourceBundle(
        name="protein_evidence_demo",
        description=(
            "Protein evidence alignment demo: reference genome and protein FASTA "
            "for Exonerate-based chunk alignment."
        ),
        pipeline_family="annotation",
        bindings={
            "ReferenceGenome": {"fasta_path": "data/braker3/reference/genome.fa"},
            "ProteinEvidenceSet": {
                "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
            },
        },
        inputs={},
        runtime_images={"exonerate_sif": "data/images/exonerate_2.2.0--1.sif"},
        tool_databases={},
        applies_to=("protein_evidence_alignment",),
        fetch_hints=(
            "Pull the Exonerate container: `scripts/rcc/download_minimal_images.sh` (or `apptainer pull data/images/exonerate_2.2.0--1.sif docker://quay.io/biocontainers/exonerate:2.2.0--1`)",
            "Stage the BRAKER3 fixture set under data/braker3/ (reference FASTA and protein FASTA) — see scripts/rcc/README.md for expected layout",
        ),
    ),
    "variant_calling_germline_minimal": ResourceBundle(
        name="variant_calling_germline_minimal",
        description=(
            "Minimal germline variant calling demo: chr20 slice of NA12878 "
            "with reference, known-sites VCFs (bgzipped + tabix indexed), "
            "and paired reads (synthetic by default, real via REAL_READS=1). "
            "Stage all data with: bash scripts/rcc/stage_gatk_local.sh"
        ),
        pipeline_family="variant_calling",
        bindings={
            "ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"},
            "ReadPair": {
                "sample_id": "NA12878_chr20",
                "r1_path": "data/reads/NA12878_chr20_R1.fastq.gz",
                "r2_path": "data/reads/NA12878_chr20_R2.fastq.gz",
            },
            # KnownSites dropped — use scalar `known_sites` list below.
        },
        inputs={
            "ref_path": "data/references/hg38/chr20.fa",
            "known_sites": [
                "data/references/hg38/dbsnp_138.hg38.vcf.gz",
                "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz",
            ],
            "r1_path": "data/reads/NA12878_chr20_R1.fastq.gz",
            "r2_path": "data/reads/NA12878_chr20_R2.fastq.gz",
            "results_dir": "results/germline_minimal/",
            "intervals": ["chr20"],
            "cohort_id": "NA12878_chr20",
        },
        runtime_images={
            "sif_path": "data/images/gatk4.sif",
            "bwa_sif": "data/images/bwa_mem2.sif",
        },
        tool_databases={
            "dbsnp": "data/references/hg38/dbsnp_138.hg38.vcf.gz",
            "mills": "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz",
        },
        applies_to=(
            "prepare_reference",
            "preprocess_sample",
            "germline_short_variant_discovery",
        ),
        fetch_hints=(
            "Stage reference data + reads: bash scripts/rcc/stage_gatk_local.sh",
            "Pull GATK4 SIF (~8 GB):        bash scripts/rcc/pull_gatk_image.sh",
            "Build bwa-mem2+samtools SIF:   bash scripts/rcc/build_bwa_mem2_sif.sh",
            "Verify all fixtures:           bash scripts/rcc/check_gatk_fixtures.sh",
        ),
    ),
    "variant_calling_vqsr_chr20": ResourceBundle(
        name="variant_calling_vqsr_chr20",
        description=(
            "Full-chr20 NA12878 WGS germline VQSR demo. "
            "Uses a joint-called VCF from germline_short_variant_discovery plus "
            "five GATK Best Practices training VCFs for SNP + INDEL recalibration. "
            "Reference data from gs://gcp-public-data--broad-references/hg38/v0/. "
            "NA12878 chr20 BAM and VCF are user-staged (SCP); "
            "training VCFs are downloaded by scripts/rcc/download_vqsr_training_vcfs.sh."
        ),
        pipeline_family="variant_calling",
        bindings={
            "ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"},
            "VariantCallSet": {
                "vcf_path": "data/vcf/NA12878_chr20_joint.vcf.gz",
                "variant_type": "vcf",
                "sample_id": "NA12878_chr20",
            },
        },
        inputs={
            "ref_path": "data/references/hg38/chr20.fa",
            "joint_vcf": "data/vcf/NA12878_chr20_joint.vcf.gz",
            "snp_resources": [
                "data/references/hg38/hapmap_3.3.hg38.vcf.gz",
                "data/references/hg38/1000G_omni2.5.hg38.vcf.gz",
                "data/references/hg38/1000G_phase1.snps.high_confidence.hg38.vcf.gz",
                "data/references/hg38/Homo_sapiens_assembly38.dbsnp138.vcf",
            ],
            "snp_resource_flags": [
                {"resource_name": "hapmap", "known": "false", "training": "true",  "truth": "true",  "prior": "15"},
                {"resource_name": "omni",   "known": "false", "training": "true",  "truth": "true",  "prior": "12"},
                {"resource_name": "1000g",  "known": "false", "training": "true",  "truth": "false", "prior": "10"},
                {"resource_name": "dbsnp",  "known": "true",  "training": "false", "truth": "false", "prior": "2"},
            ],
            "indel_resources": [
                "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz",
                "data/references/hg38/Homo_sapiens_assembly38.dbsnp138.vcf",
            ],
            "indel_resource_flags": [
                {"resource_name": "mills", "known": "false", "training": "true",  "truth": "true",  "prior": "12"},
                {"resource_name": "dbsnp", "known": "true",  "training": "false", "truth": "false", "prior": "2"},
            ],
            "cohort_id": "NA12878_chr20",
            "results_dir": "results/vqsr_chr20/",
        },
        runtime_images={"sif_path": "data/images/gatk4.sif"},
        tool_databases={
            "hapmap": "data/references/hg38/hapmap_3.3.hg38.vcf.gz",
            "omni":   "data/references/hg38/1000G_omni2.5.hg38.vcf.gz",
            "1000g":  "data/references/hg38/1000G_phase1.snps.high_confidence.hg38.vcf.gz",
            "mills":  "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz",
            "dbsnp":  "data/references/hg38/Homo_sapiens_assembly38.dbsnp138.vcf",
        },
        applies_to=(
            "variant_recalibrator",
            "apply_vqsr",
            "genotype_refinement",
        ),
        fetch_hints=(
            "Download training VCFs: bash scripts/rcc/download_vqsr_training_vcfs.sh",
            "Stage NA12878 chr20 BAM via SCP (if running on HPC or download on HPC); run germline_short_variant_discovery to produce the joint VCF at data/vcf/NA12878_chr20_joint.vcf.gz",
            "Pull GATK4 SIF image: bash scripts/rcc/pull_gatk_image.sh",
            "chr20.fa must match the Homo_sapiens_assembly38.fasta reference used for alignment (contig name 'chr20', not '20')",
        ),
    ),
    "rnaseq_paired_demo": ResourceBundle(
        name="rnaseq_paired_demo",
        description=(
            "Paired RNA-seq transcript evidence demo: reference genome and "
            "paired-end reads for STAR + Trinity assembly."
        ),
        pipeline_family="annotation",
        bindings={
            "ReferenceGenome": {"fasta_path": "data/braker3/reference/genome.fa"},
            "ReadSet": {
                "sample_id": "demo",
                "left_reads_path": "data/braker3/rnaseq/reads_1.fq.gz",
                "right_reads_path": "data/braker3/rnaseq/reads_2.fq.gz",
            },
        },
        inputs={},
        runtime_images={"star_sif": "data/images/star_2.7.10b.sif"},
        tool_databases={},
        applies_to=("transcript_evidence_generation",),
        fetch_hints=(
            "Pull the STAR container: `scripts/rcc/download_minimal_images.sh` (or `apptainer pull data/images/star_2.7.10b.sif docker://quay.io/biocontainers/star:2.7.10b--h9ee0642_0`)",
            "Stage the BRAKER3 fixture set under data/braker3/ (reference FASTA and paired reads at data/braker3/rnaseq/reads_1.fq.gz and reads_2.fq.gz) — see scripts/rcc/README.md for expected layout",
        ),
    ),
}


@dataclass(frozen=True)
class BundleAvailability:
    """Structured availability result for a bundle.

    ``available=True`` means every referenced file/directory exists on disk and
    the bundle is structurally consistent with its declared ``applies_to``
    entries.  ``available=False`` means one or more paths are missing or the
    registry contract is violated; ``reasons`` lists each problem as a short
    string suitable for surfacing to the scientist.
    """

    name: str
    available: bool
    reasons: tuple[str, ...] = ()


def _check_bundle_availability(b: ResourceBundle) -> BundleAvailability:
    """Return structured availability for a bundle without raising.

    This is the runtime check used by ``list_bundles()`` and ``load_bundle()``.
    It defers path validation to call time so that a missing BUSCO lineage
    directory cannot prevent the server from starting or block unrelated tasks.
    """
    reasons: list[str] = []

    for type_name, field_dict in b.bindings.items():
        for field_name, value in field_dict.items():
            if field_name.endswith("_path") and not Path(value).exists():
                reasons.append(f"{type_name}.{field_name} missing: {value}")

    for key, value in b.runtime_images.items():
        if not Path(value).exists():
            reasons.append(f"runtime_image {key!r} missing: {value}")

    for key, value in b.tool_databases.items():
        if not Path(value).exists():
            reasons.append(f"tool_database {key!r} missing: {value}")

    for entry_name in b.applies_to:
        try:
            entry = get_entry(entry_name)
        except KeyError:
            reasons.append(f"applies_to entry {entry_name!r} not in registry")
            continue
        accepted = set(entry.compatibility.accepted_planner_types)
        missing_types = set(b.bindings) - accepted
        if missing_types:
            reasons.append(
                f"bindings {sorted(missing_types)} not accepted by {entry_name!r} "
                f"(accepts {sorted(accepted)})"
            )
        if entry.compatibility.pipeline_family != b.pipeline_family:
            reasons.append(
                f"pipeline_family {b.pipeline_family!r} mismatches "
                f"{entry_name!r} family {entry.compatibility.pipeline_family!r}"
            )

    if reasons and b.fetch_hints:
        reasons.append("To resolve:")
        reasons.extend(f"  - {hint}" for hint in b.fetch_hints)

    return BundleAvailability(name=b.name, available=not reasons, reasons=tuple(reasons))


def list_bundles(pipeline_family: str | None = None) -> list[dict]:
    """Enumerate curated bundles, optionally filtered by pipeline family.

    Each entry includes an ``available`` flag plus a ``reasons`` list.
    Unavailable bundles are surfaced rather than hidden so a scientist can see
    what is missing and decide whether to resolve the paths or choose a
    different bundle.
    """
    results: list[dict] = []
    for b in BUNDLES.values():
        if pipeline_family is not None and b.pipeline_family != pipeline_family:
            continue
        status = _check_bundle_availability(b)
        results.append({
            "name": b.name,
            "description": b.description,
            "pipeline_family": b.pipeline_family,
            "applies_to": list(b.applies_to),
            "binding_types": sorted(b.bindings.keys()),
            "available": status.available,
            "reasons": list(status.reasons),
        })
    return results


def load_bundle(name: str) -> dict:
    """Return a bundle's typed bindings + scalar inputs + runtime images ready
    to spread into ``run_task`` / ``run_workflow``.

    Raises ``KeyError`` for unknown names (with the available names in the
    message).  Returns a structured reply with ``supported=False`` for a
    known-but-unavailable bundle — never silently returning partial data.
    """
    if name not in BUNDLES:
        raise KeyError(f"Unknown bundle {name!r}. Available: {sorted(BUNDLES)}")
    b = BUNDLES[name]
    status = _check_bundle_availability(b)
    if not status.available:
        return {
            "supported": False,
            "name": b.name,
            "reasons": list(status.reasons),
            "next_steps": [
                "Resolve the missing paths under data/ and retry load_bundle(...)",
                "Or call list_available_bindings() to locate substitute inputs",
            ],
        }
    return {
        "supported": True,
        "bindings": dict(b.bindings),
        "inputs": dict(b.inputs),
        "runtime_images": dict(b.runtime_images),
        "tool_databases": dict(b.tool_databases),
        "description": b.description,
        "pipeline_family": b.pipeline_family,
    }
