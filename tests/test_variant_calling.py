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
    apply_bqsr,
    base_recalibrator,
    combine_gvcfs,
    create_sequence_dictionary,
    haplotype_caller,
    index_feature_file,
    joint_call_gvcfs,
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
        self.assertIn("sequence_dict", output_names)
        self.assertIn("sequence_dict", MANIFEST_OUTPUT_KEYS)

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


# ---------------------------------------------------------------------------
# index_feature_file
# ---------------------------------------------------------------------------

class IndexFeatureFileRegistryTests(TestCase):
    """Guard the index_feature_file registry entry shape."""

    def test_index_feature_file_registry_entry_shape(self) -> None:
        """Entry exists with correct pipeline_family and stage_order."""
        from flytetest.registry import get_entry

        entry = get_entry("index_feature_file")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "task")
        self.assertIsNotNone(entry.compatibility)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 2)
        self.assertIn("KnownSites", entry.compatibility.accepted_planner_types)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("feature_index", output_names)
        self.assertIn("feature_index", MANIFEST_OUTPUT_KEYS)


class IndexFeatureFileInvocationTests(TestCase):
    """Verify index_feature_file builds the correct GATK command and index paths."""

    def _run_with_fake(self, vcf_name: str) -> tuple[list[str], File]:
        """Helper: create a temp vcf, patch run_tool, return (cmd, result File)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf_file = tmp_path / vcf_name
            vcf_file.write_text("placeholder\n")

            captured: list[list[str]] = []

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
            ) -> None:
                captured.append(cmd)
                i_idx = cmd.index("-I")
                input_path = Path(cmd[i_idx + 1])
                if input_path.suffix == ".gz":
                    input_path.with_suffix(input_path.suffix + ".tbi").write_text("index\n")
                else:
                    input_path.with_suffix(input_path.suffix + ".idx").write_text("index\n")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = index_feature_file(
                    vcf=File(path=str(vcf_file)),
                    gatk_sif="data/images/gatk4.sif",
                )

        return captured[0], result

    def test_index_feature_file_uses_tbi_for_gz(self) -> None:
        """sites.vcf.gz input yields an output path ending in .vcf.gz.tbi."""
        cmd, result = self._run_with_fake("sites.vcf.gz")
        self.assertEqual(cmd[0], "gatk")
        self.assertEqual(cmd[1], "IndexFeatureFile")
        self.assertIn("-I", cmd)
        self.assertTrue(result.path.endswith(".vcf.gz.tbi"))

    def test_index_feature_file_uses_idx_for_plain_vcf(self) -> None:
        """sites.vcf input yields an output path ending in .vcf.idx."""
        cmd, result = self._run_with_fake("sites.vcf")
        self.assertEqual(cmd[0], "gatk")
        self.assertEqual(cmd[1], "IndexFeatureFile")
        self.assertTrue(result.path.endswith(".vcf.idx"))


class IndexFeatureFileManifestTests(TestCase):
    """Verify index_feature_file emits a well-formed run_manifest.json."""

    def test_index_feature_file_emits_manifest(self) -> None:
        """run_manifest.json has correct stage and outputs.feature_index."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf_file = tmp_path / "sites.vcf"
            vcf_file.write_text("placeholder\n")

            emitted_out_dir: list[Path] = []

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
            ) -> None:
                i_idx = cmd.index("-I")
                input_path = Path(cmd[i_idx + 1])
                input_path.with_suffix(input_path.suffix + ".idx").write_text("index\n")
                for p in bind_paths:
                    if "gatk_index_" in str(p):
                        emitted_out_dir.append(p)

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                index_feature_file(
                    vcf=File(path=str(vcf_file)),
                    gatk_sif="data/images/gatk4.sif",
                )

        out_dir = emitted_out_dir[0]
        manifest_path = out_dir / "run_manifest.json"
        self.assertTrue(manifest_path.exists(), "run_manifest.json was not written")

        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["stage"], "index_feature_file")
        self.assertIn("feature_index", manifest["outputs"])
        self.assertTrue(manifest["outputs"]["feature_index"].endswith(".vcf.idx"))


