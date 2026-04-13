"""Shared manifest and file-copy helpers for FLyteTest task modules.

This module keeps the mechanical JSON and filesystem staging logic in one
place so task modules can share it without changing their manifest contracts
or output-path behavior.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def as_json_compatible(value: Any) -> Any:
    """Recursively convert paths and containers into JSON-serializable data.

    Args:
        value: Arbitrary payload from a manifest or result bundle.

    Returns:
        JSON-compatible data with `Path` objects stringified and tuples
        converted to lists so `json.dumps()` can serialize the result.
    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: as_json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [as_json_compatible(item) for item in value]
    if isinstance(value, list):
        return [as_json_compatible(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write one JSON payload with deterministic indentation.

    Args:
        path: Destination `run_manifest.json` or related bundle file.
        payload: Structured manifest or metadata to serialize.

    Returns:
        The destination path after the JSON file is written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(as_json_compatible(payload), indent=2))
    return path


def read_json(path: Path) -> dict[str, Any]:
    """Read one JSON file into a dictionary."""
    return json.loads(path.read_text())


def copy_file(source: Path, destination: Path) -> Path:
    """Copy one file to a deterministic destination path.

    Args:
        source: File to stage into a bundle or result directory.
        destination: Path where the file should be copied.

    Returns:
        The destination path after the copy completes.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def copy_tree(source: Path, destination: Path, *, dirs_exist_ok: bool = False) -> Path:
    """Copy one directory tree to a deterministic destination path.

    Args:
        source: Directory tree to stage into a bundle or result directory.
        destination: Target directory for the copied tree.
        dirs_exist_ok: Allow the destination to exist when merging trees.

    Returns:
        The destination directory after the copy completes.
    """
    if destination.exists() and not dirs_exist_ok:
        shutil.rmtree(destination)
    shutil.copytree(source, destination, dirs_exist_ok=dirs_exist_ok)
    return destination
