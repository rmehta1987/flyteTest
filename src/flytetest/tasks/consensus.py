"""Consensus-stage preparation and EVM execution tasks for FLyteTest.

    Stage ordering and the pre-EVM file contract follow `docs/braker3_evm_notes.md`.
    Tool-level command and input/output expectations follow the tool references
    under `docs/tool_refs/` (notably `evidencemodeler.md`).

    This module preserves the current pre-EVM contract assembly boundary, then runs
    deterministic EVidenceModeler partitioning, command generation, execution, and
    recombination strictly downstream of that existing bundle.
"""

from __future__ import annotations

import json
import shlex
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir

from flytetest.config import (
    CONSENSUS_EVM_RESULTS_PREFIX,
    CONSENSUS_EVM_WORKFLOW_NAME,
    CONSENSUS_RESULTS_PREFIX,
    CONSENSUS_WORKFLOW_NAME,
    RESULTS_ROOT,
    consensus_evm_env,
    consensus_prep_env,
    project_mkdtemp,
    require_path,
    run_tool,
)
from flytetest.tasks.annotation import _staged_genome_fasta
from flytetest.tasks.pasa import _pasa_assemblies_gff3, _sqlite_db_path
from flytetest.tasks.transdecoder import _transdecoder_genome_gff3
from flytetest.types import (
    EvmCommandSetAsset,
    EvmConsensusResultBundle,
    EvmExecutionInputBundleAsset,
    EvmInputPreparationBundle,
    EvmPartitionBundleAsset,
    EvmPredictionInputBundleAsset,
    EvmProteinInputBundleAsset,
    EvmTranscriptInputBundleAsset,
)


def _as_json_compatible(value: Any) -> Any:
    """Convert manifest values into JSON-serializable primitives for persistent staging.

    Args:
        value: The value or values processed by the helper.

    Returns:
        The returned `Any` value used by the caller.
"""
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
    """Read a JSON manifest file into a Python dictionary.

    Args:
        path: A filesystem path used by the helper.

    Returns:
        The returned `dict[str, Any]` value used by the caller.
"""
    return json.loads(path.read_text())


def _copy_file(source: Path, destination: Path) -> Path:
    """Copy a file into a deterministic staging location and preserve metadata.

    Args:
        source: A filesystem path used by the helper.
        destination: A filesystem path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _manifest_path(results_dir: Path, label: str) -> Path:
    """Locate the canonical `run_manifest.json` file in a results bundle directory.

    Args:
        results_dir: A directory path used by the helper.
        label: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    return require_path(results_dir / "run_manifest.json", f"{label} manifest")


def _manifest_output_path(manifest: dict[str, Any], key: str, description: str) -> Path | None:
    """Resolve a named output path from a stage manifest's `outputs` section if present.

    Args:
        manifest: A value used by the helper.
        key: A value used by the helper.
        description: A value used by the helper.

    Returns:
        The returned `Path | None` value used by the caller.
"""
    output_path = manifest.get("outputs", {}).get(key)
    if not output_path:
        return None
    return require_path(Path(str(output_path)), description)


def _pasa_assemblies_gff3_from_results(results_dir: Path, manifest: dict[str, Any]) -> Path:
    """Locate the PASA assemblies GFF3 file from an upstream PASA results bundle.

    Args:
        results_dir: A directory path used by the helper.
        manifest: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    manifest_path = _manifest_output_path(
        manifest,
        "pasa_assemblies_gff3",
        "PASA assemblies GFF3 recorded in the PASA manifest",
    )
    if manifest_path is not None:
        return manifest_path

    pasa_dir = require_path(results_dir / "pasa", "PASA output directory")
    config_dir = require_path(results_dir / "config", "PASA config directory")
    database_name = _sqlite_db_path(config_dir).name
    pasa_assemblies_gff3 = _pasa_assemblies_gff3(pasa_dir, database_name)
    if pasa_assemblies_gff3 is None:
        raise FileNotFoundError(
            f"PASA assemblies GFF3 not found under {pasa_dir}; expected `${{db}}.pasa_assemblies.gff3`."
        )
    return pasa_assemblies_gff3


def _transdecoder_genome_gff3_from_results(results_dir: Path, manifest: dict[str, Any]) -> Path:
    """Locate the TransDecoder genome GFF3 from PASA/TransDecoder results.

    Args:
        results_dir: A directory path used by the helper.
        manifest: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    manifest_path = _manifest_output_path(
        manifest,
        "transdecoder_genome_gff3",
        "TransDecoder genome GFF3 recorded in the TransDecoder manifest",
    )
    if manifest_path is not None:
        return manifest_path

    transdecoder_dir = require_path(results_dir / "transdecoder", "TransDecoder output directory")
    transcript_fasta_path = _manifest_output_path(
        manifest,
        "input_transcripts_fasta",
        "TransDecoder input transcript FASTA recorded in the TransDecoder manifest",
    )
    if transcript_fasta_path is None:
        raise FileNotFoundError(
            "TransDecoder manifest does not record input_transcripts_fasta, so the genome GFF3 cannot be resolved deterministically."
        )
    transdecoder_genome_gff3 = _transdecoder_genome_gff3(transdecoder_dir, transcript_fasta_path.name)
    if transdecoder_genome_gff3 is None:
        raise FileNotFoundError(
            f"TransDecoder genome GFF3 not found under {transdecoder_dir}; expected `{transcript_fasta_path.name}.transdecoder.genome.gff3`."
        )
    return transdecoder_genome_gff3


def _protein_evidence_gff3_from_results(results_dir: Path, manifest: dict[str, Any]) -> Path:
    """Locate the final processed protein evidence GFF3 file from upstream Exonerate results.

    Args:
        results_dir: A directory path used by the helper.
        manifest: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    manifest_path = _manifest_output_path(
        manifest,
        "concatenated_evm_protein_gff3",
        "Concatenated protein evidence GFF3 recorded in the protein-evidence manifest",
    )
    if manifest_path is not None:
        return manifest_path
    return require_path(results_dir / "protein_evidence.evm.gff3", "Protein evidence EVM GFF3")


def _normalized_braker_gff3_from_results(results_dir: Path, manifest: dict[str, Any]) -> Path:
    """Resolve the normalized BRAKER3 GFF3 file prepared for evidence integration.

    Args:
        results_dir: A directory path used by the helper.
        manifest: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    manifest_path = _manifest_output_path(
        manifest,
        "normalized_braker_gff3",
        "Normalized BRAKER3 GFF3 recorded in the BRAKER3 manifest",
    )
    if manifest_path is not None:
        return manifest_path
    return require_path(
        results_dir / "braker3_normalized" / "braker3.evm.gff3",
        "Normalized BRAKER3 GFF3",
    )


def _braker_genome_fasta(results_dir: Path) -> Path:
    """Retrieve the reference genome FASTA from the BRAKER3 results staging area.

    Args:
        results_dir: A directory path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    staged_inputs_dir = require_path(results_dir / "staged_inputs", "BRAKER3 staged inputs directory")
    return _staged_genome_fasta(staged_inputs_dir)


def _write_concatenated_gff3(source_paths: list[Path], destination: Path) -> Path:
    """Concatenate multiple GFF3 files into one canonical merged file with unified header.

    Args:
        source_paths: A value used by the helper.
        destination: A filesystem path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w") as out_handle:
        out_handle.write("##gff-version 3\n")
        for source_path in source_paths:
            with source_path.open() as source_handle:
                for raw_line in source_handle:
                    if not raw_line.strip() or raw_line.startswith("##gff-version"):
                        continue
                    out_handle.write(raw_line if raw_line.endswith("\n") else f"{raw_line}\n")
    return destination


