"""Saved workflow-spec artifacts for replayable typed planning.

    This module saves metadata-only `WorkflowSpec` and `BindingPlan` pairs
    produced by typed planning so a later step can reload the selected workflow
    shape without re-parsing the original prompt.  It also owns the durable
    `RecipeApprovalRecord` that gates composed-recipe execution.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flytetest.specs import BindingPlan, SpecSerializable, WorkflowSpec


SPEC_ARTIFACT_SCHEMA_VERSION = "workflow-spec-artifact-v1"
DEFAULT_SPEC_ARTIFACT_FILENAME = "workflow_spec_artifact.json"
RECIPE_APPROVAL_SCHEMA_VERSION = "recipe-approval-v1"
DEFAULT_RECIPE_APPROVAL_FILENAME = "recipe_approval.json"


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


@dataclass(frozen=True, slots=True)
class RecipeApprovalRecord(SpecSerializable):
    """Durable approval state for a composed recipe artifact.

    Execution tools must check for a valid (non-expired, approved) record
    before running a composed recipe.  Approval is never auto-granted by the
    planner; it must be written explicitly by a human client through the
    ``approve_composed_recipe`` MCP tool.
    """

    schema_version: str
    artifact_path: str
    workflow_name: str
    approved: bool
    approved_at: str | None = None
    approved_by: str | None = None
    expires_at: str | None = None
    reason: str = ""


def _approval_path_for_artifact(artifact_path: Path) -> Path:
    """Return the companion approval-record path for a given artifact path."""
    if artifact_path.suffix == "":
        return artifact_path / DEFAULT_RECIPE_APPROVAL_FILENAME
    return artifact_path.parent / DEFAULT_RECIPE_APPROVAL_FILENAME


def save_recipe_approval(record: RecipeApprovalRecord, artifact_path: Path) -> Path:
    """Persist a recipe approval record as a companion file alongside the artifact.

    Uses atomic temp-file writes so the approval file is never partially written.

    Args:
        record: The approval record to persist.
        artifact_path: Path to the frozen artifact; the approval file is written
            as a sibling.

    Returns:
        The path where the approval record was written.
    """
    output_path = _approval_path_for_artifact(artifact_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n"
    fd, tmp_path = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
    try:
        os.write(fd, payload.encode())
        os.close(fd)
        os.replace(tmp_path, output_path)
    except BaseException:
        os.close(fd) if not os.get_inheritable(fd) else None
        if Path(tmp_path).exists():
            os.unlink(tmp_path)
        raise
    return output_path


def load_recipe_approval(artifact_path: Path) -> RecipeApprovalRecord:
    """Load the companion approval record for a given artifact path.

    Args:
        artifact_path: Path to the frozen artifact or its parent directory.

    Returns:
        The deserialized :class:`RecipeApprovalRecord`.

    Raises:
        FileNotFoundError: When no companion approval record exists.
        ValueError: When the schema version does not match.
    """
    record_path = _approval_path_for_artifact(artifact_path)
    payload = json.loads(record_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != RECIPE_APPROVAL_SCHEMA_VERSION:
        raise ValueError(f"Unsupported recipe approval schema version: {schema_version!r}")
    return RecipeApprovalRecord.from_dict(payload)


def check_recipe_approval(artifact_path: Path, now: str | None = None) -> tuple[bool, str]:
    """Check whether a composed recipe has a valid, non-expired approval.

    Args:
        artifact_path: Path to the frozen artifact.
        now: ISO-8601 timestamp to use as the current time for expiry checks.
            Defaults to the current UTC time.

    Returns:
        ``(True, "")`` when approved and not expired, or ``(False, reason)``
        when approval is missing, rejected, or expired.
    """
    try:
        record = load_recipe_approval(artifact_path)
    except FileNotFoundError:
        return False, "No approval record found for this composed recipe."
    except (ValueError, json.JSONDecodeError) as exc:
        return False, f"Invalid approval record: {exc}"

    if not record.approved:
        return False, f"Approval was explicitly rejected: {record.reason or 'no reason given'}"

    if record.expires_at:
        from datetime import datetime, UTC
        check_time = now or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if check_time > record.expires_at:
            return False, f"Approval expired at {record.expires_at}."

    return True, ""


__all__ = [
    "DEFAULT_RECIPE_APPROVAL_FILENAME",
    "DEFAULT_SPEC_ARTIFACT_FILENAME",
    "RECIPE_APPROVAL_SCHEMA_VERSION",
    "SPEC_ARTIFACT_SCHEMA_VERSION",
    "RecipeApprovalRecord",
    "SavedWorkflowSpecArtifact",
    "artifact_from_typed_plan",
    "check_recipe_approval",
    "load_recipe_approval",
    "load_workflow_spec_artifact",
    "replayable_spec_pair",
    "save_recipe_approval",
    "save_workflow_spec_artifact",
]
