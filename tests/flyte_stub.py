"""Minimal Flyte test double used by the synthetic Exonerate suite.

The repository's current test environment does not ship the real Flyte SDK, so
the tests install these small stand-ins before importing the pipeline modules.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(slots=True)
class _Artifact:
    """Simple file-or-directory wrapper with the methods the tasks expect."""

    path: str

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    @classmethod
    def from_local_sync(cls, path: str | Path) -> "_Artifact":
        return cls(path)

    def download_sync(self) -> str:
        return self.path


class File(_Artifact):
    """Stub replacement for `flyte.io.File`."""


class Dir(_Artifact):
    """Stub replacement for `flyte.io.Dir`."""


class TaskEnvironment:
    """Minimal stand-in for the Flyte task environment decorator container."""

    def __init__(self, name: str) -> None:
        self.name = name

    def task(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return fn


def install_flyte_stub() -> None:
    """Install the Flyte stub modules into `sys.modules` if needed."""
    flyte_mod = types.ModuleType("flyte")
    io_mod = types.ModuleType("flyte.io")
    io_mod.File = File
    io_mod.Dir = Dir
    flyte_mod.TaskEnvironment = TaskEnvironment
    flyte_mod.io = io_mod
    sys.modules["flyte"] = flyte_mod
    sys.modules["flyte.io"] = io_mod