class BaseRecalibratorRegistryTests(TestCase):
    def test_base_recalibrator_registry_entry_shape(self):
        from flytetest.registry._variant_calling import VARIANT_CALLING_ENTRIES

        entry = next(e for e in VARIANT_CALLING_ENTRIES if e.name == "base_recalibrator")
        self.assertEqual(entry.category, "task")
        input_names = [f.name for f in entry.inputs]
        self.assertIn("reference_fasta", input_names)
        self.assertIn("aligned_bam", input_names)
        self.assertIn("known_sites", input_names)
        self.assertIn("sample_id", input_names)
        output_names = [f.name for f in entry.outputs]
        self.assertIn("bqsr_report", output_names)
        self.assertEqual(entry.compatibility.pipeline_stage_order, 3)
        self.assertIn("ReferenceGenome", entry.compatibility.accepted_planner_types)
        self.assertIn("AlignmentSet", entry.compatibility.accepted_planner_types)
        self.assertIn("KnownSites", entry.compatibility.accepted_planner_types)


class BaseRecalibratorInvocationTests(TestCase):
    def test_base_recalibrator_rejects_empty_known_sites(self):
        stub_ref = File(path="/data/ref.fa")
        stub_bam = File(path="/data/sample.bam")
        with self.assertRaises(ValueError) as ctx:
            base_recalibrator(
                reference_fasta=stub_ref,
                aligned_bam=stub_bam,
                known_sites=[],
                sample_id="sample1",
            )
        self.assertIn("known_sites list cannot be empty", str(ctx.exception))

    def test_base_recalibrator_cmd_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            bam_file = tmp_path / "sample.bam"
            site1 = tmp_path / "dbsnp.vcf"
            site2 = tmp_path / "mills.vcf"
            for p in (ref_fa, bam_file, site1, site2):
                p.touch()

            captured_cmd = []
            emitted_out_dir = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                out_path = Path(cmd[out_idx + 1])
                emitted_out_dir.append(out_path.parent)
                out_path.touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = base_recalibrator(
                    reference_fasta=File(path=str(ref_fa)),
                    aligned_bam=File(path=str(bam_file)),
                    known_sites=[
                        File(path=str(site1)),
                        File(path=str(site2)),
                    ],
                    sample_id="sample1",
                )

            self.assertEqual(captured_cmd[0], "gatk")
            self.assertEqual(captured_cmd[1], "BaseRecalibrator")
            self.assertIn("-R", captured_cmd)
            self.assertIn("-I", captured_cmd)
            self.assertIn("-O", captured_cmd)
            # --known-sites should appear once per site
            known_sites_flags = [i for i, v in enumerate(captured_cmd) if v == "--known-sites"]
            self.assertEqual(len(known_sites_flags), 2)
            self.assertEqual(captured_cmd[known_sites_flags[0] + 1], str(site1))
            self.assertEqual(captured_cmd[known_sites_flags[1] + 1], str(site2))
            self.assertTrue(result.path.endswith(".table"))


class BaseRecalibratorManifestTests(TestCase):
    def test_base_recalibrator_emits_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            bam_file = tmp_path / "sample.bam"
            site1 = tmp_path / "dbsnp.vcf"
            for p in (ref_fa, bam_file, site1):
                p.touch()

            emitted_out_dir = []

            def fake_run_tool(cmd, sif, bind_paths):
                out_idx = cmd.index("-O")
                out_path = Path(cmd[out_idx + 1])
                emitted_out_dir.append(out_path.parent)
                out_path.touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                base_recalibrator(
                    reference_fasta=File(path=str(ref_fa)),
                    aligned_bam=File(path=str(bam_file)),
                    known_sites=[File(path=str(site1))],
                    sample_id="sample1",
                )

            out_dir = emitted_out_dir[0]
            manifest_path = out_dir / "run_manifest.json"
            self.assertTrue(manifest_path.exists(), "run_manifest.json was not written")

            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["stage"], "base_recalibrator")
            self.assertIn("bqsr_report", manifest["outputs"])
            self.assertTrue(manifest["outputs"]["bqsr_report"].endswith(".table"))


