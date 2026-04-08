"""Local execution path for saved workflow-spec artifacts.

This Milestone 7 module executes saved `WorkflowSpec` artifacts over registered
building blocks through explicit handlers. It keeps execution separate from the
current Flyte entrypoints and uses the resolver plus saved `BindingPlan` data
to prepare node inputs before any registered stage is called.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
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


@dataclass(frozen=True, slots=True)
class LocalNodeExecutionRequest:
    """Inputs passed to one registered task or workflow handler."""

    node: WorkflowNodeSpec
    inputs: Mapping[str, Any]
    resolved_planner_inputs: Mapping[str, Any]
    upstream_outputs: Mapping[str, Mapping[str, Any]]
    binding_plan_target: str
    execution_profile: str | None
    resource_spec: ResourceSpec | None
    runtime_image: RuntimeImageSpec | None


@dataclass(frozen=True, slots=True)
class LocalNodeExecutionResult:
    """Execution details recorded for one saved-spec node."""

    node_name: str
    reference_name: str
    outputs: Mapping[str, Any]
    manifest_paths: Mapping[str, Path] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LocalSpecExecutionResult:
    """Outcome of executing a saved workflow spec through local handlers."""

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
class SlurmRunRecord(SpecSerializable):
    """Durable filesystem record for one accepted Slurm recipe submission."""

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
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SlurmSpecExecutionResult:
    """Outcome of submitting a frozen workflow-spec artifact to Slurm."""

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
    """Scheduler state observed for one Slurm job."""

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
    """Result of reloading, reconciling, or cancelling a Slurm run record."""

    supported: bool
    run_record: SlurmRunRecord | None = None
    scheduler_snapshot: SlurmSchedulerSnapshot | None = None
    action: str = "status"
    limitations: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)


def _artifact_from_source(source: SavedWorkflowSpecArtifact | Path) -> SavedWorkflowSpecArtifact:
    """Load an artifact from disk when the caller provides a path."""
    if isinstance(source, SavedWorkflowSpecArtifact):
        return source
    return load_workflow_spec_artifact(source)


def _artifact_path_from_source(source: SavedWorkflowSpecArtifact | Path) -> Path | None:
    """Return the artifact path when the caller supplied a filesystem source."""
    return Path(source) if not isinstance(source, SavedWorkflowSpecArtifact) else None


def _planner_type_names_for_node_inputs(artifact: SavedWorkflowSpecArtifact) -> tuple[str, ...]:
    """Return planner type names that must be resolved before node execution."""
    names: list[str] = []
    for input_spec in artifact.workflow_spec.inputs:
        for name in input_spec.planner_type_names:
            if name not in names:
                names.append(name)
    return tuple(names)


def _serialized_resolved_value(result: ResolutionResult) -> Any:
    """Convert one resolved planner value into an executor-friendly payload."""
    value = result.resolved_value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _quality_assessment_target_from_serialized(value: Any) -> QualityAssessmentTarget | None:
    """Convert a serialized quality target into the planner dataclass when possible."""
    if isinstance(value, QualityAssessmentTarget):
        return value
    if isinstance(value, Mapping):
        return QualityAssessmentTarget.from_dict(dict(value))
    return None


def _manifest_source_bundle_path(target: QualityAssessmentTarget, source_bundle_key: str) -> Path | None:
    """Return one source bundle path from the target manifest when it is recorded."""
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
    """Derive the concrete workflow input directory required by a QC target."""
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
    """Derive node inputs from a resolved quality target when present."""
    quality_target_inputs = {
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
    """Resolve all planner-facing inputs declared by the saved workflow spec."""
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
    """Collect manifest paths from any node outputs that look like result directories."""
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
    """Write a JSON payload through a temporary file before replacing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n")
    os.replace(temporary_path, path)


def _slurm_run_record_path(source: Path) -> Path:
    """Resolve a run-record directory or JSON path to the record file."""
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
    """Persist one Slurm run record atomically."""
    _write_json_atomically(record.run_record_path, record.to_dict())
    return record.run_record_path


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


