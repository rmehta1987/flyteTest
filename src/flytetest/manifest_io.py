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
    """Recursively normalize task output values so json.dumps can serialize them.

    Flyte task outputs and result-bundle helpers frequently carry ``Path``
    objects and tuples, neither of which ``json.dumps`` handles by default.
    This function converts them in-place so manifests and run records can be
    serialized without a custom encoder at every call site.

    Args:
        value: Arbitrary payload from a manifest, result bundle, or task
            output.  ``Path`` instances are converted to POSIX strings;
            tuples are flattened to lists; dicts and lists are recursively
            normalized.  All other types are returned unchanged.

    Returns:
        A JSON-serializable copy of *value*.  The original is not mutated.
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
    """Write a manifest or metadata payload as indented, human-readable JSON.

    Uses 2-space indentation so result-bundle manifests can be inspected in a
    terminal or diff tool without a JSON formatter.  Creates the parent
    directory when it does not exist so task modules do not need to mkdir
    before calling this function.

    Unlike the atomic write in ``spec_executor.py``, this helper does not
    swap through a temporary file.  Manifests are written once at the end of
    a successful task run, so partial writes from a mid-write crash are a
    signal that the task did not complete rather than a consistency hazard.

    Args:
        path: Destination path for the JSON file — typically
            ``<result_dir>/run_manifest.json`` but also used for other
            bundle metadata files.
        payload: Manifest or metadata dict.  Values are normalized through
            :func:`as_json_compatible` so ``Path`` objects and tuples are
            handled automatically.

    Returns:
        *path* after the file is written, so callers can chain or log the
        location.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(as_json_compatible(payload), indent=2))
    return path


def read_json(path: Path) -> dict[str, Any]:
    """Read one JSON file into a dictionary."""
    return json.loads(path.read_text())


def copy_file(source: Path, destination: Path) -> Path:
    """Stage one file into a result bundle at a deterministic path.

    Uses ``shutil.copy2`` rather than ``copy`` to preserve the source
    file's modification timestamp, which matters when downstream tools
    check file age to decide whether to re-run (e.g. ``make``-style
    dependency checking in some PASA helpers).

    Creates the destination parent directory when it does not exist, so
    task modules do not need to mkdir before staging each output file.

    Args:
        source: File to copy into the bundle; must exist.
        destination: Exact file path within the result bundle, not a
            directory.  The parent is created automatically.

    Returns:
        *destination* after the copy completes, so callers can record
        the staged path in the manifest without a separate lookup.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def copy_tree(source: Path, destination: Path, *, dirs_exist_ok: bool = False) -> Path:
    """Stage a tool output directory into a result bundle.

    The default behaviour (``dirs_exist_ok=False``) removes an existing
    destination tree before copying, so the bundle always reflects exactly
    what the tool produced in the current run rather than accumulating stale
    files from an earlier run in the same output directory.

    Set ``dirs_exist_ok=True`` only when deliberately merging two tool output
    trees into one bundle directory, such as when combining PASA assembly
    and alignment outputs under a single result root.

    Args:
        source: Tool output directory to copy into the bundle.  Must exist
            and be a directory.
        destination: Target directory path within the result bundle.  Created
            by ``shutil.copytree``; must not exist when
            ``dirs_exist_ok=False`` (the rmtree above handles that).
        dirs_exist_ok: Set ``True`` to merge *source* into an existing
            *destination* instead of replacing it.  Use sparingly; the
            default clean-copy behaviour is safer.

    Returns:
        *destination* after the copy completes, so callers can record the
        staged path in the manifest.
    """
    if destination.exists() and not dirs_exist_ok:
        shutil.rmtree(destination)
    shutil.copytree(source, destination, dirs_exist_ok=dirs_exist_ok)
    return destination
