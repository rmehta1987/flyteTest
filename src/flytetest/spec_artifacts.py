"""Saved workflow-spec artifacts for replayable typed planning.

    This module saves metadata-only `WorkflowSpec` and `BindingPlan` pairs
    produced by typed planning so a later step can reload the selected workflow
    shape without re-parsing the original prompt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flytetest.specs import BindingPlan, SpecSerializable, WorkflowSpec


SPEC_ARTIFACT_SCHEMA_VERSION = "workflow-spec-artifact-v1"
DEFAULT_SPEC_ARTIFACT_FILENAME = "workflow_spec_artifact.json"


@dataclass(frozen=True, slots=True)
class SavedWorkflowSpecArtifact(SpecSerializable):
    """A saved, metadata-only workflow plan that can be reloaded later.

    The artifact records the selected workflow shape, the matching binding plan,
    and the prompt/provenance details needed for review. It is intentionally not
    an execution record and does not contain generated Python code.
"""

    schema_version: str
    workflow_spec: WorkflowSpec
    binding_plan: BindingPlan
    source_prompt: str
    biological_goal: str
    planning_outcome: str
    candidate_outcome: str
    referenced_registered_stages: tuple[str, ...]
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    runtime_requirements: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = "not_recorded"
    replay_metadata: dict[str, Any] = field(default_factory=dict)
    metadata_only: bool = True


def _artifact_path(path: Path) -> Path:
    """Resolve a directory or JSON path to the saved artifact file path.

    Args:
        path: A filesystem path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    return path / DEFAULT_SPEC_ARTIFACT_FILENAME if path.is_dir() else path


def artifact_from_typed_plan(
    typed_plan: Mapping[str, Any],
    *,
    created_at: str,
    replay_metadata: Mapping[str, Any] | None = None,
) -> SavedWorkflowSpecArtifact:
    """Build a saved artifact from a successful typed-planning payload.

    Args:
        typed_plan: A value used by the helper.
        created_at: A value used by the helper.
        replay_metadata: A value used by the helper.

    Returns:
        The returned `SavedWorkflowSpecArtifact` value used by the caller.
"""
    if not typed_plan.get("supported"):
        raise ValueError("Only supported typed plans can be saved as replayable workflow spec artifacts.")
    if typed_plan.get("workflow_spec") is None or typed_plan.get("binding_plan") is None:
        raise ValueError("Typed plans must include both workflow_spec and binding_plan payloads before saving.")

    workflow_spec = WorkflowSpec.from_dict(typed_plan["workflow_spec"])
    binding_plan = BindingPlan.from_dict(typed_plan["binding_plan"])
    return SavedWorkflowSpecArtifact(
        schema_version=SPEC_ARTIFACT_SCHEMA_VERSION,
        workflow_spec=workflow_spec,
        binding_plan=binding_plan,
        source_prompt=str(typed_plan["original_request"]),
        biological_goal=str(typed_plan["biological_goal"]),
        planning_outcome=str(typed_plan["planning_outcome"]),
        candidate_outcome=str(typed_plan.get("candidate_outcome") or typed_plan["planning_outcome"]),
        referenced_registered_stages=tuple(str(name) for name in typed_plan["matched_entry_names"]),
        assumptions=tuple(str(assumption) for assumption in typed_plan.get("assumptions", ())),
        runtime_requirements=tuple(str(requirement) for requirement in typed_plan.get("runtime_requirements", ())),
        created_at=created_at,
        replay_metadata={
            "created_by": "plan_typed_request",
            "schema_version": SPEC_ARTIFACT_SCHEMA_VERSION,
            **dict(replay_metadata or {}),
        },
    )


def save_workflow_spec_artifact(artifact: SavedWorkflowSpecArtifact, destination: Path) -> Path:
    """Write one saved workflow-spec artifact as stable, inspectable JSON.

    Args:
        artifact: A value used by the helper.
        destination: A filesystem path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    output_path = destination / DEFAULT_SPEC_ARTIFACT_FILENAME if destination.suffix == "" else destination
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n")
    return output_path


def load_workflow_spec_artifact(path: Path) -> SavedWorkflowSpecArtifact:
    """Load a saved workflow-spec artifact from a JSON file or artifact directory.

    Args:
        path: A filesystem path used by the helper.

    Returns:
        The returned `SavedWorkflowSpecArtifact` value used by the caller.
"""
    payload = json.loads(_artifact_path(path).read_text())
    schema_version = payload.get("schema_version")
    if schema_version != SPEC_ARTIFACT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported workflow spec artifact schema version: {schema_version!r}")
    return SavedWorkflowSpecArtifact.from_dict(payload)


def replayable_spec_pair(artifact: SavedWorkflowSpecArtifact) -> tuple[WorkflowSpec, BindingPlan]:
    """Return the saved spec and binding plan without re-reading the original prompt.

    Args:
        artifact: A value used by the helper.

    Returns:
        The returned `tuple[WorkflowSpec, BindingPlan]` value used by the caller.
"""
    return artifact.workflow_spec, artifact.binding_plan


__all__ = [
    "DEFAULT_SPEC_ARTIFACT_FILENAME",
    "SPEC_ARTIFACT_SCHEMA_VERSION",
    "SavedWorkflowSpecArtifact",
    "artifact_from_typed_plan",
    "load_workflow_spec_artifact",
    "replayable_spec_pair",
    "save_workflow_spec_artifact",
]