def _prepared_prediction_transdecoder_gff3(prepared_dir: Path, manifest: dict[str, Any]) -> Path:
    """Resolve the staged TransDecoder genome GFF3 within a prepared prediction bundle.

    Args:
        prepared_dir: A directory path used by the helper.
        manifest: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    recorded_path = manifest.get("outputs", {}).get("transdecoder_genome_gff3")
    if recorded_path:
        return require_path(
            prepared_dir / Path(str(recorded_path)).name,
            "Collected staged TransDecoder genome GFF3",
        )

    candidates = sorted(prepared_dir.glob("*.transdecoder.genome.gff3"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(
        f"Unable to resolve the staged TransDecoder genome GFF3 under {prepared_dir}."
    )


@consensus_prep_env.task
def prepare_evm_transcript_inputs(
    passa_results: Dir,
) -> Dir:
    """Stage PASA transcript evidence as the EVM transcript channel input.

    Args:
        passa_results: A directory path used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    results_dir = require_path(Path(pasa_results.download_sync()), "PASA results directory")
    manifest = _read_json(_manifest_path(results_dir, "PASA"))
    pasa_assemblies_gff3 = _pasa_assemblies_gff3_from_results(results_dir, manifest)

    out_dir = project_mkdtemp("evm_transcript_inputs_") / "transcript_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    staged_gff3 = _copy_file(pasa_assemblies_gff3, out_dir / "transcripts.gff3")
    source_fields = _gff3_source_names(staged_gff3)
    asset = EvmTranscriptInputBundleAsset(
        staged_dir=out_dir,
        transcripts_gff3_path=staged_gff3,
        source_results_dir=results_dir,
        notes=(
            "The transcript channel is the PASA assemblies GFF3 copied directly to transcripts.gff3.",
        ),
    )
    run_manifest = {
        "stage": "prepare_evm_transcript_inputs",
        "evm_category": "TRANSCRIPT",
        "evm_source_fields": list(source_fields),
        "evm_weight_categories": ["TRANSCRIPT" for _ in source_fields],
        "assumptions": [
            "The source notes define `${db}.pasa_assemblies.gff3` as the transcript evidence input to the pre-EVM boundary.",
            "This milestone does not invent an additional PASA-to-EVM transcript conversion step beyond deterministic staging to transcripts.gff3.",
        ],
        "source_results_bundle": str(results_dir),
        "source_bundle_manifest": manifest,
        "outputs": {
            "transcripts_gff3": str(staged_gff3),
        },
        "assets": _as_json_compatible({"evm_transcript_input_bundle": asdict(asset)}),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2))
    return Dir(path=str(out_dir))


@consensus_prep_env.task
def prepare_evm_protein_inputs(
    protein_evidence_results: Dir,
) -> Dir:
    """Stage protein homology evidence as the EVM protein channel input.

    Args:
        protein_evidence_results: A directory path used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    results_dir = require_path(
        Path(protein_evidence_results.download_sync()),
        "Protein evidence results directory",
    )
    manifest = _read_json(_manifest_path(results_dir, "Protein evidence"))
    protein_gff3 = _protein_evidence_gff3_from_results(results_dir, manifest)

    out_dir = project_mkdtemp("evm_protein_inputs_") / "protein_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    staged_gff3 = _copy_file(protein_gff3, out_dir / "proteins.gff3")
    source_fields = _gff3_source_names(staged_gff3)
    asset = EvmProteinInputBundleAsset(
        staged_dir=out_dir,
        proteins_gff3_path=staged_gff3,
        source_results_dir=results_dir,
        notes=(
            "The protein channel is staged from the downstream-ready Exonerate-derived GFF3 already produced upstream.",
        ),
    )
    run_manifest = {
        "stage": "prepare_evm_protein_inputs",
        "evm_category": "PROTEIN",
        "evm_source_fields": list(source_fields),
        "evm_weight_categories": ["PROTEIN" for _ in source_fields],
        "assumptions": [
            "The notes-faithful protein channel is an Exonerate-derived protein evidence GFF3 staged here as proteins.gff3.",
            "No additional protein preprocessing or database fetching is added in this milestone.",
        ],
        "source_results_bundle": str(results_dir),
        "source_bundle_manifest": manifest,
        "outputs": {
            "proteins_gff3": str(staged_gff3),
        },
        "assets": _as_json_compatible({"evm_protein_input_bundle": asdict(asset)}),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2))
    return Dir(path=str(out_dir))


@consensus_prep_env.task
def prepare_evm_prediction_inputs(
    transdecoder_results: Dir,
    braker3_results: Dir,
) -> Dir:
    """Assemble ab initio and coding predictions as the EVM predictions channel.

    Args:
        transdecoder_results: A directory path used by the helper.
        braker3_results: A directory path used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    transdecoder_results_dir = require_path(
        Path(transdecoder_results.download_sync()),
        "TransDecoder results directory",
    )
    braker3_results_dir = require_path(Path(braker3_results.download_sync()), "BRAKER3 results directory")
    transdecoder_manifest = _read_json(_manifest_path(transdecoder_results_dir, "TransDecoder"))
    braker_manifest = _read_json(_manifest_path(braker3_results_dir, "BRAKER3"))

    transdecoder_genome_gff3 = _transdecoder_genome_gff3_from_results(
        transdecoder_results_dir,
        transdecoder_manifest,
    )
    normalized_braker_gff3 = _normalized_braker_gff3_from_results(braker3_results_dir, braker_manifest)
    genome_fasta = _braker_genome_fasta(braker3_results_dir)

    out_dir = project_mkdtemp("evm_prediction_inputs_") / "prediction_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    staged_braker_gff3 = _copy_file(normalized_braker_gff3, out_dir / "braker.gff3")
    staged_transdecoder_gff3 = _copy_file(
        transdecoder_genome_gff3,
        out_dir / transdecoder_genome_gff3.name,
    )
    staged_genome = _copy_file(genome_fasta, out_dir / "genome.fa")
    predictions_gff3 = _write_concatenated_gff3(
        [staged_braker_gff3, staged_transdecoder_gff3],
        out_dir / "predictions.gff3",
    )
    source_fields = _gff3_source_names(predictions_gff3)

    asset = EvmPredictionInputBundleAsset(
        staged_dir=out_dir,
        predictions_gff3_path=predictions_gff3,
        braker_gff3_path=staged_braker_gff3,
        transdecoder_genome_gff3_path=staged_transdecoder_gff3,
        reference_genome_fasta_path=staged_genome,
        source_braker3_results_dir=braker3_results_dir,
        source_transdecoder_results_dir=transdecoder_results_dir,
        notes=(
            "The predictions channel is assembled by concatenating braker.gff3 with the PASA-derived TransDecoder genome GFF3.",
            "The staged braker.gff3 copy comes from the deterministic normalized BRAKER3 result bundle produced upstream.",
        ),
    )
    run_manifest = {
        "stage": "prepare_evm_prediction_inputs",
        "evm_source_fields": list(source_fields),
        "evm_weight_categories": [
            "OTHER_PREDICTION" if source_name.strip().lower() == "transdecoder" else "ABINITIO_PREDICTION"
            for source_name in source_fields
        ],
        "notes_backed_behavior": [
            "The source notes define predictions.gff3 as braker.gff3 plus `${db}.assemblies.fasta.transdecoder.genome.gff3`.",
        ],
        "tutorial_backed_behavior": [
            "The upstream BRAKER3 source bundle comes from the repo's Galaxy tutorial-backed runtime model.",
        ],
        "repo_policy": [
            "This milestone reuses the normalized BRAKER3 GFF3 already produced upstream and stages it back to the note-faithful braker.gff3 filename for the pre-EVM bundle.",
            "The normalized BRAKER3 bundle preserves upstream source-column values instead of rewriting them to a repo-owned label.",
            "Exact TransDecoder command sequencing remains an inferred upstream contract documented in the source bundles.",
        ],
        "source_results_bundles": {
            "transdecoder_results": str(transdecoder_results_dir),
            "braker3_results": str(braker3_results_dir),
        },
        "source_bundle_manifests": {
            "transdecoder": transdecoder_manifest,
            "braker3": braker_manifest,
        },
        "component_order": [
            str(staged_braker_gff3),
            str(staged_transdecoder_gff3),
        ],
        "outputs": {
            "reference_genome_fasta": str(staged_genome),
            "braker_gff3": str(staged_braker_gff3),
            "transdecoder_genome_gff3": str(staged_transdecoder_gff3),
            "predictions_gff3": str(predictions_gff3),
        },
        "assets": _as_json_compatible({"evm_prediction_input_bundle": asdict(asset)}),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2))
    return Dir(path=str(out_dir))


