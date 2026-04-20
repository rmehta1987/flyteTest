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