class ApplyBqsrRegistryTests(TestCase):
    def test_apply_bqsr_registry_entry_shape(self):
        from flytetest.registry._variant_calling import VARIANT_CALLING_ENTRIES

        entry = next(e for e in VARIANT_CALLING_ENTRIES if e.name == "apply_bqsr")
        self.assertEqual(entry.category, "task")
        input_names = [f.name for f in entry.inputs]
        self.assertIn("reference_fasta", input_names)
        self.assertIn("aligned_bam", input_names)
        self.assertIn("bqsr_report", input_names)
        self.assertIn("sample_id", input_names)
        output_names = [f.name for f in entry.outputs]
        self.assertIn("recalibrated_bam", output_names)
        self.assertEqual(entry.compatibility.pipeline_stage_order, 4)
        self.assertIn("ReferenceGenome", entry.compatibility.accepted_planner_types)
        self.assertIn("AlignmentSet", entry.compatibility.accepted_planner_types)
        self.assertIn("AlignmentSet", entry.compatibility.produced_planner_types)


class ApplyBqsrInvocationTests(TestCase):
    def test_apply_bqsr_cmd_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            bam_file = tmp_path / "sample.bam"
            recal_table = tmp_path / "sample_bqsr.table"
            for p in (ref_fa, bam_file, recal_table):
                p.touch()

            captured_cmd = []
            emitted_out_dir = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                out_path = Path(cmd[out_idx + 1])
                emitted_out_dir.append(out_path.parent)
                out_path.touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = apply_bqsr(
                    reference_fasta=File(path=str(ref_fa)),
                    aligned_bam=File(path=str(bam_file)),
                    bqsr_report=File(path=str(recal_table)),
                    sample_id="sample1",
                )

            self.assertEqual(captured_cmd[0], "gatk")
            self.assertEqual(captured_cmd[1], "ApplyBQSR")
            self.assertIn("--bqsr-recal-file", captured_cmd)
            recal_idx = captured_cmd.index("--bqsr-recal-file")
            o_idx = captured_cmd.index("-O")
            self.assertLess(recal_idx, o_idx)
            self.assertIn("sample1_recalibrated.bam", result.path)


class ApplyBqsrManifestTests(TestCase):
    def test_apply_bqsr_emits_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            bam_file = tmp_path / "sample.bam"
            recal_table = tmp_path / "sample_bqsr.table"
            for p in (ref_fa, bam_file, recal_table):
                p.touch()

            emitted_out_dir = []

            def fake_run_tool(cmd, sif, bind_paths):
                out_idx = cmd.index("-O")
                out_path = Path(cmd[out_idx + 1])
                emitted_out_dir.append(out_path.parent)
                out_path.touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                apply_bqsr(
                    reference_fasta=File(path=str(ref_fa)),
                    aligned_bam=File(path=str(bam_file)),
                    bqsr_report=File(path=str(recal_table)),
                    sample_id="sample1",
                )

            out_dir = emitted_out_dir[0]
            manifest_path = out_dir / "run_manifest.json"
            self.assertTrue(manifest_path.exists(), "run_manifest.json was not written")

            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["stage"], "apply_bqsr")
            self.assertIn("recalibrated_bam", manifest["outputs"])
            self.assertIn("recalibrated_bam_index", manifest["outputs"])
            self.assertTrue(manifest["outputs"]["recalibrated_bam"].endswith(".bam"))


class HaplotypeCallerRegistryTests(TestCase):
    def test_haplotype_caller_registry_entry_shape(self):
        from flytetest.registry._variant_calling import VARIANT_CALLING_ENTRIES

        entry = next(e for e in VARIANT_CALLING_ENTRIES if e.name == "haplotype_caller")
        self.assertEqual(entry.category, "task")
        input_names = [f.name for f in entry.inputs]
        self.assertIn("reference_fasta", input_names)
        self.assertIn("aligned_bam", input_names)
        self.assertIn("sample_id", input_names)
        output_names = [f.name for f in entry.outputs]
        self.assertIn("gvcf", output_names)
        self.assertEqual(entry.compatibility.pipeline_stage_order, 5)
        self.assertIn("ReferenceGenome", entry.compatibility.accepted_planner_types)
        self.assertIn("AlignmentSet", entry.compatibility.accepted_planner_types)
        self.assertIn("VariantCallSet", entry.compatibility.produced_planner_types)


