"""Manifest-backed input resolution for planner-facing biology types.

This module adds the first local resolver layer for the `realtime` migration.
It can look for planner-friendly biology inputs in three places:

- explicit local bindings supplied by the caller
- prior `run_manifest.json` files
- current result-bundle objects from registered workflows

This first version is intentionally local and file-based. It does not add a
database requirement, remote search, or automatic execution.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

from flytetest.errors import (
    BindingTypeMismatchError,
    BindingPathMissingError,
    ManifestNotFoundError,
    PlannerResolutionError,
    UnknownOutputNameError,
    UnknownRunIdError,
)
from flytetest.registry import get_entry
from flytetest.planner_adapters import (
    annotation_evidence_from_ab_initio_bundle,
    annotation_evidence_from_braker_bundle,
    annotation_evidence_from_evm_prep_bundle,
    annotation_evidence_from_manifest,
    consensus_annotation_from_bundle,
    consensus_annotation_from_manifest,
    protein_evidence_from_bundle,
    protein_evidence_from_manifest,
    quality_assessment_target_from_manifest,
    reference_genome_from_manifest,
    transcript_evidence_from_manifest,
)
from flytetest.planner_types import (
    AnnotationEvidenceSet,
    ConsensusAnnotation,
    ProteinEvidenceSet,
    QualityAssessmentTarget,
    ReadSet,
    ReferenceGenome,
    TranscriptEvidenceSet,
)
from flytetest.spec_artifacts import DurableAssetRef
from flytetest.types.assets import (
    AbInitioResultBundle,
    Braker3ResultBundle,
    EvmConsensusResultBundle,
    EvmInputPreparationBundle,
    ProteinEvidenceResultBundle,
)


_LOG = logging.getLogger(__name__)


ResolverSourceKind = Literal["explicit_binding", "manifest", "result_bundle"]


@dataclass(frozen=True, slots=True)
class ResolverSource:
    """Describe where one resolved planner value came from.

    This dataclass keeps the planning or execution contract explicit and easy to review.
    """

    kind: ResolverSourceKind
    label: str
    manifest_path: Path | None = None
    workflow_name: str | None = None
    bundle_type: str | None = None


@dataclass(frozen=True, slots=True)
class ResolutionCandidate:
    """Hold one candidate planner value found by the resolver.

    This dataclass keeps the planning or execution contract explicit and easy to review.
    """

    target_type_name: str
    value: Any
    source: ResolverSource


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """Report the outcome of one resolver lookup.

    A lookup can end in one of three states:

    - resolved: exactly one clear value was found, or an explicit binding won
    - ambiguous: multiple possible values were found and the resolver refused to guess
    - missing: no usable value was found
