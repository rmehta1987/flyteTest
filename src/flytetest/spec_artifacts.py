"""Saved workflow-spec artifacts for replayable typed planning.

This module saves metadata-only `WorkflowSpec` and `BindingPlan` pairs so a
later step can reload the selected workflow shape without re-parsing the
original prompt. It also owns the durable `RecipeApprovalRecord` that gates
composed-recipe execution.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from flytetest.specs import BindingPlan, SpecSerializable, WorkflowSpec


SPEC_ARTIFACT_SCHEMA_VERSION = "workflow-spec-artifact-v1"
DEFAULT_SPEC_ARTIFACT_FILENAME = "workflow_spec_artifact.json"
RECIPE_APPROVAL_SCHEMA_VERSION = "recipe-approval-v1"
DEFAULT_RECIPE_APPROVAL_FILENAME = "recipe_approval.json"
DURABLE_ASSET_INDEX_SCHEMA_VERSION = "durable-asset-index-v1"
DEFAULT_DURABLE_ASSET_INDEX_FILENAME = "durable_asset_index.json"

_TARGET_NAME_UNSAFE = re.compile(r"[^a-z0-9_-]")


def make_recipe_id(target_name: str, *, now: datetime | None = None) -> str:
    """Generate a stable recipe identifier: ``<YYYYMMDDThhmmss.mmm>Z-<target_name>``.

    Millisecond resolution makes collisions negligible for serialized calls.
    ``target_name`` is lower-cased and stripped of filesystem-unsafe characters
    so the id is valid as a filename stem and a Slurm job name.

    Composition-fallback plans should pass ``"composed-<first>_to_<last>"`` as
    *target_name* so the id self-describes the DAG boundaries.
    """
    ts = now or datetime.now(UTC)
    millis = ts.microsecond // 1000
    slug = _TARGET_NAME_UNSAFE.sub("_", target_name.lower()).strip("_") or "unknown"
    return f"{ts.strftime('%Y%m%dT%H%M%S')}.{millis:03d}Z-{slug}"


@dataclass(frozen=True, slots=True)
class SavedWorkflowSpecArtifact(SpecSerializable):
    """Saved, metadata-only planning data that can be reloaded later.

    The artifact records the selected workflow shape, the matching binding plan,
    and the prompt and provenance details needed for review. It is intentionally
    not an execution record and does not contain generated Python code.
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


