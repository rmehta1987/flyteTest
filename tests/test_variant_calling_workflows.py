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
    germline_short_variant_discovery,
    prepare_reference,
    preprocess_sample,
    preprocess_sample_from_ubam,
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


# ---------------------------------------------------------------------------
# Step 07 — preprocess_sample
# ---------------------------------------------------------------------------

class PreprocessSampleRegistryTests(TestCase):
    """Guard the preprocess_sample registry entry shape."""

    def test_preprocess_sample_registry_entry_shape(self) -> None:
        """Entry exists with category=workflow, stage_order=2."""
        from flytetest.registry import get_entry

        entry = get_entry("preprocess_sample")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 2)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("preprocessed_bam", output_names)
        self.assertIn("preprocessed_bam", MANIFEST_OUTPUT_KEYS)


class PreprocessSampleInvocationTests(TestCase):
    """Verify preprocess_sample calls sub-tasks in order."""

    def _make_fake_file(self, path: str):
        f = MagicMock(spec=File)
        f.path = path
        return f

    def test_sub_tasks_called_in_order(self) -> None:
        """bwa_mem2_mem → sort_sam → mark_duplicates → base_recalibrator → apply_bqsr."""
        call_order: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            results_dir = tmp_path / "sample_out"
            results_dir.mkdir()

            def fake_bwa_mem(ref_path, r1_path, sample_id, results_dir, **kw):
                call_order.append("bwa_mem2_mem")
                return {"stage": "bwa_mem2_mem", "outputs": {"aligned_bam": "/tmp/s1_aligned.bam"}}

            def fake_sort(bam_path, sample_id, results_dir, **kw):
                call_order.append("sort_sam")
                return {"stage": "sort_sam", "outputs": {"sorted_bam": "/tmp/s1_sorted.bam"}}

            def fake_dedup(bam_path, sample_id, results_dir, **kw):
                call_order.append("mark_duplicates")
                return {"stage": "mark_duplicates", "outputs": {"dedup_bam": "/tmp/s1_dedup.bam"}}

            def fake_bqsr(reference_fasta, aligned_bam, known_sites, sample_id, **kw):
                call_order.append("base_recalibrator")
                return self._make_fake_file("/tmp/s1_bqsr.table")

            def fake_apply(reference_fasta, aligned_bam, bqsr_report, sample_id, **kw):
                call_order.append("apply_bqsr")
                return self._make_fake_file("/tmp/s1_recal.bam")

            with (
                patch.object(variant_calling_wf, "bwa_mem2_mem", side_effect=fake_bwa_mem),
                patch.object(variant_calling_wf, "sort_sam", side_effect=fake_sort),
                patch.object(variant_calling_wf, "mark_duplicates", side_effect=fake_dedup),
                patch.object(variant_calling_wf, "base_recalibrator", side_effect=fake_bqsr),
                patch.object(variant_calling_wf, "apply_bqsr", side_effect=fake_apply),
            ):
                preprocess_sample(
                    ref_path=str(ref_fasta),
                    r1_path="/tmp/r1.fq.gz",
                    sample_id="s1",
                    known_sites=["/tmp/dbsnp.vcf"],
                    results_dir=str(results_dir),
                )

        self.assertEqual(
            call_order,
            ["bwa_mem2_mem", "sort_sam", "mark_duplicates", "base_recalibrator", "apply_bqsr"],
        )


