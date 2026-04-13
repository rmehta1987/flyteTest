"""EggNOG functional-annotation tasks for the post-BUSCO milestone.

This module runs EggNOG-mapper on the repeat-filtered protein boundary, derives
a deterministic `tx2gene` bridge from the repeat-filtered GFF3, and propagates
the resulting annotations into a reviewable GFF3 bundle without broadening into
AGAT or submission-prep work.

Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
input/output expectations follow `docs/tool_refs/eggnog-mapper.md`.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir, File

from flytetest.config import (
    EGGNOG_RESULTS_PREFIX,
    EGGNOG_WORKFLOW_NAME,
    RESULTS_ROOT,
    eggnog_env,
    project_mkdtemp,
    require_path,
    run_tool,
)
from flytetest.gff3 import (
    attribute_value as _attribute_value,
    escape_value as _escape_gff3_value,
    format_attributes as _format_gff3_attributes,
    parse_attributes as _parse_gff3_attributes,
)
from flytetest.manifest_io import (
    as_json_compatible as _as_json_compatible,
    copy_file as _copy_file,
    copy_tree as _copy_tree,
    read_json as _read_json,
    write_json as _write_json,
)


_EGGNOG_OUTPUT_PREFIX = "eggnog_output"


def _manifest_path(directory: Path, label: str) -> Path:
    """Resolve the manifest that anchors a staged or collected EggNOG bundle."""
    return require_path(directory / "run_manifest.json", f"{label} manifest")


def _manifest_output_path(manifest: dict[str, Any], key: str) -> Path | None:
    """Resolve one recorded output path from a loaded EggNOG manifest."""
    output_path = manifest.get("outputs", {}).get(key)
    if not output_path:
        return None
    return require_path(Path(str(output_path)), f"Manifest output `{key}`")


def _repeat_filter_final_proteins(results_dir: Path) -> Path:
    """Resolve the final repeat-filtered protein FASTA from a results bundle."""
    manifest_path = results_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        manifest_output = _manifest_output_path(manifest, "final_proteins_fasta")
        if manifest_output is not None:
            return manifest_output
    return require_path(
        results_dir / "all_repeats_removed.proteins.fa",
        "Repeat-filtered proteins FASTA",
    )


def _repeat_filter_final_gff3(results_dir: Path) -> Path:
    """Resolve the final repeat-filtered GFF3 from a results bundle."""
    manifest_path = results_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        manifest_output = _manifest_output_path(manifest, "all_repeats_removed_gff3")
        if manifest_output is not None:
            return manifest_output
    return require_path(
        results_dir / "all_repeats_removed.gff3",
        "Repeat-filtered GFF3",
    )

def _set_attribute(attributes: list[tuple[str, str]], key: str, value: str) -> list[tuple[str, str]]:
    """Replace or append one GFF3 attribute while preserving order."""
    escaped = _escape_gff3_value(value)
    updated: list[tuple[str, str]] = []
    replaced = False
    for current_key, current_value in attributes:
        if current_key == key:
            if replaced:
                continue
            updated.append((key, escaped))
            replaced = True
            continue
        updated.append((current_key, current_value))
    if not replaced:
        updated.append((key, escaped))
    return updated


def _tx2gene_rows_from_gff3(gff3_path: Path) -> list[tuple[str, str]]:
    """Extract transcript-to-gene rows from the repeat-filtered GFF3 boundary."""
    rows: list[tuple[str, str]] = []
    fallback_rows: list[tuple[str, str]] = []
    for raw_line in gff3_path.read_text().splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        fields = raw_line.split("\t")
        if len(fields) != 9:
            continue
        feature_type = fields[2]
        attributes = _parse_gff3_attributes(fields[8])
        feature_id = _attribute_value(attributes, "ID")
        parent = _attribute_value(attributes, "Parent")
        if feature_id is None or parent is None:
            continue
        first_parent = parent.split(",")[0]
        row = (feature_id, first_parent)
        if feature_type in {"mRNA", "transcript"}:
            rows.append(row)
        else:
            fallback_rows.append(row)
    return rows or fallback_rows


def _write_tx2gene(rows: list[tuple[str, str]], destination: Path) -> Path:
    """Write the transcript-to-gene bridge used by the EggNOG collector."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerows(rows)
    return destination


