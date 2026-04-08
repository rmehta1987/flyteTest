"""Normalized planning and replay data shapes for the `realtime` architecture.

This module introduces the shared metadata types described in `DESIGN.md`.
These types are only for planning and saved metadata in this milestone; they do
not change current execution behavior or mean that runtime workflow generation
already exists.
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, TypeVar, Union, get_args, get_origin, get_type_hints


_SpecSerializableT = TypeVar("_SpecSerializableT", bound="SpecSerializable")
EntityKind = Literal["task", "workflow", "generated_workflow"]
NodeKind = Literal["task", "workflow", "generated_workflow"]


def _serialize(value: Any) -> Any:
    """Convert spec values into JSON-compatible primitives."""
    # Persist filesystem paths as strings so spec payloads stay JSON-compatible.
    if isinstance(value, Path):
        return str(value)
    # Immutable tuple fields become JSON lists during serialization.
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    # Dict values may contain nested dataclasses or paths, so recurse through
    # both the keys and values before returning the payload.
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    # Nested spec dataclasses serialize using the same field-by-field rules.
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    return value


def _is_optional(annotation: Any) -> bool:
    """Return whether one type hint is an optional union."""
    origin = get_origin(annotation)
    return origin in (Union, types.UnionType) and type(None) in get_args(annotation)


def _deserialize(annotation: Any, value: Any) -> Any:
    """Rehydrate one serialized spec value using a dataclass type hint."""
    if value is None:
        return None

    # Recover serialized path strings as `Path` objects.
    if annotation is Path:
        return Path(str(value))

    origin = get_origin(annotation)
    # Rebuild tuple members item-by-item with the declared element type.
    if origin in (tuple, tuple):
        item_type = get_args(annotation)[0]
        return tuple(_deserialize(item_type, item) for item in value)

    # Mapping members recurse through both key and value type hints.
    if origin is dict:
        key_type, value_type = get_args(annotation)
        return {
            _deserialize(key_type, key): _deserialize(value_type, item)
            for key, item in value.items()
        }

    # Optional values are represented as unions, so unwrap the real inner type
    # before recursing further.
    if _is_optional(annotation):
        inner = [item for item in get_args(annotation) if item is not type(None)]
        if len(inner) == 1:
            return _deserialize(inner[0], value)

    # Nested spec dataclasses expose `from_dict`, so reuse that instead of
    # rebuilding each structure manually here.
    if isinstance(annotation, type) and is_dataclass(annotation):
        return annotation.from_dict(value)

    return value


class SpecSerializable:
    """Mixin that gives spec dataclasses stable dict round-trips."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize one spec dataclass into JSON-compatible data."""
        # Preserve declared field order so serialized specs stay predictable in
        # tests, docs, and any later saved artifact formats.
        return {field.name: _serialize(getattr(self, field.name)) for field in fields(self)}

    @classmethod
    def from_dict(cls: type[_SpecSerializableT], payload: Mapping[str, Any]) -> _SpecSerializableT:
        """Deserialize one spec dataclass from JSON-compatible data."""
        hints = get_type_hints(cls)
        kwargs = {}
        for field_info in fields(cls):
            if field_info.name not in payload:
                continue
            # Deserialize each provided field using the declared type hints so
            # nested specs and path members round-trip correctly.
            kwargs[field_info.name] = _deserialize(hints[field_info.name], payload[field_info.name])
        return cls(**kwargs)


@dataclass(frozen=True, slots=True)
class TypedFieldSpec(SpecSerializable):
    """Describe one named input or output in a planning-time data shape."""

    name: str
    type_name: str
    description: str
    required: bool = True
    repeated: bool = False
    planner_type_names: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ResourceSpec(SpecSerializable):
    """Describe the expected compute resources for one step or workflow."""

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None
    queue: str | None = None
    walltime: str | None = None
    execution_class: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RuntimeImageSpec(SpecSerializable):
    """Describe the expected container or runtime image for one runnable step."""

    container_image: str | None = None
    apptainer_image: str | None = None
    runtime_assumptions: tuple[str, ...] = field(default_factory=tuple)
    compatibility_notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ExecutionProfile(SpecSerializable):
    """Describe one named way to run the same biology with different resources."""

    name: str
    description: str
    resource_overrides: ResourceSpec | None = None
    runtime_image: RuntimeImageSpec | None = None
    scheduler_profile: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DeterministicExecutionContract(SpecSerializable):
    """Summarize what kind of repeatable behavior one spec is meant to describe."""

    deterministic: bool = True
    result_boundary: str = ""
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class WorkflowNodeSpec(SpecSerializable):
    """Describe one step inside a planning-time workflow description."""

    name: str
    kind: NodeKind
    reference_name: str
    description: str
    input_bindings: dict[str, str] = field(default_factory=dict)
    output_names: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class WorkflowEdgeSpec(SpecSerializable):
    """Describe how the output of one workflow step feeds into another."""

    source_node: str
    source_output: str
    target_node: str
    target_input: str


