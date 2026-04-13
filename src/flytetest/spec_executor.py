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

    It captures the node metadata, resolved planner inputs, and frozen runtime
    policy that a local handler needs in order to execute one stage.
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

    It captures the node metadata, resolved planner inputs, and frozen runtime
    policy that a local handler needs in order to execute one stage.
"""

    max_attempts: int = DEFAULT_SLURM_MAX_ATTEMPTS


@dataclass(frozen=True, slots=True)
class SlurmFailureClassification(SpecSerializable):
    """Conservative retryability assessment for one Slurm run record.

    It captures the node metadata, resolved planner inputs, and frozen runtime
    policy that a local handler needs in order to execute one stage.
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

    It captures the node metadata, resolved planner inputs, and frozen runtime
    policy that a local handler needs in order to execute one stage.
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
    if hasattr(value, "to_dict"):
        return value.to_dict()
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
    """Resolve all planner-facing inputs declared by the saved workflow spec.

    Args:
        artifact: Saved workflow-spec artifact being loaded, inspected, or executed.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        result_bundles: A directory path used by the helper.
        resolver: Resolver used to discover planner-facing inputs from local sources.

    Returns:
        The computed result returned by this helper.
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
    """Resolve a compact `inputs.TypeName` or `node.output` binding expression.

    Args:
        expression: The `expression` input processed by this helper.
        resolved_planner_inputs: The `resolved_planner_inputs` input processed by this helper.
        upstream_outputs: The `upstream_outputs` input processed by this helper.

    Returns:
        The computed result returned by this helper.
"""
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
    """Return a node-specific or shared runtime binding when one is present.

    Args:
        runtime_bindings: Frozen runtime inputs supplied alongside planner-discovered values.
        node_name: Workflow node name used to scope a runtime binding lookup.
        input_name: Input name being looked up on the current node or shared bindings.

    Returns:
        The computed result returned by this helper.
"""
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
    """Build handler inputs from spec bindings plus saved runtime bindings.

    Args:
        node: The workflow node or task node under inspection.
        resolved_planner_inputs: The `resolved_planner_inputs` input processed by this helper.
        upstream_outputs: The `upstream_outputs` input processed by this helper.
        runtime_bindings: Frozen runtime inputs supplied alongside planner-discovered values.

    Returns:
        The computed result returned by this helper.
"""
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
    """Return a manifest path for result-directory outputs when present.

    Args:
        value: The value or values processed by the helper.

    Returns:
        The computed result returned by this helper.
"""
    try:
        output_path = Path(value)
    except TypeError:
        return None
    manifest_path = output_path / "run_manifest.json"
    return manifest_path if manifest_path.exists() else None


def _manifest_paths_for_outputs(outputs: Mapping[str, Any]) -> dict[str, Path]:
    """Collect manifest paths from any node outputs that look like result directories.

    Args:
        outputs: Node outputs being scanned for manifest paths.

    Returns:
        The computed result returned by this helper.
"""
    return {
        name: manifest_path
        for name, value in outputs.items()
        if (manifest_path := _manifest_path_for_output(value)) is not None
    }


def _json_ready(value: Any) -> Any:
    """Convert executor values into stable JSON-compatible data.

    Args:
        value: The value or values processed by the helper.

    Returns:
        The computed result returned by this helper.
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
    """Write a JSON payload through a temporary file before replacing.

    Args:
        path: A filesystem path used by the helper.
        payload: The structured payload to serialize or inspect.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n")
    os.replace(temporary_path, path)


def _slurm_run_record_path(source: Path) -> Path:
    """Resolve a run-record directory or JSON path to the record file.

    Args:
        source: A filesystem path used by the helper.

    Returns:
        The computed result returned by this helper.
"""
    return source / DEFAULT_SLURM_RUN_RECORD_FILENAME if source.is_dir() else source


def load_slurm_run_record(source: Path) -> SlurmRunRecord:
    """Load one durable Slurm run record from a directory or JSON path.

    Args:
        source: A filesystem path used by the helper.

    Returns:
        The computed result returned by this helper.
