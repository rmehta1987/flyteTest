"""BUSCO-based annotation-QC tasks for the post-repeat-filtering milestone.

This module runs one BUSCO protein assessment per lineage downstream of the
repeat-filtered annotation boundary and collects deterministic QC bundles
without broadening into EggNOG, AGAT, or submission-prep work.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir, File

from flytetest.config import (
    FUNCTIONAL_QC_RESULTS_PREFIX,
    FUNCTIONAL_QC_WORKFLOW_NAME,
    RESULTS_ROOT,
    functional_qc_env,
    require_path,
    run_tool,
)


DEFAULT_BUSCO_LINEAGES_TEXT = (
    "eukaryota_odb10,metazoa_odb10,insecta_odb10,arthropoda_odb10,diptera_odb10"
)


def _as_json_compatible(value: Any) -> Any:
    """Recursively convert manifest values into JSON-serializable primitives."""
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
    """Resolve the manifest expected under one staged or collected directory."""
    return require_path(directory / "run_manifest.json", f"{label} manifest")


def _manifest_output_path(manifest: dict[str, Any], key: str) -> Path | None:
    """Resolve one manifest-recorded output path when present."""
    output_path = manifest.get("outputs", {}).get(key)
    if not output_path:
        return None
    return require_path(Path(str(output_path)), f"Manifest output `{key}`")


def _lineages_from_text(busco_lineages_text: str) -> list[str]:
    """Split a comma-separated lineage list into deterministic BUSCO inputs."""
    lineages = [item.strip() for item in busco_lineages_text.split(",") if item.strip()]
    if not lineages:
        raise ValueError("At least one BUSCO lineage must be supplied.")
    return lineages


def _lineage_slug(lineage_dataset: str) -> str:
    """Return a filesystem-safe slug for one BUSCO lineage dataset input."""
    base_name = Path(lineage_dataset).name or lineage_dataset
    slug = "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in base_name)
    return slug or "busco_lineage"


def _busco_output_name(lineage_dataset: str) -> str:
    """Return the deterministic BUSCO output-name prefix for one lineage."""
    return f"busco_output_{_lineage_slug(lineage_dataset)}"


def _busco_short_summary(run_dir: Path) -> Path | None:
    """Resolve the short BUSCO summary text file when the run emitted one."""
    candidates = sorted(run_dir.glob("short_summary*.txt"))
    if not candidates:
        return None
    return candidates[0]


def _busco_full_table(run_dir: Path) -> Path | None:
    """Resolve the BUSCO full table when the run emitted one."""
    candidate = run_dir / "full_table.tsv"
    if candidate.exists():
        return candidate
    return None


def _busco_summary_notation(summary_path: Path | None) -> str | None:
    """Extract the BUSCO `C:/S:/D:/F:/M:` notation line when present."""
    if summary_path is None:
        return None
    for raw_line in summary_path.read_text().splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("C:") and "S:" in stripped:
            return stripped
    return None


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


def _write_busco_summary(rows: list[dict[str, str]], destination: Path) -> Path:
    """Write a deterministic TSV summarizing copied BUSCO lineage runs."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "lineage_dataset",
                "run_dir",
                "short_summary",
                "full_table",
                "summary_notation",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return destination