class HaplotypeCallerInvocationTests(TestCase):
    def test_haplotype_caller_cmd_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            bam_file = tmp_path / "sample.bam"
            for p in (ref_fa, bam_file):
                p.touch()

            captured_cmd = []
            emitted_out_dir = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                out_path = Path(cmd[out_idx + 1])
                emitted_out_dir.append(out_path.parent)
                out_path.touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = haplotype_caller(
                    reference_fasta=File(path=str(ref_fa)),
                    aligned_bam=File(path=str(bam_file)),
                    sample_id="sample1",
                )

            self.assertEqual(captured_cmd[0], "gatk")
            self.assertEqual(captured_cmd[1], "HaplotypeCaller")
            self.assertIn("--emit-ref-confidence", captured_cmd)
            erc_idx = captured_cmd.index("--emit-ref-confidence")
            self.assertEqual(captured_cmd[erc_idx + 1], "GVCF")
            self.assertTrue(result.path.endswith(".g.vcf"))
            self.assertIn("sample1", result.path)


class HaplotypeCallerManifestTests(TestCase):
    def test_haplotype_caller_emits_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            bam_file = tmp_path / "sample.bam"
            for p in (ref_fa, bam_file):
                p.touch()

            emitted_out_dir = []

            def fake_run_tool(cmd, sif, bind_paths):
                out_idx = cmd.index("-O")
                out_path = Path(cmd[out_idx + 1])
                emitted_out_dir.append(out_path.parent)
                out_path.touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                haplotype_caller(
                    reference_fasta=File(path=str(ref_fa)),
                    aligned_bam=File(path=str(bam_file)),
                    sample_id="sample1",
                )

            out_dir = emitted_out_dir[0]
            manifest_path = out_dir / "run_manifest.json"
            self.assertTrue(manifest_path.exists(), "run_manifest.json was not written")

            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["stage"], "haplotype_caller")
            self.assertIn("gvcf", manifest["outputs"])
            self.assertTrue(manifest["outputs"]["gvcf"].endswith(".g.vcf"))


class CombineGvcfsRegistryTests(TestCase):
    def test_combine_gvcfs_registry_entry_shape(self):
        from flytetest.registry._variant_calling import VARIANT_CALLING_ENTRIES

        entry = next(e for e in VARIANT_CALLING_ENTRIES if e.name == "combine_gvcfs")
        self.assertEqual(entry.category, "task")
        input_names = [f.name for f in entry.inputs]
        self.assertIn("reference_fasta", input_names)
        self.assertIn("gvcfs", input_names)
        self.assertIn("cohort_id", input_names)
        output_names = [f.name for f in entry.outputs]
        self.assertIn("combined_gvcf", output_names)
        self.assertEqual(entry.compatibility.pipeline_stage_order, 6)
        self.assertIn("ReferenceGenome", entry.compatibility.accepted_planner_types)
        self.assertIn("VariantCallSet", entry.compatibility.accepted_planner_types)
        self.assertIn("VariantCallSet", entry.compatibility.produced_planner_types)


class CombineGvcfsInvocationTests(TestCase):
    def test_combine_gvcfs_rejects_empty_list(self):
        stub_ref = File(path="/data/ref.fa")
        with self.assertRaises(ValueError) as ctx:
            combine_gvcfs(reference_fasta=stub_ref, gvcfs=[])
        self.assertIn("gvcfs list cannot be empty", str(ctx.exception))

    def test_combine_gvcfs_cmd_emits_V_per_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            gvcf1 = tmp_path / "sample1.g.vcf"
            gvcf2 = tmp_path / "sample2.g.vcf"
            gvcf3 = tmp_path / "sample3.g.vcf"
            for p in (ref_fa, gvcf1, gvcf2, gvcf3):
                p.touch()

            captured_cmd = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = combine_gvcfs(
                    reference_fasta=File(path=str(ref_fa)),
                    gvcfs=[File(path=str(gvcf1)), File(path=str(gvcf2)), File(path=str(gvcf3))],
                    cohort_id="trio",
                )

        self.assertEqual(captured_cmd[0], "gatk")
        self.assertEqual(captured_cmd[1], "CombineGVCFs")
        v_indices = [i for i, v in enumerate(captured_cmd) if v == "-V"]
        self.assertEqual(len(v_indices), 3)
        self.assertEqual(captured_cmd[v_indices[0] + 1], str(gvcf1))
        self.assertEqual(captured_cmd[v_indices[1] + 1], str(gvcf2))
        self.assertEqual(captured_cmd[v_indices[2] + 1], str(gvcf3))
        self.assertIn("trio_combined.g.vcf", result.path)


