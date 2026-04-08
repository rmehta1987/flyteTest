"""Local execution path for saved workflow-spec artifacts.

This Milestone 7 module executes saved `WorkflowSpec` artifacts over registered
building blocks through explicit handlers. It keeps execution separate from the
current Flyte entrypoints and uses the resolver plus saved `BindingPlan` data
to prepare node inputs before any registered stage is called.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flytetest.registry import get_entry
from flytetest.resolver import AssetResolver, LocalManifestAssetResolver, ResolutionResult
from flytetest.spec_artifacts import SavedWorkflowSpecArtifact, load_workflow_spec_artifact
from flytetest.specs import WorkflowNodeSpec


RegisteredNodeHandler = Callable[["LocalNodeExecutionRequest"], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class LocalNodeExecutionRequest:
    """Inputs passed to one registered task or workflow handler."""

    node: WorkflowNodeSpec
    inputs: Mapping[str, Any]
    resolved_planner_inputs: Mapping[str, Any]
    upstream_outputs: Mapping[str, Mapping[str, Any]]
    binding_plan_target: str
    execution_profile: str | None


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
    node_results: tuple[LocalNodeExecutionResult, ...] = field(default_factory=tuple)
    final_outputs: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)


def _artifact_from_source(source: SavedWorkflowSpecArtifact | Path) -> SavedWorkflowSpecArtifact:
    """Load an artifact from disk when the caller provides a path."""
    if isinstance(source, SavedWorkflowSpecArtifact):
        return source
    return load_workflow_spec_artifact(source)


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
            node_results=tuple(node_results),
            final_outputs=final_outputs,
            assumptions=tuple(dict.fromkeys(assumptions)),
        )


__all__ = [
    "LocalNodeExecutionRequest",
    "LocalNodeExecutionResult",
    "LocalSpecExecutionResult",
    "LocalWorkflowSpecExecutor",
    "RegisteredNodeHandler",
]
