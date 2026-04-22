"""Planner-facing catalog of available workflows and tasks.

This package lists the registered stages the planner can choose from. Each
entry describes the public inputs, outputs, and biological role of a task or
workflow, so user requests stay tied to known Flyte code instead of ad hoc
runtime generation.

Entries are split by pipeline family across the private submodules and
collected here into a single ``REGISTRY_ENTRIES`` tuple. All existing public
imports (``REGISTRY_ENTRIES``, ``list_entries``, ``get_entry``,
``get_pipeline_stages``, ``RegistryEntry``, ``InterfaceField``,
``RegistryCompatibilityMetadata``, ``Category``) continue to work unchanged.
"""

from __future__ import annotations

from flytetest.registry._types import (  # noqa: F401
    Category,
    InterfaceField,
    RegistryCompatibilityMetadata,
    RegistryEntry,
)
from flytetest.registry._transcript_evidence import TRANSCRIPT_EVIDENCE_ENTRIES
from flytetest.registry._consensus import CONSENSUS_ENTRIES
from flytetest.registry._protein_evidence import PROTEIN_EVIDENCE_ENTRIES
from flytetest.registry._annotation import ANNOTATION_ENTRIES
from flytetest.registry._evm import EVM_ENTRIES
from flytetest.registry._postprocessing import POSTPROCESSING_ENTRIES
from flytetest.registry._rnaseq import RNASEQ_ENTRIES
from flytetest.registry._variant_calling import VARIANT_CALLING_ENTRIES

REGISTRY_ENTRIES: tuple[RegistryEntry, ...] = (
    TRANSCRIPT_EVIDENCE_ENTRIES
    + CONSENSUS_ENTRIES
    + PROTEIN_EVIDENCE_ENTRIES
    + ANNOTATION_ENTRIES
    + EVM_ENTRIES
    + POSTPROCESSING_ENTRIES
    + RNASEQ_ENTRIES
    + VARIANT_CALLING_ENTRIES
)

_REGISTRY: dict[str, RegistryEntry] = {entry.name: entry for entry in REGISTRY_ENTRIES}


def list_entries(category: Category | None = None) -> tuple[RegistryEntry, ...]:
    """List supported catalog entries, optionally restricted to tasks or workflows.

    Args:
        category: Optional category filter for tasks or workflows.

    Returns:
        The supported catalog entries in the requested category, if any.
    """
    if category is None:
        return REGISTRY_ENTRIES
    return tuple(entry for entry in REGISTRY_ENTRIES if entry.category == category)


def get_entry(name: str) -> RegistryEntry:
    """Return one catalog entry by name with a helpful error for unknown names.

    Args:
        name: The supported entry name being looked up.

    Returns:
        The catalog entry for the requested name.
    """
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        supported = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"Unknown catalog entry '{name}'. Supported entries: {supported}") from exc


def get_pipeline_stages(family: str) -> list[tuple[str, str]]:
    """Return (workflow_name, biological_stage_label) pairs for a pipeline family.

    Entries are ordered by pipeline_stage_order.  Workflows with
    pipeline_family != family or pipeline_stage_order == 0 are excluded.
    Returns an empty list for unknown or empty family strings.
    """
    if not family:
        return []
    candidates = [
        (entry.name, entry.compatibility.biological_stage, entry.compatibility.pipeline_stage_order)
        for entry in REGISTRY_ENTRIES
        if entry.compatibility.pipeline_family == family and entry.compatibility.pipeline_stage_order > 0
    ]
    candidates.sort(key=lambda t: t[2])
    return [(name, label) for name, label, _ in candidates]
