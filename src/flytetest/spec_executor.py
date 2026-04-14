"""Execution helpers for saved workflow-spec artifacts and Slurm run records.

This module executes saved `WorkflowSpec` artifacts through explicit local
handlers, and it also owns the repo's Slurm submission, reconciliation, and
cancellation helpers for frozen recipe runs. It keeps execution separate from
the current Flyte entrypoints and uses the resolver plus saved `BindingPlan`
data to prepare node inputs before any supported stage is called.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flytetest.registry import get_entry
from flytetest.resolver import AssetResolver, LocalManifestAssetResolver, ResolutionResult
from flytetest.planner_types import QualityAssessmentTarget
from flytetest.spec_artifacts import SavedWorkflowSpecArtifact, load_workflow_spec_artifact
from flytetest.specs import ResourceSpec, RuntimeImageSpec, SpecSerializable, WorkflowNodeSpec


RegisteredNodeHandler = Callable[["LocalNodeExecutionRequest"], Mapping[str, Any]]
SLURM_RUN_RECORD_SCHEMA_VERSION = "slurm-run-record-v1"
DEFAULT_SLURM_RUN_RECORD_FILENAME = "slurm_run_record.json"
DEFAULT_SLURM_SCRIPT_FILENAME = "submit_slurm.sh"
DEFAULT_SLURM_MAX_ATTEMPTS = 2
LOCAL_RUN_RECORD_SCHEMA_VERSION = "local-run-record-v1"
DEFAULT_LOCAL_RUN_RECORD_FILENAME = "local_run_record.json"
HANDLER_SCHEMA_VERSION = "1"


def _normalize_path_for_cache_key(value: str, repo_root: str | None = None) -> str:
    """Convert a path string to a stable POSIX form for cache-key hashing.

    Strips the *repo_root* prefix when present so the same logical input from a
    different checkout directory does not invalidate the cache.  All backslash
    separators are converted to forward slashes.

    Only the repo-root prefix is stripped.  Every path component below it is
    kept so that genuinely different inputs still produce different keys.
    """
    posix = value.replace("\\", "/")
    if repo_root:
        prefix = repo_root.replace("\\", "/").rstrip("/") + "/"
        if posix.startswith(prefix):
            posix = posix[len(prefix):]
    return posix


def _normalize_value_for_cache_key(value: Any, repo_root: str | None = None) -> Any:
    """Recursively normalize a JSON-compatible value for deterministic hashing.

    * ``Path`` instances are converted to POSIX strings.
    * Strings that look like absolute filesystem paths have the *repo_root*
      prefix stripped so cosmetic checkout-location differences do not
      invalidate the cache.
    * Dicts are rebuilt with sorted keys.
    * Lists/tuples are recursively normalized.
    """
    if isinstance(value, Path):
        return _normalize_path_for_cache_key(str(value), repo_root)
    if isinstance(value, str):
        if value.startswith("/") or (len(value) > 2 and value[1] == ":"):
            return _normalize_path_for_cache_key(value, repo_root)
        return value
    if isinstance(value, dict):
        return {k: _normalize_value_for_cache_key(v, repo_root) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize_value_for_cache_key(v, repo_root) for v in value]
    return value


def cache_identity_key(
    workflow_spec_dict: dict[str, Any],
    binding_plan_dict: dict[str, Any],
    resolved_planner_inputs: dict[str, Any],
    *,
    handler_schema_version: str = HANDLER_SCHEMA_VERSION,
    repo_root: str | None = None,
) -> str:
    """Compute a deterministic hex digest that identifies a frozen execution.

    The key is built from the JSON serialization of four normalized inputs:
    the full workflow shape, the binding plan, the resolved planner inputs,
    and an explicit handler-schema version that invalidates prior records
    when handler output shapes or internal behavior change.

    Path normalization strips the *repo_root* prefix and uses POSIX
    separators so the same biology from a different checkout path produces
    the same key.

    This function is pure: no filesystem reads or network calls.
    """
    normalized = {
        "workflow_spec": _normalize_value_for_cache_key(workflow_spec_dict, repo_root),
        "binding_plan": _normalize_value_for_cache_key(binding_plan_dict, repo_root),
        "resolved_planner_inputs": _normalize_value_for_cache_key(resolved_planner_inputs, repo_root),
        "handler_schema_version": handler_schema_version,
    }
    canonical = json.dumps(normalized, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class LocalNodeExecutionRequest:
    """Inputs passed to one supported task or workflow handler.

    It captures the node metadata, resolved planner inputs, and frozen runtime
    policy that a local handler needs in order to execute one stage.
"""

    node: WorkflowNodeSpec
    inputs: Mapping[str, Any]
    resolved_planner_inputs: Mapping[str, Any]
    upstream_outputs: Mapping[str, Mapping[str, Any]]
    binding_plan_target: str
    execution_profile: str | None
    resource_spec: ResourceSpec | None
    runtime_image: RuntimeImageSpec | None


@dataclass(frozen=True, slots=True)
class LocalNodeExecutionResult(SpecSerializable):
    """Execution details recorded for one saved-spec node.

    It captures the node identifier, outputs, and manifest references for each
    stage that ran during local saved-spec execution. Extending SpecSerializable
    allows these records to round-trip through the durable LocalRunRecord JSON.
"""

    node_name: str
    reference_name: str
    outputs: Mapping[str, Any]
    manifest_paths: dict[str, Path] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LocalSpecExecutionResult:
    """Outcome of executing a saved workflow spec through local handlers.

    Attributes:
        supported: Whether the artifact could be executed by the local handler
            registry instead of only planned or rejected.
        workflow_name: Frozen workflow name from the saved spec, included so
            callers can report which recipe accepted or rejected execution.
        node_results: Per-node outputs collected in workflow order when local
            execution succeeds.
        final_outputs: Workflow-level outputs resolved from the final output
            bindings after all required nodes complete.
        limitations: User-facing reasons local execution could not proceed.
        assumptions: Deduplicated execution notes collected while resolving
            planner inputs and running handlers.
    """

    supported: bool
    workflow_name: str
    execution_profile: str | None
    resolved_planner_inputs: Mapping[str, Any]
    resource_spec: ResourceSpec | None = None
    runtime_image: RuntimeImageSpec | None = None
    node_results: tuple[LocalNodeExecutionResult, ...] = field(default_factory=tuple)
    final_outputs: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LocalRunRecord(SpecSerializable):
    """Durable run record for one local saved-spec execution.

    It captures frozen recipe identity, resolved inputs, per-node completion
    state, and output references so interrupted work can resume without
    recomputing already-completed stages.  The record is written atomically
    after every successful local execution and can be reloaded by Phase B
    resume logic using only the frozen recipe and recorded bindings.

    Schema version:
        ``local-run-record-v1`` — initial Phase A shape.  Increment the
        version constant if fields are added or semantics change so that
        stale records are rejected rather than silently misinterpreted.