def _annotation_label_from_row(header: list[str], columns: list[str]) -> tuple[str, str] | None:
    """Extract the query ID and preferred annotation label from one EggNOG row."""
    if not columns:
        return None
    row = dict(zip(header, columns)) if header and len(header) == len(columns) else {}
    query = row.get("query") or row.get("query_name") or columns[0]
    label_candidates = (
        row.get("Preferred_name"),
        row.get("Description"),
        row.get("seed_ortholog"),
        row.get("seed_eggNOG_ortholog"),
        row.get("eggNOG_OGs"),
    )
    label = next((candidate for candidate in label_candidates if candidate and candidate.strip()), None)
    if label is None and len(columns) > 1 and columns[1].strip():
        label = columns[1]
    if query and label:
        return query.strip(), label.strip()
    return None


def _read_eggnog_annotations(annotations_path: Path) -> dict[str, str]:
    """Read EggNOG annotations into a deterministic query-to-label mapping."""
    header: list[str] = []
    annotations: dict[str, str] = {}
    for raw_line in annotations_path.read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            maybe_header = line.lstrip("#").split("\t")
            if maybe_header and maybe_header[0] in {"query", "query_name"}:
                header = maybe_header
            continue
        columns = line.split("\t")
        parsed = _annotation_label_from_row(header, columns)
        if parsed is not None:
            query, label = parsed
            annotations[query] = label
    return annotations


def _build_gene_annotations(gff3_path: Path, annotations: dict[str, str]) -> dict[str, str]:
    """Lift transcript-level EggNOG labels to gene IDs through the GFF3 boundary."""
    gene_to_transcripts: dict[str, list[str]] = {}
    for raw_line in gff3_path.read_text().splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        fields = raw_line.split("\t")
        if len(fields) != 9:
            continue
        feature_type = fields[2]
        if feature_type not in {"mRNA", "transcript"}:
            continue
        attributes = _parse_gff3_attributes(fields[8])
        feature_id = _attribute_value(attributes, "ID")
        parent = _attribute_value(attributes, "Parent")
        if feature_id is None or parent is None:
            continue
        for parent_id in parent.split(","):
            gene_to_transcripts.setdefault(parent_id, []).append(feature_id)

    gene_annotations: dict[str, str] = {}
    for gene_id, transcript_ids in gene_to_transcripts.items():
        for transcript_id in transcript_ids:
            annotation = annotations.get(transcript_id)
            if annotation:
                gene_annotations[gene_id] = annotation
                break
    return gene_annotations


def _write_annotated_gff3(source_gff3: Path, annotations: dict[str, str], destination: Path) -> Path:
    """Propagate EggNOG labels into the deterministic annotation GFF3 boundary."""
    gene_annotations = _build_gene_annotations(source_gff3, annotations)
    out_lines: list[str] = []
    for raw_line in source_gff3.read_text().splitlines():
        if not raw_line or raw_line.startswith("#"):
            out_lines.append(raw_line)
            continue
        fields = raw_line.split("\t")
        if len(fields) != 9:
            out_lines.append(raw_line)
            continue
        feature_type = fields[2]
        attributes = _parse_gff3_attributes(fields[8])
        feature_id = _attribute_value(attributes, "ID")
        annotation = None
        if feature_type == "gene" and feature_id is not None:
            annotation = gene_annotations.get(feature_id)
        elif feature_id is not None:
            annotation = annotations.get(feature_id)
        if annotation:
            attributes = _set_attribute(attributes, "Name", annotation)
            attributes = _set_attribute(attributes, "EggNOG", annotation)
        fields[8] = _format_gff3_attributes(attributes)
        out_lines.append("\t".join(fields))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(out_lines) + "\n")
    return destination