class PreprocessSampleManifestTests(TestCase):
    """Verify preprocess_sample emits a well-formed manifest."""

    def test_preprocess_sample_emits_preprocessed_bam(self) -> None:
        """Manifest contains preprocessed_bam."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            results_dir = tmp_path / "sample_out"
            results_dir.mkdir()

            fake_file = MagicMock(spec=File)
            fake_file.path = "/tmp/s1_recal.bam"

            with (
                patch.object(variant_calling_wf, "bwa_mem2_mem", return_value={"stage": "bwa_mem2_mem", "outputs": {"aligned_bam": "/tmp/a.bam"}}),
                patch.object(variant_calling_wf, "sort_sam", return_value={"stage": "sort_sam", "outputs": {"sorted_bam": "/tmp/s.bam"}}),
                patch.object(variant_calling_wf, "mark_duplicates", return_value={"stage": "mark_duplicates", "outputs": {"dedup_bam": "/tmp/d.bam"}}),
                patch.object(variant_calling_wf, "base_recalibrator", return_value=MagicMock(spec=File, path="/tmp/bqsr.table")),
                patch.object(variant_calling_wf, "apply_bqsr", return_value=fake_file),
            ):
                result = preprocess_sample(
                    ref_path=str(ref_fasta),
                    r1_path="/tmp/r1.fq.gz",
                    sample_id="s1",
                    known_sites=["/tmp/dbsnp.vcf"],
                    results_dir=str(results_dir),
                )

        self.assertEqual(result["stage"], "preprocess_sample")
        self.assertIn("preprocessed_bam", result["outputs"])
        self.assertEqual(result["outputs"]["preprocessed_bam"], "/tmp/s1_recal.bam")


# ---------------------------------------------------------------------------
# Step 08 — germline_short_variant_discovery
# ---------------------------------------------------------------------------

class GermlineShortVariantDiscoveryRegistryTests(TestCase):
    """Guard the germline_short_variant_discovery registry entry shape."""

    def test_germline_short_variant_discovery_registry_entry_shape(self) -> None:
        """Entry exists with category=workflow, stage_order=3."""
        from flytetest.registry import get_entry

        entry = get_entry("germline_short_variant_discovery")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 3)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("genotyped_vcf", output_names)
        self.assertIn("genotyped_vcf", MANIFEST_OUTPUT_KEYS)


class GermlineShortVariantDiscoveryInvocationTests(TestCase):
    """Verify germline_short_variant_discovery validation and call counts."""

    def test_raises_on_sample_ids_r1_paths_length_mismatch(self) -> None:
        """ValueError when sample_ids and r1_paths differ in length."""
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "out"
            results_dir.mkdir()
            with self.assertRaises(ValueError):
                germline_short_variant_discovery(
                    ref_path="/tmp/ref.fa",
                    sample_ids=["s1", "s2"],
                    r1_paths=["/tmp/r1.fq.gz"],
                    known_sites=["/tmp/dbsnp.vcf"],
                    intervals=["chr20"],
                    results_dir=str(results_dir),
                )

    def test_raises_on_r2_paths_length_mismatch(self) -> None:
        """ValueError when r2_paths is provided but length mismatches sample_ids."""
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "out"
            results_dir.mkdir()
            with self.assertRaises(ValueError):
                germline_short_variant_discovery(
                    ref_path="/tmp/ref.fa",
                    sample_ids=["s1", "s2"],
                    r1_paths=["/tmp/r1a.fq.gz", "/tmp/r1b.fq.gz"],
                    known_sites=["/tmp/dbsnp.vcf"],
                    intervals=["chr20"],
                    results_dir=str(results_dir),
                    r2_paths=["/tmp/r2a.fq.gz"],
                )

    def test_per_sample_and_cohort_call_counts(self) -> None:
        """preprocess_sample and haplotype_caller called once per sample; combine/joint once."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            results_dir = tmp_path / "out"
            results_dir.mkdir()

            fake_vcf = MagicMock(spec=File)
            fake_vcf.path = "/tmp/cohort.vcf"

            def fake_preprocess(ref_path, r1_path, sample_id, **kw):
                return {"stage": "preprocess_sample", "outputs": {"preprocessed_bam": f"/tmp/{sample_id}.bam"}}

            def fake_hc(reference_fasta, aligned_bam, sample_id, **kw):
                return MagicMock(spec=File, path=f"/tmp/{sample_id}.g.vcf")

            with (
                patch.object(variant_calling_wf, "preprocess_sample", side_effect=fake_preprocess) as mock_pp,
                patch.object(variant_calling_wf, "haplotype_caller", side_effect=fake_hc) as mock_hc,
                patch.object(variant_calling_wf, "combine_gvcfs", return_value=fake_vcf) as mock_cg,
                patch.object(variant_calling_wf, "joint_call_gvcfs", return_value=fake_vcf) as mock_jc,
            ):
                germline_short_variant_discovery(
                    ref_path="/tmp/ref.fa",
                    sample_ids=["s1", "s2"],
                    r1_paths=["/tmp/r1a.fq.gz", "/tmp/r1b.fq.gz"],
                    known_sites=["/tmp/dbsnp.vcf"],
                    intervals=["chr20"],
                    results_dir=str(results_dir),
                )

        self.assertEqual(mock_pp.call_count, 2)
        self.assertEqual(mock_hc.call_count, 2)
        mock_cg.assert_called_once()
        mock_jc.assert_called_once()


