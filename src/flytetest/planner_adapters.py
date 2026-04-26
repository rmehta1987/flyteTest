"""Adapters from current assets and manifests into planner-facing biology types.

This module maps the current asset layer and manifest-bearing result bundles
into planner-facing types without changing runnable Flyte task signatures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flytetest.planner_types import (
    AnnotationEvidenceSet,
    ConsensusAnnotation,
    ProteinEvidenceSet,
    QualityAssessmentTarget,
    ReadSet,
    ReferenceGenome,
    TranscriptEvidenceSet,
)
from flytetest.types.assets import (
    AbInitioResultBundle,
    Braker3ResultBundle,
    EvmConsensusResultBundle,
    EvmInputPreparationBundle,
    ProteinEvidenceResultBundle,
    ReadPair,
)
from flytetest.planner_types import ReferenceGenome as AssetReferenceGenome


def _manifest_data(source: Path | Mapping[str, Any]) -> tuple[dict[str, Any], Path | None]:
    """Load one manifest payload and preserve its on-disk location when available.

    Args:
        source: A manifest file path or an already-loaded mapping.

    Returns:
        Parsed manifest data and the source path when the manifest came from disk.
    """
    if isinstance(source, Path):
        return json.loads(source.read_text()), source
    return dict(source), None


def _result_dir_from_manifest(manifest: Mapping[str, Any], manifest_path: Path | None) -> Path | None:
    """Infer the result directory that owns a manifest when one can be traced.

    Args:
        manifest: Loaded manifest content, which may carry a nested source bundle reference.
        manifest_path: The manifest file path when the payload came from disk.

    Returns:
        Directory containing the manifest, or a nested result path when only that is recorded.
    """
    if manifest_path is not None:
        return manifest_path.parent
    source_bundle = manifest.get("source_bundle")
    if isinstance(source_bundle, Mapping):
        repeat_filter_results = source_bundle.get("repeat_filter_results")
        if isinstance(repeat_filter_results, str):
            return Path(repeat_filter_results)
    return None


def _path_or_none(value: Any) -> Path | None:
    """Convert an optional manifest value into a `Path` when one is present."""
    if value in (None, ""):
        return None
    return Path(str(value))


def _paths(value: Any) -> tuple[Path, ...]:
    """Convert a manifest list into a stable tuple of `Path` values."""
    if not isinstance(value, list):
        return ()
    return tuple(Path(str(item)) for item in value)


def _string_tuple(value: Any) -> tuple[str, ...]:
    """Convert a manifest list into a trimmed tuple of strings."""
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _asset_entry(
    assets: Mapping[str, Any],
    primary_key: str,
    *legacy_keys: str,
) -> Mapping[str, Any] | None:
    """Return one manifest asset payload, preferring the generic key first.

    Args:
        assets: Manifest asset mapping that may contain several naming variants.
        primary_key: The preferred asset key for current manifests.
        legacy_keys: Older asset keys to check if the preferred key is absent.

    Returns:
        The first mapping payload found for the requested asset, or ``None``.
    """
    for key in (primary_key, *legacy_keys):
        value = assets.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def reference_genome_from_asset(
    asset: AssetReferenceGenome,
    *,
    source_result_dir: Path | None = None,
    source_manifest_path: Path | None = None,
    notes: tuple[str, ...] = (),
) -> ReferenceGenome:
    """Lift a lower-level genome asset into the planner-facing type.

    Args:
        asset: Genome asset carrying the FASTA path and any biological metadata already known.
        source_result_dir: Origin bundle directory to preserve in the planner-facing object.
        source_manifest_path: Manifest path to preserve for replay and provenance checks.
        notes: Additional planner notes to append to any notes already present on the asset.

    Returns:
        Planner-facing reference genome that still points back to its source bundle.
    """
    asset_notes = getattr(asset, "notes", ())
    return ReferenceGenome(
        fasta_path=asset.fasta_path,
        organism_name=asset.organism_name,
        assembly_name=asset.assembly_name,
        taxonomy_id=asset.taxonomy_id,
        softmasked_fasta_path=asset.softmasked_fasta_path,
        annotation_gff3_path=asset.annotation_gff3_path,
        source_result_dir=source_result_dir,
        source_manifest_path=source_manifest_path,
        notes=tuple(asset_notes) + notes,
    )


def read_set_from_asset(
    asset: ReadPair,
    *,
    source_result_dir: Path | None = None,
    source_manifest_path: Path | None = None,
    notes: tuple[str, ...] = (),
) -> ReadSet:
    """Lift a paired-read asset into the planner-facing read-set type.

    Args:
        asset: Paired-end read asset with sample metadata and the read file paths.
        source_result_dir: Origin bundle directory to preserve for replayable planning.
        source_manifest_path: Manifest path to preserve for provenance and input recovery.
        notes: Additional planner notes to attach to the read set.

    Returns:
        Planner-facing read set that keeps the source bundle reference intact.
    """
    return ReadSet(
        sample_id=asset.sample_id,
        left_reads_path=asset.left_reads_path,
        right_reads_path=asset.right_reads_path,
        platform=asset.platform,
        strandedness=asset.strandedness,
        condition=asset.condition,
        replicate_label=asset.replicate_label,
        source_result_dir=source_result_dir,
        source_manifest_path=source_manifest_path,
        notes=notes,
    )


def _reference_from_manifest(
    manifest: Mapping[str, Any],
    *,
    result_dir: Path | None,
    manifest_path: Path | None,
    annotation_gff3_path: Path | None = None,
) -> ReferenceGenome:
    """Resolve a planner-facing reference genome from the current manifest layouts.

    Args:
        manifest: Loaded manifest data that may contain several reference genome layouts.
        result_dir: Result directory to preserve on the returned planner object.
        manifest_path: Manifest path to preserve on the returned planner object.
        annotation_gff3_path: Optional annotation path to bind when the manifest is missing one.

    Returns:
        Planner-facing reference genome assembled from the manifest's current conventions.
    """
    assets = manifest.get("assets", {})
    if isinstance(assets, Mapping):
        reference_asset = assets.get("reference_genome")
        if isinstance(reference_asset, Mapping):
            payload = dict(reference_asset)
            payload["source_result_dir"] = str(result_dir) if result_dir is not None else None
            payload["source_manifest_path"] = str(manifest_path) if manifest_path is not None else None
            payload["annotation_gff3_path"] = (
                str(annotation_gff3_path)
                if annotation_gff3_path is not None
                else payload.get("annotation_gff3_path")
            )
            return ReferenceGenome.from_dict(payload)

        evm_bundle = assets.get("evm_input_preparation_bundle")
        if isinstance(evm_bundle, Mapping):
            return ReferenceGenome(
                fasta_path=Path(str(evm_bundle["reference_genome_fasta_path"])),
                annotation_gff3_path=annotation_gff3_path,
                source_result_dir=result_dir,
                source_manifest_path=manifest_path,
            )

        consensus_bundle = assets.get("evm_consensus_result_bundle")
        if isinstance(consensus_bundle, Mapping):
            execution_bundle = consensus_bundle.get("execution_input_bundle")
            if isinstance(execution_bundle, Mapping):
                return ReferenceGenome(
                    fasta_path=Path(str(execution_bundle["reference_genome_fasta_path"])),
                    annotation_gff3_path=annotation_gff3_path,
                    source_result_dir=result_dir,
                    source_manifest_path=manifest_path,
                )

    outputs = manifest.get("outputs", {})
    if isinstance(outputs, Mapping):
        for key in ("reference_genome_fasta", "reference_genome"):
            if outputs.get(key):
                return ReferenceGenome(
                    fasta_path=Path(str(outputs[key])),
                    annotation_gff3_path=annotation_gff3_path,
                    source_result_dir=result_dir,
                    source_manifest_path=manifest_path,
                )

    inputs = manifest.get("inputs", {})
    if isinstance(inputs, Mapping) and inputs.get("reference_genome"):
        return ReferenceGenome(
            fasta_path=Path(str(inputs["reference_genome"])),
            annotation_gff3_path=annotation_gff3_path,
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
        )

    pre_evm_contract = manifest.get("pre_evm_contract", {})
    if isinstance(pre_evm_contract, Mapping):
        reference_entry = pre_evm_contract.get("reference_genome_fasta")
        if isinstance(reference_entry, Mapping) and reference_entry.get("path"):
            return ReferenceGenome(
                fasta_path=Path(str(reference_entry["path"])),
                annotation_gff3_path=annotation_gff3_path,
                source_result_dir=result_dir,
                source_manifest_path=manifest_path,
            )

    raise ValueError("Could not resolve a reference genome from the provided manifest.")


def reference_genome_from_manifest(source: Path | Mapping[str, Any]) -> ReferenceGenome:
    """Adapt a manifest into a planner-facing reference genome.

    Args:
        source: Manifest file path or loaded manifest mapping.

    Returns:
        Reference genome resolved from the manifest's current storage layout.
    """
    manifest, manifest_path = _manifest_data(source)
    result_dir = _result_dir_from_manifest(manifest, manifest_path)
    return _reference_from_manifest(manifest, result_dir=result_dir, manifest_path=manifest_path)


def transcript_evidence_from_manifest(source: Path | Mapping[str, Any]) -> TranscriptEvidenceSet:
    """Adapt a transcript-evidence manifest into the planner contract.

    Args:
        source: Transcript-evidence manifest file path or loaded mapping.

    Returns:
        Transcript evidence carrying source references and stage outputs from the manifest.
    """
    manifest, manifest_path = _manifest_data(source)
    result_dir = _result_dir_from_manifest(manifest, manifest_path)
    outputs = manifest.get("outputs", {})
    assets = manifest.get("assets", {})

    reference_genome = _reference_from_manifest(manifest, result_dir=result_dir, manifest_path=manifest_path)
    read_sets: tuple[ReadSet, ...] = ()
    if isinstance(assets, Mapping):
        read_pair = assets.get("read_pair")
        if isinstance(read_pair, Mapping):
            read_sets = (
                ReadSet.from_dict(
                    {
                        **dict(read_pair),
                        "source_result_dir": str(result_dir) if result_dir is not None else None,
                        "source_manifest_path": str(manifest_path) if manifest_path is not None else None,
                    }
                ),
            )

    notes = []
    notes_alignment = manifest.get("notes_alignment", {})
    if isinstance(notes_alignment, Mapping) and notes_alignment.get("reason"):
        notes.append(str(notes_alignment["reason"]))
    notes.extend(_string_tuple(manifest.get("assumptions", [])))

    return TranscriptEvidenceSet(
        reference_genome=reference_genome,
        read_sets=read_sets,
        de_novo_transcripts_path=_path_or_none(outputs.get("trinity_denovo_fasta")),
        genome_guided_transcripts_path=_path_or_none(outputs.get("trinity_gg_fasta")),
        stringtie_gtf_path=_path_or_none(outputs.get("stringtie_gtf")),
        merged_bam_path=_path_or_none(outputs.get("merged_bam")),
        source_result_dir=result_dir,
        source_manifest_path=manifest_path,
        notes=tuple(notes),
    )


def protein_evidence_from_bundle(bundle: ProteinEvidenceResultBundle) -> ProteinEvidenceSet:
    """Adapt a protein-evidence bundle into the planner contract.

    Args:
        bundle: Protein-evidence result bundle with staged protein and EVM-ready outputs.

    Returns:
        Planner-facing protein evidence that still refers back to the result bundle.
    """
    reference_genome = (
        reference_genome_from_asset(bundle.reference_genome, source_result_dir=bundle.result_dir)
        if bundle.reference_genome is not None
        else None
    )
    source_fastas = bundle.staged_dataset.source_fasta_paths if bundle.staged_dataset is not None else ()
    return ProteinEvidenceSet(
        reference_genome=reference_genome,
        source_protein_fastas=source_fastas,
        evm_ready_gff3_path=bundle.concatenated_evm_gff3_path,
        raw_alignment_path=bundle.concatenated_raw_output_path,
        source_result_dir=bundle.result_dir,
        notes=tuple(bundle.notes),
    )


def protein_evidence_from_manifest(source: Path | Mapping[str, Any]) -> ProteinEvidenceSet:
    """Adapt a protein-evidence manifest into the planner contract.

    Args:
        source: Protein-evidence manifest file path or loaded mapping.

    Returns:
        Planner-facing protein evidence assembled from the manifest layout.
    """
    manifest, manifest_path = _manifest_data(source)
    result_dir = _result_dir_from_manifest(manifest, manifest_path)
    outputs = manifest.get("outputs", {})
    assets = manifest.get("assets", {})

    reference_genome = _reference_from_manifest(manifest, result_dir=result_dir, manifest_path=manifest_path)
    source_fastas: tuple[Path, ...] = ()
    if isinstance(assets, Mapping):
        dataset = assets.get("protein_reference_dataset")
        if isinstance(dataset, Mapping):
            source_fastas = _paths(dataset.get("source_fasta_paths"))

    notes = list(_string_tuple(manifest.get("assumptions", [])))
    chunking = manifest.get("chunking", {})
    if isinstance(chunking, Mapping) and chunking.get("proteins_per_chunk") is not None:
        notes.append(f"Current chunk size: {chunking['proteins_per_chunk']} proteins.")

    return ProteinEvidenceSet(
        reference_genome=reference_genome,
        source_protein_fastas=source_fastas,
        evm_ready_gff3_path=_path_or_none(outputs.get("concatenated_evm_protein_gff3")),
        raw_alignment_path=_path_or_none(outputs.get("concatenated_raw_exonerate")),
        source_result_dir=result_dir,
        source_manifest_path=manifest_path,
        notes=tuple(notes),
    )


def annotation_evidence_from_ab_initio_bundle(bundle: AbInitioResultBundle | Braker3ResultBundle) -> AnnotationEvidenceSet:
    """Adapt an ab initio bundle into planner-facing annotation evidence.

    Args:
        bundle: BRAKER3-style result bundle carrying reference genome and normalized predictions.

    Returns:
        Annotation evidence that keeps the source bundle and provenance notes intact.
    """
    if bundle.reference_genome is None:
        raise ValueError("AbInitioResultBundle must include a reference genome for planner adaptation.")
    provenance_notes: tuple[str, ...] = ()
    if getattr(bundle, "provenance", None) is not None:
        provenance_notes = (
            f"Ab initio evidence adapted from {bundle.provenance.tool_name} at {bundle.provenance.tool_stage}.",
        )
    return AnnotationEvidenceSet(
        reference_genome=reference_genome_from_asset(bundle.reference_genome, source_result_dir=bundle.result_dir),
        ab_initio_predictions_gff3_path=bundle.normalized_gff3_path,
        source_result_dir=bundle.result_dir,
        notes=provenance_notes + tuple(bundle.notes),
    )


def annotation_evidence_from_braker_bundle(bundle: Braker3ResultBundle) -> AnnotationEvidenceSet:
    """Adapt the legacy BRAKER3 bundle into planner-facing annotation evidence.

    Args:
        bundle: BRAKER3 result bundle with the same contract used by current ab initio planning.

    Returns:
        Annotation evidence adapted from the BRAKER3-specific wrapper.
    """
    return annotation_evidence_from_ab_initio_bundle(bundle)


def annotation_evidence_from_evm_prep_bundle(bundle: EvmInputPreparationBundle) -> AnnotationEvidenceSet:
    """Adapt a pre-EVM bundle into planner-facing annotation evidence.

    Args:
        bundle: Pre-EVM bundle containing transcript, protein, and prediction evidence.

    Returns:
        Annotation evidence assembled from the explicit pre-EVM contract bundle.
    """
    reference_genome = ReferenceGenome(
        fasta_path=bundle.reference_genome_fasta_path,
        source_result_dir=bundle.result_dir,
        source_manifest_path=bundle.manifest_path,
    )
    transcript_evidence = TranscriptEvidenceSet(
        reference_genome=reference_genome,
        pasa_assemblies_gff3_path=bundle.transcripts_gff3_path,
        source_result_dir=bundle.transcript_bundle.source_results_dir if bundle.transcript_bundle else None,
        notes=tuple(bundle.transcript_bundle.notes) if bundle.transcript_bundle else (),
    )
    protein_evidence = ProteinEvidenceSet(
        reference_genome=reference_genome,
        evm_ready_gff3_path=bundle.proteins_gff3_path,
        source_result_dir=bundle.protein_bundle.source_results_dir if bundle.protein_bundle else None,
        notes=tuple(bundle.protein_bundle.notes) if bundle.protein_bundle else (),
    )
    return AnnotationEvidenceSet(
        reference_genome=reference_genome,
        transcript_evidence=transcript_evidence,
        protein_evidence=protein_evidence,
        transcript_alignments_gff3_path=bundle.transcripts_gff3_path,
        protein_alignments_gff3_path=bundle.proteins_gff3_path,
        ab_initio_predictions_gff3_path=(
            bundle.prediction_bundle.braker_gff3_path if bundle.prediction_bundle is not None else None
        ),
        combined_predictions_gff3_path=bundle.predictions_gff3_path,
        source_result_dir=bundle.result_dir,
        source_manifest_path=bundle.manifest_path,
        notes=tuple(bundle.notes),
    )


def annotation_evidence_from_manifest(source: Path | Mapping[str, Any]) -> AnnotationEvidenceSet:
    """Adapt BRAKER3 or pre-EVM manifests into planner-facing annotation evidence.

    Args:
        source: Manifest file path or loaded mapping for the relevant annotation stage.

    Returns:
        Annotation evidence resolved from the manifest's current workflow boundary.
    """
    manifest, manifest_path = _manifest_data(source)
    result_dir = _result_dir_from_manifest(manifest, manifest_path)
    workflow = str(manifest.get("workflow", ""))
    outputs = manifest.get("outputs", {})
    assets = manifest.get("assets", {})

    if workflow == "ab_initio_annotation_braker3":
        reference_genome = _reference_from_manifest(manifest, result_dir=result_dir, manifest_path=manifest_path)
        provenance_notes = ()
        if isinstance(assets, Mapping):
            ab_initio_bundle = _asset_entry(assets, "ab_initio_result_bundle", "braker3_result_bundle")
            if ab_initio_bundle is not None:
                provenance = ab_initio_bundle.get("provenance")
                if isinstance(provenance, Mapping) and provenance.get("tool_name"):
                    provenance_notes = (
                        f"Ab initio evidence adapted from {provenance['tool_name']}.",
                    )
        return AnnotationEvidenceSet(
            reference_genome=reference_genome,
            ab_initio_predictions_gff3_path=_path_or_none(outputs.get("normalized_braker_gff3")),
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
            notes=provenance_notes + _string_tuple(manifest.get("repo_policy", [])),
        )

    if workflow == "consensus_annotation_evm_prep":
        transcript_evidence = TranscriptEvidenceSet(
            reference_genome=_reference_from_manifest(manifest, result_dir=result_dir, manifest_path=manifest_path),
            pasa_assemblies_gff3_path=_path_or_none(outputs.get("transcripts_gff3")),
            source_result_dir=_path_or_none(manifest.get("source_bundles", {}).get("pasa_results")),
            source_manifest_path=manifest_path,
            notes=("This planner view is adapted from the pre-EVM transcript boundary.",),
        )
        protein_evidence = ProteinEvidenceSet(
            reference_genome=transcript_evidence.reference_genome,
            evm_ready_gff3_path=_path_or_none(outputs.get("proteins_gff3")),
            source_result_dir=_path_or_none(manifest.get("source_bundles", {}).get("protein_evidence_results")),
            source_manifest_path=manifest_path,
            notes=("This planner view is adapted from the pre-EVM protein boundary.",),
        )
        reference_genome = _reference_from_manifest(manifest, result_dir=result_dir, manifest_path=manifest_path)
        ab_initio_path = None
        if isinstance(assets, Mapping):
            bundle = assets.get("evm_input_preparation_bundle")
            if isinstance(bundle, Mapping):
                prediction_bundle = bundle.get("prediction_bundle")
                if isinstance(prediction_bundle, Mapping):
                    ab_initio_path = _path_or_none(prediction_bundle.get("braker_gff3_path"))
        return AnnotationEvidenceSet(
            reference_genome=reference_genome,
            transcript_evidence=transcript_evidence,
            protein_evidence=protein_evidence,
            transcript_alignments_gff3_path=_path_or_none(outputs.get("transcripts_gff3")),
            protein_alignments_gff3_path=_path_or_none(outputs.get("proteins_gff3")),
            ab_initio_predictions_gff3_path=ab_initio_path,
            combined_predictions_gff3_path=_path_or_none(outputs.get("predictions_gff3")),
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
            notes=_string_tuple(manifest.get("notes_backed_behavior", []))
            + _string_tuple(manifest.get("repo_policy", [])),
        )

    raise ValueError(f"Unsupported manifest workflow for annotation evidence adaptation: {workflow or '<missing>'}")


def consensus_annotation_from_bundle(bundle: EvmConsensusResultBundle) -> ConsensusAnnotation:
    """Adapt an EVM consensus bundle into a planner-facing annotation.

    Args:
        bundle: EVM consensus result bundle with its execution-input and output paths.

    Returns:
        Consensus annotation that preserves the recorded EVM provenance.
    """
    reference_genome = ReferenceGenome(
        fasta_path=bundle.execution_input_bundle.reference_genome_fasta_path,
        source_result_dir=bundle.result_dir,
        source_manifest_path=bundle.manifest_path,
    )
    supporting_evidence = AnnotationEvidenceSet(
        reference_genome=reference_genome,
        transcript_alignments_gff3_path=bundle.execution_input_bundle.transcripts_gff3_path,
        protein_alignments_gff3_path=bundle.execution_input_bundle.proteins_gff3_path,
        combined_predictions_gff3_path=bundle.execution_input_bundle.predictions_gff3_path,
        source_result_dir=bundle.pre_evm_bundle_dir,
        notes=("Consensus annotation was adapted from the explicit EVM execution-input boundary.",),
    )
    return ConsensusAnnotation(
        reference_genome=reference_genome,
        annotation_gff3_path=bundle.sorted_gff3_path,
        weights_path=bundle.weights_path,
        supporting_evidence=supporting_evidence,
        source_result_dir=bundle.result_dir,
        source_manifest_path=bundle.manifest_path,
        notes=tuple(bundle.notes),
    )


def consensus_annotation_from_manifest(source: Path | Mapping[str, Any]) -> ConsensusAnnotation:
    """Adapt EVM or repeat-filter manifests into a planner-facing consensus annotation.

    Args:
        source: Manifest file path or loaded mapping for EVM or repeat-filter outputs.

    Returns:
        Consensus annotation resolved from the manifest's reported workflow.
    """
    manifest, manifest_path = _manifest_data(source)
    result_dir = _result_dir_from_manifest(manifest, manifest_path)
    workflow = str(manifest.get("workflow", ""))
    outputs = manifest.get("outputs", {})

    if workflow == "consensus_annotation_evm":
        annotation_path = _path_or_none(outputs.get("sorted_gff3"))
        reference_genome = _reference_from_manifest(
            manifest,
            result_dir=result_dir,
            manifest_path=manifest_path,
            annotation_gff3_path=annotation_path,
        )
        stage_manifests = manifest.get("stage_manifests", {})
        supporting_evidence = None
        if isinstance(stage_manifests, Mapping):
            execution_manifest = stage_manifests.get("evm_execution_inputs")
            if isinstance(execution_manifest, Mapping):
                supporting_evidence = AnnotationEvidenceSet(
                    reference_genome=reference_genome,
                    transcript_alignments_gff3_path=_path_or_none(execution_manifest.get("outputs", {}).get("transcripts_gff3")),
                    protein_alignments_gff3_path=_path_or_none(execution_manifest.get("outputs", {}).get("proteins_gff3")),
                    combined_predictions_gff3_path=_path_or_none(
                        execution_manifest.get("outputs", {}).get("predictions_gff3")
                    ),
                    source_result_dir=_path_or_none(manifest.get("source_bundle", {}).get("evm_prep_results")),
                    source_manifest_path=manifest_path,
                )
        return ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=annotation_path,
            weights_path=_path_or_none(outputs.get("weights_path")),
            supporting_evidence=supporting_evidence,
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
            notes=_string_tuple(manifest.get("assumptions", [])),
        )

    if workflow == "annotation_repeat_filtering":
        annotation_path = _path_or_none(outputs.get("all_repeats_removed_gff3"))
        protein_fasta_path = _path_or_none(outputs.get("final_proteins_fasta"))
        reference_genome = _reference_from_manifest(
            manifest,
            result_dir=result_dir,
            manifest_path=manifest_path,
            annotation_gff3_path=annotation_path,
        )
        return ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=annotation_path,
            protein_fasta_path=protein_fasta_path,
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
            notes=_string_tuple(manifest.get("assumptions", [])),
        )

    raise ValueError(f"Unsupported manifest workflow for consensus adaptation: {workflow or '<missing>'}")


def quality_assessment_target_from_manifest(source: Path | Mapping[str, Any]) -> QualityAssessmentTarget:
    """Adapt downstream manifests into a planner-facing QC target.

    Args:
        source: Manifest file path or loaded mapping for the downstream QC boundary.

    Returns:
        QC target that points to the current reviewable output boundary.
    """
    manifest, manifest_path = _manifest_data(source)
    result_dir = _result_dir_from_manifest(manifest, manifest_path)
    workflow = str(manifest.get("workflow", ""))
    outputs = manifest.get("outputs", {})

    if workflow == "annotation_repeat_filtering":
        consensus = consensus_annotation_from_manifest(manifest)
        return QualityAssessmentTarget(
            reference_genome=consensus.reference_genome,
            consensus_annotation=consensus,
            annotation_gff3_path=consensus.annotation_gff3_path,
            proteins_fasta_path=consensus.protein_fasta_path,
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
            notes=("Repeat-filtered outputs are the current QC-ready target boundary.",)
            + _string_tuple(manifest.get("assumptions", [])),
        )

    if workflow == "annotation_functional_eggnog":
        return QualityAssessmentTarget(
            annotation_gff3_path=_path_or_none(outputs.get("eggnog_annotated_gff3")),
            proteins_fasta_path=_path_or_none(outputs.get("repeat_filter_proteins_fasta")),
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
            notes=("EggNOG functional-annotation outputs remain a reviewable downstream target boundary.",)
            + _string_tuple(manifest.get("assumptions", [])),
        )

    if workflow == "annotation_qc_busco":
        source_bundle = manifest.get("source_bundle", {})
        repeat_filter_results = None
        if isinstance(source_bundle, Mapping):
            repeat_filter_results = _path_or_none(source_bundle.get("repeat_filter_results"))
        return QualityAssessmentTarget(
            proteins_fasta_path=_path_or_none(outputs.get("final_proteins_fasta")),
            source_result_dir=repeat_filter_results or result_dir,
            source_manifest_path=manifest_path,
            notes=("BUSCO QC outputs point back to the repeat-filtered protein boundary for EggNOG.",)
            + _string_tuple(manifest.get("assumptions", [])),
        )

    if workflow == "annotation_postprocess_agat_conversion":
        return QualityAssessmentTarget(
            annotation_gff3_path=_path_or_none(outputs.get("agat_converted_gff3")),
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
            notes=("AGAT conversion outputs are the current cleanup-ready target boundary.",)
            + _string_tuple(manifest.get("assumptions", [])),
        )

    if workflow == "consensus_annotation_evm":
        consensus = consensus_annotation_from_manifest(manifest)
        return QualityAssessmentTarget(
            reference_genome=consensus.reference_genome,
            consensus_annotation=consensus,
            annotation_gff3_path=consensus.annotation_gff3_path,
            source_result_dir=result_dir,
            source_manifest_path=manifest_path,
            notes=("Consensus EVM outputs can be reviewed directly even before later cleanup stages.",)
            + _string_tuple(manifest.get("assumptions", [])),
        )

    raise ValueError(f"Unsupported manifest workflow for QC target adaptation: {workflow or '<missing>'}")


__all__ = [
    "annotation_evidence_from_ab_initio_bundle",
    "annotation_evidence_from_braker_bundle",
    "annotation_evidence_from_evm_prep_bundle",
    "annotation_evidence_from_manifest",
    "consensus_annotation_from_bundle",
    "consensus_annotation_from_manifest",
    "protein_evidence_from_bundle",
    "protein_evidence_from_manifest",
    "quality_assessment_target_from_manifest",
    "read_set_from_asset",
    "reference_genome_from_asset",
    "reference_genome_from_manifest",
    "transcript_evidence_from_manifest",
]
