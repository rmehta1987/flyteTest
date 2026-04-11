"""Synthetic coverage for planner-adapter asset compatibility behavior.

    These checks focus on the Milestone 17 migration: generic asset keys should be
    preferred in new outputs while legacy alias loading remains replay-safe.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.planner_adapters import annotation_evidence_from_manifest


class PlannerAdapterTests(TestCase):
    """Compatibility checks for generic asset adoption in planner adapters.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_annotation_evidence_adapter_accepts_legacy_braker_bundle_alias(self) -> None:
        """Load legacy-only BRAKER bundle manifests without requiring a rewrite.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        manifest = {
            "workflow": "ab_initio_annotation_braker3",
            "repo_policy": ["Normalization preserves upstream BRAKER source labels."],
            "outputs": {
                "normalized_braker_gff3": "results/braker3/braker.normalized.gff3",
            },
            "assets": {
                "reference_genome": {
                    "fasta_path": "data/braker3/reference/genome.fa",
                    "organism_name": None,
                    "assembly_name": None,
                    "taxonomy_id": None,
                    "softmasked_fasta_path": None,
                    "annotation_gff3_path": None,
                    "notes": [],
                },
                "braker3_result_bundle": {
                    "provenance": {
                        "tool_name": "BRAKER3",
                        "tool_stage": "ab initio annotation",
                        "legacy_asset_name": "Braker3ResultBundle",
                        "source_manifest_key": "braker3_result_bundle",
                        "notes": [],
                    }
                },
            },
        }

        adapted = annotation_evidence_from_manifest(manifest)

        self.assertEqual(adapted.reference_genome.fasta_path, Path("data/braker3/reference/genome.fa"))
        self.assertEqual(adapted.ab_initio_predictions_gff3_path, Path("results/braker3/braker.normalized.gff3"))
        self.assertIn("BRAKER3", adapted.notes[0])