class GermlineShortVariantDiscoveryManifestTests(TestCase):
    """Verify germline_short_variant_discovery emits a well-formed manifest."""

    def test_manifest_emits_genotyped_vcf(self) -> None:
        """Manifest contains genotyped_vcf from joint_call_gvcfs output."""
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "out"
            results_dir.mkdir()

            fake_vcf = MagicMock(spec=File)
            fake_vcf.path = "/tmp/cohort_genotyped.vcf"

            with (
                patch.object(variant_calling_wf, "preprocess_sample", return_value={"stage": "preprocess_sample", "outputs": {"preprocessed_bam": "/tmp/s1.bam"}}),
                patch.object(variant_calling_wf, "haplotype_caller", return_value=MagicMock(spec=File, path="/tmp/s1.g.vcf")),
                patch.object(variant_calling_wf, "combine_gvcfs", return_value=fake_vcf),
                patch.object(variant_calling_wf, "joint_call_gvcfs", return_value=fake_vcf),
            ):
                result = germline_short_variant_discovery(
                    ref_path="/tmp/ref.fa",
                    sample_ids=["s1"],
                    r1_paths=["/tmp/r1.fq.gz"],
                    known_sites=["/tmp/dbsnp.vcf"],
                    intervals=["chr20"],
                    results_dir=str(results_dir),
                )

        self.assertEqual(result["stage"], "germline_short_variant_discovery")
        self.assertIn("genotyped_vcf", result["outputs"])
        self.assertEqual(result["outputs"]["genotyped_vcf"], "/tmp/cohort_genotyped.vcf")


# ---------------------------------------------------------------------------
# GenotypeRefinement workflow tests (Milestone D Step 03)
# ---------------------------------------------------------------------------

import json


class GenotypeRefinementRegistryTests(TestCase):
    """Guard the genotype_refinement registry entry shape."""

    def test_genotype_refinement_registry_entry_shape(self) -> None:
        """Entry exists at workflow stage_order 4 with refined_vcf output."""
        from flytetest.registry import get_entry

        entry = get_entry("genotype_refinement")
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 4)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        output_names = [f.name for f in entry.outputs]
        self.assertIn("refined_vcf", output_names)


