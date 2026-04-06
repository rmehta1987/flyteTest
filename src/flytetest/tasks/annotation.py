"""BRAKER3 task implementations for the current FLyteTest annotation milestone.

This module stages local ab initio inputs, runs the tutorial-backed BRAKER3
boundary, preserves the note-backed `braker.gff3` handoff for EVM, and
collects a stable downstream bundle with explicit repo-policy metadata.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir, File

from flytetest.config import (
    ANNOTATION_RESULTS_PREFIX,
    ANNOTATION_WORKFLOW_NAME,
    RESULTS_ROOT,
    annotation_env,
    require_path,
    run_tool,
)
from flytetest.types import (
    Braker3InputBundleAsset,
    Braker3NormalizedGff3Asset,
    Braker3RawRunResultAsset,
    Braker3ResultBundle,
    ReferenceGenome,
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


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON manifest into a dictionary."""
    return json.loads(path.read_text())


def _stage_manifest_path(staged_dir: Path) -> Path:
    """Resolve the staged-input manifest written by `stage_braker3_inputs`."""
    return require_path(staged_dir / "run_manifest.json", "BRAKER3 staged-input manifest")


def _staged_genome_fasta(staged_dir: Path) -> Path:
    """Resolve the single staged genome FASTA under a BRAKER3 input bundle."""
    genome_dir = require_path(staged_dir / "genome", "Staged BRAKER3 genome directory")
    candidates = sorted(path for path in genome_dir.iterdir() if path.is_file())
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single staged genome FASTA under {genome_dir}")


def _single_staged_file(staged_dir: Path, subdir_name: str, description: str) -> Path | None:
    """Resolve one optional staged evidence file from a named subdirectory."""
    candidate_dir = staged_dir / subdir_name
    if not candidate_dir.exists():
        return None
    resolved_dir = require_path(candidate_dir, description)
    candidates = sorted(path for path in resolved_dir.iterdir() if path.is_file())
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single file under {resolved_dir}")


