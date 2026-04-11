"""Bounded composition of registered workflows and tasks.

This module provides `compose_workflow_path()` and
`bundle_composition_into_workflow_spec()` for Milestone 15. Together they find
short, reviewable stage sequences from biological intent, keep the search
bounded, avoid cycles, and turn a successful path into a frozen workflow spec
that can be inspected before execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from flytetest.registry import RegistryEntry, get_entry
from flytetest.specs import (
    TypedFieldSpec,
    WorkflowEdgeSpec,
    WorkflowNodeSpec,
    WorkflowOutputBinding,
    WorkflowSpec,
)


# Keep composition searches small and predictable for reviewers.
DEFAULT_MAX_COMPOSITION_DEPTH = 5
"""Maximum number of sequential stages allowed in one composed workflow."""

DEFAULT_MAX_BREADTH_PER_STAGE = 10
"""Maximum number of compatible next stages considered at each step."""


@dataclass(frozen=True)
class CompositionDeclineReason:
    """Structured explanation for why a composition could not be built."""

    category: str
    """Short label for the reason composition stopped."""

    message: str
    """Human-readable explanation of the decline."""

    suggested_alternatives: tuple[str, ...] = field(default_factory=tuple)
    """Other registered workflows or tasks to try instead, if known."""


def _find_compatible_successors(
    current_entry: RegistryEntry,
    current_entry_name: str | None = None,
    max_breadth: int = DEFAULT_MAX_BREADTH_PER_STAGE,
) -> list[str]:
    """Return registered stages that can consume the current stage's outputs.

    Args:
        current_entry: The registry entry whose outputs are being reused.
        current_entry_name: The current entry name, used to avoid self-links.
        max_breadth: Maximum number of next stages to return.

    Returns:
        Registry entry names that can accept the current stage's outputs.
    """
    produced_types = set(current_entry.compatibility.produced_planner_types or ())
    if not produced_types:
        return []

    compatible_successors: list[str] = []
    for candidate_name in _get_all_synthesis_eligible_entries():
        if current_entry_name and candidate_name == current_entry_name:
            continue
        try:
            candidate_entry = get_entry(candidate_name)
            accepted = set(candidate_entry.compatibility.accepted_planner_types or ())
            if produced_types & accepted:
                compatible_successors.append(candidate_name)
                if len(compatible_successors) >= max_breadth:
                    break
        except (KeyError, ValueError):
            continue

    return compatible_successors


def _get_all_synthesis_eligible_entries() -> list[str]:
    """Return registered entries that are allowed to seed composition.

    Returns:
        Registry entry names whose compatibility metadata allows composition.
    """
    eligible: list[str] = []
    try:
        # Import inside the helper to avoid a circular import during registry setup.
        from flytetest.registry import REGISTRY_ENTRIES

        for entry in REGISTRY_ENTRIES:
            if entry.compatibility.synthesis_eligible:
                eligible.append(entry.name)
    except (ImportError, AttributeError):
        # If the registry is unavailable, return no candidates.
        pass
    return eligible


def _detect_cycles(path: Sequence[str]) -> bool:
    """Return ``True`` when a path repeats a stage name.

    Args:
        path: Stage names selected so far.

    Returns:
        ``True`` if any stage appears more than once.
    """
    seen = set()
    for stage_name in path:
        if stage_name in seen:
            return True
        seen.add(stage_name)
    return False


def compose_workflow_path(
    start_entry_name: str,
    target_output_type: str | None = None,
    max_depth: int = DEFAULT_MAX_COMPOSITION_DEPTH,
) -> tuple[tuple[str, ...], CompositionDeclineReason | None]:
    """Build a bounded path of registered stages that matches the request.

    Args:
        start_entry_name: Registry entry name to start from.
        target_output_type: Optional biological type that should appear at the end.
        max_depth: Maximum number of stages to include.

    Returns:
        A tuple of ``(path, decline_reason)``. On success, ``decline_reason`` is
        ``None``. On failure, the path is empty and the decline explains why.
    """
    try:
        start_entry = get_entry(start_entry_name)
    except (KeyError, ValueError):
        return (
            (),
            CompositionDeclineReason(
                category="unsupported_stage",
                message=f"Start stage `{start_entry_name}` is not found in the registry.",
            ),
        )

    if not start_entry.compatibility.synthesis_eligible:
        return (
            (),
            CompositionDeclineReason(
                category="not_composition_eligible",
                message=f"Start stage `{start_entry_name}` is not marked as synthesis-eligible in the registry.",
                suggested_alternatives=tuple(_get_all_synthesis_eligible_entries()[:3]),
            ),
        )

    path: list[str] = [start_entry_name]

    # Walk forward until we reach the target type or hit a composition limit.
    for _ in range(max_depth - 1):
        current_entry = get_entry(path[-1])
        produced_types = set(current_entry.compatibility.produced_planner_types or ())

        if target_output_type and target_output_type in produced_types:
            break

        successors = _find_compatible_successors(
            current_entry,
            current_entry_name=path[-1],
        )
        if not successors:
            break  # No next stage fits, so return the path built so far.

        candidate_name = successors[0]
        test_path = path + [candidate_name]
        if _detect_cycles(test_path):
            # Stop if the next step would repeat a stage.
            break

        path.append(candidate_name)

    if target_output_type:
        final_entry = get_entry(path[-1])
        final_types = set(final_entry.compatibility.produced_planner_types or ())
        if target_output_type not in final_types:
            return (
                (),
                CompositionDeclineReason(
                    category="target_unreachable",
                    message=f"Composition path {' -> '.join(path)} produces {final_types} but does not include the target type `{target_output_type}`.",
                    suggested_alternatives=tuple(
                        stage for stage in _get_all_synthesis_eligible_entries()
                        if target_output_type in get_entry(stage).compatibility.produced_planner_types
                    )[:3],
                ),
            )

    return tuple(path), None


def bundle_composition_into_workflow_spec(
    composition_path: Sequence[str],
    biological_intent: str,
    source_prompt: str = "",
) -> tuple[WorkflowSpec | None, CompositionDeclineReason | None]:
    """Bundle a composition path into a frozen, reviewable WorkflowSpec.

    This function takes a sequence of stage names and converts it into explicit
    nodes, edges, and output bindings suitable for review and later execution.

    Args:
        composition_path: The ordered sequence of registry entry names to compose.
        biological_intent: Human-readable description of what the composition is for.
        source_prompt: Optional source prompt for provenance tracking.

    Returns:
        A tuple of (workflow_spec, decline_reason). On success, the spec is
        non-None and decline_reason is None. On failure, the spec is None
        and decline_reason explains why bundling failed.
    """
    if not composition_path:
        return (
            None,
            CompositionDeclineReason(
                category="empty_composition",
                message="Cannot bundle an empty composition path into a workflow spec.",
            ),
        )

    if len(composition_path) == 1:
        # A one-stage path is just a direct reference to the registered entry.
        stage_name = composition_path[0]
        try:
            entry = get_entry(stage_name)
        except (KeyError, ValueError):
            return (
                None,
                CompositionDeclineReason(
                    category="invalid_stage",
                    message=f"Stage `{stage_name}` could not be found in the registry.",
                ),
            )

        inputs = tuple(
            TypedFieldSpec(
                name=planner_type_name,
                type_name=planner_type_name,
                description=f"Planner input `{planner_type_name}`.",
                planner_type_names=(planner_type_name,),
            )
            for planner_type_name in (entry.compatibility.accepted_planner_types or ())
        )
        outputs = tuple(
            TypedFieldSpec(
                name=planner_type_name,
                type_name=planner_type_name,
                description=f"Planned output `{planner_type_name}`.",
                planner_type_names=(planner_type_name,),
            )
            for planner_type_name in (entry.compatibility.produced_planner_types or ())
        )

        return (
            WorkflowSpec(
                name=f"single_stage_{stage_name}",
                analysis_goal=biological_intent,
                inputs=inputs,
                outputs=outputs,
                nodes=(
                    WorkflowNodeSpec(
                        name="stage",
                        kind=entry.category,
                        reference_name=entry.name,
                        description=f"Direct selection of registered {entry.category} `{entry.name}`.",
                        output_names=tuple(field.name for field in entry.outputs),
                    ),
                ),
                edges=(),
                reusable_registered_refs=(entry.name,),
                final_output_bindings=(
                    WorkflowOutputBinding(
                        output_name=entry.outputs[0].name if entry.outputs else "results",
                        source_node="stage",
                        source_output=entry.outputs[0].name if entry.outputs else "results",
                        description="Pass through the registered stage output.",
                    ),
                ),
                replay_metadata={"composition_type": "single_stage_reference", "source_prompt": source_prompt},
            ),
            None,
        )

    # Build nodes and edges for a multi-stage path.
    nodes: list[WorkflowNodeSpec] = []
    edges: list[WorkflowEdgeSpec] = []

    for idx, stage_name in enumerate(composition_path):
        try:
            entry = get_entry(stage_name)
        except (KeyError, ValueError):
            return (
                None,
                CompositionDeclineReason(
                    category="invalid_stage",
                    message=f"Stage `{stage_name}` at position {idx} could not be found in the registry.",
                ),
            )

        node_id = f"stage_{idx}"
        nodes.append(
            WorkflowNodeSpec(
                name=node_id,
                kind=entry.category,
                reference_name=entry.name,
                description=f"Stage {idx + 1} of {len(composition_path)}: `{entry.name}`.",
                output_names=tuple(field.name for field in entry.outputs),
            ),
        )

        if idx > 0:
            prev_entry = get_entry(composition_path[idx - 1])
            prev_node_id = f"stage_{idx - 1}"
            if prev_entry.outputs and entry.inputs:
                edges.append(
                    WorkflowEdgeSpec(
                        source_node=prev_node_id,
                        source_output=prev_entry.outputs[0].name,
                        target_node=node_id,
                        target_input=entry.inputs[0].name,
                    ),
                )

    first_entry = get_entry(composition_path[0])
    last_entry = get_entry(composition_path[-1])

    inputs = tuple(
        TypedFieldSpec(
            name=planner_type_name,
            type_name=planner_type_name,
            description=f"Planner input `{planner_type_name}` for the first stage.",
            planner_type_names=(planner_type_name,),
        )
        for planner_type_name in (first_entry.compatibility.accepted_planner_types or ())
    )

    outputs = tuple(
        TypedFieldSpec(
            name=planner_type_name,
            type_name=planner_type_name,
            description=f"Composition output `{planner_type_name}` from the final stage.",
            planner_type_names=(planner_type_name,),
        )
        for planner_type_name in (last_entry.compatibility.produced_planner_types or ())
    )

    return (
        WorkflowSpec(
            name=f"composed_{'_'.join(composition_path[:2])}",
            analysis_goal=biological_intent,
            inputs=inputs,
            outputs=outputs,
            nodes=tuple(nodes),
            edges=tuple(edges),
            ordering_constraints=tuple(f"stage_{i} before stage_{i + 1}" for i in range(len(nodes) - 1)),
            reusable_registered_refs=tuple(composition_path),
            final_output_bindings=(
                WorkflowOutputBinding(
                    output_name=last_entry.outputs[0].name if last_entry.outputs else "results",
                    source_node=f"stage_{len(composition_path) - 1}",
                    source_output=last_entry.outputs[0].name if last_entry.outputs else "results",
                    description="Final output bundle from the composed workflow.",
                ),
            ),
            replay_metadata={
                "composition_type": "multi_stage_registry_constrained",
                "path_length": len(composition_path),
                "source_prompt": source_prompt,
            },
        ),
        None,
    )


__all__ = [
    "CompositionDeclineReason",
    "compose_workflow_path",
    "bundle_composition_into_workflow_spec",
    "DEFAULT_MAX_COMPOSITION_DEPTH",
    "DEFAULT_MAX_BREADTH_PER_STAGE",
]