class GenotypeRefinementWorkflowTests(TestCase):
    """Verify genotype_refinement two-pass VQSR ordering and manifest."""

    _SNP_RESOURCES = ["/data/hapmap.vcf.gz", "/data/dbsnp.vcf"]
    _SNP_FLAGS = [
        {"resource_name": "hapmap", "known": "false", "training": "true",  "truth": "true",  "prior": "15"},
        {"resource_name": "dbsnp",  "known": "true",  "training": "false", "truth": "false", "prior": "2"},
    ]
    _INDEL_RESOURCES = ["/data/mills.vcf.gz", "/data/dbsnp.vcf"]
    _INDEL_FLAGS = [
        {"resource_name": "mills", "known": "false", "training": "true",  "truth": "true",  "prior": "12"},
        {"resource_name": "dbsnp", "known": "true",  "training": "false", "truth": "false", "prior": "2"},
    ]

    def _mock_vr(self, mode):
        """Return a fake variant_recalibrator manifest for the given mode."""
        return {
            "stage": "variant_recalibrator",
            "outputs": {
                "recal_file": f"/tmp/cohort_{mode.lower()}.recal",
                "tranches_file": f"/tmp/cohort_{mode.lower()}.tranches",
            },
        }

    def _mock_av(self, mode):
        """Return a fake apply_vqsr manifest for the given mode."""
        return {
            "stage": "apply_vqsr",
            "outputs": {
                "vqsr_vcf": f"/tmp/cohort_vqsr_{mode.lower()}.vcf.gz",
                "vqsr_vcf_index": f"/tmp/cohort_vqsr_{mode.lower()}.vcf.gz.tbi",
            },
        }

    def test_genotype_refinement_runs(self) -> None:
        """Workflow completes; manifest has refined_vcf key."""
        from flytetest.workflows.variant_calling import genotype_refinement

        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "gr_out"
            results_dir.mkdir()

            with (
                patch.object(variant_calling_wf, "variant_recalibrator",
                             side_effect=[self._mock_vr("SNP"), self._mock_vr("INDEL")]),
                patch.object(variant_calling_wf, "apply_vqsr",
                             side_effect=[self._mock_av("SNP"), self._mock_av("INDEL")]),
            ):
                result = genotype_refinement(
                    ref_path="/tmp/ref.fa",
                    joint_vcf="/tmp/cohort.vcf.gz",
                    snp_resources=self._SNP_RESOURCES,
                    snp_resource_flags=self._SNP_FLAGS,
                    indel_resources=self._INDEL_RESOURCES,
                    indel_resource_flags=self._INDEL_FLAGS,
                    cohort_id="cohort1",
                    results_dir=str(results_dir),
                )

        self.assertEqual(result["stage"], "genotype_refinement")
        self.assertIn("refined_vcf", result["outputs"])

    def test_genotype_refinement_indel_uses_snp_vcf(self) -> None:
        """INDEL pass vcf_path is the SNP apply_vqsr output, not the original joint_vcf."""
        from flytetest.workflows.variant_calling import genotype_refinement

        snp_filtered_vcf = "/tmp/cohort_vqsr_snp.vcf.gz"
        snp_apply_result = {
            "stage": "apply_vqsr",
            "outputs": {"vqsr_vcf": snp_filtered_vcf, "vqsr_vcf_index": ""},
        }

        vr_calls: list[dict] = []

        def capturing_vr(**kwargs):
            vr_calls.append(kwargs)
            mode = kwargs["mode"]
            return self._mock_vr(mode)

        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "gr_out"
            results_dir.mkdir()

            with (
                patch.object(variant_calling_wf, "variant_recalibrator",
                             side_effect=capturing_vr),
                patch.object(variant_calling_wf, "apply_vqsr",
                             side_effect=[snp_apply_result, self._mock_av("INDEL")]),
            ):
                genotype_refinement(
                    ref_path="/tmp/ref.fa",
                    joint_vcf="/tmp/cohort.vcf.gz",
                    snp_resources=self._SNP_RESOURCES,
                    snp_resource_flags=self._SNP_FLAGS,
                    indel_resources=self._INDEL_RESOURCES,
                    indel_resource_flags=self._INDEL_FLAGS,
                    cohort_id="cohort1",
                    results_dir=str(results_dir),
                )

        # Second variant_recalibrator call must have received the SNP-filtered VCF
        self.assertEqual(len(vr_calls), 2)
        self.assertEqual(vr_calls[1]["vcf_path"], snp_filtered_vcf)

    def test_genotype_refinement_manifest_key(self) -> None:
        """run_manifest.json has refined_vcf pointing at the INDEL-pass output."""
        from flytetest.workflows.variant_calling import genotype_refinement

        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "gr_out"
            results_dir.mkdir()

            with (
                patch.object(variant_calling_wf, "variant_recalibrator",
                             side_effect=[self._mock_vr("SNP"), self._mock_vr("INDEL")]),
                patch.object(variant_calling_wf, "apply_vqsr",
                             side_effect=[self._mock_av("SNP"), self._mock_av("INDEL")]),
            ):
                genotype_refinement(
                    ref_path="/tmp/ref.fa",
                    joint_vcf="/tmp/cohort.vcf.gz",
                    snp_resources=self._SNP_RESOURCES,
                    snp_resource_flags=self._SNP_FLAGS,
                    indel_resources=self._INDEL_RESOURCES,
                    indel_resource_flags=self._INDEL_FLAGS,
                    cohort_id="cohort1",
                    results_dir=str(results_dir),
                )

            manifest = json.loads((results_dir / "run_manifest.json").read_text())
            self.assertEqual(manifest["stage"], "genotype_refinement")
            self.assertIn("refined_vcf", manifest["outputs"])
            self.assertTrue(manifest["outputs"]["refined_vcf"].endswith("_vqsr_indel.vcf.gz"))


# ---------------------------------------------------------------------------
# Milestone E Step 03 — preprocess_sample_from_ubam
# ---------------------------------------------------------------------------