def _normalize_scheduler_state(value: str | None) -> str | None:
    """Normalize a scheduler state into a compact uppercase state name."""
    if value in (None, ""):
        return None
    return str(value).strip().split()[0].split("+")[0].split("(")[0].upper()


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


def _slurm_directives(
    *,
    workflow_name: str,
    run_id: str,
    stdout_path: Path,
    stderr_path: Path,
    resource_spec: ResourceSpec | None,
) -> list[str]:
    """Build deterministic `#SBATCH` directives from the frozen resource spec."""
    job_name = _slug(f"flytetest-{workflow_name}-{run_id}", max_length=64)
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
    """Render a deterministic Slurm script for one frozen recipe artifact."""
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
            f"export PYTHONPATH={shlex.quote(str(repo_root / 'src'))}${{PYTHONPATH:+:$PYTHONPATH}}",
            f"{shlex.quote(python_executable)} -c {shlex.quote(python_code)}",
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


class LocalWorkflowSpecExecutor:
    """Execute saved workflow specs locally through registered stage handlers."""

    def __init__(
        self,
        handlers: Mapping[str, RegisteredNodeHandler],
        *,
        resolver: AssetResolver | None = None,
    ) -> None:
        """Create an executor with explicit handlers for registered stages."""
        self._handlers = dict(handlers)
        self._resolver = resolver or LocalManifestAssetResolver()

    def execute(
        self,
        artifact_source: SavedWorkflowSpecArtifact | Path,
        *,
        explicit_bindings: Mapping[str, Any] | None = None,
        manifest_sources: Sequence[Path | Mapping[str, Any]] = (),
        result_bundles: Sequence[Any] = (),
    ) -> LocalSpecExecutionResult:
        """Execute one saved spec artifact through local registered handlers."""
        artifact = _artifact_from_source(artifact_source)
        workflow_spec = artifact.workflow_spec
        binding_plan = artifact.binding_plan

        resolved_planner_inputs, resolver_limitations, resolver_assumptions = _resolve_planner_inputs(
            artifact,
            explicit_bindings=explicit_bindings or {},
            manifest_sources=manifest_sources,
            result_bundles=result_bundles,
            resolver=self._resolver,
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
        assumptions = [*artifact.assumptions, *binding_plan.assumptions, *resolver_assumptions]

        for node in workflow_spec.nodes:
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
                    limitations=(f"No local handler is registered for `{node.reference_name}`.",),
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
    """Submit saved workflow-spec artifacts through deterministic `sbatch` scripts."""

    def __init__(
        self,
        *,
        run_root: Path,
        repo_root: Path,
        python_executable: str | None = None,
        sbatch_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        scheduler_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        """Create a Slurm executor with explicit filesystem and command policy."""
        self._run_root = run_root
        self._repo_root = repo_root
        self._python_executable = python_executable or sys.executable
        self._sbatch_runner = sbatch_runner
        self._scheduler_runner = scheduler_runner

    def _run_scheduler_command(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run one scheduler command with the executor's injectable runner."""
        return self._scheduler_runner(
            args,
            capture_output=True,
            text=True,
            check=False,
        )

    def _scheduler_snapshot(self, record: SlurmRunRecord) -> SlurmSchedulerSnapshot:
        """Poll Slurm commands and merge their observed state into one snapshot."""
        limitations: list[str] = []
        squeue_stdout = ""
        scontrol_stdout = ""
        sacct_stdout = ""
        squeue_state: str | None = None
        scontrol_fields: dict[str, str] = {}
        sacct_fields: dict[str, str] = {}

        try:
            squeue = self._run_scheduler_command(["squeue", "--noheader", "--jobs", record.job_id, "--format=%T"])
            squeue_stdout = squeue.stdout or ""
            if squeue.returncode == 0:
                squeue_state = _parse_squeue_state(squeue_stdout)
            elif squeue.stderr:
                limitations.append(f"squeue failed: {squeue.stderr.strip()}")
        except OSError as exc:
            limitations.append(f"squeue could not be executed: {exc}")

        try:
            scontrol = self._run_scheduler_command(["scontrol", "show", "job", record.job_id])
            scontrol_stdout = scontrol.stdout or ""
            if scontrol.returncode == 0:
                scontrol_fields = _parse_scontrol_fields(scontrol_stdout)
            elif scontrol.stderr:
                limitations.append(f"scontrol failed: {scontrol.stderr.strip()}")
        except OSError as exc:
            limitations.append(f"scontrol could not be executed: {exc}")

        try:
            sacct = self._run_scheduler_command(
                ["sacct", "-n", "-P", "-j", record.job_id, "--format=JobID,State,ExitCode"]
            )
            sacct_stdout = sacct.stdout or ""
            if sacct.returncode == 0:
                sacct_fields = _parse_sacct_fields(sacct_stdout, record.job_id)
            elif sacct.stderr:
                limitations.append(f"sacct failed: {sacct.stderr.strip()}")
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

    def render_script(
        self,
        artifact_source: SavedWorkflowSpecArtifact | Path,
        *,
        run_id: str = "dry-run",
        stdout_path: Path | None = None,
        stderr_path: Path | None = None,
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
        )

    def submit(
        self,
        artifact_source: SavedWorkflowSpecArtifact | Path,
    ) -> SlurmSpecExecutionResult:
        """Render, submit, and persist a durable record for one Slurm recipe."""
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

        artifact = _artifact_from_source(artifact_path)
        workflow_spec = artifact.workflow_spec
        binding_plan = artifact.binding_plan
        if binding_plan.execution_profile != "slurm":
            return SlurmSpecExecutionResult(
                supported=False,
                workflow_name=workflow_spec.name,
                execution_profile=binding_plan.execution_profile,
                resource_spec=binding_plan.resource_spec,
                runtime_image=binding_plan.runtime_image,
                limitations=("Slurm submission requires a frozen recipe with execution_profile `slurm`.",),
            )

        submitted_at = _created_at()
        run_id = _run_id_for_artifact(artifact, artifact_path, submitted_at)
        run_dir = self._run_root / run_id
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
                check=True,
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
            assumptions=(
                "This Milestone 13 record captures accepted Slurm submission only; polling and cancellation are later slices.",
                "Execution uses the frozen workflow-spec artifact and does not reinterpret the original prompt.",
            ),
        )
        _write_json_atomically(run_record_path, record.to_dict())
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

        final_state = snapshot.scheduler_state if snapshot.scheduler_state in _TERMINAL_SLURM_STATES else record.final_scheduler_state
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
                limitations=(f"scancel failed: {(cancellation.stderr or cancellation.stdout or '').strip()}",),
            )

        updated_record = replace(
            record,
            scheduler_state="cancellation_requested",
            scheduler_state_source="scancel",
            scheduler_reason="Cancellation requested through scancel.",
            cancellation_requested_at=cancellation_requested_at,
            last_reconciled_at=cancellation_requested_at,
        )
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


__all__ = [
    "DEFAULT_SLURM_RUN_RECORD_FILENAME",
    "DEFAULT_SLURM_SCRIPT_FILENAME",
    "LocalNodeExecutionRequest",
    "LocalNodeExecutionResult",
    "LocalSpecExecutionResult",
    "LocalWorkflowSpecExecutor",
    "RegisteredNodeHandler",
    "SLURM_RUN_RECORD_SCHEMA_VERSION",
    "SlurmLifecycleResult",
    "SlurmRunRecord",
    "SlurmSchedulerSnapshot",
    "SlurmSpecExecutionResult",
    "SlurmWorkflowSpecExecutor",
    "load_slurm_run_record",
    "parse_sbatch_job_id",
    "render_slurm_script",
    "save_slurm_run_record",
]