"""
    record_path = _slurm_run_record_path(source)
    payload = json.loads(record_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != SLURM_RUN_RECORD_SCHEMA_VERSION:
        raise ValueError(f"Unsupported Slurm run record schema version: {schema_version!r}")
    return SlurmRunRecord.from_dict(payload)


def save_slurm_run_record(record: SlurmRunRecord) -> Path:
    """Persist one Slurm run record atomically.

    Args:
        record: Slurm run record or scheduler snapshot being processed.

    Returns:
        The computed result returned by this helper.
"""
    _write_json_atomically(record.run_record_path, record.to_dict())
    return record.run_record_path


def _local_run_record_path(source: Path) -> Path:
    """Resolve a directory or JSON path to the local run record file.

    Args:
        source: A filesystem path used by the helper.  A directory resolves to
            the default local run record filename inside it; a file path is
            returned as-is.

    Returns:
        The path to the ``local_run_record.json`` file.
"""
    return source / DEFAULT_LOCAL_RUN_RECORD_FILENAME if source.is_dir() else source


def load_local_run_record(source: Path) -> "LocalRunRecord":
    """Load one durable local run record from a directory or JSON path.

    The schema version is validated before deserializing so stale or
    mismatched records are rejected explicitly rather than silently
    producing wrong data.

    Args:
        source: A directory containing ``local_run_record.json`` or a direct
            path to a ``local_run_record.json`` file.

    Returns:
        The deserialized :class:`LocalRunRecord`.

    Raises:
        ValueError: When the file's ``schema_version`` does not match
            :data:`LOCAL_RUN_RECORD_SCHEMA_VERSION`.
"""
    record_path = _local_run_record_path(source)
    payload = json.loads(record_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != LOCAL_RUN_RECORD_SCHEMA_VERSION:
        raise ValueError(f"Unsupported local run record schema version: {schema_version!r}")
    return LocalRunRecord.from_dict(payload)


def save_local_run_record(record: "LocalRunRecord") -> Path:
    """Persist one local run record atomically.

    Uses a temporary file and :func:`os.replace` so the target file is never
    left in a partially-written state.

    Args:
        record: The :class:`LocalRunRecord` to persist.

    Returns:
        The path where the record was written.
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
    """Check that a prior run record matches the current execution identity.

    The workflow name and artifact path are checked first as fast pre-filters.
    When *current_cache_key* is provided the prior record's
    ``cache_identity_key`` is compared as the authoritative content-level gate.

    Returns ``None`` when identity matches, or a human-readable mismatch
    description when the prior record should not be reused.
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
    """Parse the Slurm job ID emitted by `sbatch`.

    Args:
        stdout: Standard output text being parsed.
        stderr: Standard error text being parsed.

    Returns:
        The computed result returned by this helper.
"""
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
    """Normalize a scheduler state into a compact uppercase state name.

    Args:
        value: The value or values processed by the helper.

    Returns:
        The computed result returned by this helper.
"""
    if value in (None, ""):
        return None
    return str(value).strip().split()[0].split("+")[0].split("(")[0].upper()


def _scheduler_state_for_classification(record: SlurmRunRecord) -> str | None:
    """Prefer the durable terminal state when classifying retryability.

    Args:
        record: Slurm run record or scheduler snapshot being processed.

    Returns:
        The computed result returned by this helper.
"""
    return record.final_scheduler_state or record.scheduler_state


def _scheduler_exit_is_nonzero(exit_code: str | None) -> bool:
    """Return whether a recorded Slurm exit code represents a nonzero outcome.

    Args:
        exit_code: The `exit_code` input processed by this helper.

    Returns:
        The computed result returned by this helper.
