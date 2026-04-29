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
    apply_vqsr,
    base_recalibrator,
    bcftools_stats,
    bwa_mem2_index,
    bwa_mem2_mem,
    calculate_genotype_posteriors,
    collect_wgs_metrics,
    combine_gvcfs,
    count_vcf_records,
    create_sequence_dictionary,
    gather_vcfs,
    haplotype_caller,
    index_feature_file,
    joint_call_gvcfs,
    mark_duplicates,
    merge_bam_alignment,
    multiqc_summarize,
    my_custom_filter,
    snpeff_annotate,
    sort_sam,
    variant_filtration,
    variant_recalibrator,
    _resolve_vqsr_annotations,
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

    def test_create_sequence_dictionary_empty_sif_passes_through(self) -> None:
        """Empty gatk_sif passes "" to run_tool, enabling native/module execution."""
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

        self.assertEqual(captured_sif[0], "")


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
        manifest_path = out_dir / "run_manifest_create_sequence_dictionary.json"
        self.assertTrue(manifest_path.exists(), "run_manifest_create_sequence_dictionary.json was not written")

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
        manifest_path = out_dir / "run_manifest_index_feature_file.json"
        self.assertTrue(manifest_path.exists(), "run_manifest_index_feature_file.json was not written")

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
            manifest_path = out_dir / "run_manifest_base_recalibrator.json"
            self.assertTrue(manifest_path.exists(), "run_manifest_base_recalibrator.json was not written")

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
            manifest_path = out_dir / "run_manifest_apply_bqsr.json"
            self.assertTrue(manifest_path.exists(), "run_manifest_apply_bqsr.json was not written")

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

    def test_haplotype_caller_with_intervals_adds_L_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            bam_file = tmp_path / "sample.bam"
            for p in (ref_fa, bam_file):
                p.touch()

            captured_cmd = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                haplotype_caller(
                    reference_fasta=File(path=str(ref_fa)),
                    aligned_bam=File(path=str(bam_file)),
                    sample_id="sample1",
                    intervals=["chr1", "chr2:1-1000000"],
                )

            l_indices = [i for i, v in enumerate(captured_cmd) if v == "-L"]
            self.assertEqual(len(l_indices), 2)
            self.assertEqual(captured_cmd[l_indices[0] + 1], "chr1")
            self.assertEqual(captured_cmd[l_indices[1] + 1], "chr2:1-1000000")

    def test_haplotype_caller_no_intervals_omits_L(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fa = tmp_path / "ref.fa"
            bam_file = tmp_path / "sample.bam"
            for p in (ref_fa, bam_file):
                p.touch()

            captured_cmd = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                haplotype_caller(
                    reference_fasta=File(path=str(ref_fa)),
                    aligned_bam=File(path=str(bam_file)),
                    sample_id="sample1",
                )

            self.assertNotIn("-L", captured_cmd)


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
            manifest_path = out_dir / "run_manifest_haplotype_caller.json"
            self.assertTrue(manifest_path.exists(), "run_manifest_haplotype_caller.json was not written")

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
        manifest_path = out_dir / "run_manifest_combine_gvcfs.json"
        self.assertTrue(manifest_path.exists(), "run_manifest_combine_gvcfs.json was not written")

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
        manifest_path = out_dir / "run_manifest_joint_call_gvcfs.json"
        self.assertTrue(manifest_path.exists(), "run_manifest_joint_call_gvcfs.json was not written")

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
        """Entry exists at stage_order 8 with showcase_module set."""
        from flytetest.registry import get_entry

        entry = get_entry("bwa_mem2_index")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "task")
        self.assertIsNotNone(entry.compatibility)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 8)
        self.assertEqual(entry.showcase_module, "flytetest.tasks.variant_calling")

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("bwa_index_prefix", output_names)
        self.assertIn("bwa_index_prefix", MANIFEST_OUTPUT_KEYS)


class BwaMem2IndexInvocationTests(TestCase):
    """Verify that bwa_mem2_index builds the correct bwa-mem2 command."""

    def test_bwa_mem2_index_command_shape(self) -> None:
        """run_tool is called with bwa-mem2 index -p <prefix> <ref_path>."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")

            captured: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured.append(cmd)
                prefix = cmd[cmd.index("-p") + 1]
                for suffix in (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"):
                    Path(prefix + suffix).write_text("x")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = bwa_mem2_index(
                    reference_fasta=File(path=str(ref_fasta)),
                    bwa_sif="data/images/bwa_mem2.sif",
                )

        self.assertEqual(len(captured), 1)
        cmd = captured[0]
        self.assertIn("bwa-mem2", cmd)
        self.assertIn("index", cmd)
        self.assertIn("-p", cmd)
        self.assertIn(str(ref_fasta), cmd)
        # Returns a Dir
        from flyte.io import Dir
        self.assertIsInstance(result, Dir)

    def test_bwa_mem2_index_raises_on_missing_index_files(self) -> None:
        """FileNotFoundError is raised if any of the five index files are absent."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")

            def fake_run_tool_no_files(cmd, sif, bind_paths):
                pass

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool_no_files):
                with self.assertRaises(FileNotFoundError):
                    bwa_mem2_index(
                        reference_fasta=File(path=str(ref_fasta)),
                    )


class BwaMem2IndexManifestTests(TestCase):
    """Verify that bwa_mem2_index emits a well-formed run_manifest_bwa_mem2_index.json."""

    def test_bwa_mem2_index_emits_manifest(self) -> None:
        """Manifest contains bwa_index_prefix in outputs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")

            captured_manifests: list = []

            def fake_run_tool(cmd, sif, bind_paths):
                prefix = cmd[cmd.index("-p") + 1]
                for suffix in (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"):
                    Path(prefix + suffix).write_text("x")

            with (
                patch.object(variant_calling, "run_tool", side_effect=fake_run_tool),
                patch.object(variant_calling, "_write_json",
                             side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                result = bwa_mem2_index(
                    reference_fasta=File(path=str(ref_fasta)),
                )

        self.assertEqual(captured_manifests[0]["stage"], "bwa_mem2_index")
        self.assertIn("bwa_index_prefix", captured_manifests[0]["outputs"])
        self.assertTrue(captured_manifests[0]["outputs"]["bwa_index_prefix"].endswith("genome"))


class BwaMem2MemRegistryTests(TestCase):
    """Guard the bwa_mem2_mem registry entry shape."""

    def test_bwa_mem2_mem_registry_entry_shape(self) -> None:
        """Entry exists at stage_order 9 with library_id and platform inputs."""
        from flytetest.registry import get_entry

        entry = get_entry("bwa_mem2_mem")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "task")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 9)
        self.assertIn("ReadPair", entry.compatibility.accepted_planner_types)
        self.assertEqual(entry.showcase_module, "flytetest.tasks.variant_calling")

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("aligned_bam", output_names)
        self.assertIn("aligned_bam", MANIFEST_OUTPUT_KEYS)

        input_names = [f.name for f in entry.inputs]
        self.assertIn("library_id", input_names)
        self.assertIn("platform", input_names)


class BwaMem2MemInvocationTests(TestCase):
    """Verify bwa_mem2_mem pipeline string construction via run_tool."""

    def _run_with_mock(self, tmp_path, r2=None, capture_cmd=None):
        ref_fasta = tmp_path / "genome.fa"
        ref_fasta.write_text(">chr1\nACGT\n")
        r1_file = tmp_path / "sample_R1.fq.gz"
        r1_file.write_text("@read1\n")

        def fake_run_tool(cmd, sif, bind_paths):
            # cmd is ["bash", "-c", pipeline_str]
            pipeline_str = cmd[2]
            # create the BAM output
            import re
            m = re.search(r"-bS\s+-o\s+(\S+)", pipeline_str)
            if m:
                Path(m.group(1)).write_text("BAM")
            else:
                # fallback: find any _aligned.bam path
                bam = tmp_path / "bwa_mem2_mem_" / "s1_aligned.bam"
                bam.parent.mkdir(parents=True, exist_ok=True)
                bam.write_text("BAM")
            if capture_cmd is not None:
                capture_cmd.append(pipeline_str)

        r2_file = None
        if r2:
            r2_file = tmp_path / "sample_R2.fq.gz"
            r2_file.write_text("@read2\n")

        with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
            result = bwa_mem2_mem(
                reference_fasta=File(path=str(ref_fasta)),
                r1=File(path=str(r1_file)),
                sample_id="s1",
                r2=File(path=str(r2_file)) if r2_file else None,
            )

        # Create the actual BAM in the out_dir for path checking
        out_bam = Path(result.path)
        if not out_bam.exists():
            out_bam.parent.mkdir(parents=True, exist_ok=True)
            out_bam.write_text("BAM")
        return result

    def _run_and_capture_pipeline(self, tmp_path, r2=None):
        ref_fasta = tmp_path / "genome.fa"
        ref_fasta.write_text(">chr1\nACGT\n")
        r1_file = tmp_path / "sample_R1.fq.gz"
        r1_file.write_text("@read1\n")
        if r2:
            r2_file = tmp_path / "sample_R2.fq.gz"
            r2_file.write_text("@read2\n")
        else:
            r2_file = None

        captured_cmds: list[list[str]] = []

        def fake_run_tool(cmd, sif, bind_paths):
            captured_cmds.append(list(cmd))
            # create the BAM so FileNotFoundError doesn't fire
            import re
            pipeline_str = cmd[2]
            m = re.search(r"-bS\s+-o\s+(\S+)", pipeline_str)
            if m:
                out = Path(m.group(1))
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text("BAM")

        with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
            bwa_mem2_mem(
                reference_fasta=File(path=str(ref_fasta)),
                r1=File(path=str(r1_file)),
                sample_id="s1",
                r2=File(path=str(r2_file)) if r2_file else None,
            )
        return captured_cmds[0][2] if captured_cmds else ""  # the bash -c pipeline string

    def test_pipeline_contains_bwa_mem2_and_ref(self) -> None:
        """Pipeline string contains bwa-mem2, mem, -R, ref_path, and r1_path."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._run_and_capture_pipeline(Path(tmp))

        self.assertIn("bwa-mem2", pipeline)
        self.assertIn("mem", pipeline)
        self.assertIn("-R", pipeline)
        self.assertIn("genome.fa", pipeline)
        self.assertIn("sample_R1.fq.gz", pipeline)

    def test_r2_appended_when_provided(self) -> None:
        """R2 path appears in pipeline when r2 is provided."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._run_and_capture_pipeline(Path(tmp), r2=True)

        self.assertIn("sample_R2.fq.gz", pipeline)

    def test_r2_absent_for_single_end(self) -> None:
        """Pipeline does not contain R2 filename when r2 is None."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._run_and_capture_pipeline(Path(tmp), r2=None)

        self.assertNotIn("_R2", pipeline)

    def test_read_group_contains_sample_id(self) -> None:
        """Read-group string contains ID:<sample_id> and SM:<sample_id>."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._run_and_capture_pipeline(Path(tmp))

        self.assertIn("ID:s1", pipeline)
        self.assertIn("SM:s1", pipeline)

    def test_bwa_mem2_mem_default_library_id(self) -> None:
        """RG has LB:{sample_id}_lib when library_id omitted."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._run_and_capture_pipeline(Path(tmp))

        self.assertIn("LB:s1_lib", pipeline)

    def test_bwa_mem2_mem_explicit_library_id(self) -> None:
        """RG reflects the explicit library_id."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref = tmp_path / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            r1 = tmp_path / "r1.fq.gz"
            r1.write_text("@r\n")
            captured_cmds: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmds.append(list(cmd))
                import re
                m = re.search(r"-bS\s+-o\s+(\S+)", cmd[2])
                if m:
                    out = Path(m.group(1))
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("BAM")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                bwa_mem2_mem(
                    reference_fasta=File(path=str(ref)),
                    r1=File(path=str(r1)),
                    sample_id="s1",
                    library_id="mylib",
                )

        pipeline = captured_cmds[0][2]
        self.assertIn("LB:mylib", pipeline)
        self.assertNotIn("LB:s1_lib", pipeline)

    def test_bwa_mem2_mem_platform_override(self) -> None:
        """PL:PACBIO when platform='PACBIO'."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref = tmp_path / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            r1 = tmp_path / "r1.fq.gz"
            r1.write_text("@r\n")
            captured_cmds: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmds.append(list(cmd))
                import re
                m = re.search(r"-bS\s+-o\s+(\S+)", cmd[2])
                if m:
                    out = Path(m.group(1))
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("BAM")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                bwa_mem2_mem(
                    reference_fasta=File(path=str(ref)),
                    r1=File(path=str(r1)),
                    sample_id="s1",
                    platform="PACBIO",
                )

        pipeline = captured_cmds[0][2]
        self.assertIn("PL:PACBIO", pipeline)

    def test_missing_bam_raises(self) -> None:
        """FileNotFoundError raised when run_tool succeeds but BAM absent."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref = tmp_path / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            r1 = tmp_path / "r1.fq.gz"
            r1.write_text("@r\n")

            with patch.object(variant_calling, "run_tool"):
                with self.assertRaises(FileNotFoundError):
                    bwa_mem2_mem(
                        reference_fasta=File(path=str(ref)),
                        r1=File(path=str(r1)),
                        sample_id="s1",
                    )


class BwaMem2MemManifestTests(TestCase):
    """Verify bwa_mem2_mem returns a File and emits a manifest."""

    def test_bwa_mem2_mem_returns_file_with_aligned_bam(self) -> None:
        """Return value is a File pointing at <sample_id>_aligned.bam."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref = tmp_path / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            r1 = tmp_path / "r1.fq.gz"
            r1.write_text("@r\n")

            def fake_run_tool(cmd, sif, bind_paths):
                import re
                m = re.search(r"-bS\s+-o\s+(\S+)", cmd[2])
                if m:
                    out = Path(m.group(1))
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("BAM")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = bwa_mem2_mem(
                    reference_fasta=File(path=str(ref)),
                    r1=File(path=str(r1)),
                    sample_id="s1",
                )

        self.assertTrue(result.path.endswith("s1_aligned.bam"))