"""

    schema_version: str
    run_id: str
    workflow_name: str
    run_record_path: Path
    created_at: str
    execution_profile: str
    resolved_planner_inputs: Mapping[str, Any]
    binding_plan_target: str
    node_completion_state: dict[str, bool]
    node_results: tuple[LocalNodeExecutionResult, ...]
    artifact_path: Path | None = None
    resource_spec: ResourceSpec | None = None
    runtime_image: RuntimeImageSpec | None = None
    final_outputs: Mapping[str, Any] = field(default_factory=dict)
    completed_at: str | None = None
    node_skip_reasons: dict[str, str] = field(default_factory=dict)
    cache_identity_key: str | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SlurmRetryPolicy(SpecSerializable):
    """Explicit retry policy recorded with each Slurm run lineage.

    Attributes:
        max_attempts: Maximum number of Slurm submissions allowed for one
            retry lineage, including the original attempt.
    """

    max_attempts: int = DEFAULT_SLURM_MAX_ATTEMPTS


@dataclass(frozen=True, slots=True)
class SlurmFailureClassification(SpecSerializable):
    """Conservative retryability assessment for one Slurm run record.

    Attributes:
        status: Durable lifecycle status used by MCP retry and monitoring
            responses.
        retryable: Whether the observed scheduler outcome is safe to resubmit
            under the recorded retry policy.
        failure_class: Stable diagnostic bucket for failures that are known
            well enough to explain or retry.
        detail: Human-readable explanation of the scheduler evidence that
            drove the classification.
    """

    status: str
    retryable: bool
    failure_class: str | None = None
    scheduler_state: str | None = None
    exit_code: str | None = None
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class SlurmRunRecord(SpecSerializable):
    """Durable filesystem record for one accepted Slurm recipe submission.

    Attributes:
        run_id: Stable identifier for the submission directory and retry
            lineage.
        recipe_id: Frozen recipe identifier carried from the saved artifact.
        artifact_path: Saved workflow-spec recipe submitted to Slurm.
        script_path: Generated `sbatch` script path preserved for inspection
            and replay auditing.
        stdout_path: Scheduler stdout log path recorded as soon as submission
            is accepted.
        stderr_path: Scheduler stderr log path recorded as soon as submission
            is accepted.
        job_id: Scheduler job ID returned by `sbatch`.
        local_resume_node_state: Completed local nodes imported from a prior
            local run so Slurm execution can skip already-done stages.
    """

    schema_version: str
    run_id: str
    recipe_id: str
    workflow_name: str
    artifact_path: Path
    script_path: Path
    stdout_path: Path
    stderr_path: Path
    run_record_path: Path
    job_id: str
    execution_profile: str
    resource_spec: ResourceSpec | None = None
    resource_overrides: ResourceSpec | None = None
    runtime_image: RuntimeImageSpec | None = None
    submitted_at: str = "not_recorded"
    scheduler_stdout: str = ""
    scheduler_stderr: str = ""
    scheduler_state: str = "submitted"
    scheduler_state_source: str | None = None
    scheduler_exit_code: str | None = None
    scheduler_reason: str | None = None
    final_scheduler_state: str | None = None
    last_reconciled_at: str | None = None
    cancellation_requested_at: str | None = None
    retry_policy: SlurmRetryPolicy = field(default_factory=SlurmRetryPolicy)
    attempt_number: int = 1
    lineage_root_run_id: str | None = None
    lineage_root_run_record_path: Path | None = None
    retry_parent_run_id: str | None = None
    retry_parent_run_record_path: Path | None = None
    retry_child_run_ids: tuple[str, ...] = field(default_factory=tuple)
    retry_child_run_record_paths: tuple[Path, ...] = field(default_factory=tuple)
    failure_classification: SlurmFailureClassification | None = None
    local_resume_node_state: dict[str, bool] = field(default_factory=dict)
    local_resume_run_id: str | None = None
    cache_identity_key: str | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SlurmSpecExecutionResult:
    """Outcome of submitting a frozen workflow-spec artifact to Slurm.

    It captures whether submission was supported, which supported workflow was
    submitted, and the resulting script, logs, and run record if available.
    """

    supported: bool
    workflow_name: str
    execution_profile: str | None
    resource_spec: ResourceSpec | None = None
    runtime_image: RuntimeImageSpec | None = None
    run_record: SlurmRunRecord | None = None
    script_text: str = ""
    scheduler_stdout: str = ""
    scheduler_stderr: str = ""
    limitations: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SlurmSchedulerSnapshot(SpecSerializable):
    """Scheduler state observed for one Slurm job.

    It stores the scheduler state and raw command output observed for one job
    during status, reconciliation, or cancellation.
    """

    job_id: str
    scheduler_state: str | None
    source: str | None = None
    exit_code: str | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    reason: str | None = None
    raw_squeue_stdout: str = ""
    raw_scontrol_stdout: str = ""
    raw_sacct_stdout: str = ""
    limitations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SlurmLifecycleResult(SpecSerializable):
    """Result of reloading, reconciling, or cancelling a Slurm run record.

    It packages the durable run record together with the most recent scheduler
    snapshot after a lifecycle action.
    """

    supported: bool
    run_record: SlurmRunRecord | None = None
    scheduler_snapshot: SlurmSchedulerSnapshot | None = None
    action: str = "status"
    limitations: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SlurmRetryResult(SpecSerializable):
    """Outcome of retrying one failed Slurm run from a durable run record.

    It bundles the source record, failure classification, retry policy, and
    retry submission result so the retry lineage stays inspectable.
    """

    supported: bool
    source_run_record: SlurmRunRecord | None = None
    failure_classification: SlurmFailureClassification | None = None
    retry_policy: SlurmRetryPolicy | None = None
    retry_execution: SlurmSpecExecutionResult | None = None
    action: str = "retry"
    limitations: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)


def _artifact_from_source(source: SavedWorkflowSpecArtifact | Path) -> SavedWorkflowSpecArtifact:
    """Load an artifact from disk when the caller provides a path.

    Args:
        source: Saved workflow-spec artifact or path that should be loaded first.

    Returns:
        The loaded saved workflow-spec artifact.
    """
    if isinstance(source, SavedWorkflowSpecArtifact):
        return source
    return load_workflow_spec_artifact(source)


def _artifact_path_from_source(source: SavedWorkflowSpecArtifact | Path) -> Path | None:
    """Return the artifact path when the caller supplied a filesystem source.

    Args:
        source: Saved workflow-spec artifact or path source being inspected.

    Returns:
        The source path when the caller supplied a path, otherwise ``None``.
    """
    return Path(source) if not isinstance(source, SavedWorkflowSpecArtifact) else None


def _planner_type_names_for_node_inputs(artifact: SavedWorkflowSpecArtifact) -> tuple[str, ...]:
    """Return planner type names that must be resolved before node execution.

    Args:
        artifact: Saved workflow-spec artifact being loaded, inspected, or executed.

    Returns:
        The unique planner type names required by the workflow inputs.
    """
    names: list[str] = []
    for input_spec in artifact.workflow_spec.inputs:
        for name in input_spec.planner_type_names:
            if name not in names:
                names.append(name)
    return tuple(names)


def _serialized_resolved_value(result: ResolutionResult) -> Any:
    """Convert one resolved planner value into an executor-friendly payload.

    Args:
        result: The resolution result that selected a planner-facing value.

    Returns:
        A JSON-friendly representation of the selected planner value.
    """
    value = result.resolved_value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return value


def _quality_assessment_target_from_serialized(value: Any) -> QualityAssessmentTarget | None:
    """Convert a serialized quality target into the planner dataclass when possible.

    Args:
        value: Serialized planner data or an already-built quality target.

    Returns:
        The reconstructed quality target, or ``None`` if the payload is not compatible.
    """
    if isinstance(value, QualityAssessmentTarget):
        return value
    if isinstance(value, Mapping):
        return QualityAssessmentTarget.from_dict(dict(value))
    return None


def _manifest_source_bundle_path(target: QualityAssessmentTarget, source_bundle_key: str) -> Path | None:
    """Return one source bundle path from the target manifest when it is recorded.

    Args:
        target: The quality target whose manifest should be inspected.
        source_bundle_key: The source bundle field name expected in the manifest.

    Returns:
        The recorded source bundle path, or ``None`` when the manifest omits it.
    """
    if target.source_manifest_path is None:
        return None
    try:
        manifest = json.loads(Path(target.source_manifest_path).read_text())
    except (FileNotFoundError, TypeError, json.JSONDecodeError):
        return None
    source_bundle = manifest.get("source_bundle", {})
    if not isinstance(source_bundle, Mapping):
        return None
    value = source_bundle.get(source_bundle_key)
    if value in (None, ""):
        return None
    return Path(str(value))


def _source_dir_from_quality_target(
    target: QualityAssessmentTarget,
    *,
    source_bundle_key: str,
    execution_input_name: str,
) -> Path:
    """Derive the concrete workflow input directory required by a QC target.

    Args:
        target: The quality target whose source directory should be recovered.
        source_bundle_key: The source bundle field name expected in the manifest.
        execution_input_name: Execution input name used to select a runtime binding.

    Returns:
        The source directory that should be passed to the downstream stage.
    """
    if source_dir := _manifest_source_bundle_path(target, source_bundle_key):
        return source_dir
    if target.source_result_dir is not None:
        return Path(target.source_result_dir)
    if target.source_manifest_path is not None:
        return Path(target.source_manifest_path).parent
    raise ValueError(
        f"QualityAssessmentTarget must include source_result_dir or source_manifest_path before `{execution_input_name}` execution."
    )


def _quality_assessment_target_runtime_inputs(
    node_reference_name: str,
    resolved_planner_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Build runtime inputs for quality-assessment nodes that consume a result bundle.

    The planner can resolve a high-level :class:`QualityAssessmentTarget`
    instead of a raw directory path. In this repository, that target means a
    prior result bundle that should be handed to a downstream quality
    assessment or post-processing stage. When that happens, this helper
    converts the planner object back into the concrete result-directory input
    expected by the runtime node. The function only applies to stages whose
    input contract is based on a prior result bundle:

    - `annotation_qc_busco`
    - `annotation_functional_eggnog`
    - `annotation_postprocess_agat`
    - `annotation_postprocess_agat_conversion`
    - `annotation_postprocess_agat_cleanup`

    Args:
        node_reference_name: The supported node name being prepared for local execution.
        resolved_planner_inputs: Planner inputs after resolution, including any
            structured quality-assessment targets.

    Returns:
        A dictionary of runtime inputs that should be merged into the node
        execution request before the handler runs.
    """
    quality_target_inputs = {
        # These nodes do not take a user-authored path directly. Instead they
        # consume the source directory from a prior result bundle, so the
        # planner target has to be translated back into the exact workflow
        # input name and manifest key expected by the runtime handler.
        "annotation_qc_busco": ("repeat_filter_results", "repeat_filter_results"),
        "annotation_functional_eggnog": ("repeat_filter_results", "repeat_filter_results"),
        "annotation_postprocess_agat": ("eggnog_results", "eggnog_results"),
        "annotation_postprocess_agat_conversion": ("eggnog_results", "eggnog_results"),
        "annotation_postprocess_agat_cleanup": ("agat_conversion_results", "agat_conversion_results"),
    }
    input_rule = quality_target_inputs.get(node_reference_name)
    if input_rule is None:
        return {}

    target_value = resolved_planner_inputs.get("QualityAssessmentTarget")
    if target_value is None:
        return {}

    target = _quality_assessment_target_from_serialized(target_value)
    if target is None:
        return {}

    execution_input_name, source_bundle_key = input_rule
    return {
        execution_input_name: _source_dir_from_quality_target(
            target,
            source_bundle_key=source_bundle_key,
            execution_input_name=execution_input_name,
        )
    }


def _resolve_planner_inputs(
    artifact: SavedWorkflowSpecArtifact,
    *,
    explicit_bindings: Mapping[str, Any],
    manifest_sources: Sequence[Path | Mapping[str, Any]],
    result_bundles: Sequence[Any],
    resolver: AssetResolver,
) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]:
    """Resolve planner-facing values from saved bindings and local sources.

    Args:
        artifact: Frozen workflow-spec artifact whose planner inputs are being
            materialized for execution.
        explicit_bindings: User-supplied values that override anything found in
            manifests or result bundles.
        manifest_sources: Local manifest files or mappings that may satisfy
            planner inputs from prior runs.
        result_bundles: Result directories that can contribute reusable inputs
            for the current plan.
        resolver: Local asset resolver that performs the actual input lookup.

    Returns:
        A three-tuple of resolved planner inputs, unresolved requirement
        messages, and deduplicated assumptions.
    """
    resolved: dict[str, Any] = {}
    limitations: list[str] = []
    assumptions: list[str] = []
    saved_bindings = dict(artifact.binding_plan.explicit_user_bindings)
    saved_bindings.update(explicit_bindings)

    for planner_type_name in _planner_type_names_for_node_inputs(artifact):
        result = resolver.resolve(
            planner_type_name,
            explicit_bindings=saved_bindings,
            manifest_sources=manifest_sources,
            result_bundles=result_bundles,
        )
        assumptions.extend(assumption for assumption in result.assumptions if assumption not in assumptions)
        if result.is_resolved:
            resolved[planner_type_name] = _serialized_resolved_value(result)
            continue
        limitations.extend(result.unresolved_requirements)

    return resolved, tuple(limitations), tuple(assumptions)


def _resolve_binding_expression(
    expression: str,
    *,
    resolved_planner_inputs: Mapping[str, Any],
    upstream_outputs: Mapping[str, Mapping[str, Any]],
) -> Any:
    """Resolve a compact `inputs.TypeName` or `node.output` binding expression."""
    if expression.startswith("inputs."):
        planner_type_name = expression.removeprefix("inputs.")
        return resolved_planner_inputs[planner_type_name]

    if "." not in expression:
        return expression

    node_name, output_name = expression.split(".", maxsplit=1)
    return upstream_outputs[node_name][output_name]


def _node_runtime_binding(
    runtime_bindings: Mapping[str, Any],
    *,
    node_name: str,
    input_name: str,
) -> Any | None:
    """Return a node-specific or shared runtime binding when one is present."""
    node_scoped_name = f"{node_name}.{input_name}"
    if node_scoped_name in runtime_bindings:
        return runtime_bindings[node_scoped_name]
    return runtime_bindings.get(input_name)


