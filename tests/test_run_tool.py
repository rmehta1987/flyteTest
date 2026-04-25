"""Tests for run_tool execution modes in config.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

import pytest

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest.config import run_tool


class TestRunToolPythonCallableMode:
    def test_callable_is_invoked_with_kwargs(self):
        calls = []

        def my_fn(x: int, y: str) -> None:
            calls.append((x, y))

        run_tool(python_callable=my_fn, callable_kwargs={"x": 42, "y": "hello"})
        assert calls == [(42, "hello")]

    def test_callable_with_no_kwargs(self):
        called = []
        run_tool(python_callable=lambda: called.append(True))
        assert called == [True]

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
        def boom():
            raise ValueError("deliberate")

        with pytest.raises(ValueError, match="deliberate"):
            run_tool(python_callable=boom)

    def test_callable_kwargs_none_treated_as_empty(self):
        calls = []
        run_tool(python_callable=lambda: calls.append(True), callable_kwargs=None)
        assert calls == [True]


class TestRunToolNativeMode:
    def test_native_mode_runs_cmd(self, tmp_path):
        out = tmp_path / "out.txt"
        run_tool(cmd=["echo", "hello"], sif="", bind_paths=[], stdout_path=out)
        assert out.read_text().strip() == "hello"

    def test_missing_cmd_raises_value_error(self):
        with pytest.raises(ValueError, match="cmd.*required"):
            run_tool()

    def test_missing_cmd_with_no_callable_raises(self):
        with pytest.raises(ValueError):
            run_tool(sif="")


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

    def test_sif_mode_none_bind_paths_treated_as_empty(self, tmp_path):
        fake_sif = tmp_path / "tool.sif"
        fake_sif.write_bytes(b"fake")
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd

        with patch("flytetest.config.run", fake_run), \
             patch("flytetest.config.container_runtime", return_value="apptainer"):
            run_tool(cmd=["echo", "hi"], sif=str(fake_sif), bind_paths=None)

        assert "echo" in captured["cmd"]
