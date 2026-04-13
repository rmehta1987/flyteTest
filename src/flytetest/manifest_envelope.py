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
    """Build the common manifest envelope used by task-level result bundles.

    Args:
        stage: Pipeline stage name recorded in the manifest.
        assumptions: Ordered notes about assumptions that shaped the stage.
        inputs: Inputs forwarded into the stage contract.
        outputs: Outputs produced by the stage contract.
        code_reference: Optional pointer to the source file or workflow note.
        tool_ref: Optional name of the external tool that implemented the step.

    Returns:
        A canonical manifest dictionary with the shared stage envelope and any
        optional provenance fields that were supplied.
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
