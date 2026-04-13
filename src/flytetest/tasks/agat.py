"""AGAT post-processing tasks for the post-EggNOG milestone slices.

This module keeps the AGAT boundary split into narrow slices: statistics,
conversion, and deterministic post-conversion cleanup before table2asn. The
tool-level command shapes and input/output expectations follow
`docs/tool_refs/agat.md`, while the current milestone keeps the cleanup rules as
deterministic in-repo transforms.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir

from flytetest.config import (
    AGAT_CLEANUP_RESULTS_PREFIX,
    AGAT_CLEANUP_WORKFLOW_NAME,
    AGAT_CONVERSION_RESULTS_PREFIX,
    AGAT_CONVERSION_WORKFLOW_NAME,
    AGAT_RESULTS_PREFIX,
    AGAT_WORKFLOW_NAME,
    RESULTS_ROOT,
    agat_cleanup_env,
    agat_conversion_env,
    agat_env,
    project_mkdtemp,
    require_path,
    run_tool,
)


_AGAT_OUTPUT_DIRNAME = "agat_output"
_AGAT_OUTPUT_FILENAME = "agat_statistics.tsv"
_AGAT_CONVERT_OUTPUT_FILENAME = "all_repeats_removed.agat.gff3"
_AGAT_CLEANED_OUTPUT_FILENAME = "all_repeats_removed.agat.cleaned.gff3"
_AGAT_CLEANUP_SUMMARY_FILENAME = "agat_cleanup_summary.json"


def _as_json_compatible(value: Any) -> Any:
    """Convert manifest values into JSON-serializable primitives."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _as_json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_as_json_compatible(item) for item in value]
    if isinstance(value, list):
        return [_as_json_compatible(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write an indented JSON payload to a stable path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_as_json_compatible(payload), indent=2))


def _read_json(path: Path) -> dict[str, Any]:
    """Read one JSON manifest into a dictionary."""
    return json.loads(path.read_text())