class CombineGvcfsManifestTests(TestCase):
    def test_combine_gvcfs_emits_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            gvcf1 = tmp_path / "sample1.g.vcf"
            gvcf2 = tmp_path / "sample2.g.vcf"
            for p in (ref_fa, gvcf1, gvcf2):
                p.touch()

            emitted_out_dir = []

            def fake_run_tool(cmd, sif, bind_paths):
                out_idx = cmd.index("-O")
                out_path = Path(cmd[out_idx + 1])
                emitted_out_dir.append(out_path.parent)
                out_path.touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                combine_gvcfs(
                    reference_fasta=File(path=str(ref_fa)),
                    gvcfs=[File(path=str(gvcf1)), File(path=str(gvcf2))],
                    cohort_id="cohort1",
                )

        out_dir = emitted_out_dir[0]
        manifest_path = out_dir / "run_manifest.json"
        self.assertTrue(manifest_path.exists(), "run_manifest.json was not written")

        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["stage"], "combine_gvcfs")
        self.assertIn("combined_gvcf", manifest["outputs"])
        self.assertTrue(manifest["outputs"]["combined_gvcf"].endswith("_combined.g.vcf"))
        self.assertIsInstance(manifest["inputs"]["gvcfs"], list)
        self.assertEqual(len(manifest["inputs"]["gvcfs"]), 2)


class JointCallGvcfsRegistryTests(TestCase):
    def test_joint_call_gvcfs_registry_entry_shape(self):
        from flytetest.registry._variant_calling import VARIANT_CALLING_ENTRIES

        entry = next(e for e in VARIANT_CALLING_ENTRIES if e.name == "joint_call_gvcfs")
        self.assertEqual(entry.category, "task")
        input_names = [f.name for f in entry.inputs]
        self.assertIn("reference_fasta", input_names)
        self.assertIn("gvcfs", input_names)
        self.assertIn("sample_ids", input_names)
        self.assertIn("intervals", input_names)
        output_names = [f.name for f in entry.outputs]
        self.assertIn("joint_vcf", output_names)
        self.assertEqual(entry.compatibility.pipeline_stage_order, 7)
        self.assertIn("ReferenceGenome", entry.compatibility.accepted_planner_types)
        self.assertIn("VariantCallSet", entry.compatibility.accepted_planner_types)
        self.assertIn("VariantCallSet", entry.compatibility.produced_planner_types)