class SortSamRegistryTests(TestCase):
    """Guard the sort_sam registry entry shape."""

    def test_sort_sam_registry_entry_shape(self) -> None:
        """Entry exists at stage_order 10 in the variant_calling family."""
        from flytetest.registry import get_entry

        entry = get_entry("sort_sam")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "task")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 10)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("sorted_bam", output_names)
        self.assertIn("sorted_bam", MANIFEST_OUTPUT_KEYS)


class SortSamInvocationTests(TestCase):
    """Verify sort_sam builds the correct GATK SortSam command."""

    def test_sort_sam_command_shape(self) -> None:
        """run_tool called with SortSam, -I, -O, --SORT_ORDER coordinate, --CREATE_INDEX true."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_bam = tmp_path / "s1_aligned.bam"
            in_bam.write_text("BAM")

            captured: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured.append(cmd)
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("BAM")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = sort_sam(
                    aligned_bam=File(path=str(in_bam)),
                    sample_id="s1",
                )

        cmd = captured[0]
        self.assertIn("SortSam", cmd)
        self.assertIn("-I", cmd)
        self.assertIn("-O", cmd)
        self.assertIn("--SORT_ORDER", cmd)
        self.assertIn("coordinate", cmd)
        self.assertIn("--CREATE_INDEX", cmd)
        self.assertIn("true", cmd)
        o_idx = cmd.index("-O")
        self.assertTrue(cmd[o_idx + 1].endswith("s1_sorted.bam"))
        self.assertTrue(result.path.endswith("s1_sorted.bam"))

    def test_sort_sam_raises_on_missing_output(self) -> None:
        """FileNotFoundError raised when output BAM is absent after run."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_bam = tmp_path / "s1_aligned.bam"
            in_bam.write_text("BAM")

            with patch.object(variant_calling, "run_tool"):
                with self.assertRaises(FileNotFoundError):
                    sort_sam(
                        aligned_bam=File(path=str(in_bam)),
                        sample_id="s1",
                    )


class SortSamManifestTests(TestCase):
    """Verify sort_sam returns a File pointing at the sorted BAM."""

    def test_sort_sam_returns_sorted_bam_file(self) -> None:
        """Return value is a File with path ending in <sample_id>_sorted.bam."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_bam = tmp_path / "s1_aligned.bam"
            in_bam.write_text("BAM")

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("BAM")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = sort_sam(
                    aligned_bam=File(path=str(in_bam)),
                    sample_id="s1",
                )

        self.assertTrue(result.path.endswith("s1_sorted.bam"))


class MarkDuplicatesRegistryTests(TestCase):
    """Guard the mark_duplicates registry entry shape."""

    def test_mark_duplicates_registry_entry_shape(self) -> None:
        """Entry exists at stage_order 11 with two output fields."""
        from flytetest.registry import get_entry

        entry = get_entry("mark_duplicates")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "task")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 11)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("dedup_bam", output_names)
        self.assertIn("duplicate_metrics", output_names)
        self.assertIn("dedup_bam", MANIFEST_OUTPUT_KEYS)
        self.assertIn("duplicate_metrics", MANIFEST_OUTPUT_KEYS)


class MarkDuplicatesInvocationTests(TestCase):
    """Verify mark_duplicates builds the correct GATK MarkDuplicates command."""

    def test_mark_duplicates_command_shape(self) -> None:
        """run_tool called with MarkDuplicates, -I, -O, -M, --CREATE_INDEX true."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_bam = tmp_path / "s1_sorted.bam"
            in_bam.write_text("BAM")

            captured: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured.append(cmd)
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("BAM")
                m_idx = cmd.index("-M")
                Path(cmd[m_idx + 1]).write_text("metrics")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                dedup_bam, metrics = mark_duplicates(
                    sorted_bam=File(path=str(in_bam)),
                    sample_id="s1",
                )

        cmd = captured[0]
        self.assertIn("MarkDuplicates", cmd)
        self.assertIn("-I", cmd)
        self.assertIn("-O", cmd)
        self.assertIn("-M", cmd)
        self.assertIn("--CREATE_INDEX", cmd)
        self.assertIn("true", cmd)
        o_idx = cmd.index("-O")
        self.assertIn("_marked_duplicates", cmd[o_idx + 1])
        m_idx = cmd.index("-M")
        self.assertIn("_duplicate_metrics", cmd[m_idx + 1])
        self.assertIn("_marked_duplicates", dedup_bam.path)
        self.assertIn("_duplicate_metrics", metrics.path)

    def test_mark_duplicates_raises_on_missing_bam(self) -> None:
        """FileNotFoundError raised when output BAM is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_bam = tmp_path / "s1_sorted.bam"
            in_bam.write_text("BAM")

            with patch.object(variant_calling, "run_tool"):
                with self.assertRaises(FileNotFoundError):
                    mark_duplicates(
                        sorted_bam=File(path=str(in_bam)),
                        sample_id="s1",
                    )


class MarkDuplicatesManifestTests(TestCase):
    """Verify mark_duplicates returns tuple[File, File] with both outputs."""

    def test_mark_duplicates_returns_both_files(self) -> None:
        """Returns (dedup_bam, metrics_file) with correct path suffixes."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_bam = tmp_path / "s1_sorted.bam"
            in_bam.write_text("BAM")

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("BAM")
                m_idx = cmd.index("-M")
                Path(cmd[m_idx + 1]).write_text("metrics")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                dedup_bam, metrics = mark_duplicates(
                    sorted_bam=File(path=str(in_bam)),
                    sample_id="s1",
                )

        self.assertIn("_marked_duplicates", dedup_bam.path)
        self.assertIn("_duplicate_metrics", metrics.path)


# ---------------------------------------------------------------------------
# VariantRecalibrator tests (Milestone D Step 01)
# ---------------------------------------------------------------------------