@functional_qc_env.task
def busco_assess_proteins(
    proteins_fasta: File,
    lineage_dataset: str,
    busco_sif: str = "",
    busco_cpu: int = 8,
    busco_mode: str = "prot",
) -> Dir:
    """Run BUSCO on one protein FASTA against one selected lineage dataset."""
    proteins_path = require_path(Path(proteins_fasta.download_sync()), "Proteins FASTA")
    work_root = Path(tempfile.mkdtemp(prefix="busco_run_")) / "busco"
    work_root.mkdir(parents=True, exist_ok=True)

    output_name = _busco_output_name(lineage_dataset)
    run_tool(
        [
            "busco",
            "-i",
            str(proteins_path),
            "-o",
            output_name,
            "-l",
            lineage_dataset,
            "-m",
            busco_mode,
            "-c",
            str(busco_cpu),
        ],
        busco_sif,
        [proteins_path.parent, work_root],
        cwd=work_root,
    )

    run_dir = require_path(work_root / output_name, f"BUSCO run directory for `{lineage_dataset}`")
    short_summary = _busco_short_summary(run_dir)
    full_table = _busco_full_table(run_dir)
    manifest = {
        "stage": "busco_assess_proteins",
        "assumptions": [
            "The notes run BUSCO on the final repeat-filtered protein FASTA with `-m prot`.",
            "Lineage selection remains explicit because the notes recommend running several lineage databases rather than inferring one automatically.",
            "This task represents one BUSCO lineage invocation; multi-lineage QC is handled by a downstream workflow collector.",
        ],
        "inputs": {
            "proteins_fasta": str(proteins_path),
            "lineage_dataset": lineage_dataset,
            "busco_sif": busco_sif,
            "busco_cpu": busco_cpu,
            "busco_mode": busco_mode,
        },
        "outputs": {
            "run_dir": str(run_dir),
            "short_summary": str(short_summary) if short_summary else None,
            "full_table": str(full_table) if full_table else None,
            "summary_notation": _busco_summary_notation(short_summary),
        },
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    return Dir.from_local_sync(str(run_dir))


@functional_qc_env.task
def collect_busco_results(
    repeat_filter_results: Dir,
    busco_runs: list[Dir],
    busco_lineages_text: str = DEFAULT_BUSCO_LINEAGES_TEXT,
) -> Dir:
    """Collect BUSCO lineage runs into a manifest-bearing QC bundle."""
    if not busco_runs:
        raise ValueError("collect_busco_results requires at least one BUSCO run directory.")

    repeat_filter_dir = require_path(
        Path(repeat_filter_results.download_sync()),
        "Repeat-filtering results directory",
    )
    busco_run_dirs = [
        require_path(Path(busco_run.download_sync()), "BUSCO run directory")
        for busco_run in busco_runs
    ]

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{FUNCTIONAL_QC_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_boundary_dir = out_dir / "source_boundary"
    source_boundary_dir.mkdir(parents=True, exist_ok=True)
    copied_final_proteins = _copy_file(
        _repeat_filter_final_proteins(repeat_filter_dir),
        source_boundary_dir / "all_repeats_removed.proteins.fa",
    )

    source_manifests_dir = out_dir / "source_manifests"
    source_manifests_dir.mkdir(parents=True, exist_ok=True)
    copied_repeat_filter_manifest = _copy_file(
        _manifest_path(repeat_filter_dir, "Repeat-filter bundle"),
        source_manifests_dir / "repeat_filter.run_manifest.json",
    )

    copied_busco_runs_dir = out_dir / "busco_runs"
    copied_busco_runs_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, str]] = []
    copied_stage_dirs: dict[str, str] = {}
    stage_manifests: dict[str, dict[str, Any]] = {}
    for busco_run_dir in busco_run_dirs:
        busco_manifest = _read_json(_manifest_path(busco_run_dir, "BUSCO run"))
        lineage_dataset = str(busco_manifest.get("inputs", {}).get("lineage_dataset", busco_run_dir.name))
        lineage_slug = _lineage_slug(lineage_dataset)
        copied_run_dir = _copy_tree(busco_run_dir, copied_busco_runs_dir / lineage_slug)
        copied_short_summary = _busco_short_summary(copied_run_dir)
        copied_full_table = _busco_full_table(copied_run_dir)

        copied_stage_dirs[lineage_slug] = str(copied_run_dir)
        stage_manifests[lineage_slug] = _read_json(_manifest_path(copied_run_dir, "Copied BUSCO run"))
        summary_rows.append(
            {
                "lineage_dataset": lineage_dataset,
                "run_dir": str(copied_run_dir),
                "short_summary": str(copied_short_summary) if copied_short_summary else "",
                "full_table": str(copied_full_table) if copied_full_table else "",
                "summary_notation": _busco_summary_notation(copied_short_summary) or "",
            }
        )

    summary_tsv = _write_busco_summary(summary_rows, out_dir / "busco_summary.tsv")
    manifest = {
        "workflow": FUNCTIONAL_QC_WORKFLOW_NAME,
        "assumptions": [
            "This milestone starts from the final repeat-filtered protein FASTA boundary and does not reopen repeat filtering itself.",
            "The notes recommend running BUSCO across several lineages; this workflow therefore fans out one BUSCO task per selected lineage instead of collapsing them into one opaque run.",
            "This milestone stops after BUSCO-based QC and does not proceed into EggNOG, AGAT, or submission-prep stages.",
        ],
        "inputs": {
            "repeat_filter_results": str(repeat_filter_dir),
            "busco_lineages_text": busco_lineages_text,
        },
        "source_bundle": {
            "repeat_filter_results": str(repeat_filter_dir),
        },
        "copied_source_manifests": {
            "repeat_filter": str(copied_repeat_filter_manifest),
        },
        "copied_stage_dirs": copied_stage_dirs,
        "outputs": {
            "final_proteins_fasta": str(copied_final_proteins),
            "busco_summary_tsv": str(summary_tsv),
        },
        "stage_manifests": stage_manifests,
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir.from_local_sync(str(out_dir))


__all__ = [
    "DEFAULT_BUSCO_LINEAGES_TEXT",
    "_lineages_from_text",
    "_repeat_filter_final_proteins",
    "busco_assess_proteins",
    "collect_busco_results",
]
