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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

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
from flytetest.types.assets import (
    AbInitioResultBundle,
    Braker3ResultBundle,
    EvmConsensusResultBundle,
    EvmInputPreparationBundle,
    ProteinEvidenceResultBundle,
)


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
    ) -> ResolutionResult:
        """Resolve one planner-facing type from local bindings, manifests, or bundles.

    Args:
        target_type_name: Planner type name currently being resolved.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        result_bundles: A directory path used by the helper.

    Returns:
        A `ResolutionResult` result computed by this helper.
"""
        if target_type_name not in _PLANNER_TYPES_BY_NAME:
            raise KeyError(f"Unsupported planner type for resolution: {target_type_name}")

        explicit_bindings = explicit_bindings or {}
        candidates: list[ResolutionCandidate] = []
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
                except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
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

        return ResolutionResult(
            target_type_name=target_type_name,
            resolved_value=None,
            selected_source=None,
            candidate_count=0,
            candidate_sources=(),
            unresolved_requirements=(
                f"No {target_type_name} could be resolved from explicit bindings, manifests, or result bundles.",
            ),
            assumptions=assumptions,
        )


__all__ = [
    "AssetResolver",
    "LocalManifestAssetResolver",
    "ResolutionCandidate",
    "ResolutionResult",
    "ResolverSource",
]