_FAKE_SNP_FLAGS = [
    {"resource_name": "hapmap", "known": "false", "training": "true",  "truth": "true",  "prior": "15"},
    {"resource_name": "dbsnp",  "known": "true",  "training": "false", "truth": "false", "prior": "2"},
]
_FAKE_INDEL_FLAGS = [
    {"resource_name": "mills", "known": "false", "training": "true",  "truth": "true",  "prior": "12"},
    {"resource_name": "dbsnp", "known": "true",  "training": "false", "truth": "false", "prior": "2"},
]


class VariantRecalibratorRegistryTests(TestCase):
    """Guard the variant_recalibrator registry entry shape."""

    def test_variant_recalibrator_registry_entry_shape(self) -> None:
        """Entry exists at stage_order 12 with recal_file and tranches_file outputs."""
        from flytetest.registry import get_entry

        entry = get_entry("variant_recalibrator")
        self.assertEqual(entry.category, "task")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 12)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        output_names = [f.name for f in entry.outputs]
        self.assertIn("recal_file", output_names)
        self.assertIn("tranches_file", output_names)


class VariantRecalibratorAnnotationTests(TestCase):
    """Tests for _resolve_vqsr_annotations (Step 03 — VQSR parameterization)."""

    def test_snp_defaults_below_threshold(self) -> None:
        """sample_count=5, SNP, annotations=None → default SNP list, no InbreedingCoeff."""
        result = _resolve_vqsr_annotations("SNP", 5, None)
        self.assertEqual(result, ["QD", "MQ", "MQRankSum", "ReadPosRankSum", "FS", "SOR"])
        self.assertNotIn("InbreedingCoeff", result)

    def test_snp_auto_adds_inbreeding_coeff_at_threshold(self) -> None:
        """sample_count=10, SNP → InbreedingCoeff appended."""
        result = _resolve_vqsr_annotations("SNP", 10, None)
        self.assertIn("InbreedingCoeff", result)

    def test_snp_auto_adds_inbreeding_coeff_above_threshold(self) -> None:
        """sample_count=50, SNP → InbreedingCoeff appended."""
        result = _resolve_vqsr_annotations("SNP", 50, None)
        self.assertIn("InbreedingCoeff", result)

    def test_indel_never_auto_adds_inbreeding_coeff(self) -> None:
        """sample_count=50, INDEL → defaults unchanged, no InbreedingCoeff."""
        result = _resolve_vqsr_annotations("INDEL", 50, None)
        self.assertNotIn("InbreedingCoeff", result)

    def test_explicit_annotations_override_defaults_and_auto_add(self) -> None:
        """annotations=['QD','DP'], sample_count=50, SNP → exactly ['QD','DP']."""
        result = _resolve_vqsr_annotations("SNP", 50, ["QD", "DP"])
        self.assertEqual(result, ["QD", "DP"])
        self.assertNotIn("InbreedingCoeff", result)

    def test_effective_annotations_recorded_in_manifest(self) -> None:
        """variant_recalibrator manifest inputs contain effective_annotations."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "cohort.vcf.gz", "hapmap.vcf.gz"):
                (tmp_path / f).write_text("stub")

            captured_manifests: list[dict] = []

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("recal")
                t_idx = cmd.index("--tranches-file")
                Path(cmd[t_idx + 1]).write_text("tranches")

            with (
                patch.object(variant_calling, "run_tool", side_effect=fake_run_tool),
                patch.object(variant_calling, "_write_json",
                             side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                variant_recalibrator(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    cohort_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    known_sites=[File(path=str(tmp_path / "hapmap.vcf.gz"))],
                    known_sites_flags=[_FAKE_SNP_FLAGS[0]],
                    mode="SNP",
                    cohort_id="cohort1",
                    sample_count=5,
                )

        self.assertIn("effective_annotations", captured_manifests[0]["inputs"])


class VariantRecalibratorInvocationTests(TestCase):
    """Verify variant_recalibrator builds the correct GATK command."""

    def _run_vr(self, tmp_path, mode, resource_flags=None, sample_count=5):
        ref_fa = tmp_path / "ref.fa"
        vcf_file = tmp_path / "cohort.vcf.gz"
        site1 = tmp_path / "hapmap.vcf.gz"
        site2 = tmp_path / "dbsnp.vcf"
        for p in (ref_fa, vcf_file, site1, site2):
            p.write_text("stub")

        flags = resource_flags or _FAKE_SNP_FLAGS
        sites = [File(path=str(site1)), File(path=str(site2))]

        captured: list[list[str]] = []

        def fake_run_tool(cmd, sif, bind_paths):
            captured.append(list(cmd))
            o_idx = cmd.index("-O")
            Path(cmd[o_idx + 1]).write_text("recal")
            t_idx = cmd.index("--tranches-file")
            Path(cmd[t_idx + 1]).write_text("tranches")

        with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
            recal, tranches = variant_recalibrator(
                reference_fasta=File(path=str(ref_fa)),
                cohort_vcf=File(path=str(vcf_file)),
                known_sites=sites,
                known_sites_flags=flags,
                mode=mode,
                cohort_id="cohort1",
                sample_count=sample_count,
            )
        return captured[0], recal, tranches

    def test_variant_recalibrator_snp_runs(self) -> None:
        """SNP mode returns (recal_file, tranches_file) with correct suffixes."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd, recal, tranches = self._run_vr(Path(tmp), "SNP")
        self.assertTrue(recal.path.endswith("_snp.recal"))
        self.assertTrue(tranches.path.endswith("_snp.tranches"))

    def test_variant_recalibrator_indel_runs(self) -> None:
        """INDEL mode output paths carry _indel suffix."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd, recal, tranches = self._run_vr(Path(tmp), "INDEL", _FAKE_INDEL_FLAGS)
        self.assertTrue(recal.path.endswith("_indel.recal"))
        self.assertTrue(tranches.path.endswith("_indel.tranches"))

    def test_variant_recalibrator_invalid_mode(self) -> None:
        """ValueError raised for unsupported mode."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "cohort.vcf.gz"):
                (tmp_path / f).write_text("stub")
            with self.assertRaises(ValueError) as ctx:
                variant_recalibrator(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    cohort_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    known_sites=[File(path=str(tmp_path / "cohort.vcf.gz"))],
                    known_sites_flags=_FAKE_SNP_FLAGS[:1],
                    mode="MIXED",
                    cohort_id="c",
                    sample_count=5,
                )
            self.assertIn("MIXED", str(ctx.exception))

    def test_variant_recalibrator_resource_flags_snp(self) -> None:
        """SNP mode includes MQ and MQRankSum annotations; -mode SNP in command."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd, _, _ = self._run_vr(Path(tmp), "SNP")
        self.assertIn("-mode", cmd)
        self.assertEqual(cmd[cmd.index("-mode") + 1], "SNP")
        self.assertIn("-an", cmd)
        annotations = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-an"]
        self.assertIn("MQ", annotations)
        self.assertIn("MQRankSum", annotations)
        self.assertIn("ReadPosRankSum", annotations)
        resource_flags = [v for v in cmd if v.startswith("--resource:")]
        self.assertEqual(len(resource_flags), 2)
        self.assertIn("hapmap", resource_flags[0])
        self.assertIn("training=true", resource_flags[0])

    def test_variant_recalibrator_resource_flags_indel(self) -> None:
        """INDEL mode omits MQ and MQRankSum; -mode INDEL in command."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd, _, _ = self._run_vr(Path(tmp), "INDEL", _FAKE_INDEL_FLAGS)
        self.assertEqual(cmd[cmd.index("-mode") + 1], "INDEL")
        annotations = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-an"]
        self.assertNotIn("MQ", annotations)
        self.assertNotIn("MQRankSum", annotations)
        self.assertIn("QD", annotations)
        self.assertIn("FS", annotations)