"""

    target_type_name: str
    resolved_value: Any | None
    selected_source: ResolverSource | None
    candidate_count: int
    candidate_sources: tuple[ResolverSource, ...] = field(default_factory=tuple)
    unresolved_requirements: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_resolved(self) -> bool:
        """Return whether the resolver selected one value successfully.

        This helper keeps the relevant planning or execution step explicit and easy to review.

        Returns:
            ``True`` when the resolver chose exactly one concrete value.
        """
        return self.resolved_value is not None and self.selected_source is not None


class AssetResolver(Protocol):
    """Describe the local input-resolution behavior used by later planner work.

    This dataclass keeps the planning or execution contract explicit and easy to review.
    """

    def resolve(
        self,
        target_type_name: str,
        *,
        explicit_bindings: Mapping[str, Any] | None = None,
        manifest_sources: Sequence[Path | Mapping[str, Any]] = (),
        result_bundles: Sequence[Any] = (),
    ) -> ResolutionResult:
        """Resolve one planner-facing type from bindings, manifests, or result bundles.

        Args:
            target_type_name: The planner type name to resolve.
            explicit_bindings: Optional caller-supplied values that should win
                over discovered manifests and result bundles.
            manifest_sources: Local manifest paths or inline manifest mappings
                that may contain a serializable planner value.
            result_bundles: Result-bundle objects that can be adapted back into
                planner-facing biology types.

        Returns:
            A :class:`ResolutionResult` describing the selected value or the
            reason resolution was ambiguous or missing.
        """


_PLANNER_TYPES_BY_NAME = {
    "ReferenceGenome": ReferenceGenome,
    "ReadSet": ReadSet,
    "TranscriptEvidenceSet": TranscriptEvidenceSet,
    "ProteinEvidenceSet": ProteinEvidenceSet,
    "AnnotationEvidenceSet": AnnotationEvidenceSet,
    "ConsensusAnnotation": ConsensusAnnotation,
    "QualityAssessmentTarget": QualityAssessmentTarget,
}

_MANIFEST_ADAPTERS = {
    "ReferenceGenome": reference_genome_from_manifest,
    "TranscriptEvidenceSet": transcript_evidence_from_manifest,
    "ProteinEvidenceSet": protein_evidence_from_manifest,
    "AnnotationEvidenceSet": annotation_evidence_from_manifest,
    "ConsensusAnnotation": consensus_annotation_from_manifest,
    "QualityAssessmentTarget": quality_assessment_target_from_manifest,
}

_BUNDLE_ADAPTERS: dict[type[Any], dict[str, Any]] = {
    ProteinEvidenceResultBundle: {
        "ProteinEvidenceSet": protein_evidence_from_bundle,
    },
    AbInitioResultBundle: {
        "AnnotationEvidenceSet": annotation_evidence_from_ab_initio_bundle,
    },
    Braker3ResultBundle: {
        "AnnotationEvidenceSet": annotation_evidence_from_braker_bundle,
    },
    EvmInputPreparationBundle: {
        "AnnotationEvidenceSet": annotation_evidence_from_evm_prep_bundle,
    },
    EvmConsensusResultBundle: {
        "ConsensusAnnotation": consensus_annotation_from_bundle,
    },
}


def _binding_context_error(exc: Exception, binding_key: str) -> Exception:
    """Prefix a typed resolver exception with the binding key context."""
    exc.args = (f"Binding {binding_key!r}: {exc}",)
    return exc


def _iter_path_values(value: Any) -> tuple[Path, ...]:
    """Collect concrete Path values from a planner dataclass recursively."""
    if isinstance(value, Path):
        return (value,)
    if is_dataclass(value):
        collected: list[Path] = []
        for field_info in fields(value):
            collected.extend(_iter_path_values(getattr(value, field_info.name)))
        return tuple(collected)
    if isinstance(value, Mapping):
        collected = []
        for item in value.values():
            collected.extend(_iter_path_values(item))
        return tuple(collected)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        collected = []
        for item in value:
            collected.extend(_iter_path_values(item))
        return tuple(collected)
    return ()


def _validate_materialized_paths(binding_key: str, value: Any) -> None:
    """Raise BindingPathMissingError when a materialized raw binding path is absent."""
    for path_value in _iter_path_values(value):
        if not path_value.exists():
            raise _binding_context_error(BindingPathMissingError(str(path_value)), binding_key)


def _materialize_raw_binding(binding_key: str, binding_value: Mapping[str, Any]) -> Any:
    """Construct one planner type directly from a raw binding mapping."""
    planner_type = _PLANNER_TYPES_BY_NAME[binding_key]
    resolved = planner_type.from_dict(dict(binding_value))
    _validate_materialized_paths(binding_key, resolved)
    return resolved


def _manifest_entry_name(manifest: Mapping[str, Any]) -> str | None:
    """Return the registry entry name recorded on a manifest when present."""
    for key in ("stage", "workflow"):
        value = manifest.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _manifest_output_type(manifest: Mapping[str, Any], output_name: str | None) -> str | None:
    """Return one explicit planner type for a manifest output when recorded."""
    if not output_name:
        return None

    for mapping_key in ("output_planner_types", "output_types"):
        mapping_value = manifest.get(mapping_key)
        if not isinstance(mapping_value, Mapping):
            continue
        planner_type = mapping_value.get(output_name)
        if isinstance(planner_type, str) and planner_type.strip():
            return planner_type.strip()

    outputs = manifest.get("outputs")
    if isinstance(outputs, Mapping):
        output_value = outputs.get(output_name)
        if isinstance(output_value, Mapping):
            for field_name in ("produced_type", "planner_type", "type_name", "type"):
                planner_type = output_value.get(field_name)
                if isinstance(planner_type, str) and planner_type.strip():
                    return planner_type.strip()
    return None


def _manifest_produced_types(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the registry-declared produced planner types for one manifest."""
    entry_name = _manifest_entry_name(manifest)
    if entry_name is None:
        return ()
    try:
        entry = get_entry(entry_name)
    except KeyError:
        return ()
    return tuple(entry.compatibility.produced_planner_types or ())