class JointCallGvcfsInvocationTests(TestCase):
    def test_joint_call_gvcfs_rejects_empty_gvcfs(self):
        stub_ref = File(path="/data/ref.fa")
        with self.assertRaises(ValueError) as ctx:
            joint_call_gvcfs(
                reference_fasta=stub_ref,
                gvcfs=[],
                sample_ids=[],
                intervals=["chr20"],
            )
        self.assertIn("gvcfs list cannot be empty", str(ctx.exception))

    def test_joint_call_gvcfs_rejects_empty_intervals(self):
        stub_ref = File(path="/data/ref.fa")
        stub_gvcf = File(path="/data/sample.g.vcf")
        with self.assertRaises(ValueError) as ctx:
            joint_call_gvcfs(
                reference_fasta=stub_ref,
                gvcfs=[stub_gvcf],
                sample_ids=["s1"],
                intervals=[],
            )
        self.assertIn("intervals list cannot be empty", str(ctx.exception))

    def test_joint_call_gvcfs_rejects_mismatched_sample_ids_length(self):
        stub_ref = File(path="/data/ref.fa")
        stub_gvcf = File(path="/data/sample.g.vcf")
        with self.assertRaises(ValueError) as ctx:
            joint_call_gvcfs(
                reference_fasta=stub_ref,
                gvcfs=[stub_gvcf],
                sample_ids=["s1", "s2"],
                intervals=["chr20"],
            )
        self.assertIn("sample_ids length", str(ctx.exception))
        self.assertIn("must match gvcfs", str(ctx.exception))

    def test_joint_call_gvcfs_cmd_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            gvcf1 = tmp_path / "s1.g.vcf"
            gvcf2 = tmp_path / "s2.g.vcf"
            for p in (ref_fa, gvcf1, gvcf2):
                p.touch()

            calls: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                calls.append(list(cmd))
                # create workspace dir for require_path after GenomicsDBImport
                if cmd[1] == "GenomicsDBImport":
                    ws_idx = cmd.index("--genomicsdb-workspace-path")
                    Path(cmd[ws_idx + 1]).mkdir(parents=True, exist_ok=True)
                elif cmd[1] == "GenotypeGVCFs":
                    o_idx = cmd.index("-O")
                    Path(cmd[o_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = joint_call_gvcfs(
                    reference_fasta=File(path=str(ref_fa)),
                    gvcfs=[File(path=str(gvcf1)), File(path=str(gvcf2))],
                    sample_ids=["s1", "s2"],
                    intervals=["chr20", "chr21"],
                    cohort_id="cohort",
                )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], "GenomicsDBImport")
        self.assertEqual(calls[1][1], "GenotypeGVCFs")
        # GenomicsDBImport gets -L per interval
        l_indices = [i for i, v in enumerate(calls[0]) if v == "-L"]
        self.assertEqual(len(l_indices), 2)
        self.assertEqual(calls[0][l_indices[0] + 1], "chr20")
        self.assertEqual(calls[0][l_indices[1] + 1], "chr21")
        # GenotypeGVCFs uses gendb:// URI
        v_idx = calls[1].index("-V")
        self.assertTrue(calls[1][v_idx + 1].startswith("gendb://"))
        self.assertTrue(result.path.endswith("_genotyped.vcf"))

    def test_joint_call_gvcfs_sample_map_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            gvcf1 = tmp_path / "s1.g.vcf"
            gvcf2 = tmp_path / "s2.g.vcf"
            for p in (ref_fa, gvcf1, gvcf2):
                p.touch()

            captured_map: list[str] = []

            def fake_run_tool(cmd, sif, bind_paths):
                if cmd[1] == "GenomicsDBImport":
                    map_idx = cmd.index("--sample-name-map")
                    captured_map.append(Path(cmd[map_idx + 1]).read_text())
                    ws_idx = cmd.index("--genomicsdb-workspace-path")
                    Path(cmd[ws_idx + 1]).mkdir(parents=True, exist_ok=True)
                elif cmd[1] == "GenotypeGVCFs":
                    o_idx = cmd.index("-O")
                    Path(cmd[o_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                joint_call_gvcfs(
                    reference_fasta=File(path=str(ref_fa)),
                    gvcfs=[File(path=str(gvcf1)), File(path=str(gvcf2))],
                    sample_ids=["sampleA", "sampleB"],
                    intervals=["chr20"],
                    cohort_id="cohort",
                )

        lines = [ln for ln in captured_map[0].splitlines() if ln]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("sampleA\t"))
        self.assertIn(str(gvcf1), lines[0])
        self.assertTrue(lines[1].startswith("sampleB\t"))
        self.assertIn(str(gvcf2), lines[1])


class JointCallGvcfsManifestTests(TestCase):
    def test_joint_call_gvcfs_emits_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            gvcf1 = tmp_path / "s1.g.vcf"
            gvcf2 = tmp_path / "s2.g.vcf"
            for p in (ref_fa, gvcf1, gvcf2):
                p.touch()

            emitted_out_dir: list[Path] = []

            def fake_run_tool(cmd, sif, bind_paths):
                if cmd[1] == "GenomicsDBImport":
                    ws_idx = cmd.index("--genomicsdb-workspace-path")
                    Path(cmd[ws_idx + 1]).mkdir(parents=True, exist_ok=True)
                elif cmd[1] == "GenotypeGVCFs":
                    o_idx = cmd.index("-O")
                    out_path = Path(cmd[o_idx + 1])
                    emitted_out_dir.append(out_path.parent)
                    out_path.touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                joint_call_gvcfs(
                    reference_fasta=File(path=str(ref_fa)),
                    gvcfs=[File(path=str(gvcf1)), File(path=str(gvcf2))],
                    sample_ids=["s1", "s2"],
                    intervals=["chr20"],
                    cohort_id="trio",
                )

        out_dir = emitted_out_dir[0]
        manifest_path = out_dir / "run_manifest.json"
        self.assertTrue(manifest_path.exists(), "run_manifest.json was not written")

        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["stage"], "joint_call_gvcfs")
        self.assertIn("joint_vcf", manifest["outputs"])
        self.assertTrue(manifest["outputs"]["joint_vcf"].endswith("_genotyped.vcf"))
        self.assertIsInstance(manifest["inputs"]["gvcfs"], list)
        self.assertEqual(len(manifest["inputs"]["gvcfs"]), 2)
        self.assertEqual(manifest["inputs"]["intervals"], ["chr20"])
        self.assertEqual(manifest["inputs"]["sample_ids"], ["s1", "s2"])


