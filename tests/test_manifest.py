"""Tests for the consolidated manifest module.

This module covers the shared envelope builder, the JSON serialization
helpers, and the result-bundle copy helpers — all of which now live in
``flytetest.manifest``.  Task-module aliases are exercised here too so
the migrated tasks (eggnog, functional, filtering, pasa) keep their
re-exported helper bindings honest after the consolidation.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

import flytetest.manifest as manifest
import flytetest.tasks.eggnog as eggnog
import flytetest.tasks.filtering as filtering
import flytetest.tasks.functional as functional
import flytetest.tasks.pasa as pasa
from flytetest.manifest import build_manifest_envelope


class ManifestEnvelopeTests(TestCase):
    """Coverage for the common manifest envelope builder.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_build_manifest_envelope_keeps_common_fields_in_place(self) -> None:
        """Build the shared envelope without forcing task-specific schema changes.
"""
        manifest = build_manifest_envelope(
            stage="example_stage",
            assumptions=["first assumption", "second assumption"],
            inputs={"input_path": "input.fa"},
            outputs={"output_path": "output.fa"},
        )

        self.assertEqual(manifest["stage"], "example_stage")
        self.assertEqual(manifest["assumptions"], ["first assumption", "second assumption"])
        self.assertEqual(manifest["inputs"], {"input_path": "input.fa"})
        self.assertEqual(manifest["outputs"], {"output_path": "output.fa"})
        self.assertNotIn("code_reference", manifest)
        self.assertNotIn("tool_ref", manifest)

    def test_build_manifest_envelope_can_include_optional_reference_fields(self) -> None:
        """Record optional code and tool references without making them mandatory.
"""
        manifest = build_manifest_envelope(
            stage="example_stage",
            assumptions=["only assumption"],
            inputs={},
            outputs={},
            code_reference="src/flytetest/tasks/example.py",
            tool_ref="docs/tool_refs/example.md",
        )

        self.assertEqual(manifest["code_reference"], "src/flytetest/tasks/example.py")
        self.assertEqual(manifest["tool_ref"], "docs/tool_refs/example.md")


class ManifestIoTests(TestCase):
    """Coverage for the shared manifest IO helpers and their task-module aliases.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_write_json_round_trips_paths_and_nested_containers(self) -> None:
        """Verify JSON conversion preserves nested structure while stringifying paths.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload_path = tmp_path / "bundle" / "run_manifest.json"
            copied_source = tmp_path / "source" / "artifact.txt"
            copied_source.parent.mkdir(parents=True, exist_ok=True)
            copied_source.write_text("payload\n")

            payload = {
                "stage": "shared_manifest_io",
                "inputs": {
                    "source_path": copied_source,
                    "nested": {"tuple_value": (Path("alpha"), Path("beta"))},
                },
                "outputs": {
                    "artifact_paths": [copied_source, Path("relative/output.txt")],
                },
            }

            returned_path = manifest.write_json(payload_path, payload)
            self.assertEqual(returned_path, payload_path)

            loaded = manifest.read_json(payload_path)
            self.assertEqual(loaded["inputs"]["source_path"], str(copied_source))
            self.assertEqual(loaded["inputs"]["nested"]["tuple_value"], ["alpha", "beta"])
            self.assertEqual(
                loaded["outputs"]["artifact_paths"],
                [str(copied_source), "relative/output.txt"],
            )

    def test_copy_helpers_stage_files_and_directories_deterministically(self) -> None:
        """Verify the copy helpers keep staged files and trees in predictable locations.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_file = tmp_path / "source" / "artifact.txt"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text("payload\n")

            copied_file = manifest.copy_file(source_file, tmp_path / "dest" / "artifact.txt")
            self.assertTrue(copied_file.exists())
            self.assertEqual(copied_file.read_text(), "payload\n")

            source_tree = tmp_path / "tree_source"
            (source_tree / "nested").mkdir(parents=True, exist_ok=True)
            (source_tree / "nested" / "child.txt").write_text("tree payload\n")

            destination_tree = tmp_path / "tree_dest"
            destination_tree.mkdir(parents=True, exist_ok=True)
            (destination_tree / "keep.txt").write_text("keep me\n")

            copied_tree = manifest.copy_tree(
                source_tree,
                destination_tree,
                dirs_exist_ok=True,
            )
            self.assertEqual(copied_tree, destination_tree)
            self.assertEqual((copied_tree / "nested" / "child.txt").read_text(), "tree payload\n")
            self.assertEqual((copied_tree / "keep.txt").read_text(), "keep me\n")

    def test_migrated_task_modules_reexport_shared_helpers(self) -> None:
        """Confirm the migrated task modules still expose the shared helper functions.
"""
        for module in (eggnog, functional, filtering, pasa):
            with self.subTest(module=module.__name__):
                self.assertIs(module._as_json_compatible, manifest.as_json_compatible)
                self.assertIs(module._read_json, manifest.read_json)
                self.assertIs(module._write_json, manifest.write_json)
                self.assertIs(module._copy_file, manifest.copy_file)
                self.assertIs(module._copy_tree, manifest.copy_tree)