"""
    if exit_code in (None, ""):
        return False
    status_code, _, signal_code = str(exit_code).partition(":")
    return status_code not in {"", "0"} or signal_code not in {"", "0"}


def classify_slurm_failure(record: SlurmRunRecord) -> SlurmFailureClassification:
    """Classify one durable Slurm record as retryable, terminal, or incomplete.

    Args:
        record: Slurm run record or scheduler snapshot being processed.

    Returns:
        The computed result returned by this helper.
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
    """Return whether one command appears to be available on the current PATH.

    Args:
        command: The command arguments or command name passed to the helper.

    Returns:
        The computed result returned by this helper.
"""
    return shutil.which(command) is not None


def _format_slurm_command_list(commands: Sequence[str]) -> str:
    """Render a short backtick-wrapped command list for user-facing diagnostics.

    Args:
        commands: Command names being checked for availability or reported in diagnostics.

    Returns:
        The computed result returned by this helper.
"""
    wrapped = [f"`{command}`" for command in commands]
    if len(wrapped) == 1:
        return wrapped[0]
    if len(wrapped) == 2:
        return f"{wrapped[0]} and {wrapped[1]}"
    return f"{', '.join(wrapped[:-1])}, and {wrapped[-1]}"


def _missing_slurm_command_limitation(*, action: str, commands: Sequence[str], require_all: bool = True) -> str:
    """Describe a missing-command Slurm access boundary in one actionable sentence.

    Args:
        action: Lifecycle action being described or performed.
        commands: Command names being checked for availability or reported in diagnostics.
        require_all: The `require_all` input processed by this helper.

    Returns:
        The computed result returned by this helper.
"""
    requirement = (
        f"requires {_format_slurm_command_list(commands)} on PATH"
        if require_all
        else f"requires at least one of {_format_slurm_command_list(commands)} on PATH"
    )
    return f"Slurm {action} {requirement}. {_SLURM_AUTHENTICATED_ENVIRONMENT_GUIDANCE}"


def _partial_slurm_command_limitation(*, action: str, commands: Sequence[str]) -> str:
    """Describe a degraded command set without failing the whole lifecycle action.

    Args:
        action: Lifecycle action being described or performed.
        commands: Command names being checked for availability or reported in diagnostics.

    Returns:
        The computed result returned by this helper.
"""
    return (
        f"Slurm {action} cannot use {_format_slurm_command_list(commands)} in the current "
        "environment and will rely on the remaining scheduler commands."
    )


def _looks_like_scheduler_reachability_issue(text: str) -> bool:
    """Heuristically detect scheduler failures caused by the wrong execution context.

    Args:
        text: Free text to normalize or inspect.

    Returns:
        The computed result returned by this helper.
"""
    lowered = text.lower()
    return any(pattern in lowered for pattern in _SLURM_REACHABILITY_PATTERNS)


def _slurm_command_failure_limitation(*, command: str, stderr: str, action: str) -> str:
    """Turn one Slurm CLI failure into a user-facing limitation.

    Args:
        command: The command arguments or command name passed to the helper.
        stderr: Standard error text being parsed.
        action: Lifecycle action being described or performed.

    Returns:
        The computed result returned by this helper.
"""
    detail = stderr.strip()
    if _looks_like_scheduler_reachability_issue(detail):
        return (
            f"`{command}` is available, but the current environment could not reach the "
            f"Slurm scheduler while attempting {action}: {detail}. "
            f"{_SLURM_AUTHENTICATED_ENVIRONMENT_GUIDANCE}"
        )
    return f"{command} failed during Slurm {action}: {detail}"


def _first_nonempty_line(value: str) -> str | None:
    """Return the first non-empty line from command output.

    Args:
        value: The value or values processed by the helper.

    Returns:
        The computed result returned by this helper.
"""
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _parse_squeue_state(stdout: str) -> str | None:
    """Parse the state emitted by `squeue --format=%T`.

    Args:
        stdout: Standard output text being parsed.

    Returns:
        The computed result returned by this helper.
"""
    return _normalize_scheduler_state(_first_nonempty_line(stdout))


