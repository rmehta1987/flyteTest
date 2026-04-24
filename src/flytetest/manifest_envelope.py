"""Shared helper for the common manifest envelope used by task modules.

This module standardizes the small envelope that most stage manifests share:
`stage`, `assumptions`, `inputs`, and `outputs`. Task modules can still add
their own fields after the envelope is built when they need more provenance or
task-specific metadata.
"""

from __future__ import annotations

from typing import Any


def build_manifest_envelope(
    stage: str,
    assumptions: list[str],
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    *,
    code_reference: str | None = None,
    tool_ref: str | None = None,
) -> dict[str, Any]:
    """Assemble the shared skeleton that every stage manifest must carry.

    All task result bundles in this repo write a manifest file (typically
    ``run_manifest.json`` at the workflow level; ``run_manifest_<stage>.json``
    for individual variant-calling tasks) that starts with this envelope so
    downstream stages and the MCP result-inspection tools can rely on a
    common structure.  Task modules add their own fields
    after calling this function when they need extra provenance or tool-level
    metadata (PASA assembly IDs, BRAKER3 run directories, etc.).

    Args:
        stage: Pipeline stage name written verbatim into the manifest;
            matches the task function name so the manifest is self-identifying
            when inspected outside a running workflow.
        assumptions: Ordered notes accumulated during the stage run, such as
            which input files were found, which tool flags were applied, or
            which biological constraints governed the run.  Written in order
            so a reader can reconstruct the decision sequence.
        inputs: Paths and parameters that the stage received, serialized for
            the manifest record.  Downstream tools read this field to locate
            the upstream result directories without re-running the planner.
        outputs: Paths and metadata the stage produced.  Downstream stages
            and the MCP result viewer read this field to locate result files
            without scanning the bundle directory.
        code_reference: Source file or workflow-note reference embedded for
            traceability — typically the ``__file__`` of the task module or
            a ``docs/`` path.  ``None`` omits the field.
        tool_ref: External tool name (e.g. ``"PASA"``, ``"TransDecoder"``)
            recorded so the manifest carries the tool provenance without
            requiring separate lookup.  ``None`` omits the field.

    Returns:
        Manifest dict with at minimum ``stage``, ``assumptions``, ``inputs``,
        and ``outputs``.  The caller writes this dict as ``run_manifest.json``
        inside the result bundle directory.
    """
    manifest: dict[str, Any] = {
        "stage": stage,
        "assumptions": list(assumptions),
        "inputs": inputs,
        "outputs": outputs,
    }
    if code_reference is not None:
        manifest["code_reference"] = code_reference
    if tool_ref is not None:
        manifest["tool_ref"] = tool_ref
    return manifest