@consensus_prep_env.task
def collect_evm_prep_results(
    transcript_inputs: Dir,
    protein_inputs: Dir,
    prediction_inputs: Dir,
    pasa_results: Dir,
    transdecoder_results: Dir,
    protein_evidence_results: Dir,
    braker3_results: Dir,
) -> Dir:
    """Finalize the pre-EVM evidence bundle with consolidated provenance.

    Args:
        transcript_inputs: A value used by the helper.
        protein_inputs: A value used by the helper.
        prediction_inputs: A value used by the helper.
        pasa_results: A directory path used by the helper.
        transdecoder_results: A directory path used by the helper.
        protein_evidence_results: A directory path used by the helper.
        braker3_results: A directory path used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    transcript_inputs_dir = require_path(Path(transcript_inputs.download_sync()), "Prepared transcript inputs")
    protein_inputs_dir = require_path(Path(protein_inputs.download_sync()), "Prepared protein inputs")
    prediction_inputs_dir = require_path(Path(prediction_inputs.download_sync()), "Prepared prediction inputs")
    pasa_results_dir = require_path(Path(pasa_results.download_sync()), "PASA results directory")
    transdecoder_results_dir = require_path(
        Path(transdecoder_results.download_sync()),
        "TransDecoder results directory",
    )
    protein_results_dir = require_path(
        Path(protein_evidence_results.download_sync()),
        "Protein evidence results directory",
    )
    braker_results_dir = require_path(Path(braker3_results.download_sync()), "BRAKER3 results directory")

    transcript_manifest = _read_json(_manifest_path(transcript_inputs_dir, "Prepared transcript inputs"))
    protein_manifest = _read_json(_manifest_path(protein_inputs_dir, "Prepared protein inputs"))
    prediction_manifest = _read_json(_manifest_path(prediction_inputs_dir, "Prepared prediction inputs"))

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{CONSENSUS_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    prepared_inputs_dir = out_dir / "prepared_inputs"
    prepared_transcript_dir = prepared_inputs_dir / "transcripts"
    prepared_protein_dir = prepared_inputs_dir / "proteins"
    prepared_prediction_dir = prepared_inputs_dir / "predictions"
    source_manifests_dir = out_dir / "source_manifests"
    reference_dir = out_dir / "reference"

    shutil.copytree(transcript_inputs_dir, prepared_transcript_dir, dirs_exist_ok=True)
    shutil.copytree(protein_inputs_dir, prepared_protein_dir, dirs_exist_ok=True)
    shutil.copytree(prediction_inputs_dir, prepared_prediction_dir, dirs_exist_ok=True)
    source_manifests_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)

    transcripts_gff3 = _copy_file(
        require_path(prepared_transcript_dir / "transcripts.gff3", "Prepared transcripts.gff3"),
        out_dir / "transcripts.gff3",
    )
    proteins_gff3 = _copy_file(
        require_path(prepared_protein_dir / "proteins.gff3", "Prepared proteins.gff3"),
        out_dir / "proteins.gff3",
    )
    predictions_gff3 = _copy_file(
        require_path(prepared_prediction_dir / "predictions.gff3", "Prepared predictions.gff3"),
        out_dir / "predictions.gff3",
    )
    reference_genome = _copy_file(
        require_path(prepared_prediction_dir / "genome.fa", "Prepared reference genome FASTA"),
        reference_dir / "genome.fa",
    )
    transcript_source_fields = _gff3_source_names(transcripts_gff3)
    prediction_source_fields = _gff3_source_names(predictions_gff3)
    protein_source_fields = _gff3_source_names(proteins_gff3)

    copied_pasa_manifest = _copy_file(
        _manifest_path(pasa_results_dir, "PASA"),
        source_manifests_dir / "pasa.run_manifest.json",
    )
    copied_transdecoder_manifest = _copy_file(
        _manifest_path(transdecoder_results_dir, "TransDecoder"),
        source_manifests_dir / "transdecoder.run_manifest.json",
    )
    copied_protein_manifest = _copy_file(
        _manifest_path(protein_results_dir, "Protein evidence"),
        source_manifests_dir / "protein_evidence.run_manifest.json",
    )
    copied_braker_manifest = _copy_file(
        _manifest_path(braker_results_dir, "BRAKER3"),
        source_manifests_dir / "braker3.run_manifest.json",
    )

    transcript_asset = EvmTranscriptInputBundleAsset(
        staged_dir=prepared_transcript_dir,
        transcripts_gff3_path=require_path(
            prepared_transcript_dir / "transcripts.gff3",
            "Collected transcripts.gff3",
        ),
        source_results_dir=pasa_results_dir,
        notes=(
            "Collected transcript evidence now matches the notes-faithful pre-EVM filename contract.",
        ),
    )
    protein_asset = EvmProteinInputBundleAsset(
        staged_dir=prepared_protein_dir,
        proteins_gff3_path=require_path(prepared_protein_dir / "proteins.gff3", "Collected proteins.gff3"),
        source_results_dir=protein_results_dir,
        notes=(
            "Collected protein evidence now matches the notes-faithful pre-EVM filename contract.",
        ),
    )
    prediction_asset = EvmPredictionInputBundleAsset(
        staged_dir=prepared_prediction_dir,
        predictions_gff3_path=require_path(
            prepared_prediction_dir / "predictions.gff3",
            "Collected predictions.gff3",
        ),
        braker_gff3_path=require_path(prepared_prediction_dir / "braker.gff3", "Collected braker.gff3"),
        transdecoder_genome_gff3_path=_prepared_prediction_transdecoder_gff3(
            prepared_prediction_dir,
            prediction_manifest,
        ),
        reference_genome_fasta_path=require_path(prepared_prediction_dir / "genome.fa", "Collected genome FASTA"),
        source_braker3_results_dir=braker_results_dir,
        source_transdecoder_results_dir=transdecoder_results_dir,
        notes=(
            "Collected prediction evidence now matches the notes-faithful pre-EVM filename contract while preserving upstream inferred provenance.",
        ),
    )
    bundle_asset = EvmInputPreparationBundle(
        result_dir=out_dir,
        reference_genome_fasta_path=reference_genome,
        transcripts_gff3_path=transcripts_gff3,
        predictions_gff3_path=predictions_gff3,
        proteins_gff3_path=proteins_gff3,
        transcript_bundle=transcript_asset,
        protein_bundle=protein_asset,
        prediction_bundle=prediction_asset,
        manifest_path=out_dir / "run_manifest.json",
        notes=(
            "This milestone stops at deterministic pre-EVM file assembly and does not execute EvidenceModeler.",
        ),
    )

    manifest = {
        "workflow": CONSENSUS_WORKFLOW_NAME,
        "notes_backed_behavior": [
            "This milestone assembles the note-faithful pre-EVM contract and stops before EvidenceModeler execution.",
            "transcripts.gff3 is copied directly from PASA assemblies GFF3.",
            "predictions.gff3 is assembled by concatenating the staged braker.gff3 copy with the PASA-derived TransDecoder genome GFF3 in that order.",
            "proteins.gff3 is copied from the downstream-ready Exonerate-derived protein evidence GFF3.",
        ],
        "tutorial_backed_behavior": [
            "The upstream BRAKER3 source bundle uses the repo's Galaxy tutorial-backed runtime model, not a notes-authored command specification.",
        ],
        "repo_policy": [
            "The staged braker.gff3 copy comes from the normalized BRAKER3 output bundle so the pre-EVM contract keeps a stable file boundary while preserving upstream BRAKER source-column values.",
        ],
        "source_bundles": {
            "pasa_results": str(pasa_results_dir),
            "transdecoder_results": str(transdecoder_results_dir),
            "protein_evidence_results": str(protein_results_dir),
            "braker3_results": str(braker_results_dir),
        },
        "copied_source_manifests": {
            "pasa": str(copied_pasa_manifest),
            "transdecoder": str(copied_transdecoder_manifest),
            "protein_evidence": str(copied_protein_manifest),
            "braker3": str(copied_braker_manifest),
        },
        "pre_evm_contract": {
            "reference_genome_fasta": {
                "path": str(reference_genome),
                "authoritative_source": "BRAKER3 staged genome bundle",
            },
            "transcripts.gff3": {
                "path": str(transcripts_gff3),
                "source_fields": list(transcript_source_fields),
                "weight_categories": ["TRANSCRIPT" for _ in transcript_source_fields],
            },
            "predictions.gff3": {
                "path": str(predictions_gff3),
                "source_fields": list(prediction_source_fields),
                "weight_categories": [
                    "OTHER_PREDICTION" if source_name.strip().lower() == "transdecoder" else "ABINITIO_PREDICTION"
                    for source_name in prediction_source_fields
                ],
                "component_order": [
                    str(prediction_asset.braker_gff3_path),
                    str(prediction_asset.transdecoder_genome_gff3_path),
                ],
            },
            "proteins.gff3": {
                "path": str(proteins_gff3),
                "source_fields": list(protein_source_fields),
                "weight_categories": ["PROTEIN" for _ in protein_source_fields],
            },
        },
        "prepared_stage_manifests": {
            "transcript": transcript_manifest,
            "prediction": prediction_manifest,
            "protein": protein_manifest,
        },
        "outputs": {
            "prepared_inputs_dir": str(prepared_inputs_dir),
            "reference_dir": str(reference_dir),
            "reference_genome_fasta": str(reference_genome),
            "transcripts_gff3": str(transcripts_gff3),
            "predictions_gff3": str(predictions_gff3),
            "proteins_gff3": str(proteins_gff3),
        },
        "assets": _as_json_compatible({"evm_input_preparation_bundle": asdict(bundle_asset)}),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON manifest to disk with indentation for human readability.

    Args:
        path: A filesystem path used by the helper.
        payload: The structured payload to serialize or inspect.

    Returns:
        The returned `Path` value used by the caller.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _copy_tree(source: Path, destination: Path) -> Path:
    """Copy an entire directory tree to a deterministic staging location.

    Args:
        source: A filesystem path used by the helper.
        destination: A filesystem path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return destination


