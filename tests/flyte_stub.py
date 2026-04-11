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
    """Simple local-path file-or-directory wrapper with the methods tasks expect.

    This class keeps the current contract explicit and reviewable.
"""

    path: str

    def __init__(self, path: str | Path) -> None:
        """Store the local filesystem path as a plain string.

    Args:
        path: A filesystem path used by the helper.
"""
        self.path = str(path)

    def download_sync(self) -> str:
        """Return the local filesystem path without any transfer step.

    This helper keeps the current behavior explicit and reviewable.

    Returns:
        The returned `str` value used by the caller.
"""
        return self.path


class File(_Artifact):
    """Stub replacement for `flyte.io.File`.

    This class keeps the current contract explicit and reviewable.
"""


class Dir(_Artifact):
    """Stub replacement for `flyte.io.Dir`.

    This class keeps the current contract explicit and reviewable.
"""


class TaskEnvironment:
    """Minimal stand-in for the Flyte task environment decorator container.

    This class keeps the current contract explicit and reviewable.
"""

    def __init__(self, name: str, **kwargs: object) -> None:
        """Record the environment name and constructor kwargs for assertions.

    Args:
        name: A value used by the helper.
"""
        self.name = name
        self.kwargs = kwargs

    def task(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Return the function unchanged, just like the test double expects.

    Args:
        fn: A value used by the helper.

    Returns:
        The returned `Callable[..., Any]` value used by the caller.
"""
        return fn


@dataclass(slots=True)
class Resources:
    """Minimal stand-in for `flyte.Resources`.

    This class keeps the current contract explicit and reviewable.
"""

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None


def install_flyte_stub() -> None:
    """Install the Flyte stub modules into `sys.modules` if needed.

    This helper keeps the current behavior explicit and reviewable.
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
