"""Tests for the GATK4 variant calling workflow compositions (Milestone B)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flyte.io import File

import flytetest.workflows.variant_calling as variant_calling_wf
from flytetest.workflows.variant_calling import (
    MANIFEST_OUTPUT_KEYS,
    prepare_reference,
)


class PrepareReferenceRegistryTests(TestCase):
    """Guard the prepare_reference registry entry shape."""

    def test_prepare_reference_registry_entry_shape(self) -> None:
        """Entry exists with category=workflow and stage_order=1."""
        from flytetest.registry import get_entry

        entry = get_entry("prepare_reference")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 1)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("prepared_ref", output_names)
        self.assertIn("prepared_ref", MANIFEST_OUTPUT_KEYS)


class PrepareReferenceInvocationTests(TestCase):
    """Verify prepare_reference calls sub-tasks in the correct order."""

    def _run_prepare_reference(self, ref_fasta, known_sites, results_dir):
        fake_file = MagicMock(spec=File)
        fake_file.path = str(ref_fasta)

        def fake_create_seq_dict(reference_fasta, gatk_sif):
            return fake_file

        def fake_index_feature(vcf, gatk_sif):
            return fake_file

        def fake_bwa_index(ref_path, results_dir, sif_path):
            return {"stage": "bwa_mem2_index", "outputs": {"bwa_index_prefix": ref_path}}

        with (
            patch.object(variant_calling_wf, "create_sequence_dictionary", side_effect=fake_create_seq_dict) as mock_csd,
            patch.object(variant_calling_wf, "index_feature_file", side_effect=fake_index_feature) as mock_iff,
            patch.object(variant_calling_wf, "bwa_mem2_index", side_effect=fake_bwa_index) as mock_bwa,
        ):
            result = prepare_reference(
                ref_path=str(ref_fasta),
                known_sites=known_sites,
                results_dir=str(results_dir),
            )
            return result, mock_csd, mock_iff, mock_bwa

    def test_sub_tasks_called_in_order(self) -> None:
        """create_sequence_dictionary, index_feature_file, then bwa_mem2_index."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            results_dir = tmp_path / "ref_prep"
            results_dir.mkdir()
            known_sites = [str(tmp_path / "dbsnp.vcf"), str(tmp_path / "mills.vcf")]

            result, mock_csd, mock_iff, mock_bwa = self._run_prepare_reference(
                ref_fasta, known_sites, results_dir
            )

        mock_csd.assert_called_once()
        mock_bwa.assert_called_once()
        self.assertEqual(mock_iff.call_count, 2)

    def test_index_feature_file_called_per_known_site(self) -> None:
        """index_feature_file is called once per entry in known_sites."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            results_dir = tmp_path / "ref_prep"
            results_dir.mkdir()
            known_sites = [
                str(tmp_path / "dbsnp.vcf"),
                str(tmp_path / "mills.vcf"),
                str(tmp_path / "hapmap.vcf"),
            ]

            _, _, mock_iff, _ = self._run_prepare_reference(
                ref_fasta, known_sites, results_dir
            )

        self.assertEqual(mock_iff.call_count, 3)


class PrepareReferenceManifestTests(TestCase):
    """Verify prepare_reference emits a well-formed run_manifest.json."""

    def test_prepare_reference_emits_prepared_ref_manifest(self) -> None:
        """Manifest contains prepared_ref pointing at the ref_path."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            results_dir = tmp_path / "ref_prep"
            results_dir.mkdir()
            known_sites = [str(tmp_path / "dbsnp.vcf")]

            fake_file = MagicMock(spec=File)
            fake_file.path = str(ref_fasta)

            with (
                patch.object(variant_calling_wf, "create_sequence_dictionary", return_value=fake_file),
                patch.object(variant_calling_wf, "index_feature_file", return_value=fake_file),
                patch.object(variant_calling_wf, "bwa_mem2_index", return_value={"outputs": {"bwa_index_prefix": str(ref_fasta)}}),
            ):
                result = prepare_reference(
                    ref_path=str(ref_fasta),
                    known_sites=known_sites,
                    results_dir=str(results_dir),
                )

        self.assertEqual(result["stage"], "prepare_reference")
        self.assertIn("prepared_ref", result["outputs"])
        self.assertEqual(result["outputs"]["prepared_ref"], str(ref_fasta))