def _manifest_from_dir(results_dir: Path, label: str) -> dict[str, Any]:
    """Load the run manifest associated with a staged or results collection directory.

    Args:
        results_dir: A directory path used by the helper.
        label: A value used by the helper.

    Returns:
        The returned `dict[str, Any]` value used by the caller.
"""
    return _read_json(_manifest_path(results_dir, label))


def _gff3_source_names(gff3_path: Path) -> tuple[str, ...]:
    """Extract unique GFF3 source-column values in first-appearance order.

    Args:
        gff3_path: A filesystem path used by the helper.

    Returns:
        The returned `tuple[str, ...]` value used by the caller.
"""
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


def _workspace_file(workspace_dir: Path, name: str, description: str) -> Path:
    """Validate and resolve a required file within an EVM execution workspace.

    Args:
        workspace_dir: A directory path used by the helper.
        name: A value used by the helper.
        description: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    return require_path(workspace_dir / name, description)


def _partition_listing_path(workspace_dir: Path) -> Path:
    """Locate the `partitions_list.out` file produced by EVM partitioning.

    Args:
        workspace_dir: A directory path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    return _workspace_file(workspace_dir, "partitions_list.out", "EVM partition listing")


def _commands_path(workspace_dir: Path) -> Path:
    """Locate the `commands.list` file produced by EVM command generation.

    Args:
        workspace_dir: A directory path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    return _workspace_file(workspace_dir, "commands.list", "EVM commands list")


def _recombined_gff3_paths(workspace_dir: Path, output_file_name: str) -> list[Path]:
    """Collect per-partition GFF3 result files in deterministic lexicographic order.

    Args:
        workspace_dir: A directory path used by the helper.
        output_file_name: A value used by the helper.

    Returns:
        The returned `list[Path]` value used by the caller.
"""
    candidates = sorted(
        workspace_dir.rglob(f"{output_file_name}.gff3"),
        key=lambda path: str(path.relative_to(workspace_dir)),
    )
    if not candidates:
        raise FileNotFoundError(
            f"No converted `{output_file_name}.gff3` files were found under {workspace_dir}."
        )
    return candidates


def _partition_entries(partition_listing: Path) -> list[str]:
    """Parse the EVM partition listing file into a normalized entry list.

    Args:
        partition_listing: A value used by the helper.

    Returns:
        The returned `list[str]` value used by the caller.
"""
    return [line.strip() for line in partition_listing.read_text().splitlines() if line.strip()]


def _command_lines(commands_path: Path) -> list[str]:
    """Parse the EVM commands.list file into a normalized command set.

    Args:
        commands_path: A filesystem path used by the helper.

    Returns:
        The returned `list[str]` value used by the caller.
