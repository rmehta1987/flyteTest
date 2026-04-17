"""Lightweight Flyte test doubles that replace the real SDK types during unit tests.

WHY THIS EXISTS
---------------
The real `flyte.io.File` and `flyte.io.Dir` are Pydantic models designed for
remote-storage workflows. Their `download_sync()` method copies the file/directory
to a new temporary location before returning a path — which is correct in production
(where inputs live in object storage) but wrong in tests (where inputs are already
local temp paths that tasks should use in-place).

This module provides drop-in replacements that:
  - Accept a plain `str | Path` in their constructor (same as the real types' `path=` kwarg)
  - Return the original path directly from `download_sync()` with no copy or I/O
  - Leave `TaskEnvironment.task()` as a no-op so task modules import cleanly without
    a live Flyte cluster connection

HOW IT WORKS
------------
`install_flyte_stub()` patches `sys.modules` before any test module imports
`flytetest.tasks.*` or `flytetest.workflows.*`. Those modules do:

    from flyte.io import Dir, File

Because the patch runs first, they receive these stub classes instead of the
real Pydantic models. All task logic that calls `file.download_sync()` or
`dir.download_sync()` gets back the exact local path the test passed in.

WHERE IT IS CALLED
------------------
`tests/__init__.py` calls `install_flyte_stub()` once at package load time,
which is sufficient when running the full suite via `python3 -m unittest discover`.
Individual test files that may be run directly (e.g. `python3 tests/test_agat.py`)
also call it at module level as a safety net.

FUTURE
------
The real `flyte` SDK (v2.1.2+) is installed in the project venv. A future cleanup
could remove this stub by relying on the real types — `Dir.download_sync()` already
returns the same local path, and `File.download_sync()` behavior differences are
small. See the "Deferred TODOs" section in docs/dataserialization/checklist.md.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(slots=True)
class _Artifact:
    """Base for File and Dir stubs.

    The real `flyte.io.File` / `flyte.io.Dir` are Pydantic models whose
    `download_sync()` copies the payload to a new temp location. This base
    class skips the copy: `download_sync()` returns `self.path` directly so
    tests work against the original local paths they set up.
    """

    path: str

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    def download_sync(self) -> str:
        """Return the local path as-is — no copy, no remote I/O."""
        return self.path


class File(_Artifact):
    """Stub for `flyte.io.File`. Stands in wherever tasks accept a file input."""


class Dir(_Artifact):
    """Stub for `flyte.io.Dir`. Stands in wherever tasks accept a directory input."""


class TaskEnvironment:
    """Stub for `flyte.TaskEnvironment`.

    The real class registers tasks with the Flyte control plane. In tests we
    just need the `@env.task` decorator to be a no-op so task modules can be
    imported and called as plain functions without a cluster connection.
    """

    def __init__(self, name: str, **kwargs: object) -> None:
        self.name = name
        self.kwargs = kwargs

    def task(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Pass the function through unchanged."""
        return fn


@dataclass(slots=True)
class Resources:
    """Stub for `flyte.Resources`. Holds CPU/memory/GPU specs as plain strings."""

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None


def install_flyte_stub() -> None:
    """Patch `sys.modules` so that `from flyte.io import File, Dir` resolves to
    the stubs above instead of the real Pydantic models.

    Must be called before any `flytetest.tasks.*` or `flytetest.workflows.*`
    module is imported, because Python caches the resolved names at import time.
    """
    flyte_mod = types.ModuleType("flyte")
    io_mod = types.ModuleType("flyte.io")
    io_mod.File = File
    io_mod.Dir = Dir
    flyte_mod.Resources = Resources
    flyte_mod.TaskEnvironment = TaskEnvironment
    flyte_mod.io = io_mod
    sys.modules["flyte"] = flyte_mod
    sys.modules["flyte.io"] = io_mod
