"""Minimal Flyte test double used by the synthetic Exonerate suite.

The repository's current test environment does not ship the real Flyte SDK, so
the tests install these small stand-ins before importing the pipeline modules.
These wrappers stay local-path-only and never model remote-transfer behavior.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(slots=True)
class _Artifact:
    """Simple local-path file-or-directory wrapper with the methods tasks expect."""

    path: str

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    def download_sync(self) -> str:
        return self.path


class File(_Artifact):
    """Stub replacement for `flyte.io.File`."""


class Dir(_Artifact):
    """Stub replacement for `flyte.io.Dir`."""


class TaskEnvironment:
    """Minimal stand-in for the Flyte task environment decorator container."""

    def __init__(self, name: str, **kwargs: object) -> None:
        self.name = name
        self.kwargs = kwargs

    def task(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return fn


@dataclass(slots=True)
class Resources:
    """Minimal stand-in for `flyte.Resources`."""

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None


def install_flyte_stub() -> None:
    """Install the Flyte stub modules into `sys.modules` if needed."""
    flyte_mod = types.ModuleType("flyte")
    io_mod = types.ModuleType("flyte.io")
    io_mod.File = File
    io_mod.Dir = Dir
    flyte_mod.Resources = Resources
    flyte_mod.TaskEnvironment = TaskEnvironment
    flyte_mod.io = io_mod
    sys.modules["flyte"] = flyte_mod
    sys.modules["flyte.io"] = io_mod