"""
    return [line.strip() for line in commands_path.read_text().splitlines() if line.strip()]


def _weight_spec_for_source(source_name: str) -> tuple[str, int]:
    """Infer EVM evidence category and default weight from a GFF3 source name.

    Args:
        source_name: A value used by the helper.

    Returns:
        The returned `tuple[str, int]` value used by the caller.
"""
    normalized = source_name.strip().lower()
    if normalized in {"exonerate", "exonerate_protein"}:
        return ("PROTEIN", 5)
    if normalized in {"pasa", "assembler-pasa_db.sqlite"}:
        return ("TRANSCRIPT", 10)
    if normalized == "transdecoder":
        return ("OTHER_PREDICTION", 5)
    return ("ABINITIO_PREDICTION", 3)


def _inferred_evm_weight_lines(
    transcript_sources: tuple[str, ...],
    protein_sources: tuple[str, ...],
    prediction_sources: tuple[str, ...],
) -> list[str]:
    """Generate EVM weight file lines from discovered GFF3 source names.

    Args:
        transcript_sources: A value used by the helper.
        protein_sources: A value used by the helper.
        prediction_sources: A value used by the helper.

    Returns:
        The returned `list[str]` value used by the caller.
"""
    grouped: dict[str, list[str]] = {
        "ABINITIO_PREDICTION": [],
        "PROTEIN": [],
        "TRANSCRIPT": [],
        "OTHER_PREDICTION": [],
    }
    seen_sources: set[str] = set()
    ordered_sources = (
        [(source_name, "prediction") for source_name in prediction_sources]
        + [(source_name, "protein") for source_name in protein_sources]
        + [(source_name, "transcript") for source_name in transcript_sources]
    )
    for source_name, channel in ordered_sources:
        if source_name in seen_sources:
            continue
        category, weight = _weight_spec_for_source(source_name)
        if channel == "protein":
            category, weight = ("PROTEIN", 5)
        elif channel == "transcript":
            category, weight = ("TRANSCRIPT", 10)
        grouped[category].append(f"{category}\t{source_name}\t{weight}")
        seen_sources.add(source_name)
    ordered_lines: list[str] = []
    for category in ("ABINITIO_PREDICTION", "PROTEIN", "TRANSCRIPT", "OTHER_PREDICTION"):
        ordered_lines.extend(grouped[category])
    if not ordered_lines:
        raise ValueError("No GFF3 source names were discovered, so an EVM weights file cannot be inferred.")
    return ordered_lines


def _write_evm_weights(
    destination: Path,
    transcript_sources: tuple[str, ...],
    protein_sources: tuple[str, ...],
    prediction_sources: tuple[str, ...],
    evm_weights_text: str,
) -> Path:
    """Write an EVM weights file from explicit text or inferred source categories.

    Args:
        destination: A filesystem path used by the helper.
        transcript_sources: A value used by the helper.
        protein_sources: A value used by the helper.
        prediction_sources: A value used by the helper.
        evm_weights_text: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if evm_weights_text.strip():
        weight_lines = [line.rstrip() for line in evm_weights_text.strip().splitlines() if line.strip()]
    else:
        weight_lines = _inferred_evm_weight_lines(
            transcript_sources=transcript_sources,
            protein_sources=protein_sources,
            prediction_sources=prediction_sources,
        )
    destination.write_text("\n".join(weight_lines) + "\n")
    return destination