class VariantRecalibratorManifestTests(TestCase):
    """Verify variant_recalibrator emits a manifest with effective_annotations."""

    def test_variant_recalibrator_emits_manifest(self) -> None:
        """Manifest contains recal_file, tranches_file, and effective_annotations."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "cohort.vcf.gz", "hapmap.vcf.gz"):
                (tmp_path / f).write_text("stub")

            captured_manifests: list[dict] = []

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("recal")
                t_idx = cmd.index("--tranches-file")
                Path(cmd[t_idx + 1]).write_text("tranches")

            with (
                patch.object(variant_calling, "run_tool", side_effect=fake_run_tool),
                patch.object(variant_calling, "_write_json",
                             side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                variant_recalibrator(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    cohort_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    known_sites=[File(path=str(tmp_path / "hapmap.vcf.gz"))],
                    known_sites_flags=[_FAKE_SNP_FLAGS[0]],
                    mode="SNP",
                    cohort_id="cohort1",
                    sample_count=5,
                )

        manifest = captured_manifests[0]
        self.assertEqual(manifest["stage"], "variant_recalibrator")
        self.assertIn("recal_file", manifest["outputs"])
        self.assertIn("tranches_file", manifest["outputs"])
        self.assertIn("effective_annotations", manifest["inputs"])


# ---------------------------------------------------------------------------
# ApplyVQSR tests (Milestone D Step 02)
# ---------------------------------------------------------------------------

class ApplyVQSRRegistryTests(TestCase):
    """Guard the apply_vqsr registry entry shape."""

    def test_apply_vqsr_registry_entry_shape(self) -> None:
        """Entry exists at stage_order 13 with vqsr_vcf output."""
        from flytetest.registry import get_entry

        entry = get_entry("apply_vqsr")
        self.assertEqual(entry.category, "task")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 13)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        output_names = [f.name for f in entry.outputs]
        self.assertIn("vqsr_vcf", output_names)


class ApplyVQSRInvocationTests(TestCase):
    """Verify apply_vqsr builds the correct GATK ApplyVQSR command."""

    def _run_av(self, tmp_path, mode, filter_level=0.0):
        ref_fa = tmp_path / "ref.fa"
        vcf_file = tmp_path / "cohort.vcf.gz"
        recal = tmp_path / "cohort_snp.recal"
        tranches = tmp_path / "cohort_snp.tranches"
        for p in (ref_fa, vcf_file, recal, tranches):
            p.write_text("stub")

        captured: list[list[str]] = []

        def fake_run_tool(cmd, sif, bind_paths):
            captured.append(list(cmd))
            o_idx = cmd.index("-O")
            out = Path(cmd[o_idx + 1])
            out.write_text("VCF")
            Path(str(out) + ".tbi").write_text("TBI")

        with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
            result = apply_vqsr(
                reference_fasta=File(path=str(ref_fa)),
                input_vcf=File(path=str(vcf_file)),
                recal_file=File(path=str(recal)),
                tranches_file=File(path=str(tranches)),
                mode=mode,
                cohort_id="cohort1",
                truth_sensitivity_filter_level=filter_level,
            )
        return captured[0], result

    def test_apply_vqsr_snp_runs(self) -> None:
        """SNP mode returns File with path ending in _vqsr_snp.vcf.gz."""
        with tempfile.TemporaryDirectory() as tmp:
            _, result = self._run_av(Path(tmp), "SNP")
        self.assertTrue(result.path.endswith("_vqsr_snp.vcf.gz"))

    def test_apply_vqsr_indel_runs(self) -> None:
        """INDEL mode output path ends in _vqsr_indel.vcf.gz."""
        with tempfile.TemporaryDirectory() as tmp:
            _, result = self._run_av(Path(tmp), "INDEL")
        self.assertTrue(result.path.endswith("_vqsr_indel.vcf.gz"))

    def test_apply_vqsr_default_filter_level_snp(self) -> None:
        """filter_level=0.0 for SNP resolves to 99.5 in the command."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd, _ = self._run_av(Path(tmp), "SNP", filter_level=0.0)
        idx = cmd.index("--truth-sensitivity-filter-level")
        self.assertEqual(cmd[idx + 1], "99.5")

    def test_apply_vqsr_default_filter_level_indel(self) -> None:
        """filter_level=0.0 for INDEL resolves to 99.0 in the command."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd, _ = self._run_av(Path(tmp), "INDEL", filter_level=0.0)
        idx = cmd.index("--truth-sensitivity-filter-level")
        self.assertEqual(cmd[idx + 1], "99.0")

    def test_apply_vqsr_custom_filter_level(self) -> None:
        """Explicit filter_level overrides the default."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd, _ = self._run_av(Path(tmp), "SNP", filter_level=99.0)
        idx = cmd.index("--truth-sensitivity-filter-level")
        self.assertEqual(cmd[idx + 1], "99.0")

    def test_apply_vqsr_invalid_mode(self) -> None:
        """ValueError raised for mode != SNP|INDEL."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for stub in ("ref.fa", "cohort.vcf.gz", "c.recal", "c.tranches"):
                (tmp_path / stub).write_text("stub")
            with self.assertRaises(ValueError) as ctx:
                apply_vqsr(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    input_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    recal_file=File(path=str(tmp_path / "c.recal")),
                    tranches_file=File(path=str(tmp_path / "c.tranches")),
                    mode="BOTH",
                    cohort_id="c",
                )
            self.assertIn("BOTH", str(ctx.exception))

    def test_apply_vqsr_missing_output_raises(self) -> None:
        """FileNotFoundError raised when output VCF is absent after run."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for stub in ("ref.fa", "cohort.vcf.gz", "c.recal", "c.tranches"):
                (tmp_path / stub).write_text("stub")

            with patch.object(variant_calling, "run_tool", return_value=None):
                with self.assertRaises(FileNotFoundError):
                    apply_vqsr(
                        reference_fasta=File(path=str(tmp_path / "ref.fa")),
                        input_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                        recal_file=File(path=str(tmp_path / "c.recal")),
                        tranches_file=File(path=str(tmp_path / "c.tranches")),
                        mode="SNP",
                        cohort_id="cohort1",
                    )