@eggnog_env.task
def eggnog_map(
    repeat_filter_results: Dir,
    eggnog_data_dir: str,
    eggnog_sif: str = "",
    eggnog_cpu: int = 24,
    eggnog_database: str = "Diptera",
    eggnog_mode: str = "hmmer",
) -> Dir:
    """Run EggNOG-mapper on the repeat-filtered protein boundary."""
    repeat_filter_dir = require_path(
        Path(repeat_filter_results.download_sync()),
        "Repeat-filtering results directory",
    )
    eggnog_data_root = require_path(Path(eggnog_data_dir), "EggNOG data directory")
    proteins_fasta = _repeat_filter_final_proteins(repeat_filter_dir)
    repeat_filter_gff3 = _repeat_filter_final_gff3(repeat_filter_dir)

    work_dir = project_mkdtemp("eggnog_run_") / "eggnog"
    work_dir.mkdir(parents=True, exist_ok=True)

    source_boundary_dir = work_dir / "source_boundary"
    source_boundary_dir.mkdir(parents=True, exist_ok=True)
    staged_proteins_fasta = _copy_file(proteins_fasta, source_boundary_dir / "all_repeats_removed.proteins.fa")
    staged_gff3 = _copy_file(repeat_filter_gff3, source_boundary_dir / "all_repeats_removed.gff3")

    tx2gene_rows = _tx2gene_rows_from_gff3(staged_gff3)
    tx2gene_tsv = _write_tx2gene(tx2gene_rows, work_dir / "tx2gene.tsv")

    bind_paths = [repeat_filter_dir, eggnog_data_root, work_dir]
    run_tool(
        [
            "emapper.py",
            "-m",
            eggnog_mode,
            "-i",
            str(staged_proteins_fasta),
            "-o",
            _EGGNOG_OUTPUT_PREFIX,
            "-d",
            eggnog_database,
            "--data_dir",
            str(eggnog_data_root),
            "--cpu",
            str(eggnog_cpu),
            "--decorate_gff",
            str(staged_gff3),
            "--report_orthologs",
            "--excel",
        ],
        eggnog_sif,
        bind_paths,
        cwd=work_dir,
    )

    annotations_path = require_path(
        work_dir / f"{_EGGNOG_OUTPUT_PREFIX}.emapper.annotations",
        "EggNOG annotations",
    )
    decorated_gff_path = require_path(
        work_dir / f"{_EGGNOG_OUTPUT_PREFIX}.emapper.decorated.gff",
        "EggNOG decorated GFF3",
    )
    annotation_map = _read_eggnog_annotations(annotations_path)
    annotated_gff_path = _write_annotated_gff3(
        staged_gff3,
        annotation_map,
        work_dir / f"{_EGGNOG_OUTPUT_PREFIX}.annotated.gff3",
    )

    manifest = {
        "stage": "eggnog_map",
        "assumptions": [
            "EggNOG-mapper is run in explicit HMMER mode with a locally staged EggNOG database directory.",
            "The notes describe a downstream GFF3 decoration step; this repo records the tx2gene bridge and applies the gene-name propagation deterministically so the final bundle stays reviewable.",
            "Database download and staging remain external to this milestone.",
        ],
        "inputs": {
            "repeat_filter_results": str(repeat_filter_dir),
            "eggnog_data_dir": str(eggnog_data_root),
            "eggnog_database": eggnog_database,
            "eggnog_mode": eggnog_mode,
            "eggnog_sif": eggnog_sif,
            "eggnog_cpu": eggnog_cpu,
        },
        "outputs": {
            "repeat_filter_proteins_fasta": str(staged_proteins_fasta),
            "repeat_filter_gff3": str(staged_gff3),
            "tx2gene_tsv": str(tx2gene_tsv),
            "eggnog_annotations": str(annotations_path),
            "eggnog_decorated_gff": str(decorated_gff_path),
            "eggnog_annotated_gff3": str(annotated_gff_path),
        },
    }
    _write_json(work_dir / "run_manifest.json", manifest)
    return Dir(path=str(work_dir))


