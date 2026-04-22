"""Tests for the GATK4 variant calling task module (Milestone A, Step 03)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flyte.io import File

import flytetest.tasks.variant_calling as variant_calling
from flytetest.tasks.variant_calling import (
    MANIFEST_OUTPUT_KEYS,
    create_sequence_dictionary,
)


class RegistryEntryShapeTests(TestCase):
    """Guard the create_sequence_dictionary registry entry shape."""

    def test_create_sequence_dictionary_registry_entry_shape(self) -> None:
        """Entry exists, pipeline_family is variant_calling, interface names match MANIFEST_OUTPUT_KEYS."""
        from flytetest.registry import get_entry
        from flytetest.registry._variant_calling import VARIANT_CALLING_ENTRIES

        entry = get_entry("create_sequence_dictionary")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "task")
        self.assertIsNotNone(entry.compatibility)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 1)

        output_names = tuple(f.name for f in entry.outputs)
        for key in MANIFEST_OUTPUT_KEYS:
            self.assertIn(key, output_names)

        self.assertIn("variant_calling", VARIANT_CALLING_ENTRIES[0].tags)
        self.assertIn("gatk4", VARIANT_CALLING_ENTRIES[0].tags)


class CreateSequenceDictionaryInvocationTests(TestCase):
    """Verify that create_sequence_dictionary builds the correct GATK command."""

    def test_create_sequence_dictionary_invokes_run_tool(self) -> None:
        """run_tool is called with the correct gatk CreateSequenceDictionary command."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")

            captured: list[list[str]] = []

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
            ) -> None:
                captured.append(cmd)
                # Simulate GATK writing the .dict file to the -O path.
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("@HD\tVN:1.6\n")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = create_sequence_dictionary(
                    reference_fasta=File(path=str(ref_fasta)),
                    gatk_sif="data/images/gatk4.sif",
                )

        self.assertEqual(len(captured), 1)
        cmd = captured[0]
        self.assertEqual(cmd[0], "gatk")
        self.assertEqual(cmd[1], "CreateSequenceDictionary")
        self.assertIn("-R", cmd)
        self.assertIn("-O", cmd)

        r_idx = cmd.index("-R")
        self.assertTrue(cmd[r_idx + 1].endswith("genome.fa"))

        o_idx = cmd.index("-O")
        self.assertTrue(cmd[o_idx + 1].endswith("genome.dict"))

        # The returned File path points at the .dict file.
        self.assertTrue(result.path.endswith(".dict"))

    def test_create_sequence_dictionary_uses_default_sif_when_empty(self) -> None:
        """Empty gatk_sif falls back to data/images/gatk4.sif."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")

            captured_sif: list[str] = []

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
            ) -> None:
                captured_sif.append(sif)
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("@HD\tVN:1.6\n")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                create_sequence_dictionary(
                    reference_fasta=File(path=str(ref_fasta)),
                    gatk_sif="",
                )

        self.assertEqual(captured_sif[0], "data/images/gatk4.sif")


class CreateSequenceDictionaryManifestTests(TestCase):
    """Verify that create_sequence_dictionary emits a well-formed run_manifest.json."""

    def test_create_sequence_dictionary_emits_manifest(self) -> None:
        """run_manifest.json exists with correct stage and outputs.sequence_dict."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")

            emitted_out_dir: list[Path] = []

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
            ) -> None:
                # Locate the output dir from the -O argument and create the .dict.
                o_idx = cmd.index("-O")
                dict_path = Path(cmd[o_idx + 1])
                emitted_out_dir.append(dict_path.parent)
                dict_path.write_text("@HD\tVN:1.6\n")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                create_sequence_dictionary(
                    reference_fasta=File(path=str(ref_fasta)),
                    gatk_sif="data/images/gatk4.sif",
                )

        out_dir = emitted_out_dir[0]
        manifest_path = out_dir / "run_manifest.json"
        self.assertTrue(manifest_path.exists(), "run_manifest.json was not written")

        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["stage"], "create_sequence_dictionary")
        self.assertIn("sequence_dict", manifest["outputs"])
        self.assertTrue(manifest["outputs"]["sequence_dict"].endswith(".dict"))