def _parse_scontrol_fields(stdout: str) -> dict[str, str]:
    """Parse key-value fields from `scontrol show job` output.

    Args:
        stdout: Standard output text being parsed.

    Returns:
        The computed result returned by this helper.
"""
    fields: dict[str, str] = {}
    for token in stdout.replace("\n", " ").split():
        if "=" not in token:
            continue
        key, value = token.split("=", maxsplit=1)
        fields[key] = value
    return fields


def _parse_sacct_fields(stdout: str, job_id: str) -> dict[str, str]:
    """Parse pipe-delimited `sacct` output for the main job or batch step.

    Args:
        stdout: Standard output text being parsed.
        job_id: Scheduler job identifier assigned after submission.

    Returns:
        The computed result returned by this helper.
"""
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
    """Return a compact Slurm-safe identifier fragment.

    Args:
        value: The value or values processed by the helper.
        max_length: Maximum output length for the generated identifier fragment.

    Returns:
        The computed result returned by this helper.
"""
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return (slug or "workflow")[:max_length]


def _normalize_slurm_memory(memory: str | None) -> str | None:
    """Convert common recipe memory spellings into Slurm-friendly values.

    Args:
        memory: Memory request being normalized for Slurm.

    Returns:
        The computed result returned by this helper.
"""
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


def _slurm_directives(
    *,
    workflow_name: str,
    run_id: str,
    stdout_path: Path,
    stderr_path: Path,
    resource_spec: ResourceSpec | None,
) -> list[str]:
    """Build deterministic `#SBATCH` directives from the frozen resource spec.

    Args:
        workflow_name: The supported workflow or task name forwarded by the caller.
        run_id: Stable run identifier associated with the frozen recipe or submission.
        stdout_path: A filesystem path used by the helper.
        stderr_path: A filesystem path used by the helper.
        resource_spec: Frozen compute resource policy for the recipe or run record.

    Returns:
        The computed result returned by this helper.
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
) -> str:
    """Render a deterministic Slurm script for one frozen recipe artifact.

    Args:
        artifact_path: A filesystem path used by the helper.
        workflow_name: The supported workflow or task name forwarded by the caller.
        run_id: Stable run identifier associated with the frozen recipe or submission.
        stdout_path: A filesystem path used by the helper.
        stderr_path: A filesystem path used by the helper.
        resource_spec: Frozen compute resource policy for the recipe or run record.
        repo_root: The `repo_root` input processed by this helper.
        python_executable: The `python_executable` input processed by this helper.

    Returns:
        The computed result returned by this helper.
"""
    python_code = (
        "from flytetest.server import run_local_recipe; "
        "import json, sys; "
        f"result = run_local_recipe({str(artifact_path)!r}); "
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
            "  module load python/3.11.9",
            "  module load apptainer/1.4.1",
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
    """Return a UTC timestamp suitable for a durable run record.

    This helper keeps the supported planner or executor path explicit and easy to review.

    Returns:
        The computed result returned by this helper.
"""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id_for_artifact(artifact: SavedWorkflowSpecArtifact, artifact_path: Path, submitted_at: str) -> str:
    """Build a run-scoped ID that is not keyed only by recipe name.

    Args:
        artifact: Saved workflow-spec artifact being loaded, inspected, or executed.
        artifact_path: A filesystem path used by the helper.
        submitted_at: The `submitted_at` input processed by this helper.

    Returns:
        The computed result returned by this helper.
"""
    digest_source = f"{artifact_path.resolve()}|{artifact.workflow_spec.name}|{artifact.created_at}|{submitted_at}"
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    timestamp = submitted_at.replace(":", "").replace("-", "").replace("Z", "Z")
    return f"{timestamp}-{_slug(artifact.workflow_spec.name, max_length=32)}-{digest}"


def _allocate_run_dir(run_root: Path, requested_run_id: str) -> tuple[str, Path]:
    """Reserve a unique run directory even when submissions happen in the same second.

    Args:
        run_root: Root directory under which a unique run folder will be created.
        requested_run_id: The `requested_run_id` input processed by this helper.

    Returns:
        The computed result returned by this helper.