class BwaMem2IndexRegistryTests(TestCase):
    """Guard the bwa_mem2_index registry entry shape."""

    def test_bwa_mem2_index_registry_entry_shape(self) -> None:
        """Entry exists at stage_order 8 in the variant_calling family."""
        from flytetest.registry import get_entry

        entry = get_entry("bwa_mem2_index")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "task")
        self.assertIsNotNone(entry.compatibility)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 8)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("bwa_index_prefix", output_names)
        self.assertIn("bwa_index_prefix", MANIFEST_OUTPUT_KEYS)


class BwaMem2IndexInvocationTests(TestCase):
    """Verify that bwa_mem2_index builds the correct bwa-mem2 command."""

    def test_bwa_mem2_index_command_shape(self) -> None:
        """run_tool is called with bwa-mem2 index -p <prefix> <ref_path>."""
        from flytetest.tasks.variant_calling import bwa_mem2_index

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            results_dir = tmp_path / "index_out"
            results_dir.mkdir()

            captured: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured.append(cmd)
                prefix = cmd[cmd.index("-p") + 1]
                for suffix in (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"):
                    Path(prefix + suffix).write_text("x")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                bwa_mem2_index(
                    ref_path=str(ref_fasta),
                    results_dir=str(results_dir),
                    sif_path="data/images/gatk4.sif",
                )

        self.assertEqual(len(captured), 1)
        cmd = captured[0]
        self.assertIn("bwa-mem2", cmd)
        self.assertIn("index", cmd)
        self.assertIn("-p", cmd)
        self.assertIn(str(ref_fasta), cmd)

    def test_bwa_mem2_index_raises_on_missing_index_files(self) -> None:
        """FileNotFoundError is raised if any of the five index files are absent."""
        from flytetest.tasks.variant_calling import bwa_mem2_index

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            results_dir = tmp_path / "index_out"
            results_dir.mkdir()

            def fake_run_tool_no_files(cmd, sif, bind_paths):
                pass  # produce no index files

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool_no_files):
                with self.assertRaises(FileNotFoundError):
                    bwa_mem2_index(
                        ref_path=str(ref_fasta),
                        results_dir=str(results_dir),
                    )


class BwaMem2IndexManifestTests(TestCase):
    """Verify that bwa_mem2_index emits a well-formed run_manifest.json."""

    def test_bwa_mem2_index_emits_manifest(self) -> None:
        """run_manifest.json contains bwa_index_prefix in outputs."""
        from flytetest.tasks.variant_calling import bwa_mem2_index

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            results_dir = tmp_path / "index_out"
            results_dir.mkdir()

            def fake_run_tool(cmd, sif, bind_paths):
                prefix = cmd[cmd.index("-p") + 1]
                for suffix in (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"):
                    Path(prefix + suffix).write_text("x")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = bwa_mem2_index(
                    ref_path=str(ref_fasta),
                    results_dir=str(results_dir),
                )

        self.assertEqual(result["stage"], "bwa_mem2_index")
        self.assertIn("bwa_index_prefix", result["outputs"])
        self.assertTrue(result["outputs"]["bwa_index_prefix"].endswith("genome"))
