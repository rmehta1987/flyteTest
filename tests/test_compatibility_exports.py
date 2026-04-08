"""Compatibility export checks for the `flyte run` entry surface.

These tests keep `flyte_rnaseq_workflow.py` aligned with the package modules
while the `realtime` refactor changes internals behind that compatibility shim.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SRC_DIR = REPO_ROOT / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

import flyte_rnaseq_workflow as compatibility_exports
from flytetest.tasks import exonerate_align_chunk
from flytetest.workflows import (
    ab_initio_annotation_braker3,
    annotation_postprocess_agat,
    annotation_postprocess_agat_cleanup,
    annotation_postprocess_agat_conversion,
    annotation_functional_eggnog,
    protein_evidence_alignment,
    rnaseq_qc_quant,
    transcript_evidence_generation,
)


class CompatibilityExportTests(TestCase):
    """Freeze the current single-file compatibility surface for `flyte run`."""

    def test_entrypoint_exports_current_runnable_workflow_names(self) -> None:
        """Keep the public workflow names importable from the compatibility shim."""
        self.assertIn("ab_initio_annotation_braker3", compatibility_exports.__all__)
        self.assertIn("annotation_functional_eggnog", compatibility_exports.__all__)
        self.assertIn("annotation_postprocess_agat", compatibility_exports.__all__)
        self.assertIn("annotation_postprocess_agat_cleanup", compatibility_exports.__all__)
        self.assertIn("annotation_postprocess_agat_conversion", compatibility_exports.__all__)
        self.assertIn("protein_evidence_alignment", compatibility_exports.__all__)
        self.assertIn("rnaseq_qc_quant", compatibility_exports.__all__)
        self.assertIn("transcript_evidence_generation", compatibility_exports.__all__)

    def test_entrypoint_reexports_current_workflow_callables(self) -> None:
        """Expose the package workflow callables unchanged through the shim module."""
        self.assertIs(compatibility_exports.ab_initio_annotation_braker3, ab_initio_annotation_braker3)
        self.assertIs(compatibility_exports.annotation_functional_eggnog, annotation_functional_eggnog)
        self.assertIs(compatibility_exports.annotation_postprocess_agat, annotation_postprocess_agat)
        self.assertIs(
            compatibility_exports.annotation_postprocess_agat_cleanup,
            annotation_postprocess_agat_cleanup,
        )
        self.assertIs(
            compatibility_exports.annotation_postprocess_agat_conversion,
            annotation_postprocess_agat_conversion,
        )
        self.assertIs(compatibility_exports.protein_evidence_alignment, protein_evidence_alignment)
        self.assertIs(compatibility_exports.rnaseq_qc_quant, rnaseq_qc_quant)
        self.assertIs(compatibility_exports.transcript_evidence_generation, transcript_evidence_generation)

    def test_entrypoint_reexports_showcase_task_callable(self) -> None:
        """Keep the supported showcase task reachable from the compatibility entrypoint."""
        self.assertIn("exonerate_align_chunk", compatibility_exports.__all__)
        self.assertIs(compatibility_exports.exonerate_align_chunk, exonerate_align_chunk)