def _raise_binding_type_mismatch(binding_key: str, resolved_type: str, source: str) -> None:
    """Raise BindingTypeMismatchError with binding-key context."""
    raise _binding_context_error(
        BindingTypeMismatchError(binding_key=binding_key, resolved_type=resolved_type, source=source),
        binding_key,
    )


def _validate_manifest_binding_type(
    binding_key: str,
    manifest: Mapping[str, Any],
    *,
    manifest_path: Path,
    output_name: str | None,
) -> None:
    """Reject manifest-backed bindings whose producer type is incompatible."""
    explicit_output_type = _manifest_output_type(manifest, output_name)
    if explicit_output_type is not None:
        if explicit_output_type != binding_key:
            _raise_binding_type_mismatch(binding_key, explicit_output_type, str(manifest_path))
        return

    produced_types = _manifest_produced_types(manifest)
    if produced_types and binding_key not in produced_types:
        _raise_binding_type_mismatch(binding_key, produced_types[0], str(manifest_path))


def _validate_ref_binding_type(
    binding_key: str,
    durable_ref: DurableAssetRef,
    manifest: Mapping[str, Any],
) -> None:
    """Reject durable-ref bindings whose producer type is incompatible."""
    if durable_ref.produced_type:
        if durable_ref.produced_type != binding_key:
            _raise_binding_type_mismatch(binding_key, durable_ref.produced_type, durable_ref.run_id)
        return

    explicit_output_type = _manifest_output_type(manifest, durable_ref.output_name)
    if explicit_output_type is not None:
        if explicit_output_type != binding_key:
            _raise_binding_type_mismatch(binding_key, explicit_output_type, durable_ref.run_id)
        return

    produced_types = _manifest_produced_types(manifest)
    if produced_types and binding_key not in produced_types:
        _raise_binding_type_mismatch(binding_key, produced_types[0], durable_ref.run_id)


def _materialize_manifest_binding(binding_key: str, binding_value: Mapping[str, Any]) -> Any:
    """Construct one planner type from a manifest-backed binding form."""
    manifest_location = Path(str(binding_value["$manifest"]))
    manifest_path = manifest_location / "run_manifest.json" if manifest_location.is_dir() else manifest_location
    if not manifest_path.exists():
        raise _binding_context_error(ManifestNotFoundError(str(manifest_path)), binding_key)

    manifest = json.loads(manifest_path.read_text())
    output_name = binding_value.get("output_name")
    if isinstance(output_name, str) and output_name:
        manifest_outputs = manifest.get("outputs", {})
        if not isinstance(manifest_outputs, Mapping) or output_name not in manifest_outputs:
            raise _binding_context_error(
                UnknownOutputNameError(
                    run_id=str(manifest_path),
                    output_name=output_name,
                    known_outputs=tuple(sorted(str(key) for key in manifest_outputs))
                    if isinstance(manifest_outputs, Mapping)
                    else (),
                ),
                binding_key,
            )

    _validate_manifest_binding_type(
        binding_key,
        manifest,
        manifest_path=manifest_path,
        output_name=output_name if isinstance(output_name, str) else None,
    )

    manifest_adapter = _MANIFEST_ADAPTERS.get(binding_key)
    if manifest_adapter is None:
        raise KeyError(f"Unsupported planner type for manifest materialization: {binding_key}")
    return manifest_adapter(manifest_path)


def _materialize_ref_binding(
    binding_key: str,
    binding_value: Mapping[str, Any],
    *,
    durable_index: Sequence[DurableAssetRef],
) -> Any:
    """Resolve one durable-reference binding enough to surface typed resolver errors."""
    ref_payload = binding_value.get("$ref")
    if not isinstance(ref_payload, Mapping):
        raise ValueError(f"Binding {binding_key!r} has a malformed $ref payload.")
    run_id = str(ref_payload.get("run_id") or "")
    output_name = str(ref_payload.get("output_name") or "")

    run_refs = tuple(ref for ref in durable_index if ref.run_id == run_id)
    if not run_refs:
        available_run_ids = {ref.run_id for ref in durable_index}
        raise _binding_context_error(
            UnknownRunIdError(run_id=run_id, available_count=len(available_run_ids)),
            binding_key,
        )

    matching_ref = next((ref for ref in run_refs if ref.output_name == output_name), None)
    if matching_ref is None:
        raise _binding_context_error(
            UnknownOutputNameError(
                run_id=run_id,
                output_name=output_name,
                known_outputs=tuple(sorted(ref.output_name for ref in run_refs)),
            ),
            binding_key,
        )

    manifest_path = matching_ref.manifest_path
    if manifest_path is None or not manifest_path.exists():
        resolved_manifest_path = manifest_path or (matching_ref.asset_path / "run_manifest.json")
        raise _binding_context_error(ManifestNotFoundError(str(resolved_manifest_path)), binding_key)

    manifest = json.loads(manifest_path.read_text())
    _validate_ref_binding_type(binding_key, matching_ref, manifest)

    manifest_adapter = _MANIFEST_ADAPTERS.get(binding_key)
    if manifest_adapter is None:
        raise KeyError(f"Unsupported planner type for durable-ref materialization: {binding_key}")
    return manifest_adapter(manifest_path)