"""
    run_id = requested_run_id
    run_dir = run_root / run_id
    suffix = 1
    while run_dir.exists():
        run_id = f"{requested_run_id}-retry{suffix}"
        run_dir = run_root / run_id
        suffix += 1
    return run_id, run_dir


class LocalWorkflowSpecExecutor:
    """Execute saved workflow specs locally through supported stage handlers.

    It captures the node metadata, resolved planner inputs, and frozen runtime
    policy that a local handler needs in order to execute one stage.
"""

    def __init__(
        self,
        handlers: Mapping[str, RegisteredNodeHandler],
        *,
        resolver: AssetResolver | None = None,
        run_root: Path | None = None,
    ) -> None:
        """Create an executor with explicit handlers for supported stages.

    Args:
        handlers: The `handlers` input processed by this helper.
        resolver: Resolver used to discover planner-facing inputs from local sources.
        run_root: Optional root directory under which a dated run folder is
            created for each execution.  When provided, the executor writes a
            durable :class:`LocalRunRecord` after every successful run.  When
            ``None`` (the default), the executor behaves exactly as before and
            no record is written.
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
        """Execute one saved spec artifact through local supported handlers.

    When *resume_from* points to an existing :class:`LocalRunRecord` directory
    or JSON path, the executor loads the prior record, validates that its
    identity (workflow name and artifact path) matches the current artifact,
    and skips nodes whose ``node_completion_state`` entry is ``True``.  Skipped
    nodes reuse their prior outputs and a human-readable reason is recorded in
    the new record's ``node_skip_reasons`` dict.

    Args:
        artifact_source: Saved workflow-spec artifact or path that should be loaded first.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        result_bundles: A directory path used by the helper.
        resume_from: Optional path to a prior ``LocalRunRecord`` directory or
            JSON file.  When provided, completed nodes are skipped and their
            prior outputs are reused.

    Returns:
        The computed result returned by this helper.
"""
        artifact = _artifact_from_source(artifact_source)
        workflow_spec = artifact.workflow_spec
        binding_plan = artifact.binding_plan

        # Load and validate the prior run record when resuming (fast pre-filters).
        prior_record: LocalRunRecord | None = None
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
    """Submit saved workflow-spec artifacts through deterministic `sbatch` scripts.

    It captures the node metadata, resolved planner inputs, and frozen runtime
    policy that a local handler needs in order to execute one stage.
"""

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
        run_root: Root directory under which a unique run folder will be created.
        repo_root: The `repo_root` input processed by this helper.
        python_executable: The `python_executable` input processed by this helper.
        sbatch_runner: Injected submission command runner used for Slurm submission.
        scheduler_runner: Injected scheduler command runner used for status and cancellation.
        command_available: The `command_available` input processed by this helper.