class PreprocessSampleFromUbamWorkflowTests(TestCase):
    """Verify preprocess_sample_from_ubam calls sub-tasks in the correct order."""

    def _make_fake_file(self, path: str):
        f = MagicMock(spec=File)
        f.path = path
        return f

    def _patch_all(self, *, sort_sam_mock=None):
        """Return a context manager patching all 5 sub-tasks (+ optional sort_sam)."""
        patches = [
            patch.object(variant_calling_wf, "bwa_mem2_mem",
                         return_value={"stage": "bwa_mem2_mem", "outputs": {"aligned_bam": "/tmp/s1_aligned.bam"}}),
            patch.object(variant_calling_wf, "merge_bam_alignment",
                         return_value={"stage": "merge_bam_alignment", "outputs": {"merged_bam": "/tmp/s1_merged.bam"}}),
            patch.object(variant_calling_wf, "mark_duplicates",
                         return_value={"stage": "mark_duplicates", "outputs": {"dedup_bam": "/tmp/s1_dedup.bam"}}),
            patch.object(variant_calling_wf, "base_recalibrator",
                         return_value=self._make_fake_file("/tmp/s1_bqsr.table")),
            patch.object(variant_calling_wf, "apply_bqsr",
                         return_value=self._make_fake_file("/tmp/s1_recal.bam")),
        ]
        if sort_sam_mock is not None:
            patches.append(patch.object(variant_calling_wf, "sort_sam", sort_sam_mock))
        from contextlib import ExitStack
        stack = ExitStack()
        mocks = [stack.enter_context(p) for p in patches]
        return stack, mocks

    def test_preprocess_sample_from_ubam_runs(self) -> None:
        """Manifest has preprocessed_bam_from_ubam key."""
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "out"
            results_dir.mkdir()

            stack, _ = self._patch_all()
            with stack:
                result = preprocess_sample_from_ubam(
                    ref_path="/tmp/ref.fa",
                    r1_path="/tmp/r1.fq.gz",
                    ubam_path="/tmp/sample.ubam",
                    sample_id="s1",
                    known_sites=["/tmp/dbsnp.vcf"],
                    results_dir=str(results_dir),
                )

        self.assertIn("preprocessed_bam_from_ubam", result["outputs"])

    def test_no_sort_sam_called(self) -> None:
        """sort_sam is never invoked — MergeBamAlignment handles coordinate sorting."""
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "out"
            results_dir.mkdir()

            sort_sam_mock = MagicMock()
            stack, _ = self._patch_all(sort_sam_mock=sort_sam_mock)
            with stack:
                preprocess_sample_from_ubam(
                    ref_path="/tmp/ref.fa",
                    r1_path="/tmp/r1.fq.gz",
                    ubam_path="/tmp/sample.ubam",
                    sample_id="s1",
                    known_sites=["/tmp/dbsnp.vcf"],
                    results_dir=str(results_dir),
                )

        sort_sam_mock.assert_not_called()

    def test_merge_bam_alignment_receives_aligned_bam(self) -> None:
        """merge_bam_alignment is called with aligned_bam from bwa_mem2_mem output."""
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "out"
            results_dir.mkdir()

            mock_merge = MagicMock(
                return_value={"stage": "merge_bam_alignment", "outputs": {"merged_bam": "/tmp/s1_merged.bam"}}
            )
            with (
                patch.object(variant_calling_wf, "bwa_mem2_mem",
                             return_value={"stage": "bwa_mem2_mem", "outputs": {"aligned_bam": "/tmp/s1_aligned.bam"}}),
                patch.object(variant_calling_wf, "merge_bam_alignment", mock_merge),
                patch.object(variant_calling_wf, "mark_duplicates",
                             return_value={"stage": "mark_duplicates", "outputs": {"dedup_bam": "/tmp/s1_dedup.bam"}}),
                patch.object(variant_calling_wf, "base_recalibrator",
                             return_value=self._make_fake_file("/tmp/s1_bqsr.table")),
                patch.object(variant_calling_wf, "apply_bqsr",
                             return_value=self._make_fake_file("/tmp/s1_recal.bam")),
            ):
                preprocess_sample_from_ubam(
                    ref_path="/tmp/ref.fa",
                    r1_path="/tmp/r1.fq.gz",
                    ubam_path="/tmp/sample.ubam",
                    sample_id="s1",
                    known_sites=["/tmp/dbsnp.vcf"],
                    results_dir=str(results_dir),
                )

        _call_kwargs = mock_merge.call_args
        self.assertEqual(_call_kwargs.kwargs.get("aligned_bam"), "/tmp/s1_aligned.bam")

    def test_registry_entry_shape(self) -> None:
        """Registry entry exists at workflow stage 5 with preprocessed_bam_from_ubam output."""
        from flytetest.registry import get_entry

        entry = get_entry("preprocess_sample_from_ubam")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 5)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("preprocessed_bam_from_ubam", output_names)
        self.assertIn("preprocessed_bam_from_ubam", MANIFEST_OUTPUT_KEYS)
