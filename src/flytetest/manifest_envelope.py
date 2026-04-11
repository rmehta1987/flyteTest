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
        stage: A value used by the helper.
        assumptions: A value used by the helper.
        inputs: The inputs forwarded to the workflow or task helper.
        outputs: A value used by the helper.
        code_reference: A value used by the helper.
        tool_ref: A value used by the helper.

    Returns:
        The returned `dict[str, Any]` value used by the caller.
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
