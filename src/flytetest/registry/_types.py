"""Shared dataclass definitions for the FLyteTest registry package."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


Category = Literal["task", "workflow"]


@dataclass(frozen=True)
class InterfaceField:
    """One named input or output listed in the catalog.

    These fields keep the public shape readable without importing Flyte objects
    or task functions.
    """

    name: str
    type: str
    description: str


@dataclass(frozen=True)
class RegistryCompatibilityMetadata:
    """Planner notes about where a stage fits in the biology pipeline.

    The base catalog says that a task or workflow exists. This metadata says
    which biology types the entry can accept, which types it can produce, and
    when the planner may safely reuse it in a generated plan.
    """

    biological_stage: str = "unspecified"
    accepted_planner_types: tuple[str, ...] = ()
    produced_planner_types: tuple[str, ...] = ()
    reusable_as_reference: bool = False
    execution_defaults: dict[str, object] = field(default_factory=dict)
    supported_execution_profiles: tuple[str, ...] = ("local",)
    runtime_image_policy: str = "Optional local tool image paths remain user-supplied when supported."
    synthesis_eligible: bool = False
    composition_constraints: tuple[str, ...] = ()
    pipeline_family: str = ""
    pipeline_stage_order: int = 0


@dataclass(frozen=True)
class RegistryEntry:
    """One registered task or workflow that the planner may choose.

    Catalog entries keep the user-facing description separate from the runnable
    Flyte definitions. That separation lets the planner inspect available
    stages without importing every task module or editing workflow code.
    """

    name: str
    category: Category
    description: str
    inputs: tuple[InterfaceField, ...]
    outputs: tuple[InterfaceField, ...]
    tags: tuple[str, ...]
    compatibility: RegistryCompatibilityMetadata = field(default_factory=RegistryCompatibilityMetadata)
    showcase_module: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serialize this catalog entry for callers that need plain dictionaries.

        The method keeps `inputs` and `outputs` as lists of simple dictionaries
        while still including the compatibility metadata. The `showcase_module`
        field is excluded from the serialized output to preserve the public
        payload shape.

        Returns:
            A `dict[str, object]` representation of the catalog entry.
        """
        data = asdict(self)
        data.pop("showcase_module", None)
        data["inputs"] = [asdict(f) for f in self.inputs]
        data["outputs"] = [asdict(f) for f in self.outputs]
        return data
