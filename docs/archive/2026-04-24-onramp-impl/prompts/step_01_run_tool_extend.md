# Step 01 — Extend `run_tool` to Support Python Callable and Documented Native Mode

Read `src/flytetest/config.py` before making any changes.

---

## Context

`run_tool` at `src/flytetest/config.py:245` currently has two execution paths:

- **SIF/container**: `sif` non-empty → `apptainer exec` wraps `cmd`
- **Native**: `sif` empty → `subprocess.run(cmd)` directly

Users who want to write a pure-Python task (no subprocess, no container) have no
supported path through `run_tool` today. They either bypass it entirely or fake an
empty command. Neither is correct.

We add a third path — **Python callable** — so all task execution flows through the
same entry point regardless of execution mode.

---

## Change — `src/flytetest/config.py`

### Imports to add (if not present)

```python
from collections.abc import Callable
from typing import Any
```

### New signature

Replace the current `run_tool` signature with:

```python
def run_tool(
    cmd: list[str] | None = None,
    sif: str = "",
    bind_paths: list[Path] | None = None,
    cwd: Path | None = None,
    stdout_path: Path | None = None,
    *,
    python_callable: Callable[..., Any] | None = None,
    callable_kwargs: dict[str, Any] | None = None,
) -> None:
    """Run a tool natively, inside a container, or as a pure-Python callable.

    Three execution modes — pick exactly one per call:

    **SIF/container** — ``sif`` non-empty:
        Runs ``cmd`` inside an Apptainer/Singularity image with the given
        ``bind_paths`` mounted read-write. Requires Apptainer or Singularity on
        the host PATH.

    **Native executable** — ``sif`` empty, ``cmd`` provided:
        Runs ``cmd`` directly via ``subprocess.run``.  Use for binaries on PATH
        (``samtools``, ``Rscript``, compiled C++) or absolute executable paths.
        No container overhead; the binary must be available on the compute node.

    **Python callable** — ``python_callable`` provided:
        Calls ``python_callable(**callable_kwargs)`` in-process.  No subprocess,
        no container.  Use for pure-Python logic that has no external binary
        dependency.  ``cmd``, ``sif``, and ``bind_paths`` are ignored.

    Args:
        cmd: Command arguments for native or containerized execution.
        sif: Container image path; empty string means native execution.
        bind_paths: Host paths to bind into the container (SIF mode only).
        cwd: Working directory for subprocess execution.
        stdout_path: Optional file that receives captured stdout (subprocess modes only).
        python_callable: A Python callable to invoke directly (callable mode).
        callable_kwargs: Keyword arguments forwarded to ``python_callable``.
    """
    if python_callable is not None:
        python_callable(**(callable_kwargs or {}))
        return

    if cmd is None:
        raise ValueError(
            "run_tool: 'cmd' is required when 'python_callable' is not provided."
        )

    if not sif:
        run(cmd, cwd=cwd, stdout_path=stdout_path)
        return

    # --- SIF/container path (unchanged) ---
    sif_path = Path(sif)
    if not sif_path.is_absolute():
        sif_path = Path(__file__).resolve().parents[2] / sif_path
    sif_abs = str(sif_path)
    mounts: set[str] = set()
    for path in (bind_paths or []):
        resolved = str(path.resolve())
        mounts.add(f"{resolved}:{resolved}")

    runtime = container_runtime()
    sing_cmd = [runtime, "exec", "--cleanenv"]
    for mount in sorted(mounts):
        sing_cmd.extend(["-B", mount])
    sing_cmd.extend([sif_abs, *cmd])
    run(sing_cmd, cwd=cwd, stdout_path=stdout_path)
```

**Backward compatibility note:** existing call sites use
`run_tool(cmd, sif, bind_paths)` positionally. Making `cmd` and `bind_paths`
optional (`None` default) does not break positional calls. No existing call site
needs to change.

---

## New test file — `tests/test_run_tool.py`

Create a new file. Test all three modes in isolation without touching the filesystem
for the callable mode test, and using `tmp_path` for subprocess tests.

```python
"""Tests for run_tool execution modes in config.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from flytetest.config import run_tool


class TestRunToolPythonCallableMode:
    def test_callable_is_invoked_with_kwargs(self):
        calls = []
        def my_fn(x: int, y: str) -> None:
            calls.append((x, y))

        run_tool(python_callable=my_fn, callable_kwargs={"x": 42, "y": "hello"})
        assert calls == [(42, "hello")]

    def test_callable_with_no_kwargs(self):
        calls = []
        run_tool(python_callable=lambda: calls.append(True))
        assert calls == [True]

    def test_callable_mode_ignores_cmd_and_sif(self):
        """When python_callable is set, cmd/sif/bind_paths are not used."""
        called = []
        run_tool(
            cmd=["should", "not", "run"],
            sif="should_not_use.sif",
            bind_paths=[],
            python_callable=lambda: called.append(True),
        )
        assert called == [True]

    def test_callable_exception_propagates(self):
        with pytest.raises(ValueError, match="deliberate"):
            run_tool(python_callable=lambda: (_ for _ in ()).throw(ValueError("deliberate")))


class TestRunToolNativeMode:
    def test_native_mode_runs_cmd(self, tmp_path):
        out = tmp_path / "out.txt"
        run_tool(cmd=["echo", "hello"], sif="", bind_paths=[], stdout_path=out)
        assert out.read_text().strip() == "hello"

    def test_missing_cmd_raises(self):
        with pytest.raises(ValueError, match="cmd.*required"):
            run_tool()


class TestRunToolSifMode:
    def test_sif_mode_builds_apptainer_command(self, tmp_path):
        """When sif is non-empty, run_tool assembles an apptainer exec command."""
        fake_sif = tmp_path / "tool.sif"
        fake_sif.write_bytes(b"fake")
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd

        with patch("flytetest.config.run", fake_run), \
             patch("flytetest.config.container_runtime", return_value="apptainer"):
            run_tool(
                cmd=["gatk", "--version"],
                sif=str(fake_sif),
                bind_paths=[tmp_path],
            )

        assert captured["cmd"][0] == "apptainer"
        assert "exec" in captured["cmd"]
        assert str(fake_sif) in captured["cmd"]
        assert "gatk" in captured["cmd"]
```

---

## Verification

```bash
python3 -m compileall src/flytetest/config.py

PYTHONPATH=src python3 -m pytest tests/test_run_tool.py -v

# Confirm existing task tests still pass (no regression in run_tool call sites)
PYTHONPATH=src python3 -m pytest tests/test_variant_calling.py -x -q
```