def _copy_file(source: Path, destination: Path) -> Path:
    """Copy one file into a deterministic destination path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _copy_tree(source: Path, destination: Path) -> Path:
    """Copy one directory tree into a deterministic destination path."""
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def _manifest_path(directory: Path, label: str) -> Path:
    """Resolve the manifest that anchors one staged or collected bundle."""
    return require_path(directory / "run_manifest.json", f"{label} manifest")


def _manifest_output_path(manifest: dict[str, Any], key: str) -> Path | None:
    """Resolve one recorded output path from a loaded stage manifest."""
    output_path = manifest.get("outputs", {}).get(key)
    if not output_path:
        return None
    return require_path(Path(str(output_path)), f"Manifest output `{key}`")


def _eggnog_annotated_gff3(results_dir: Path) -> Path:
    """Resolve the EggNOG-annotated GFF3 boundary from one results bundle."""
    manifest_path = results_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        for key in ("eggnog_annotated_gff3", "eggnog_decorated_gff"):
            manifest_output = _manifest_output_path(manifest, key)
            if manifest_output is not None:
                return manifest_output
    for candidate_name in ("all_repeats_removed.eggnog.gff3", "eggnog.emapper.decorated.gff"):
        candidate = results_dir / candidate_name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Unable to resolve an EggNOG-annotated GFF3 under {results_dir}")


def _agat_converted_gff3(results_dir: Path) -> Path:
    """Resolve the AGAT-converted GFF3 boundary from one results bundle."""
    manifest_path = results_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        manifest_output = _manifest_output_path(manifest, "agat_converted_gff3")
        if manifest_output is not None:
            return manifest_output
    for candidate in (
        results_dir / _AGAT_CONVERT_OUTPUT_FILENAME,
        results_dir / _AGAT_OUTPUT_DIRNAME / _AGAT_CONVERT_OUTPUT_FILENAME,
    ):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Unable to resolve an AGAT-converted GFF3 under {results_dir}")


def _parse_gff3_attributes(raw_attributes: str) -> list[tuple[str, str | None]]:
    """Parse a simple GFF3 attribute column while preserving attribute order."""
    if raw_attributes in ("", "."):
        return []
    attributes: list[tuple[str, str | None]] = []
    for raw_attribute in raw_attributes.split(";"):
        if raw_attribute == "":
            continue
        if "=" not in raw_attribute:
            attributes.append((raw_attribute, None))
            continue
        key, value = raw_attribute.split("=", 1)
        attributes.append((key, value))
    return attributes


def _format_gff3_attributes(attributes: list[tuple[str, str | None]]) -> str:
    """Format parsed GFF3 attributes back into one column."""
    if not attributes:
        return "."
    formatted = []
    for key, value in attributes:
        if value is None:
            formatted.append(key)
        else:
            formatted.append(f"{key}={value}")
    return ";".join(formatted)


def _attribute_value(attributes: list[tuple[str, str | None]], key: str) -> str | None:
    """Return the first value for one GFF3 attribute key."""
    for attribute_key, value in attributes:
        if attribute_key == key:
            return value
    return None


def _remove_attribute(attributes: list[tuple[str, str | None]], key: str) -> tuple[list[tuple[str, str | None]], int]:
    """Remove all attributes matching one key and return the removal count."""
    kept = [(attribute_key, value) for attribute_key, value in attributes if attribute_key != key]
    return kept, len(attributes) - len(kept)


def _set_attribute(attributes: list[tuple[str, str | None]], key: str, value: str) -> tuple[list[tuple[str, str | None]], bool]:
    """Set one attribute value, preserving position when the key already exists."""
    updated: list[tuple[str, str | None]] = []
    found = False
    changed = False
    for attribute_key, attribute_value in attributes:
        if attribute_key == key:
            if not found:
                updated.append((attribute_key, value))
                changed = attribute_value != value
                found = True
            else:
                changed = True
            continue
        updated.append((attribute_key, attribute_value))
    if found:
        return updated, changed
    updated.append((key, value))
    return updated, True


def _matching_mrna_name(parent_value: str | None, mrna_names: dict[str, str]) -> str | None:
    """Resolve a CDS parent to the first mRNA Name value available."""
    if parent_value is None:
        return None
    for parent_id in parent_value.split(","):
        mrna_name = mrna_names.get(parent_id)
        if mrna_name:
            return mrna_name
    return None


def _cleanup_gff3_attributes(source_gff3: Path, cleaned_gff3: Path) -> dict[str, int]:
    """Apply the deterministic post-AGAT GFF3 attribute cleanup rules."""
    lines = source_gff3.read_text().splitlines(keepends=True)
    mrna_names: dict[str, str] = {}
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        columns = line.rstrip("\n").split("\t")
        if len(columns) != 9 or columns[2] != "mRNA":
            continue
        attributes = _parse_gff3_attributes(columns[8])
        mrna_id = _attribute_value(attributes, "ID")
        mrna_name = _attribute_value(attributes, "Name")
        if mrna_id and mrna_name:
            mrna_names[mrna_id] = mrna_name

    summary = {
        "mrna_names_indexed": len(mrna_names),
        "cds_products_propagated": 0,
        "gene_notes_removed": 0,
        "cds_products_replaced_with_putative": 0,
    }
    cleaned_lines: list[str] = []
    for line in lines:
        line_ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        raw_line = line[: -len(line_ending)] if line_ending else line
        if not raw_line.strip() or raw_line.startswith("#"):
            cleaned_lines.append(line)
            continue

        columns = raw_line.split("\t")
        if len(columns) != 9:
            cleaned_lines.append(line)
            continue

        attributes = _parse_gff3_attributes(columns[8])
        feature_type = columns[2]
        if feature_type == "gene":
            attributes, removed = _remove_attribute(attributes, "Note")
            summary["gene_notes_removed"] += removed
        elif feature_type == "CDS":
            mrna_name = _matching_mrna_name(_attribute_value(attributes, "Parent"), mrna_names)
            if mrna_name is not None:
                attributes, _ = _set_attribute(attributes, "product", mrna_name)
                summary["cds_products_propagated"] += 1
            product = _attribute_value(attributes, "product")
            if product is not None and product.startswith("-"):
                attributes, changed = _set_attribute(attributes, "product", "putative")
                if changed:
                    summary["cds_products_replaced_with_putative"] += 1

        columns[8] = _format_gff3_attributes(attributes)
        cleaned_lines.append("\t".join(columns) + line_ending)

    cleaned_gff3.parent.mkdir(parents=True, exist_ok=True)
    cleaned_gff3.write_text("".join(cleaned_lines))
    return summary


@agat_cleanup_env.task
def agat_cleanup_gff3(
    agat_conversion_results: Dir,
) -> Dir:
    """Clean the AGAT-converted GFF3 with the deterministic attribute edits."""
    conversion_dir = require_path(
        Path(agat_conversion_results.download_sync()),
        "AGAT conversion results directory",
    )
    converted_gff3 = _agat_converted_gff3(conversion_dir)

    work_dir = project_mkdtemp("agat_cleanup_") / "agat"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir = work_dir / _AGAT_OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned_output = output_dir / _AGAT_CLEANED_OUTPUT_FILENAME
    summary = _cleanup_gff3_attributes(converted_gff3, cleaned_output)

    cleaned_output_path = require_path(cleaned_output, "AGAT cleaned GFF3")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{AGAT_CLEANUP_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_boundary_dir = out_dir / "source_boundary"
    source_boundary_dir.mkdir(parents=True, exist_ok=True)
    copied_converted = _copy_file(converted_gff3, source_boundary_dir / _AGAT_CONVERT_OUTPUT_FILENAME)

    source_manifests_dir = out_dir / "source_manifests"
    source_manifests_dir.mkdir(parents=True, exist_ok=True)
    copied_conversion_manifest = _copy_file(
        _manifest_path(conversion_dir, "AGAT conversion results"),
        source_manifests_dir / "agat_conversion.run_manifest.json",
    )

    agat_output_dir = _copy_tree(output_dir, out_dir / _AGAT_OUTPUT_DIRNAME)
    copied_cleaned = _copy_file(cleaned_output_path, out_dir / _AGAT_CLEANED_OUTPUT_FILENAME)
    summary_path = out_dir / _AGAT_CLEANUP_SUMMARY_FILENAME
    _write_json(summary_path, summary)

    manifest = {
        "workflow": AGAT_CLEANUP_WORKFLOW_NAME,
        "assumptions": [
            "This cleanup slice consumes the AGAT conversion result bundle and preserves the converted GFF3 as its source boundary.",
            "The cleanup rules are deterministic translations of the repository's R and awk commands rather than a new AGAT binary invocation.",
            "CDS product values are populated from parent mRNA Name attributes when available, gene Note attributes are removed, and CDS products beginning with '-' are replaced with 'putative'.",
            "table2asn remains deferred after this cleanup slice.",
        ],
        "source_bundle": {
            "agat_conversion_results": str(conversion_dir),
        },
        "copied_source_manifests": {
            "agat_conversion": str(copied_conversion_manifest),
        },
        "inputs": {
            "agat_conversion_results": str(conversion_dir),
        },
        "outputs": {
            "agat_converted_gff3": str(copied_converted),
            "agat_output_dir": str(agat_output_dir),
            "agat_cleaned_gff3": str(copied_cleaned),
            "agat_cleanup_summary_json": str(summary_path),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@agat_conversion_env.task
def agat_convert_sp_gxf2gxf(
    eggnog_results: Dir,
    agat_sif: str = "",
) -> Dir:
    """Run AGAT conversion on the EggNOG-annotated GFF3 boundary."""
    eggnog_dir = require_path(Path(eggnog_results.download_sync()), "EggNOG results directory")
    eggnog_gff3 = _eggnog_annotated_gff3(eggnog_dir)

    work_dir = project_mkdtemp("agat_convert_") / "agat"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir = work_dir / _AGAT_OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)
    converted_output = output_dir / _AGAT_CONVERT_OUTPUT_FILENAME

    source_boundary_dir = work_dir / "source_boundary"
    source_boundary_dir.mkdir(parents=True, exist_ok=True)
    staged_gff3 = _copy_file(eggnog_gff3, source_boundary_dir / "all_repeats_removed.eggnog.gff3")

    command = [
        "agat_convert_sp_gxf2gxf.pl",
        "-g",
        str(staged_gff3),
        "-o",
        str(converted_output),
    ]
    run_tool(command, agat_sif, [eggnog_dir, work_dir], cwd=work_dir)

    converted_output_path = require_path(converted_output, "AGAT converted GFF3")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{AGAT_CONVERSION_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_boundary_out_dir = out_dir / "source_boundary"
    source_boundary_out_dir.mkdir(parents=True, exist_ok=True)
    copied_gff3 = _copy_file(eggnog_gff3, source_boundary_out_dir / "all_repeats_removed.eggnog.gff3")

    source_manifests_dir = out_dir / "source_manifests"
    source_manifests_dir.mkdir(parents=True, exist_ok=True)
    copied_eggnog_manifest = _copy_file(
        _manifest_path(eggnog_dir, "EggNOG results"),
        source_manifests_dir / "eggnog.run_manifest.json",
    )

    agat_output_dir = _copy_tree(output_dir, out_dir / _AGAT_OUTPUT_DIRNAME)
    copied_converted = _copy_file(converted_output_path, out_dir / _AGAT_CONVERT_OUTPUT_FILENAME)

    manifest = {
        "workflow": AGAT_CONVERSION_WORKFLOW_NAME,
        "assumptions": [
            "This AGAT slice starts from the EggNOG-annotated GFF3 boundary and runs the gxf-to-gxf conversion command explicitly.",
            "The notes show `agat_convert_sp_gxf2gxf.pl` as a GTF-to-GFF3 example; applying the same command family to the EggNOG-annotated GFF3 bundle is an inferred normalization slice that remains reviewable and narrow.",
            "Cleanup remains a separate follow-on slice and table2asn remains deferred after conversion.",
        ],
        "source_bundle": {
            "eggnog_results": str(eggnog_dir),
        },
        "copied_source_manifests": {
            "eggnog": str(copied_eggnog_manifest),
        },
        "inputs": {
            "eggnog_results": str(eggnog_dir),
            "agat_sif": agat_sif,
        },
        "outputs": {
            "eggnog_annotated_gff3": str(copied_gff3),
            "agat_output_dir": str(agat_output_dir),
            "agat_converted_gff3": str(copied_converted),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@agat_env.task
def agat_statistics(
    eggnog_results: Dir,
    annotation_fasta_path: str = "",
    agat_sif: str = "",
) -> Dir:
    """Run AGAT statistics on the EggNOG-annotated GFF3 boundary."""
    eggnog_dir = require_path(Path(eggnog_results.download_sync()), "EggNOG results directory")
    eggnog_gff3 = _eggnog_annotated_gff3(eggnog_dir)
    annotation_fasta = require_path(Path(annotation_fasta_path), "Annotation FASTA") if annotation_fasta_path else None

    work_dir = project_mkdtemp("agat_run_") / "agat"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir = work_dir / _AGAT_OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)
    stats_output = output_dir / _AGAT_OUTPUT_FILENAME

    bind_paths = [eggnog_dir, work_dir]
    if annotation_fasta is not None:
        bind_paths.append(annotation_fasta.parent)

    command = ["agat_sp_statistics.pl", "--gff", str(eggnog_gff3)]
    if annotation_fasta is not None:
        command.extend(["-f", str(annotation_fasta)])
    command.extend(["--output", str(stats_output)])

    run_tool(command, agat_sif, bind_paths, cwd=work_dir)

    stats_output_path = require_path(stats_output, "AGAT statistics output")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{AGAT_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_boundary_dir = out_dir / "source_boundary"
    source_boundary_dir.mkdir(parents=True, exist_ok=True)
    copied_gff3 = _copy_file(eggnog_gff3, source_boundary_dir / "all_repeats_removed.eggnog.gff3")
    copied_annotation_fasta = (
        _copy_file(annotation_fasta, source_boundary_dir / annotation_fasta.name) if annotation_fasta is not None else None
    )

    source_manifests_dir = out_dir / "source_manifests"
    source_manifests_dir.mkdir(parents=True, exist_ok=True)
    copied_eggnog_manifest = _copy_file(
        _manifest_path(eggnog_dir, "EggNOG results"),
        source_manifests_dir / "eggnog.run_manifest.json",
    )

    agat_output_dir = _copy_tree(output_dir, out_dir / _AGAT_OUTPUT_DIRNAME)
    copied_statistics = _copy_file(stats_output_path, out_dir / _AGAT_OUTPUT_FILENAME)

    manifest = {
        "workflow": AGAT_WORKFLOW_NAME,
        "assumptions": [
            "This AGAT slice starts from the EggNOG-annotated GFF3 boundary and stays focused on statistics reporting.",
            "The command shape is inferred from the notes and official AGAT documentation; this milestone keeps the core statistics invocation explicit and leaves optional distribution-plot behavior out of scope.",
            "A companion annotation FASTA is optional in this slice because the notes show it for one statistics example, but the bundle should still be usable without inventing extra inputs.",
        ],
        "source_bundle": {
            "eggnog_results": str(eggnog_dir),
        },
        "copied_source_manifests": {
            "eggnog": str(copied_eggnog_manifest),
        },
        "inputs": {
            "eggnog_results": str(eggnog_dir),
            "annotation_fasta_path": str(annotation_fasta) if annotation_fasta is not None else "",
            "agat_sif": agat_sif,
        },
        "outputs": {
            "eggnog_annotated_gff3": str(copied_gff3),
            "annotation_fasta_path": str(copied_annotation_fasta) if copied_annotation_fasta is not None else "",
            "agat_output_dir": str(agat_output_dir),
            "agat_statistics_tsv": str(copied_statistics),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


__all__ = ["agat_cleanup_gff3", "agat_convert_sp_gxf2gxf", "agat_statistics"]