"""
        self._run_root = run_root
        self._repo_root = repo_root
        self._python_executable = python_executable or sys.executable
        self._sbatch_runner = sbatch_runner
        self._scheduler_runner = scheduler_runner
        self._command_available = command_available

    def _run_scheduler_command(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run one scheduler command with the executor's injectable runner.

    Args:
        args: The argument vector forwarded to the helper.

    Returns:
        The computed result returned by this helper.
"""
        return self._scheduler_runner(
            args,
            capture_output=True,
            text=True,
            check=False,
        )

    def _missing_commands(self, commands: Sequence[str]) -> tuple[str, ...]:
        """Return the subset of commands that do not appear to be available.

    Args:
        commands: Command names being checked for availability or reported in diagnostics.

    Returns:
        The computed result returned by this helper.
"""
        return tuple(command for command in commands if not self._command_available(command))

    def _scheduler_snapshot(self, record: SlurmRunRecord) -> SlurmSchedulerSnapshot:
        """Poll Slurm commands and merge their observed state into one snapshot.

    Args:
        record: Slurm run record or scheduler snapshot being processed.

    Returns:
        The computed result returned by this helper.
"""
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
        """Merge one scheduler snapshot into the durable run record.

    Args:
        record: Slurm run record or scheduler snapshot being processed.
        snapshot: Observed scheduler snapshot being merged into the durable record.

    Returns:
        The computed result returned by this helper.
"""
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
    ) -> SlurmSpecExecutionResult:
        """Render, submit, and persist one saved Slurm recipe artifact.

    Args:
        artifact_path: A filesystem path used by the helper.
        retry_parent: The `retry_parent` input processed by this helper.
        resume_from_local_record: Optional prior ``LocalRunRecord`` path.

    Returns:
        The computed result returned by this helper.
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
            resource_spec=binding_plan.resource_spec,
            repo_root=self._repo_root,
            python_executable=self._python_executable,
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
                    resource_spec=binding_plan.resource_spec,
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
                resource_spec=binding_plan.resource_spec,
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
            resource_spec=binding_plan.resource_spec,
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
            resource_spec=binding_plan.resource_spec,
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
    ) -> str:
        """Render the Slurm script without submitting it.

    Args:
        artifact_source: Saved workflow-spec artifact or path that should be loaded first.
        run_id: Stable run identifier associated with the frozen recipe or submission.
        stdout_path: A filesystem path used by the helper.
        stderr_path: A filesystem path used by the helper.

    Returns:
        The computed result returned by this helper.
"""
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
        )

    def submit(
        self,
        artifact_source: SavedWorkflowSpecArtifact | Path,
        *,
        resume_from_local_record: Path | None = None,
    ) -> SlurmSpecExecutionResult:
        """Render, submit, and persist a durable record for one Slurm recipe.

    When *resume_from_local_record* points to an existing :class:`LocalRunRecord`,
    the local record's completed node state is copied into the new
    :class:`SlurmRunRecord` so that the Slurm job can skip already-done stages.

    Args:
        artifact_source: Saved workflow-spec artifact or path that should be loaded first.
        resume_from_local_record: Optional path to a prior ``LocalRunRecord``
            directory or JSON file whose completed nodes should be treated as
            pre-done in the new Slurm submission.

    Returns:
        The computed result returned by this helper.
"""
        artifact_path = _artifact_path_from_source(artifact_source)
        if artifact_path is None:
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
        """Reload a Slurm run record and reconcile it with scheduler state.

    Args:
        run_record_source: Run-record directory or JSON file used to reload durable Slurm state.

    Returns:
        The computed result returned by this helper.
"""
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
        """Request cancellation for a submitted Slurm run and update the record.

    Args:
        run_record_source: Run-record directory or JSON file used to reload durable Slurm state.

    Returns:
        The computed result returned by this helper.
"""
        try:
            record = load_slurm_run_record(run_record_source)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            return SlurmLifecycleResult(
                supported=False,
                action="cancel",
                limitations=(str(exc),),
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
        if cancellation.returncode != 0:
            return SlurmLifecycleResult(
                supported=False,
                run_record=record,
                action="cancel",
                limitations=(
                    _slurm_command_failure_limitation(
                        command="scancel",
                        stderr=cancellation.stderr or cancellation.stdout or "unknown scancel error",
                        action="cancellation",
                    ),
                ),
            )

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
        return SlurmLifecycleResult(
            supported=True,
            run_record=updated_record,
            scheduler_snapshot=snapshot,
            action="cancel",
            assumptions=(
                "Cancellation requests are recorded durably; final cancelled state is confirmed by a later reconciliation.",
            ),
        )

    def retry(self, run_record_source: Path) -> SlurmRetryResult:
        """Resubmit one retryable Slurm run from its durable failed run record.

    Args:
        run_record_source: Run-record directory or JSON file used to reload durable Slurm state.

    Returns:
        The computed result returned by this helper.
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

        if not failure_classification.retryable:
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

        retry_execution = self._submit_saved_artifact(current_record.artifact_path, retry_parent=current_record)
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
