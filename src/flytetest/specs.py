"""Normalized planning and replay data shapes for the `realtime` architecture.

This module introduces the shared metadata types described in `DESIGN.md`.
These types are only for planning and saved metadata in this milestone; they do
not change current execution behavior or imply that runtime workflow generation
already exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from flytetest.serialization import SerializableMixin, deserialize_value_strict, serialize_value_with_dicts

EntityKind = Literal["task", "workflow", "generated_workflow"]
NodeKind = Literal["task", "workflow", "generated_workflow"]


class SpecSerializable(SerializableMixin):
    _serialize_fn = staticmethod(serialize_value_with_dicts)
    _deserialize_fn = staticmethod(deserialize_value_strict)


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
    """Describe the expected compute resources for one step or workflow.

    Attributes:
        module_loads: Scheduler environment modules to load before activating
            the project runtime.  Empty means use FLyteTest's Slurm defaults
            (``python/3.11.9`` and ``apptainer/1.4.1``) for backward-compatible
            submissions.  Adding this field changes ``dataclasses.asdict()``
            output and therefore ``cache_identity_key`` for any artifact that
            carries a ``ResourceSpec``; legacy artifacts that lack this field
            still deserialize correctly because the default is ``()``.
    """

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None
    queue: str | None = None
    account: str | None = None
    walltime: str | None = None
    execution_class: str | None = None
    module_loads: tuple[str, ...] = field(default_factory=tuple)
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
    """Summarize the repeatability expectations for one spec."""

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
    """Store the provenance details for one saved generated workflow record."""

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
    """Describe one workflow for planner-time previews and frozen saved recipes.

    This is a metadata shape, not a live runtime execution object.
    """

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
    """Record how user inputs were matched to concrete files and run settings.

    This captures the handoff from prompt or manifest inputs to the concrete
    runtime bindings used when a workflow preview is replayed later.
    """

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