def _json_ready(value: Any) -> Any:
    """Convert spec and executor values into stable JSON-compatible data.

    Recursively converts ``Path`` objects to strings, calls ``.to_dict()`` on
    objects that expose it, and recurses through mapping and sequence values.
    This function is intentionally generic so it can be used by both
    artifact-level and executor-level write helpers.
    """
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict"):
        return _json_ready(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _write_json_atomically(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON payload through a temporary file before replacing it.

    The temporary file is placed in the same directory as the target so the
    final ``os.replace`` is always an in-filesystem rename rather than a
    cross-device copy.  Writes are pretty-printed and key-sorted so diffs and
    code-review remain readable.

    Args:
        path: Destination path for the JSON file.  The parent directory is
            created when it does not exist.
        payload: JSON-compatible data to write.  ``Path`` values and nested
            ``SpecSerializable`` instances are recursively converted by
            :func:`_json_ready` before serialization.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n")
    os.replace(temporary_path, path)


@dataclass(frozen=True, slots=True)
class DurableAssetRef(SpecSerializable):
    """Stable identity record for one workflow output captured after local execution.

    A ``DurableAssetRef`` names the filesystem location of one Path-valued
    output from a completed local run so a later session can locate it without
    knowing the exact path up front.  All refs for one run are written together
    into a ``durable_asset_index.json`` sidecar alongside ``local_run_record.json``.

    Attributes:
        schema_version: Always ``DURABLE_ASSET_INDEX_SCHEMA_VERSION``; used to
            reject index files written by an incompatible version.
        run_id: Stable run identifier from the parent :class:`LocalRunRecord`.
        workflow_name: Workflow that produced this output.
        output_name: Field name of the output as declared in the workflow spec
            (key in ``LocalRunRecord.final_outputs``-adjacent data).
        node_name: Name of the workflow node whose handler produced this output.
        asset_path: Absolute path to the output directory or file.
        manifest_path: Path to the ``run_manifest.json`` inside *asset_path*,
            or ``None`` when the handler did not write a manifest.
        created_at: UTC timestamp from the parent ``LocalRunRecord.created_at``.
        run_record_path: Absolute path to the companion ``local_run_record.json``
            so callers can navigate from any ref back to the full run record.
        produced_type: Planner type this durable ref is known to produce when
            the originating entry declares exactly one produced planner type or
            the manifest carries per-output planner-type metadata. Empty means
            the ref must fall back to manifest membership checks.
    """

    schema_version: str
    run_id: str
    workflow_name: str
    output_name: str
    node_name: str
    asset_path: Path
    manifest_path: Path | None
    created_at: str
    run_record_path: Path
    produced_type: str = ""


def save_durable_asset_index(refs: Sequence[DurableAssetRef], run_dir: Path) -> Path:
    """Write a ``durable_asset_index.json`` sidecar atomically to *run_dir*.

    The index envelope carries top-level ``schema_version``, ``run_id``, and
    ``workflow_name`` fields so tools can skip parsing individual entries when
    they only need the run identity.  Each entry serializes a full
    :class:`DurableAssetRef` so the index is self-contained.

    Args:
        refs: Non-empty sequence of refs to index.  All refs are assumed to
            belong to the same run; the envelope fields are taken from the
            first ref.
        run_dir: Directory where the index is written.  Normally the per-run
            subdirectory that already contains ``local_run_record.json``.

    Returns:
        Path to the written index file.

    Raises:
        ValueError: When *refs* is empty (an empty index is never valid).
    """
    if not refs:
        raise ValueError("Cannot write an empty durable asset index.")
    first = refs[0]
    payload: dict[str, Any] = {
        "schema_version": DURABLE_ASSET_INDEX_SCHEMA_VERSION,
        "run_id": first.run_id,
        "workflow_name": first.workflow_name,
        "entries": [ref.to_dict() for ref in refs],
    }
    output_path = run_dir / DEFAULT_DURABLE_ASSET_INDEX_FILENAME
    _write_json_atomically(output_path, payload)
    return output_path


def load_durable_asset_index(run_dir: Path) -> list[DurableAssetRef]:
    """Load a ``durable_asset_index.json`` from *run_dir*; return ``[]`` if absent.

    Returns an empty list rather than raising when the sidecar does not exist
    so callers can treat pre-M20b run directories (which have no index) the
    same as runs with no Path-valued outputs — both yield an empty sequence.

    Args:
        run_dir: Directory to search for ``durable_asset_index.json``.

    Returns:
        List of :class:`DurableAssetRef` entries, or ``[]`` when no index file
        is present.

    Raises:
        ValueError: When an index file exists but carries an unrecognised
            ``schema_version``, signalling that the file should not be
            silently parsed under a different field layout.
    """
    index_path = run_dir / DEFAULT_DURABLE_ASSET_INDEX_FILENAME
    if not index_path.exists():
        return []
    payload = json.loads(index_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != DURABLE_ASSET_INDEX_SCHEMA_VERSION:
        raise ValueError(f"Unsupported durable asset index schema version: {schema_version!r}")
    return [DurableAssetRef.from_dict(entry) for entry in payload.get("entries", [])]


def _artifact_path(path: Path) -> Path:
    """Resolve a directory or JSON path to the saved artifact file path.

    Args:
        path: Artifact directory or artifact JSON file path.

    Returns:
        The artifact JSON file path.
    """
    return path / DEFAULT_SPEC_ARTIFACT_FILENAME if path.is_dir() else path


def artifact_from_typed_plan(
    typed_plan: Mapping[str, Any],
    *,
    created_at: str,
    replay_metadata: Mapping[str, Any] | None = None,
) -> SavedWorkflowSpecArtifact:
    """Freeze a successful typed-planning response into a replayable artifact.

    The planner layer returns a ``typed_plan`` dict by serializing the selected
    ``WorkflowSpec`` and ``BindingPlan`` together with the original prompt,
    biological goal, and matched stage names.  This function validates that
    response and locks it into a :class:`SavedWorkflowSpecArtifact` that can
    be saved to disk, approved, and re-executed without re-running the planner.

    Args:
        typed_plan: Serialized response from the ``plan_typed_request`` MCP
            handler.  Must carry ``supported=True`` and both
            ``workflow_spec`` and ``binding_plan`` keys; raises immediately
            when either is missing so the caller cannot accidentally persist
            an unsupported or partial plan.
        created_at: UTC timestamp injected by the caller rather than computed
            here so the artifact's ``created_at`` field matches the timestamp
            the MCP response was returned to the client.  Injecting it also
            keeps this function deterministic in tests.
        replay_metadata: Additional key/value pairs embedded in
            ``replay_metadata`` alongside the standard provenance fields.
            Useful for clients that want to record the planner model version,
            session ID, or other audit information without adding top-level
            artifact fields.

    Returns:
        Frozen :class:`SavedWorkflowSpecArtifact` ready to pass to
        :func:`save_workflow_spec_artifact`.  The artifact carries the full
        workflow shape, binding plan, and prompt provenance so any later
        execution can be traced back to the original planning decision.
    """
    if not typed_plan.get("supported"):
        raise ValueError("Only supported typed plans can be saved as replayable workflow spec artifacts.")
    if typed_plan.get("workflow_spec") is None or typed_plan.get("binding_plan") is None:
        raise ValueError("Typed plans must include both workflow_spec and binding_plan payloads before saving.")

    # Merge top-level tool_databases from the plan into the workflow_spec dict
    # so callers can carry tool_databases at either location.  The value inside
    # workflow_spec takes precedence; a top-level key fills the gap when the
    # spec was built before the field existed (§8 resolution order).
    workflow_spec_dict = dict(typed_plan["workflow_spec"])
    if "tool_databases" not in workflow_spec_dict:
        workflow_spec_dict["tool_databases"] = typed_plan.get("tool_databases") or {}
    # Merge top-level runtime_images from the plan into the workflow_spec dict
    # by the same §8 resolution order: the value inside workflow_spec wins.
    if not workflow_spec_dict.get("runtime_images"):
        workflow_spec_dict["runtime_images"] = typed_plan.get("runtime_images") or {}
    workflow_spec = WorkflowSpec.from_dict(workflow_spec_dict)
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
    """Write a frozen workflow-spec artifact to disk as human-readable JSON.

    The file is written as pretty-printed, key-sorted JSON so it can be
    inspected and reviewed in a text editor before the recipe is approved
    or executed.  The write is not atomic-swapped (unlike run records) because
    artifacts are write-once: an artifact path is allocated once and never
    overwritten by a later call.

    Args:
        artifact: Immutable workflow-spec artifact to serialize.  The content
            is not validated here; callers should use
            :func:`artifact_from_typed_plan` to construct a valid artifact
            before saving.
        destination: Directory path or explicit ``.json`` file path.  When
            *destination* has no suffix (bare directory), the artifact is
            written as ``workflow_spec_artifact.json`` inside that directory.
            When it has a suffix, the path is used verbatim.  The parent
            directory is created if it does not exist.

    Returns:
        Absolute path to the written artifact JSON file, for the caller to
        record in the MCP response or pass to the approval flow.
    """
    output_path = destination / DEFAULT_SPEC_ARTIFACT_FILENAME if destination.suffix == "" else destination
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n")
    return output_path


def load_workflow_spec_artifact(path: Path) -> SavedWorkflowSpecArtifact:
    """Reload a saved workflow-spec artifact so it can be executed or inspected.

    Validates the ``schema_version`` field before deserializing.  The artifact
    schema evolves as planning and binding fields are added; a version mismatch
    means the stored file was written by an older code path and its field
    layout may differ from what :class:`SavedWorkflowSpecArtifact` now expects.
    Rejecting it here prevents silent data loss when unexpectedly missing fields
    are filled with dataclass defaults.

    Args:
        path: Artifact JSON file or the directory that contains it.  The
            directory form is the normal case (matches the layout written by
            :func:`save_workflow_spec_artifact`); the file form is used in
            tests and when the caller already resolved the path.

    Returns:
        :class:`SavedWorkflowSpecArtifact` whose ``workflow_spec`` and
        ``binding_plan`` are ready to pass to
        :meth:`~flytetest.spec_executor.LocalWorkflowSpecExecutor.execute`
        or to :meth:`~flytetest.spec_executor.SlurmWorkflowSpecExecutor.submit`.

    Raises:
        ValueError: When the stored ``schema_version`` does not match
            :data:`SPEC_ARTIFACT_SCHEMA_VERSION`.
    """
    payload = json.loads(_artifact_path(path).read_text())
    schema_version = payload.get("schema_version")
    if schema_version != SPEC_ARTIFACT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported workflow spec artifact schema version: {schema_version!r}")
    return SavedWorkflowSpecArtifact.from_dict(payload)


def replayable_spec_pair(artifact: SavedWorkflowSpecArtifact) -> tuple[WorkflowSpec, BindingPlan]:
    """Extract the workflow spec and binding plan from a loaded artifact.

    Exists so callers that only need the two execution-facing objects do not
    have to unpack the artifact's fields by name.  The artifact itself is the
    source of truth; this function adds no logic.

    Args:
        artifact: Already-loaded :class:`SavedWorkflowSpecArtifact`; the
            caller is responsible for loading it (and checking approval if
            required) before extracting the pair.

    Returns:
        ``(workflow_spec, binding_plan)`` ready to hand directly to an
        executor without re-running the planner against the original prompt.
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


def save_recipe_approval(
    record: RecipeApprovalRecord, artifact_path: Path
) -> Path:
    """Write an approval record as a sidecar file collocated with the artifact.

    The approval record lives next to the artifact so the execution gate
    (:func:`check_recipe_approval`) can locate it with only the artifact path.
    Keeping them together also means the artifact directory is self-contained:
    an artifact plus its sidecar can be moved or archived as a unit without
    breaking the approval check.

    The write is atomic via a temp-file swap so the sidecar is never left in a
    partially-written state.  A partial approval file would cause
    :func:`load_recipe_approval` to raise a parse error rather than silently
    report a false approval.

    Args:
        record: Approval state to write.  Typically produced by the
            ``approve_composed_recipe`` MCP tool after the user confirms
            the recipe details; never auto-generated by the planner.
        artifact_path: Path to the frozen artifact JSON whose approval this
            record represents.  Used to derive the sidecar path; the artifact
            file itself is not modified.

    Returns:
        Path to the written sidecar file, so the MCP handler can include it
        in the confirmation response.
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
    """Read the approval sidecar for a given artifact so callers can inspect its fields.

    Most callers should use :func:`check_recipe_approval` rather than this
    function directly.  Load directly only when you need to read the full
    record (e.g. to display approval details to a user) rather than just
    the approved/rejected decision.

    Args:
        artifact_path: Path to the frozen artifact JSON or its parent
            directory.  The sidecar path is derived from this location by
            :func:`_approval_path_for_artifact`.

    Returns:
        :class:`RecipeApprovalRecord` with the ``approved``, ``approved_at``,
        and ``expires_at`` fields that callers can display or forward to
        :func:`check_recipe_approval`.

    Raises:
        FileNotFoundError: When no sidecar exists, meaning the recipe has
            never been explicitly approved or rejected.
        ValueError: When the sidecar's ``schema_version`` does not match
            :data:`RECIPE_APPROVAL_SCHEMA_VERSION`.
    """
    record_path = _approval_path_for_artifact(artifact_path)
    payload = json.loads(record_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != RECIPE_APPROVAL_SCHEMA_VERSION:
        raise ValueError(f"Unsupported recipe approval schema version: {schema_version!r}")
    return RecipeApprovalRecord.from_dict(payload)


def check_recipe_approval(artifact_path: Path, now: str | None = None) -> tuple[bool, str]:
    """Gate composed-recipe execution by checking approval state and expiry.

    Called by execution tools before running any composed recipe so that
    execution cannot start without explicit human approval through the
    ``approve_composed_recipe`` MCP tool.  Never auto-approves; a missing
    sidecar always returns ``(False, ...)``.  Approval is edge-triggered: once
    ``expires_at`` passes, the recipe must be re-approved even if the artifact
    and inputs are unchanged.

    Args:
        artifact_path: Path to the frozen artifact JSON whose approval sidecar
            should be checked.  The sidecar path is derived automatically.
        now: ISO-8601 UTC timestamp to use as the current time for expiry
            comparison.  Injected so tests can simulate future or past times
            without patching the system clock.  Defaults to the actual current
            UTC time when ``None``.

    Returns:
        ``(True, "")`` when the recipe is approved and the approval has not
        expired.  ``(False, reason)`` in all other cases, where *reason* is a
        human-readable string suitable for embedding in an MCP limitation
        response.
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
    "DEFAULT_DURABLE_ASSET_INDEX_FILENAME",
    "make_recipe_id",
    "DEFAULT_RECIPE_APPROVAL_FILENAME",
    "DEFAULT_SPEC_ARTIFACT_FILENAME",
    "DURABLE_ASSET_INDEX_SCHEMA_VERSION",
    "RECIPE_APPROVAL_SCHEMA_VERSION",
    "SPEC_ARTIFACT_SCHEMA_VERSION",
    "DurableAssetRef",
    "RecipeApprovalRecord",
    "SavedWorkflowSpecArtifact",
    "artifact_from_typed_plan",
    "check_recipe_approval",
    "load_durable_asset_index",
    "load_recipe_approval",
    "load_workflow_spec_artifact",
    "replayable_spec_pair",
    "save_durable_asset_index",
    "save_recipe_approval",
    "save_workflow_spec_artifact",
]