def _materialize_bindings(
    bindings: Mapping[str, Mapping[str, Any]],
    *,
    durable_index: Sequence[DurableAssetRef] = (),
) -> dict[str, Any]:
    """Materialize structured run bindings into planner dataclasses.

    Supports the raw-path form plus manifest-backed and durable-ref forms,
    including the exact-name type compatibility checks for $manifest and $ref.
    """
    materialized: dict[str, Any] = {}
    for binding_key, binding_value in bindings.items():
        if binding_key not in _PLANNER_TYPES_BY_NAME:
            raise KeyError(f"Unsupported planner type for materialization: {binding_key}")
        if not isinstance(binding_value, Mapping):
            raise TypeError(f"Binding {binding_key!r} must be a mapping payload.")

        if "$manifest" in binding_value:
            materialized[binding_key] = _materialize_manifest_binding(binding_key, binding_value)
        elif "$ref" in binding_value:
            try:
                materialized[binding_key] = _materialize_ref_binding(
                    binding_key,
                    binding_value,
                    durable_index=durable_index,
                )
            except PlannerResolutionError as exc:
                ref_payload = binding_value.get("$ref")
                if isinstance(ref_payload, Mapping):
                    ref_run_id = str(ref_payload.get("run_id") or "")
                    ref_output_name = str(ref_payload.get("output_name") or "")
                else:
                    ref_run_id = ""
                    ref_output_name = ""
                _LOG.warning(
                    "$ref binding resolution failed "
                    "(recipe_id=pending binding=%s run_id=%s output_name=%s): %s",
                    binding_key,
                    ref_run_id,
                    ref_output_name,
                    exc,
                )
                raise
        else:
            materialized[binding_key] = _materialize_raw_binding(binding_key, binding_value)
    return materialized


def _manifest_workflow_name(manifest: Mapping[str, Any]) -> str | None:
    """Return the workflow label recorded in one current manifest when present.

    Args:
        manifest: The manifest payload being inspected.

    Returns:
        The recorded workflow name, or ``None`` when the manifest does not
        include a usable workflow label.
    """
    workflow = manifest.get("workflow")
    if isinstance(workflow, str) and workflow.strip():
        return workflow
    return None


def _manifest_payload(source: Path | Mapping[str, Any]) -> tuple[dict[str, Any], Path | None]:
    """Load one manifest source from a mapping or a local path.

    Args:
        source: A manifest path or inline mapping.

    Returns:
        The parsed manifest payload and, when available, the on-disk path it
        came from.
    """
    if isinstance(source, Path):
        manifest_path = source / "run_manifest.json" if source.is_dir() else source
        return json.loads(manifest_path.read_text()), manifest_path
    return dict(source), None


def _candidate_from_explicit_binding(target_type_name: str, binding: Any) -> Any:
    """Convert one explicit binding into the requested planner type when possible.

    Args:
        target_type_name: The planner type name being resolved.
        binding: The explicit binding value supplied by the caller.

    Returns:
        The planner type instance reconstructed from the explicit binding.
    """
    planner_type = _PLANNER_TYPES_BY_NAME[target_type_name]
    if isinstance(binding, planner_type):
        return binding
    if isinstance(binding, Mapping):
        return planner_type.from_dict(binding)
    raise TypeError(
        f"Explicit binding for `{target_type_name}` must already be that type or a matching mapping payload."
    )


def _candidate_key(candidate: ResolutionCandidate) -> tuple[str, str]:
    """Return a stable key used to avoid duplicate candidates from the same source.

    Args:
        candidate: The candidate being deduplicated.

    Returns:
        A stable `(source.kind, source.label)` tuple for deduplication.
    """
    return candidate.source.kind, candidate.source.label