def _braker_gff3(run_dir: Path) -> Path:
    """Resolve the single `braker.gff3` produced anywhere under a BRAKER3 run tree."""
    candidates = sorted(run_dir.rglob("braker.gff3"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single braker.gff3 under {run_dir}")


def _raw_run_manifest_path(run_dir: Path) -> Path:
    """Resolve the manifest written by the raw BRAKER3 execution task."""
    return require_path(run_dir / "run_manifest.json", "BRAKER3 raw-run manifest")


def _normalized_braker_gff3(normalized_dir: Path) -> Path:
    """Resolve the normalized BRAKER3 GFF3 prepared for later EVM use."""
    candidates = sorted(normalized_dir.glob("*.gff3"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single normalized BRAKER3 GFF3 under {normalized_dir}")


def _normalized_manifest_path(normalized_dir: Path) -> Path:
    """Resolve the manifest written by BRAKER3 normalization."""
    return require_path(normalized_dir / "run_manifest.json", "Normalized BRAKER3 manifest")


def _gff3_source_names(gff3_path: Path) -> tuple[str, ...]:
    """Resolve unique GFF3 source-column values in first-appearance order."""
    source_names: list[str] = []
    seen: set[str] = set()
    for raw_line in gff3_path.read_text().splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        fields = raw_line.split("\t")
        if len(fields) != 9:
            continue
        source_name = fields[1].strip()
        if source_name and source_name not in seen:
            source_names.append(source_name)
            seen.add(source_name)
    return tuple(source_names)


@annotation_env.task
def stage_braker3_inputs(
    genome: File,
    rnaseq_bam_path: str = "",
    protein_fasta_path: str = "",
) -> Dir:
    """Stage the local genome and evidence inputs needed for a BRAKER3 run."""
    genome_path = require_path(Path(genome.download_sync()), "Reference genome FASTA")
    rnaseq_bam = require_path(Path(rnaseq_bam_path), "RNA-seq BAM evidence") if rnaseq_bam_path else None
    protein_fasta = (
        require_path(Path(protein_fasta_path), "Protein FASTA evidence") if protein_fasta_path else None
    )

    if rnaseq_bam is None and protein_fasta is None:
        raise ValueError(
            "stage_braker3_inputs requires at least one local BRAKER3 evidence input: rnaseq_bam_path or protein_fasta_path."
        )

    out_dir = Path(tempfile.mkdtemp(prefix="braker3_stage_")) / "staged_inputs"
    genome_dir = out_dir / "genome"
    bam_dir = out_dir / "rnaseq_bam"
    protein_dir = out_dir / "protein_fasta"
    genome_dir.mkdir(parents=True, exist_ok=True)
    if rnaseq_bam is not None:
        bam_dir.mkdir(parents=True, exist_ok=True)
    if protein_fasta is not None:
        protein_dir.mkdir(parents=True, exist_ok=True)

    staged_genome_path = genome_dir / genome_path.name
    shutil.copy2(genome_path, staged_genome_path)

    staged_bam_path = None
    if rnaseq_bam is not None:
        staged_bam_path = bam_dir / rnaseq_bam.name
        shutil.copy2(rnaseq_bam, staged_bam_path)

    staged_protein_path = None
    if protein_fasta is not None:
        staged_protein_path = protein_dir / protein_fasta.name
        shutil.copy2(protein_fasta, staged_protein_path)

    manifest = {
        "stage": "stage_braker3_inputs",
        "notes_backed_behavior": [
            "The source-of-truth notes place BRAKER3 upstream of EVM but do not define a fetch-or-stage contract for local input acquisition.",
        ],
        "tutorial_backed_behavior": [
            "The Galaxy BRAKER3 tutorial is the runtime model for this repo milestone: masked genome plus RNA-seq BAM and/or protein FASTA evidence staged locally.",
        ],
        "repo_policy": [
            "This milestone accepts only local user-provided BRAKER3 inputs and does not fetch remote evidence datasets automatically.",
            "The staged input contract requires at least one local evidence input: RNA-seq BAM and/or protein FASTA.",
            "No automatic RNA-seq BAM preparation, protein preprocessing, or cluster-specific BRAKER3 environment bootstrapping is performed in this milestone.",
        ],
        "outputs": {
            "staged_genome_fasta": str(staged_genome_path),
            "staged_rnaseq_bam": str(staged_bam_path) if staged_bam_path else None,
            "staged_protein_fasta": str(staged_protein_path) if staged_protein_path else None,
        },
        "source_inputs": {
            "genome": str(Path(str(genome.path))),
            "rnaseq_bam_path": rnaseq_bam_path or None,
            "protein_fasta_path": protein_fasta_path or None,
        },
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir.from_local_sync(str(out_dir))


@annotation_env.task
def braker3_predict(
    staged_inputs: Dir,
    braker_species: str = "flytetest_braker3",
    braker3_sif: str = "",
) -> Dir:
    """Run the tutorial-backed BRAKER3 boundary against staged local inputs."""
    staged_dir = require_path(Path(staged_inputs.download_sync()), "Staged BRAKER3 input directory")
    genome_path = _staged_genome_fasta(staged_dir)
    rnaseq_bam = _single_staged_file(staged_dir, "rnaseq_bam", "Staged RNA-seq BAM directory")
    protein_fasta = _single_staged_file(staged_dir, "protein_fasta", "Staged protein FASTA directory")

    out_dir = Path(tempfile.mkdtemp(prefix="braker3_run_")) / "braker3"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "braker.pl",
        "--genome",
        str(genome_path),
        "--workingdir",
        str(out_dir),
        "--species",
        braker_species,
        "--gff3",
    ]
    if rnaseq_bam is not None:
        cmd.extend(["--bam", str(rnaseq_bam)])
    if protein_fasta is not None:
        cmd.extend(["--prot_seq", str(protein_fasta)])

    bind_paths = [staged_dir, out_dir]
    run_tool(cmd, braker3_sif, bind_paths)
    braker_gff3_path = _braker_gff3(out_dir)

    manifest = {
        "stage": "braker3_predict",
        "notes_backed_behavior": [
            "The notes require `braker.gff3` as the downstream ab initio input that later feeds EVM.",
        ],
        "tutorial_backed_behavior": [
            "The Galaxy BRAKER3 tutorial provides the operational model for this milestone: a masked genome, RNA-seq BAM and/or protein FASTA evidence, GFF3 output, and tutorial-style BRAKER3 parameterization.",
            "This milestone therefore follows the tutorial-backed braker.pl boundary with --gff3 plus optional --bam and --prot_seq inputs when those local staged evidence files are provided.",
        ],
        "repo_policy": [
            "This task preserves the raw BRAKER3 output directory as the authoritative upstream record for later stages.",
        ],
        "inputs": {
            "staged_inputs": str(staged_dir),
            "genome": str(genome_path),
            "rnaseq_bam": str(rnaseq_bam) if rnaseq_bam else None,
            "protein_fasta": str(protein_fasta) if protein_fasta else None,
            "species": braker_species,
        },
        "outputs": {
            "raw_run_dir": str(out_dir),
            "braker_gff3": str(braker_gff3_path),
        },
        "command_inference": cmd,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir.from_local_sync(str(out_dir))


@annotation_env.task
def normalize_braker3_for_evm(
    braker_run: Dir,
) -> Dir:
    """Normalize resolved `braker.gff3` into a stable source-preserving directory."""
    run_dir = require_path(Path(braker_run.download_sync()), "BRAKER3 run directory")
    source_gff3 = _braker_gff3(run_dir)

    out_dir = Path(tempfile.mkdtemp(prefix="braker3_normalized_")) / "normalized"
    out_dir.mkdir(parents=True, exist_ok=True)
    normalized_gff3_path = out_dir / "braker3.evm.gff3"
    source_fields = _gff3_source_names(source_gff3)

    wrote_header = False
    with source_gff3.open() as source_handle, normalized_gff3_path.open("w") as out_handle:
        for raw_line in source_handle:
            # Preserve a single canonical header even if the upstream file emits
            # repeated version lines before later GFF records.
            if raw_line.startswith("##gff-version"):
                if not wrote_header:
                    out_handle.write("##gff-version 3\n")
                    wrote_header = True
                continue
            if not wrote_header:
                out_handle.write("##gff-version 3\n")
                wrote_header = True
            if raw_line.startswith("#"):
                out_handle.write(raw_line)
                continue
            stripped = raw_line.rstrip("\n")
            fields = stripped.split("\t")
            if len(fields) != 9:
                continue
            out_handle.write("\t".join(fields) + "\n")

    normalized_source_fields = _gff3_source_names(normalized_gff3_path)

    manifest = {
        "stage": "normalize_braker3_for_evm",
        "notes_backed_behavior": [
            "The notes clearly identify `braker.gff3` as the downstream EVM boundary.",
            "The notes require each GFF3 source column to match the eventual `evm.weights` file, but they do not specify any BRAKER-specific source rewriting step.",
        ],
        "tutorial_backed_behavior": [
            "This normalized bundle is derived from the repo's tutorial-backed BRAKER3 runtime output.",
        ],
        "repo_policy": [
            "Normalization is intentionally narrow: preserve upstream source-column values, emit one canonical GFF3 header, and write a stable `braker3.evm.gff3` filename for downstream staging.",
            "Broader BRAKER3-to-EVM transformations remain intentionally deferred to keep the boundary honest and reviewable.",
        ],
        "inputs": {
            "braker_run_dir": str(run_dir),
            "source_braker_gff3": str(source_gff3),
            "source_fields": list(source_fields),
        },
        "outputs": {
            "normalized_gff3": str(normalized_gff3_path),
            "normalized_source_fields": list(normalized_source_fields),
        },
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir.from_local_sync(str(out_dir))


@annotation_env.task
def collect_braker3_results(
    genome: File,
    staged_inputs: Dir,
    braker_run: Dir,
    normalized_braker: Dir,
    braker_species: str = "flytetest_braker3",
) -> Dir:
    """Collect BRAKER3 staging, raw outputs, and source-preserving normalization."""
    genome_input = Path(str(genome.path))
    staged_dir = require_path(Path(staged_inputs.download_sync()), "Staged BRAKER3 input directory")
    braker_run_dir = require_path(Path(braker_run.download_sync()), "BRAKER3 run directory")
    normalized_dir = require_path(Path(normalized_braker.download_sync()), "Normalized BRAKER3 directory")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{ANNOTATION_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_staged_dir = out_dir / "staged_inputs"
    copied_raw_dir = out_dir / "braker3_raw"
    copied_normalized_dir = out_dir / "braker3_normalized"
    shutil.copytree(staged_dir, copied_staged_dir, dirs_exist_ok=True)
    shutil.copytree(braker_run_dir, copied_raw_dir, dirs_exist_ok=True)
    shutil.copytree(normalized_dir, copied_normalized_dir, dirs_exist_ok=True)

    staged_manifest = _read_json(_stage_manifest_path(copied_staged_dir))
    raw_run_manifest = _read_json(_raw_run_manifest_path(copied_raw_dir))
    normalized_manifest = _read_json(_normalized_manifest_path(copied_normalized_dir))

    reference_asset = ReferenceGenome(fasta_path=genome_input)
    input_bundle_asset = Braker3InputBundleAsset(
        staged_dir=copied_staged_dir,
        genome_fasta_path=_staged_genome_fasta(copied_staged_dir),
        rnaseq_bam_path=_single_staged_file(copied_staged_dir, "rnaseq_bam", "Copied staged RNA-seq BAM directory"),
        protein_fasta_path=_single_staged_file(
            copied_staged_dir,
            "protein_fasta",
            "Copied staged protein FASTA directory",
        ),
        notes=(
            "This staged bundle preserves the local inputs used for the tutorial-backed BRAKER3 boundary in this milestone.",
        ),
    )
    raw_run_asset = Braker3RawRunResultAsset(
        output_dir=copied_raw_dir,
        braker_gff3_path=_braker_gff3(copied_raw_dir),
        species_name=braker_species,
        input_bundle=input_bundle_asset,
        notes=(
            "The BRAKER3 command boundary is tutorial-backed: the Galaxy tutorial provides the masked genome, RNA-seq BAM and/or protein FASTA evidence model, and GFF3 output shape that the notes leave implicit.",
        ),
    )
    normalized_asset = Braker3NormalizedGff3Asset(
        output_dir=copied_normalized_dir,
        normalized_gff3_path=_normalized_braker_gff3(copied_normalized_dir),
        source_run=raw_run_asset,
        notes=(
            "Normalization remains intentionally narrow and stops at a stable later-EVM-ready GFF3 boundary.",
        ),
    )
    result_bundle = Braker3ResultBundle(
        result_dir=out_dir,
        staged_inputs_dir=copied_staged_dir,
        raw_run_dir=copied_raw_dir,
        normalized_dir=copied_normalized_dir,
        braker_gff3_path=raw_run_asset.braker_gff3_path,
        normalized_gff3_path=normalized_asset.normalized_gff3_path,
        reference_genome=reference_asset,
        input_bundle=input_bundle_asset,
        raw_run=raw_run_asset,
        normalized_prediction=normalized_asset,
        notes=(
            "This milestone stops at BRAKER3 raw-output capture plus deterministic normalization for later EVM use.",
        ),
    )

    manifest = {
        "workflow": ANNOTATION_WORKFLOW_NAME,
        "notes_backed_behavior": [
            "The source-of-truth notes require `braker.gff3` as the ab initio EVM input boundary.",
        ],
        "tutorial_backed_behavior": [
            "The Galaxy BRAKER3 tutorial is treated as the concrete invocation model for this milestone, while the notes still provide the downstream `braker.gff3` contract for EVM.",
        ],
        "repo_policy": [
            "This milestone accepts only local user-provided evidence inputs staged explicitly into the results bundle.",
            "Normalization preserves upstream BRAKER source-column values while stabilizing the output filename and header for later EVM staging.",
            "This milestone does not yet implement EVM, PASA update rounds, repeat filtering, BUSCO, EggNOG, AGAT, or submission preparation.",
        ],
        "outputs": {
            "staged_inputs_dir": str(copied_staged_dir),
            "braker3_raw_dir": str(copied_raw_dir),
            "braker_gff3": str(raw_run_asset.braker_gff3_path),
            "braker3_normalized_dir": str(copied_normalized_dir),
            "normalized_braker_gff3": str(normalized_asset.normalized_gff3_path),
            "normalized_source_fields": normalized_manifest.get("outputs", {}).get("normalized_source_fields", []),
        },
        "inputs": {
            "genome": str(genome_input),
            "rnaseq_bam_path": staged_manifest.get("source_inputs", {}).get("rnaseq_bam_path"),
            "protein_fasta_path": staged_manifest.get("source_inputs", {}).get("protein_fasta_path"),
            "species": braker_species,
        },
        "assets": _as_json_compatible(
            {
                "reference_genome": asdict(reference_asset),
                "braker3_input_bundle": asdict(input_bundle_asset),
                "braker3_raw_run": asdict(raw_run_asset),
                "braker3_normalized_gff3": asdict(normalized_asset),
                "braker3_result_bundle": asdict(result_bundle),
            }
        ),
        "raw_run_manifest": raw_run_manifest,
        "normalized_manifest": normalized_manifest,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir.from_local_sync(str(out_dir))