@eggnog_env.task
def collect_eggnog_results(
    repeat_filter_results: Dir,
    eggnog_run: Dir,
) -> Dir:
    """Collect the EggNOG run into the stable functional-annotation bundle."""
    repeat_filter_dir = require_path(
        Path(repeat_filter_results.download_sync()),
        "Repeat-filtering results directory",
    )
    eggnog_run_dir = require_path(Path(eggnog_run.download_sync()), "EggNOG run directory")

    eggnog_manifest = _read_json(_manifest_path(eggnog_run_dir, "EggNOG run"))
    eggnog_database = str(eggnog_manifest.get("inputs", {}).get("eggnog_database", "eggnog"))
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{EGGNOG_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_boundary_dir = out_dir / "source_boundary"
    source_boundary_dir.mkdir(parents=True, exist_ok=True)
    copied_proteins = _copy_file(
        _repeat_filter_final_proteins(repeat_filter_dir),
        source_boundary_dir / "all_repeats_removed.proteins.fa",
    )
    copied_gff3 = _copy_file(
        _repeat_filter_final_gff3(repeat_filter_dir),
        source_boundary_dir / "all_repeats_removed.gff3",
    )

    source_manifests_dir = out_dir / "source_manifests"
    source_manifests_dir.mkdir(parents=True, exist_ok=True)
    copied_repeat_filter_manifest = _copy_file(
        _manifest_path(repeat_filter_dir, "Repeat-filtering results"),
        source_manifests_dir / "repeat_filter.run_manifest.json",
    )

    copied_run_dir = _copy_tree(eggnog_run_dir, out_dir / "eggnog_runs" / eggnog_database)
    copied_tx2gene = _copy_file(
        require_path(copied_run_dir / "tx2gene.tsv", "EggNOG tx2gene TSV"),
        out_dir / "all_repeats_removed.tx2gene.tsv",
    )
    copied_annotations = _copy_file(
        require_path(copied_run_dir / f"{_EGGNOG_OUTPUT_PREFIX}.emapper.annotations", "EggNOG annotations"),
        out_dir / "eggnog.emapper.annotations",
    )
    copied_decorated_gff = _copy_file(
        require_path(copied_run_dir / f"{_EGGNOG_OUTPUT_PREFIX}.emapper.decorated.gff", "EggNOG decorated GFF3"),
        out_dir / "eggnog.emapper.decorated.gff",
    )
    copied_annotated_gff = _copy_file(
        require_path(copied_run_dir / f"{_EGGNOG_OUTPUT_PREFIX}.annotated.gff3", "EggNOG annotated GFF3"),
        out_dir / "all_repeats_removed.eggnog.gff3",
    )

    manifest = {
        "workflow": EGGNOG_WORKFLOW_NAME,
        "assumptions": [
            "This milestone starts from the repeat-filtered protein FASTA boundary and keeps the repeat-filtered GFF3 boundary available for downstream review.",
            "The repo records the tx2gene bridge and the decorated GFF3 boundary explicitly so later cleanup stages can remain auditable.",
            "EggNOG database download and staging remain external and are not managed by this bundle collector.",
            "AGAT and table2asn remain deferred after this milestone.",
        ],
        "source_bundle": {
            "repeat_filter_results": str(repeat_filter_dir),
            "eggnog_run": str(eggnog_run_dir),
        },
        "copied_source_manifests": {
            "repeat_filter": str(copied_repeat_filter_manifest),
        },
        "inputs": {
            "repeat_filter_proteins_fasta": str(copied_proteins),
            "repeat_filter_gff3": str(copied_gff3),
            "eggnog_database": eggnog_database,
            "eggnog_annotations": str(require_path(copied_annotations, "EggNOG annotations")),
        },
        "outputs": {
            "repeat_filter_proteins_fasta": str(copied_proteins),
            "repeat_filter_gff3": str(copied_gff3),
            "tx2gene_tsv": str(copied_tx2gene),
            "eggnog_annotations": str(copied_annotations),
            "eggnog_decorated_gff": str(copied_decorated_gff),
            "eggnog_annotated_gff3": str(copied_annotated_gff),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


__all__ = [
    "collect_eggnog_results",
    "eggnog_map",
]