def _write_blank_line_filtered_gff3(source: Path, destination: Path) -> Path:
    """Remove blank lines from a GFF3 file to produce syntactically clean output.

    Args:
        source: A filesystem path used by the helper.
        destination: A filesystem path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    filtered_lines = [line for line in source.read_text().splitlines() if line.strip()]
    destination.write_text("\n".join(filtered_lines) + "\n")
    return destination


@consensus_evm_env.task
def prepare_evm_execution_inputs(
    evm_prep_results: Dir,
    evm_weights_text: str = "",
) -> Dir:
    """Stage pre-EVM evidence into an execution workspace with computed weights.

    Args:
        evm_prep_results: A directory path used by the helper.
        evm_weights_text: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    prep_results_dir = require_path(
        Path(evm_prep_results.download_sync()),
        "Pre-EVM results directory",
    )
    prep_manifest = _manifest_from_dir(prep_results_dir, "Pre-EVM")

    out_dir = project_mkdtemp("evm_execution_inputs_") / "evm_execution_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    transcripts_gff3 = _copy_file(
        require_path(prep_results_dir / "transcripts.gff3", "Pre-EVM transcripts.gff3"),
        out_dir / "transcripts.gff3",
    )
    predictions_gff3 = _copy_file(
        require_path(prep_results_dir / "predictions.gff3", "Pre-EVM predictions.gff3"),
        out_dir / "predictions.gff3",
    )
    proteins_gff3 = _copy_file(
        require_path(prep_results_dir / "proteins.gff3", "Pre-EVM proteins.gff3"),
        out_dir / "proteins.gff3",
    )
    genome_fasta = _copy_file(
        require_path(prep_results_dir / "reference" / "genome.fa", "Pre-EVM reference genome FASTA"),
        out_dir / "genome.fa",
    )
    if (prep_results_dir / "source_manifests").exists():
        _copy_tree(prep_results_dir / "source_manifests", out_dir / "source_manifests")

    transcript_sources = _gff3_source_names(transcripts_gff3)
    protein_sources = _gff3_source_names(proteins_gff3)
    prediction_sources = _gff3_source_names(predictions_gff3)
    weights_path = _write_evm_weights(
        out_dir / "evm.weights",
        transcript_sources=transcript_sources,
        protein_sources=protein_sources,
        prediction_sources=prediction_sources,
        evm_weights_text=evm_weights_text,
    )

    execution_asset = EvmExecutionInputBundleAsset(
        workspace_dir=out_dir,
        reference_genome_fasta_path=genome_fasta,
        transcripts_gff3_path=transcripts_gff3,
        predictions_gff3_path=predictions_gff3,
        proteins_gff3_path=proteins_gff3,
        weights_path=weights_path,
        source_pre_evm_results_dir=prep_results_dir,
        notes=(
            "This workspace is staged strictly from the existing pre-EVM bundle and does not re-derive transcript, prediction, or protein evidence.",
            "When no explicit weights are provided, the weights file is an inferred adaptation of the note example to the staged per-channel source names present in this repo.",
        ),
    )
    manifest = {
        "stage": "prepare_evm_execution_inputs",
        "notes_backed_behavior": [
            "This Milestone 2 stage consumes the existing pre-EVM bundle directly instead of re-deriving upstream evidence channels.",
            "The pre-EVM filenames remain unchanged from Milestone 1: transcripts.gff3, predictions.gff3, and proteins.gff3.",
        ],
        "tutorial_backed_behavior": [
            "Any BRAKER-derived prediction sources present in the pre-EVM bundle came from the repo's tutorial-backed BRAKER3 runtime model.",
        ],
        "repo_policy": [
            "If evm_weights_text is empty, the weights file is inferred from the notes example and adapted to the staged per-channel source fields rather than to a forced `BRAKER3` label.",
            "Any non-TransDecoder prediction source discovered in predictions.gff3 is treated as an ab initio prediction with the repo's default weight of 3 unless the user supplies an explicit weights file override.",
        ],
        "inputs": {
            "evm_prep_results": str(prep_results_dir),
            "explicit_evm_weights_text_provided": bool(evm_weights_text.strip()),
        },
        "discovered_sources": {
            "transcripts": list(transcript_sources),
            "proteins": list(protein_sources),
            "predictions": list(prediction_sources),
        },
        "source_bundle_manifest": prep_manifest,
        "outputs": {
            "genome_fasta": str(genome_fasta),
            "transcripts_gff3": str(transcripts_gff3),
            "predictions_gff3": str(predictions_gff3),
            "proteins_gff3": str(proteins_gff3),
            "evm_weights": str(weights_path),
        },
        "assets": _as_json_compatible({"evm_execution_input_bundle": asdict(execution_asset)}),
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@consensus_evm_env.task
def evm_partition_inputs(
    evm_execution_inputs: Dir,
    evm_partition_script: str = "partition_EVM_inputs.pl",
    evm_segment_size: int = 3000000,
    evm_overlap_size: int = 300000,
    evm_sif: str = "",
) -> Dir:
    """Partition genome and evidence tracks into segments for distributed EVM execution.

    Args:
        evm_execution_inputs: A value used by the helper.
        evm_partition_script: A value used by the helper.
        evm_segment_size: A value used by the helper.
        evm_overlap_size: A value used by the helper.
        evm_sif: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    execution_inputs_dir = require_path(
        Path(evm_execution_inputs.download_sync()),
        "EVM execution input directory",
    )
    input_manifest = _manifest_from_dir(execution_inputs_dir, "EVM execution inputs")

    out_dir = project_mkdtemp("evm_partition_") / "evm_partitioned"
    _copy_tree(execution_inputs_dir, out_dir)

    cmd = [
        "perl",
        evm_partition_script,
        "--partition_dir",
        "Partitions",
        "--genome",
        "genome.fa",
        "--gene_predictions",
        "predictions.gff3",
        "--protein_alignments",
        "proteins.gff3",
        "--transcript_alignments",
        "transcripts.gff3",
        "--segmentSize",
        str(evm_segment_size),
        "--overlapSize",
        str(evm_overlap_size),
        "--partition_listing",
        "partitions_list.out",
    ]
    run_tool(cmd, evm_sif, [out_dir], cwd=out_dir)

    partitions_dir = _workspace_file(out_dir, "Partitions", "EVM partition directory")
    partition_listing = _partition_listing_path(out_dir)
    partition_entries = _partition_entries(partition_listing)

    partition_asset = EvmPartitionBundleAsset(
        workspace_dir=out_dir,
        partitions_dir=partitions_dir,
        partition_listing_path=partition_listing,
        segment_size=evm_segment_size,
        overlap_size=evm_overlap_size,
        execution_input_bundle=EvmExecutionInputBundleAsset(
            workspace_dir=execution_inputs_dir,
            reference_genome_fasta_path=_workspace_file(
                execution_inputs_dir,
                "genome.fa",
                "EVM execution genome FASTA",
            ),
            transcripts_gff3_path=_workspace_file(
                execution_inputs_dir,
                "transcripts.gff3",
                "EVM execution transcripts.gff3",
            ),
            predictions_gff3_path=_workspace_file(
                execution_inputs_dir,
                "predictions.gff3",
                "EVM execution predictions.gff3",
            ),
            proteins_gff3_path=_workspace_file(
                execution_inputs_dir,
                "proteins.gff3",
                "EVM execution proteins.gff3",
            ),
            weights_path=_workspace_file(execution_inputs_dir, "evm.weights", "EVM weights file"),
        ),
        notes=(
            "Partitioning uses the exact segment and overlap settings shown in the notes by default.",
        ),
    )
    manifest = {
        "stage": "evm_partition_inputs",
        "assumptions": [
            "Partitioning is run directly against the Milestone 1 pre-EVM bundle staged into the EVM workspace.",
            "The default segment and overlap sizes follow the note example: 3000000 and 300000.",
        ],
        "inputs": {
            "evm_execution_inputs": str(execution_inputs_dir),
            "evm_partition_script": evm_partition_script,
            "evm_segment_size": evm_segment_size,
            "evm_overlap_size": evm_overlap_size,
            "evm_sif": evm_sif,
        },
        "source_stage_manifest": input_manifest,
        "partition_entries": partition_entries,
        "outputs": {
            "partitions_dir": str(partitions_dir),
            "partition_listing": str(partition_listing),
        },
        "assets": _as_json_compatible({"evm_partition_bundle": asdict(partition_asset)}),
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@consensus_evm_env.task
def evm_write_commands(
    partitioned_evm_inputs: Dir,
    evm_write_commands_script: str = "write_EVM_commands.pl",
    evm_output_file_name: str = "evm.out",
    evm_sif: str = "",
) -> Dir:
    """Generate the EvidenceModeler command list for each partition and normalize it.

    Args:
        partitioned_evm_inputs: A value used by the helper.
        evm_write_commands_script: A value used by the helper.
        evm_output_file_name: A value used by the helper.
        evm_sif: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    partitioned_dir = require_path(
        Path(partitioned_evm_inputs.download_sync()),
        "Partitioned EVM directory",
    )
    partition_manifest = _manifest_from_dir(partitioned_dir, "Partitioned EVM inputs")

    out_dir = project_mkdtemp("evm_commands_") / "evm_commands"
    _copy_tree(partitioned_dir, out_dir)

    commands_path = out_dir / "commands.list"
    cmd = [
        "perl",
        evm_write_commands_script,
        "--genome",
        "genome.fa",
        "--weights",
        str(require_path(out_dir / "evm.weights", "EVM weights file")),
        "--gene_predictions",
        "predictions.gff3",
        "--protein_alignments",
        "proteins.gff3",
        "--transcript_alignments",
        "transcripts.gff3",
        "--output_file_name",
        evm_output_file_name,
        "--partitions",
        "partitions_list.out",
    ]
    run_tool(cmd, evm_sif, [out_dir], cwd=out_dir, stdout_path=commands_path)

    normalized_commands = _command_lines(commands_path)
    if not normalized_commands:
        raise ValueError("EVM command generation produced no commands.")
    commands_path.write_text("\n".join(normalized_commands) + "\n")

    command_asset = EvmCommandSetAsset(
        workspace_dir=out_dir,
        commands_path=commands_path,
        output_file_name=evm_output_file_name,
        command_count=len(normalized_commands),
        partition_bundle=EvmPartitionBundleAsset(
            workspace_dir=partitioned_dir,
            partitions_dir=_workspace_file(partitioned_dir, "Partitions", "Partitioned EVM work directory"),
            partition_listing_path=_partition_listing_path(partitioned_dir),
            segment_size=int(partition_manifest["inputs"]["evm_segment_size"]),
            overlap_size=int(partition_manifest["inputs"]["evm_overlap_size"]),
        ),
        notes=(
            "Commands are preserved in file order and normalized to one non-empty shell command per line.",
        ),
    )
    manifest = {
        "stage": "evm_write_commands",
        "assumptions": [
            "The notes describe a command-generation step after partitioning; this task preserves that boundary explicitly.",
            "Command generation writes to stdout in the notes, so this task captures stdout deterministically into commands.list.",
        ],
        "inputs": {
            "partitioned_evm_inputs": str(partitioned_dir),
            "evm_write_commands_script": evm_write_commands_script,
            "evm_output_file_name": evm_output_file_name,
            "evm_sif": evm_sif,
        },
        "source_stage_manifest": partition_manifest,
        "command_count": len(normalized_commands),
        "outputs": {
            "commands_path": str(commands_path),
        },
        "assets": _as_json_compatible({"evm_command_set": asdict(command_asset)}),
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@consensus_evm_env.task
def evm_execute_commands(
    evm_commands: Dir,
    evm_sif: str = "",
) -> Dir:
    """Execute the generated EVM partition commands sequentially in deterministic order.

    Args:
        evm_commands: A value used by the helper.
        evm_sif: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    commands_dir = require_path(Path(evm_commands.download_sync()), "EVM commands directory")
    commands_manifest = _manifest_from_dir(commands_dir, "EVM commands")

    out_dir = project_mkdtemp("evm_execute_") / "evm_executed"
    _copy_tree(commands_dir, out_dir)

    normalized_commands = _command_lines(_commands_path(out_dir))
    if not normalized_commands:
        raise ValueError("evm_execute_commands requires at least one generated EVM command.")

    logs_dir = out_dir / "execution_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    executed_commands: list[dict[str, Any]] = []
    for index, command_line in enumerate(normalized_commands, start=1):
        stdout_path = logs_dir / f"command_{index:04d}.stdout.txt"
        run_tool(
            ["bash", "-lc", command_line],
            evm_sif,
            [out_dir],
            cwd=out_dir,
            stdout_path=stdout_path,
        )
        executed_commands.append(
            {
                "index": index,
                "command": command_line,
                "argv_preview": shlex.split(command_line),
                "stdout_path": str(stdout_path),
            }
        )

    manifest = {
        "stage": "evm_execute_commands",
        "assumptions": [
            "The notes describe HPC submission scripts, but this local-first milestone executes generated EVM commands sequentially in deterministic order instead of submitting jobs through sbatch.",
            "Each command is run through `bash -lc` because EVM command generation emits shell commands rather than structured argv records.",
        ],
        "inputs": {
            "evm_commands": str(commands_dir),
            "evm_sif": evm_sif,
        },
        "source_stage_manifest": commands_manifest,
        "executed_commands": executed_commands,
        "outputs": {
            "execution_logs_dir": str(logs_dir),
            "commands_path": str(_commands_path(out_dir)),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@consensus_evm_env.task
def evm_recombine_outputs(
    executed_evm_commands: Dir,
    evm_recombine_script: str = "recombine_EVM_partial_outputs.pl",
    evm_convert_script: str = "convert_EVM_outputs_to_GFF3.pl",
    gff3sort_script: str = "gff3sort.pl",
    evm_output_file_name: str = "evm.out",
    evm_sif: str = "",
) -> Dir:
    """Recombine partitioned EVM outputs and convert them into a final sorted GFF3.

    Args:
        executed_evm_commands: A value used by the helper.
        evm_recombine_script: A value used by the helper.
        evm_convert_script: A value used by the helper.
        gff3sort_script: A value used by the helper.
        evm_output_file_name: A value used by the helper.
        evm_sif: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    executed_dir = require_path(
        Path(executed_evm_commands.download_sync()),
        "Executed EVM command directory",
    )
    execution_manifest = _manifest_from_dir(executed_dir, "Executed EVM commands")

    out_dir = project_mkdtemp("evm_recombine_") / "evm_recombined"
    _copy_tree(executed_dir, out_dir)

    run_tool(
        [
            "perl",
            evm_recombine_script,
            "--partitions",
            "partitions_list.out",
            "--output_file_name",
            evm_output_file_name,
        ],
        evm_sif,
        [out_dir],
        cwd=out_dir,
    )
    run_tool(
        [
            "perl",
            evm_convert_script,
            "--partitions",
            "partitions_list.out",
            "--output",
            evm_output_file_name,
            "--genome",
            "genome.fa",
        ],
        evm_sif,
        [out_dir],
        cwd=out_dir,
    )

    partition_gff3_paths = _recombined_gff3_paths(out_dir, evm_output_file_name)
    concatenated_gff3 = _write_concatenated_gff3(partition_gff3_paths, out_dir / "EVM.all.gff3")
    blank_lines_removed_gff3 = _write_blank_line_filtered_gff3(
        concatenated_gff3,
        out_dir / "EVM.all.removed.gff3",
    )
    sorted_gff3 = out_dir / "EVM.all.sort.gff3"
    if gff3sort_script.strip():
        run_tool(
            [
                "perl",
                gff3sort_script,
                "--chr_order",
                "natural",
                "--precise",
                str(blank_lines_removed_gff3),
            ],
            evm_sif,
            [out_dir],
            cwd=out_dir,
            stdout_path=sorted_gff3,
        )
    else:
        shutil.copy2(blank_lines_removed_gff3, sorted_gff3)

    manifest = {
        "stage": "evm_recombine_outputs",
        "assumptions": [
            "Recombination and GFF3 conversion follow the note-described EVM utilities directly.",
            "If gff3sort_script is empty, this task copies EVM.all.removed.gff3 to EVM.all.sort.gff3 and records that sorting was skipped explicitly.",
        ],
        "inputs": {
            "executed_evm_commands": str(executed_dir),
            "evm_recombine_script": evm_recombine_script,
            "evm_convert_script": evm_convert_script,
            "gff3sort_script": gff3sort_script,
            "evm_output_file_name": evm_output_file_name,
            "evm_sif": evm_sif,
        },
        "source_stage_manifest": execution_manifest,
        "converted_partition_gff3s": [str(path) for path in partition_gff3_paths],
        "outputs": {
            "concatenated_gff3": str(concatenated_gff3),
            "blank_lines_removed_gff3": str(blank_lines_removed_gff3),
            "sorted_gff3": str(sorted_gff3),
        },
        "sorting_applied": bool(gff3sort_script.strip()),
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@consensus_evm_env.task
def collect_evm_results(
    evm_prep_results: Dir,
    evm_execution_inputs: Dir,
    partitioned_evm_inputs: Dir,
    evm_commands: Dir,
    executed_evm_commands: Dir,
    recombined_evm_outputs: Dir,
) -> Dir:
    """Collect the full EVM result hierarchy into a single manifest-bearing bundle.

    Args:
        evm_prep_results: A directory path used by the helper.
        evm_execution_inputs: A value used by the helper.
        partitioned_evm_inputs: A value used by the helper.
        evm_commands: A value used by the helper.
        executed_evm_commands: A value used by the helper.
        recombined_evm_outputs: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    prep_results_dir = require_path(Path(evm_prep_results.download_sync()), "Pre-EVM results directory")
    execution_inputs_dir = require_path(
        Path(evm_execution_inputs.download_sync()),
        "EVM execution input directory",
    )
    partitioned_dir = require_path(
        Path(partitioned_evm_inputs.download_sync()),
        "Partitioned EVM directory",
    )
    commands_dir = require_path(Path(evm_commands.download_sync()), "EVM commands directory")
    executed_dir = require_path(
        Path(executed_evm_commands.download_sync()),
        "Executed EVM directory",
    )
    recombined_dir = require_path(
        Path(recombined_evm_outputs.download_sync()),
        "Recombined EVM directory",
    )

    execution_manifest = _manifest_from_dir(execution_inputs_dir, "EVM execution inputs")
    partition_manifest = _manifest_from_dir(partitioned_dir, "Partitioned EVM inputs")
    commands_manifest = _manifest_from_dir(commands_dir, "EVM commands")
    executed_manifest = _manifest_from_dir(executed_dir, "Executed EVM commands")
    recombined_manifest = _manifest_from_dir(recombined_dir, "Recombined EVM outputs")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{CONSENSUS_EVM_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_prep_dir = _copy_tree(prep_results_dir, out_dir / "pre_evm_bundle")
    copied_execution_dir = _copy_tree(execution_inputs_dir, out_dir / "evm_execution_inputs")
    copied_partition_dir = _copy_tree(partitioned_dir, out_dir / "evm_partitioned")
    copied_command_dir = _copy_tree(commands_dir, out_dir / "evm_commands")
    copied_executed_dir = _copy_tree(executed_dir, out_dir / "evm_executed")
    copied_recombined_dir = _copy_tree(recombined_dir, out_dir / "evm_recombined")

    weights_path = _copy_file(
        _workspace_file(copied_execution_dir, "evm.weights", "Collected EVM weights file"),
        out_dir / "evm.weights",
    )
    partition_listing = _copy_file(
        _partition_listing_path(copied_partition_dir),
        out_dir / "partitions_list.out",
    )
    commands_path = _copy_file(_commands_path(copied_command_dir), out_dir / "commands.list")
    concatenated_gff3 = _copy_file(
        _workspace_file(copied_recombined_dir, "EVM.all.gff3", "Collected concatenated EVM GFF3"),
        out_dir / "EVM.all.gff3",
    )
    blank_lines_removed_gff3 = _copy_file(
        _workspace_file(
            copied_recombined_dir,
            "EVM.all.removed.gff3",
            "Collected blank-line-filtered EVM GFF3",
        ),
        out_dir / "EVM.all.removed.gff3",
    )
    sorted_gff3 = _copy_file(
        _workspace_file(copied_recombined_dir, "EVM.all.sort.gff3", "Collected sorted EVM GFF3"),
        out_dir / "EVM.all.sort.gff3",
    )

    execution_asset = EvmExecutionInputBundleAsset(
        workspace_dir=copied_execution_dir,
        reference_genome_fasta_path=_workspace_file(
            copied_execution_dir,
            "genome.fa",
            "Collected execution genome FASTA",
        ),
        transcripts_gff3_path=_workspace_file(
            copied_execution_dir,
            "transcripts.gff3",
            "Collected execution transcripts.gff3",
        ),
        predictions_gff3_path=_workspace_file(
            copied_execution_dir,
            "predictions.gff3",
            "Collected execution predictions.gff3",
        ),
        proteins_gff3_path=_workspace_file(
            copied_execution_dir,
            "proteins.gff3",
            "Collected execution proteins.gff3",
        ),
        weights_path=_workspace_file(copied_execution_dir, "evm.weights", "Collected execution weights"),
        source_pre_evm_results_dir=prep_results_dir,
        notes=(
            "The EVM workflow consumed the existing pre-EVM bundle directly.",
        ),
    )
    partition_asset = EvmPartitionBundleAsset(
        workspace_dir=copied_partition_dir,
        partitions_dir=_workspace_file(copied_partition_dir, "Partitions", "Collected partition directory"),
        partition_listing_path=_partition_listing_path(copied_partition_dir),
        segment_size=int(partition_manifest["inputs"]["evm_segment_size"]),
        overlap_size=int(partition_manifest["inputs"]["evm_overlap_size"]),
        execution_input_bundle=execution_asset,
        notes=(
            "Partitioning remains explicit in the final EVM results bundle for reviewability.",
        ),
    )
    command_asset = EvmCommandSetAsset(
        workspace_dir=copied_command_dir,
        commands_path=_commands_path(copied_command_dir),
        output_file_name=str(commands_manifest["inputs"]["evm_output_file_name"]),
        command_count=int(commands_manifest["command_count"]),
        partition_bundle=partition_asset,
        notes=(
            "The recorded commands are the exact sequential shell commands executed in this local-first milestone.",
        ),
    )
    result_bundle = EvmConsensusResultBundle(
        result_dir=out_dir,
        pre_evm_bundle_dir=copied_prep_dir,
        execution_input_dir=copied_execution_dir,
        partition_dir=copied_partition_dir,
        command_dir=copied_command_dir,
        execution_dir=copied_executed_dir,
        recombined_dir=copied_recombined_dir,
        weights_path=weights_path,
        partition_listing_path=partition_listing,
        commands_path=commands_path,
        concatenated_gff3_path=concatenated_gff3,
        blank_lines_removed_gff3_path=blank_lines_removed_gff3,
        sorted_gff3_path=sorted_gff3,
        manifest_path=out_dir / "run_manifest.json",
        execution_input_bundle=execution_asset,
        partition_bundle=partition_asset,
        command_set=command_asset,
        notes=(
            "This bundle stops at deterministic EVM execution and does not proceed into PASA update rounds or later post-EVM stages.",
        ),
    )

    manifest = {
        "workflow": CONSENSUS_EVM_WORKFLOW_NAME,
        "assumptions": [
            "This Milestone 2 workflow consumes the existing pre-EVM contract bundle instead of re-deriving upstream evidence.",
            "When evm_weights_text is not provided, evm.weights is an inferred adaptation of the note example to the staged per-channel source fields present in this repo.",
            "The notes describe HPC submission scripts for per-partition execution, but this milestone runs the generated commands sequentially and locally for deterministic reviewable behavior.",
            "This milestone stops after EVM recombination and final GFF3 sorting; PASA update rounds, repeat filtering, BUSCO, EggNOG, AGAT, and table2asn remain deferred.",
        ],
        "source_bundle": {
            "evm_prep_results": str(prep_results_dir),
        },
        "copied_stage_dirs": {
            "pre_evm_bundle": str(copied_prep_dir),
            "evm_execution_inputs": str(copied_execution_dir),
            "evm_partitioned": str(copied_partition_dir),
            "evm_commands": str(copied_command_dir),
            "evm_executed": str(copied_executed_dir),
            "evm_recombined": str(copied_recombined_dir),
        },
        "stage_manifests": {
            "evm_execution_inputs": execution_manifest,
            "evm_partitioned": partition_manifest,
            "evm_commands": commands_manifest,
            "evm_executed": executed_manifest,
            "evm_recombined": recombined_manifest,
        },
        "outputs": {
            "weights_path": str(weights_path),
            "partition_listing": str(partition_listing),
            "commands_path": str(commands_path),
            "concatenated_gff3": str(concatenated_gff3),
            "blank_lines_removed_gff3": str(blank_lines_removed_gff3),
            "sorted_gff3": str(sorted_gff3),
        },
        "assets": _as_json_compatible({"evm_consensus_result_bundle": asdict(result_bundle)}),
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


__all__ = [
    "collect_evm_results",
    "collect_evm_prep_results",
    "evm_execute_commands",
    "evm_partition_inputs",
    "evm_recombine_outputs",
    "evm_write_commands",
    "prepare_evm_execution_inputs",
    "prepare_evm_prediction_inputs",
    "prepare_evm_protein_inputs",
    "prepare_evm_transcript_inputs",
]