@dataclass(frozen=True, slots=True)
class WorkflowOutputBinding(SpecSerializable):
    """Describe how a final workflow output is produced from an earlier step."""

    output_name: str
    source_node: str
    source_output: str
    description: str


@dataclass(frozen=True, slots=True)
class GeneratedEntityRecord(SpecSerializable):
    """Store the background details for one saved generated workflow record."""

    generated_entity_id: str
    source_prompt: str
    assumptions: tuple[str, ...]
    selected_execution_profile: str
    referenced_registered_building_blocks: tuple[str, ...]
    created_at: str
    replay_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TaskSpec(SpecSerializable):
    """Describe one runnable task in a shared planning-time format."""

    name: str
    biological_stage: str
    description: str
    inputs: tuple[TypedFieldSpec, ...]
    outputs: tuple[TypedFieldSpec, ...]
    deterministic_execution: DeterministicExecutionContract
    resource_spec: ResourceSpec | None = None
    runtime_image: RuntimeImageSpec | None = None
    supported_execution_profiles: tuple[str, ...] = field(default_factory=tuple)
    compatibility_constraints: tuple[str, ...] = field(default_factory=tuple)
    metadata_only: bool = True


@dataclass(frozen=True, slots=True)
class WorkflowSpec(SpecSerializable):
    """Describe one workflow in a shared format for planning and saved metadata."""

    name: str
    analysis_goal: str
    inputs: tuple[TypedFieldSpec, ...]
    outputs: tuple[TypedFieldSpec, ...]
    nodes: tuple[WorkflowNodeSpec, ...]
    edges: tuple[WorkflowEdgeSpec, ...]
    ordering_constraints: tuple[str, ...] = field(default_factory=tuple)
    fanout_behavior: tuple[str, ...] = field(default_factory=tuple)
    fanin_behavior: tuple[str, ...] = field(default_factory=tuple)
    reusable_registered_refs: tuple[str, ...] = field(default_factory=tuple)
    final_output_bindings: tuple[WorkflowOutputBinding, ...] = field(default_factory=tuple)
    default_execution_profile: str | None = None
    replay_metadata: dict[str, Any] = field(default_factory=dict)
    generated_entity_record: GeneratedEntityRecord | None = None
    metadata_only: bool = True


@dataclass(frozen=True, slots=True)
class BindingPlan(SpecSerializable):
    """Record how user inputs were matched to concrete files and run settings."""

    target_name: str
    target_kind: EntityKind
    explicit_user_bindings: dict[str, Any] = field(default_factory=dict)
    resolved_prior_assets: dict[str, Any] = field(default_factory=dict)
    manifest_derived_paths: dict[str, Any] = field(default_factory=dict)
    execution_profile: str | None = None
    resource_spec: ResourceSpec | None = None
    runtime_image: RuntimeImageSpec | None = None
    runtime_bindings: dict[str, Any] = field(default_factory=dict)
    unresolved_requirements: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    metadata_only: bool = True


__all__ = [
    "BindingPlan",
    "DeterministicExecutionContract",
    "ExecutionProfile",
    "GeneratedEntityRecord",
    "ResourceSpec",
    "RuntimeImageSpec",
    "SpecSerializable",
    "TaskSpec",
    "TypedFieldSpec",
    "WorkflowEdgeSpec",
    "WorkflowNodeSpec",
    "WorkflowOutputBinding",
    "WorkflowSpec",
]