def _durable_ref_for_missing_source(
    source: Path | Mapping[str, Any],
    durable_index: Sequence[DurableAssetRef],
) -> DurableAssetRef | None:
    """Return the first DurableAssetRef whose paths match a missing manifest source.

    Only Path sources are matched; inline ``Mapping`` sources have no filesystem
    path to check.  The comparison tries three candidate paths in order:

    1. ``durable_ref.manifest_path == source`` — source is the manifest JSON file
       directly.
    2. ``durable_ref.asset_path == source`` — source is the asset directory.
    3. ``durable_ref.manifest_path == source / "run_manifest.json"`` — source is
       an asset directory path (even though it doesn't exist as a dir on disk, the
       original caller may have passed it intending to locate the sidecar manifest).

    Args:
        source: The manifest source that caused a FileNotFoundError during loading.
        durable_index: Sequence of DurableAssetRef entries from a prior run's index.

    Returns:
        The first matching ref, or ``None`` when no match is found.
    """
    if not isinstance(source, Path) or not durable_index:
        return None
    for ref in durable_index:
        if ref.manifest_path == source or ref.asset_path == source:
            return ref
        if ref.manifest_path == source / "run_manifest.json":
            return ref
    return None


class LocalManifestAssetResolver:
    """Resolve planner-facing types from explicit local bindings and local manifests.

    Resolution rules in this first version are intentionally simple:

    - an explicit binding wins over all discovered manifest or bundle matches
    - one discovered candidate resolves successfully
    - more than one discovered candidate is treated as ambiguous
    - no candidates produces a missing-input result
"""

    def resolve(
        self,
        target_type_name: str,
        *,
        explicit_bindings: Mapping[str, Any] | None = None,
        manifest_sources: Sequence[Path | Mapping[str, Any]] = (),
        result_bundles: Sequence[Any] = (),
        durable_index: Sequence[DurableAssetRef] = (),
    ) -> ResolutionResult:
        """Resolve one planner-facing type from local bindings, manifests, or bundles.

    Args:
        target_type_name: Planner type name currently being resolved.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        result_bundles: A directory path used by the helper.
        durable_index: Optional sequence of :class:`~flytetest.spec_artifacts.DurableAssetRef`
            entries from a prior run's ``durable_asset_index.json``.  When a manifest source
            path is missing from the filesystem, the index is searched for a matching entry
            and an explicit limitation is added to guide the caller.  Defaults to ``()``
            so all existing callers remain unaffected.

    Returns:
        A `ResolutionResult` result computed by this helper.
"""
        if target_type_name not in _PLANNER_TYPES_BY_NAME:
            return ResolutionResult(
                target_type_name=target_type_name,
                resolved_value=None,
                selected_source=None,
                candidate_count=0,
                candidate_sources=(),
                unresolved_requirements=(
                    f"No resolver registered for planner type `{target_type_name}`; "
                    f"provide an explicit binding or supply it via scalar inputs.",
                ),
                assumptions=(
                    "This first resolver is local and manifest-backed only.",
                    "Database-backed and remote-backed lookup remain out of scope in this milestone.",
                    "When more than one discovered candidate exists, the resolver refuses to guess.",
                ),
            )

        explicit_bindings = explicit_bindings or {}
        candidates: list[ResolutionCandidate] = []
        durable_limitations: list[str] = []
        assumptions = (
            "This first resolver is local and manifest-backed only.",
            "Database-backed and remote-backed lookup remain out of scope in this milestone.",
            "When more than one discovered candidate exists, the resolver refuses to guess.",
        )

        explicit_binding = explicit_bindings.get(target_type_name)
        if explicit_binding is not None:
            resolved = _candidate_from_explicit_binding(target_type_name, explicit_binding)
            source = ResolverSource(
                kind="explicit_binding",
                label=target_type_name,
            )
            return ResolutionResult(
                target_type_name=target_type_name,
                resolved_value=resolved,
                selected_source=source,
                candidate_count=1,
                candidate_sources=(source,),
                assumptions=assumptions + ("Explicit local bindings take priority over discovered manifest matches.",),
            )

        # Manifest adapter discovery: if this planner type has a manifest
        # adapter, try to recover it from each provided local manifest source.
        manifest_adapter = _MANIFEST_ADAPTERS.get(target_type_name)
        if manifest_adapter is not None:
            for source in manifest_sources:
                try:
                    manifest, manifest_path = _manifest_payload(source)
                    value = manifest_adapter(manifest_path if manifest_path is not None else manifest)
                except FileNotFoundError:
                    # When the source is a filesystem path that no longer exists, check
                    # whether the durable index has an entry for it.  If so, surface an
                    # explicit limitation instead of silently skipping the source.
                    matched_ref = _durable_ref_for_missing_source(source, durable_index)
                    if matched_ref is not None:
                        durable_limitations.append(
                            f"Manifest at {source} no longer exists; it was last captured in run "
                            f"{matched_ref.run_id!r} (output {matched_ref.output_name!r}). "
                            "To reuse this output, restore the path or re-run the workflow."
                        )
                    continue
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    continue

                label = str(manifest_path) if manifest_path is not None else (
                    _manifest_workflow_name(manifest) or f"manifest:{len(candidates)+1}"
                )
                candidates.append(
                    ResolutionCandidate(
                        target_type_name=target_type_name,
                        value=value,
                        source=ResolverSource(
                            kind="manifest",
                            label=label,
                            manifest_path=manifest_path,
                            workflow_name=_manifest_workflow_name(manifest),
                        ),
                    )
                )

        for bundle in result_bundles:
            # Match the bundle instance against known result-bundle types so we
            # can reuse the same planner adapters that the manifest path uses.
            bundle_adapters = {}
            bundle_type_name = type(bundle).__name__
            for bundle_type, candidate_adapters in _BUNDLE_ADAPTERS.items():
                if isinstance(bundle, bundle_type):
                    # Found a matching bundle type; use its adapters and record
                    # the canonical type name for the resolution source.
                    bundle_adapters = candidate_adapters
                    bundle_type_name = bundle_type.__name__
                    break
            bundle_adapter = bundle_adapters.get(target_type_name)
            if bundle_adapter is None:
                continue
            try:
                value = bundle_adapter(bundle)
            except (FileNotFoundError, KeyError, TypeError, ValueError):
                continue
            candidates.append(
                ResolutionCandidate(
                    target_type_name=target_type_name,
                    value=value,
                    source=ResolverSource(
                        kind="result_bundle",
                        label=bundle_type_name,
                        bundle_type=bundle_type_name,
                    ),
                )
            )

        # Deduplicate by source.kind + source.label so the same asset does not
        # count twice when it is discoverable through more than one path.
        unique_candidates: list[ResolutionCandidate] = []
        seen_keys: set[tuple[str, str]] = set()
        for candidate in candidates:
            key = _candidate_key(candidate)  # Key is (source.kind, source.label)
            if key in seen_keys:
                continue  # Already discovered from this source; skip duplicate.
            seen_keys.add(key)
            unique_candidates.append(candidate)

        if len(unique_candidates) == 1:
            selected = unique_candidates[0]
            return ResolutionResult(
                target_type_name=target_type_name,
                resolved_value=selected.value,
                selected_source=selected.source,
                candidate_count=1,
                candidate_sources=(selected.source,),
                assumptions=assumptions,
            )

        if len(unique_candidates) > 1:
            # Ambiguous case: Multiple valid candidates found.
            # Refuse to guess; caller must provide explicit binding to disambiguate.
            source_text = ", ".join(f"`{candidate.source.label}`" for candidate in unique_candidates)
            return ResolutionResult(
                target_type_name=target_type_name,
                resolved_value=None,
                selected_source=None,
                candidate_count=len(unique_candidates),
                candidate_sources=tuple(candidate.source for candidate in unique_candidates),
                unresolved_requirements=(
                    f"Multiple {target_type_name} candidates were found from {source_text}; choose one explicitly.",
                ),
                assumptions=assumptions,
            )

        base_unresolved = (
            f"No {target_type_name} could be resolved from explicit bindings, manifests, or result bundles.",
        )
        return ResolutionResult(
            target_type_name=target_type_name,
            resolved_value=None,
            selected_source=None,
            candidate_count=0,
            candidate_sources=(),
            unresolved_requirements=base_unresolved + tuple(durable_limitations),
            assumptions=assumptions,
        )


__all__ = [
    "AssetResolver",
    "LocalManifestAssetResolver",
    "ResolutionCandidate",
    "ResolutionResult",
    "ResolverSource",
    "_materialize_bindings",
]
