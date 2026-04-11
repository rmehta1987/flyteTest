"""Tests for the shared manifest-envelope helper.

    This module covers the small reusable manifest builder that standardizes the
    common `stage` / `assumptions` / `inputs` / `outputs` shape while leaving
    task-specific fields available for later enrichment.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest.manifest_envelope import build_manifest_envelope


class ManifestEnvelopeTests(TestCase):
    """Coverage for the common manifest envelope builder.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_build_manifest_envelope_keeps_common_fields_in_place(self) -> None:
        """Build the shared envelope without forcing task-specific schema changes.

    This test keeps the current contract explicit and guards the documented behavior against regression.
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

    This test keeps the current contract explicit and guards the documented behavior against regression.
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
