"""Normalized planning and replay data shapes for the `realtime` architecture.

This module introduces the shared metadata types described in `DESIGN.md`.
These types are only for planning and saved metadata in this milestone; they do
not change current execution behavior or imply that runtime workflow generation
already exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from flytetest.serialization import SerializableMixin, deserialize_value_strict, serialize_value_with_dicts


_MEMORY_RE = re.compile(r"^\d+(\.\d+)?(K|M|G|T)i?$")
"""Slurm-accepted memory units: ``\\d+(.\\d+)?(K|M|G|T)i?``.

Examples that pass: ``32G``, ``500M``, ``2Ti``, ``80Gi``.  Common mistakes
this rejects at freeze: ``32 GB`` (space + ``B`` suffix), ``32GB`` (``B``
suffix), ``32 G`` (space).
"""

_WALLTIME_RE = re.compile(r"^(\d+-)?\d{1,2}:\d{2}(:\d{2})?$")
"""Slurm-accepted walltime: ``[D-]HH:MM[:SS]``.

Examples that pass: ``04:00:00``, ``1-12:00:00``, ``00:30``.  Common
mistakes this rejects at freeze: ``48h`` (Slurm expects colon-separated),
``4 hours``, ``4:00`` past 99 hours (use day-prefix instead).
"""

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
        module_loads: Full replacement of FLyteTest's
            ``DEFAULT_SLURM_MODULE_LOADS`` defaults.  Use only when you need
            to drop a default module (rare).  For the common case of "I want
            the defaults plus one more module" prefer ``extend_module_loads``,
            which appends to the defaults instead of replacing them.  If both
            ``module_loads`` and ``extend_module_loads`` are set,
            ``module_loads`` wins for backward compatibility and a warning
            is logged at submit time so the silent-drop footgun is visible.
        extend_module_loads: Modules appended to ``DEFAULT_SLURM_MODULE_LOADS``
            for this recipe.  Recommended over ``module_loads`` for the
            common case of adding a tool to the defaults
            (``extend_module_loads=("bcftools/1.20",)``).  Ignored with a
            warning when ``module_loads`` is also set.
    """

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None
    partition: str | None = None
    account: str | None = None
    walltime: str | None = None
    execution_class: str | None = None
    module_loads: tuple[str, ...] = field(default_factory=tuple)
    extend_module_loads: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate format-sensitive fields at freeze time.

        Slurm UX rollout Phase 0 step 04.  Catches typos like
        ``memory="32 GB"`` (Slurm rejects the space + ``B`` suffix),
        ``walltime="48h"`` (Slurm requires colon-separated), or
        ``cpu="eight"`` at freeze rather than 30 seconds into the sbatch
        attempt.  ``partition`` and ``account`` must be non-empty when
        ``execution_class`` is anything other than ``"local"``; the
        scheduler's queue policy is otherwise unspecified and submissions
        are rejected at the controller.

        ``frozen=True`` does not interfere — ``__post_init__`` runs after
        the field assignments and only raises; no mutation is needed.
        """
        if self.memory is not None and not _MEMORY_RE.match(self.memory):
            raise ValueError(
                f"memory={self.memory!r} does not match the Slurm-accepted "
                f"format <number>(K|M|G|T)[i] (e.g., '32G', '2Ti'). "
                f"Common mistakes: trailing/leading whitespace, the 'B' "
                f"suffix ('32GB'), or a space before the unit ('32 G')."
            )
        if self.walltime is not None and not _WALLTIME_RE.match(self.walltime):
            raise ValueError(
                f"walltime={self.walltime!r} does not match Slurm format "
                f"D-HH:MM:SS, HH:MM:SS, or HH:MM (e.g., '04:00:00', "
                f"'1-12:00:00'). Common mistakes: '48h' or '4 hours' — "
                f"Slurm requires colon-separated values."
            )
        if self.cpu is not None:
            try:
                cpu_int = int(self.cpu)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"cpu={self.cpu!r} is not a positive integer string "
                    f"(e.g., '8')."
                ) from exc
            if cpu_int <= 0:
                raise ValueError(
                    f"cpu={self.cpu!r} must be a positive integer string."
                )
        if self.execution_class and self.execution_class != "local":
            if not (self.partition and self.partition.strip()):
                raise ValueError(
                    f"partition is required for execution_class="
                    f"{self.execution_class!r}; empty / whitespace not allowed."
                )
            if not (self.account and self.account.strip()):
                raise ValueError(
                    f"account is required for execution_class="
                    f"{self.execution_class!r}; empty / whitespace not allowed."
                )


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
    tool_databases: dict[str, str] = field(default_factory=dict)
    runtime_images: dict[str, str] = field(default_factory=dict)
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