class ApplyVQSRManifestTests(TestCase):
    """Verify apply_vqsr emits a manifest with vqsr_vcf key."""

    def test_apply_vqsr_emits_manifest(self) -> None:
        """run_manifest_apply_vqsr.json has vqsr_vcf key."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for stub in ("ref.fa", "cohort.vcf.gz", "c.recal", "c.tranches"):
                (tmp_path / stub).write_text("stub")

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                out = Path(cmd[o_idx + 1])
                out.write_text("VCF")
                Path(str(out) + ".tbi").write_text("TBI")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = apply_vqsr(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    input_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    recal_file=File(path=str(tmp_path / "c.recal")),
                    tranches_file=File(path=str(tmp_path / "c.tranches")),
                    mode="SNP",
                    cohort_id="cohort1",
                )

        self.assertTrue(result.path.endswith("_vqsr_snp.vcf.gz"))


# ---------------------------------------------------------------------------
# MergeBamAlignment tests (Milestone E Step 02)
# ---------------------------------------------------------------------------

class MergeBamAlignmentRegistryTests(TestCase):
    """Guard the merge_bam_alignment registry entry shape."""

    def test_merge_bam_alignment_registry_entry_shape(self) -> None:
        from flytetest.registry import get_entry
        entry = get_entry("merge_bam_alignment")
        self.assertEqual(entry.category, "task")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 14)
        output_names = [f.name for f in entry.outputs]
        self.assertIn("merged_bam", output_names)


class MergeBamAlignmentTests(TestCase):
    """Verify merge_bam_alignment command and return value."""

    def _run_mba(self, tmp_path):
        ref_fa = tmp_path / "ref.fa"
        aligned = tmp_path / "s1_aligned.bam"
        ubam = tmp_path / "s1.unmapped.bam"
        for p in (ref_fa, aligned, ubam):
            p.write_text("stub")

        captured: list[list[str]] = []

        def fake_run_tool(cmd, sif, bind_paths):
            captured.append(list(cmd))
            o_idx = cmd.index("-O")
            Path(cmd[o_idx + 1]).write_text("BAM")

        with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
            result = merge_bam_alignment(
                reference_fasta=File(path=str(ref_fa)),
                aligned_bam=File(path=str(aligned)),
                ubam=File(path=str(ubam)),
                sample_id="s1",
            )
        return captured[0], result

    def test_merge_bam_alignment_runs(self) -> None:
        """Returns File with path ending in _merged.bam."""
        with tempfile.TemporaryDirectory() as tmp:
            _, result = self._run_mba(Path(tmp))
        self.assertTrue(result.path.endswith("_merged.bam"))

    def test_merge_bam_alignment_command_shape(self) -> None:
        """All required flags present in command."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd, _ = self._run_mba(Path(tmp))
        self.assertIn("MergeBamAlignment", cmd)
        self.assertIn("-ALIGNED", cmd)
        self.assertIn("-UNMAPPED", cmd)
        sort_idx = cmd.index("--SORT_ORDER")
        self.assertEqual(cmd[sort_idx + 1], "coordinate")
        clip_idx = cmd.index("--CLIP_ADAPTERS")
        self.assertEqual(cmd[clip_idx + 1], "false")
        self.assertIn("--PRIMARY_ALIGNMENT_STRATEGY", cmd)
        primary_idx = cmd.index("--PRIMARY_ALIGNMENT_STRATEGY")
        self.assertEqual(cmd[primary_idx + 1], "MostDistant")
        self.assertIn("--ATTRIBUTES_TO_RETAIN", cmd)
        self.assertIn("X0", cmd)

    def test_merge_bam_alignment_missing_output_raises(self) -> None:
        """FileNotFoundError when output BAM absent after run."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for stub in ("ref.fa", "aligned.bam", "ubam.bam"):
                (tmp_path / stub).write_text("stub")
            with patch.object(variant_calling, "run_tool", return_value=None):
                with self.assertRaises(FileNotFoundError):
                    merge_bam_alignment(
                        reference_fasta=File(path=str(tmp_path / "ref.fa")),
                        aligned_bam=File(path=str(tmp_path / "aligned.bam")),
                        ubam=File(path=str(tmp_path / "ubam.bam")),
                        sample_id="s1",
                    )

    def test_merge_bam_alignment_manifest_key(self) -> None:
        """Manifest contains merged_bam key."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for stub in ("ref.fa", "aligned.bam", "ubam.bam"):
                (tmp_path / stub).write_text("stub")

            captured_manifests: list[dict] = []

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("BAM")

            with (
                patch.object(variant_calling, "run_tool", side_effect=fake_run_tool),
                patch.object(variant_calling, "_write_json",
                             side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                merge_bam_alignment(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    aligned_bam=File(path=str(tmp_path / "aligned.bam")),
                    ubam=File(path=str(tmp_path / "ubam.bam")),
                    sample_id="s1",
                )

        self.assertEqual(captured_manifests[0]["stage"], "merge_bam_alignment")
        self.assertIn("merged_bam", captured_manifests[0]["outputs"])


# ---------------------------------------------------------------------------
# Milestone F Step 02 — gather_vcfs
# ---------------------------------------------------------------------------

class GatherVcfsTests(TestCase):
    """Tests for the gather_vcfs task."""

    def test_gather_vcfs_runs(self):
        """Returns File ending in _gathered.g.vcf.gz."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gvcf1 = tmp_path / "s1_chr1.g.vcf"
            gvcf2 = tmp_path / "s1_chr2.g.vcf"
            gvcf1.write_text("gvcf")
            gvcf2.write_text("gvcf")

            def fake_run_tool(cmd, sif, bind_paths):
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = gather_vcfs(
                    gvcfs=[File(path=str(gvcf1)), File(path=str(gvcf2))],
                    sample_id="s1",
                )

        self.assertTrue(result.path.endswith("_gathered.g.vcf.gz"))

    def test_gather_vcfs_builds_I_flags(self):
        """Each gvcf File produces one -I flag in the correct order."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gvcf_files = []
            for i in range(3):
                gvcf = tmp_path / f"s1_chr{i}.g.vcf"
                gvcf.write_text("gvcf")
                gvcf_files.append(gvcf)

            captured_cmd = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                gather_vcfs(
                    gvcfs=[File(path=str(f)) for f in gvcf_files],
                    sample_id="s1",
                )

        i_indices = [i for i, v in enumerate(captured_cmd) if v == "-I"]
        self.assertEqual(len(i_indices), 3)
        for pos, expected in zip(i_indices, gvcf_files):
            self.assertEqual(captured_cmd[pos + 1], str(expected))

    def test_gather_vcfs_empty_list_raises(self):
        """ValueError raised when gvcfs is empty."""
        with self.assertRaises(ValueError):
            gather_vcfs(
                gvcfs=[],
                sample_id="s1",
            )

    def test_gather_vcfs_missing_output_raises(self):
        """FileNotFoundError raised when run_tool does not produce output."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gvcf = tmp_path / "s1_chr1.g.vcf"
            gvcf.write_text("gvcf")

            with patch.object(variant_calling, "run_tool"):
                with self.assertRaises(FileNotFoundError):
                    gather_vcfs(
                        gvcfs=[File(path=str(gvcf))],
                        sample_id="s1",
                    )


# ---------------------------------------------------------------------------
# Milestone G Step 01 — calculate_genotype_posteriors
# ---------------------------------------------------------------------------

class CalculateGenotypePosteriorTests(TestCase):
    """Tests for the calculate_genotype_posteriors task (File-based API)."""

    def test_cgp_runs_without_supporting_callsets(self):
        """--supporting-callsets flag is omitted when supporting_callsets is None."""
        with tempfile.TemporaryDirectory() as tmp:
            vcf = Path(tmp) / "cohort.vcf.gz"
            vcf.touch()

            captured_cmd = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = calculate_genotype_posteriors(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                )

        self.assertNotIn("--supporting-callsets", captured_cmd)
        self.assertTrue(result.path.endswith("_cgp.vcf.gz"))

    def test_cgp_runs_with_supporting_callsets(self):
        """--supporting-callsets appears once per entry when list is non-empty."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf = tmp_path / "cohort.vcf.gz"
            vcf.touch()
            cs1 = tmp_path / "pop1.vcf"
            cs2 = tmp_path / "pop2.vcf"
            cs1.write_text("vcf")
            cs2.write_text("vcf")

            captured_cmd = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                calculate_genotype_posteriors(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                    supporting_callsets=[File(path=str(cs1)), File(path=str(cs2))],
                )

        sc_indices = [i for i, v in enumerate(captured_cmd) if v == "--supporting-callsets"]
        self.assertEqual(len(sc_indices), 2)
        self.assertEqual(captured_cmd[sc_indices[0] + 1], str(cs1))
        self.assertEqual(captured_cmd[sc_indices[1] + 1], str(cs2))

    def test_cgp_output_filename(self):
        """Return file path ends with _cgp.vcf.gz and contains cohort_id."""
        with tempfile.TemporaryDirectory() as tmp:
            vcf = Path(tmp) / "cohort.vcf.gz"
            vcf.touch()

            def fake_run_tool(cmd, sif, bind_paths):
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = calculate_genotype_posteriors(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                )

        self.assertTrue(result.path.endswith("_cgp.vcf.gz"))
        self.assertIn("cohort1", result.path)

    def test_cgp_missing_output_raises(self):
        """FileNotFoundError raised when output VCF is not produced."""
        with tempfile.TemporaryDirectory() as tmp:
            vcf = Path(tmp) / "cohort.vcf.gz"
            vcf.touch()

            with patch.object(variant_calling, "run_tool"):
                with self.assertRaises(FileNotFoundError):
                    calculate_genotype_posteriors(
                        input_vcf=File(path=str(vcf)),
                        cohort_id="cohort1",
                    )

    def test_cgp_no_R_flag(self):
        """The -R flag must not appear in the command."""
        with tempfile.TemporaryDirectory() as tmp:
            vcf = Path(tmp) / "cohort.vcf.gz"
            vcf.touch()

            captured_cmd = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmd.extend(cmd)
                out_idx = cmd.index("-O")
                Path(cmd[out_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                calculate_genotype_posteriors(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                )

        self.assertNotIn("-R", captured_cmd)

    def test_cgp_signature_has_no_ref_path(self):
        """calculate_genotype_posteriors signature must not include ref_path."""
        import inspect
        sig = inspect.signature(calculate_genotype_posteriors)
        self.assertNotIn("ref_path", sig.parameters)


class BwaMem2MemShellQuotingTests(TestCase):
    """Regression tests for shell-injection safety in bwa_mem2_mem (pipeline string via run_tool)."""

    def _capture_pipeline(self, ref, r1, r2=None, sample_id="s1"):
        captured_cmds: list[list[str]] = []

        def fake_run_tool(cmd, sif, bind_paths):
            captured_cmds.append(list(cmd))
            import re
            pipeline_str = cmd[2]
            m = re.search(r"-bS\s+-o\s+(\S+)", pipeline_str)
            if m:
                out = Path(m.group(1))
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text("BAM")

        with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
            bwa_mem2_mem(
                reference_fasta=File(path=str(ref)),
                r1=File(path=str(r1)),
                sample_id=sample_id,
                r2=File(path=str(r2)) if r2 else None,
            )
        return captured_cmds[0][2] if captured_cmds else ""

    def test_bwa_mem2_mem_handles_path_with_space(self) -> None:
        """Paths containing spaces appear shell-quoted in the pipeline string."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "my ref" / "genome.fa"
            ref.parent.mkdir()
            ref.write_text(">chr1\nACGT\n")
            r1 = Path(tmp) / "my ref" / "sample R1.fq.gz"
            r1.write_text("@r\n")

            pipeline = self._capture_pipeline(ref, r1)

        self.assertIn("bwa-mem2", pipeline)
        self.assertRegex(pipeline, r"'[^']*my ref[^']*genome\.fa'")

    def test_bwa_mem2_mem_rejects_unquoted_metacharacters(self) -> None:
        """Shell metacharacters in paths are quoted, not interpreted as shell tokens."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            r1 = Path(tmp) / "reads;echo pwned.fq.gz"
            r1.write_text("@r\n")

            pipeline = self._capture_pipeline(ref, r1)

        self.assertNotIn(";echo pwned", pipeline.split("'")[0] if "'" in pipeline else pipeline)
        self.assertIn("echo pwned", pipeline)


class PerStageManifestFilenameTests(TestCase):
    """Regression tests for per-stage manifest naming in variant_calling tasks."""

    def test_each_task_writes_namespaced_manifest(self) -> None:
        """calculate_genotype_posteriors writes run_manifest_calculate_genotype_posteriors.json."""
        import unittest.mock as mock

        written_paths: list[str] = []

        def capturing_write(path, data):
            written_paths.append(str(path))

        def fake_run_tool(cmd, sif, bind_paths):
            out_idx = cmd.index("-O")
            Path(cmd[out_idx + 1]).touch()

        with mock.patch.object(variant_calling, "_write_json", side_effect=capturing_write):
            with tempfile.TemporaryDirectory() as tmp:
                vcf = Path(tmp) / "cohort.vcf.gz"
                vcf.touch()

                with mock.patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                    calculate_genotype_posteriors(
                        input_vcf=File(path=str(vcf)),
                        cohort_id="cohort1",
                    )

        self.assertTrue(
            any("run_manifest_calculate_genotype_posteriors.json" in p for p in written_paths),
            f"Expected run_manifest_calculate_genotype_posteriors.json, got: {written_paths}",
        )
        self.assertFalse(
            any(p.endswith("run_manifest.json") for p in written_paths),
            f"Found bare run_manifest.json: {written_paths}",
        )

    def test_manifest_filename_never_bare_run_manifest(self) -> None:
        """bwa_mem2_mem writes run_manifest_bwa_mem2_mem.json, not run_manifest.json."""
        import unittest.mock as mock

        written_paths: list[str] = []

        def capturing_write(path, data):
            written_paths.append(str(path))

        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            r1 = Path(tmp) / "r1.fq.gz"
            r1.write_text("@r\n")

            def fake_run_tool(cmd, sif, bind_paths):
                import re
                pipeline_str = cmd[2]
                m = re.search(r"-bS\s+-o\s+(\S+)", pipeline_str)
                if m:
                    out = Path(m.group(1))
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("BAM")

            with mock.patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                with mock.patch.object(variant_calling, "_write_json", side_effect=capturing_write):
                    bwa_mem2_mem(
                        reference_fasta=File(path=str(ref)),
                        r1=File(path=str(r1)),
                        sample_id="s1",
                    )

        self.assertTrue(
            any("run_manifest_bwa_mem2_mem.json" in p for p in written_paths),
            f"Expected run_manifest_bwa_mem2_mem.json, got: {written_paths}",
        )
        self.assertFalse(
            any(p.endswith("run_manifest.json") for p in written_paths),
            f"Found bare run_manifest.json in bwa_mem2_mem: {written_paths}",
        )


# ---------------------------------------------------------------------------
# Milestone I Steps 04–06 — new task tests
# ---------------------------------------------------------------------------

class VariantFiltrationTests(TestCase):
    """Tests for the variant_filtration task (Step 04 — hard-filtering)."""

    def test_default_snp_expressions_applied(self) -> None:
        """mode='SNP', filter_expressions=None → cmd contains the 6 default name/expression pairs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "cohort.vcf.gz"):
                (tmp_path / f).write_text("stub")

            captured: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured.append(list(cmd))
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = variant_filtration(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    input_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    mode="SNP",
                    cohort_id="cohort1",
                )

        cmd = captured[0]
        filter_names = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--filter-name"]
        self.assertIn("QD2", filter_names)
        self.assertIn("FS60", filter_names)
        self.assertIn("MQ40", filter_names)
        self.assertIn("SOR3", filter_names)

    def test_default_indel_expressions_applied(self) -> None:
        """mode='INDEL', filter_expressions=None → cmd contains the 4 default INDEL pairs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "cohort.vcf.gz"):
                (tmp_path / f).write_text("stub")

            captured: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured.append(list(cmd))
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                variant_filtration(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    input_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    mode="INDEL",
                    cohort_id="cohort1",
                )

        cmd = captured[0]
        filter_names = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--filter-name"]
        self.assertIn("FS200", filter_names)
        self.assertIn("SOR10", filter_names)
        # SNP-only filters must be absent
        self.assertNotIn("MQ40", filter_names)

    def test_override_filter_expressions(self) -> None:
        """Custom tuple list passes through as-is; defaults not present."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "cohort.vcf.gz"):
                (tmp_path / f).write_text("stub")

            custom = [("MYFILTER", "QD < 1.0")]
            captured: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured.append(list(cmd))
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).touch()

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                variant_filtration(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    input_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    mode="SNP",
                    cohort_id="cohort1",
                    filter_expressions=custom,
                )

        cmd = captured[0]
        filter_names = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--filter-name"]
        self.assertIn("MYFILTER", filter_names)
        self.assertNotIn("QD2", filter_names)

    def test_invalid_mode_raises(self) -> None:
        """mode='CNV' raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "ref.fa").write_text("stub")
            (tmp_path / "vcf.vcf").write_text("stub")
            with self.assertRaises(ValueError):
                variant_filtration(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    input_vcf=File(path=str(tmp_path / "vcf.vcf")),
                    mode="CNV",
                    cohort_id="cohort1",
                )

    def test_missing_output_raises(self) -> None:
        """FileNotFoundError when output absent after run."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "cohort.vcf.gz"):
                (tmp_path / f).write_text("stub")

            with patch.object(variant_calling, "run_tool"):
                with self.assertRaises(FileNotFoundError):
                    variant_filtration(
                        reference_fasta=File(path=str(tmp_path / "ref.fa")),
                        input_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                        mode="SNP",
                        cohort_id="cohort1",
                    )

    def test_effective_expressions_recorded_in_manifest(self) -> None:
        """Manifest inputs include effective_filter_expressions."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "cohort.vcf.gz"):
                (tmp_path / f).write_text("stub")

            captured_manifests: list[dict] = []

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).touch()

            with (
                patch.object(variant_calling, "run_tool", side_effect=fake_run_tool),
                patch.object(variant_calling, "_write_json",
                             side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                variant_filtration(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    input_vcf=File(path=str(tmp_path / "cohort.vcf.gz")),
                    mode="SNP",
                    cohort_id="cohort1",
                )

        self.assertIn("effective_filter_expressions", captured_manifests[0]["inputs"])

    def test_registry_entry_shape(self) -> None:
        """Entry at task stage 17 with showcase_module set."""
        from flytetest.registry import get_entry
        entry = get_entry("variant_filtration")
        self.assertEqual(entry.category, "task")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 17)
        self.assertEqual(entry.showcase_module, "flytetest.tasks.variant_calling")
        self.assertIn("filtered_vcf", MANIFEST_OUTPUT_KEYS)


class CollectWgsMetricsTests(TestCase):
    """Tests for collect_wgs_metrics task (Step 05)."""

    def test_both_outputs_returned(self) -> None:
        """Returns (wgs_metrics_txt, insert_size_metrics_txt) tuple."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "s1.bam"):
                (tmp_path / f).write_text("stub")

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("metrics")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                wgs, insert = collect_wgs_metrics(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    aligned_bam=File(path=str(tmp_path / "s1.bam")),
                    sample_id="s1",
                )

        self.assertTrue(wgs.path.endswith("_wgs_metrics.txt"))
        self.assertTrue(insert.path.endswith("_insert_size_metrics.txt"))

    def test_missing_wgs_output_raises(self) -> None:
        """FileNotFoundError when WGS metrics file absent."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "s1.bam"):
                (tmp_path / f).write_text("stub")

            with patch.object(variant_calling, "run_tool"):
                with self.assertRaises(FileNotFoundError):
                    collect_wgs_metrics(
                        reference_fasta=File(path=str(tmp_path / "ref.fa")),
                        aligned_bam=File(path=str(tmp_path / "s1.bam")),
                        sample_id="s1",
                    )

    def test_manifest_records_both_paths(self) -> None:
        """Manifest outputs contain wgs_metrics and insert_size_metrics."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for f in ("ref.fa", "s1.bam"):
                (tmp_path / f).write_text("stub")

            captured_manifests: list[dict] = []

            def fake_run_tool(cmd, sif, bind_paths):
                o_idx = cmd.index("-O")
                Path(cmd[o_idx + 1]).write_text("metrics")

            with (
                patch.object(variant_calling, "run_tool", side_effect=fake_run_tool),
                patch.object(variant_calling, "_write_json",
                             side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                collect_wgs_metrics(
                    reference_fasta=File(path=str(tmp_path / "ref.fa")),
                    aligned_bam=File(path=str(tmp_path / "s1.bam")),
                    sample_id="s1",
                )

        m = captured_manifests[0]
        self.assertIn("wgs_metrics", m["outputs"])
        self.assertIn("insert_size_metrics", m["outputs"])


class BcftoolsStatsTests(TestCase):
    """Tests for bcftools_stats task (Step 05)."""

    def test_stats_file_produced(self) -> None:
        """Returns File ending in _bcftools_stats.txt."""
        with tempfile.TemporaryDirectory() as tmp:
            vcf = Path(tmp) / "cohort.vcf.gz"
            vcf.write_text("vcf")

            def fake_run_tool(cmd, sif, bind_paths):
                # cmd is ["bash", "-c", pipeline_str]; create the output
                import re
                pipeline_str = cmd[2]
                m = re.search(r">\s+(\S+)", pipeline_str)
                if m:
                    Path(m.group(1)).write_text("stats")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                result = bcftools_stats(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                )

        self.assertTrue(result.path.endswith("_bcftools_stats.txt"))

    def test_path_is_shell_quoted(self) -> None:
        """vcf path appears shell-quoted in the bcftools command."""
        with tempfile.TemporaryDirectory() as tmp:
            vcf = Path(tmp) / "my cohort.vcf.gz"
            vcf.write_text("vcf")

            captured_cmds: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmds.append(list(cmd))
                import re
                m = re.search(r">\s+(\S+)", cmd[2])
                if m:
                    Path(m.group(1)).write_text("stats")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                bcftools_stats(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                )

        pipeline_str = captured_cmds[0][2]
        self.assertIn("my cohort", pipeline_str)


class MultiqcSummarizeTests(TestCase):
    """Tests for multiqc_summarize task (Step 05)."""

    def test_empty_qc_inputs_raises(self) -> None:
        """ValueError when qc_inputs is empty."""
        with self.assertRaises(ValueError):
            multiqc_summarize(qc_inputs=[], cohort_id="cohort1")

    def test_copy_semantics_produce_scan_root(self) -> None:
        """All inputs are copied into the scan root before MultiQC runs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            qc1 = tmp_path / "s1_wgs.txt"
            qc2 = tmp_path / "s1_insert.txt"
            qc1.write_text("wgs")
            qc2.write_text("insert")

            scan_roots: list[Path] = []

            def fake_run_tool(cmd, sif, bind_paths):
                # cmd is ["multiqc", scan_root, ...]
                scan_roots.append(Path(cmd[1]))
                report = Path(cmd[cmd.index("-o") + 1]) / cmd[cmd.index("-n") + 1]
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text("html")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                multiqc_summarize(
                    qc_inputs=[File(path=str(qc1)), File(path=str(qc2))],
                    cohort_id="cohort1",
                )

        scan_root = scan_roots[0]
        files_in_scan = list(scan_root.iterdir())
        self.assertEqual(len(files_in_scan), 2)

    def test_report_path_in_manifest(self) -> None:
        """Manifest outputs contain multiqc_report_html."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            qc1 = tmp_path / "s1_wgs.txt"
            qc1.write_text("wgs")

            captured_manifests: list[dict] = []

            def fake_run_tool(cmd, sif, bind_paths):
                report = Path(cmd[cmd.index("-o") + 1]) / cmd[cmd.index("-n") + 1]
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text("html")

            with (
                patch.object(variant_calling, "run_tool", side_effect=fake_run_tool),
                patch.object(variant_calling, "_write_json",
                             side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                multiqc_summarize(
                    qc_inputs=[File(path=str(qc1))],
                    cohort_id="cohort1",
                )

        self.assertIn("multiqc_report_html", captured_manifests[0]["outputs"])


class SnpeffAnnotateTests(TestCase):
    """Tests for snpeff_annotate task (Step 06)."""

    def test_annotated_vcf_emitted(self) -> None:
        """Returns (annotated_vcf, genes_txt) tuple; both are File instances."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf = tmp_path / "cohort.vcf"
            vcf.write_text("vcf")
            data_dir = tmp_path / "snpeff_data"
            data_dir.mkdir()

            def fake_run_tool(cmd, sif, bind_paths):
                import re
                pipeline_str = cmd[2]
                m = re.search(r">\s+(\S+)", pipeline_str)
                if m:
                    out = Path(m.group(1))
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("annotated_vcf_content")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                annotated, genes = snpeff_annotate(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                    snpeff_database="GRCh38.105",
                    snpeff_data_dir=str(data_dir),
                )

        self.assertTrue(annotated.path.endswith("_snpeff.vcf"))

    def test_data_dir_quoted_and_bound(self) -> None:
        """snpeff_data_dir appears shell-quoted in the command."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf = tmp_path / "cohort.vcf"
            vcf.write_text("vcf")
            data_dir = tmp_path / "my snpeff data"
            data_dir.mkdir()

            captured_cmds: list[list[str]] = []

            def fake_run_tool(cmd, sif, bind_paths):
                captured_cmds.append(list(cmd))
                import re
                m = re.search(r">\s+(\S+)", cmd[2])
                if m:
                    out = Path(m.group(1))
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("ann")

            with patch.object(variant_calling, "run_tool", side_effect=fake_run_tool):
                snpeff_annotate(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                    snpeff_database="GRCh38.105",
                    snpeff_data_dir=str(data_dir),
                )

        pipeline_str = captured_cmds[0][2]
        self.assertIn("my snpeff data", pipeline_str)
        bound_dirs = [str(p) for p in captured_cmds[0]]
        # data_dir should appear in bind_paths
        from flyte.io import Dir
        self.assertIn(str(data_dir), pipeline_str)

    def test_missing_output_raises(self) -> None:
        """FileNotFoundError when output VCF absent after run."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf = tmp_path / "cohort.vcf"
            vcf.write_text("vcf")
            data_dir = tmp_path / "snpeff_data"
            data_dir.mkdir()

            with patch.object(variant_calling, "run_tool"):
                with self.assertRaises(FileNotFoundError):
                    snpeff_annotate(
                        input_vcf=File(path=str(vcf)),
                        cohort_id="cohort1",
                        snpeff_database="GRCh38.105",
                        snpeff_data_dir=str(data_dir),
                    )

    def test_genes_txt_optional_in_manifest(self) -> None:
        """When genes_txt is absent, manifest output reads '' instead of raising."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf = tmp_path / "cohort.vcf"
            vcf.write_text("vcf")
            data_dir = tmp_path / "snpeff_data"
            data_dir.mkdir()

            captured_manifests: list[dict] = []

            def fake_run_tool(cmd, sif, bind_paths):
                import re
                m = re.search(r">\s+(\S+)", cmd[2])
                if m:
                    out = Path(m.group(1))
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("ann")
                    # Do NOT create genes_txt

            with (
                patch.object(variant_calling, "run_tool", side_effect=fake_run_tool),
                patch.object(variant_calling, "_write_json",
                             side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                snpeff_annotate(
                    input_vcf=File(path=str(vcf)),
                    cohort_id="cohort1",
                    snpeff_database="GRCh38.105",
                    snpeff_data_dir=str(data_dir),
                )

        m = captured_manifests[0]
        # genes_txt missing → empty string, not an error
        self.assertEqual(m["outputs"]["snpeff_genes_txt"], "")


# ---------------------------------------------------------------------------
# On-ramp reference task: my_custom_filter
# ---------------------------------------------------------------------------

_MY_FILTER_SYNTHETIC_VCF = (
    "##fileformat=VCFv4.2\n"
    "##FILTER=<ID=PASS,Description=\"All filters passed\">\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    "chr20\t100\t.\tA\tT\t10.0\tPASS\t.\n"
    "chr20\t200\t.\tC\tG\t50.0\tPASS\t.\n"
    "chr20\t300\t.\tT\tA\t.\tPASS\t.\n"
)


class MyCustomFilterInvocationTests(TestCase):
    """Layer 2: invoke my_custom_filter directly via flyte_stub File.

    This is the first pure-Python task in the repo: no run_tool subprocess,
    no patch.object(config, 'run_tool', ...). Call directly and assert outputs.
    """

    def _run(self, min_qual: float = 30.0) -> tuple[str, dict, str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf_file = tmp_path / "input.vcf"
            vcf_file.write_text(_MY_FILTER_SYNTHETIC_VCF)

            result = my_custom_filter(
                input_vcf=File(path=str(vcf_file)),
                min_qual=min_qual,
            )
            out_path = Path(result.path)
            out_content = out_path.read_text()
            manifest_path = out_path.parent / "run_manifest_my_custom_filter.json"
            manifest = json.loads(manifest_path.read_text())
        return out_content, manifest, str(out_path)

    def test_returns_vcf_file(self):
        _, _, out_path = self._run()
        self.assertTrue(out_path.endswith(".vcf"))

    def test_low_qual_record_filtered_out(self):
        content, _, _ = self._run(min_qual=30.0)
        self.assertNotIn("chr20\t100\t", content)

    def test_high_qual_record_retained(self):
        content, _, _ = self._run(min_qual=30.0)
        self.assertIn("chr20\t200\t", content)

    def test_missing_qual_filtered_out(self):
        content, _, _ = self._run(min_qual=30.0)
        # chr20 pos 300 has QUAL=. → dropped
        self.assertNotIn("chr20\t300\t", content)

    def test_headers_preserved(self):
        content, _, _ = self._run()
        header_lines = [l for l in content.splitlines() if l.startswith("#")]
        self.assertGreater(len(header_lines), 0)

    def test_manifest_stage_name(self):
        _, manifest, _ = self._run()
        self.assertEqual(manifest["stage"], "my_custom_filter")

    def test_manifest_contains_output_key(self):
        _, manifest, out_path = self._run()
        self.assertIn("my_filtered_vcf", manifest["outputs"])
        self.assertEqual(manifest["outputs"]["my_filtered_vcf"], out_path)

    def test_manifest_file_written_alongside_output(self):
        _, _, out_path = self._run()
        manifest_path = Path(out_path).parent / "run_manifest_my_custom_filter.json"
        self.assertTrue(manifest_path.exists())

    def test_manifest_records_filter_stats(self):
        _, manifest, _ = self._run(min_qual=30.0)
        self.assertIn("filter_stats", manifest)
        stats = manifest["filter_stats"]
        # The synthetic VCF has 3 data lines: QUAL=10 (drop), QUAL=50 (keep),
        # QUAL=. (drop). No malformed lines.
        self.assertEqual(stats["records_kept"], 1)
        self.assertEqual(stats["low_qual_dropped"], 1)
        self.assertEqual(stats["missing_qual_dropped"], 1)
        self.assertEqual(stats["malformed_lines_dropped"], 0)


class MyCustomFilterRegistryTests(TestCase):
    """Layer 3: assert RegistryEntry shape and manifest-output consistency."""

    def setUp(self) -> None:
        from flytetest.registry import get_entry
        self.entry = get_entry("my_custom_filter")

    def test_entry_exists(self):
        self.assertIsNotNone(self.entry)

    def test_category_is_task(self):
        self.assertEqual(self.entry.category, "task")

    def test_pipeline_family(self):
        self.assertEqual(self.entry.compatibility.pipeline_family, "variant_calling")

    def test_accepted_planner_types(self):
        self.assertEqual(
            self.entry.compatibility.accepted_planner_types, ("VariantCallSet",)
        )

    def test_produced_planner_types(self):
        self.assertEqual(
            self.entry.compatibility.produced_planner_types, ("VariantCallSet",)
        )

    def test_showcase_module(self):
        self.assertEqual(self.entry.showcase_module, "flytetest.tasks.variant_calling")

    def test_output_key_in_manifest_output_keys(self):
        output_names = {f.name for f in self.entry.outputs}
        self.assertIn("my_filtered_vcf", output_names)
        self.assertIn("my_filtered_vcf", MANIFEST_OUTPUT_KEYS)

    def test_input_names_match_task_signature(self):
        input_names = {f.name for f in self.entry.inputs}
        self.assertIn("input_vcf", input_names)
        self.assertIn("min_qual", input_names)

    def test_runtime_images_empty_for_pure_python(self):
        images = self.entry.compatibility.execution_defaults.get("runtime_images", {})
        self.assertEqual(images, {})

    def test_pipeline_stage_order(self):
        self.assertEqual(self.entry.compatibility.pipeline_stage_order, 22)


class MyCustomFilterMCPExposureTests(TestCase):
    """Layer 4: MCP discovery and scalar-parameter subtraction."""

    def test_appears_in_supported_task_names(self):
        from flytetest.mcp_contract import SUPPORTED_TASK_NAMES
        self.assertIn("my_custom_filter", SUPPORTED_TASK_NAMES)

    def test_task_parameters_entry_exact(self):
        from flytetest.server import TASK_PARAMETERS
        self.assertIn("my_custom_filter", TASK_PARAMETERS)
        self.assertEqual(
            TASK_PARAMETERS["my_custom_filter"],
            (("input_vcf", True), ("min_qual", False)),
        )

    def test_scalar_params_with_and_without_typed_bindings(self):
        """Document the binding-key vs parameter-name relationship for my_custom_filter.

        The binding inner key is ``vcf_path`` (the VariantCallSet planner-type
        field name). The task parameter / scalar-input key is ``input_vcf``.
        These two keys are intentionally distinct — that distinction is what
        prevents the resolver classification collision fixed in this milestone.
        """
        from flytetest.server import _scalar_params_for_task

        # Without any binding: every TASK_PARAMETERS entry remains scalar.
        unbound = [name for name, _ in _scalar_params_for_task("my_custom_filter", bindings={})]
        self.assertEqual(set(unbound), {"input_vcf", "min_qual"})

        # With the canonical VariantCallSet binding the resolver subtracts
        # the planner-type field name (``vcf_path``) from candidate scalar
        # params. Because that name does NOT match any TASK_PARAMETERS entry
        # (we deliberately use ``input_vcf``), nothing is removed — and the
        # function signature still gets ``input_vcf`` from the inputs dict.
        bound = [
            name
            for name, _ in _scalar_params_for_task(
                "my_custom_filter",
                bindings={"VariantCallSet": {"vcf_path": "/tmp/x.vcf"}},
            )
        ]
        self.assertEqual(set(bound), {"input_vcf", "min_qual"})

        # Regression guard: if a future refactor renames the task parameter
        # back to ``vcf_path``, the binding inner key WILL match and silently
        # strip the parameter from validation — recreating the bug fixed here.
        collision_bound = [
            name
            for name, _ in _scalar_params_for_task(
                "my_custom_filter",
                bindings={"VariantCallSet": {"input_vcf": "/tmp/x.vcf"}},
            )
        ]
        self.assertNotIn("input_vcf", collision_bound)

    def test_min_qual_is_not_required(self):
        from flytetest.server import TASK_PARAMETERS
        for name, required in TASK_PARAMETERS["my_custom_filter"]:
            if name == "min_qual":
                self.assertFalse(required, "min_qual has a default and must not be required")


# ---------------------------------------------------------------------------
# Tutorial chapter 07 toy task: count_vcf_records
# ---------------------------------------------------------------------------

_COUNT_RECORDS_SYNTHETIC_VCF = (
    "##fileformat=VCFv4.2\n"
    "##contig=<ID=chr20>\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    "chr20\t100\t.\tA\tT\t10.0\tPASS\t.\n"
    "chr20\t200\t.\tC\tG\t50.0\tPASS\t.\n"
    "\n"
    "chr20\t300\t.\tT\tA\t.\tPASS\t.\n"
)


class CountVcfRecordsUnitTests(TestCase):
    """Layer 1: pure-Python tests for the helper.

    These tests do not involve Flyte at all — the helper takes a Path and
    returns a dict. The tutorial uses this layer to demonstrate that logic
    bugs are best caught at the unit level, not at integration time.
    """

    def _write(self, body: str) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="count_vcf_records_unit_"))
        path = tmp / "input.vcf"
        path.write_text(body)
        return path

    def test_counts_header_and_data_lines(self):
        from flytetest.tasks._filter_helpers import count_vcf_records as count_pure
        counts = count_pure(self._write(_COUNT_RECORDS_SYNTHETIC_VCF))
        self.assertEqual(counts["header_lines"], 3)
        self.assertEqual(counts["data_lines"], 3)

    def test_blank_lines_are_ignored(self):
        from flytetest.tasks._filter_helpers import count_vcf_records as count_pure
        body = "##fileformat=VCFv4.2\n\n\n#CHROM\tPOS\n"
        counts = count_pure(self._write(body))
        self.assertEqual(counts["header_lines"], 2)
        self.assertEqual(counts["data_lines"], 0)

    def test_data_only_file(self):
        from flytetest.tasks._filter_helpers import count_vcf_records as count_pure
        body = "chr1\t1\t.\tA\tT\t.\t.\t.\nchr1\t2\t.\tA\tT\t.\t.\t.\n"
        counts = count_pure(self._write(body))
        self.assertEqual(counts["header_lines"], 0)
        self.assertEqual(counts["data_lines"], 2)

    def test_empty_file(self):
        from flytetest.tasks._filter_helpers import count_vcf_records as count_pure
        counts = count_pure(self._write(""))
        self.assertEqual(counts, {"header_lines": 0, "data_lines": 0})


class CountVcfRecordsInvocationTests(TestCase):
    """Layer 2: invoke count_vcf_records directly via flyte_stub File.

    Asserts the manifest envelope is well-formed and the JSON output exists
    next to the manifest. Mirrors the MyCustomFilterInvocationTests shape so
    readers can compare the two side by side.
    """

    def _run(self) -> tuple[dict, dict, str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf_file = tmp_path / "input.vcf"
            vcf_file.write_text(_COUNT_RECORDS_SYNTHETIC_VCF)

            result = count_vcf_records(vcf=File(path=str(vcf_file)))
            out_path = Path(result.path)
            counts = json.loads(out_path.read_text())
            manifest_path = out_path.parent / "run_manifest_count_vcf_records.json"
            manifest = json.loads(manifest_path.read_text())
        return counts, manifest, str(out_path)

    def test_returns_json_file(self):
        _, _, out_path = self._run()
        self.assertTrue(out_path.endswith(".json"))

    def test_counts_match_synthetic_input(self):
        counts, _, _ = self._run()
        self.assertEqual(counts["header_lines"], 3)
        self.assertEqual(counts["data_lines"], 3)

    def test_manifest_stage_name(self):
        _, manifest, _ = self._run()
        self.assertEqual(manifest["stage"], "count_vcf_records")

    def test_manifest_contains_output_key(self):
        _, manifest, out_path = self._run()
        self.assertIn("vcf_record_counts", manifest["outputs"])
        self.assertEqual(manifest["outputs"]["vcf_record_counts"], out_path)

    def test_manifest_file_written_alongside_output(self):
        _, _, out_path = self._run()
        manifest_path = Path(out_path).parent / "run_manifest_count_vcf_records.json"
        self.assertTrue(manifest_path.exists())

    def test_manifest_records_counts(self):
        _, manifest, _ = self._run()
        self.assertIn("record_counts", manifest)
        self.assertEqual(manifest["record_counts"]["data_lines"], 3)


class CountVcfRecordsRegistryTests(TestCase):
    """Layer 3: assert RegistryEntry shape and manifest-output consistency."""

    def setUp(self) -> None:
        from flytetest.registry import get_entry
        self.entry = get_entry("count_vcf_records")

    def test_entry_exists(self):
        self.assertIsNotNone(self.entry)

    def test_category_is_task(self):
        self.assertEqual(self.entry.category, "task")

    def test_pipeline_family(self):
        self.assertEqual(self.entry.compatibility.pipeline_family, "variant_calling")

    def test_accepted_planner_types(self):
        self.assertEqual(
            self.entry.compatibility.accepted_planner_types, ("VariantCallSet",)
        )

    def test_showcase_module(self):
        self.assertEqual(self.entry.showcase_module, "flytetest.tasks.variant_calling")

    def test_output_key_in_manifest_output_keys(self):
        output_names = {f.name for f in self.entry.outputs}
        self.assertIn("vcf_record_counts", output_names)
        self.assertIn("vcf_record_counts", MANIFEST_OUTPUT_KEYS)

    def test_input_names_match_task_signature(self):
        input_names = {f.name for f in self.entry.inputs}
        self.assertEqual(input_names, {"vcf"})

    def test_runtime_images_empty_for_pure_python(self):
        images = self.entry.compatibility.execution_defaults.get("runtime_images", {})
        self.assertEqual(images, {})


class CountVcfRecordsMCPExposureTests(TestCase):
    """Layer 4: MCP discovery and flat-tool importability."""

    def test_appears_in_supported_task_names(self):
        from flytetest.mcp_contract import SUPPORTED_TASK_NAMES
        self.assertIn("count_vcf_records", SUPPORTED_TASK_NAMES)

    def test_flat_tool_importable_with_docstring(self):
        from flytetest.mcp_tools import vc_count_records
        self.assertTrue(callable(vc_count_records))
        self.assertTrue(vc_count_records.__doc__)

    def test_task_parameters_entry_exact(self):
        from flytetest.server import TASK_PARAMETERS
        self.assertIn("count_vcf_records", TASK_PARAMETERS)
        self.assertEqual(
            TASK_PARAMETERS["count_vcf_records"],
            (("vcf", True),),
        )

    def test_listed_in_flat_tools(self):
        from flytetest.mcp_contract import FLAT_TOOLS, VC_COUNT_RECORDS_TOOL_NAME
        self.assertEqual(VC_COUNT_RECORDS_TOOL_NAME, "vc_count_records")
        self.assertIn(VC_COUNT_RECORDS_TOOL_NAME, FLAT_TOOLS)


class ApplyCustomFilterWorkflowRegistryTests(TestCase):
    """Registry shape and MCP exposure for the on-ramp composed workflow."""

    def setUp(self) -> None:
        from flytetest.registry import get_entry
        self.entry = get_entry("apply_custom_filter")

    def test_entry_exists(self):
        self.assertIsNotNone(self.entry)

    def test_category_is_workflow(self):
        self.assertEqual(self.entry.category, "workflow")

    def test_pipeline_family(self):
        self.assertEqual(self.entry.compatibility.pipeline_family, "variant_calling")

    def test_accepted_planner_types(self):
        self.assertEqual(
            self.entry.compatibility.accepted_planner_types, ("VariantCallSet",)
        )

    def test_produced_planner_types(self):
        self.assertEqual(
            self.entry.compatibility.produced_planner_types, ("VariantCallSet",)
        )

    def test_showcase_module(self):
        self.assertEqual(
            self.entry.showcase_module, "flytetest.workflows.variant_calling"
        )

    def test_runtime_images_empty_for_pure_python(self):
        images = self.entry.compatibility.execution_defaults.get("runtime_images", {})
        self.assertEqual(images, {})

    def test_pipeline_stage_order(self):
        self.assertEqual(self.entry.compatibility.pipeline_stage_order, 23)

    def test_output_key_in_manifest_output_keys(self):
        output_names = {f.name for f in self.entry.outputs}
        self.assertIn("my_filtered_vcf", output_names)
        self.assertIn("my_filtered_vcf", MANIFEST_OUTPUT_KEYS)

    def test_input_names(self):
        input_names = {f.name for f in self.entry.inputs}
        self.assertEqual(input_names, {"input_vcf", "min_qual"})

    def test_appears_in_supported_workflow_names(self):
        from flytetest.mcp_contract import SUPPORTED_WORKFLOW_NAMES
        self.assertIn("apply_custom_filter", SUPPORTED_WORKFLOW_NAMES)

    def test_flat_tool_registered(self):
        from flytetest.mcp_contract import FLAT_TOOLS, TOOL_DESCRIPTIONS
        self.assertIn("vc_apply_custom_filter", FLAT_TOOLS)
        self.assertIn("vc_apply_custom_filter", TOOL_DESCRIPTIONS)


class VcCustomFilterMCPContractTests(TestCase):
    """Contract registration for the task-level flat tool vc_custom_filter."""

    def test_in_flat_tools(self):
        from flytetest.mcp_contract import FLAT_TOOLS
        self.assertIn("vc_custom_filter", FLAT_TOOLS)

    def test_has_tool_description(self):
        from flytetest.mcp_contract import TOOL_DESCRIPTIONS
        self.assertIn("vc_custom_filter", TOOL_DESCRIPTIONS)
        self.assertIn("QUAL", TOOL_DESCRIPTIONS["vc_custom_filter"])

    def test_in_mcp_tool_names(self):
        from flytetest.mcp_contract import MCP_TOOL_NAMES
        self.assertIn("vc_custom_filter", MCP_TOOL_NAMES)
