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
    """Recursively convert one value into JSON-serializable primitives.

    Args:
        value: The value or values processed by the helper.

    Returns:
        The returned `Any` value used by the caller.
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
        path: A filesystem path used by the helper.
        payload: The structured payload to serialize or inspect.

    Returns:
        The returned `Path` value used by the caller.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(as_json_compatible(payload), indent=2))
    return path


def read_json(path: Path) -> dict[str, Any]:
    """Read one JSON file into a dictionary.

    Args:
        path: A filesystem path used by the helper.

    Returns:
        The returned `dict[str, Any]` value used by the caller.
"""
    return json.loads(path.read_text())


def copy_file(source: Path, destination: Path) -> Path:
    """Copy one file to a deterministic destination path.

    Args:
        source: A filesystem path used by the helper.
        destination: A filesystem path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def copy_tree(source: Path, destination: Path, *, dirs_exist_ok: bool = False) -> Path:
    """Copy one directory tree to a deterministic destination path.

    Args:
        source: A filesystem path used by the helper.
        destination: A filesystem path used by the helper.
        dirs_exist_ok: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    if destination.exists() and not dirs_exist_ok:
        shutil.rmtree(destination)
    shutil.copytree(source, destination, dirs_exist_ok=dirs_exist_ok)
    return destination