def _build_node_inputs(
    node: WorkflowNodeSpec,
    *,
    resolved_planner_inputs: Mapping[str, Any],
    upstream_outputs: Mapping[str, Mapping[str, Any]],
    runtime_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """Build handler inputs from spec bindings plus saved runtime bindings."""
    inputs = {
        input_name: _resolve_binding_expression(
            expression,
            resolved_planner_inputs=resolved_planner_inputs,
            upstream_outputs=upstream_outputs,
        )
        for input_name, expression in node.input_bindings.items()
    }

    entry = get_entry(node.reference_name)
    for field_spec in entry.inputs:
        if field_spec.name in inputs:
            continue
        runtime_value = _node_runtime_binding(runtime_bindings, node_name=node.name, input_name=field_spec.name)
        if runtime_value is not None:
            inputs[field_spec.name] = runtime_value

    # Quality-assessment and post-processing nodes can inherit their source
    # result directory from a resolved planner target. Merge those translated
    # inputs only when the spec bindings and runtime bindings did not already
    # set the field.
    inputs.update(
        {
            key: value
            for key, value in _quality_assessment_target_runtime_inputs(
                node.reference_name,
                resolved_planner_inputs,
            ).items()
            if key not in inputs
        }
    )
    return inputs


def _manifest_path_for_output(value: Any) -> Path | None:
    """Return a manifest path for result-directory outputs when present."""
    try:
        output_path = Path(value)
    except TypeError:
        return None
    manifest_path = output_path / "run_manifest.json"
    return manifest_path if manifest_path.exists() else None


def _manifest_paths_for_outputs(outputs: Mapping[str, Any]) -> dict[str, Path]:
    """Collect manifest paths from node outputs that look like result directories."""
    return {
        name: manifest_path
        for name, value in outputs.items()
        if (manifest_path := _manifest_path_for_output(value)) is not None
    }


def _json_ready(value: Any) -> Any:
    """Convert executor values into stable JSON-compatible data."""
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
    """Write a JSON payload through a temporary file before replacing it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n")
    os.replace(temporary_path, path)


def _slurm_run_record_path(source: Path) -> Path:
    """Resolve a Slurm run-record directory or JSON path to the record file."""
    return source / DEFAULT_SLURM_RUN_RECORD_FILENAME if source.is_dir() else source


def load_slurm_run_record(source: Path) -> SlurmRunRecord:
    """Load one durable Slurm run record from a directory or JSON path."""
    record_path = _slurm_run_record_path(source)
    payload = json.loads(record_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != SLURM_RUN_RECORD_SCHEMA_VERSION:
        raise ValueError(f"Unsupported Slurm run record schema version: {schema_version!r}")
    return SlurmRunRecord.from_dict(payload)


def save_slurm_run_record(record: SlurmRunRecord) -> Path:
    """Write a Slurm run record atomically to the path it carries internally.

    Uses a temporary file and ``os.replace`` so the record file is never left
    partially written, even when the process is interrupted mid-write.

    Both the async polling loop in ``slurm_monitor.py`` and synchronous MCP
    handlers call this function.  Callers on the async path should use
    ``save_slurm_run_record_locked`` from ``slurm_monitor.py`` instead, because
    that wrapper takes an exclusive file lock around the read-modify-write
    sequence to prevent concurrent overwrites.

    Args:
        record: Slurm run record to persist.  The record carries its own
            destination path in ``run_record_path``; the caller does not need
            to supply a separate path.

    Returns:
        The path where the record was written, so callers can log or return
        the location without reading it back from the record.
    """
    _write_json_atomically(record.run_record_path, record.to_dict())
    return record.run_record_path


def _local_run_record_path(source: Path) -> Path:
    """Resolve a directory or JSON path to the local run record file."""
    return source / DEFAULT_LOCAL_RUN_RECORD_FILENAME if source.is_dir() else source


def load_local_run_record(source: Path) -> "LocalRunRecord":
    """Read a prior local execution record so a new run can resume from it.

    Checks the file's ``schema_version`` field before loading.  Records
    written by an older version of FLyteTest are rejected here rather than
    silently loaded and then misread — the field set evolves as the resume
    contract grows, and a version mismatch means the stored data should not
    be trusted without a manual review.

    Args:
        source: Run directory that contains ``local_run_record.json``, or a
            direct path to the JSON file.  The run-directory form is the
            normal case; the direct-path form is useful in tests.

    Returns:
        The :class:`LocalRunRecord` ready to hand to
        :meth:`LocalWorkflowSpecExecutor.execute` as *resume_from*, or to
        inspect the prior run's ``node_completion_state``.

    Raises:
        ValueError: When the file's ``schema_version`` does not match
            :data:`LOCAL_RUN_RECORD_SCHEMA_VERSION`.  This happens when the
            record was written by an older code path; callers must not reuse
            such a record without verifying the field layout manually.
    """
    record_path = _local_run_record_path(source)
    payload = json.loads(record_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != LOCAL_RUN_RECORD_SCHEMA_VERSION:
        raise ValueError(f"Unsupported local run record schema version: {schema_version!r}")
    return LocalRunRecord.from_dict(payload)


def save_local_run_record(record: "LocalRunRecord") -> Path:
    """Write a completed local run record as the permanent evidence that all nodes finished.

    Writes through a temporary file and swaps it into place atomically with
    ``os.replace``, so the record file is never left partially written.
    The executor only calls this after every node succeeds, so there is no
    partial record on a failed run that could be mistaken for a completed one.

    Args:
        record: The :class:`LocalRunRecord` to persist.  The record carries
            its own destination path in ``run_record_path``.

    Returns:
        The path where the record was written, so callers can log or return
        the location.
    """
    _write_json_atomically(record.run_record_path, record.to_dict())
    return record.run_record_path


def _validate_resume_identity(
    prior: LocalRunRecord,
    workflow_name: str,
    artifact_path: Path | None,
    *,
    current_cache_key: str | None = None,
) -> str | None:
    """Reject a prior run record whose workflow or content identity has changed.

    Called twice during a resume: first with only the workflow name and
    artifact path as cheap pre-filters, then again after planner inputs are
    resolved so the deterministic cache-key comparison can act as the
    authoritative content-level gate.  Running the cheap checks first avoids
    the planner-resolution cost when the workflow name alone does not match.

    Args:
        prior: Prior local run record being evaluated for reuse.
        workflow_name: Name of the workflow the caller is about to run.  A
            mismatch means the caller is pointing at the wrong run directory.
        artifact_path: Path to the frozen recipe file being submitted.  Only
            compared when the prior record also carries a path; ``None`` skips
            the path check without failing, which handles the in-memory
            artifact case.
        current_cache_key: Deterministic SHA-256 digest of the current frozen
            workflow, binding plan, and resolved inputs.  When provided this
            is the definitive test — a mismatch means the biology or inputs
            changed and the prior completion state cannot be safely reused.

    Returns:
        ``None`` when the prior record is safe to reuse.  A human-readable
        mismatch description when it is not, ready to embed in
        ``LocalSpecExecutionResult.limitations``.
    """
    mismatches: list[str] = []
    if prior.workflow_name != workflow_name:
        mismatches.append(
            f"workflow name mismatch: prior={prior.workflow_name!r}, "
            f"current={workflow_name!r}"
        )
    if artifact_path is not None and prior.artifact_path is not None:
        if prior.artifact_path != artifact_path:
            mismatches.append(
                f"artifact path mismatch: prior={prior.artifact_path!r}, "
                f"current={artifact_path!r}"
            )
    # Content-level cache-key comparison as the authoritative gate.
    if current_cache_key is not None and prior.cache_identity_key is not None:
        if prior.cache_identity_key != current_cache_key:
            mismatches.append(
                f"cache identity key mismatch: prior={prior.cache_identity_key!r}, "
                f"current={current_cache_key!r}"
            )
    if mismatches:
        return (
            "Resume identity mismatch — prior run record does not match "
            "the current artifact: " + "; ".join(mismatches)
        )
    return None


def parse_sbatch_job_id(stdout: str, stderr: str = "") -> str:
    """Parse the Slurm job ID emitted by `sbatch`."""
    combined = "\n".join(stream for stream in (stdout, stderr) if stream)
    submitted_match = re.search(r"\bSubmitted\s+batch\s+job\s+([0-9]+(?:\.[0-9]+)?)\b", combined)
    if submitted_match:
        return submitted_match.group(1)
    generic_match = re.search(r"\b([0-9]{2,}(?:\.[0-9]+)?)\b", combined)
    if generic_match:
        return generic_match.group(1)
    raise ValueError("Could not parse a Slurm job ID from sbatch output.")


_TERMINAL_SLURM_STATES = {
    "BOOT_FAIL",
    "CANCELLED",
    "COMPLETED",
    "DEADLINE",
    "FAILED",
    "NODE_FAIL",
    "OUT_OF_MEMORY",
    "PREEMPTED",
    "REQUEUED",
    "REVOKED",
    "SPECIAL_EXIT",
    "TIMEOUT",
}
_RETRYABLE_SLURM_STATES = {
    "BOOT_FAIL",
    "NODE_FAIL",
    "PREEMPTED",
    "REVOKED",
}
_RETRYABLE_REASON_PATTERNS = (
    "node failure",
    "launch failed",
    "system failure",
    "communication connection failure",
    "socket timed out",
    "failed to connect",
)

_SLURM_AUTHENTICATED_ENVIRONMENT_GUIDANCE = (
    "Start FLyteTest inside an already-authenticated scheduler environment such as "
    "a login-node shell, `tmux`, or `screen` session."
)
_SLURM_REACHABILITY_PATTERNS = (
    "unable to contact slurm controller",
    "unable to establish configuration source",
    "could not establish a configuration source",
    "communication connection failure",
    "connection refused",
    "socket timed out",
    "failed to connect",
    "no route to host",
)


def _normalize_scheduler_state(value: str | None) -> str | None:
    """Normalize a scheduler state into a compact uppercase state name."""
    if value in (None, ""):
        return None
    return str(value).strip().split()[0].split("+")[0].split("(")[0].upper()


def _scheduler_state_for_classification(record: SlurmRunRecord) -> str | None:
    """Prefer the durable terminal state when classifying retryability."""
    return record.final_scheduler_state or record.scheduler_state


def _scheduler_exit_is_nonzero(exit_code: str | None) -> bool:
    """Return whether a recorded Slurm exit code represents a nonzero outcome."""
    if exit_code in (None, ""):
        return False
    status_code, _, signal_code = str(exit_code).partition(":")
    return status_code not in {"", "0"} or signal_code not in {"", "0"}


def classify_slurm_failure(record: SlurmRunRecord) -> SlurmFailureClassification:
    """Classify one durable Slurm record for retry and lifecycle handling.

    Args:
        record: Durable Slurm run record whose scheduler state and exit data
            should be interpreted.

    Returns:
        A classification record with the retryability flag and diagnostic
        detail needed by status, cancel, and retry flows.
    """
    state = _scheduler_state_for_classification(record)
    reason = record.scheduler_reason
    exit_code = record.scheduler_exit_code
    detail_parts = [part for part in (reason, exit_code) if part not in (None, "")]
    detail = " | ".join(detail_parts)

    if state in (None, ""):
        return SlurmFailureClassification(
            status="unknown",
            retryable=False,
            scheduler_state=state,
            exit_code=exit_code,
            reason=reason,
            detail="No scheduler state is recorded yet for this Slurm run.",
        )

    if state == "COMPLETED":
        return SlurmFailureClassification(
            status="completed",
            retryable=False,
            scheduler_state=state,
            exit_code=exit_code,
            reason=reason,
            detail="The Slurm job completed successfully and should not be retried.",
        )

    if state not in _TERMINAL_SLURM_STATES and state != "cancellation_requested":
        return SlurmFailureClassification(
            status="not_terminal",
            retryable=False,
            scheduler_state=state,
            exit_code=exit_code,
            reason=reason,
            detail="Retry is only available after the scheduler records a terminal job state.",
        )

    if state in _RETRYABLE_SLURM_STATES:
        return SlurmFailureClassification(
            status="retryable_failure",
            retryable=True,
            failure_class="scheduler_infrastructure",
            scheduler_state=state,
            exit_code=exit_code,
            reason=reason,
            detail=detail or "The scheduler recorded an infrastructure failure that can be retried conservatively.",
        )

    if state == "FAILED":
        lowered_reason = (reason or "").lower()
        if any(pattern in lowered_reason for pattern in _RETRYABLE_REASON_PATTERNS) and not _scheduler_exit_is_nonzero(exit_code):
            return SlurmFailureClassification(
                status="retryable_failure",
                retryable=True,
                failure_class="scheduler_infrastructure",
                scheduler_state=state,
                exit_code=exit_code,
                reason=reason,
                detail=detail or "The scheduler reported an infrastructure-style failure without a nonzero job exit code.",
            )
        return SlurmFailureClassification(
            status="terminal_failure",
            retryable=False,
            failure_class="workflow_exit_failure",
            scheduler_state=state,
            exit_code=exit_code,
            reason=reason,
            detail=detail or "The Slurm job failed with an application or workflow exit status.",
        )

    if state in {"OUT_OF_MEMORY", "TIMEOUT", "DEADLINE"}:
        return SlurmFailureClassification(
            status="terminal_failure",
            retryable=False,
            failure_class="resource_exhaustion",
            scheduler_state=state,
            exit_code=exit_code,
            reason=reason,
            detail=detail or "The recorded scheduler state indicates a resource-limit failure, so a retry would likely repeat the same outcome.",
        )

    if state in {"CANCELLED", "cancellation_requested"}:
        return SlurmFailureClassification(
            status="terminal_failure",
            retryable=False,
            failure_class="cancelled",
            scheduler_state=state,
            exit_code=exit_code,
            reason=reason,
            detail=detail or "Cancelled jobs are treated as terminal and are not retried automatically.",
        )

    if state == "REQUEUED":
        return SlurmFailureClassification(
            status="terminal_failure",
            retryable=False,
            failure_class="scheduler_requeue",
            scheduler_state=state,
            exit_code=exit_code,
            reason=reason,
            detail=detail or "Slurm already requeued this job, so FLyteTest does not submit an additional retry.",
        )

    return SlurmFailureClassification(
        status="terminal_failure",
        retryable=False,
        failure_class="terminal_scheduler_failure",
        scheduler_state=state,
        exit_code=exit_code,
        reason=reason,
        detail=detail or "The recorded terminal scheduler state is not classified as retryable.",
    )


def _command_is_available(command: str) -> bool:
    """Return whether one command appears to be available on the current PATH."""
    return shutil.which(command) is not None


def _format_slurm_command_list(commands: Sequence[str]) -> str:
    """Render a short backtick-wrapped command list for user-facing diagnostics."""
    wrapped = [f"`{command}`" for command in commands]
    if len(wrapped) == 1:
        return wrapped[0]
    if len(wrapped) == 2:
        return f"{wrapped[0]} and {wrapped[1]}"
    return f"{', '.join(wrapped[:-1])}, and {wrapped[-1]}"


def _missing_slurm_command_limitation(*, action: str, commands: Sequence[str], require_all: bool = True) -> str:
    """Describe a missing-command Slurm access boundary in one actionable sentence."""
    requirement = (
        f"requires {_format_slurm_command_list(commands)} on PATH"
        if require_all
        else f"requires at least one of {_format_slurm_command_list(commands)} on PATH"
    )
    return f"Slurm {action} {requirement}. {_SLURM_AUTHENTICATED_ENVIRONMENT_GUIDANCE}"


def _partial_slurm_command_limitation(*, action: str, commands: Sequence[str]) -> str:
    """Describe a degraded command set without failing the whole lifecycle action."""
    return (
        f"Slurm {action} cannot use {_format_slurm_command_list(commands)} in the current "
        "environment and will rely on the remaining scheduler commands."
    )


def _looks_like_scheduler_reachability_issue(text: str) -> bool:
    """Heuristically detect scheduler failures caused by the wrong execution context."""
    lowered = text.lower()
    return any(pattern in lowered for pattern in _SLURM_REACHABILITY_PATTERNS)


def _slurm_command_failure_limitation(*, command: str, stderr: str, action: str) -> str:
    """Turn one Slurm CLI failure into a user-facing limitation."""
    detail = stderr.strip()
    if _looks_like_scheduler_reachability_issue(detail):
        return (
            f"`{command}` is available, but the current environment could not reach the "
            f"Slurm scheduler while attempting {action}: {detail}. "
            f"{_SLURM_AUTHENTICATED_ENVIRONMENT_GUIDANCE}"
        )
    return f"{command} failed during Slurm {action}: {detail}"


def _first_nonempty_line(value: str) -> str | None:
    """Return the first non-empty line from command output."""
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _parse_squeue_state(stdout: str) -> str | None:
    """Parse the state emitted by `squeue --format=%T`."""
    return _normalize_scheduler_state(_first_nonempty_line(stdout))


def _parse_scontrol_fields(stdout: str) -> dict[str, str]:
    """Parse key-value fields from `scontrol show job` output."""
    fields: dict[str, str] = {}
    for token in stdout.replace("\n", " ").split():
        if "=" not in token:
            continue
        key, value = token.split("=", maxsplit=1)
        fields[key] = value
    return fields


def _parse_sacct_fields(stdout: str, job_id: str) -> dict[str, str]:
    """Parse pipe-delimited `sacct` output for the main job or batch step."""
    fallback: dict[str, str] = {}
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            continue
        parts = stripped.split("|")
        if len(parts) < 3:
            continue
        row = {"JobID": parts[0], "State": parts[1], "ExitCode": parts[2]}
        fallback = fallback or row
        if parts[0] == job_id or parts[0] == f"{job_id}.batch":
            return row
    return fallback


def _slug(value: str, *, max_length: int = 48) -> str:
    """Return a compact Slurm-safe identifier fragment."""
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return (slug or "workflow")[:max_length]


def _normalize_slurm_memory(memory: str | None) -> str | None:
    """Convert common recipe memory spellings into Slurm-friendly values."""
    if memory is None:
        return None
    normalized = memory.strip()
    if normalized.lower().endswith("gib"):
        return normalized[:-3] + "G"
    if normalized.lower().endswith("gi"):
        return normalized[:-2] + "G"
    if normalized.lower().endswith("gb"):
        return normalized[:-2] + "G"
    if normalized.lower().endswith("mib"):
        return normalized[:-3] + "M"
    if normalized.lower().endswith("mi"):
        return normalized[:-2] + "M"
    if normalized.lower().endswith("mb"):
        return normalized[:-2] + "M"
    return normalized


# ---------------------------------------------------------------------------
# Slurm resource-escalation retry helpers
# ---------------------------------------------------------------------------

DEFAULT_SLURM_MODULE_LOADS: tuple[str, ...] = ("python/3.11.9", "apptainer/1.4.1")
"""Default environment modules loaded when none are specified in the recipe."""

_RETRY_RESOURCE_OVERRIDE_FIELDS: frozenset[str] = frozenset(
    {"cpu", "memory", "walltime", "queue", "account", "gpu"}
)


def _coerce_retry_resource_overrides(
    value: Mapping[str, Any] | ResourceSpec | None,
) -> tuple[ResourceSpec | None, tuple[str, ...]]:
    """Normalize MCP retry overrides into a typed resource spec.

    Accepts a plain mapping at the API edge so MCP callers do not need to
    construct a full ``ResourceSpec``, then validates that all keys are
    known escalation fields.  Durable records always store a typed
    ``ResourceSpec``.

    Args:
        value: Optional MCP-provided escalation values.  Mappings are
            accepted at the API edge; durable records store a typed
            ``ResourceSpec``.

    Returns:
        A ``(ResourceSpec | None, limitations)`` pair.  A non-empty
        limitations tuple means the caller should decline without
        submitting a job.
    """
    if value is None:
        return None, ()
    if isinstance(value, ResourceSpec):
        return value, ()

    unknown = sorted(set(value) - _RETRY_RESOURCE_OVERRIDE_FIELDS)
    if unknown:
        return None, (f"Unsupported resource override key(s): {', '.join(unknown)}.",)

    kwargs: dict[str, str] = {
        key: str(raw)
        for key, raw in value.items()
        if key in _RETRY_RESOURCE_OVERRIDE_FIELDS and raw not in (None, "")
    }
    if not kwargs:
        return None, (
            "resource_overrides was provided but did not contain any non-empty override values.",
        )
    return ResourceSpec(**kwargs), ()


def _effective_resource_spec(
    frozen_resource_spec: ResourceSpec | None,
    resource_overrides: ResourceSpec | None,
) -> ResourceSpec | None:
    """Overlay retry escalation values onto the frozen Slurm resource spec.

    The frozen artifact is never modified.  Overrides are applied only at
    submission time so the saved recipe remains an exact record of the
    original intent.

    Args:
        frozen_resource_spec: Resource spec from the frozen recipe artifact.
        resource_overrides: Explicit user-requested escalation values from
            a retry call.  ``None`` means use the frozen spec unchanged.

    Returns:
        The effective resource spec used for the Slurm submission, or
        ``None`` when both sides are absent.
    """
    if resource_overrides is None:
        return frozen_resource_spec
    base = frozen_resource_spec or ResourceSpec()
    return replace(
        base,
        cpu=resource_overrides.cpu or base.cpu,
        memory=resource_overrides.memory or base.memory,
        gpu=resource_overrides.gpu or base.gpu,
        queue=resource_overrides.queue or base.queue,
        account=resource_overrides.account or base.account,
        walltime=resource_overrides.walltime or base.walltime,
        execution_class=resource_overrides.execution_class or base.execution_class,
        module_loads=resource_overrides.module_loads or base.module_loads,
        notes=(*base.notes, *resource_overrides.notes),
    )


def _slurm_module_load_lines(resource_spec: ResourceSpec | None) -> list[str]:
    """Render scheduler module-load commands for the generated Slurm script.

    Falls back to ``DEFAULT_SLURM_MODULE_LOADS`` when the resource spec
    carries no explicit ``module_loads`` so existing recipes continue to
    get the same default modules without change.  All module names are
    shell-quoted so spaces or special characters in a name do not break
    the generated script.

    Args:
        resource_spec: Effective resource spec for this submission, or
            ``None`` to use defaults.

    Returns:
        A list of ``  module load <quoted_name>`` lines ready to embed
        in the submission script body.
    """
    module_loads = resource_spec.module_loads if resource_spec is not None else ()
    selected = module_loads or DEFAULT_SLURM_MODULE_LOADS
    return [f"  module load {shlex.quote(name)}" for name in selected]


def _slurm_directives(
    *,
    workflow_name: str,
    run_id: str,
    stdout_path: Path,
    stderr_path: Path,
    resource_spec: ResourceSpec | None,
) -> list[str]:
    """Translate a frozen resource spec into ``#SBATCH`` directive lines.

    The job name, stdout log, and stderr log are always included.  CPU,
    memory, walltime, partition, account, and GPU directives are added only
    when the corresponding field is set in *resource_spec*.  When
    *resource_spec* is ``None``, only the three baseline directives are
    returned and the cluster's default queue policy applies.

    Memory values are normalised from common recipe spellings (``GiB``,
    ``Gi``, ``GB``) to Slurm-accepted suffixes (``G``) before the directive
    is written, so recipe authors can use any conventional notation.

    Args:
        workflow_name: Selects the job-name prefix.  Protein-evidence
            alignment jobs use the short ``pe-`` prefix to stay within
            Slurm's job-name character limit; everything else uses
            ``flytetest-``.
        run_id: Appended to the job name so Slurm accounting entries and
            the run directory on disk share a correlatable identifier.
        stdout_path: Passed verbatim to ``--output``; the ``%j`` token is
            preserved for scheduler substitution at job acceptance time.
        stderr_path: Passed verbatim to ``--error``.
        resource_spec: CPU, memory, walltime, partition, account, and GPU
            constraints from the frozen binding plan.  ``None`` means no
            cluster-specific constraints are embedded in the script.

    Returns:
        Ordered list of ``#SBATCH`` directive strings ready to be embedded
        in the submission script immediately after the shebang line.
    """
    job_prefix = "pe" if workflow_name == "protein_evidence_alignment" else "flytetest"
    job_name = _slug(f"{job_prefix}-{run_id}", max_length=32)
    directives = [
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --output={stdout_path}",
        f"#SBATCH --error={stderr_path}",
    ]
    if resource_spec is None:
        return directives
    if resource_spec.cpu:
        directives.append(f"#SBATCH --cpus-per-task={resource_spec.cpu}")
    if memory := _normalize_slurm_memory(resource_spec.memory):
        directives.append(f"#SBATCH --mem={memory}")
    if resource_spec.queue:
        directives.append(f"#SBATCH --partition={resource_spec.queue}")
    if resource_spec.account:
        directives.append(f"#SBATCH --account={resource_spec.account}")
    if resource_spec.walltime:
        directives.append(f"#SBATCH --time={resource_spec.walltime}")
    if resource_spec.gpu:
        directives.append(f"#SBATCH --gres=gpu:{resource_spec.gpu}")
    return directives


def render_slurm_script(
    *,
    artifact_path: Path,
    workflow_name: str,
    run_id: str,
    stdout_path: Path,
    stderr_path: Path,
    resource_spec: ResourceSpec | None,
    repo_root: Path,
    python_executable: str,
    resume_from_local_record: Path | None = None,
) -> str:
    """Render the bash script that Slurm runs when the job lands on a compute node.

    The generated script is self-contained so the compute node does not need
    FLyteTest to be pre-installed beyond what the repo tree and ``.venv``
    provide.  Its execution sequence is:

    1. ``cd`` to *repo_root* so all relative paths inside the recipe resolve
       against the same checkout that produced it.
    2. Load ``python/3.11.9`` and ``apptainer/1.4.1`` via the environment
       module system when available — required on the HPC cluster but silently
       skipped on hosts without ``module``.
    3. Activate the project ``.venv`` when it exists.
    4. Export ``FLYTETEST_TMPDIR`` and ``TMPDIR`` pointing at
       ``results/.tmp`` under the repo, so tools write temporary files inside
       the project tree rather than a potentially small node-local ``/tmp``.
    5. Call ``_run_local_recipe_impl`` against the frozen *artifact_path*,
       optionally passing *resume_from_local_record* so already-completed
       local nodes are skipped on the cluster.
    6. Exit 0 on success or 1 when the recipe returns ``supported=False``,
       so Slurm records the job as ``FAILED`` rather than silently
       ``COMPLETED`` when the execution reports an error.

    Args:
        artifact_path: Frozen recipe JSON baked verbatim into the script.
            The compute node runs exactly this artifact regardless of
            subsequent changes to the recipe directory.
        workflow_name: Used by :func:`_slurm_directives` to pick the job-name
            prefix (``pe-`` for protein-evidence alignment,
            ``flytetest-`` otherwise).
        run_id: Unique identifier used in the Slurm job name so accounting
            entries and the run directory share a correlatable handle.
        stdout_path: ``#SBATCH --output`` path; the ``%j`` token is preserved
            so the scheduler substitutes the accepted job ID.
        stderr_path: ``#SBATCH --error`` path.
        resource_spec: CPU, memory, walltime, partition, account, and GPU
            constraints translated into ``#SBATCH`` directives.  ``None``
            lets the cluster's default queue policy apply.
        repo_root: Absolute path to the FLyteTest checkout on the shared
            filesystem.  The script ``cd``s here before executing anything;
            the path must be accessible from compute nodes.
        python_executable: Python interpreter embedded as the default
            ``PYTHON_BIN``.  Overridden by the ``PYTHON_BIN`` environment
            variable at runtime so cluster admins can pin a specific
            interpreter without regenerating the script.
        resume_from_local_record: When set, the embedded Python call passes
            this record path to ``_run_local_recipe_impl`` so nodes that
            finished in a prior local run are skipped on the cluster.

    Returns:
        Bash script text ready to be written to disk and passed to
        ``sbatch``.  No side effects; the caller is responsible for
        writing the file and setting permissions.
    """
    python_call = f"result = _run_local_recipe_impl({str(artifact_path)!r})"
    if resume_from_local_record is not None:
        python_call = (
            f"result = _run_local_recipe_impl({str(artifact_path)!r}, "
            f"resume_from_local_record={str(resume_from_local_record)!r})"
        )
    python_code = (
        "from flytetest.server import _run_local_recipe_impl; "
        "import json, sys; "
        f"{python_call}; "
        "print(json.dumps(result, sort_keys=True)); "
        "sys.exit(0 if result.get('supported') else 1)"
    )
    directives = _slurm_directives(
        workflow_name=workflow_name,
        run_id=run_id,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        resource_spec=resource_spec,
    )
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            *directives,
            "set -euo pipefail",
            f"cd {shlex.quote(str(repo_root))}",
            "if command -v module >/dev/null 2>&1; then",
            *_slurm_module_load_lines(resource_spec),
            "fi",
            f"if [[ -f {shlex.quote(str(repo_root / '.venv/bin/activate'))} ]]; then",
            f"  source {shlex.quote(str(repo_root / '.venv/bin/activate'))}",
            "fi",
            f"mkdir -p {shlex.quote(str(repo_root / 'results/.tmp'))}",
            f"export FLYTETEST_TMPDIR={shlex.quote(str(repo_root / 'results/.tmp'))}",
            "export TMPDIR=\"$FLYTETEST_TMPDIR\"",
            f"export PYTHONPATH={shlex.quote(str(repo_root / 'src'))}${{PYTHONPATH:+:$PYTHONPATH}}",
            "PYTHON_BIN=\"${PYTHON_BIN:-$(command -v python3)}\"",
            f"$PYTHON_BIN -c {shlex.quote(python_code)}",
            "",
        ]
    )


def _created_at() -> str:
    """Return a UTC timestamp suitable for a durable run record."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id_for_artifact(artifact: SavedWorkflowSpecArtifact, artifact_path: Path, submitted_at: str) -> str:
    """Build a run-scoped ID that is not keyed only by recipe name."""
    digest_source = f"{artifact_path.resolve()}|{artifact.workflow_spec.name}|{artifact.created_at}|{submitted_at}"
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    timestamp = submitted_at.replace(":", "").replace("-", "").replace("Z", "Z")
    return f"{timestamp}-{_slug(artifact.workflow_spec.name, max_length=32)}-{digest}"


def _allocate_run_dir(run_root: Path, requested_run_id: str) -> tuple[str, Path]:
    """Reserve a unique run directory even when submissions happen in the same second."""
    run_id = requested_run_id
    run_dir = run_root / run_id
    suffix = 1
    while run_dir.exists():
        run_id = f"{requested_run_id}-retry{suffix}"
        run_dir = run_root / run_id
        suffix += 1
    return run_id, run_dir


class LocalWorkflowSpecExecutor:
    """Execute saved workflow specs locally through registered stage handlers."""

    def __init__(
        self,
        handlers: Mapping[str, RegisteredNodeHandler],
        *,
        resolver: AssetResolver | None = None,
        run_root: Path | None = None,
    ) -> None:
        """Create a local executor with explicit handlers and optional run records.

        Args:
            handlers: Mapping from node reference names to the local handler
                that can execute each supported stage.
            resolver: Asset resolver used to discover planner-facing inputs
                from local manifests and saved bundles.
            run_root: Optional directory where durable :class:`LocalRunRecord`
                files are written after successful local execution.
        """
        self._handlers = dict(handlers)
        self._resolver = resolver or LocalManifestAssetResolver()
        self._run_root = run_root

    def execute(
        self,
        artifact_source: SavedWorkflowSpecArtifact | Path,
        *,
        explicit_bindings: Mapping[str, Any] | None = None,
        manifest_sources: Sequence[Path | Mapping[str, Any]] = (),
        result_bundles: Sequence[Any] = (),
        resume_from: Path | None = None,
    ) -> LocalSpecExecutionResult:
        """Execute one saved spec through local handlers, optionally resuming a prior run.

        When *resume_from* points to an existing :class:`LocalRunRecord`,
        completed nodes are skipped and their outputs are reused after the
        prior record is validated against the current artifact identity.

        Args:
            artifact_source: Saved workflow-spec artifact or path that should
                be loaded before any node handlers run.
            explicit_bindings: User-supplied planner values that override
                discovered inputs from manifests or result bundles.
            manifest_sources: Local manifest files or mappings that may satisfy
                planner inputs for the current execution.
            result_bundles: Previously materialized result directories that can
                contribute reusable planner inputs.
            resume_from: Optional path to a prior local run record whose
                completed nodes should be reused.

        Returns:
            A :class:`LocalSpecExecutionResult` describing whether every node
            ran locally and, if so, the final outputs and recorded assumptions.
        """
        artifact = _artifact_from_source(artifact_source)
        workflow_spec = artifact.workflow_spec
        binding_plan = artifact.binding_plan

        # Load and validate the prior run record when resuming (fast pre-filters).
        prior_record: LocalRunRecord | None = None
        prior_node_outputs: dict[str, Mapping[str, Any]] = {}
        prior_node_results_by_name: dict[str, LocalNodeExecutionResult] = {}
        if resume_from is not None:
            prior_record = load_local_run_record(resume_from)
            artifact_path_for_check = _artifact_path_from_source(artifact_source)
            mismatch = _validate_resume_identity(prior_record, workflow_spec.name, artifact_path_for_check)
            if mismatch:
                return LocalSpecExecutionResult(
                    supported=False,
                    workflow_name=workflow_spec.name,
                    execution_profile=binding_plan.execution_profile,
                    resolved_planner_inputs={},
                    limitations=(mismatch,),
                )
            # Index prior node results for fast lookup when skipping.
            prior_node_outputs: dict[str, Mapping[str, Any]] = {
                nr.node_name: nr.outputs for nr in prior_record.node_results
            }
            prior_node_results_by_name: dict[str, LocalNodeExecutionResult] = {
                nr.node_name: nr for nr in prior_record.node_results
            }

        resolved_planner_inputs, resolver_limitations, resolver_assumptions = _resolve_planner_inputs(
            artifact,
            explicit_bindings=explicit_bindings or {},
            manifest_sources=manifest_sources,
            result_bundles=result_bundles,
            resolver=self._resolver,
        )

        # Compute the deterministic cache identity key from frozen inputs.
        computed_cache_key = cache_identity_key(
            workflow_spec.to_dict(),
            binding_plan.to_dict(),
            dict(resolved_planner_inputs),
        )

        # Authoritative cache-key gate for resume (runs after planner inputs
        # are resolved so the key is available).
        if prior_record is not None and computed_cache_key is not None:
            artifact_path_for_check = _artifact_path_from_source(artifact_source)
            key_mismatch = _validate_resume_identity(
                prior_record, workflow_spec.name, artifact_path_for_check,
                current_cache_key=computed_cache_key,
            )
            if key_mismatch:
                return LocalSpecExecutionResult(
                    supported=False,
                    workflow_name=workflow_spec.name,
                    execution_profile=binding_plan.execution_profile,
                    resolved_planner_inputs=dict(resolved_planner_inputs),
                    limitations=(key_mismatch,),
                )

        if resolver_limitations:
            return LocalSpecExecutionResult(
                supported=False,
                workflow_name=workflow_spec.name,
                execution_profile=binding_plan.execution_profile,
                resolved_planner_inputs=resolved_planner_inputs,
                resource_spec=binding_plan.resource_spec,
                runtime_image=binding_plan.runtime_image,
                limitations=resolver_limitations,
                assumptions=resolver_assumptions,
            )

        upstream_outputs: dict[str, Mapping[str, Any]] = {}
        node_results: list[LocalNodeExecutionResult] = []
        node_skip_reasons: dict[str, str] = {}
        assumptions = [*artifact.assumptions, *binding_plan.assumptions, *resolver_assumptions]

        for node in workflow_spec.nodes:
            # Check whether this node can be skipped from the prior record.
            if (
                prior_record is not None
                and prior_record.node_completion_state.get(node.name) is True
                and node.name in prior_node_outputs
            ):
                upstream_outputs[node.name] = prior_node_outputs[node.name]
                node_results.append(prior_node_results_by_name[node.name])
                node_skip_reasons[node.name] = (
                    f"Reused from prior run {prior_record.run_id}: "
                    f"node was completed in the prior record."
                )
                continue

            get_entry(node.reference_name)
            handler = self._handlers.get(node.reference_name)
            if handler is None:
                return LocalSpecExecutionResult(
                    supported=False,
                    workflow_name=workflow_spec.name,
                    execution_profile=binding_plan.execution_profile,
                    resolved_planner_inputs=resolved_planner_inputs,
                    resource_spec=binding_plan.resource_spec,
                    runtime_image=binding_plan.runtime_image,
                    node_results=tuple(node_results),
                    limitations=(f"No local handler is available for `{node.reference_name}`.",),
                    assumptions=tuple(dict.fromkeys(assumptions)),
                )

            node_inputs = _build_node_inputs(
                node,
                resolved_planner_inputs=resolved_planner_inputs,
                upstream_outputs=upstream_outputs,
                runtime_bindings=binding_plan.runtime_bindings,
            )
            request = LocalNodeExecutionRequest(
                node=node,
                inputs=node_inputs,
                resolved_planner_inputs=resolved_planner_inputs,
                upstream_outputs=upstream_outputs,
                binding_plan_target=binding_plan.target_name,
                execution_profile=binding_plan.execution_profile,
                resource_spec=binding_plan.resource_spec,
                runtime_image=binding_plan.runtime_image,
            )
            outputs = dict(handler(request))
            upstream_outputs[node.name] = outputs
            node_results.append(
                LocalNodeExecutionResult(
                    node_name=node.name,
                    reference_name=node.reference_name,
                    outputs=outputs,
                    manifest_paths=_manifest_paths_for_outputs(outputs),
                )
            )

        final_outputs = {
            binding.output_name: upstream_outputs[binding.source_node][binding.source_output]
            for binding in workflow_spec.final_output_bindings
        }

        # Persist a durable local run record when the executor was constructed
        # with a run_root and the artifact was loaded from a filesystem path.
        # Records are only written after every node succeeds so incomplete
        # runs do not produce a partially-filled record that could be
        # mistaken for a completed execution.
        if self._run_root is not None:
            artifact_path = _artifact_path_from_source(artifact_source)
            completed_at = _created_at()
            if artifact_path is not None:
                run_id, run_dir = _allocate_run_dir(
                    self._run_root,
                    _run_id_for_artifact(artifact, artifact_path, completed_at),
                )
            else:
                # Artifact provided as an in-memory object; use workflow name
                # and timestamp for the run directory without a path digest.
                run_id = f"{completed_at.replace(':', '').replace('-', '').replace('Z', 'Z')}-{_slug(workflow_spec.name)}"
                run_id, run_dir = _allocate_run_dir(self._run_root, run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            resume_assumptions = list(assumptions)
            if prior_record is not None:
                resume_assumptions.append(
                    f"Resumed from prior run {prior_record.run_id}; "
                    f"{len(node_skip_reasons)} node(s) reused."
                )
            local_run_record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id=run_id,
                workflow_name=workflow_spec.name,
                run_record_path=run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at=completed_at,
                execution_profile=binding_plan.execution_profile or "local",
                resolved_planner_inputs=dict(resolved_planner_inputs),
                binding_plan_target=binding_plan.target_name,
                node_completion_state={nr.node_name: True for nr in node_results},
                node_results=tuple(node_results),
                artifact_path=artifact_path,
                resource_spec=binding_plan.resource_spec,
                runtime_image=binding_plan.runtime_image,
                final_outputs=dict(final_outputs),
                completed_at=completed_at,
                node_skip_reasons=dict(node_skip_reasons),
                cache_identity_key=computed_cache_key,
                assumptions=tuple(dict.fromkeys(resume_assumptions)),
            )
            save_local_run_record(local_run_record)

        return LocalSpecExecutionResult(
            supported=True,
            workflow_name=workflow_spec.name,
            execution_profile=binding_plan.execution_profile,
            resolved_planner_inputs=resolved_planner_inputs,
            resource_spec=binding_plan.resource_spec,
            runtime_image=binding_plan.runtime_image,
            node_results=tuple(node_results),
            final_outputs=final_outputs,
            assumptions=tuple(dict.fromkeys(assumptions)),
        )


class SlurmWorkflowSpecExecutor:
    """Submit, reconcile, cancel, and retry saved workflow-spec artifacts on Slurm."""

    def __init__(
        self,
        *,
        run_root: Path,
        repo_root: Path,
        python_executable: str | None = None,
        sbatch_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        scheduler_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        command_available: Callable[[str], bool] = _command_is_available,
    ) -> None:
        """Create a Slurm executor with explicit filesystem and command policy.

        Args:
            run_root: Root directory under which durable Slurm run records are
                created.
            repo_root: Repository root used when rendering submission scripts
                and resolving project-local paths.
            python_executable: Python interpreter to embed in the generated
                Slurm script.
            sbatch_runner: Injectable submission runner used to submit the
                generated script.
            scheduler_runner: Injectable scheduler runner used for polling and
                cancellation commands.
            command_available: Command probe used to gate Slurm lifecycle
                operations when scheduler tools are missing.
        """
        self._run_root = run_root
        self._repo_root = repo_root
        self._python_executable = python_executable or sys.executable
        self._sbatch_runner = sbatch_runner
        self._scheduler_runner = scheduler_runner
        self._command_available = command_available

    def _run_scheduler_command(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run one scheduler command with the executor's injectable runner."""
        return self._scheduler_runner(
            args,
            capture_output=True,
            text=True,
            check=False,
        )

    def _missing_commands(self, commands: Sequence[str]) -> tuple[str, ...]:
        """Return the subset of scheduler commands that are not available."""
        return tuple(command for command in commands if not self._command_available(command))

    def _scheduler_snapshot(self, record: SlurmRunRecord) -> SlurmSchedulerSnapshot:
        """Poll Slurm commands and merge their observed state into one snapshot."""
        limitations: list[str] = []
        squeue_stdout = ""
        scontrol_stdout = ""
        sacct_stdout = ""
        squeue_state: str | None = None
        scontrol_fields: dict[str, str] = {}
        sacct_fields: dict[str, str] = {}
        missing_commands = self._missing_commands(("squeue", "scontrol", "sacct"))
        if missing_commands:
            if len(missing_commands) == 3:
                limitations.append(
                    _missing_slurm_command_limitation(
                        action="monitoring",
                        commands=("squeue", "scontrol", "sacct"),
                        require_all=False,
                    )
                )
            else:
                limitations.append(
                    _partial_slurm_command_limitation(action="monitoring", commands=missing_commands)
                )

        if "squeue" not in missing_commands:
            try:
                squeue = self._run_scheduler_command(["squeue", "--noheader", "--jobs", record.job_id, "--format=%T"])
                squeue_stdout = squeue.stdout or ""
                if squeue.returncode == 0:
                    squeue_state = _parse_squeue_state(squeue_stdout)
                else:
                    detail = squeue.stderr or squeue.stdout or ""
                    if detail.strip():
                        limitations.append(
                            _slurm_command_failure_limitation(
                                command="squeue",
                                stderr=detail,
                                action="monitoring",
                            )
                        )
            except OSError as exc:
                limitations.append(f"squeue could not be executed: {exc}")

        if "scontrol" not in missing_commands:
            try:
                scontrol = self._run_scheduler_command(["scontrol", "show", "job", record.job_id])
                scontrol_stdout = scontrol.stdout or ""
                if scontrol.returncode == 0:
                    scontrol_fields = _parse_scontrol_fields(scontrol_stdout)
                else:
                    detail = scontrol.stderr or scontrol.stdout or ""
                    if detail.strip():
                        limitations.append(
                            _slurm_command_failure_limitation(
                                command="scontrol",
                                stderr=detail,
                                action="monitoring",
                            )
                        )
            except OSError as exc:
                limitations.append(f"scontrol could not be executed: {exc}")

        if "sacct" not in missing_commands:
            try:
                sacct = self._run_scheduler_command(
                    ["sacct", "-n", "-P", "-j", record.job_id, "--format=JobID,State,ExitCode"]
                )
                sacct_stdout = sacct.stdout or ""
                if sacct.returncode == 0:
                    sacct_fields = _parse_sacct_fields(sacct_stdout, record.job_id)
                else:
                    detail = sacct.stderr or sacct.stdout or ""
                    if detail.strip():
                        limitations.append(
                            _slurm_command_failure_limitation(
                                command="sacct",
                                stderr=detail,
                                action="monitoring",
                            )
                        )
            except OSError as exc:
                limitations.append(f"sacct could not be executed: {exc}")

        scontrol_state = _normalize_scheduler_state(scontrol_fields.get("JobState"))
        sacct_state = _normalize_scheduler_state(sacct_fields.get("State"))
        state = squeue_state or scontrol_state or sacct_state
        source = "squeue" if squeue_state else "scontrol" if scontrol_state else "sacct" if sacct_state else None
        exit_code = scontrol_fields.get("ExitCode") or sacct_fields.get("ExitCode")
        reason = scontrol_fields.get("Reason")
        stdout_path = Path(scontrol_fields["StdOut"]) if scontrol_fields.get("StdOut") not in (None, "", "Unknown") else None
        stderr_path = Path(scontrol_fields["StdErr"]) if scontrol_fields.get("StdErr") not in (None, "", "Unknown") else None

        if state is None:
            limitations.append(
                f"No live Slurm scheduler state could be reconciled for job `{record.job_id}`; the run record was not updated."
            )

        return SlurmSchedulerSnapshot(
            job_id=record.job_id,
            scheduler_state=state,
            source=source,
            exit_code=exit_code,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            reason=reason,
            raw_squeue_stdout=squeue_stdout,
            raw_scontrol_stdout=scontrol_stdout,
            raw_sacct_stdout=sacct_stdout,
            limitations=tuple(limitations),
        )

    def _record_with_snapshot(self, record: SlurmRunRecord, snapshot: SlurmSchedulerSnapshot) -> SlurmRunRecord:
        """Merge one scheduler snapshot into the durable run record."""
        final_state = (
            snapshot.scheduler_state
            if snapshot.scheduler_state in _TERMINAL_SLURM_STATES
            else record.final_scheduler_state
        )
        updated_record = replace(
            record,
            scheduler_state=snapshot.scheduler_state,
            scheduler_state_source=snapshot.source,
            scheduler_exit_code=snapshot.exit_code,
            scheduler_reason=snapshot.reason,
            stdout_path=snapshot.stdout_path or record.stdout_path,
            stderr_path=snapshot.stderr_path or record.stderr_path,
            final_scheduler_state=final_state,
            last_reconciled_at=_created_at(),
            limitations=tuple(dict.fromkeys((*record.limitations, *snapshot.limitations))),
        )
        return replace(updated_record, failure_classification=classify_slurm_failure(updated_record))

    def _submit_saved_artifact(
        self,
        artifact_path: Path,
        *,
        retry_parent: SlurmRunRecord | None = None,
        resume_from_local_record: Path | None = None,
        resource_overrides: ResourceSpec | None = None,
    ) -> SlurmSpecExecutionResult:
        """Render a Slurm script, submit it via sbatch, and save the run record.

        This is the core submission path for :class:`SlurmWorkflowSpecExecutor`.
        The full sequence is:

        1. Load and validate the frozen recipe artifact.
        2. Gate on ``execution_profile == "slurm"`` and ``sbatch`` availability;
           return ``supported=False`` if either check fails.
        3. Optionally validate and import completed-node state from a prior
           local run record so the cluster job can skip already-done stages.
        4. Allocate a unique run directory under ``run_root``.
        5. Render the submission script and write it to the run directory.
        6. Call ``sbatch`` and parse the accepted Slurm job ID from its output.
        7. Write a :class:`SlurmRunRecord` immediately so the job is trackable
           before the first status poll arrives.

        Submission assumes FLyteTest is running inside an already-authenticated
        HPC login-node session.  The cluster's 2FA policy prevents SSH key
        pairing, so there is no automated credential refresh and this function
        will fail with a limitation note if ``sbatch`` cannot reach the
        scheduler.

        Args:
            artifact_path: Frozen recipe JSON to submit.  Baked into the
                generated script so the compute node loads exactly this
                artifact.
            retry_parent: When retrying a failed run, pass the prior
                :class:`SlurmRunRecord` here so the new record inherits the
                lineage chain, retry policy, and attempt count.
            resume_from_local_record: Path to a prior local run record whose
                ``node_completion_state`` is embedded in the Slurm script,
                letting the cluster job skip stages that already succeeded
                locally.

        Returns:
            A :class:`SlurmSpecExecutionResult` with ``supported=True`` and
            the accepted scheduler job ID when submission succeeds, or
            ``supported=False`` with a ``limitations`` entry describing the
            failure.
        """
        artifact = _artifact_from_source(artifact_path)
        workflow_spec = artifact.workflow_spec
        binding_plan = artifact.binding_plan

        # Validate and load local resume record when provided.
        local_resume_node_state: dict[str, bool] = {}
        local_resume_run_id: str | None = None
        if resume_from_local_record is not None:
            prior_local = load_local_run_record(resume_from_local_record)
            mismatch = _validate_resume_identity(prior_local, workflow_spec.name, artifact_path)
            if mismatch:
                return SlurmSpecExecutionResult(
                    supported=False,
                    workflow_name=workflow_spec.name,
                    execution_profile=binding_plan.execution_profile,
                    resource_spec=binding_plan.resource_spec,
                    runtime_image=binding_plan.runtime_image,
                    limitations=(mismatch,),
                )
            local_resume_node_state = dict(prior_local.node_completion_state)
            local_resume_run_id = prior_local.run_id
        if binding_plan.execution_profile != "slurm":
            return SlurmSpecExecutionResult(
                supported=False,
                workflow_name=workflow_spec.name,
                execution_profile=binding_plan.execution_profile,
                resource_spec=binding_plan.resource_spec,
                runtime_image=binding_plan.runtime_image,
                limitations=("Slurm submission requires a frozen recipe with execution_profile `slurm`.",),
            )

        missing_commands = self._missing_commands(("sbatch",))
        if missing_commands:
            return SlurmSpecExecutionResult(
                supported=False,
                workflow_name=workflow_spec.name,
                execution_profile=binding_plan.execution_profile,
                resource_spec=binding_plan.resource_spec,
                runtime_image=binding_plan.runtime_image,
                limitations=(
                    _missing_slurm_command_limitation(
                        action="submission",
                        commands=("sbatch",),
                    ),
                ),
            )

        submitted_at = _created_at()
        run_id, run_dir = _allocate_run_dir(
            self._run_root,
            _run_id_for_artifact(artifact, artifact_path, submitted_at),
        )
        script_path = run_dir / DEFAULT_SLURM_SCRIPT_FILENAME
        stdout_path = run_dir / "slurm-%j.out"
        stderr_path = run_dir / "slurm-%j.err"
        run_record_path = run_dir / DEFAULT_SLURM_RUN_RECORD_FILENAME
        run_dir.mkdir(parents=True, exist_ok=False)

        script_text = render_slurm_script(
            artifact_path=artifact_path,
            workflow_name=workflow_spec.name,
            run_id=run_id,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            resource_spec=_effective_resource_spec(binding_plan.resource_spec, resource_overrides),
            repo_root=self._repo_root,
            python_executable=self._python_executable,
            resume_from_local_record=resume_from_local_record,
        )
        script_path.write_text(script_text)
        script_path.chmod(0o755)

        try:
            submission = self._sbatch_runner(
                ["sbatch", str(script_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if submission.returncode != 0:
                detail = submission.stderr or submission.stdout or "unknown sbatch error"
                return SlurmSpecExecutionResult(
                    supported=False,
                    workflow_name=workflow_spec.name,
                    execution_profile=binding_plan.execution_profile,
                    resource_spec=_effective_resource_spec(binding_plan.resource_spec, resource_overrides),
                    runtime_image=binding_plan.runtime_image,
                    script_text=script_text,
                    limitations=(
                        _slurm_command_failure_limitation(
                            command="sbatch",
                            stderr=detail,
                            action="submission",
                        ),
                    ),
                )
            job_id = parse_sbatch_job_id(submission.stdout or "", submission.stderr or "")
        except Exception as exc:
            return SlurmSpecExecutionResult(
                supported=False,
                workflow_name=workflow_spec.name,
                execution_profile=binding_plan.execution_profile,
                resource_spec=_effective_resource_spec(binding_plan.resource_spec, resource_overrides),
                runtime_image=binding_plan.runtime_image,
                script_text=script_text,
                limitations=(str(exc),),
            )

        assumptions = [
            "This durable record captures accepted Slurm submission from a frozen recipe artifact.",
            "Execution uses the frozen workflow-spec artifact and does not reinterpret the original prompt.",
            "Submission assumes FLyteTest is running inside an already-authenticated scheduler environment.",
        ]
        if retry_parent is not None:
            assumptions.append(
                "This submission is an explicit retry attempt linked to a prior failed Slurm run record."
            )
        if local_resume_node_state:
            completed_count = sum(1 for v in local_resume_node_state.values() if v)
            assumptions.append(
                f"Resumed from local run {local_resume_run_id}; "
                f"{completed_count} node(s) pre-completed from prior local record."
            )

        retry_policy = retry_parent.retry_policy if retry_parent is not None else SlurmRetryPolicy()
        attempt_number = retry_parent.attempt_number + 1 if retry_parent is not None else 1
        lineage_root_run_id = (
            (retry_parent.lineage_root_run_id or retry_parent.run_id)
            if retry_parent is not None
            else run_id
        )
        lineage_root_run_record_path = (
            retry_parent.lineage_root_run_record_path or retry_parent.run_record_path
            if retry_parent is not None
            else run_record_path
        )

        effective_resource_spec = _effective_resource_spec(binding_plan.resource_spec, resource_overrides)
        record = SlurmRunRecord(
            schema_version=SLURM_RUN_RECORD_SCHEMA_VERSION,
            run_id=run_id,
            recipe_id=artifact_path.stem,
            workflow_name=workflow_spec.name,
            artifact_path=artifact_path,
            script_path=script_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            run_record_path=run_record_path,
            job_id=job_id,
            execution_profile=binding_plan.execution_profile,
            resource_spec=effective_resource_spec,
            resource_overrides=resource_overrides,
            runtime_image=binding_plan.runtime_image,
            submitted_at=submitted_at,
            scheduler_stdout=submission.stdout or "",
            scheduler_stderr=submission.stderr or "",
            retry_policy=retry_policy,
            attempt_number=attempt_number,
            lineage_root_run_id=lineage_root_run_id,
            lineage_root_run_record_path=lineage_root_run_record_path,
            retry_parent_run_id=retry_parent.run_id if retry_parent is not None else None,
            retry_parent_run_record_path=retry_parent.run_record_path if retry_parent is not None else None,
            local_resume_node_state=local_resume_node_state,
            local_resume_run_id=local_resume_run_id,
            cache_identity_key=cache_identity_key(
                workflow_spec.to_dict(),
                binding_plan.to_dict(),
                dict(binding_plan.explicit_user_bindings),
            ),
            assumptions=tuple(dict.fromkeys(assumptions)),
        )
        record = replace(record, failure_classification=classify_slurm_failure(record))
        save_slurm_run_record(record)
        return SlurmSpecExecutionResult(
            supported=True,
            workflow_name=workflow_spec.name,
            execution_profile=binding_plan.execution_profile,
            resource_spec=effective_resource_spec,
            runtime_image=binding_plan.runtime_image,
            run_record=record,
            script_text=script_text,
            scheduler_stdout=submission.stdout or "",
            scheduler_stderr=submission.stderr or "",
            assumptions=record.assumptions,
        )

    def render_script(
        self,
        artifact_source: SavedWorkflowSpecArtifact | Path,
        *,
        run_id: str = "dry-run",
        stdout_path: Path | None = None,
        stderr_path: Path | None = None,
        resume_from_local_record: Path | None = None,
    ) -> str:
        """Render the Slurm script without submitting it."""
        artifact = _artifact_from_source(artifact_source)
        artifact_path = _artifact_path_from_source(artifact_source) or Path("<in-memory-artifact>")
        workflow_spec = artifact.workflow_spec
        binding_plan = artifact.binding_plan
        return render_slurm_script(
            artifact_path=artifact_path,
            workflow_name=workflow_spec.name,
            run_id=run_id,
            stdout_path=stdout_path or Path("slurm.out"),
            stderr_path=stderr_path or Path("slurm.err"),
            resource_spec=binding_plan.resource_spec,
            repo_root=self._repo_root,
            python_executable=self._python_executable,
            resume_from_local_record=resume_from_local_record,
        )

    def submit(
        self,
        artifact_source: SavedWorkflowSpecArtifact | Path,
        *,
        resume_from_local_record: Path | None = None,
    ) -> SlurmSpecExecutionResult:
        """Render, submit, and persist a durable record for one Slurm recipe."""
        artifact_path = _artifact_path_from_source(artifact_source)
        if artifact_path is None:
            assert isinstance(artifact_source, SavedWorkflowSpecArtifact)
            return SlurmSpecExecutionResult(
                supported=False,
                workflow_name=artifact_source.workflow_spec.name,
                execution_profile=artifact_source.binding_plan.execution_profile,
                resource_spec=artifact_source.binding_plan.resource_spec,
                runtime_image=artifact_source.binding_plan.runtime_image,
                limitations=("Slurm submission requires a saved recipe artifact path, not only an in-memory artifact.",),
            )
        return self._submit_saved_artifact(
            artifact_path,
            resume_from_local_record=resume_from_local_record,
        )

    def reconcile(self, run_record_source: Path) -> SlurmLifecycleResult:
        """Reload a Slurm run record and reconcile it with scheduler state."""
        try:
            record = load_slurm_run_record(run_record_source)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            return SlurmLifecycleResult(
                supported=False,
                action="status",
                limitations=(str(exc),),
            )

        snapshot = self._scheduler_snapshot(record)
        if snapshot.scheduler_state is None:
            return SlurmLifecycleResult(
                supported=False,
                run_record=record,
                scheduler_snapshot=snapshot,
                action="status",
                limitations=snapshot.limitations,
                assumptions=(
                    "The filesystem run record is the durable source of truth; missing scheduler data is reported rather than guessed.",
                ),
            )

        updated_record = self._record_with_snapshot(record, snapshot)
        save_slurm_run_record(updated_record)
        return SlurmLifecycleResult(
            supported=True,
            run_record=updated_record,
            scheduler_snapshot=snapshot,
            action="status",
            limitations=snapshot.limitations,
            assumptions=(
                "The filesystem run record is the durable source of truth and has been reconciled from Slurm scheduler state.",
            ),
        )

    def cancel(self, run_record_source: Path) -> SlurmLifecycleResult:
        """Request cancellation for a submitted Slurm run and update the record."""
        try:
            record = load_slurm_run_record(run_record_source)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            return SlurmLifecycleResult(
                supported=False,
                action="cancel",
                limitations=(str(exc),),
            )

        # Idempotency: a second cancel on a record that already has
        # cancellation_requested_at set would be a duplicate scancel call.
        # Return the existing cancellation state without contacting the scheduler.
        if record.cancellation_requested_at is not None:
            snapshot = SlurmSchedulerSnapshot(
                job_id=record.job_id,
                scheduler_state="cancellation_requested",
                source="scancel",
                reason="Cancellation was already requested; no duplicate scancel issued.",
            )
            return SlurmLifecycleResult(
                supported=True,
                run_record=record,
                scheduler_snapshot=snapshot,
                action="cancel",
                assumptions=(
                    "Cancellation was already requested for this job; the existing cancellation record is returned unchanged.",
                ),
            )

        missing_commands = self._missing_commands(("scancel",))
        if missing_commands:
            return SlurmLifecycleResult(
                supported=False,
                run_record=record,
                action="cancel",
                limitations=(
                    _missing_slurm_command_limitation(
                        action="cancellation",
                        commands=("scancel",),
                    ),
                ),
            )

        cancellation_requested_at = _created_at()
        try:
            cancellation = self._run_scheduler_command(["scancel", record.job_id])
        except OSError as exc:
            return SlurmLifecycleResult(
                supported=False,
                run_record=record,
                action="cancel",
                limitations=(f"scancel could not be executed: {exc}",),
            )

        # Always persist cancellation_requested_at regardless of the scancel exit
        # code.  The request was made and should be recorded as the durable intent
        # even when the scheduler rejects it (e.g. job already completed).
        updated_record = replace(
            record,
            scheduler_state="cancellation_requested",
            scheduler_state_source="scancel",
            scheduler_reason="Cancellation requested through scancel.",
            cancellation_requested_at=cancellation_requested_at,
            last_reconciled_at=cancellation_requested_at,
        )
        updated_record = replace(updated_record, failure_classification=classify_slurm_failure(updated_record))
        save_slurm_run_record(updated_record)
        snapshot = SlurmSchedulerSnapshot(
            job_id=record.job_id,
            scheduler_state="cancellation_requested",
            source="scancel",
            reason="Cancellation requested through scancel.",
        )

        if cancellation.returncode != 0:
            return SlurmLifecycleResult(
                supported=False,
                run_record=updated_record,
                scheduler_snapshot=snapshot,
                action="cancel",
                limitations=(
                    _slurm_command_failure_limitation(
                        command="scancel",
                        stderr=cancellation.stderr or cancellation.stdout or "unknown scancel error",
                        action="cancellation",
                    ),
                ),
            )

        return SlurmLifecycleResult(
            supported=True,
            run_record=updated_record,
            scheduler_snapshot=snapshot,
            action="cancel",
            assumptions=(
                "Cancellation requests are recorded durably; final cancelled state is confirmed by a later reconciliation.",
            ),
        )

    def retry(
        self,
        run_record_source: Path,
        *,
        resource_overrides: Mapping[str, Any] | ResourceSpec | None = None,
    ) -> SlurmRetryResult:
        """Resubmit one retryable Slurm run from its durable failed run record.

        Supports explicit resource-escalation retries for
        ``resource_exhaustion`` failures (``OUT_OF_MEMORY``, ``TIMEOUT``).
        Pass *resource_overrides* with updated ``memory``, ``walltime``, or
        other fields to override the frozen recipe's resource spec for this
        submission only.  The frozen artifact is never modified.

        ``DEADLINE`` failures are excluded from the escalation path and behave
        the same as ``TIMEOUT`` — they require a new ``prepare_run_recipe``
        call with an updated resource request rather than an escalation retry.

        Args:
            run_record_source: Path to the durable ``SlurmRunRecord`` JSON for
                the failed run.
            resource_overrides: Optional resource escalation values for
                ``resource_exhaustion`` retries.  Valid keys are
                ``cpu``, ``memory``, ``walltime``, ``queue``, ``account``,
                and ``gpu``.  Ignored for regular retryable failures.
        """
        try:
            source_record = load_slurm_run_record(run_record_source)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            return SlurmRetryResult(
                supported=False,
                action="retry",
                limitations=(str(exc),),
            )

        if source_record.retry_child_run_record_paths:
            child_paths = ", ".join(str(path) for path in source_record.retry_child_run_record_paths)
            return SlurmRetryResult(
                supported=False,
                source_run_record=source_record,
                failure_classification=source_record.failure_classification or classify_slurm_failure(source_record),
                retry_policy=source_record.retry_policy,
                action="retry",
                limitations=(
                    f"Run record `{source_record.run_record_path}` already has explicit retry child record(s): {child_paths}. "
                    "Retry the latest child record instead of branching from a stale parent.",
                ),
            )

        # Validate resource overrides at the gate before any scheduler calls.
        override_spec, override_limitations = _coerce_retry_resource_overrides(resource_overrides)
        if override_limitations:
            return SlurmRetryResult(
                supported=False,
                source_run_record=source_record,
                failure_classification=source_record.failure_classification,
                retry_policy=source_record.retry_policy,
                action="retry",
                limitations=override_limitations,
            )

        current_record = source_record
        current_state = _scheduler_state_for_classification(current_record)
        if current_state not in _TERMINAL_SLURM_STATES:
            missing_commands = self._missing_commands(("squeue", "scontrol", "sacct"))
            if not missing_commands:
                snapshot = self._scheduler_snapshot(current_record)
                if snapshot.scheduler_state is not None:
                    current_record = self._record_with_snapshot(current_record, snapshot)
                    save_slurm_run_record(current_record)

        failure_classification = classify_slurm_failure(current_record)
        current_record = replace(current_record, failure_classification=failure_classification)
        save_slurm_run_record(current_record)

        if failure_classification.status in {"not_terminal", "unknown", "completed"}:
            return SlurmRetryResult(
                supported=False,
                source_run_record=current_record,
                failure_classification=failure_classification,
                retry_policy=current_record.retry_policy,
                action="retry",
                limitations=(failure_classification.detail,),
                assumptions=(
                    "Retry stays frozen-recipe driven and only proceeds from an explicit terminal failed Slurm run record.",
                ),
            )

        # Allow escalation retry when the user explicitly provides resource
        # overrides for a resource_exhaustion failure.  DEADLINE is excluded
        # from this path (same treatment as TIMEOUT without overrides) because
        # it represents a wall-clock policy that requires a new recipe with
        # an updated walltime rather than an escalation of the existing one.
        escalation_retry = (
            failure_classification.failure_class == "resource_exhaustion"
            and failure_classification.scheduler_state != "DEADLINE"
            and override_spec is not None
        )

        if not failure_classification.retryable and not escalation_retry:
            return SlurmRetryResult(
                supported=False,
                source_run_record=current_record,
                failure_classification=failure_classification,
                retry_policy=current_record.retry_policy,
                action="retry",
                limitations=(
                    f"Run `{current_record.run_id}` is classified as `{failure_classification.failure_class}` and is not retryable. "
                    f"{failure_classification.detail}",
                ),
                assumptions=(
                    "If a failure is not clearly retryable from scheduler state and exit details, FLyteTest declines instead of guessing.",
                ),
            )

        max_attempts = max(1, current_record.retry_policy.max_attempts)
        if current_record.attempt_number >= max_attempts:
            return SlurmRetryResult(
                supported=False,
                source_run_record=current_record,
                failure_classification=failure_classification,
                retry_policy=current_record.retry_policy,
                action="retry",
                limitations=(
                    f"Run `{current_record.run_id}` is already at attempt {current_record.attempt_number} of {max_attempts}; no additional retry is allowed.",
                ),
            )

        if not current_record.artifact_path.exists():
            return SlurmRetryResult(
                supported=False,
                source_run_record=current_record,
                failure_classification=failure_classification,
                retry_policy=current_record.retry_policy,
                action="retry",
                limitations=(
                    f"Frozen recipe artifact `{current_record.artifact_path}` is missing, so the Slurm retry cannot be resubmitted safely.",
                ),
            )

        retry_execution = self._submit_saved_artifact(
            current_record.artifact_path,
            retry_parent=current_record,
            resource_overrides=override_spec,
        )
        if not retry_execution.supported or retry_execution.run_record is None:
            return SlurmRetryResult(
                supported=False,
                source_run_record=current_record,
                failure_classification=failure_classification,
                retry_policy=current_record.retry_policy,
                retry_execution=retry_execution,
                action="retry",
                limitations=retry_execution.limitations,
            )

        updated_source_record = replace(
            current_record,
            retry_child_run_ids=tuple(dict.fromkeys((*current_record.retry_child_run_ids, retry_execution.run_record.run_id))),
            retry_child_run_record_paths=tuple(
                dict.fromkeys((*current_record.retry_child_run_record_paths, retry_execution.run_record.run_record_path))
            ),
        )
        save_slurm_run_record(updated_source_record)
        return SlurmRetryResult(
            supported=True,
            source_run_record=updated_source_record,
            failure_classification=failure_classification,
            retry_policy=updated_source_record.retry_policy,
            retry_execution=retry_execution,
            action="retry",
            assumptions=(
                "Slurm retries reuse the frozen workflow-spec artifact and recorded execution profile rather than rebuilding intent.",
                "Each retry remains an explicit child run record linked back to the source failure.",
            ),
        )


__all__ = [
    "DEFAULT_LOCAL_RUN_RECORD_FILENAME",
    "DEFAULT_SLURM_MAX_ATTEMPTS",
    "DEFAULT_SLURM_MODULE_LOADS",
    "DEFAULT_SLURM_RUN_RECORD_FILENAME",
    "DEFAULT_SLURM_SCRIPT_FILENAME",
    "LOCAL_RUN_RECORD_SCHEMA_VERSION",
    "LocalNodeExecutionRequest",
    "LocalNodeExecutionResult",
    "LocalRunRecord",
    "LocalSpecExecutionResult",
    "LocalWorkflowSpecExecutor",
    "RegisteredNodeHandler",
    "SLURM_RUN_RECORD_SCHEMA_VERSION",
    "SlurmFailureClassification",
    "SlurmLifecycleResult",
    "SlurmRetryPolicy",
    "SlurmRetryResult",
    "SlurmRunRecord",
    "SlurmSchedulerSnapshot",
    "SlurmSpecExecutionResult",
    "SlurmWorkflowSpecExecutor",
    "classify_slurm_failure",
    "load_local_run_record",
    "load_slurm_run_record",
    "parse_sbatch_job_id",
    "render_slurm_script",
    "save_local_run_record",
    "save_slurm_run_record",
]
